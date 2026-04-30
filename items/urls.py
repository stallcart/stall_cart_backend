# items/urls.py
from django.urls import path
from . import views

app_name = 'items'

urlpatterns = [
    # ── Unified Dashboard (seller sees own; superuser sees all) ────────────
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # ── Seller-specific dashboard (orders + overview) ─────────────────────
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),

    # ── Product CRUD ───────────────────────────────────────────────────────
    path('product/add/',                        views.product_create,        name='product_create'),
    path('product/<int:product_id>/edit/',      views.product_edit,          name='product_edit'),
    path('product/<int:product_id>/toggle/',    views.product_toggle_status, name='product_toggle_status'),
    path('product/<int:product_id>/delete/',    views.product_delete,        name='product_delete'),

    # ── JSON API (used by edit modal) ─────────────────────────────────────
    path('api/product/<int:product_id>/',       views.product_api_detail,    name='product_api_detail'),

    # ── Public pages ──────────────────────────────────────────────────────
    path('products/', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
]