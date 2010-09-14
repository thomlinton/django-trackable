from django.contrib.contenttypes.models import ContentType
from django.core.mail import mail_admins
from django.db import transaction
from django.conf import settings

from carrot.connection import DjangoBrokerConnection
from carrot.messaging import Publisher, Consumer
from trackable import site, TrackableError
from trackable.models import Spider

import datetime
import warnings

USER_AGENT_FILTERING = getattr(settings,'TRACKABLE_USER_AGENT_FILTERING', False)
REMOVE_MALFORMED_MESSAGES = getattr(settings,'TRACKABLE_REMOVE_MALFORMED_MESSAGES', False)
CAPTURE_CONNECTION_ERRORS = getattr(settings,'TRACKABLE_CAPTURE_CONNECTION_ERRORS', False)

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
        try:
            data_cls = site._registry[obj.__class__][0]
        except (KeyError,IndexError):
            raise

    value = None
    try:
        value = options.pop('value')
    except KeyError:
        pass

    data_obj = data_cls.objects.get_data_object(obj,options)
    content_type_pk = ContentType.objects.get_for_model(data_cls).pk
    object_id = data_obj.pk
    message_body = \
        "%s:(%s,%d,%d,%s)=%d" % \
            (request.META['HTTP_USER_AGENT'], 
             op_name,content_type_pk,
             object_id,field_name,value)
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

@transaction.commit_on_success
def process_messages(log=False, model_cls=None):
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

    for message in consumer.iterqueue():
        try:
            (user_agent,body) = message.body.rsplit(':',1)
            if USER_AGENT_FILTERING:
                hits = Spider.objects.filter(user_agent__icontains=user_agent[:128])
                if hits:
                    msg = "Will not process potential spider-generated tracking message (%s)" % (user_agent)
                    warnings.warn( msg )
                    message.ack()
                    continue
        except ValueError:
            msg = "Malformed message: does not contain user agent information: %s" % (message.body)
            warnings.warn( msg )
            if REMOVE_MALFORMED_MESSAGES:
                message.ack()
            continue

        (func,result) = body.split('=')
        (op_name,contenttype_pk,object_id,field_name) = func.strip("()").split(',')

        try:
            model_content_type = ContentType.objects.get(pk=long(contenttype_pk))
        except ContentType.DoesNotExist, e:
            msg = "Cannot process message concerning object of content_type %d: %s" % (contenttype_pk,message.body)
            warnings.warn( msg )
            continue

        if model_cls and model_content_type.model_class() != model_cls:
            continue

        _model_cls = model_cls
        if not model_cls:
            _model_cls = model_content_type.model_class()

        try:
            record = _model_cls.objects.get(pk=long(object_id))
        except _model_cls.DoesNotExist:
            msg = u"Trackable record doesn't exist (ctype=%s,pk=%s): %s" % (_model_cls,object_id,message.body)
            warnings.warn( msg )
            continue

        key = (record,op_name,field_name)
        l_operand,r_operand = (
            values_lookup.get(key,None),
            result
            )

        try:
            op_func = getattr(record,op_name)
        except AttributeError:
            raise TrackableError( \
                u"%s does not support %s operation." \
                    % (record._meta.verbose_name,op_name))

        values_lookup[key] = op_func( \
            field_name,
            value=r_operand, 
            initial_value=l_operand,
            update=False
            )

        # Keep the message objects so we can ack the messages as processed 
        # when we are finished with them.
        if key in messages_lookup:
            messages_lookup[key].append(message)
        else:
            messages_lookup[key] = [message]

    for key, result in values_lookup.items():
        (record,op_name,field_name) = key
        record._write_attribute_value(field_name,result)

        if log:
            print "(%s)->%s on %s: %s" % (record,op_name,field_name,result)
        
        # Acknowledge the messages now that the operation has been registered
        [message.ack() for message in messages_lookup[key]]
