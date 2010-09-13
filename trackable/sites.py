"""
Emulates the behaviour of a django ``AdminSite``.

Implementation is modified directly from ``django.contrib.admin.sites.AdminSite``
in order to maintain ``AdminSite`` semantics.

"""
from django.utils.translation import ugettext_lazy, ugettext as _
from django.utils.functional import update_wrapper
from django.utils.safestring import mark_safe
from django.db.models.base import ModelBase
from django.utils.text import capfirst
from django.contrib import admin
from django.conf import settings

import re


REGISTER_ADMIN_MODELS = getattr(settings,'TRACKABLE_REGISTER_ADMIN_MODELS',settings.DEBUG)

class AlreadyRegistered(Exception):
    pass

class NotRegistered(Exception):
    pass


class TrackableDataAdmin(admin.ModelAdmin):
    list_display = ('parent',)

class TrackableRegistry(object):
    """ """

    def __init__(self, name=None):
        self._registry = {} # model_class class -> admin_class instance
        self._actions = {}
        self._global_actions = self._actions.copy()

    def register(self, model_or_iterable, trackable_cls=None, admin_cls=None, **options):
        """
        Registers the given model(s) with the given trackable data class.

        The model(s) should be Model classes, not instances.


        If a model is already registered, this will raise AlreadyRegistered.
        """
        if not admin_cls:
            admin_cls = TrackableDataAdmin
        if isinstance(model_or_iterable, ModelBase):
            model_or_iterable = [model_or_iterable]
        for model in model_or_iterable:
            if model not in self._registry:
                self._registry[model] = [trackable_cls,]
            else:
                self._registry[model].append(
                    trackable_cls
                    )
            if REGISTER_ADMIN_MODELS:
                admin.site.register(trackable_cls,admin_cls)

    def unregister(self, model_or_iterable):
        """
        Unregisters the given model(s).

        If a model isn't already registered, this will raise NotRegistered.
        """
        if isinstance(model_or_iterable, ModelBase):
            model_or_iterable = [model_or_iterable]
        for model in model_or_iterable:
            if model not in self._registry:
                raise NotRegistered('The model %s is not registered' % model.__name__)
            trackable_cls = self._registry[model]
            del self._registry[model]
            admin.site.unregister(trackable_cls)

    def get_parent(self, trackable_cls):
        """ """
        for model_cls,trackable_models in self._registry.iteritems():
            for trackable_model_cls in trackable_models:
                if trackable_model_cls == trackable_cls:
                    return model_cls

        raise NotRegistered( \
            'The model %s has not been registered to track any model' % trackable_cls.__name__)

    def add_action(self, action, name=None):
        """
        Register an action to be available globally.
        """
        name = name or action.__name__
        self._actions[name] = action
        self._global_actions[name] = action

    def disable_action(self, name):
        """
        Disable a globally-registered action. Raises KeyError for invalid names.
        """
        del self._actions[name]

    def get_action(self, name):
        """
        Explicitally get a registered global action wheather it's enabled or
        not. Raises KeyError for invalid names.
        """
        return self._global_actions[name]

    def actions(self):
        """
        Get all the enabled actions as an iterable of (name, func).
        """
        return self._actions.iteritems()
    actions = property(actions)

# This global object represents the default trackable site, for the common case.
# You can instantiate TrackableRegistry in your own code to create a custom trackable registry.
site = TrackableRegistry()
