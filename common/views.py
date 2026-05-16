# common/views.py
from django.contrib import messages
from django.shortcuts import redirect, resolve_url
from django.urls import reverse


def custom_404(request, exception=None):
    """Show 404 as toast popup, redirect to home or referrer"""
    messages.warning(request, "🔍 Page not found. The link may be broken or the page was removed.")
    return redirect_to_safe_location(request)

def custom_403(request, exception=None):
    """Show 403 as toast popup"""
    messages.error(request, "⛔ Access denied. You don't have permission to view this page.")
    return redirect_to_safe_location(request)

def custom_400(request, exception=None):
    """Show 400 as toast popup"""
    messages.error(request, "⚠️ Invalid request. Please try again.")
    return redirect_to_safe_location(request)

def custom_500(request):
    """Show 500 as toast popup (no exception param)"""
    messages.error(request, "💥 Something went wrong on our end. We've been notified!")
    # For 500 errors, always go home to avoid cascading failures
    return redirect(reverse('shop:home'))

def redirect_to_safe_location(request):
    """Redirect to referrer or home, avoiding open redirect vulnerabilities"""
    referrer = request.META.get('HTTP_REFERER')
    
    # Only redirect to referrer if it's from our domain
    if referrer and request.get_host() in referrer:
        return redirect(referrer)
    
    # Fallback to home
    return redirect(reverse('shop:home'))