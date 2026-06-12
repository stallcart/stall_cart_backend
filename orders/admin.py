from django.contrib import admin
from django.utils.html import format_html
from decimal import Decimal
from .models import Order, OrderItem, ReturnRequest, OrderReturnImage, SellerSettlement, SystemActivityLog
from common.admin import BaseModelAdmin

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'variant_display', 'quantity', 'price', 'subtotal', 'total_display', 'commission_display', 'earnings_display')
    
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

    def commission_display(self, obj):
        """Show the commission amount and percentage"""
        pct = obj.product.category.commision_percentage if obj.product and obj.product.category else 0
        return f"₹{obj.commission_amount:.2f} ({pct}%)"
    commission_display.short_description = "Admin Commission"

    def earnings_display(self, obj):
        """Show net seller earnings"""
        return f"₹{obj.seller_earnings:.2f}"
    earnings_display.short_description = "Seller Earnings"


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
    actions = ['reconcile_refunds_action']
    
    def reconcile_refunds_action(self, request, queryset):
        """Run refund reconciliation for all under-refunded orders (calls management command)"""
        if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
            self.message_user(request, "🔐 Permission Denied: Only superadmins/admins can run refund reconciliation.", level='ERROR')
            return
            
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        try:
            call_command('reconcile_refunds', stdout=out)
            output = out.getvalue()
            lines = [line.strip() for line in output.split('\n') if line.strip() and not line.startswith('=')]
            summary = ", ".join(lines) if lines else "Done."
            self.message_user(request, f"🔄 Refund Reconciliation completed successfully: {summary}", level='SUCCESS')
        except Exception as e:
            self.message_user(request, f"❌ Error running reconciliation: {e}", level='ERROR')
    reconcile_refunds_action.short_description = "🔄 Run refund reconciliation (reconcile_refunds command)"

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


class OrderReturnImageInline(admin.TabularInline):
    model = OrderReturnImage
    extra = 0
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px; object-fit: contain;" />', obj.image.url)
        return "No Image"
    image_preview.short_description = "Preview"


@admin.register(ReturnRequest)
class ReturnRequestAdmin(BaseModelAdmin):
    list_display = ('id', 'order_item', 'user', 'quantity', 'reason', 'status', 'refund_amount', 'refund_status', 'created_at')
    list_filter = ('status', 'refund_status', 'refund_method', 'created_at')
    search_fields = ('id', 'user__phone', 'user__full_name', 'order_item__order__unique_order_id', 'order_item__product__name')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    inlines = [OrderReturnImageInline]
    
    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('user', 'order_item__product', 'order_item__order')
        # Sellers see only return requests for their own products
        if not request.user.is_superuser and hasattr(request.user, 'seller_profile'):
            return qs.filter(order_item__product__seller=request.user.seller_profile)
        return qs


@admin.register(SellerSettlement)
class SellerSettlementAdmin(BaseModelAdmin):
    list_display = ('settlement_id', 'seller', 'amount', 'commission_deducted', 'status', 'payment_reference', 'razorpay_payout_id', 'settled_at')
    list_filter = ('status', 'settled_at', 'seller')
    search_fields = ('settlement_id', 'payment_reference', 'razorpay_payout_id', 'seller__shop_name', 'seller__user__phone')
    readonly_fields = ('settlement_id', 'amount', 'commission_deducted', 'razorpay_payout_id', 'created_at', 'updated_at')
    filter_horizontal = ('order_items',)
    actions = ['trigger_bulk_payouts']

    def trigger_bulk_payouts(self, request, queryset):
        """Trigger RazorpayX payouts for selected settlements in bulk."""
        from orders.razorpayx_service import initiate_payout
        success_count = 0
        fail_count = 0
        errors = []
        
        for settlement in queryset:
            if settlement.status != 'processed' or not settlement.razorpay_payout_id:
                success, msg = initiate_payout(settlement)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{settlement.settlement_id}: {msg}")
            else:
                fail_count += 1
                errors.append(f"{settlement.settlement_id}: Already processed.")
                
        if success_count > 0:
            self.message_user(request, f"Successfully initiated {success_count} RazorpayX payout(s).", level='SUCCESS')
        if fail_count > 0:
            self.message_user(request, f"Failed/Skipped {fail_count} payout(s). Details: {', '.join(errors)}", level='ERROR')
    trigger_bulk_payouts.short_description = "💸 Trigger RazorpayX payout for selected settlements"

    def save_model(self, request, obj, form, change):
        # If status changes to processed and no payout_id exists, trigger it
        if change and obj.status == 'processed' and not obj.razorpay_payout_id:
            from orders.razorpayx_service import initiate_payout
            success, msg = initiate_payout(obj)
            if not success:
                self.message_user(request, f"Error initiating RazorpayX payout: {msg}", level='ERROR')
            else:
                self.message_user(request, f"Payout initiated successfully: {msg}", level='SUCCESS')
        else:
            super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = admin.ModelAdmin.get_queryset(self, request).select_related('seller')
        if not request.user.is_superuser and hasattr(request.user, 'seller_profile'):
            return qs.filter(seller=request.user.seller_profile)
        return qs

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "order_items":
            # If editing an existing object, filter order items to that seller
            obj_id = request.resolver_match.kwargs.get('object_id')
            if obj_id:
                settlement = self.get_object(request, obj_id)
                if settlement:
                    kwargs["queryset"] = OrderItem.objects.filter(seller=settlement.seller)
            else:
                # If adding a new settlement, restrict choices to order items belonging to sellers
                pass
        return super().formfield_for_manytomany(db_field, request, **kwargs)


@admin.register(SystemActivityLog)
class SystemActivityLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'event_type', 'status', 'description', 'order', 'settlement', 'user', 'created_at')
    list_filter = ('event_type', 'status', 'created_at')
    search_fields = ('description', 'order__unique_order_id', 'settlement__settlement_id', 'user__phone', 'user__full_name')
    readonly_fields = ('event_type', 'order', 'settlement', 'user', 'status', 'description', 'metadata', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False  # Log entries are read-only and created programmatically

    def has_change_permission(self, request, obj=None):
        return False  # Log entries cannot be edited

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete logs