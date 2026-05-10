from .models import *

def add_to_wishlist(user, product, variant=None, note='', priority=2):
    wishlist, _ = Wishlist.objects.get_or_create(
        user=user,
        defaults={'name': 'My Wishlist'}
    )
    
    # Try to restore a soft-deleted item first
    item = wishlist.items.filter(product=product, variant=variant, is_deleted=True).first()
    if item:
        item.is_deleted = False
        item.note = note or item.note
        item.priority = priority
        item.save(update_fields=['is_deleted', 'note', 'priority'])
        return item, False  # not "newly created"

    item, created = WishlistItem.objects.get_or_create(
        wishlist=wishlist,
        product=product,
        variant=variant,
        is_deleted=False,
        defaults={'note': note, 'priority': priority}
    )
    
    if not created and (note or priority != item.priority):
        item.note = note or item.note
        item.priority = priority
        item.save(update_fields=['note', 'priority'])
    
    return item, created


def remove_from_wishlist(user, product_id, variant_id=None):
    try:
        wishlist = user.wishlist
        filters = {'wishlist': wishlist, 'product_id': product_id, 'is_deleted': False}
        if variant_id:
            filters['variant_id'] = variant_id
        # Soft delete instead of hard delete
        return wishlist.items.filter(**filters).update(is_deleted=True)
    except Exception:
        return 0