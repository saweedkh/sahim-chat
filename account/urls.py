# Django imports
from django.urls import path

# Local improts
from . import views

urlpatterns = [
    path('otp/send/', views.SendOtpView.as_view(), name='otp_send'),
    path('otp/verify/', views.OtpVerifyView.as_view(), name='otp_verify'),
    path('login/password/', views.LoginWithPasswordView.as_view(), name='login_with_password'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
]
