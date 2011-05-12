from django.core.mail import mail_admins
from django.conf import settings

from kombu.connection import BrokerConnection
from kombu.compat import Publisher, Consumer

from trackable.message.backends.base import BaseMessageBackend


class MessageBackend(BaseMessageBackend):
    """ """
    def __init__(self):
        self.sent_failure_notification = False
        try:
            self.connection = BrokerConnection()
            self.consumer = Consumer( \
                connection=self.connection,
                queue='trackable_internal',
                exchange='direct',
                routing_key='trackable_internal',
                )
            self.publisher = Publisher( \
                connection=self.connection,
                # queue='trackable_internal',
                exchange='direct',
                routing_key='trackable_internal',
                serializer='pickle',
                )
        except Exception, e:
            if settings.DEBUG:
                raise e
            mail_admins(
                '[django-trackable] Error while acquiring a connection in kombu backend',
                '%s' % (str(e))
                )


    def send(self, payload):
        try:
            return self.publisher.send( payload )
        except Exception, e:
            if settings.DEBUG:
                raise e
            if not self.sent_failure_notification:
                mail_admins(
                    '[django-trackable] Error while sending message in kombu backend',
                    '%s' % (str(e))
                    )
                self.sent_failure_notification = True

    def recv(self):
        try:
            return self.consumer.fetch()
        except Exception, e:
            if settings.DEBUG:
                raise e
            if not self.sent_failure_notification:
                mail_admins(
                    '[django-trackable] Error while recieving message in kombu backend',
                    '%s' % (str(e))
                    )
                self.sent_failure_notification = True
