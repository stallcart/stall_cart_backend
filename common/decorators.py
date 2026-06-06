# common/decorators.py
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse
from functools import wraps

def is_customer(user):
    """Check if user is a customer"""
    return hasattr(user, 'role') and user.role == 'customer'

def is_seller(user):
    """Check if user is a verified seller or user is staff/admin"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff or getattr(user, 'role', '') in ['staff', 'admin']:
        # Auto-create SellerProfile if missing
        if not hasattr(user, 'seller_profile'):
            from items.models import SellerProfile
            try:
                SellerProfile.objects.create(
                    user=user,
                    shop_name=f"Staff_{user.phone}",
                    phone=user.phone,
                    is_verified=True,
                    created_by=user
                )
            except Exception:
                pass
        return True
    return (hasattr(user, 'role') and user.role == 'seller' and 
            hasattr(user, 'seller_profile') and user.seller_profile.is_verified)

def is_admin(user):
    """Check if user is a superuser or staff member"""
    return user.is_superuser or user.is_staff

def _is_json_request(request):
    return (
        request.headers.get('Accept') == 'application/json' or
        request.content_type == 'application/json' or
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
    )

def customer_only(view_func):
    """
    Decorator to restrict view to customers only.
    Redirects sellers/admins with error message.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if _is_json_request(request):
                return JsonResponse({'error': 'Authentication required.'}, status=401)
            return redirect('accounts:login')
        
        if not is_customer(request.user):
            if _is_json_request(request):
                return JsonResponse({'error': '🔐 Customer access required.'}, status=403)
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
            if _is_json_request(request):
                return JsonResponse({'error': 'Authentication required.'}, status=401)
            return redirect('accounts:login')
        
        if not is_seller(request.user):
            if _is_json_request(request):
                return JsonResponse({'error': '🔐 Seller access required.'}, status=403)
            messages.error(request, "🔐 Seller access required.")
            if request.user.role == 'customer':
                return redirect('shop:home')
            elif request.user.is_superuser:
                return redirect('/admin/')
            return redirect('accounts:login')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def admin_only(view_func):
    """Restrict view to superusers or staff members"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not (request.user.is_superuser or request.user.is_staff):
            if _is_json_request(request):
                return JsonResponse({'error': '🔐 Admin/Staff access required.'}, status=403)
            messages.error(request, "🔐 Admin/Staff access required.")
            return redirect('shop:home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def is_seller_or_admin(user):
    """Check if user is a verified seller OR superuser OR staff"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff or getattr(user, 'role', '') in ['staff', 'admin']:
        # Auto-create SellerProfile if missing
        if not hasattr(user, 'seller_profile'):
            from items.models import SellerProfile
            try:
                SellerProfile.objects.create(
                    user=user,
                    shop_name=f"Staff_{user.phone}",
                    phone=user.phone,
                    is_verified=True,
                    created_by=user
                )
            except Exception:
                pass
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
            if _is_json_request(request):
                return JsonResponse({'error': 'Authentication required.'}, status=401)
            return redirect('accounts:login')
        
        if not is_seller_or_admin(request.user):
            if _is_json_request(request):
                return JsonResponse({'error': '🔐 Seller or Admin access required.'}, status=403)
            messages.error(request, "🔐 This page is for sellers and admins only.")
            return redirect('shop:home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view