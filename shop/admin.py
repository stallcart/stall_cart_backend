from django.contrib import admin
from django.utils.html import format_html
from .models import Cart, CartItem, HomepageBanner, AnnouncementBanner


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('unit_price', 'subtotal', 'savings', 'added_at', 'updated_at')
    autocomplete_fields = ('product',)

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'user',
        'total_items_display',
        'total_price_display',
        'updated_at',
        'is_deleted',
        'is_active'
    )
    list_editable = ('is_deleted','is_active')
    search_fields = ('user__phone', 'user__email')
    list_filter = ('created_at', 'updated_at')
    inlines = [CartItemInline]
    readonly_fields = ('total_items', 'total_price', 'created_at', 'updated_at')

    def total_items_display(self, obj):
        return obj.total_items
    total_items_display.short_description = "Total Items"

    def total_price_display(self, obj):
        return f"₹{obj.total_price:.2f}"
    total_price_display.short_description = "Total Price"


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'cart',
        'product',
        'quantity',
        'unit_price_display',
        'subtotal_display',
        'savings_display',
        'updated_at',
    )

    search_fields = (
        'product__name',
        'product__sku',
        'cart__user__phone'
    )

    list_filter = (
        'added_at',
        'updated_at',
        'product'
    )

    autocomplete_fields = ('cart', 'product')

    readonly_fields = (
        'unit_price',
        'subtotal',
        'savings',
        'added_at',
        'updated_at'
    )

    def unit_price_display(self, obj):
        return f"₹{obj.unit_price:.2f}"
    unit_price_display.short_description = "Unit Price"

    def subtotal_display(self, obj):
        return f"₹{obj.subtotal:.2f}"
    subtotal_display.short_description = "Subtotal"

    def savings_display(self, obj):
        return f"₹{obj.savings:.2f}"
    savings_display.short_description = "Savings"


@admin.register(HomepageBanner)
class HomepageBannerAdmin(admin.ModelAdmin):
    list_display = ('image_preview', 'title', 'banner_type', 'link_url', 'order', 'is_active', 'created_at')
    list_editable = ('order', 'is_active')
    list_filter = ('banner_type', 'is_active', 'created_at')
    search_fields = ('title', 'subtitle', 'link_url')
    ordering = ('order', '-created_at')
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px; max-width: 120px; border-radius: 4px;" />', obj.image.url)
        return "No Image"
    image_preview.short_description = 'Preview'


@admin.register(AnnouncementBanner)
class AnnouncementBannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'coupon_code', 'end_datetime', 'is_active', 'created_at')
    list_editable = ('is_active',)
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'subtitle', 'coupon_code')