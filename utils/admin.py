from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import TimeStampedModel

class TimeStampedModelAdmin(admin.ModelAdmin):
    fields = ('jcreated', 'jupdated',)
    fieldsets = (
        (_('وضعیت'), {
            'fields': ('is_active',)
        }),
        (_('تاریخچه'), {
            'fields': ('jcreated', 'jupdated',)
        }),
    )
    readonly_fields = ('jcreated', 'jupdated',)
    list_display = ('jcreated', 'jupdated',)
    list_filter = ('created_at', 'updated_at',)
    date_hierarchy = 'created_at'
