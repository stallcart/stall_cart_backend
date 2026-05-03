# items/models.py
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from common.models import BaseModel  # Your existing BaseModel
from decimal import Decimal
class SellerProfile(BaseModel):
    """Extended profile for sellers"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='seller_profile',
        limit_choices_to={'role': 'seller'}  # Only users with role='seller'
    )
    shop_name = models.CharField(max_length=150, unique=True)
    shop_description = models.TextField(blank=True)
    gst_number = models.CharField(max_length=15, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.JSONField(default=dict, blank=True)  # {address, city, state, postalCode}
    is_verified = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0.0)    
    def __str__(self):
        return f"{self.shop_name} ({self.user.phone})"
        
    class Meta:
        verbose_name = 'Seller Profile'
        verbose_name_plural = 'Seller Profiles'

class Category(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True,null=True)
    commision_percentage = models.FloatField(default=0)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

class Product(BaseModel):
    """Main product model - sellers add these"""
    
    # ✅ NEW: Gender/Target Audience Choices
    GENDER_CHOICES = [
        ('men', '👨 Men'),
        ('women', '👩 Women'),
        ('boys', '👦 Boys'),
        ('girls', '👧 Girls'),
        ('unisex', '👫 Unisex'),
        ('kids', '🧒 Kids (2-12)'),
        ('teen', '🧑 Teen (13-19)'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('out_of_stock', 'Out of Stock'),
        ('discontinued', 'Discontinued'),
    ]
    
    seller = models.ForeignKey(
        SellerProfile, 
        on_delete=models.CASCADE, 
        related_name='products',
        limit_choices_to={'is_verified': True}
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='products'
    )
    
    # ✅ NEW: Gender field
    gender = models.CharField(
        max_length=20, 
        choices=GENDER_CHOICES, 
        blank=True, 
        null=True,
        help_text="Target audience (optional)"
    )
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    short_description = models.CharField(max_length=255, blank=True)
    
    price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="MRP for discount display")
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="For seller profit calculation")
    
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5, help_text="Alert when stock <= this value")
    
    images = models.ManyToManyField('ProductImage', blank=True, related_name='products')
    primary_image = models.ImageField(
        upload_to='products/%Y/%m/', 
        blank=True, null=True,
        help_text="Primary image for listing (auto-set from ProductImage if not provided)"
    )
    
    # Product attributes
    brand = models.CharField(max_length=100, blank=True)
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, help_text="in grams")
    dimensions = models.CharField(max_length=50, blank=True, help_text="L x W x H in cm")
    
    # SEO & Marketing
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(max_length=160, blank=True)
    
    # Status & Visibility
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    is_hot_deal = models.BooleanField(default=False)
    discount_percent = models.PositiveIntegerField(default=0, help_text="0-100")
    
    # Stats (auto-calculated)
    views_count = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    review_count = models.PositiveIntegerField(default=0)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        if not self.sku and self.seller:
            self.sku = f"{self.seller.shop_name[:3].upper()}-{self.name[:5].upper().replace(' ', '')}-{self.pk or 'NEW'}"

        super().save(*args, **kwargs)

        # Auto-set primary image from ProductImage if not provided
        if not self.primary_image and self.images.exists():
            primary = self.images.filter(is_primary=True).first()
            if primary:
                self.primary_image = primary.image
                super().save(update_fields=['primary_image'])
    
    def __str__(self):
        gender_label = f" [{self.get_gender_display()}]" if self.gender else ""
        return f"{self.name}{gender_label} (₹{self.price}) - {self.seller.shop_name}"
    
    @property
    def discount_price(self):
        if self.discount_percent > 0:
            discount = Decimal(self.discount_percent) / Decimal(100)
            return self.price * (Decimal(1) - discount)
        return self.price
    
    @property
    def savings(self):
        if self.mrp and self.price and self.mrp > self.price:
            return self.mrp - self.price
        return 0
    
    @property
    def is_in_stock(self):
        return self.stock > 0 and self.status == 'published'
    
    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold and self.is_in_stock
    
    @property
    def profit_margin(self):
        if self.cost_price and self.cost_price > 0:
            return ((self.price - self.cost_price) / self.price) * 100
        return None
    
    @property
    def final_price(self):
        """Return price after discount"""
        return self.discount_price if self.discount_percent > 0 else self.price

    @property
    def savings_per_unit(self):
        """Return savings per unit (MRP - final price)"""
        return self.price - self.final_price if self.discount_percent > 0 else 0

    def calculate_savings(self, quantity):
        """Return total savings for given quantity"""
        return self.savings_per_unit * quantity

    class Meta:
        verbose_name_plural = 'Products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['seller', 'status']),
            models.Index(fields=['category', 'status', 'price']),
            models.Index(fields=['gender', 'status']),  # ✅ Index for gender filtering
            models.Index(fields=['-created_at']),
        ]

class ProductImage(BaseModel):
    """Multiple images per product"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_image_product')
    image = models.ImageField(upload_to='products/%Y/%m/')
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)
    
    def save(self, *args, **kwargs):
        # Ensure only one primary image per product
        if self.is_primary:
            ProductImage.objects.filter(product=self.product).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Image for {self.product.name}"
    
    class Meta:
        ordering = ['display_order', '-is_primary']