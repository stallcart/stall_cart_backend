from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings

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