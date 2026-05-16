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

    path('forgot-password/', views.CustomPasswordResetView.as_view(), name='forgot_password'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('api/address/<int:address_id>/', views.api_address_detail, name='api_address_detail'),

]