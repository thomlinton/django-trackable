from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, TransactionTestCase
from django.conf import settings

from trackable.messaging import ( \
    send_increment_message, send_decrement_message, process_messages)
from trackable.tests.trackabledata import PageViewTrackableData, PageRevisionTrackableData
from trackable.tasks import CollectTrackingData
from trackable.tests.models import Page

import datetime
import logging
import os.path
import time


class CorrectnessTest(TransactionTestCase):
    urls = 'trackable.tests.urls'
    fixtures = ['page.json',]
    celeryd_concurrency = 2
    template_dirs = [
        os.path.join(os.path.dirname(__file__), 'templates'),
    ]

    def setUp(self):
        self.old_template_dir = settings.TEMPLATE_DIRS
        settings.TEMPLATE_DIRS = self.template_dirs
        # self.old_celeryd_concurrency = getattr(settings,'CELERYD_CONCURRENCY',0)
        self.old_celeryd_concurrency = getattr(settings,'CELERYD_CONCURRENCY',0)
        settings.CELERYD_CONCURRENCY = self.celeryd_concurrency

    def tearDown(self):
        settings.TEMPLATE_DIRS = self.old_template_dir

    def testTrackableData(self):
        test_page = Page.objects.get(pk=1)
        kwargs = {
            'object_id':test_page.pk,
            'content_type':ContentType.objects.get_for_model(Page)
            }

        self.assertRaises( \
            PageViewTrackableData.DoesNotExist, 
            PageViewTrackableData.objects.get,
            **kwargs
            )

        trackable_data = PageViewTrackableData.objects.get_data_object(test_page)
        self.assertEquals(trackable_data.views,0)

        for i in xrange(100):
            self.client.get(test_page.get_absolute_url())

        trackable_data = PageViewTrackableData.objects.get_data_object(test_page)
        self.assertEquals(trackable_data.views,0)

        # HACK: to support multiprocessing with Django DB connections, & c.
        # connection.close()

        # process_messages()

        # procs = [multiprocessing.Process(target=process_messages) for i in xrange(2)]
        # for proc in procs: proc.start(); time.sleep(5)
        # for proc in procs: proc.join(timeout=120)

        # (task1,task2) = ( CollectTrackingData(),CollectTrackingData() )
        # t1 = task1.delay()
        # t2 = task2.delay()
        # t2.get()
        # t1.get()

        task = CollectTrackingData()
        t = task.delay()
        result = t.get()

        # time.sleep(20)

        trackable_data = PageViewTrackableData.objects.get_data_object(test_page)
        self.assertEquals(trackable_data.views,100)

        for i in xrange(200):
            self.client.get(test_page.get_absolute_url())

        self.assertEquals(trackable_data.views,100)

        process_messages(max_messages=200)

        trackable_data = PageViewTrackableData.objects.get_data_object(test_page)
        self.assertEquals(trackable_data.views,300)

    def testTimeSeriesTrackableData(self):
        pass

__tests__ = {}
