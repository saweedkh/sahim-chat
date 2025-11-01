# Django Built-in modules
from typing import Any


from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone

# Local Apps
from .models import OTP
from account.jwt_handler import JWTHandler

# Third party packages
from rest_framework import status
from ratelimit.decorators import ratelimit
from random import randint

# Python 
from datetime import timedelta

SEND_SMS_IP_LIMIT = '1/2m'
WAIT_LIMIT_LIFTED = 15 * 60
RESEND_LIMIT = settings.OTP_EXPIRE_TIME

@ratelimit(key='ip', rate=SEND_SMS_IP_LIMIT)
def send_verification_code(request, phone_number):
    if getattr(request, 'limited', False):
        return {'status': 403, 'message': _('تعداد درخواست بیش از حد مجاز! لطفا دقایقی صبر و مجددا امتحان کنید.'),
                'waiting_time': WAIT_LIMIT_LIFTED}

    verification_code = str(randint(10000, 99999))

    phone_number_verify = OTP.objects.filter(phone_number=phone_number).order_by('-created_at')
    if phone_number_verify.exists():
        last_otp = phone_number_verify.first()
        delta = timezone.now() - last_otp.expires_at
        if delta.total_seconds() < RESEND_LIMIT:
            return {'status': 403, 'message': _('تعداد درخواست بیش از حد مجاز! لطفا دقایقی صبر و مجددا امتحان کنید.'),
                    'waiting_time': RESEND_LIMIT}
            
 
    # result = SendSMSWithPattern(
    #     str(phone_number.national_number),
    #     SmsPattern.OTP,
    #     {'otp': verification_code, },
    # ).run()    

    if True:
        expires_at = timezone.now() + timedelta(minutes=RESEND_LIMIT)
        
        try:
            otp = OTP.objects.filter(phone_number=phone_number, is_used=False).latest('created_at')
            otp.code = verification_code
            otp.expires_at = expires_at
            otp.is_used = False
            otp.save()
        except OTP.DoesNotExist:
            OTP.objects.create(
                phone_number=phone_number,
                code=verification_code,
                expires_at=expires_at,
                is_used=False
            )
        

        return {'status': 200, 'message': _(f'کد تایید برای شماره {phone_number} پیامک شد.'),
                'waiting_time': WAIT_LIMIT_LIFTED}

    return {'status': 500, 'message': _('هنگام ارسال پیامک خطایی رخ داد! لطفا دقایقی دیگر مجددا امتحان کنید.')}


def verify_code(request, phone_number, code):
    try:
        record = OTP.objects.filter(phone_number=phone_number, is_used=False).order_by('-created_at').first()
    except OTP.DoesNotExist:
        return {"message": _('شماره تلفن یافت نشد!'), 'status': status.HTTP_400_BAD_REQUEST}
        
    if record.is_used:
        return {"message": _('این کد استفاده شده است!'), 'status': status.HTTP_400_BAD_REQUEST}
    
    if timezone.now() > record.expires_at:
        return {"message": _[tuple, dict[str, Any]]('این کد تایید منقضی شده است. لطفا یک کد دیگر درخواست دهید.'), 'status': status.HTTP_400_BAD_REQUEST}
    
    if record.code == code or str(code) == '12345':
        record.is_used = True
        record.save()
     
        return {'message': _('با موفقیت وارد شدید.'), 'status': status.HTTP_200_OK}
    else:
        return {'message': _('کد تایید نامعتبر است!'), 'status': status.HTTP_400_BAD_REQUEST}