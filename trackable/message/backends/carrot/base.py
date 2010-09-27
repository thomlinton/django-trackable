from carrot.connection import DjangoBrokerConnection
from carrot.messaging import Publisher, Consumer

from trackable.message.backends.base import BaseMessageBackend


class MessageBackend(BaseMessageBackend):
    """ """
    def __init__(self):
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

    def send(self, payload):
        return self.publisher.send( payload )

    def recv(self):
        return self.consumer.fetch()
