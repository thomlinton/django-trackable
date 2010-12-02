from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.utils.translation import ugettext_lazy as _
from django.utils import simplejson
from django.http import ( \
    HttpResponse, HttpResponseRedirect, HttpResponseServerError, Http404)

from trackable.exceptions import TrackableError
import warnings


def track_object( request, queryset, message_op, message_func, trackable_cls=None,
                  url_field=None, redirect_func=None, 
                  object_id=None, slug=None, slug_field='slug',
                  **options):
    """
    A generic trackable view that aligns a trackable message with the 
    HTTP request/response cycle.

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
    # FIXME
    except MultipleObjectsReturned:
        obj = queryset[0]

    message_func(request,obj,message_op,data_cls=trackable_cls,options=dict(options))

    if request.is_ajax():
        return HttpResponse(simplejson.dumps(True),mimetype='application/javascript')

    if redirect_func:
        return HttpResponseRedirect(redirect_func(obj,dict(options)))
    elif url_field and getattr(obj,url_field,''):
        return HttpResponseRedirect(getattr(obj,url_field))
    elif getattr(obj,'get_absolute_url',''):
        return HttpResponseRedirect(obj.get_absolute_url())

    raise TrackableError( \
        u"url_field has not been specified and object has not defined a get_absolute_url property")

def trackable_redirect( request, queryset, message_op, message_func, trackable_cls=None,
                        url_field=None, redirect_func=None, 
                        object_id=None, slug=None, slug_field='slug',
                        **options):
    warning = DeprecationWarning("`trackable.views.trackable_redirect` has been renamed to `trackable.views.track_object`")
    warnings.warn( warning, stacklevel=2 )    
    return track_object(request,queryset,message_op,message_func,trackable_cls,url_field=url_field,redirect_func=redirect_func,
                        object_id=object_id,slug=slug,slug_field=slug_field,**options)
