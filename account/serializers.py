# Django imports
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.conf import settings

# Third Party Packages
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from phonenumber_field.serializerfields import PhoneNumberField

# Python imports
import os
from datetime import datetime


User = get_user_model()

class CustomTokenObtainPairSerializer(serializers.Serializer):
    token_class = RefreshToken

    phone_number = PhoneNumberField()

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')
        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            raise serializers.ValidationError(_("کاربر با این شماره موبایل وجود ندارد."))

        refresh = self.get_token(user)
    
        return { 
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

    
    @classmethod
    def get_token(cls, user):
        return cls.token_class.for_user(user)

class OtpSendSerializer(serializers.Serializer):
    phone_number = PhoneNumberField()
    class Meta:
        fields = ('phone_number',)
    
class VerifySerializer(serializers.ModelSerializer):
    """
        Verify Serializers
    """
    phone_number = PhoneNumberField()
    code = serializers.IntegerField()

    class Meta:
        model = User
        fields = (
            'phone_number', 
            'code',
            'created_at',
            'updated_at',
        )
        optional_fields = ('phone_number', 'code',)
        read_only_fields = ('created_at', 'updated_at')
        
class LoginWithPasswordSerializer(serializers.ModelSerializer):
    """
        Login With Password Serializers
    """
    
    phone_number = PhoneNumberField()
    password = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = (
            'phone_number', 
            'password',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('created_at', 'updated_at')

class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile (GET and UPDATE)."""
    phone_number = PhoneNumberField(read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    profile_picture_url = serializers.SerializerMethodField()
    profile_picture = serializers.ImageField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = (
            'id',
            'phone_number',
            'username',
            'first_name',
            'last_name',
            'full_name',
            'profile_picture',
            'profile_picture_url',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'phone_number', 'created_at', 'updated_at')
    
    def validate_username(self, value):
        """Validate that username is unique (except for current user)."""
        if value:
            user = self.context['request'].user
            if User.objects.filter(username=value).exclude(id=user.id).exists():
                raise serializers.ValidationError(_('این نام کاربری قبلاً استفاده شده است.'))
        return value
    
    def get_profile_picture_url(self, obj):
        """Return full URL for profile picture."""
        return obj.get_profile_picture(self.context.get('request'))

   