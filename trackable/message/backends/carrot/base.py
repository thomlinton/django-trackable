from django.core.mail import mail_admins
from django.conf import settings

from carrot.connection import DjangoBrokerConnection
from carrot.messaging import Publisher, Consumer

from trackable.message.backends.base import BaseMessageBackend


class MessageBackend(BaseMessageBackend):
    """ """
    def __init__(self):
        try:
            self.connection = DjangoBrokerConnection()
            self.consumer = Consumer( \
                connection=self.connection,
                queue='trackable_internal',
                exchange='direct',
                routing_key='trackable_internal',
                )
            self.publisher = Publisher( \
                connection=self.connection,
                queue='trackable_internal',
                exchange='direct',
                routing_key='trackable_internal',
                serializer='pickle',
                )
        except Exception, e:
            if settings.DEBUG:
                raise e
            mail_admins(
                '[django-trackable] Error while acquiring a connection in carrot backend',
                '%s' % (str(e))
                )


    def send(self, payload):
        try:
            return self.publisher.send( payload )
        except Exception, e:
            if settings.DEBUG:
                raise e
            mail_admins(
                '[django-trackable] Error while sending message in carrot backend',
                '%s' % (str(e))
                )

    def recv(self):
        try:
            return self.consumer.fetch()
        except Exception, e:
            if settings.DEBUG:
                raise e
            mail_admins(
                '[django-trackable] Error while sending message in carrot backend',
                '%s' % (str(e))
                )
