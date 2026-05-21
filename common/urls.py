# common/urls.py
from django.urls import path
from . import views

app_name = 'common'

urlpatterns = [
    path('api/fcm/register/',   views.register_fcm_token,   name='fcm_register'),
    path('api/fcm/unregister/', views.unregister_fcm_token, name='fcm_unregister'),
]