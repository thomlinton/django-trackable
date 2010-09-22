================
django-trackable
================

.. toctree::
   getting_started
   running_tests


``Django-trackable`` attempts to be a reusable Django application that provides
infrastructure to easily implement the functionality required to capture
arbitrary tracking data out-of-band. This documentation assumes a basic 
familiarity with `Django`_ and the `Celery`_ package. For usage and installation 
instructions, please review the documentation.

.. _Django: http://djangoproject.org
.. _Celery: http://celeryproject.org


Release notes
-------------

0.2.0
=====

* Refactoring process_messages to remove ad-hoc message structure and to instead utilize pickle.
* Added tests/test infrastructure.
* Restructuring application to operate correctly under (real) concurrency.

0.1.2
=====

* Maintenance release to fix PyPI issues.

0.1.1
=====

* Updating documentation

0.1.0
=====

* Initial release
