# items/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from orders.models import OrderItem
from .models import (
    SellerProfile,
    Category,
    Product,
    ProductImage,
    ProductVariant,
    ProductReview
)

# ─────────────────────────────────────────────
# Custom Stock Filter
# ─────────────────────────────────────────────
class StockFilter(admin.SimpleListFilter):
    title = 'Stock Level'
    parameter_name = 'stock_level'

    def lookups(self, request, model_admin):
        return (
            ('in_stock', 'In Stock'),
            ('low', 'Low Stock'),
            ('out', 'Out Of Stock'),
        )

    def queryset(self, request, queryset):

        if self.value() == 'in_stock':
            return queryset.filter(stock__gt=5)

        if self.value() == 'low':
            return queryset.filter(stock__lte=5, stock__gt=0)

        if self.value() == 'out':
            return queryset.filter(stock=0)

        return queryset


# ─────────────────────────────────────────────
# Product Image Inline
# ─────────────────────────────────────────────
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

    fields = (
        'image',
        'alt_text',
        'is_primary',
        'display_order',
        'image_preview',
    )

    readonly_fields = ('image_preview',)

    def image_preview(self, obj):

        if obj.image:
            return format_html(
                '''
                <img src="{}"
                     style="
                        max-height:80px;
                        max-width:120px;
                        border-radius:6px;
                        border:1px solid #eee;
                        object-fit:cover;
                     ">
                ''',
                obj.image.url
            )

        return "No image"

    image_preview.short_description = "Preview"


# ─────────────────────────────────────────────
# Product Variant Inline
# ─────────────────────────────────────────────
class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1

    fields = (
        'size_type',
        'size_value',
        'color',
        'price_override',
        'stock',
        'is_active',
        'sku',
    )

    show_change_link = True
    classes = ('collapse',)


# ─────────────────────────────────────────────
# Seller Profile Admin
# ─────────────────────────────────────────────
@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):

    list_display = (
        'shop_name',
        'user',
        'phone',
        'is_verified',
        'is_active',
        'product_count',
        'total_sales',
        'created_at',
    )

    list_editable = (
        'is_verified',
        'is_active',
    )

    list_filter = (
        'is_verified',
        'is_active',
        'created_at',
    )

    search_fields = (
        'shop_name',
        'user__phone',
        'user__full_name',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
        'created_by',
        'updated_by',
    )

    fieldsets = (

        ('Shop Information', {
            'fields': (
                'user',
                'shop_name',
                'shop_description',
            )
        }),

        ('Verification', {
            'fields': (
                'gst_number',
                'is_verified',
                'is_active',
                'rating',
            )
        }),

        ('Contact', {
            'fields': (
                'phone',
                'address',
            )
        }),

        ('Audit', {
            'fields': (
                'created_at',
                'updated_at',
                'created_by',
                'updated_by',
            )
        }),
    )

    def product_count(self, obj):
        return obj.products.count()

    product_count.short_description = "Products"

    def total_sales(self, obj):
        

        total = OrderItem.objects.filter(
            product__seller=obj,
            order__status='Delivered'
        ).aggregate(total=Sum('price'))['total'] or 0

        # ✅ Format the number FIRST, then pass to format_html
        formatted = f"₹{total:,.2f}"
        return format_html('<strong>{}</strong>', formatted)

    total_sales.short_description = "Total Sales"


# ─────────────────────────────────────────────
# Category Admin
# ─────────────────────────────────────────────
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'slug',
        'parent',
        'commision_percentage',
        'product_count',
        'is_active',
    )

    list_filter = (
        'parent',
        'is_active',
    )

    search_fields = (
        'name',
        'description',
    )

    prepopulated_fields = {
        'slug': ('name',)
    }

    def product_count(self, obj):

        return obj.products.filter(
            status='published'
        ).count()

    product_count.short_description = "Published Products"


