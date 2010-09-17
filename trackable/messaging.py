from django.contrib.contenttypes.models import ContentType
from django.core.mail import mail_admins
from django.conf import settings
from django.db import connection

from carrot.connection import DjangoBrokerConnection
from carrot.messaging import Publisher, Consumer
from trackable import site, TrackableError
from trackable.models import Spider

import multiprocessing
import datetime
import warnings
import logging

try:
    import cPickle as pickle
except ImportError:
    import pickle

USER_AGENT_FILTERING = getattr(settings,'TRACKABLE_USER_AGENT_FILTERING', False)
REMOVE_MALFORMED_MESSAGES = getattr(settings,'TRACKABLE_REMOVE_MALFORMED_MESSAGES', False)
CAPTURE_CONNECTION_ERRORS = getattr(settings,'TRACKABLE_CAPTURE_CONNECTION_ERRORS', False)
PROCESS_NUM_MESSAGES = getattr(settings,'TRACKABLE_PROCESS_NUM_MESSAGES', 100)

UNDEFINED_AGENT = 'UNDEFINED_HTTP_USER_AGENT'

_connection_cache = {
    'connection': None,
    'queues': {
        'trackable': {}
        },
}


# TODO: make get_connection suck far less than it
#       currently does.
def get_connection(con_type='connection', op_name=None):
    if not _connection_cache['connection']:
        _connection_cache['connection'] = DjangoBrokerConnection()
    connection = _connection_cache['connection']

    if con_type == 'connection':
        return _connection_cache['connection']
    # elif not op_name:
    #     return _connection_cache['queues']

    queues = _connection_cache['queues']
    try:
        # queues[op_name]
        queues['trackable']['consumer']
    except KeyError:
        consumer = Consumer( \
            connection=connection,
            queue="trackable",
            exchange="trackable",
            routing_key="trackable",
            )
        queues['trackable']['consumer'] = consumer
    try:
        queues['trackable']['publisher']
    except KeyError:
        publisher = Publisher( \
                connection=connection,
                queue="trackable",
                exchange="trackable",
                routing_key="trackable",
                )
        queues['trackable']['publisher'] = publisher

    return queues['trackable'][con_type]

def send_message(request, obj, field_name, op_name, data_cls=None, options={}):
    """
    Defines the interface for defining a message handler for an operation.

    """
    connection, publisher = (None,None)
    try:
        connection = get_connection()
        publisher = get_connection('publisher',op_name)
    except Exception, e:
        if not CAPTURE_CONNECTION_ERRORS:
            raise e
        else:
            mail_admins( \
                'MQ connection failed',
                'Unable to connect get connection to message queue. Bailing. %s' % str(e))
            return

    if not data_cls:
        data_cls = site._registry[obj.__class__][0]

    value = None
    try:
        value = options.pop('value')
    except KeyError:
        pass

    # data_obj = data_cls.objects.get_data_object(obj,options)
    # content_type_pk = ContentType.objects.get_for_model(data_cls).pk
    # object_id = data_obj.pk
    # user_agent = request.META['HTTP_USER_AGENT'] \
    #     if 'HTTP_USER_AGENT' in request.META else 'Undefined HTTP_USER_AGENT'
    # message_body = \
    #     "%s:(%s,%d,%d,%s)=%d" % (user_agent,op_name,content_type_pk,object_id,field_name,value)

    message_obj = {}
    message_obj['content_type_pk'] = ContentType.objects.get_for_model(data_cls).pk
    message_obj['object_id'] = data_cls.objects.get_data_object(obj,options).pk
    message_obj['user_agent'] = request.META['HTTP_USER_AGENT'] \
        if 'HTTP_USER_AGENT' in request.META else UNDEFINED_AGENT
    message_obj['field_name'] = field_name
    message_obj['op_name'] = op_name
    message_obj['options'] = options
    message_obj['value'] = value

    message_body = pickle.dumps( message_obj )
    publisher.send(message_body)

def send_increment_message(request, obj, field_name, data_cls=None, options={}):
    """
    Send a message for incrementing the ``field_name`` count
    for the trackable data model associated with ``contenttype_pk``
    by ``value``.
    
    """
    if not options.get('value',None):
        options.update([('value',1)])
    send_message(request, obj, field_name, 'incr', data_cls=data_cls, options=options)

def send_decrement_message(request, obj, field_name, data_cls=None, options={}):
    """
    Send a message for decrementing the ``field_name`` count
    for the data tracking model associated with ``contenttype_pk``
    by ``value``.
    
    """
    if not options.get('value',None):
        options.update([('value',1)])
    send_message(request, obj, field_name, 'decr', data_cls=data_cls, options=options)

def process_messages(log=False, model_cls=None, max_messages=PROCESS_NUM_MESSAGES):
    """
    Process all currently gathered messages by compiling and 
    saving them to the database.
    
    """
    consumer = None
    try:
        consumer = get_connection('consumer')
    except Exception, e:
        mail_admins( \
            'MQ connection failed',
            'Unable to connect get connection to message queue. Bailing. %s' % str(e))
        return

    values_lookup = {}
    messages_lookup = {}

    cnt = 1

    logger = multiprocessing.get_logger()

    # HACK: to support multiprocessing with Django DB connections, & c.
    connection.close()

    for i in xrange(max_messages):
        message = consumer.fetch()
        if not message:
            return

        message_obj = pickle.loads(message.body)
        logger.info( "%d Got message: %s" % (cnt,message_obj) )
        cnt += 1

        if USER_AGENT_FILTERING:
            if message_obj['user_agent'] == UNDEFINED_AGENT:
                msg = "Cannot match: user agent does not exist."
                logger.warn( msg )
                message.ack()
                continue
            hits = Spider.objects.filter( \
                user_agent__icontains=message_obj['user_agent'][:128])
            if hits:
                msg = "Not processing potential spider-generated tracking message. User agent=%s" % (message_obj['user_agent'])
                logger.warn( msg )
                message.ack()
                continue

        (op_name,field_name,contenttype_pk,object_id,result) = \
            message_obj['op_name'], message_obj['field_name'], \
            message_obj['content_type_pk'], message_obj['object_id'], \
            message_obj['value']

        logger.debug( "Parsed message parameters" )

        try:
            model_content_type = ContentType.objects.get(pk=contenttype_pk)
        except ContentType.DoesNotExist, e:
            msg = "Cannot process message concerning object of content_type %d: %s" % (contenttype_pk,message.body)
            logger.warn( msg )
            continue

        logger.debug( "Determined content_type" )

        if model_cls and model_content_type.model_class() != model_cls:
            logger.warn( "Skipping model_cls != model_content_type.model_class()" )
            continue

        _model_cls = model_cls
        if not model_cls:
            _model_cls = model_content_type.model_class()

        try:
            record = _model_cls.objects.get(pk=object_id)
        except _model_cls.DoesNotExist:
            msg = u"Trackable record doesn't exist (ctype=%s,pk=%s): %s" % (_model_cls,object_id,message_obj)
            logger.warn( msg )
            continue

        try:
            getattr(record,op_name)
        except AttributeError:
            raise TrackableError( \
                u"%s does not support %s operation." \
                    % (record._meta.verbose_name,op_name))

        op_func = getattr(record,op_name)
        op_func(field_name,result)

        record = _model_cls.objects.get(pk=object_id)

        if log:
            logger.info( "(%s)->%s on %s: %s" % (record,op_name,field_name,result))

        # Acknowledge the messages now that the operation has been registered
        message.ack()
