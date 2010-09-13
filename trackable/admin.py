from django.contrib import admin
from trackable.models import Spider


class SpiderAdmin(admin.ModelAdmin):
    list_display = ('user_agent',)

admin.site.register(Spider,SpiderAdmin)
