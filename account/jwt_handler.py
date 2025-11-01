from jwt import ExpiredSignatureError, InvalidTokenError, encode, decode
from datetime import datetime, timedelta
from django.conf import settings
from django.http import HttpRequest

class JWTHandler:
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or settings.SECRET_KEY
    
    def generate_token(self, payload: dict, expiry_minutes: int = settings.OTP_EXPIRE_TIME) -> str:
        """Generate JWT token using HS256"""
        payload.update({
            'exp': datetime.utcnow() + timedelta(minutes=expiry_minutes),
            'iat': datetime.utcnow()
        })
        return encode(
            payload=payload,
            key=self.secret_key,
            algorithm='HS256'
        )

    def decode_token(self, token: str) -> dict:
        """Decode JWT token"""
        return decode(
            jwt=token,
            key=self.secret_key,
            algorithms=['HS256']
        )

    def verify_token(self, token: str) -> bool:
        """Verify JWT token validity"""
        try:
            decode(
                jwt=token,
                key=self.secret_key,
                algorithms=['HS256']
            )
            return True
        except:
            return False

    def get_verification_token(self, request: HttpRequest, data: dict):
        """Get and validate verification token from cookie"""
        if data.get('verification_token'):
            token = data.get('verification_token')
        else:
            token = request.COOKIES.get('verification_token')
        if not token:
            return None
            
        decoded_token = self.decode_token(token)
        
        return decoded_token