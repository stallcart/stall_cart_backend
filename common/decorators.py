# common/decorators.py
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def is_customer(user):
    """Check if user is a customer"""
    return hasattr(user, 'role') and user.role == 'customer'

def is_seller(user):
    """Check if user is a verified seller"""
    return (hasattr(user, 'role') and user.role == 'seller' and 
            hasattr(user, 'seller_profile') and user.seller_profile.is_verified)

def is_admin(user):
    """Check if user is a superuser"""
    return user.is_superuser

def customer_only(view_func):
    """
    Decorator to restrict view to customers only.
    Redirects sellers/admins with error message.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not is_customer(request.user):
            messages.error(request, "🔐 This page is for customers only.")
            if request.user.is_seller:
                return redirect('items:admin_dashboard')
            elif request.user.is_superuser:
                return redirect('/admin/')
            return redirect('shop:home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def seller_only(view_func):
    """Restrict view to verified sellers only"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not is_seller(request.user):
            messages.error(request, "🔐 Seller access required.")
            if request.user.role == 'customer':
                return redirect('shop:home')
            elif request.user.is_superuser:
                return redirect('/admin/')
            return redirect('accounts:login')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_only(view_func):
    """Restrict view to superusers only"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            messages.error(request, "🔐 Admin access required.")
            return redirect('shop:home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def is_seller_or_admin(user):
    """Check if user is a verified seller OR superuser"""
    if user.is_superuser:
        return True
    return (hasattr(user, 'role') and user.role == 'seller' and 
            hasattr(user, 'seller_profile') and user.seller_profile.is_verified)

def seller_or_admin_only(view_func):
    """
    Decorator to restrict view to verified sellers or admins only.
    Redirects customers/guests with error message.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        if not is_seller_or_admin(request.user):
            messages.error(request, "🔐 This page is for sellers and admins only.")
            return redirect('shop:home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view