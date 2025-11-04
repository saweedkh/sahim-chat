# Django imports
from typing import Any
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend

from chat.serializers import UserSerializer

# Local imports
from .models import User
from .serializers import OtpSendSerializer, VerifySerializer, LoginWithPasswordSerializer, CustomTokenObtainPairSerializer, ProfileSerializer
from .utils import send_verification_code, verify_code

# Third Party Packages
from rest_framework import filters, status
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
        - phone_number (str): The mobile number to send OTP to
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
            "phone_number": "09123456789"
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
            phone_number = srz_data.get('phone_number')

            result = send_verification_code(request, phone_number)
            return Response({'msg': result.get('message')}, status=result.get('status'))
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                   
class OtpVerifyView(generics.GenericAPIView):
    """
    API view to verify OTP code and handle login/registration flow.
    
    This view verifies the OTP code sent to a mobile number and automatically
    handles both login and registration. For existing users, it performs login
    and returns authentication tokens. For new users (if user doesn't exist),
    it automatically creates the user account and returns authentication tokens.
    
    Permissions:
        - AllowAny: No authentication required
    
    Request Data:
        - phone_number (str): The mobile number that received the OTP
            * Must match the number OTP was sent to
            * Required field
        - code (str): The OTP code received via SMS
            * 4-6 digit verification code
            * Required field
    
    Returns:
        - Success (200): User authenticated/created successfully
            * msg: Success message
            * refresh: JWT refresh token
            * access: JWT access token
            * phone_number: User's mobile number
            * need_register: false (always false, registration is automatic)
            * profile_picture: User's profile picture URL (if exists)
        - Error (400): Invalid OTP or expired code
            * msg: Error message
    
    Flow:
        1. Verify OTP code
        2. Check if user exists with mobile number
        3. If exists: Generate tokens and login
        4. If not exists: Automatically create user account and generate tokens
    
    Example:
        POST /api/account/otp/verify/
        {
            "phone_number": "09123456789",
            "code": "12345"
        }
        
        Response (Existing User or New User):
        {
            "msg": "با موفقیت وارد شدید." or "حساب کاربری شما با موفقیت ایجاد شد و وارد شدید.",
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "phone_number": "09123456789",
            "need_register": false,
            "profile_picture": null
        }
    """
    serializer_class = VerifySerializer
    permission_classes = [AllowAny]
    model = User
    
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        phone_number = serializer.validated_data.get('phone_number')
        code = serializer.validated_data.get('code')
        
        result = verify_code(request, phone_number, code)
        if result.get('status') != status.HTTP_200_OK:
            return Response({"msg": result.get('message', 'کد تایید نامعتبر است')}, status=result.get('status'))
        
        try:
            user = User.objects.get(phone_number=phone_number)
            success_msg = _('با موفقیت وارد شدید.')
        except User.DoesNotExist:
            try:
                user = User.objects.create_user(
                    phone_number=phone_number,
                )
                success_msg = _('حساب کاربری شما با موفقیت ایجاد شد و وارد شدید.')
            except Exception as e:
                return Response({"msg": f"خطا در ایجاد حساب کاربری: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        
        token_serializer = CustomTokenObtainPairSerializer(data={'phone_number': phone_number})
        try:
            token_serializer.is_valid(raise_exception=True)
            refresh = token_serializer.validated_data
        except Exception as e:
            return Response({"msg": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        profile_picture = user.get_profile_picture(request)
        
        return Response({
            "msg": success_msg,
            "refresh": refresh['refresh'],
            "access": refresh['access'],
            "phone_number": str(phone_number),
            "need_register": False,
            "profile_picture": profile_picture
        }, status=status.HTTP_200_OK)
    
class LoginWithPasswordView(generics.GenericAPIView):
    """
    API view for user authentication using mobile number and password.
    
    This view authenticates existing users using their mobile number and password
    credentials. It validates the user's account status, password correctness,
    and returns authentication tokens along with user profile information.
    
    Permissions:
        - AllowAny: No authentication required
    
    Request Data:
        - phone_number (str): User's registered mobile number
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
                - phone_number: User's mobile number
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
            "phone_number": "09123456789",
            "password": "mypassword123"
        }
        
        Response:
        {
            "msg": "با موفقیت وارد شدید.",
            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "user": {
                "phone_number": "09123456789",
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
            phone_number = srz_data.get('phone_number')
            password = srz_data.get('password')
            
            try:
                user = User.objects.get(phone_number=phone_number)
            except User.DoesNotExist:
                return Response({"msg": _("کاربر با این شماره موبایل وجود ندارد."), }, status=status.HTTP_404_NOT_FOUND)
            if not user.password:
                return Response({"msg": _("رمز عبور اشتباه است.")}, status=status.HTTP_400_BAD_REQUEST)
            if not user.check_password(password):
                return Response({"msg": _("رمز عبور اشتباه است.")}, status=status.HTTP_400_BAD_REQUEST)
            
            if not user.is_active:
                return Response({"msg": _("حساب کاربری شما غیرفعال است.")}, status=status.HTTP_403_FORBIDDEN)

            token_serializer = CustomTokenObtainPairSerializer(data={'phone_number': phone_number})
            try:
                token_serializer.is_valid(raise_exception=True)
                tokens = token_serializer.validated_data
            except Exception as e:
                return Response({"msg": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            profile_picture = user.get_profile_picture(request)
            return Response({
                "msg": _("با موفقیت وارد شدید."),
                "refresh": tokens['refresh'],
                "access": tokens['access'],
                "user": {
                    "phone_number": phone_number,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "full_name": user.get_full_name(),
                    "profile_picture": profile_picture,
                }
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(generics.RetrieveUpdateAPIView):
    """
    API view to get and update user profile.
    
    This view allows authenticated users to retrieve and update their profile information
    including username, first_name, last_name, and profile_picture.
    
    Permissions:
        - IsAuthenticated: User must be authenticated
    
    Methods:
        - GET: Retrieve current user's profile
        - PUT: Full update of user profile
        - PATCH: Partial update of user profile
    
    Returns:
        - GET (200): User profile information
            * id: User ID
            * phone_number: User's phone number (read-only)
            * username: User's username
            * first_name: User's first name
            * last_name: User's last name
            * full_name: User's full name (read-only)
            * profile_picture_url: Full URL to profile picture (read-only)
            * created_at: Account creation date (read-only)
            * updated_at: Last update date (read-only)
        - PUT/PATCH (200): Updated profile information
    
    Example:
        GET /api/account/profile/
        
        Response:
        {
            "id": 1,
            "phone_number": "09123456789",
            "username": "john_doe",
            "first_name": "John",
            "last_name": "Doe",
            "full_name": "John Doe",
            "profile_picture_url": "http://example.com/media/profile_pictures/1_20240101_120000.jpg",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T12:00:00Z"
        }
        
        PUT /api/account/profile/
        {
            "username": "new_username",
            "first_name": "Jane",
            "last_name": "Smith",
            "profile_picture": <file>
        }
    """
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Return the current authenticated user."""
        return self.request.user
 

class UsersListView(generics.ListAPIView):
    """
    API view to list all users.
    
    This view lists all users in the system.
    
    Permissions:
        - IsAuthenticated: User must be authenticated
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    search_fields = ['phone_number', 'username']
    queryset = User.objects.all()