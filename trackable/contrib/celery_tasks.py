from django.conf import settings

from celery.registry import tasks
from celery.task import Task

from trackable.message import connection

# COLLECTION_PERIOD = getattr(settings,'TRACKABLE_COLLECTION_PERIOD',1800)
# DISABLE_COLLECTION_TASK = getattr(settings,'TRACKABLE_DISABLE_COLLECTION_TASK',False)


class ProcessTrackableMessages(Task):
    name = 'trackable.process_messages'
    max_retries = 1

    def run(self, *args, **kwargs):
        logger = self.get_logger(**kwargs)
        try:
            return connection.process_messages(logger=logger)
        except Exception, exc:
            logger.error(exc)
            self.retry(args, kwargs, exc=exc)

tasks.register(ProcessTrackableMessages)
