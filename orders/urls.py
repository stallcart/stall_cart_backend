# orders/urls.py
from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views

app_name = 'orders'

urlpatterns = [
    # ==================== CUSTOMER URLS ====================
    
    # My Orders (list)
    path('my-orders/', 
         login_required(views.my_orders), 
         name='my_orders'),
    
    # Order Detail (tracking timeline)
    path('order/<str:order_id>/', 
         login_required(views.order_detail), 
         name='order_detail'),
    
    # Cancel Order
    path('order/<str:order_id>/cancel/', 
         login_required(views.cancel_order), 
         name='cancel_order'),
    
    # Request Return for an item
    path('return/<int:order_item_id>/', 
         login_required(views.request_return), 
         name='request_return'),
    
    # Return Request Detail
    path('return/<int:return_id>/', 
         login_required(views.return_detail), 
         name='return_detail'),
    
    # Download Invoice
    path('order/<str:order_id>/invoice/', 
         login_required(views.download_invoice), 
         name='invoice'),
    
    # ==================== SELLER URLS ====================
    
    # Seller's Orders (items from their products)
    path('seller/orders/', 
         login_required(views.seller_orders), 
         name='seller_orders'),
    
    # Seller Order Detail (view order with their items)
    path('seller/order/<str:order_id>/', 
         login_required(views.seller_order_detail), 
         name='seller_order_detail'),
    
    # Seller: Update Order Status (e.g., mark as shipped)
    path('seller/order/<str:order_id>/update-status/', 
         login_required(views.seller_update_status), 
         name='seller_update_status'),
    
    # Seller: Add Tracking Number
    path('seller/order/<str:order_id>/add-tracking/', 
         login_required(views.seller_add_tracking), 
         name='seller_add_tracking'),
    
    # ==================== ADMIN URLS (Optional) ====================
    
    # Admin: All Orders (system-wide)
    path('admin/orders/', 
         login_required(views.admin_orders), 
         name='admin_orders'),
    
    # Admin: Order Detail (full view)
    path('admin/order/<str:order_id>/', 
         login_required(views.admin_order_detail), 
         name='admin_order_detail'),
    
    # Admin: Update Any Order Status
    path('admin/order/<str:order_id>/update-status/', 
         login_required(views.admin_update_status), 
         name='admin_update_status'),
    
    # ==================== WEBHOOKS & API ====================
    
    # Razorpay Payment Webhook
    path('razorpay-webhook/', 
         views.razorpay_webhook, 
         name='razorpay_webhook'),
    
    # Shiprocket Webhook (for delivery tracking updates)
    path('shiprocket-webhook/', 
         views.shiprocket_webhook, 
         name='shiprocket_webhook'),
    
    # ==================== PUBLIC/UTILITY ====================
    
    # Track Order (public, no login required - like Flipkart)
    path('track/<str:order_id>/', 
         views.track_order_public, 
         name='track_order_public'),
    
    # Order Success Page (after payment)
    path('success/<str:order_id>/', 
         views.order_success, 
         name='order_success'),
    
    # Order Failed Page
    path('failed/', 
         views.order_failed, 
         name='order_failed'),
]