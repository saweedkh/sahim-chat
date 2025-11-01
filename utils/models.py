# Django imports
from django.db import models
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from utils.jdatetime import humanize_and_pretty_jalali_datetime


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('فعال'),
    )

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save()

    
    @admin.display(description=_('ایجاد شده'), empty_value='-')
    def jcreated(self):
        return humanize_and_pretty_jalali_datetime(self.created_at)

    jcreated.admin_order_field = 'created_at'

    @admin.display(description=_('آپدیت شده'), empty_value='-')
    def jupdated(self):
        return humanize_and_pretty_jalali_datetime(self.updated_at)

    jupdated.admin_order_field = 'updated_at'
