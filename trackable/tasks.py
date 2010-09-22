from django.conf import settings

from celery.registry import tasks
from celery.task import Task

from trackable.messaging import process_messages

import datetime

COLLECTION_PERIOD = getattr(settings,'TRACKABLE_COLLECTION_PERIOD',1800)
DISABLE_COLLECTION_TASK = getattr(settings,'TRACKABLE_DISABLE_COLLECTION_TASK',False)

try:
    from celery.task import PeriodicTask
    class CollectTrackingData(PeriodicTask):
        run_every = datetime.timedelta(seconds=long(COLLECTION_PERIOD))
        def run(self, **kwargs):
            logger = self.get_logger(**kwargs)
            return process_messages(logger=logger)
except ImportError:
    class CollectTrackingData(Task):
        def run(self, **kwargs):
            logger = self.get_logger(**kwargs)
            return process_messages(logger=logger)
finally:
    if not DISABLE_COLLECTION_TASK:
        tasks.register(CollectTrackingData)
