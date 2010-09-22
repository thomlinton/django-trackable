from django.views.generic.list_detail import object_detail
from django.shortcuts import get_object_or_404

from trackable.messaging import send_increment_message
from trackable.tests.models import Page


def page_detail(request, slug):
    response = object_detail(request,Page.objects.all(),slug=slug)
    if response.status_code == 200:
        send_increment_message(
            request,Page.objects.get(slug=slug),'views'
            )
    return response
