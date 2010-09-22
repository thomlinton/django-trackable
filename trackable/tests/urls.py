from django.conf.urls.defaults import *

from trackable.tests.models import Page
from trackable.tests.views import page_detail


urlpatterns = patterns('',
    url(r'^page/(?P<slug>[\w-]+)/$', page_detail, {}, name='page-detail'),
)
