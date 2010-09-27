from django.core.exceptions import ImproperlyConfigured
from django.utils.importlib import import_module
from django.conf import settings

import os


def load_backend(backend_name):
    try:
        return import_module('.base', 'trackable.message.backends.%s' % backend_name)
    except ImportError, e:
        try:
            return import_module('.base', backend_name)
        except ImportError, e_user:
            backend_dir = os.path.join(os.path.dirname(__file__), 'backends')
            try:
                available_backends = [f for f in os.listdir(backend_dir)
                                      if os.path.isdir(os.path.join(backend_dir, f))
                                      and not f.startswith('.')]
            except EnvironmentError:
                available_backends = []
            available_backends.sort()
            if backend_name not in available_backends:
                error_msg = ("%r isn't an available database backend. \n" +
                    "Try using trackable.message.backends.XXX, where XXX is one of:\n    %s\n" +
                    "Error was: %s") % \
                    (backend_name, ", ".join(map(repr, available_backends)), e_user)
                raise ImproperlyConfigured(error_msg)
            else:
                raise
