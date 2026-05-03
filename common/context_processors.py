from .models import SiteSettings
from django.core.cache import cache
from items.models import Category
def site_settings(request):
    settings = SiteSettings.get_singleton()
    logo_url = settings.logo_primary.url if settings.logo_primary else ''
    
    # Build absolute URL for Open Graph
    og_logo = request.build_absolute_uri(logo_url) if logo_url and request else ''
    
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

def cart_count(request):
    """Add cart count to every template context"""
    count = 0
    if request.user.is_authenticated and request.user.role == 'customer':
        cart = request.session.get('cart', {})
        count = sum(cart.values())
    return {'cart_count': count}

def get_categories():
    categories = cache.get('main_categories')
    if not categories:
        categories = Category.objects.filter(
            is_active=True, parent__isnull=True
        ).prefetch_related('children').order_by('name')
        cache.set('main_categories', categories, 3600)  # Cache for 1 hour
    return categories