from carrot.connection import DjangoBrokerConnection
from carrot.messaging import Messaging

from trackable.message.backends.base import BaseMessageBackend


class MessageBackend(BaseMessageBackend):
    """ """
    def get_connection(self):
        Messaging.publisher_cls.serializer = 'pickle'
        return Messaging( \
            connection=DjangoBrokerConnection(),
            queue='trackable_internal',
            exchange='direct',
            routing_key='trackable_internal',
            )

    def send(self, payload):
        return self.connection.send( payload )

    def recv(self):
        return self.connection.fetch()
