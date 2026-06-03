from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, Address, SellerShopAddress, Wallet, WalletTransaction, OTPRequest


# ===============================
# ✅ USER ADMIN
# ===============================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('phone', 'email', 'full_name', 'role', 'is_active', 'is_staff', 'is_verified', 'created_at')
    list_filter = ('role', 'is_active', 'is_staff', 'is_verified', 'created_at')
    search_fields = ('phone', 'email', 'full_name')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        (_('Personal Info'), {'fields': ('email', 'full_name', 'role', 'is_verified')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Audit'), {'fields': ('created_at', 'updated_at', 'created_by', 'updated_by')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'password1', 'password2', 'full_name', 'role'),
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


# ===============================
# ✅ ADDRESS ADMIN (CUSTOMER)
# ===============================
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'phone', 'city', 'state', 'address_type', 'is_default', 'is_active')
    list_filter = ('address_type', 'is_default', 'is_active', 'state', 'city')
    search_fields = ('user__phone', 'name', 'phone', 'city', 'state', 'postal_code')
    list_editable = ('is_default', 'is_active')
    ordering = ('-is_default', '-created_at')

    fieldsets = (
        ('User Info', {
            'fields': ('user',)
        }),
        ('Contact Details', {
            'fields': ('name', 'phone')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Settings', {
            'fields': ('address_type', 'is_default', 'is_active')
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    readonly_fields = ('created_at', 'updated_at')


# ===============================
# ✅ SELLER SHOP ADDRESS ADMIN
# ===============================
@admin.register(SellerShopAddress)
class SellerShopAddressAdmin(admin.ModelAdmin):
    list_display = ('shop_name', 'seller', 'city', 'state', 'shop_phone', 'is_verified')
    list_filter = ('is_verified', 'state', 'city')
    search_fields = ('shop_name', 'shop_phone', 'shop_email', 'gst_number', 'city', 'state')
    list_editable = ('is_verified',)
    ordering = ('-created_at',)

    fieldsets = (
        ('Seller Info', {
            'fields': ('seller',)
        }),
        ('Shop Details', {
            'fields': ('shop_name', 'shop_phone', 'shop_email')
        }),
        ('Address', {
            'fields': ('address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country')
        }),
        ('Business Info', {
            'fields': ('gst_number', 'pickup_instructions')
        }),
        ('Verification', {
            'fields': ('is_verified',)
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    readonly_fields = ('created_at', 'updated_at')


# ===============================
# ✅ WALLET ADMIN
# ===============================
class WalletTransactionInline(admin.TabularInline):
    model = WalletTransaction
    extra = 0
    readonly_fields = ('transaction_type', 'amount', 'reference_id', 'description', 'timestamp')
    can_delete = False


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'created_at', 'updated_at')
    search_fields = ('user__phone', 'user__full_name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [WalletTransactionInline]


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'transaction_type', 'amount', 'reference_id', 'description', 'timestamp')
    list_filter = ('transaction_type', 'timestamp')
    search_fields = ('wallet__user__phone', 'wallet__user__full_name', 'reference_id')
    readonly_fields = ('timestamp',)


# ===============================
# ✅ OTP REQUEST ADMIN
# ===============================
@admin.register(OTPRequest)
class OTPRequestAdmin(admin.ModelAdmin):
    list_display = ('phone', 'purpose', 'otp', 'is_verified', 'expires_at', 'created_at')
    list_filter = ('purpose', 'is_verified', 'expires_at', 'created_at')
    search_fields = ('phone', 'otp')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')