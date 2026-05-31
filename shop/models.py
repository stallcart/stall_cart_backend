# shop/models.py
from django.db import models
from django.conf import settings
from items.models import Product, ProductVariant
from common.models import BaseModel
class Cart(BaseModel):
    """
    Shopping cart for authenticated users.
    Guests use session-based cart until login.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
        null=True,  # Allow null for migration safety
        blank=True
    )

    
    class Meta:
        verbose_name_plural = 'Carts'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Cart for {self.user.phone if self.user else 'Guest'}"
    
    @property
    def total_items(self):
        """Total quantity of all items in cart"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def total_price(self):
        """Total price of all items (with discounts)"""
        return sum(item.subtotal for item in self.items.all())
    
    def get_cart_count(self):
        """For template context - returns total item count"""
        return self.total_items


class CartItem(BaseModel):
    """Individual item in a cart"""
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    variant = models.ForeignKey(          # ← ADD THIS
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cart_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['cart', 'product', 'variant']
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name}"
    
    @property
    # def unit_price(self):
    #     """Price per unit (with discount applied)"""
    #     return self.product.discount_price if self.product.discount_percent > 0 else self.product.price
    def unit_price(self):
        # Use variant price if available, else product price
        if self.variant and self.variant.price_override:
            return self.variant.price_override
        return self.product.discount_price if self.product.discount_percent > 0 else self.product.price

    
    @property
    def subtotal(self):
        """Total price for this line item"""
        return self.unit_price * self.quantity
    
    @property
    def savings(self):
        """Total savings for this line item vs MRP"""
        if self.product.mrp and self.product.mrp > self.unit_price:
            return (self.product.mrp - self.unit_price) * self.quantity
        return 0


class HomepageBanner(BaseModel):
    BANNER_TYPE_CHOICES = [
        ('main_slider', '✨ Top Main Slider/Hero Banner'),
        ('festive_sale', '🎉 Festive Sale Banner'),
        ('coming_soon', '⏰ Coming Soon Banner'),
    ]
    
    title = models.CharField(max_length=200, help_text="For internal tracking/admin use or overlay title")
    subtitle = models.CharField(max_length=300, blank=True, null=True, help_text="Subtitle or description text")
    image = models.ImageField(upload_to='banners/', help_text="Upload premium high-resolution banner image")
    mobile_image = models.ImageField(upload_to='banners/mobile/', blank=True, null=True, help_text="Optional mobile-optimized image (falls back to main image if blank)")
    link_url = models.CharField(max_length=500, blank=True, default='#', help_text="URL redirect link (e.g. /items/?category=sarees)")
    banner_type = models.CharField(max_length=30, choices=BANNER_TYPE_CHOICES, default='main_slider')
    is_active = models.BooleanField(default=True, help_text="Only show active banners on home page")
    order = models.PositiveIntegerField(default=0, help_text="Display priority (lower numbers shown first)")
    
    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = 'Homepage Banner'
        verbose_name_plural = 'Homepage Banners'
        
    def __str__(self):
        return f"[{self.get_banner_type_display()}] {self.title}"