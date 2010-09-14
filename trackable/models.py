from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction, IntegrityError
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes import generic
from django.conf import settings
from django.db.models import F

import datetime


class TrackableError(Exception):
    pass

class Spider(models.Model):
    """ """
    user_agent = models.CharField(max_length=128, unique=True)

    class Meta:
        verbose_name = _(u'spider')

class TrackableDataManager(models.Manager):
    """ """
    def get_data_parameters(self, obj, options={}):
        raise NotImplementedError

    def get_filtered_fields(self):
        return ['id','content_type','object_id','parent',]

    def get_trackable_fields(self):
        trackable_fields = []
        for field in self.model._meta.fields:
            if field.name not in self.get_filtered_fields():
                trackable_fields.append(field.name)
        return trackable_fields

    def get_data_object(self, obj, options={}):
        data_obj = None
        params = {}

        try:
            params = self.get_data_parameters(obj,options)
        except NotImplementedError:
            pass
        params.update({
            'content_type':
                ContentType.objects.get_for_model(obj.__class__),
            'object_id':obj.pk
            })

        try:
            return self.get_query_set().get(**params)
        except ObjectDoesNotExist:
            try:
                return self.get_query_set().create(**params)
            except IntegrityError, e:
                transaction.rollback()
                return self.get_query_set().get(**params)
        except MultipleObjectsReturned:
            return self.get_query_set().filter(**params)[0]

class TrackableData(models.Model):
    """ """
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    parent = generic.GenericForeignKey('content_type','object_id')

    class Meta:
        verbose_name_plural = _(u'trackable data')
        abstract = True
        ordering = ('content_type','object_id')
        unique_together = ('content_type','object_id')

    def op(self, attr, change_func, commit=False):
        try:
            _attr = getattr(self,attr)
        except AttributeError:
            raise TrackableError( \
                u"Attribute %s does not exist" % attr)

        _attr = change_func( F(attr) )
        return _attr

    def incr(self, attr, value=1, commit=False):
        value = long(value)
        return self.op(attr, lambda x:x+value, commit=commit)

    def decr(self, attr, value=1, commit=False):
        value = long(value)
        return self.op(attr, lambda x:x-value, commit=commit)

    def __unicode__(self):
        return u"%s (%s)" % \
            (self._meta.verbose_name,self.parent)

    objects = TrackableDataManager()

class TrackableTimeSeriesDataManager(TrackableDataManager):
    """ """
    def get_filtered_fields(self):
        filtered_fields = super(TrackableTimeSeriesDataManager,self).get_filtered_fields()
        filtered_fields.append('collected_during')
        return filtered_fields

    def get_data_parameters(self, obj, options={}):
        return {
            'collected_during': datetime.date.today(),
            }

class TrackableTimeSeriesData(TrackableData):
    """ """
    collected_during = models.DateField()

    class Meta(TrackableData.Meta):
        verbose_name_plural = _(u'trackable time series data')
        abstract = True
        ordering = ('-collected_during','content_type','object_id')
        unique_together = ('content_type','object_id','collected_during',)

    def __unicode__(self):
        return u"%s (%s) for %s" % \
            (self._meta.verbose_name,self.parent,self.collected_during)

    objects = TrackableTimeSeriesDataManager()
