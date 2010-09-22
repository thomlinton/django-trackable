from django.utils.translation import ugettext_lazy as _
from django.db import models

from trackable.models import TrackableData, TrackableTimeSeriesData
from trackable.tests.models import Page
from trackable.sites import site


class PageViewTrackableData(TrackableData):
    """ """
    views = models.PositiveIntegerField(_(u'page views'), default=0)

    class Meta(TrackableData.Meta):
        verbose_name_plural = _(u'page views')

    def __unicode__(self):
        return u"%s (%s views)" % (self.parent,self.views)

class PageRevisionTrackableData(TrackableTimeSeriesData):
    """ """
    revisions = models.PositiveIntegerField(_(u'page revisions'), default=0)

    class Meta(TrackableTimeSeriesData.Meta):
        verbose_name_plural = _(u'page revisions')

    def __unicode__(self):
        return u"%s (%s revisions)" % (self.parent,self.revisions)

# trackable.site.register(Page,PageViewTrackableData)
site.register(Page,PageViewTrackableData)
# trackable.site.register(Page,PageRevisionTrackableData)
site.register(Page,PageRevisionTrackableData)
