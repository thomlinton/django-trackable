import os.path
import logging


DEBUG = True
TEMPLATE_DEBUG = DEBUG
DEBUG_PROPAGATE_EXCEPTIONS = DEBUG
THUMBNAIL_DEBUG = DEBUG

ADMINS = (
    ('Thom Linton', 'thom.linton@gmail.com'),
)
MANAGERS = ()
INTERNAL_IPS = (
    '127.0.0.1',
)

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Los_Angeles'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False
USE_ETAGS = False

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    'django.template.loaders.eggs.load_template_source',
)

# default timeout is 300s 
CACHE_BACKEND = 'memcached://127.0.0.1:11211/'
# CACHE_BACKEND = 'newcache://127.0.0.1:11211/?binary=true'

# CACHE_MIDDLEWARE_SECONDS = 300
# CACHE_MIDDLEWARE_ANONYMOUS_ONLY = True

MIDDLEWARE_CLASSES = [
    'django.middleware.common.CommonMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
]

TEMPLATE_CONTEXT_PROCESSORS = [
    "django.core.context_processors.debug",
]

AUTHENTICATION_BACKENDS = []

INSTALLED_APPS = [
    'django.contrib.contenttypes',

    'trackable',
    'trackable.tests',

    'south',
    'djcelery',
]

ROOT_URLCONF = 'tests.test_urls'

# Base path info
BASE_PATH = os.path.dirname(__file__)

# Testing settings
# TEST_RUNNER = "djcelery.contrib.test_runner.run_tests"

# Celery settings
# CELERY_RESULT_BACKEND = "cache"
CELERY_QUEUES = {
    "trackable": {
        "exchange": "direct",
        "binding_key": "trackable",
        },
}
CELERY_DEFAULT_QUEUE = "trackable"
CELERY_DEFAULT_EXCHANGE_TYPE = "direct"
CELERY_DEFAULT_ROUTING_KEY = "trackable"

# CELERY_SEND_TASK_ERROR_EMAILS = False
# CELERY_SEND_EVENTS = True

# CELERYD_CONCURRENCY = 2
CELERYD_LOG_LEVEL = 'INFO'

# Carrot settings
BROKER_HOST = "localhost"
BROKER_PORT = 5672
BROKER_VHOST = "/"
BROKER_USER = "guest"
BROKER_PASSWORD = "guest"

TRACKABLE_USER_AGENT_FILTERING = False
TRACKABLE_REMOVE_MALFORMED_MESSAGES = True
TRACKABLE_CAPTURE_CONNECTION_ERRORS = True
TRACKABLE_DISABLE_COLLECTION_TASK = True
# TRACKABLE_LOGLEVEL = logging.DEBUG
TRACKABLE_ENGINE = 'trackable.message.backends.kombu'

FIXTURE_DIRS = (
    os.path.join( BASE_PATH, 'fixtures' )
)
TEMPLATE_DIRS = (
    os.path.join( BASE_PATH, 'templates')
)

try:
    from local_settings import *

    import djcelery
    djcelery.setup_loader()

except ImportError:
    pass
