from django.contrib import admin
from django.utils.html import format_html
from .models import DeliveryPartner, DeliveryTask
from common.admin import BaseModelAdmin

@admin.register(DeliveryPartner)
class DeliveryPartnerAdmin(BaseModelAdmin):
    list_display = ('full_name', 'phone', 'status', 'delivered_count', 'is_active', 'created_at')
    list_filter = ('status', 'is_active')
    search_fields = ('full_name', 'phone', 'aadhar_id')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Profile', {'fields': ('user', 'full_name', 'phone', 'aadhar_id')}),
        ('Address', {'fields': ('current_address',)}),
        ('Status', {'fields': ('status', 'delivered_count', 'is_active')}),
        ('Audit', {'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')}),
    )

@admin.register(DeliveryTask)
class DeliveryTaskAdmin(BaseModelAdmin):
    list_display = ('id_short', 'order_link', 'partner', 'status', 'delivery_otp', 'delivered_at')
    list_filter = ('status', 'partner__status')
    search_fields = ('id', 'order__id', 'partner__phone')
    readonly_fields = ('id', 'delivery_otp', 'created_at', 'updated_at', 'created_by', 'updated_by')
    
    def id_short(self, obj):
        return str(obj.id)[:8].upper()
    id_short.short_description = "Task ID"
    
    def order_link(self, obj):
        if obj.order:
            return format_html('<a href="/admin/orders/order/{}/change/">{}</a>', obj.order.id, str(obj.order.id)[:8].upper())
        return "N/A"
    order_link.short_description = "Order"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Delivery partners only see their own tasks
        if not request.user.is_superuser and hasattr(request.user, 'delivery_profile'):
            return qs.filter(partner=request.user.delivery_profile)
        return qs