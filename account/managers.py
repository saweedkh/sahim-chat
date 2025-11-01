# Django imports
from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, phone_number, first_name, last_name, password=None, **extra_fields):
        if not phone_number:
            raise ValueError(_('شماره تلفن باید تنظیم شود'))
        
        user = self.model(
            first_name = first_name,
            last_name = last_name,
            phone_number=phone_number,
            **extra_fields,
        )
        if password:
            user.set_password(password)
        user.save()
        return user

    def create_superuser(self, phone_number, first_name, last_name, password):
        user = self.create_user(phone_number, first_name, last_name)
        user.is_superuser = True
        user.is_staff = True
        user.set_password(password)
        user.save()
        return user
