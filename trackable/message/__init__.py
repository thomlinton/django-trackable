from trackable.message.utils import load_backend
from django.conf import settings


backend = load_backend(settings.TRACKABLE_ENGINE)
connection = backend.MessageBackend()
