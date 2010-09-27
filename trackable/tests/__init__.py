from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, TransactionTestCase
from django.conf import settings

from trackable.tests.trackabledata import PageViewTrackableData, PageRevisionTrackableData
from trackable.contrib.celery_tasks import ProcessTrackableMessages
from trackable.message import connection
from trackable.tests.models import Page

from celery.execute import send_task

import multiprocessing
import datetime
import logging
import os.path
import time


class CeleryTest(TransactionTestCase):
    urls = 'trackable.tests.urls'
    fixtures = ['page.json',]
    template_dirs = [
        os.path.join(os.path.dirname(__file__), 'templates'),
    ]

    def setUp(self):
        self.old_template_dir = settings.TEMPLATE_DIRS
        settings.TEMPLATE_DIRS = self.template_dirs

    def tearDown(self):
        settings.TEMPLATE_DIRS = self.old_template_dir

    def testUniprocessingWorkers(self):
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

        for i in xrange(200):
            self.client.get(test_page.get_absolute_url())

        trackable_data = PageViewTrackableData.objects.get_data_object(test_page)
        self.assertEquals(trackable_data.views,0)

        t3 = send_task("trackable.contrib.celery_tasks.ProcessTrackableMessages")
        t3.get()

        trackable_data = PageViewTrackableData.objects.get_data_object(test_page)
        self.assertEquals(trackable_data.views,200)


class ConcurrencyTest(TransactionTestCase):
    urls = 'trackable.tests.urls'
    fixtures = ['page.json',]
    template_dirs = [
        os.path.join(os.path.dirname(__file__), 'templates'),
    ]

    def setUp(self):
        self.old_template_dir = settings.TEMPLATE_DIRS
        settings.TEMPLATE_DIRS = self.template_dirs

    def tearDown(self):
        settings.TEMPLATE_DIRS = self.old_template_dir

    # def someTestFunc(self):
    # 
    # ...
    # 
    #     from django.db import connection as dj_connection
    #     dj_connection.close()
    # 
    #     p1 = multiprocessing.Process(target=connection.process_messages)
    #     p2 = multiprocessing.Process(target=connection.process_messages)
    #
    #     p1.start()
    #     p2.start()
    # 
    #     p1.join()
    #     p2.join()
    # 
    # ...

__tests__ = {}
