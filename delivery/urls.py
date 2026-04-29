# delivery/urls.py
from django.urls import path
from . import views

app_name = 'delivery'  # 🔑 Namespace for {% url 'delivery:... %}

urlpatterns = [
    # ============ DELIVERY PORTAL (Matches delivery.html) ============
    path('', views.delivery_portal, name='portal'),
    
    # ============ AJAX API ENDPOINTS (Replaces Firebase Firestore) ============
    
    # Register new delivery partner (POST)
    path('api/register/', views.register_partner, name='api_register'),
    
    # Fetch assigned tasks for a partner (GET)
    path('api/tasks/', views.get_tasks, name='api_tasks'),
    
    # Update task status: Out for Delivery / Delivered (POST)
    path('api/update/<uuid:task_id>/', views.update_task_status, name='api_update'),
]