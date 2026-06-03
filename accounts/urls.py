from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    # Forgot/Reset Password Flow
    path('profile/', views.profile_view, name='profile'),  # ← Add this
    path('latest-otp/', views.latest_otp_view, name='latest_otp'),

    # Forgot/Reset Password Flow with OTP
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('forgot-password/verify/', views.forgot_password_verify_view, name='forgot_password_verify'),
    path('forgot-password/reset/', views.forgot_password_reset_view, name='forgot_password_reset'),
    path('api/send-change-password-otp/', views.send_change_password_otp, name='send_change_password_otp'),
    path('api/address/<int:address_id>/', views.api_address_detail, name='api_address_detail'),

]