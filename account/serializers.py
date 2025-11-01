# Django imports
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

# Third Party Packages
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from phonenumber_field.serializerfields import PhoneNumberField


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
   