.. _running_tests:


=============
Running tests
=============


In order to run the tests packaged with Django-trackable as a standalone application, utilize the buildout recipes to build the application and ensure that ``celeryd`` is assigned the correct (testing) database while running. E.g.,::

    DATABASES = {
        'default': {
	    'NAME': '<name of chosen test database>'

    ...
