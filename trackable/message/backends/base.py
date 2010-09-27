from django.contrib.contenttypes.models import ContentType
from django.core.mail import mail_admins
from django.conf import settings

from trackable import TrackableError
from trackable.models import Spider
from trackable.sites import site

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
PROCESS_NUM_MESSAGES = getattr(settings,'TRACKABLE_PROCESS_NUM_MESSAGES', None)
LOGLEVEL = getattr(settings,'TRACKABLE_LOGLEVEL', logging.WARNING)
MAGIC_FLAG = getattr(settings,'TRACKABLE_MAGIC_FLAG', '7R4CK4813M491C')

UNDEFINED_AGENT = 'UNDEFINED_HTTP_USER_AGENT'


class BaseMessageBackend(object):
    """ """
    def send(self, payload):
        """
        Publish ``payload`` to the message backend.

        """
        raise NotImplementedError

    def recv(self):
        """
        Fetch a message from the message backend.

        """
        raise NotImplementedError

    def send_message(self, request, obj, field_name, op_name, data_cls, options={}):
        """
        

        """
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

        # message_body = pickle.dumps( message_obj )
        # self.send(message_body)
        self.send( message_obj )

    def process_messages(self, logger=None, model_cls=None, max_messages=PROCESS_NUM_MESSAGES):
        """
        Process all currently gathered messages by compiling and 
        saving them to the database.
        
        """
        test_condition = lambda x: x < max_messages
        if not max_messages:
            test_condition = lambda x: True

        values_lookup = {}
        messages_lookup = {}
        cnt = 0

        if not logger:
            logger = logging.getLogger('trackable')
            console = logging.StreamHandler()
            logger.setLevel(LOGLEVEL)
            logger.addHandler(console)

        while test_condition:
            message = self.recv()
            if not message:
                break

            # message_obj = pickle.loads(message.body)
            message_obj = message.payload
            if 'magic' not in message_obj or message_obj['magic'] != MAGIC_FLAG:
                logger.warning( "Magic bytes not found or do not match. Skipping message." )
                continue

            logger.info( "%d Got message: %s" % (cnt+1,message_obj) )
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

            (op_name,field_name,data_cls,data_object_pk,result) = \
                message_obj['op_name'], message_obj['field_name'], \
                message_obj['data_cls'], message_obj['data_object_pk'], \
                message_obj['value']

            if model_cls and data_cls != model_cls:
                msg = u"Skipping TrackableData type=%s" % (str(data_cls))
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

            data_object = data_cls.objects.get(pk=data_object_pk)
            logger.info( "(%s)->%s on %s: %s" % (data_object,op_name,field_name,result))

            # Acknowledge the message now that the operation has been registered
            message.ack()

        return cnt
