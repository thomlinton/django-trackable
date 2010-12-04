from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import mail_admins
from django.conf import settings

from trackable.exceptions import TrackableError
from trackable.models import Spider
from trackable.sites import site

import collections
import datetime
import warnings
import logging
import shelve
import socket
import errno

try:
    import cPickle as pickle
except ImportError:
    import pickle

BACKEND_CONNECTION_BACKOFF_SECONDS = getattr(settings,'TRACKABLE_BACKEND_CONNECTION_BACKOFF_SECONDS', 30)
BACKEND_CONNECTION_LIMIT = getattr(settings,'TRACKABLE_BACKEND_CONNECTION_LIMIT', 5)
BACKEND_SEND_QUEUE_SIZE = getattr(settings,'TRACKABLE_BACKEND_SEND_QUEUE', 1000)
USER_AGENT_FILTERING = getattr(settings,'TRACKABLE_USER_AGENT_FILTERING', False)
PROCESS_NUM_MESSAGES = getattr(settings,'TRACKABLE_PROCESS_NUM_MESSAGES', None)
STRICT_MODE = getattr(settings,'TRACKABLE_STRICT_MODE', True)
LOGLEVEL = getattr(settings,'TRACKABLE_LOGLEVEL', logging.WARNING)
MAGIC_FLAG = getattr(settings,'TRACKABLE_MAGIC_FLAG', '7R4CK4813M491C')

UNDEFINED_AGENT = 'UNDEFINED_HTTP_USER_AGENT'
SEND_QUEUE_PERSIST_NAME = 'trackable_send_queue.db'

# configure default module logger
_logger = logging.getLogger('trackable')
_logger.setLevel(LOGLEVEL)
_logger.addHandler(logging.StreamHandler())


class MockMessage(object):
    """ """
    def __init__(self,payload={}):
        self.payload = payload
        self.payload['SOURCE'] = 'MockMessage'
    def ack(self):
        pass

