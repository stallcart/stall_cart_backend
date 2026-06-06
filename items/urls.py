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
    path('seller/dashboard/save/', 
         seller_or_admin_only(views.save_product), 
         name='save_product'),

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
    path('api/image/<int:image_id>/delete/', views.delete_product_image, name='delete_product_image'),     
     path('wishlist/status/<int:product_id>/', views.wishlist_status, name='wishlist_status'),
     path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
     path('wishlist/', views.wishlist_page, name='wishlist'),
      path('review/<int:review_id>/update/', views.update_review, name='update_review'),
    path('review/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    path('review/<int:review_id>/helpful/', views.mark_helpful, name='mark_helpful'),
    path('product/<slug:product_slug>/review/submit/', views.submit_review, name='submit_review'),
    path('seller/<int:seller_id>/review/submit/', views.submit_seller_review, name='submit_seller_review'),
    path('seller/review/<int:review_id>/update/', views.update_seller_review, name='update_seller_review'),
    path('seller/review/<int:review_id>/delete/', views.delete_seller_review, name='delete_seller_review'),
     path('admin/verify-sellers/', views.verify_sellers_view, name='verify_sellers'),
    path('admin/verify-sellers/<int:seller_id>/action/', views.verify_seller_action, name='verify_seller_action'),
    path('admin/api/seller/<int:seller_id>/', views.seller_detail_api, name='seller_detail_api'),
    path('admin/seller/<int:seller_id>/edit/', views.seller_edit_view, name='seller_edit'),

]