# common/views.py
from django.contrib import messages
from django.shortcuts import redirect, resolve_url
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from pathlib import Path  # ← Required for firebase_sw view

from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.cache import never_cache
import json

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

# common/views.py  (FCM section — replace the existing API views)

import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.conf import settings
from fcm_django.models import FCMDevice
from common.notification_service import notify_login_welcome

logger = logging.getLogger(__name__)


@login_required
@require_POST
def register_fcm_token(request):
    """
    Register (or refresh) an FCM token for the current user.
    Fires a welcome notification immediately so the user
    sees proof that notifications work right after login.

    POST body (JSON):
        token       — FCM registration token (required)
        device_id   — stable client-generated ID (optional)
        device_name — human label e.g. "Chrome on Windows" (optional)
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    token = body.get('token', '').strip()
    if not token:
        return JsonResponse({'error': 'token is required'}, status=400)

    device_id   = body.get('device_id', '')
    device_name = body.get('device_name', 'Web Browser')

    # Upsert the FCMDevice record
    device, created = FCMDevice.objects.update_or_create(
        registration_id=token,
        type='web',
        defaults={
            'user':      request.user,
            'name':      device_name,
            'device_id': device_id,
            'active':    True,
        },
    )

    # If token belonged to another user (e.g. shared device), reassign
    if device.user_id != request.user.id:
        device.user = request.user
        device.save(update_fields=['user'])

    # Fire welcome / test notification immediately
    delivered = notify_login_welcome(request.user, token)

    return JsonResponse({
        'ok':        True,
        'created':   created,
        'device_id': device.id,
        'notified':  delivered,    # True = test notification was sent
    }, status=201 if created else 200)


@login_required
@require_POST
def unregister_fcm_token(request):
    """Remove an FCM token (called on logout or permission revoke)."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    token = body.get('token', '').strip()
    if not token:
        return JsonResponse({'error': 'token is required'}, status=400)

    deleted, _ = FCMDevice.objects.filter(
        registration_id=token,
        user=request.user,
        type='web',
    ).delete()

    return JsonResponse({'ok': True, 'deleted': deleted > 0})


# ── Service Worker (config injected server-side) ──────────────────────────────

from django.views.decorators.cache import never_cache


@never_cache
def firebase_sw(request):
    """Serve SW at root scope with Firebase config baked in."""
    config = getattr(settings, 'FIREBASE_FRONTEND_CONFIG', {}) or {}
    sw_path = Path(settings.BASE_DIR) / 'static/js/firebase-messaging-sw.js'

    try:
        sw_content = sw_path.read_text()
    except FileNotFoundError:
        return HttpResponse(
            '// Service Worker not found', 
            content_type='application/javascript', 
            status=404
        )

    # Inject config at VERY TOP of SW file
    injected = f"self.FIREBASE_CONFIG = {json.dumps(config)};\n\n" + sw_content
    
    return HttpResponse(
        injected,
        content_type='application/javascript',
        headers={'Service-Worker-Allowed': '/'}  # ✅ Critical for root scope
    )