class BaseMessageBackend(object):
    """ """
    def __init__(self):
        #
        # TODO: 
        # Figure out if we need a hard limit (can we determine a bound)
        # ... or perhaps we can just flush on overflow?
        #
        queue_kwargs = {}
        try:
            collections.deque.maxlen
            queue_kwargs['maxlen'] = long(BACKEND_SEND_QUEUE_SIZE)
        except AttributeError:
            pass
        self.send_queue = collections.deque(**queue_kwargs)
        self.send_queue_loaded = False

        self.connection_attempts = 0
        self.connection_backoff_ts = None
        self.connection_backoff_period = \
            datetime.timedelta(seconds=BACKEND_CONNECTION_BACKOFF_SECONDS)
        self.disconnected_notification_sent = False

        self.connect() # avoid 'protected' _connect on __init__

    def _readin_send_queue(self):
        # default kwarg flag='c'
        #   this mode will lock concurrent access
        #   for both read & write (creating if necessary)
        db = shelve.open(SEND_QUEUE_PERSIST_NAME)
        for i in xrange(0,len(db)):
            item_key = "%d" % (i)
            self.send_queue.append( db[item_key] )
            del db[item_key]
        db.close()
        self.send_queue_loaded = True

    def _writeout_send_queue(self):
        if len(self.send_queue):
            # default kwarg flag='c'
            #   this mode will lock concurrent access
            #   for both read & write (creating if necessary)
            db = shelve.open(SEND_QUEUE_PERSIST_NAME)
            sq_range = xrange(0,len(self.send_queue))
            db_range = sq_range
            if not self.send_queue_loaded:
                db_range = xrange(len(db),len(db)+len(self.send_queue))
            _range = zip(db_range,sq_range)
            for i,j in _range:
                item_key = "%d" % (i)
                db[item_key] = self.send_queue[j]
                del self.send_queue[j]
            db.close()

    def get_connection(self):
        """ """
        raise NotImplementedError

    def is_connected(self):
        """
        Determines whether or not the current instance should be
        considered connected.

        """
        try:
            test_connection = self.get_connection()
        except socket.error:
            return False
        else:
            if not test_connection:
                return False
            return True

    def _connect(self):
        if self.connection_attempts > BACKEND_CONNECTION_LIMIT:
            if not self.connection_backoff_ts:
                self.connection_backoff_ts = datetime.datetime.now()
            if (datetime.datetime.now() - self.connection_backoff_ts) > self.connection_backoff_period:
                self.connection_attempts = 0
                self.connection_backoff_ts = None
            else:
                _logger.warning( \
                    "Throttling connection attempt until %s" % ( \
                        self.connection_backoff_ts + self.connection_backoff_period)
                    )
                return False

        self.connect()
        self.connection_attempts += 1
        return True

    def connect(self):
        """
        Handle the creation and/or negotiation of messages service.

        """
        try:
            _logger.info( \
                "Trying connection (%d previous attempts)" % (self.connection_attempts)
                )
            self.connection = self.get_connection()
        except socket.error, e:
            if settings.DEBUG:
                raise e
            if not self.disconnected_notification_sent:
                mail_admins(
                    '[django-trackable] Error while acquiring a connection in backend %s' % \
                        (self.__class__), '%s' % (str(e))
                    )
                self.disconnected_notification_sent = True

    def try_connect(self):
        keep_trying = self._connect()
        while not self.is_connected() and keep_trying:
            keep_trying = self._connect()
            if self.is_connected():
                self.disconnected_notification_sent = False
                _logger.info( \
                    "Connection via backend %s acquired" % (self.__class__)
                    )
        self.connection_attempts = 0
        self.connection_backoff_ts = None

    def _send(self, payload):
        self.try_connect()
        if self.is_connected():
            return self.send( payload )

        self.send_queue.append(MockMessage(payload))
        self._writeout_send_queue()

    def send(self, payload):
        """
        Publish ``payload`` to the message backend.

        """
        raise NotImplementedError

    def _recv(self, load_send_queue=False):
        # give priority to send_queue in the case
        # that the call to self.try_connect will
        # reacquire a connection.
        if not self.send_queue_loaded and load_send_queue:
            self._readin_send_queue()
        if len(self.send_queue):
            return self.send_queue.popleft()

        self.try_connect()
        if self.is_connected():
            return self.recv()

    def recv(self):
        """
        Fetch a message from the message backend.

        """
        raise NotImplementedError

    def send_message(self, request, obj, field_name, op_name, data_cls, options={}):
        """
        In-process entry-point for data tracking facilities that packages a tracking
        request up and emits a signal to be processed at some future point in time.

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

        #
        # TODO: Consider alternative formulations?
        #
        if USER_AGENT_FILTERING:
            if message_obj['user_agent'] == UNDEFINED_AGENT:
                msg = "Cannot match: user agent does not exist."
                _logger.warning( msg )
                message.ack()
                return
            hits = Spider.objects.filter( \
                user_agent__icontains=message_obj['user_agent'][:128])
            if hits:
                msg = "Not processing potential spider-generated tracking message. User agent=%s" % (message_obj['user_agent'])
                _logger.warning( msg )
                message.ack()
                return

        self._send( message_obj )

    def process_messages(self, logger=None, model_cls=None, max_messages=PROCESS_NUM_MESSAGES, load_send_queue=False):
        """
        Process all currently gathered messages by compiling and 
        saving them to the database.
        
        """
        if not logger:
            logger = _logger

        msg = "Send queue contains %d items" % (len(self.send_queue))
        logger.info( msg )

        test_condition = lambda x: x < max_messages
        if not max_messages:
            test_condition = lambda x: True

        values_lookup = {}
        messages_lookup = {}
        processed = 0
        cnt = 0

        while test_condition(processed):
            message = self._recv(load_send_queue=load_send_queue)
            if not message:
                break

            message_obj = message.payload
            if 'magic' not in message_obj or message_obj['magic'] != MAGIC_FLAG:
                # logger.warning( "Magic bytes not found or do not match. Skipping message." )
                message.ack()
                continue

            logger.info( "%d Got message: %s" % (cnt+1,message_obj) )
            cnt += 1

            (op_name,field_name,data_cls,data_object_pk,result) = \
                message_obj['op_name'], message_obj['field_name'], \
                message_obj['data_cls'], message_obj['data_object_pk'], \
                message_obj['value']

            if model_cls and data_cls != model_cls:
                msg = u"Skipping TrackableData type=%s" % (str(data_cls))
                logger.info( msg )
                continue

            try:
                data_object = data_cls.objects.get(pk=data_object_pk)
            except ObjectDoesNotExist, e:
                msg = "%s object with primary key %s does not exist" \
                    % (data_cls.__name__,data_object_pk)
                logger.warning( msg )
                if not STRICT_MODE:
                    continue
                raise e

            try:
                op_func = getattr(data_object,op_name)
                op_func(field_name,result)
            except AttributeError, e:
                msg = u"%s does not support %s operation." \
                    % (data_object,op_name)
                logger.warning( msg )
                if not STRICT_MODE:
                    continue
                raise e
            except TrackableError, e:
                msg = u"%s does not have an attribute %s" \
                    % (data_object,field_name)
                logger.warning( msg )
                if not STRICT_MODE:
                    continue
                raise e

            data_object = data_cls.objects.get(pk=data_object_pk)
            logger.info( "(%s)->%s on %s: %s" % (data_object,op_name,field_name,result))

            # Acknowledge the message now that the operation has been registered
            message.ack()
            processed += 1

        return processed
