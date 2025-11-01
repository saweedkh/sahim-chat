# Django imports
from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

# Local imports
from utils.admin import TimeStampedModelAdmin
from utils.jdatetime import humanize_and_pretty_jalali_datetime
from .models import User, OTP

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    
    fieldsets = (
        (
            _('اطلاعات'),
            {
                'classes': ('wide',),
                'fields': ('phone_number', 'first_name', 'last_name', 'username', 'password', 'get_last_password_change_jalali')
            }
        ),
        (_("تصویر"), {
            'fields': ('profile_picture', 'profile_picture_preview')
        }),
        (
            _('لاگ'),
            {
                'classes': ('collapse',),
                'fields': ('get_last_login_jalali',) 
            }
        ),
        (
            _('مجوز ها'),
            {
                'classes': ('collapse',),
                'fields': ( 'is_staff', 'is_superuser', 'groups', 'user_permissions',),
            }
        ),
        *TimeStampedModelAdmin.fieldsets,
    )
    add_fieldsets = (
        (
            _('اطلاعات'),
            {
                'classes': ('wide',),
                'fields': (
                    'phone_number', 'first_name', 'last_name', 'username', 'password', 
                )
            }
        ),
        (
            _('مجوز ها'),
            {
                'classes': ('collapse',),
                'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions',),
            }
        ),
    )
    readonly_fields = (*TimeStampedModelAdmin.readonly_fields, 'get_last_login_jalali', 'get_last_password_change_jalali','profile_picture_preview')
    list_display = ('id', 'get_phone_number', 'display_fullname', 'username', 'is_superuser',)
    list_filter = ('is_staff', 'is_superuser', 'is_active',)
    search_fields = ('phone_number', 'first_name', 'last_name', 'username',)
    ordering = ('-created_at',)
    save_on_top = True

    @admin.display(description=_('شماره تلفن'), empty_value='-')
    def get_phone_number(self, obj):
        if obj.phone_number:
            number = str(obj.phone_number.national_number)
            # Format: 0912 345 6789
            return f"0{number[:3]}-{number[3:6]}-{number[6:]}"
        return '-'

    @admin.display(description=_('نام و نام خانوادگی'), empty_value='-')
    def display_fullname(self, obj):
        return f'{obj.fullname}'

    @admin.display(description=_('آخرین ورود'))
    def get_last_login_jalali(self, obj):
        if obj.last_login:
            return humanize_and_pretty_jalali_datetime(obj.last_login)
        return '-'
    
    @admin.display(description=_('تاریخ آخرین تغییر پسورد'))
    def get_last_password_change_jalali(self, obj):
        if obj.last_password_change:
            return humanize_and_pretty_jalali_datetime(obj.last_login)
        return '-'
    
    def profile_picture_preview(self, obj):
        profile_picture = obj.get_profile_picture(self.request)
        if profile_picture:
            return format_html(
                '<img src="{}" style="width: 200px; height: 200px; object-fit: cover; border-radius: 10px;" />',
                profile_picture
            )
        return _("بدون تصویر")
    profile_picture_preview.short_description = _("پیش‌نمایش")


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('phone_number', *TimeStampedModelAdmin.list_display)
    fieldsets = (
        (_('اطلاعات'), {
            'fields': ('phone_number', 'code', 'expires_at', 'is_used')
        }),
        *TimeStampedModelAdmin.fieldsets
    )
    readonly_fields = (*TimeStampedModelAdmin.readonly_fields,)

