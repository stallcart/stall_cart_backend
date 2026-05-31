# orders/urls.py
from django.urls import path
from . import views
from common.decorators import customer_only, seller_only, admin_only

app_name = 'orders'

urlpatterns = [
    # ==================== ✅ CUSTOMER URLS (Restricted to customers only) ====================
    
    # My Orders (list)
    path('my-orders/', 
         customer_only(views.my_orders), 
         name='my_orders'),
    
    # Order Detail (tracking timeline)
    path('order/<str:order_id>/', 
         customer_only(views.order_detail), 
         name='order_detail'),
    
    # Cancel Order
    path('order/<str:order_id>/cancel/', 
         customer_only(views.cancel_order), 
         name='cancel_order'),
    
    # Request Return for an item
    path('return/<int:order_item_id>/', 
         customer_only(views.request_return), 
         name='request_return'),
    
    # Return Request Detail
    path('return/<int:return_id>/', 
         customer_only(views.return_detail), 
         name='return_detail'),
    
    # Download Invoice
#     path('order/<str:order_id>/invoice/', 
#          customer_only(views.download_invoice), 
#          name='invoice'),
     path(
        'order/<str:order_id>/invoice/',
        views.download_invoice,
        name='invoice_download'
    ),
    path(
        'order/<str:order_id>/invoice/preview/',
        views.preview_invoice,
        name='invoice_preview'
    ),
    path(
        'order/<str:order_id>/invoice/debug/',
        views.debug_invoice,
        name='invoice_debug'
    ),
    path('order/<str:order_id>/reorder/', 
         customer_only(views.reorder_order), 
         name='reorder_order'),
    # ==================== ✅ SELLER URLS (Restricted to sellers only) ====================
    
    # Seller's Orders (items from their products)
    path('seller/orders/', 
         seller_only(views.seller_orders), 
         name='seller_orders'),
    
    # Seller Order Detail
    path('seller/order/<str:order_id>/', 
         seller_only(views.seller_order_detail), 
         name='seller_order_detail'),
    
    # Seller: Update Order Status
    path('seller/order/<str:order_id>/update-status/', 
         seller_only(views.seller_update_status), 
         name='seller_update_status'),
    
    # Seller: Add Tracking Number
    path('seller/order/<str:order_id>/add-tracking/', 
         seller_only(views.seller_add_tracking), 
         name='seller_add_tracking'),
    
    # ==================== ✅ ADMIN URLS (Restricted to superusers only) ====================
    
    # Admin: All Orders
    path('admin/orders/', 
         admin_only(views.admin_orders), 
         name='admin_orders'),
    
    # Admin: Order Detail
    path('admin/order/<str:order_id>/', 
         admin_only(views.admin_order_detail), 
         name='admin_order_detail'),
    
    # Admin: Update Any Order Status
    path('admin/order/<str:order_id>/update-status/', 
         admin_only(views.admin_update_status), 
         name='admin_update_status'),
    
    # ==================== ✅ WEBHOOKS & API (No auth required) ====================
    
    # Razorpay Payment Webhook
    path('razorpay-webhook/', 
         views.razorpay_webhook, 
         name='razorpay_webhook'),
    
    # Shiprocket Webhook
    path('shiprocket-webhook/', 
         views.shiprocket_webhook, 
         name='shiprocket_webhook'),
    
    # ==================== ✅ PUBLIC/UTILITY (No login required) ====================
    
    # Track Order (public, no login required)
    path('track/<str:order_id>/', 
         views.track_order_public, 
         name='track_order_public'),
    
    # Order Success Page (after payment)
#     path('success/<str:order_id>/', 
#          views.order_success, 
#          name='order_success'),
     path('success/<str:order_id>/', views.order_success, name='order_success'),
    path('failed/', 
         views.order_failed, 
         name='order_failed'),

     # Return management
    path('return/<int:return_id>/approve/', views.approve_return, name='approve_return'),
        
]