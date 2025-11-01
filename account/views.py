# Django imports
from django.utils.translation import gettext_lazy as _

# Local imports
from .models import User
from .serializers import OtpSendSerializer, VerifySerializer, LoginWithPasswordSerializer, CustomTokenObtainPairSerializer
from .utils import send_verification_code, verify_code

# Third Party Packages
from rest_framework import status
from rest_framework.response import Response
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import UserRateThrottle

class SendOtpView(generics.GenericAPIView, UserRateThrottle):
    """
    API view to send OTP (One-Time Password) to a mobile number for verification.
    
    This view sends an OTP code to the provided mobile number which can be used 
    for login or registration verification. Rate limiting is applied to prevent 
    abuse and spam.
    
    Permissions:
        - AllowAny: No authentication required
    
    Request Data:
        - mobile_number (str): The mobile number to send OTP to
            * Must be a valid mobile number format
            * Required field
    
    Returns:
        - Success (200): OTP sent successfully
            * msg: Success message
        - Error (400): Invalid request data
            * Validation errors from serializer
        - Error (429): Rate limit exceeded
    
    Rate Limiting:
        - UserRateThrottle: Prevents excessive OTP requests
    
    Example:
        POST /api/account/send-otp/
        {
            "mobile_number": "09123456789"
        }
        
        Response:
        {
            "msg": "OTP sent successfully"
        }
    """
    permission_classes = [AllowAny]
    serializer_class = OtpSendSerializer
    model = User

    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            srz_data = serializer.validated_data
            mobile_number = srz_data.get('mobile_number')

            result = send_verification_code(request, mobile_number)
            return Response({'msg': result.get('message')}, status=result.get('status'))
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                   
class OtpVerifyView(generics.GenericAPIView):
    """
    API view to verify OTP code and handle login/registration flow.
    
    This view verifies the OTP code sent to a mobile number and determines
    the appropriate action based on user existence. For existing users,
    it performs login and returns authentication tokens. For new users,
    it provides a verification token for registration.
    
    Permissions:
        - AllowAny: No authentication required
    
    Request Data:
        - mobile_number (str): The mobile number that received the OTP
            * Must match the number OTP was sent to
            * Required field
        - code (str): The OTP code received via SMS
            * 4-6 digit verification code
            * Required field
    
    Returns:
        - Existing User Login (200): User authenticated successfully
            * msg: Success message
            * refresh: JWT refresh token
            * access: JWT access token
            * mobile_number: User's mobile number
            * need_register: false
        - New User Verification (200): OTP verified for registration
            * msg: Verification success message
            * verification_token: Token for registration process
            * need_register: true
        - Error (400): Invalid OTP or expired code
            * msg: Error message
    
    Flow:
        1. Verify OTP code
        2. Check if user exists with mobile number
        3. If exists: Generate tokens and login
        4. If not exists: Provide verification token for registration
    
    Example:
        POST /api/account/verify-otp/
        {
            "mobile_number": "09123456789",
            "code": "1234"
        }
        
        Response (Existing User):
        {
            "msg": "با موفقیت وارد شدید.",
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "mobile_number": "09123456789",
            "need_register": false
        }
    """
    serializer_class = VerifySerializer
    permission_classes = [AllowAny]
    model = User
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            srz_data = serializer.data
            mobile_number = srz_data.get('mobile_number')
            code = srz_data.get('code')

            user = User.objects.filter(mobile_number=mobile_number)
            if user.exists():
                # login
                result = verify_code(request, mobile_number, code)
                status_code = result.get('status')
                if status_code == status.HTTP_200_OK:
                    token_serializer = CustomTokenObtainPairSerializer(data={'mobile_number': mobile_number})
                    try:
                        token_serializer.is_valid(raise_exception=True)
                        refresh = token_serializer.validated_data
                    except Exception as e:
                        return Response({"msg": str(e)}, status=status.HTTP_400_BAD_REQUEST)
                    
                    user_avatar = user.first().get_avatar()
                    return Response({
                        "msg": _('با موفقیت وارد شدید.'),
                        "refresh": refresh['refresh'],
                        "access": refresh['access'],
                        "mobile_number": mobile_number,
                        "need_register": False,
                        "role": user.first().role,
                        "avatar": request.build_absolute_uri(user_avatar) if user_avatar else None
                    }, status=status.HTTP_200_OK)
                else :
                    return Response({"msg": 'کد تایید نامعتبر است'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                # redirect to register
                result = verify_code(request, mobile_number, code)
                status_code = result.get('status')
                if status_code == status.HTTP_200_OK:
                    response = Response({"msg": 'کد تایید شد'}, status=status.HTTP_200_OK)

                    if result.get('encoded_data'):
                        response.data['verification_token'] = result.get('encoded_data')
                        response.data['need_register'] = True                         
                    return response

                else:
                    return Response({"msg": result.get('message')}, status=status_code)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class LoginWithPasswordView(generics.GenericAPIView):
    """
    API view for user authentication using mobile number and password.
    
    This view authenticates existing users using their mobile number and password
    credentials. It validates the user's account status, password correctness,
    and returns authentication tokens along with user profile information.
    
    Permissions:
        - AllowAny: No authentication required
    
    Request Data:
        - mobile_number (str): User's registered mobile number
            * Must be a valid and registered mobile number
            * Required field
        - password (str): User's account password
            * Must match the user's current password
            * Required field
    
    Returns:
        - Success (200): User authenticated successfully
            * msg: Success message
            * refresh: JWT refresh token
            * access: JWT access token
            * user: User profile information
                - mobile_number: User's mobile number
                - first_name: User's first name
                - last_name: User's last name
                - full_name: User's full name
                - email: User's email address
                - role: User's role in system
                - avatar: User's avatar URL
                - gender: User's gender
        - Error (404): User not found
            * msg: User with mobile number does not exist
        - Error (400): Invalid password
            * msg: Incorrect password message
        - Error (403): Account inactive
            * msg: Account deactivated message
    
    Validations:
        - User existence check
        - Password verification
        - Account active status check
        - Token generation validation
    
    Example:
        POST /api/account/login/
        {
            "mobile_number": "09123456789",
            "password": "mypassword123"
        }
        
        Response:
        {
            "msg": "با موفقیت وارد شدید.",
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "user": {
                "mobile_number": "09123456789",
                "first_name": "John",
                "last_name": "Doe",
                "full_name": "John Doe",
                "email": "john@example.com",
                "role": "customer",
                "avatar": "http://example.com/media/avatars/default.png",
                "gender": "male"
            }
        }
    """
    serializer_class = LoginWithPasswordSerializer
    permission_classes = [AllowAny]
    model = User
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            srz_data = serializer.data
            mobile_number = srz_data.get('mobile_number')
            password = srz_data.get('password')
            
            try:
                user = User.objects.get(mobile_number=mobile_number)
            except User.DoesNotExist:
                return Response({"msg": _("کاربر با این شماره موبایل وجود ندارد."), }, status=status.HTTP_404_NOT_FOUND)
            if not user.password:
                return Response({"msg": _("رمز عبور اشتباه است.")}, status=status.HTTP_400_BAD_REQUEST)
            if not user.check_password(password):
                return Response({"msg": _("رمز عبور اشتباه است.")}, status=status.HTTP_400_BAD_REQUEST)
            
            if not user.is_active_user:
                return Response({"msg": _("حساب کاربری شما غیرفعال است.")}, status=status.HTTP_403_FORBIDDEN)

            token_serializer = CustomTokenObtainPairSerializer(data={'mobile_number': mobile_number})
            try:
                token_serializer.is_valid(raise_exception=True)
                tokens = token_serializer.validated_data
            except Exception as e:
                return Response({"msg": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            user_avatar = user.get_avatar()
            return Response({
                "msg": _("با موفقیت وارد شدید."),
                "refresh": tokens['refresh'],
                "access": tokens['access'],
                "user": {
                    "mobile_number": mobile_number,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "full_name": user.get_full_name(),
                    "email": user.email,
                    "role": user.role,
                    "avatar": request.build_absolute_uri(user_avatar) if user_avatar else None,
                    "gender": user.gender
                }
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
 