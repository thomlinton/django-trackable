from django.contrib.contenttypes.models import ContentType
from django.db import connection, transaction
from django.core.mail import mail_admins
from django.conf import settings

from carrot.connection import DjangoBrokerConnection
from carrot.messaging import Publisher, Consumer
from trackable import TrackableError
from trackable.models import Spider
from trackable.sites import site

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
LOGLEVEL = getattr(settings,'TRACKABLE_LOGLEVEL', logging.WARNING)
MAGIC_FLAG = getattr(settings,'TRACKABLE_MAGIC_FLAG', '7R4CK4813M491C')

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

    message_obj = {}
    message_obj['magic'] = MAGIC_FLAG
    message_obj['data_object_pk'] = data_cls.objects.get_data_object(obj,options).pk
    message_obj['data_cls'] = data_cls
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

def process_messages(logger=None, model_cls=None, max_messages=PROCESS_NUM_MESSAGES):
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

    if not logger:
        logger = logging.getLogger('trackable')
        console = logging.StreamHandler()
        logger.setLevel(LOGLEVEL)
        logger.addHandler(console)

    # HACK: to support multiprocessing with Django DB connections, & c.
    # connection.close()

    for i in xrange(max_messages):
        message = consumer.fetch()
        if not message:
            return

        message_obj = pickle.loads(message.body)
        if 'magic' not in message_obj or message_obj['magic'] != MAGIC_FLAG:
            continue

        logger.info( "%d Got message: %s" % (cnt,message_obj) )
        cnt += 1

        if USER_AGENT_FILTERING:
            if message_obj['user_agent'] == UNDEFINED_AGENT:
                msg = "Cannot match: user agent does not exist."
                logger.warning( msg )
                message.ack()
                continue
            hits = Spider.objects.filter( \
                user_agent__icontains=message_obj['user_agent'][:128])
            if hits:
                msg = "Not processing potential spider-generated tracking message. User agent=%s" % (message_obj['user_agent'])
                logger.warning( msg )
                message.ack()
                continue

        # (op_name,field_name,contenttype_pk,object_id,result) = \
        #     message_obj['op_name'], message_obj['field_name'], \
        #     message_obj['content_type_pk'], message_obj['object_id'], \
        #     message_obj['value']

        (op_name,field_name,data_cls,data_object_pk,result) = \
            message_obj['op_name'], message_obj['field_name'], \
            message_obj['data_cls'], message_obj['data_object_pk'], \
            message_obj['value']

        # _model_cls = model_cls
        # (op_name,field_name,content_type_pk,object_pk,result) = \
        #     message_obj['op_name'], message_obj['field_name'], \
        #     message_obj['content_type_pk'], message_obj['object_pk'], \
        #     message_obj['value']

        # try:
        #     model_content_type = ContentType.objects.get(pk=content_type_pk)
        # except ContentType.DoesNotExist, e:
        #     msg = "Cannot process message concerning object of content_type %d: %s" % \
        #         (content_type_pk,message.body)
        #     logger.warning( msg )
        #     continue

        # logger.info( "Using content_type_pk: %d" % (content_type_pk) )
        # logger.info( "Determined content_type: %s" % (model_content_type) )
        # logger.info( "Determined content_type.model_class(): %s" % (model_content_type.model_class()) )

        # _model_cls = model_content_type.model_class()
        # if model_cls and _model_cls != model_cls:
        #     msg = u""
        #     logger.warning( msg )
        #     continue

        # record = None
        # try:
        #     record = _model_cls.objects.get(pk=object_pk)
        # except AttributeError:
        #     msg = u"Trackable model class unspecified. Skipping: model_cls=%s _model_cls=%s" % (model_cls,_model_cls)
        #     logger.warning( msg )
        #     continue
        # except _model_cls.DoesNotExist:
        #     msg = u"Trackable record doesn't exist (ctype=%s,pk=%s): %s" % (_model_cls,object_pk,message_obj)
        #     logger.warning( msg )
        #     continue

        # @transaction.commit_on_success
        # def commit():
        #     print "commit record: %s" % (record)
        #     record.save()

        if model_cls and data_cls != model_cls:
            msg = u"Skipping TrackableData type=%s" % (data_cls)
            logger.info( msg )
            continue

        data_object = data_cls.objects.get(pk=data_object_pk)

        try:
            getattr(data_object,op_name)
        except AttributeError:
            raise TrackableError( \
                u"%s does not support %s operation." \
                    % (data_object,op_name))

        op_func = getattr(data_object,op_name)
        op_func(field_name,result)
        # commit()

        # record = _model_cls.objects.get(pk=object_pk)
        # record = model_cls.objects.get(pk=record.pk)
        data_object = data_cls.objects.get(pk=data_object_pk)
        logger.info( "(%s)->%s on %s: %s" % (data_object,op_name,field_name,result))

        # Acknowledge the messages now that the operation has been registered
        message.ack()

    return cnt-1
