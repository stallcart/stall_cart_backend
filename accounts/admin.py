from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('phone', 'email', 'full_name', 'role', 'is_active', 'is_staff', 'is_verified', 'created_at')
    list_filter = ('role', 'is_active', 'is_staff', 'is_verified', 'created_at')  # ✅ Only existing fields
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