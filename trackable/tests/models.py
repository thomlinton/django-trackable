### these models are for testing

from django.utils.translation import ugettext_lazy as _
from django.db import models


class Page(models.Model):
    """ """
    title = models.CharField(_(u'title'), max_length=128)
    slug = models.SlugField(_(u'slug'))
    abstract = models.TextField(_(u'abstract'))
    content = models.TextField(_(u'content'))

    published_on = models.DateTimeField(_(u'published on'))

    class Meta:
        ordering = ('published_on',)

    def get_absolute_url(self):
        return ('page-detail', (), {'slug':self.slug})
    get_absolute_url = models.permalink(get_absolute_url)

    def __unicode__(self):
        return self.title
