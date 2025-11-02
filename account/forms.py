# Django imports
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    """Custom user creation form with optional password."""
    password1 = forms.CharField(
        label=_('پسورد'),
        widget=forms.PasswordInput,
        required=False,
        help_text=_('اگر خالی بگذارید، پسورد تصادفی ایجاد می‌شود.')
    )
    password2 = forms.CharField(
        label=_('تکرار پسورد'),
        widget=forms.PasswordInput,
        required=False,
        help_text=_('برای تأیید، همان پسورد را دوباره وارد کنید.')
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('phone_number', 'first_name', 'last_name', 'username')

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        
        if not password1 and not password2:
            return password2
        
        if password1 and not password2:
            raise forms.ValidationError(_("لطفاً تکرار پسورد را وارد کنید."))
        if password2 and not password1:
            raise forms.ValidationError(_("لطفاً پسورد را وارد کنید."))
        
        if password1 != password2:
            raise forms.ValidationError(_("پسوردها مطابقت ندارند."))
        
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        password1 = self.cleaned_data.get("password1")
        if password1:
            user.set_password(password1)
        else:
            user.set_unusable_password()
        
        if commit:
            user.save()
        return user