# ─────────────────────────────────────────────
# Product Admin
# ─────────────────────────────────────────────
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    list_display = (
        'name_preview',
        'seller_shop',
        'category',
        'gender',
        'price_display',
        'stock_status',
        'status',
        'is_featured',
        'is_hot_deal',
        'views_count',
        'updated_at',
    )

    list_filter = (
        'status',
        'gender',
        'is_featured',
        'is_hot_deal',
        'category',
        'seller',
        StockFilter,
    )

    search_fields = (
        'name',
        'description',
        'sku',
        'seller__shop_name',
    )

    prepopulated_fields = {
        'slug': ('name',)
    }

    inlines = [
        ProductImageInline,
        ProductVariantInline,
    ]

    readonly_fields = (
        'created_at',
        'updated_at',
        'created_by',
        'updated_by',
        'views_count',
        'sold_count',
        'rating_avg',
        'review_count',
        'profit_margin_display',
        'discount_price_display',
    )

    fieldsets = (

        ('Basic Information', {
            'fields': (
                'name',
                'slug',
                'gender',
                'short_description',
                'description',
            )
        }),

        ('Pricing', {
            'fields': (
                'price',
                'mrp',
                'cost_price',
                'discount_percent',
                'discount_price_display',
                'profit_margin_display',
            ),
            'description': 'Discount price auto-calculates.'
        }),

        ('Inventory', {
            'fields': (
                'stock',
                'low_stock_threshold',
                'status',
            )
        }),

        ('Media', {
            'fields': (
                'primary_image',
            )
        }),

        ('Product Details', {
            'fields': (
                'brand',
                'sku',
                'weight',
                'dimensions',
            ),
            'classes': ('collapse',)
        }),

        ('SEO', {
            'fields': (
                'meta_title',
                'meta_description',
            ),
            'classes': ('collapse',)
        }),

        ('Relations & Visibility', {
            'fields': (
                'seller',
                'category',
                'is_featured',
                'is_hot_deal',
            )
        }),

        ('Statistics', {
            'fields': (
                'views_count',
                'sold_count',
                'rating_avg',
                'review_count',
                'created_at',
                'updated_at',
                'created_by',
                'updated_by',
            ),
            'classes': ('collapse',)
        }),
    )

    # ─────────────────────────────────────────
    # Queryset Permissions
    # ─────────────────────────────────────────
    def get_queryset(self, request):

        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        if hasattr(request.user, 'seller_profile'):
            return qs.filter(
                seller=request.user.seller_profile
            )

        return qs.none()

    # ─────────────────────────────────────────
    # Save Product
    # ─────────────────────────────────────────
    def save_model(self, request, obj, form, change):

        if not obj.pk and hasattr(request.user, 'seller_profile'):
            obj.seller = request.user.seller_profile

        super().save_model(request, obj, form, change)

    # ─────────────────────────────────────────
    # Permissions
    # ─────────────────────────────────────────
    def has_change_permission(self, request, obj=None):

        if request.user.is_superuser:
            return True

        if obj and hasattr(request.user, 'seller_profile'):
            return obj.seller.user == request.user

        return False

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    # ─────────────────────────────────────────
    # Display Methods
    # ─────────────────────────────────────────
    def name_preview(self, obj):

        short_desc = obj.short_description or ""

        if len(short_desc) > 50:
            short_desc = short_desc[:50] + "..."

        return format_html(
            '''
            <strong>{}</strong>
            <br>
            <small style="color:#666;">{}</small>
            ''',
            obj.name,
            short_desc
        )

    name_preview.short_description = "Product"

    def seller_shop(self, obj):
        return obj.seller.shop_name

    seller_shop.short_description = "Seller"

    def price_display(self, obj):

        if obj.discount_percent > 0:

            return format_html(
                '''
                <span style="text-decoration:line-through;color:#888;">
                    ₹{}
                </span>
                <br>
                <strong style="color:#e91e63;">
                    ₹{}
                </strong>
                <br>
                <span style="
                    background:#ffebee;
                    color:#c62828;
                    padding:2px 6px;
                    border-radius:4px;
                    font-size:11px;
                    font-weight:700;
                ">
                    -{}%
                </span>
                ''',
                obj.price,
                obj.discount_price,
                obj.discount_percent
            )

        return format_html(
            '<strong>₹{}</strong>',
            obj.price
        )

    price_display.short_description = "Price"

    def stock_status(self, obj):

        total_stock = obj.total_stock

        if total_stock <= 0:
            return format_html(
                '<span style="color:#c62828;font-weight:700;">OUT OF STOCK</span>'
            )

        if total_stock <= obj.low_stock_threshold:
            return format_html(
                '''
                <span style="color:#f57f17;font-weight:700;">
                    ⚠ LOW STOCK ({})
                </span>
                ''',
                total_stock
            )

        return format_html(
            '''
            <span style="color:#2e7d32;font-weight:600;">
                {} in stock
            </span>
            ''',
            total_stock
        )

    stock_status.short_description = "Stock"

    def profit_margin_display(self, obj):

        margin = obj.profit_margin

        if margin is None:
            return "N/A"

        color = (
            '#2e7d32'
            if margin > 30 else
            '#f57f17'
            if margin > 15 else
            '#c62828'
        )

        return format_html(
            '''
            <span style="color:{};font-weight:700;">
                {:.1f}%
            </span>
            ''',
            color,
            margin
        )

    profit_margin_display.short_description = "Profit Margin"

    def discount_price_display(self, obj):

        if obj.discount_percent > 0:

            return format_html(
                '''
                <strong style="color:#e91e63;">
                    ₹{:.2f}
                </strong>
                ''',
                obj.discount_price
            )

        return "No discount"

    discount_price_display.short_description = "Discount Price"


