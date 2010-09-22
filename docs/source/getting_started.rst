.. _getting_started:


===============
Getting started
===============


Defining tracking datasets
--------------------------

For developers already accustomed to Django, ``Django-trackable`` employs an 
interface identical to ``django.contrib.admin``. It provides basic scaffolding
with which to construct more complex tracking datasets; for example, time-series 
data is supported out-of-the-box. To construct your own tracking dataset models 
simple define your object, providing the proper incantations::

    from django.contrib import admin
    from my_app.models import MyObject
    import trackable

    class MyObjectTrackableData(trackable.TrackableTimeSeriesData):
        impressions = models.PositiveIntegerField(default=0)
        click_throughs = models.PositiveIntegerField(default=0)

        class Meta(trackable.TrackableTimeSeriesData.Meta):
            app_label = 'my_app'
            verbose_name_plural = _('My object trackable data')

Similar to ``django.contrib.admin``, you must register your models::

    trackable.site.register(MyObject, MyObjectTrackableData)

For convenience, you can supply your own ``ModelAdmin`` class in the same call::

    class MyObjectTrackableDataAdmin(admin.ModelAdmin):
        list_display = ('parent','collected_during', 'impressions','click_throughs',)

    trackable.site.register(MyObject, MyObjectTrackableData, MyObjectTrackableDataAdmin)

Please note that for convenience, ``Django-trackable`` will only actually register the 
``ModelAdmin`` class when ``DEBUG`` is set; in other words, it's unlikely of much use 
unless you are debugging your application.


Emitting tracking events
------------------------

In order to interact with these datasets, you'll need broadcast builtin or user-defined 
messages (events) when encountering an event of interest within a, e.g., a view. For more 
information on extending ``Django-trackable`` by defining your own messages please consult 
the documentation.

Continuing the previous example::

    from django.shortcuts import get_object_or_404
    from django import http
    from my_app.models import MyObject
    from trackable.messaging import send_increment_message

    def someone_looked_at_my_object( request, slug ):
        my_object = get_object_or_404(MyObject, slug=slug)
	send_increment_message(request,my_object,'impressions')
	return http.HttpResponse("My object, how does it work?",status=418)

Notice that you pass the object to which the tracking data will be attached as well as 
the field you wish to signal (in this case, the ``impressions`` field on 
``MyObjectTrackingData``).


Collecting tracking data
------------------------

In order to collect and process these events, you may utilize the utility 
``trackable.messaging.process_messages``. As a convenience, a Celery ``Task`` has been 
provided (``trackable.tasks.CollectTrackingData``) and is enabled by default. 

Prior to Celery 3.0, a ``PendingDeprecation`` has been applied to "old-style" periodic tasks.
Depending with which version of Celery your project is built you may adjust the collection 
period as follows::

    #
    # Old Style
    #

    # in your django settings
    TRACKABLE_COLLECTION_PERIOD = N seconds [1800]

or, ::

    #
    # New Style (taken from Celery documentation)
    #
    from datetime import timedelta

    CELERYBEAT_SCHEDULE = {
        "runs-every-30-seconds": {
            "task": "tasks.add",
            "schedule": timedelta(seconds=30),
            "args": (16, 16)
        },
    }

    from celery.schedules import crontab

    CELERYBEAT_SCHEDULE = {
        # Executes every monday morning at 7:30 A.M
        "every-monday-morning": {
            "task": "tasks.add",
            "schedule": crontab(hour=7, minute=30, day_of_week=1),
            "args": (16, 16),
        },
    }

To disable the collection task completely (trackable won't register the task)::

    TRACKABLE_DISABLE_COLLECTION_TASK = True [False]

Alternatively, you may trigger this function from the builtin Django shell by using the 
management command ``fold_trackable_messages``. 


Settings & Miscellany
---------------------

To enable the capture of connection errors (when connecting to the messaging broker) to avoid 
e.g., HTTP 500::

    TRACKABLE_CAPTURE_CONNECTION_ERRORS = True [False]

Any exception caught while this configuration setting is enabled with be emailed to the 
addresses listed in ``ADMINS``.

For convenience, a tracking data migration command is provided; your mileage may vary::

    ./manage.py convert_tracking_data --help

Some nonzero interval of time -- varying on the developer in question -- you might manage 
to create 'malformed' messages for a variety of reasons; to prevent the collection tasks 
from continually revisiting the same broken messages::

    TRACKABLE_REMOVE_MALFORMED_MESSAGES = True [False]

``Django-trackable`` includes an optional, primitive spider-filtering mechanism that is 
disabled by default. To enable it::

    TRACKABLE_USER_AGENT_FILTERING = True [False]

A poorly-fashioned dataset of spiders is provided as a fixture which you are welcome to 
use with the knowledge that you'll likely need to craft a means of generating your own.
