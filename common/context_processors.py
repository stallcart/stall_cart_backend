from .models import SiteSettings
from django.core.cache import cache
from items.models import Category,SellerProfile
from shop.models import Cart 
from django.conf import settings
import json
def site_settings(request):
    settings = SiteSettings.get_singleton()
    logo_url = settings.logo_primary.url if settings.logo_primary else ''
    
    # Build absolute URL for Open Graph
    try:
        og_logo = request.build_absolute_uri(logo_url) if logo_url and request else ''
    except Exception:
        og_logo = logo_url  # Fallback to relative URL if get_host() raises DisallowedHost
    
    return {
        'site_settings': settings,
        'SITE_NAME': settings.site_name,
        'PRIMARY_COLOR': settings.primary_color,
        'SECONDARY_COLOR': settings.secondary_color,
        'CONTACT_PHONE': settings.contact_phone,
        'WHATSAPP_LINK': settings.whatsapp_link,
        'IS_MAINTENANCE': settings.is_maintenance_mode,
        'OG_LOGO_URL': og_logo,  # ✅ Absolute URL for social sharing
    }

# context_processors.py

def cart_count(request):
    """
    Add cart count to every template context.
    ONLY uses database Cart model - no session fallback.
    Guests will see cart_count = 0 until they log in.
    """
    cart_count = 0
    
    # Only authenticated customers get a database cart
    if hasattr(request, 'user') and request.user.is_authenticated and getattr(request.user, 'role', None) == 'customer':
        try:
            # Fetch cart with annotated total_items for efficiency
            cart = request.user.cart
            if cart:
                # Use the model property (cached via @property)
                cart_count = cart.total_items
        except Cart.DoesNotExist:
            # User has no cart yet - that's okay, count is 0
            cart_count = 0
        except AttributeError:
            # Safety fallback if cart relation isn't loaded
            cart_count = 0
    
    return {'cart_count': cart_count}

def get_categories():
    categories = cache.get('main_categories')
    if not categories:
        categories = Category.objects.filter(
            is_active=True, parent__isnull=True
        ).prefetch_related('children').order_by('name')
        cache.set('main_categories', categories, 3600)  # Cache for 1 hour
    return categories

def cart_and_wishlist(request):
    cart_count = 0
    wishlist_count = 0

    if hasattr(request, 'user') and request.user.is_authenticated and hasattr(request.user, 'role'):
        if request.user.role == 'customer':
            # Cart count
            cart = getattr(request.user, 'cart', None)
            if cart:
                cart_count = cart.total_items

            # Wishlist count
            try:
                wishlist_count = request.user.wishlist.items.filter(
                    is_deleted=False
                ).count()
            except Exception:
                wishlist_count = 0
    else:
        # Guest cart from session
        cart = request.session.get('cart', {})
        cart_count = sum(cart.values())
    admin_pending_count = 0
    admin_verified_count = 0
    
    if hasattr(request, 'user') and request.user.is_authenticated and (request.user.is_superuser or request.user.has_perm('items.verify_seller')):
        admin_pending_count = SellerProfile.objects.filter(
            is_verified=False, 
            is_active=True
        ).count()
        admin_verified_count = SellerProfile.objects.filter(
            is_verified=True, 
            is_active=True
        ).count()
    return {
        'cart_count': cart_count,
        'wishlist_count': wishlist_count,
        'admin_pending_sellers': admin_pending_count,
        'admin_verified_sellers': admin_verified_count,
        'show_admin_verify_link': hasattr(request, 'user') and request.user.is_authenticated and (
            request.user.is_superuser or request.user.has_perm('items.verify_seller')
        ),
    }


# common/context_processors.py

from django.utils.safestring import mark_safe

def firebase_config(request):
    config = getattr(settings, 'FIREBASE_FRONTEND_CONFIG', {}) or {}
    
    return {
        # ✅ For HTML data attributes (already escaped)
        'firebase_config': config,
        
        # ✅ For embedding in <script type="application/json"> - PRE-SERIALIZED
        'firebase_config_json': mark_safe(json.dumps(config)),
        
        # ✅ VAPID key for web push
        'FIREBASE_VAPID_PUBLIC_KEY': getattr(settings, 'FIREBASE_VAPID_PUBLIC_KEY', ''),
    }