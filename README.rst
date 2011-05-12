================
django-trackable
================

``Django-trackable`` attempts to be a reusable Django application that provides
infrastructure to easily implement the functionality required to capture
arbitrary tracking data out-of-band. This documentation assumes a basic 
familiarity with `Django`_ and the `Celery`_ package. For usage and installation 
instructions, please review the documentation.

.. _Django: http://djangoproject.org
.. _Celery: http://celeryproject.org


Release notes
-------------

0.3.7
=====

* Bug fixes and migration from carrot -> kombu

0.3.6
=====

* Various bug fixes backported from development

0.3.5
=====

* Correcting stupidity in trackable.views.track_object (proper handling of AJAX-call)

0.3.2 - 0.3.4
=============

* Fixing setuptools configuration to properly include templates and fixtures.

0.3.1
=====

* Renaming trackable.views.trackable_redirect and enabling support for AJAX requests.
* Bug fix (trackable.management.commands.convert_tracking_data)

0.3.0
=====

* Creating extensible message backend (currently supports carrot) 
* Refactoring message/messaging infrastructure
