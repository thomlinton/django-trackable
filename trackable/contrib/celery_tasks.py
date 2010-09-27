from django.conf import settings

from celery.registry import tasks
from celery.task import Task

from trackable.message import connection

# COLLECTION_PERIOD = getattr(settings,'TRACKABLE_COLLECTION_PERIOD',1800)
# DISABLE_COLLECTION_TASK = getattr(settings,'TRACKABLE_DISABLE_COLLECTION_TASK',False)


class ProcessTrackableMessages(Task):
    def run(self, **kwargs):
        logger = self.get_logger(**kwargs)
        return connection.process_messages(logger=logger)

tasks.register(ProcessTrackableMessages)
