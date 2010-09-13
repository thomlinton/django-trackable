from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _
from django.db.models.loading import get_model
from django.db import models, transaction

from optparse import make_option
from trackable import site

import warnings
import sys


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--update-fields', action='store', dest='update_fields',
            help='A series of one or more key:value pairs delimited by commas '
                 'specifying fields from the existing tracking data model '
                 'with which to update the destination trackable data model'), 
        make_option('--key-fields', action='store', dest='key_fields',
            help='Fields when taken together unambiguously identify a single '
                 'record. A series of one or more key:value pairs delimited by commas '
                 'mapping fields from the existing tracking data model to the '
                 'destination trackable data model'), 
        make_option('--link-field', action='store', dest='link_field',
            help='Related model attribute on source_data_model that links to it\'s parent model. Chaining permitted using dot notation, e.g., attribute.other_attribute'),
        make_option('--match-spec', action='store', dest='match_spec',
            help='String option in the form source_attr:app_label.ModelName[:dest_attr]. Use in place of --link-field'),
        make_option('--max-records', action='store', dest='max_records',
            help='Set a limit on the number of records imported from the given source data model'),
        make_option('--order-by', action='store', dest='order_by',
            help='Specify parameters, delimited by commas, to source_queryset.order_by(...)'),

    )
    help = 'Used to import pre-existing tracking data to trackable data stores.'
    args = 'source_data_model dest_trackable_model'

    @transaction.commit_on_success
    def handle_model_data_migration( self, model_cls, trackable_model_cls, update_fields={}, key_fields={}, link_field='parent', match_spec=None, max_records=0, order_by=[] ):
        """ """
        print "Conversion parameters: "
        print "  Source: %s" % (model_cls._meta.verbose_name)
        print "  Destination: %s" % (trackable_model_cls._meta.verbose_name)
        print "  Update fields: %s" % (update_fields)
        print "  Key fields: %s" % (key_fields)
        print "  Link field: %s" % (link_field)
        print "  Match spec: %s" % (match_spec)
        print "  Max records: %d" % (max_records)
        print "  Order by: %s" % (order_by)

        parent_model_cls = site.get_parent( trackable_model_cls )
        source_queryset = model_cls.objects.all()
        if order_by:
            source_queryset = source_queryset.order_by(*order_by)
        if max_records:
            source_queryset = source_queryset[:max_records]

        instance_cnt = source_queryset.count()
        progress_cnt = 0

        for old_instance in source_queryset:

            parent_object_id = None
            if match_spec:
                match_parts = match_spec.split(':')
                if len(match_parts) == 2:
                    source_attr,model_spec = match_parts
                    dest_attr = source_attr
                elif len(match_parts) == 3:
                    source_attr,model_spec,dest_attr = match_parts
                else:
                    raise CommandError("Invalid match_spec option: %s" % match_spec)

                try:
                    parent_model_cls = get_model(*model_spec.split('.'))

                    source_attr_links = source_attr.split('.')
                    source_attr = getattr(old_instance,source_attr_links[0])
                    for link in source_attr_links[1:]:
                        source_attr = getattr(source_attr,link)
                    source_attr_value = source_attr

                    parent_kwargs = {dest_attr:source_attr_value}
                    parent_instance = parent_model_cls.objects.get(**parent_kwargs)
                    parent_object_id = parent_instance.pk
                except AttributeError, e:
                    raise e
                except parent_model_cls.DoesNotExist, e:
                    continue
            else:
                links = link_field.split('.')
                parent_attr = getattr(old_instance,links[0])
                for link in links[1:]:
                    parent_attr = getattr(parent_attr,link)
                parent_object_id = parent_attr.pk

            if not parent_object_id:
                warnings.warn("Could not determine parent for trackable data model. Skipping")
                continue

            filter_kwargs = {}
            filter_kwargs['content_type'] = \
                ContentType.objects.get_for_model(parent_model_cls)
            filter_kwargs['object_id'] = parent_object_id
            filter_kwargs.update( \
                [(field,getattr( old_instance, field )) for field in key_fields] )

            new_instance, created = trackable_model_cls.objects.get_or_create(**filter_kwargs)
            for source_field,dest_field in update_fields.iteritems():
                try:
                    source_field_value = getattr(old_instance,source_field)
                    setattr(new_instance,dest_field,source_field_value)
                except AttributeError:
                    raise CommandError( \
                        "You specified fields in the update option that do not exist.")
            new_instance.save()

            progress_cnt += 1
            if progress_cnt % 100 == 0:
                print ".",
                sys.stdout.flush()

        print "Migrated %d objects" % (progress_cnt)

    def handle(self, *args, **options):
        """ """
        model_spec,trackable_model_spec = (None,None)
        try:
            (model_spec,trackable_model_spec) = args
        except ValueError:
            raise CommandError("Command takes two arguments")

        model_cls = get_model(*model_spec.split('.'))
        trackable_model_cls = get_model(*trackable_model_spec.split('.'))
        kwargs = {}

        if options.get('key_fields',{}):
            kwargs['key_fields'] = dict([ (pair.split(':')[0],pair.split(':')[1]) for pair in options.get('key_fields').split(',') ])
        if options.get('update_fields',{}):
            kwargs['update_fields'] = dict([ (pair.split(':')[0],pair.split(':')[1]) for pair in options.get('update_fields').split(',') ])
        if options.get('link_field',''):
            kwargs['link_field'] = options.get('link_field')
        if options.get('match_spec',''):
            kwargs['match_spec'] = options.get('match_spec')
        if options.get('max_records',0):
            kwargs['max_records'] = long(options.get('max_records'))
        if options.get('order_by',[]):
            kwargs['order_by'] = options.get('order_by').split(',')

        self.handle_model_data_migration( \
            model_cls, trackable_model_cls, **kwargs )
