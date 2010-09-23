from django.core.management.base import BaseCommand, CommandError
from django.db.models.loading import get_model

from trackable.messaging import process_messages
from trackable.sites import site, NotRegistered


class Command(BaseCommand):
    help = 'Used to generate summary data for Vendor tracking data.'
    args = 'app.trackable_model [app.trackable_model ...]'

    def handle(self, *trackable_model_specs, **options):
        for model_spec in trackable_model_specs:
            print "Processing messages for trackable model %s" % (model_spec)
            try:
                app_label,model = model_spec.split('.')
                model_cls = get_model(app_label,model)
                if model_cls is None:
                    raise CommandError("Unknown model: %s.%s" % (app_label,model))
            except ValueError:
                raise CommandError("Use full appname.ModelName specification for argument %s" % model_spec)
            try:
                site.get_parent( model_cls )
            except NotRegistered, e:
                raise CommandError( str(e) )
            process_messages(model_cls=model_cls)
        if not len(trackable_model_specs):
            print "Processing messages for all trackable models"
            process_messages()
