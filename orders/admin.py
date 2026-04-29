from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem
from common.admin import BaseModelAdmin

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price', 'subtotal')
    
    def subtotal(self, obj):
        return f"₹{obj.quantity * obj.price:.2f}"
    subtotal.short_description = "Subtotal"

@admin.register(Order)
class OrderAdmin(BaseModelAdmin):
    list_display = ('id_short', 'user', 'total_amount', 'status', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status', 'created_at')
    search_fields = ('id', 'user__phone', 'user__full_name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'created_by', 'updated_by', 'address_display')
    inlines = [OrderItemInline]
    
    def id_short(self, obj):
        return str(obj.id)[:8].upper()
    id_short.short_description = "Order ID"
    
    def address_display(self, obj):
        addr = obj.address or {}
        return format_html(
            "<strong>{}</strong><br>{}<br>{}, {} - {}",
            addr.get('name', 'N/A'),
            addr.get('address', ''),
            addr.get('city', ''),
            addr.get('state', ''),
            addr.get('postalCode', '')
        )
    address_display.short_description = "Shipping Address"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Sellers see orders containing their products
        if not request.user.is_superuser and hasattr(request.user, 'seller_profile'):
            return qs.filter(items__product__seller=request.user.seller_profile).distinct()
        return qs