from django.contrib import admin
from django.utils.html import format_html
from decimal import Decimal
from .models import Order, OrderItem
from common.admin import BaseModelAdmin

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'variant_display', 'quantity', 'price', 'subtotal', 'total_display')
    
    def subtotal(self, obj):
        """Calculate subtotal with None-safe handling"""
        quantity = obj.quantity or 0
        price = obj.price if obj.price is not None else Decimal('0')
        return f"₹{quantity * price:.2f}"
    subtotal.short_description = "Subtotal"
    
    def total_display(self, obj):
        """Show the stored total field (also None-safe)"""
        total = obj.total if obj.total is not None else Decimal('0')
        return f"₹{total:.2f}"
    total_display.short_description = "Total (Stored)"
    
    def variant_display(self, obj):
        """Show variant info if exists"""
        if obj.variant:
            parts = []
            if obj.variant.size_value:
                parts.append(obj.variant.size_value)
            if obj.variant.color:
                parts.append(obj.variant.color)
            return ' • '.join(parts) if parts else '—'
        return '—'
    variant_display.short_description = "Variant"

@admin.register(Order)
class OrderAdmin(BaseModelAdmin):
    list_display = ('unique_order_id', 'user_display', 'total_amount', 'payment_method', 'payment_status', 'status', 'created_at')
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('unique_order_id', 'user__phone', 'user__full_name', 'user__email')
    readonly_fields = (
        'unique_order_id', 'created_at', 'updated_at', 'created_by', 'updated_by', 
        'address_display', 'razorpay_order_id', 'razorpay_payment_id'
    )
    inlines = [OrderItemInline]
    
    def user_display(self, obj):
        if obj.user:
            return f"{obj.user.full_name or obj.user.phone} ({obj.user.role})"
        return f"Guest: {obj.guest_email or obj.guest_phone or 'N/A'}"
    user_display.short_description = "Customer"
    
    def address_display(self, obj):
        addr = obj.shipping_address or {}
        if not addr:
            return "— No address —"
        return format_html(
            "<strong>{}</strong><br>{}<br>{}, {} - {}<br>📞 {}",
            addr.get('name', 'N/A'),
            addr.get('address_line1', '') + (f", {addr.get('address_line2')}" if addr.get('address_line2') else ''),
            addr.get('city', ''),
            addr.get('state', ''),
            addr.get('postal_code', ''),
            addr.get('phone', 'N/A')
        )
    address_display.short_description = "Shipping Address"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('user')
        # Sellers see only orders containing their products
        if not request.user.is_superuser and hasattr(request.user, 'seller_profile'):
            return qs.filter(items__product__seller=request.user.seller_profile).distinct()
        return qs