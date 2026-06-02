from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from common.models import BaseModel
from decimal import Decimal
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
    def get_display_name(self):
        """Return full_name if available, otherwise phone"""
        return self.full_name.strip() if self.full_name else self.phone
    
    def __str__(self):
        return f"{self.phone} | {self.role}"

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


class Wallet(BaseModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.user.phone}'s Wallet - Bal: ₹{self.balance}"

    def deposit(self, amount, reference_id=None, description=""):
        from decimal import Decimal
        amount_dec = Decimal(str(amount))
        self.balance += amount_dec
        self.save()
        return WalletTransaction.objects.create(
            wallet=self,
            transaction_type='credit',
            amount=amount_dec,
            reference_id=reference_id,
            description=description
        )

    def withdraw(self, amount, reference_id=None, description=""):
        from decimal import Decimal
        amount_dec = Decimal(str(amount))
        if self.balance < amount_dec:
            raise ValueError("Insufficient wallet balance")
        self.balance -= amount_dec
        self.save()
        return WalletTransaction.objects.create(
            wallet=self,
            transaction_type='debit',
            amount=amount_dec,
            reference_id=reference_id,
            description=description
        )


class WalletTransaction(BaseModel):
    TRANSACTION_TYPES = [
        ('credit', 'Credit (Refund/Deposit)'),
        ('debit', 'Debit (Purchase)'),
    ]
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference_id = models.CharField(max_length=100, blank=True, null=True, help_text="Order or Return ID")
    description = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.wallet.user.phone} | {self.transaction_type} | {self.amount}"


class OTPRequest(BaseModel):
    phone = models.CharField(max_length=255, db_index=True)
    otp = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50)  # 'forgot_password', 'change_password'
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.phone} | {self.purpose} | {self.otp}"

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @classmethod
    def check_and_create_otp(cls, phone, purpose, expiry_minutes=10):
        from django.utils import timezone
        from datetime import timedelta
        import random
        from common.models import SiteSettings

        try:
            site_settings = SiteSettings.get_singleton()
            limit = site_settings.daily_otp_limit
        except Exception:
            limit = 5

        twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
        daily_count = cls.objects.filter(phone=phone, created_at__gte=twenty_four_hours_ago).count()
        if daily_count >= limit:
            return None, f"You have exceeded the limit of {limit} OTP requests per day. Please try again later."

        otp = f"{random.randint(100000, 999999)}"
        expires_at = timezone.now() + timedelta(minutes=expiry_minutes)

        otp_req = cls.objects.create(
            phone=phone,
            otp=otp,
            purpose=purpose,
            expires_at=expires_at
        )
        return otp_req, None