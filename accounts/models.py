from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from common.models import BaseModel
class UserManager(BaseUserManager):
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("The Phone field must be set")
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(phone, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('seller', 'Seller'),
        ('delivery_partner', 'Delivery Partner'),
        ('admin', 'Admin'),
    ]

    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    
    # ✅ ADD THESE MISSING FIELDS:
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_users'
    )  
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='updated_users'
    )  
    objects = UserManager()
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return f"{self.phone} | {self.role}"

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

 
    @property
    def is_seller(self):
        return hasattr(self, 'seller_profile')

    @property
    def is_verified_seller(self):
        return self.is_seller and self.seller_profile.is_verified

    @property
    def is_admin(self):
        return self.is_superuser or self.role == 'admin'
    

class Address(BaseModel):
    """Multiple addresses per user (customers)"""
    ADDRESS_TYPES = [
        ('shipping', '📦 Shipping Address'),
        ('billing', '💳 Billing Address'),
        ('both', '🔄 Both Shipping & Billing'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    
    # Address details
    name = models.CharField(max_length=100, help_text="Recipient name")
    phone = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')
    
    # Address type
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES, default='shipping')
    
    # Flags
    is_default = models.BooleanField(default=False, help_text="Set as default for checkout")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_default']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.city}, {self.state} ({'Default' if self.is_default else 'Secondary'})"
    
    def save(self, *args, **kwargs):
        # If this is set as default, unset others for this user
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class SellerShopAddress(BaseModel):
    """Shop address for sellers (separate from personal address)"""
    seller = models.OneToOneField(
        'items.SellerProfile',  # Link to existing SellerProfile
        on_delete=models.CASCADE,
        related_name='shop_address'
    )
    
    # Shop details
    shop_name = models.CharField(max_length=150, help_text="Registered shop name")
    shop_phone = models.CharField(max_length=15)
    shop_email = models.EmailField(blank=True)
    
    # Address
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')
    
    # Business details
    gst_number = models.CharField(max_length=15, blank=True)
    pickup_instructions = models.TextField(blank=True, help_text="Instructions for delivery pickup")
    
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        verbose_name_plural = 'Seller Shop Addresses'
    
    def __str__(self):
        return f"{self.shop_name} - {self.city}, {self.state}"    