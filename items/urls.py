# items/urls.py
from django.urls import path
from django.views.decorators.http import require_POST
from . import views
from common.decorators import seller_only, admin_only, seller_or_admin_only

app_name = 'items'

urlpatterns = [
    # ── Unified Dashboard (Accessible to Sellers AND Admins) ────────────
    path('dashboard/', 
         seller_or_admin_only(views.admin_dashboard), 
         name='admin_dashboard'),

    # ── Seller-specific dashboard ───────────────────────────────────────
    path('seller/dashboard/', 
         seller_only(views.seller_dashboard), 
         name='seller_dashboard'),

    # ── Product CRUD (Accessible to Sellers AND Admins) ─────────────────
    path('product/add/',                        
         seller_or_admin_only(views.product_create),        
         name='product_create'),
         
    path('product/<int:product_id>/edit/',      
         seller_or_admin_only(views.product_edit),          
         name='product_edit'),
         
    path('product/<int:product_id>/toggle/',    
         require_POST(seller_or_admin_only(views.product_toggle_status)), 
         name='product_toggle_status'),
         
    path('product/<int:product_id>/delete/',    
         require_POST(seller_or_admin_only(views.product_delete)),        
         name='product_delete'),

    # ── JSON API (Accessible to Sellers AND Admins) ─────────────────────
    path('api/product/<int:product_id>/',       
         seller_or_admin_only(views.product_api_detail),    
         name='product_api_detail'),

    # ── Public pages ───────────────────────────────────────────────────
    path('products/', 
         views.product_list, 
         name='product_list'),
         
    path('product/<slug:slug>/', 
         views.product_detail, 
         name='product_detail'),
]