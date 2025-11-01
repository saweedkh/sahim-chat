# Django imports
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

# Local imports
from utils.models import TimeStampedModel
from .managers import UserManager

# Third party imports
from phonenumber_field.modelfields import PhoneNumberField

# Models
class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    phone_number = PhoneNumberField(
        verbose_name=_('شماره تلفن'),
        unique=True,
        db_index=True,
    )
    username = models.CharField(
        max_length=150,
        verbose_name=_('نام کاربری'),
        unique=True,
        db_index=True,
        blank=True,
        null=True,
    )
    first_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('نام')
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('نام خانوادگی')
    )
    profile_picture = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('تصویر پروفایل')
    )
    is_staff = models.BooleanField(
        default=False,
        verbose_name=_('وضعیت کاربری'),
        help_text=_('تعیین می کند که آیا کاربر می تواند وارد سایت ادمین شود.')
    )
    is_superuser = models.BooleanField(
        default=False,
        verbose_name=_('وضعیت ادمین'),
        help_text=_('تعیین می کند که آیا کاربر دارای تمام دسترسی ها است.')
    )

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = _('کاربر')
        verbose_name_plural = _('کاربران')
        indexes = [
            models.Index(fields=['phone_number'], name='idx_user_phone_number'),
            models.Index(fields=['username'], name='idx_user_username'),
        ]

    def __str__(self):
        if self.username:
            return f"{self.username} ({self.phone_number})"
        return self.phone_number

    @property
    def fullname(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return str(self.phone_number)

    def get_full_name(self):
        return self.fullname

    def get_short_name(self):
        return self.first_name or str(self.phone_number)


class OTP(TimeStampedModel):
    phone_number = PhoneNumberField(
        verbose_name=_('شماره تلفن'),
        db_index=True,
    )
    code = models.CharField(
        max_length=5,
        verbose_name=_('کد یکبار مصرف'),
    )
    expires_at = models.DateTimeField(
        verbose_name=_('زمان انقضا'),
    )
    is_used = models.BooleanField(
        default=False,
        verbose_name=_('وضعیت استفاده'),
    )

    class Meta:
        indexes = [
            models.Index(fields=['phone_number'], name='idx_otp_phone_number'),
        ]

    def __str__(self):
        return f"کد یکبار مصرف برای {self.phone_number} - {self.code}"
