from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, TransactionTestCase
from django.conf import settings
from django.db import connection

from trackable.messaging import send_increment_message, send_decrement_message, process_messages
from trackable.tests.trackabledata import PageViewTrackableData, PageRevisionTrackableData
from trackable.tests.models import Page

import multiprocessing
import datetime
import logging
import os.path
import time


class CorrectnessTest(TransactionTestCase):
    urls = 'trackable.tests.test_urls'
    fixtures = ['page.json',]
    template_dirs = [
        os.path.join(os.path.dirname(__file__), 'templates'),
    ]

    def setUp(self):
        self.old_template_dir = settings.TEMPLATE_DIRS
        settings.TEMPLATE_DIRS = self.template_dirs

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

        self.assertEquals(trackable_data.views,0)

        # HACK: to support multiprocessing with Django DB connections, & c.
        connection.close()

        logger = multiprocessing.log_to_stderr()
        logger.setLevel(logging.WARNING)

        procs = [multiprocessing.Process(target=process_messages) for i in xrange(2)]
        for proc in procs: proc.start(); time.sleep(5)
        for proc in procs: proc.join(timeout=120)

        trackable_data = PageViewTrackableData.objects.get_data_object(test_page)
        self.assertEquals(trackable_data.views,100)

        for i in xrange(1000):
            self.client.get(test_page.get_absolute_url())

        self.assertEquals(trackable_data.views,100)

        process_messages(max_messages=1000)

        trackable_data = PageViewTrackableData.objects.get_data_object(test_page)
        self.assertEquals(trackable_data.views,1100)

    def testTimeSeriesTrackableData(self):
        pass
