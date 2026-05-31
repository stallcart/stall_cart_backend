# shop/urls.py
from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.home, name='home'),
    # path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('cart/', views.cart_view, name='cart'),              # ✅ Cart page
    path('cart/add/', views.add_to_cart, name='add_to_cart'), # ✅ AJAX add
    path('cart/update/', views.update_cart, name='update_cart'), # ✅ AJAX update/remove
    path('checkout/', views.checkout, name='checkout'),       # ✅ Checkout page
    path('orders/create/', views.create_order, name='create_order'), # ✅ Place order
    path('shop/verify-payment/', views.verify_payment, name='verify_payment'),
    path('check-pincode/', views.check_pincode, name='check_pincode'),
]