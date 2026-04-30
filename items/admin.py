# items/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg
from .models import SellerProfile, Category, Product, ProductImage

# Inline for Product Images
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'alt_text', 'is_primary', 'display_order', 'image_preview')
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:80px; max-width:120px; border-radius:4px; border:1px solid #eee;">',
                obj.image.url
            )
        return 'No image'
    image_preview.short_description = 'Preview'

# Seller Profile Admin
@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'user', 'phone', 'is_verified', 'product_count', 'total_sales', 'created_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('shop_name', 'user__phone', 'user__full_name')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')
    
    fieldsets = (
        ('Shop Info', {'fields': ('user', 'shop_name', 'shop_description')}),
        ('Verification', {'fields': ('gst_number', 'is_verified', 'rating')}),
        ('Contact', {'fields': ('phone', 'address')}),
        ('Audit', {'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')}),
    )
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'
    
   
    def total_sales(self, obj):
        from orders.models import OrderItem

        total = OrderItem.objects.filter(
            product__seller=obj,
            order__status='Delivered'
        ).aggregate(total=Sum('price'))['total'] or 0

        # ✅ Proper formatting
        formatted = f"{total:,.2f}"

        return format_html('<strong>₹{}</strong>', formatted)
    total_sales.short_description = 'Total Sales'

# Category Admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'product_count', 'is_active')
    list_filter = ('parent', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    
    def product_count(self, obj):
        return obj.products.filter(status='published').count()
    product_count.short_description = 'Published Products'

# Product Admin - THE CORE: Seller vs Superuser Permissions
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name_preview', 'seller_shop', 'category', 'price_display', 
        'stock_status', 'status', 'is_featured', 'views_count', 'updated_at'
    )
    list_filter = (
        'status', 'is_featured', 'is_hot_deal', 'category', 'seller',
        ('stock', admin.SimpleListFilter),  # Custom stock filter
    )
    search_fields = ('name', 'description', 'sku', 'seller__shop_name')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]
    readonly_fields = (
        'created_at', 'updated_at', 'created_by', 'updated_by',
        'views_count', 'sold_count', 'rating_avg', 'review_count',
        'profit_margin_display', 'discount_price_display'
    )
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'short_description', 'description')
        }),
        ('Pricing', {
            'fields': ('price', 'mrp', 'cost_price', 'discount_percent'),
            'description': 'Discount auto-calculates final price'
        }),
        ('Inventory', {
            'fields': ('stock', 'low_stock_threshold', 'status'),
            'description': 'Set status to "Published" to make visible'
        }),
        ('Media', {
            'fields': ('primary_image',),
            'description': 'Upload multiple images via inline below'
        }),
        ('Product Details', {
            'fields': ('brand', 'sku', 'weight', 'dimensions'),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Relations', {
            'fields': ('seller', 'category', 'is_featured', 'is_hot_deal')
        }),
        ('Stats (Read-Only)', {
            'fields': (
                'views_count', 'sold_count', 'rating_avg', 'review_count',
                'profit_margin_display', 'discount_price_display',
                'created_at', 'updated_at', 'created_by', 'updated_by'
            ),
            'classes': ('collapse',)
        }),
    )
    
    # 🔐 PERMISSIONS: Sellers see ONLY their products
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs  # Superuser sees everything
        if hasattr(request.user, 'seller_profile'):
            return qs.filter(seller=request.user.seller_profile)  # Seller sees own
        return qs.none()  # Others see nothing
    
    def save_model(self, request, obj, form, change):
        # Auto-assign seller if creating new product
        if not obj.pk and hasattr(request.user, 'seller_profile'):
            obj.seller = request.user.seller_profile
        super().save_model(request, obj, form, change)
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj and hasattr(request.user, 'seller_profile'):
            return obj.seller.user == request.user  # Only edit own products
        return False
    
    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)  # Same as edit
    
    # Custom display methods
    def name_preview(self, obj):
        return format_html('<strong>{}</strong><br><small style="color:#666;">{}</small>', 
                          obj.name, obj.short_description[:50] + '...' if len(obj.short_description) > 50 else obj.short_description)
    name_preview.short_description = 'Product'
    
    def seller_shop(self, obj):
        return obj.seller.shop_name
    seller_shop.short_description = 'Seller'
    
    def price_display(self, obj):
        if obj.discount_percent > 0:
            return format_html(
                '<span style="text-decoration:line-through;color:#999;">₹{}</span> <strong style="color:#e91e63;">₹{}</strong> <span style="background:#ffebee;color:#c62828;padding:2px 6px;border-radius:3px;font-size:0.8em;">-{}%</span>',
                obj.price, obj.discount_price, obj.discount_percent
            )
        return format_html('<strong>₹{}</strong>', obj.price)
    price_display.short_description = 'Price'
    
    def stock_status(self, obj):
        if obj.stock == 0:
            return format_html('<span style="color:#c62828;font-weight:600;">OUT OF STOCK</span>')
        elif obj.stock <= obj.low_stock_threshold:
            return format_html('<span style="color:#f57f17;font-weight:600;">⚠️ Low: {}</span>', obj.stock)
        return format_html('<span style="color:#2e7d32;">{} in stock</span>', obj.stock)
    stock_status.short_description = 'Stock'
    
    def profit_margin_display(self, obj):
        margin = obj.profit_margin
        if margin is None:
            return 'N/A'
        color = '#2e7d32' if margin > 30 else '#f57f17' if margin > 15 else '#c62828'
        return format_html('<span style="color:{};font-weight:600;">{:.1f}%</span>', color, margin)
    profit_margin_display.short_description = 'Profit Margin'
    
    def discount_price_display(self, obj):
        if obj.discount_percent > 0:
            return format_html('<strong style="color:#e91e63;">₹{:.2f}</strong>', obj.discount_price)
        return 'No discount'
    discount_price_display.short_description = 'After Discount'

# Custom Stock Filter for Admin
class StockFilter(admin.SimpleListFilter):
    title = 'Stock Level'
    parameter_name = 'stock_level'
    
    def lookups(self, request, model_admin):
        return (
            ('in_stock', 'In Stock'),
            ('low', 'Low Stock'),
            ('out', 'Out of Stock'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'in_stock':
            return queryset.filter(stock__gt=5)
        elif self.value() == 'low':
            return queryset.filter(stock__lte=5, stock__gt=0)
        elif self.value() == 'out':
            return queryset.filter(stock=0)
        return queryset

# Register the custom filter
ProductAdmin.list_filter = list(ProductAdmin.list_filter)
# Replace the stock tuple with our custom filter class
ProductAdmin.list_filter = [
    f if not isinstance(f, tuple) or f[0] != 'stock' else StockFilter 
    for f in ProductAdmin.list_filter
]