# ─────────────────────────────────────────────
# Product Image Admin
# ─────────────────────────────────────────────
@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):

    list_display = (
        'product',
        'image_preview',
        'is_primary',
        'display_order',
        'created_at',
    )

    list_filter = (
        'is_primary',
        'created_at',
    )

    search_fields = (
        'product__name',
        'alt_text',
    )

    readonly_fields = (
        'image_preview',
    )

    def image_preview(self, obj):

        if obj.image:
            return format_html(
                '''
                <img src="{}"
                     style="
                        max-height:80px;
                        border-radius:6px;
                        border:1px solid #eee;
                     ">
                ''',
                obj.image.url
            )

        return "No image"

    image_preview.short_description = "Preview"


# ─────────────────────────────────────────────
# Product Variant Admin
# ─────────────────────────────────────────────
@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):

    list_display = (
        'product',
        'size_value',
        'size_type',
        'color',
        'effective_price_display',
        'stock',
        'is_active',
    )

    list_filter = (
        'size_type',
        'is_active',
    )

    search_fields = (
        'product__name',
        'sku',
        'size_value',
        'color',
    )

    readonly_fields = (
        'effective_price_display',
        'admin_commission_display',
        'seller_profit_display',
    )

    fieldsets = (

        ('Variant Information', {
            'fields': (
                'product',
                'sku',
                'size_type',
                'size_value',
                'color',
            )
        }),

        ('Pricing & Stock', {
            'fields': (
                'price_override',
                'effective_price_display',
                'stock',
                'is_active',
            )
        }),

        ('Custom Attributes', {
            'fields': (
                'attributes',
            ),
            'classes': ('collapse',)
        }),

        ('Profit Analytics', {
            'fields': (
                'admin_commission_display',
                'seller_profit_display',
            ),
            'classes': ('collapse',)
        }),
    )

    def effective_price_display(self, obj):

        return format_html(
            '<strong>₹{}</strong>',
            obj.effective_price
        )

    effective_price_display.short_description = "Effective Price"

    def admin_commission_display(self, obj):

        return format_html(
            '<span style="color:#1976d2;">₹{:.2f}</span>',
            obj.admin_commission
        )

    admin_commission_display.short_description = "Admin Commission"

    def seller_profit_display(self, obj):

        profit = obj.seller_profit

        if profit is None:
            return "N/A"

        return format_html(
            '<span style="color:#2e7d32;font-weight:700;">₹{:.2f}</span>',
            profit
        )

    seller_profit_display.short_description = "Seller Profit"


 
@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'title', 'is_verified_purchase', 'is_approved', 'created_at']
    list_filter = ['rating', 'is_verified_purchase', 'is_approved', 'created_at']
    search_fields = ['product__name', 'user__phone', 'review', 'title']
    readonly_fields = ['created_at', 'updated_at', 'helpful_count']
    
    actions = ['approve_reviews', 'reject_reviews']
    
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} review(s) approved.")
    approve_reviews.short_description = "Approve selected reviews"
    
    def reject_reviews(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(request, f"{queryset.count()} review(s) rejected.")
    reject_reviews.short_description = "Reject selected reviews"   