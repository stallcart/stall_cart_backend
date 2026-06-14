# items/models.py
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from common.models import BaseModel  # Your existing BaseModel
from decimal import Decimal
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator, FileExtensionValidator
from django.core.exceptions import ValidationError

def validate_video_size(value):
    limit = 20 * 1024 * 1024  # 20MB
    if value.size > limit:
        raise ValidationError('Video file size cannot exceed 20MB.')


class SellerProfile(BaseModel):
    """Extended profile for sellers"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='seller_profile',
        limit_choices_to={'role__in': ['seller', 'staff', 'admin']}  # Allow seller or staff/admin
    )
    shop_name = models.CharField(max_length=150, unique=True)
    shop_description = models.TextField(blank=True)
    gst_number = models.CharField(max_length=15, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True)
    address = models.JSONField(default=dict, blank=True)  # {address, city, state, postalCode}
    is_verified = models.BooleanField(default=False)
    pan_number = models.CharField(max_length=10, blank=True, null=True)
    pan_card_file = models.FileField(upload_to='seller_pan_cards/', blank=True, null=True)
    pan_verification_status = models.CharField(
        max_length=20, 
        choices=[('pending', 'Pending Verification'), ('verified', 'Verified'), ('rejected', 'Rejected')], 
        default='pending'
    )
    pan_rejection_reason = models.TextField(blank=True, null=True)
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=0.0)    

    # Bank account details for payouts/settlements
    bank_name = models.CharField(max_length=150, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    account_holder_name = models.CharField(max_length=150, blank=True)

    # RazorpayX Payout IDs
    razorpay_contact_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_fund_account_id = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        old_status = None
        old_pan_number = None
        old_pan_card_file = None
        old_is_verified = None
        
        status_changed = False
        pan_updated = False
        
        if not is_new:
            try:
                old_obj = type(self).objects.filter(pk=self.pk).values('pan_verification_status', 'pan_number', 'pan_card_file', 'is_verified').first()
                if old_obj:
                    old_status = old_obj.get('pan_verification_status')
                    old_pan_number = old_obj.get('pan_number')
                    old_pan_card_file = old_obj.get('pan_card_file')
                    old_is_verified = old_obj.get('is_verified')
                    
                    if old_status != self.pan_verification_status:
                        status_changed = True
                    
                    old_pan_card_name = old_pan_card_file if old_pan_card_file else ''
                    new_pan_card_name = self.pan_card_file.name if self.pan_card_file else ''
                    if old_pan_number != self.pan_number or old_pan_card_name != new_pan_card_name:
                        pan_updated = True
            except Exception:
                pass
        
        # If the PAN details are updated by the seller, reset status to pending and set is_verified to False
        if pan_updated:
            self.pan_verification_status = 'pending'
            self.is_verified = False
            self.pan_rejection_reason = None
            status_changed = True
            
        # Sync changes between is_verified and pan_verification_status
        if is_new:
            if self.is_verified:
                self.pan_verification_status = 'verified'
        else:
            if self.is_verified and not old_is_verified and self.pan_verification_status != 'verified':
                self.pan_verification_status = 'verified'
                status_changed = True
            elif not self.is_verified and old_is_verified and self.pan_verification_status == 'verified':
                self.pan_verification_status = 'pending'
                status_changed = True
        
        # For staff/admin users, they are auto-verified
        if self.user and self.user.role in ['staff', 'admin']:
            self.is_verified = True
            self.pan_verification_status = 'verified'
        
        # Ensure status consistency
        if self.pan_verification_status == 'verified':
            self.is_verified = True
            self.pan_rejection_reason = None
        elif self.pan_verification_status in ['pending', 'rejected']:
            self.is_verified = False
            
        # Save first
        super().save(*args, **kwargs)
        
        # Send emails on changes
        if pan_updated or (is_new and self.pan_number):
            # Send notification to admins
            try:
                from orders.models import SystemActivityLog
                SystemActivityLog.log(
                    event_type='seller_verification',
                    description=f"Seller {self.user.phone} ({self.shop_name}) submitted/updated PAN: {self.pan_number}.",
                    status='success'
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to log PAN update to SystemActivityLog: {e}")

            try:
                from common.email_service import send_dynamic_email
                from accounts.models import User as AuthUser
                admins = AuthUser.objects.filter(role__in=['admin', 'staff'], is_active=True)
                admin_emails = [admin.email for admin in admins if admin.email]
                if admin_emails:
                    send_dynamic_email('admin_notify_pan_verification', admin_emails, {
                        'seller_name': self.user.full_name or self.user.phone,
                        'shop_name': self.shop_name,
                        'pan_number': self.pan_number,
                        'dashboard_url': 'https://stallcart.in/items/admin/verify-sellers/'
                    })
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to send PAN update email to admins: {e}")
                
        elif status_changed and not is_new:
            # Log status change
            try:
                from orders.models import SystemActivityLog
                SystemActivityLog.log(
                    event_type='seller_verification',
                    description=f"Seller {self.user.phone} ({self.shop_name}) PAN verification status changed to '{self.pan_verification_status}'.",
                    status='success',
                    metadata={'rejection_reason': self.pan_rejection_reason} if self.pan_verification_status == 'rejected' else {}
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to log PAN status change to SystemActivityLog: {e}")

            # Send notification to seller and admin
            try:
                from common.email_service import send_dynamic_email
                recipient_list = []
                if self.user.email:
                    recipient_list.append(self.user.email)
                    
                if self.pan_verification_status == 'verified':
                    if recipient_list:
                        send_dynamic_email('seller_pan_verified', recipient_list, {
                            'seller_name': self.user.full_name or self.shop_name,
                            'shop_name': self.shop_name,
                            'pan_number': self.pan_number
                        })
                elif self.pan_verification_status == 'rejected':
                    if recipient_list:
                        send_dynamic_email('seller_pan_rejected', recipient_list, {
                            'seller_name': self.user.full_name or self.shop_name,
                            'shop_name': self.shop_name,
                            'rejection_reason': self.pan_rejection_reason or "Incomplete or incorrect documents.",
                            'profile_url': 'https://stallcart.in/accounts/profile/'
                        })
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to send PAN status update email to seller: {e}")

    def _update_rating_cache(self):
        """Update average rating from approved seller reviews"""
        stats = self.reviews.filter(is_approved=True).aggregate(
            avg=models.Avg('rating')
        )
        self.rating = stats['avg'] or 0.0
        self.save(update_fields=['rating'])

    def __str__(self):
        return f"{self.shop_name} ({self.user.phone})"
        
    class Meta:
        verbose_name = 'Seller Profile'
        verbose_name_plural = 'Seller Profiles'

class Category(BaseModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True,null=True)
    commision_percentage = models.FloatField(default=0)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    icon = models.ImageField(upload_to='category_icons/', null=True, blank=True, help_text="Category icon image (displayed on storefront/menus)")
    
    def save(self, *args, **kwargs):
        if not self.slug:
            max_len = self._meta.get_field('slug').max_length or 255
            base_slug = slugify(self.name)
            reserved_chars = 15
            if len(base_slug) > max_len - reserved_chars:
                base_slug = base_slug[:max_len - reserved_chars].rstrip('-')
            
            slug = base_slug
            if not slug:
                slug = 'category'
            
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
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
        # ('boys', '👦 Boys'),
        # ('girls', '👧 Girls'),
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
    slug = models.SlugField(max_length=255, unique=True, blank=True)
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
    material = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Cotton, Leather, Wood")
    warranty = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. 1 Year Manufacturer Warranty")
    country_of_origin = models.CharField(max_length=100, blank=True, null=True, default="India", help_text="e.g. India, USA")
    
    # SEO & Marketing
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(max_length=160, blank=True)
    
    # Status & Visibility
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    is_hot_deal = models.BooleanField(default=False)
    is_returnable = models.BooleanField(default=True, help_text="Designates whether the product is eligible for return/refund")
    discount_percent = models.PositiveIntegerField(default=0, help_text="0-100")
    
    # Stats (auto-calculated)
    views_count = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    review_count = models.PositiveIntegerField(default=0)
    
    def update_stock_from_variants(self, save=True):
        """
        Recalculates base stock from active variants using a direct DB query.
        Returns the updated stock.
        """
        active_variants = ProductVariant.objects.filter(product=self, is_active=True)
        if active_variants.exists():
            total_stock = active_variants.aggregate(
                total=models.Sum('stock')
            )['total'] or 0
            self.stock = total_stock
            if total_stock <= 0:
                self.status = 'out_of_stock'
            elif self.status == 'out_of_stock':
                self.status = 'published'
        else:
            if ProductVariant.objects.filter(product=self).exists():
                self.stock = 0
                self.status = 'out_of_stock'
        
        if save and self.pk:
            Product.objects.filter(pk=self.pk).update(stock=self.stock, status=self.status)
        return self.stock

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if not self.slug:
            max_len = self._meta.get_field('slug').max_length or 255
            base_slug = slugify(self.name)
            reserved_chars = 15
            if len(base_slug) > max_len - reserved_chars:
                base_slug = base_slug[:max_len - reserved_chars].rstrip('-')
            
            slug = base_slug
            if not slug:
                slug = 'product'
            
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        if not self.sku and self.seller:
            # Option A: Generate AFTER first save (two-phase save)
            if is_new:
                # First save to get pk
                super().save(*args, **kwargs)
                is_new = False  # Mark as saved
                # Since we already saved/inserted, subsequent save should not use force_insert
                kwargs.pop('force_insert', None)
                
            # Now generate unique SKU with pk
            base_sku = f"{self.seller.shop_name[:3].upper()}-{self.name[:5].upper().replace(' ', '')}-{self.pk}"
            sku = base_sku
            counter = 1
            # Ensure uniqueness with retry loop (like slug)
            while Product.objects.filter(sku=sku).exclude(pk=self.pk).exists():
                sku = f"{base_sku}-{counter}"
                counter += 1
            self.sku = sku

        # If this product has active variants, synchronize parent product stock and status before save
        if not is_new:
            self.update_stock_from_variants(save=False)

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
    
    # def savings(self):
    #     """Calculate savings amount: MRP - Final Price (never negative)"""
    #     mrp = self.mrp if self.mrp else self.price
    #     final = self.final_price if hasattr(self, 'final_price') and self.final_price else self.price
    #     return max(0, mrp - final)
    
    @property
    def is_in_stock(self):
        return self.stock > 0 and self.status == 'published'
    
    @property
    def is_low_stock(self):
        return self.stock <= self.low_stock_threshold and self.is_in_stock
    
    @property
    def profit_margin(self):
        if self.cost_price and self.cost_price > 0 and self.final_price > 0:
            return ((self.final_price - self.cost_price) / self.final_price) * 100
        return None
    
    # @property
    # def final_price(self):
    #     """Get discounted price if applicable"""
    #     if self.discount_percent and self.discount_percent > 0:
    #         return round(self.price * (1 - self.discount_percent / 100), 2)
    #     return self.price
    # @property
    # def savings_per_unit(self):
    #     """Return savings per unit (MRP - final price)"""
    #     return self.price - self.final_price if self.discount_percent > 0 else 0
    @property
    def savings_per_unit(self):
        """Return savings per unit: MRP - Final Price (never negative)"""
        # Use MRP if available, otherwise fall back to regular price
        base_price = self.mrp if self.mrp and self.mrp > 0 else self.price
        final_price = self.final_price
        return max(Decimal('0'), base_price - final_price)

    def calculate_savings(self, quantity):
        """Return total savings for given quantity"""
        return self.savings_per_unit * quantity
    @property
    def savings(self):
        """Alias for savings_per_unit for template compatibility"""
        return self.savings_per_unit
    @property
    def total_stock(self):
        """Returns sum of variant stock if variants exist, else base product stock"""
        if self.variants.filter(is_active=True).exists():
            return sum(v.stock for v in self.variants.filter(is_active=True))
        return self.stock
    @property
    def final_price(self):
        """Get discounted price if applicable (always returns Decimal)"""
        if self.discount_percent and self.discount_percent > 0:
            return round(self.price * (Decimal('1') - Decimal(self.discount_percent) / Decimal('100')), 2)
        return self.price
    @property
    def available_variants(self):
        """Returns only active variants with stock > 0"""
        return self.variants.filter(is_active=True, stock__gt=0).order_by('size_value')
    @property
    def commission_rate(self):
        """Returns category commission as Decimal (e.g., 0.15 for 15%)"""
        if self.category and self.category.commision_percentage:
            # Convert to string first to avoid float precision issues
            return Decimal(str(self.category.commision_percentage)) / Decimal('100')
        return Decimal('0')

    @property
    def admin_commission(self):
        """Platform commission based on final selling price (after discount)"""
        return self.final_price * self.commission_rate

    @property
    def seller_profit(self):
        """Seller's net profit per unit after commission & cost price"""
        if self.cost_price is None:
            return None
        return self.final_price - self.admin_commission - self.cost_price

    @property
    def seller_profit_margin(self):
        """Profit margin as a percentage"""
        profit = self.seller_profit
        if profit is not None and self.final_price > 0:
            return (profit / self.final_price) * Decimal('100')
        return None

    def calculate_profit_for_quantity(self, quantity):
        """Returns (admin_commission, seller_profit) for a given quantity"""
        if self.cost_price is None or quantity <= 0:
            return Decimal('0'), Decimal('0')
        total_commission = self.admin_commission * quantity
        total_profit = self.seller_profit * quantity
        return total_commission, total_profit
    
    def is_in_user_wishlist(self, user):
        """Check if this product (any variant) is in user's wishlist"""
        if not user or not user.is_authenticated:
            return False
        try:
            wishlist = user.wishlist
            return wishlist.items.filter(
                models.Q(product=self) | 
                models.Q(variant__product=self)
            ).exists()
        except Wishlist.DoesNotExist:
            return False
    def get_absolute_url(self):
        return reverse('items:product_detail', kwargs={'slug': self.slug})

    def _update_rating_cache(self):
        """Update review_count and rating_avg fields based on approved reviews"""
        stats = self.reviews.filter(is_approved=True).aggregate(
            avg=models.Avg('rating'),
            count=models.Count('id')
        )
        self.rating_avg = stats['avg'] or 0.00
        self.review_count = stats['count'] or 0
        self.save(update_fields=['rating_avg', 'review_count'])
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


class ProductVariantManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class ProductVariant(BaseModel):
    """
    Handles size/color/variant-specific stock & pricing.
    Works for clothing (S/M/L), jewelry (ring size 6/7), furniture (dimensions), etc.
    """
    objects = ProductVariantManager()
    all_objects = models.Manager()
    SIZE_TYPE_CHOICES = [
        ('standard', 'Standard / Free Size'),
        ('clothing', 'Clothing (XS-XXL, Numeric)'),
        ('jewelry', 'Jewelry (Ring Size, Chain Length, Carat)'),
        ('furniture', 'Furniture (Dimensions, Configuration)'),
        ('footwear', 'Footwear (US/UK/EU)'),
        ('custom', 'Custom / Other'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True)
    size_value = models.CharField(max_length=50, help_text="e.g., 'M', '6', '24x36 inches', '18k'")
    size_type = models.CharField(max_length=20, choices=SIZE_TYPE_CHOICES, default='standard')
    color = models.CharField(max_length=50, blank=True, help_text="Optional color/finish")
    price_override = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Overrides base product price")
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    attributes = models.JSONField(default=dict, blank=True, help_text="Custom specs: {'material': 'Gold', 'fit': 'Slim', 'assembly': 'Required'}")

    def __str__(self):
        return f"{self.product.name} - {self.size_value} {self.color}".strip()

    def get_effective_price(self):
        return self.price_override if self.price_override else self.product.price
    
    @property
    def effective_price(self):
        """Returns variant price or falls back to product price"""
        return self.get_effective_price()

    @property
    def final_price(self):
        """Get discounted price of variant if parent product has discount (always returns Decimal)"""
        effective = self.effective_price
        if self.product.discount_percent and self.product.discount_percent > 0:
            return round(effective * (Decimal('1') - Decimal(self.product.discount_percent) / Decimal('100')), 2)
        return effective

    @property
    def savings_per_unit(self):
        """Return savings per unit: original/mrp base price - final price (never negative)"""
        base_price = self.product.mrp if (self.product.mrp and self.product.mrp > self.effective_price) else self.effective_price
        return max(Decimal('0'), base_price - self.final_price)

    @property
    def savings(self):
        """Alias for savings_per_unit for template compatibility"""
        return self.savings_per_unit

    @property
    def commission_rate(self):
        """Inherits commission rate from parent product's category"""
        return self.product.commission_rate

    @property
    def admin_commission(self):
        return self.final_price * self.commission_rate

    @property
    def seller_profit(self):
        """Variant profit uses product's cost_price (unless you add variant-specific cost later)"""
        if self.product.cost_price is None:
            return None
        return self.final_price - self.admin_commission - self.product.cost_price

    @property
    def seller_profit_margin(self):
        profit = self.seller_profit
        if profit is not None and self.final_price > 0:
            return (profit / self.final_price) * Decimal('100')
        return None

    def calculate_profit_for_quantity(self, quantity):
        if self.product.cost_price is None or quantity <= 0:
            return Decimal('0'), Decimal('0')
        total_commission = self.admin_commission * quantity
        total_profit = self.seller_profit * quantity
        return total_commission, total_profit
    @property
    def is_in_stock(self):
        return self.stock > 0 and self.is_active
    def save(self, *args, **kwargs):
        if self.attributes is None:
            self.attributes = {}
        super().save(*args, **kwargs)
        self.product.update_stock_from_variants()

    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)
        product.update_stock_from_variants()
    class Meta:
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        constraints = [
            models.UniqueConstraint(fields=['product', 'size_value', 'color'], name='unique_variant_per_product')
        ]
        ordering = ['size_value']       


