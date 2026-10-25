# common/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply a number by another number"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def divide(value, arg):
    """Divide a number by another number"""
    try:
        return float(value) / float(arg) if float(arg) != 0 else 0
    except (ValueError, TypeError):
        return value

@register.filter
def add(value, arg):
    """Add two values (for dynamic dict key access)"""
    return f"{value}{arg}"

@register.filter
def split(value, arg):
    """Split a string by the given delimiter"""
    if not value:
        return []
    return value.split(arg)


@register.filter
def get_item(dictionary, key):
    """Safely get an item from a dictionary or map using various key representations."""
    if not dictionary or not hasattr(dictionary, 'get'):
        return None
    val = dictionary.get(key)
    if val is None:
        try:
            val = dictionary.get(int(key))
        except (ValueError, TypeError):
            pass
    if val is None and hasattr(key, 'id'):
        val = dictionary.get(key.id)
    return val


@register.filter
def is_in_wishlist(product, user):
    """Check if the product is in the user's wishlist"""
    if not user or not user.is_authenticated:
        return False
    try:
        return product.is_in_user_wishlist(user)
    except Exception:
        return False


@register.simple_tag
def modify_query(request, **kwargs):
    """Override or set parameters in URL query string, keeping other parameters intact."""
    updated = request.GET.copy()
    for k, v in kwargs.items():
        if v is not None:
            updated[k] = v
        else:
            updated.pop(k, None)
    return updated.urlencode()