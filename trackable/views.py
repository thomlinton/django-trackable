from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ObjectDoesNotExist
from django.http import ( \
    HttpResponse, HttpResponseRedirect, HttpResponseServerError, Http404)

from trackable import TrackableError


def trackable_redirect( request, queryset, message_op, message_func, trackable_cls=None,
                        url_field=None, redirect_func=None, 
                        object_id=None, slug=None, slug_field='slug',
                        **options):
    """

    """
    model = queryset.model
    if object_id:
        queryset = queryset.filter(pk=object_id)
    elif slug and slug_field:
        queryset = queryset.filter(**{slug_field: slug})
    else:
        raise TrackableError("trackable_redirect view must be called with either an object_id or a slug/slug_field.")

    try:
        obj = queryset.get()
    except ObjectDoesNotExist:
        raise Http404("No %s found matching the query" % (model._meta.verbose_name))

    message_func(request,obj,message_op,data_cls=trackable_cls,options=dict(options))

    if redirect_func:
        return HttpResponseRedirect(redirect_func(obj,dict(options)))
    elif url_field and getattr(obj,url_field,''):
        return HttpResponseRedirect(getattr(obj,url_field))
    elif getattr(obj,'get_absolute_url',''):
        return HttpResponseRedirect(obj.get_absolute_url())

    raise TrackableError( \
        u"url_field has not been specified and object has not defined a get_absolute_url property")