class Wishlist(BaseModel):
    """
    User's wishlist container.
    One user can have only one active wishlist (simplifies UI logic).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist'
    )
    name = models.CharField(
        max_length=100,
        default='My Wishlist',
        help_text="Custom name for this wishlist (e.g., 'Wedding Gifts')"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="If True, others can view this wishlist via link"
    )
    # Future: share_token = models.UUIDField(unique=True, blank=True, null=True)

    def __str__(self):
        return f"{self.user.phone}'s {self.name}"

    class Meta:
        verbose_name = 'Wishlist'
        verbose_name_plural = 'Wishlists'
        ordering = ['-updated_at']


class WishlistItem(BaseModel):
    """
    Individual item in a wishlist.
    Supports both products AND specific variants.
    """
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    # Optional: link to specific variant (size/color)
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,  # Keep wishlist item if variant deleted
        null=True,
        blank=True,
        related_name='wishlist_items'
    )
    # Optional: user note (e.g., "For mom's birthday")
    note = models.TextField(blank=True, max_length=200)
    # Optional: priority (1=high, 3=low)
    priority = models.PositiveSmallIntegerField(
        choices=[(1, '🔥 High'), (2, '⭐ Medium'), (3, '📦 Low')],
        default=2
    )
    # Auto-track when added
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        # Prevent duplicate product+variant in same wishlist
        constraints = [
            models.UniqueConstraint(
                fields=['wishlist', 'product', 'variant'],
                name='unique_wishlist_item'
            )
        ]
        ordering = ['-priority', '-added_at']  # High priority + newest first

    def __str__(self):
        variant_str = f" ({self.variant.size_value})" if self.variant else ""
        return f"{self.product.name}{variant_str} in {self.wishlist.name}"

    @property
    def is_available(self):
        """Check if product/variant is still in stock & published"""
        if self.variant:
            return self.variant.is_in_stock
        return self.product.is_in_stock

    @property
    def current_price(self):
        """Get current price (handles variant override)"""
        if self.variant:
            return self.variant.effective_price
        return self.product.final_price        



class ProductReview(BaseModel):
    """User reviews and ratings for products"""
    
    RATING_CHOICES = [(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)]
    
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    
    # Rating & Content
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    title = models.CharField(max_length=200, blank=True, help_text="Optional review title")
    review = models.TextField(max_length=2000, help_text="Your detailed review")
    
    # Media (optional)
    images = models.ImageField(
        upload_to='reviews/',
        blank=True, null=True,
        help_text="Optional: Upload photos of the product"
    )
    video = models.FileField(
        upload_to='reviews/videos/',
        blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'avi', 'mkv', 'webm']), validate_video_size],
        help_text="Optional: Upload video of the product"
    )
    
    # Moderation
    is_verified_purchase = models.BooleanField(default=False, help_text="Auto-set if user bought this product")
    is_approved = models.BooleanField(default=True, help_text="Set to False for moderation queue")
    helpful_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Product Review'
        verbose_name_plural = 'Product Reviews'
        ordering = ['-created_at']
        unique_together = ['product', 'user']  # One review per user per product
        indexes = [
            models.Index(fields=['product', '-rating']),
            models.Index(fields=['product', '-created_at']),
            models.Index(fields=['is_approved', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.phone} rated {self.product.name} ⭐{self.rating}"
    
    def save(self, *args, **kwargs):
        # Auto-set verified purchase if user ordered this product
        if not self.is_verified_purchase and self.pk is None:
            from orders.models import OrderItem
            self.is_verified_purchase = OrderItem.objects.filter(
                product=self.product,
                order__user=self.user,
                order__status='delivered'
            ).exists()
        super().save(*args, **kwargs)
        self.product._update_rating_cache()

    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)
        product._update_rating_cache()
    
    @property
    def rating_display(self):
        """Return star string for templates: ★★★★☆"""
        return '★' * self.rating + '☆' * (5 - self.rating)


class SellerReview(BaseModel):
    """User reviews and ratings for sellers"""
    
    RATING_CHOICES = [(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)]
    
    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_reviews'
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    title = models.CharField(max_length=200, blank=True, help_text="Optional review title")
    review = models.TextField(max_length=2000, help_text="Your detailed review")
    
    images = models.ImageField(
        upload_to='reviews/sellers/',
        blank=True, null=True,
        help_text="Optional: Upload photos of the packaging/delivery"
    )
    video = models.FileField(
        upload_to='reviews/sellers/videos/',
        blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'avi', 'mkv', 'webm']), validate_video_size],
        help_text="Optional: Upload video of the packaging/delivery"
    )
    
    is_verified_purchase = models.BooleanField(default=False, help_text="Auto-set if user bought from this seller")
    is_approved = models.BooleanField(default=True, help_text="Set to False for moderation queue")
    helpful_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Seller Review'
        verbose_name_plural = 'Seller Reviews'
        ordering = ['-created_at']
        unique_together = ['seller', 'user']
        indexes = [
            models.Index(fields=['seller', '-rating']),
            models.Index(fields=['seller', '-created_at']),
            models.Index(fields=['is_approved', '-created_at']),
        ]
        
    def __str__(self):
        return f"{self.user.phone} rated {self.seller.shop_name} ⭐{self.rating}"
        
    def save(self, *args, **kwargs):
        if not self.is_verified_purchase and self.pk is None:
            from orders.models import OrderItem
            self.is_verified_purchase = OrderItem.objects.filter(
                seller=self.seller,
                order__user=self.user,
                order__status='delivered'
            ).exists()
        super().save(*args, **kwargs)
        self.seller._update_rating_cache()

    def delete(self, *args, **kwargs):
        seller = self.seller
        super().delete(*args, **kwargs)
        seller._update_rating_cache()

    @property
    def rating_display(self):
        """Return star string for templates: ★★★★☆"""
        return '★' * self.rating + '☆' * (5 - self.rating)        