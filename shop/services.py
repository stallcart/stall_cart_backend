# shop/services.py
from django.db import transaction
from .models import Cart, CartItem
from items.models import Product,ProductVariant

# class CartService:
#     """Centralized cart logic for session + DB carts"""
    
#     @staticmethod
#     def get_cart(request):
#         """Get cart object (DB for users, session for guests)"""
#         if request.user.is_authenticated and request.user.role == 'customer':
#             cart, _ = Cart.objects.get_or_create(user=request.user)
#             return cart
#         return None  # Guest uses session
    
#     @staticmethod
#     def add_to_cart(request, product_id, quantity=1):
#         """Add product to cart (DB or session)"""
#         product = Product.objects.get(id=product_id, status='published', stock__gt=0)
        
#         if request.user.is_authenticated and request.user.role == 'customer':
#             # Database cart
#             cart, _ = Cart.objects.get_or_create(user=request.user)
#             cart_item, created = CartItem.objects.get_or_create(
#                 cart=cart,
#                 product=product,
#                 defaults={'quantity': quantity}
#             )
#             if not created:
#                 cart_item.quantity += quantity
#                 cart_item.save()
#             return cart.total_items
#         else:
#             # Session cart
#             cart = request.session.get('cart', {})
#             product_id_str = str(product_id)
#             cart[product_id_str] = cart.get(product_id_str, 0) + quantity
#             request.session['cart'] = cart
#             return sum(cart.values())
    
#     @staticmethod
#     def update_cart_item(request, product_id, quantity):
#         """Update quantity of a cart item"""
#         if request.user.is_authenticated and request.user.role == 'customer':
#             cart = Cart.objects.get(user=request.user)
#             cart_item = CartItem.objects.get(cart=cart, product_id=product_id)
#             if quantity <= 0:
#                 cart_item.delete()
#             else:
#                 cart_item.quantity = quantity
#                 cart_item.save()
#             return cart.total_items
#         else:
#             # Session cart
#             cart = request.session.get('cart', {})
#             product_id_str = str(product_id)
#             if quantity <= 0:
#                 cart.pop(product_id_str, None)
#             else:
#                 cart[product_id_str] = quantity
#             request.session['cart'] = cart
#             return sum(cart.values())
    
#     @staticmethod
#     def remove_from_cart(request, product_id):
#         """Remove item from cart"""
#         return CartService.update_cart_item(request, product_id, 0)
    
#     @staticmethod
#     def get_cart_items(request):
#         """Get cart items with product details for template"""
#         if request.user.is_authenticated and request.user.role == 'customer':
#             cart = getattr(request.user, 'cart', None)
#             if not cart:
#                 return []
#             items = []
#             for cart_item in cart.items.select_related('product__seller').all():
#                 items.append({
#                     'product': cart_item.product,
#                     'quantity': cart_item.quantity,
#                     'subtotal': cart_item.subtotal,
#                     'unit_price': cart_item.unit_price,
#                     'savings': cart_item.savings,
#                     'in_stock': cart_item.product.stock >= cart_item.quantity
#                 })
#             return items
#         else:
#             # Session cart - build list from session
#             cart = request.session.get('cart', {})
#             if not cart:
#                 return []
#             product_ids = list(cart.keys())
#             products = Product.objects.filter(
#                 id__in=product_ids,
#                 status='published',
#                 stock__gt=0
#             ).select_related('seller')
            
#             items = []
#             for p in products:
#                 qty = cart.get(str(p.id), 0)
#                 if qty > 0 and p.stock >= qty:
#                     unit_price = p.discount_price if p.discount_percent > 0 else p.price
#                     items.append({
#                         'product': p,
#                         'quantity': qty,
#                         'subtotal': unit_price * qty,
#                         'unit_price': unit_price,
#                         'savings': (p.mrp - unit_price) * qty if p.mrp else 0,
#                         'in_stock': True
#                     })
#             return items
    
#     @staticmethod
#     def merge_guest_cart(request, user):
#         """Merge guest session cart into user's DB cart on login"""
#         session_cart = request.session.get('cart', {})
#         if not session_cart or not user.is_authenticated:
#             return
        
#         cart, _ = Cart.objects.get_or_create(user=user)
        
#         for product_id_str, qty in session_cart.items():
#             try:
#                 product = Product.objects.get(
#                     id=int(product_id_str),
#                     status='published',
#                     stock__gt=0
#                 )
#                 cart_item, created = CartItem.objects.get_or_create(
#                     cart=cart,
#                     product=product,
#                     defaults={'quantity': qty}
#                 )
#                 if not created:
#                     cart_item.quantity += qty
#                     cart_item.save()
#             except Product.DoesNotExist:
#                 continue
        
#         # Clear session cart after merge
#         request.session['cart'] = {}
#         return cart.total_items

# shop/services.py


 
class CartService:
    """Centralized cart logic for session + DB carts"""
 
    @staticmethod
    def get_cart(request):
        """Get cart object (DB for customers, None for guests)"""
        if request.user.is_authenticated and request.user.role == 'customer':
            cart, _ = Cart.objects.get_or_create(user=request.user)
            return cart
        return None
 
    # ------------------------------------------------------------------ #
    #  ADD TO CART                                                         #
    # ------------------------------------------------------------------ #
    @staticmethod
    def add_to_cart(request, product_id, quantity=1, variant_id=None):
        """
        Add a product (with optional variant) to cart.
        - Authenticated customers  → DB cart  (CartItem)
        - Guests                   → session cart
        """
 
        # ── Stock validation ────────────────────────────────────────────
        if variant_id:
            try:
                variant = ProductVariant.objects.get(
                    id=variant_id,
                    product_id=product_id,
                    is_active=True,
                )
            except ProductVariant.DoesNotExist:
                raise ValueError('Selected variant not found or inactive.')
 
            if variant.stock < quantity:
                raise ValueError(f'Only {variant.stock} available for this variant.')
 
        else:
            try:
                product = Product.objects.get(id=product_id, status='published')
            except Product.DoesNotExist:
                raise ValueError('Product not found.')
 
            if product.stock < quantity:
                raise ValueError(f'Only {product.stock} available.')
 
        # ── DB cart (authenticated customers) ───────────────────────────
        if request.user.is_authenticated and request.user.role == 'customer':
            product = Product.objects.get(id=product_id)
            cart, _ = Cart.objects.get_or_create(user=request.user)
 
            # Use variant_id=None for non-variant products so each
            # product+variant combination is a separate CartItem row.
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                variant_id=variant_id,          # None when no variant
                defaults={'quantity': quantity},
            )
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
 
            return cart.total_items
 
        # ── Session cart (guests) ───────────────────────────────────────
        else:
            cart = request.session.get('cart', {})
            # Key format: "pid" or "pid_vid" so different variants are stored separately
            key = f"{product_id}_{variant_id}" if variant_id else str(product_id)
            cart[key] = cart.get(key, 0) + quantity
            request.session['cart'] = cart
            request.session.modified = True
            return sum(cart.values())
 
    # ------------------------------------------------------------------ #
    #  UPDATE CART ITEM                                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def update_cart_item(request, product_id, quantity, variant_id=None):
        if request.user.is_authenticated and request.user.role == 'customer':
            try:
                cart = Cart.objects.get(user=request.user)
                qs = CartItem.objects.filter(cart=cart, product_id=product_id)
                if variant_id:
                    qs = qs.filter(variant_id=variant_id)
                else:
                    qs = qs.filter(variant_id__isnull=True)
 
                cart_item = qs.first()
                if cart_item:
                    if quantity <= 0:
                        cart_item.delete()
                    else:
                        cart_item.quantity = quantity
                        cart_item.save()
            except Cart.DoesNotExist:
                pass
            return Cart.objects.get(user=request.user).total_items
 
        else:
            cart = request.session.get('cart', {})
            key = f"{product_id}_{variant_id}" if variant_id else str(product_id)
            if quantity <= 0:
                cart.pop(key, None)
            else:
                cart[key] = quantity
            request.session['cart'] = cart
            request.session.modified = True
            return sum(cart.values())
 
    # ------------------------------------------------------------------ #
    #  REMOVE FROM CART                                                    #
    # ------------------------------------------------------------------ #
    @staticmethod
    def remove_from_cart(request, product_id, variant_id=None):
        return CartService.update_cart_item(request, product_id, 0, variant_id)
 
    # ------------------------------------------------------------------ #
    #  GET CART ITEMS (for templates)                                      #
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_cart_items(request):
        if request.user.is_authenticated and request.user.role == 'customer':
            cart = getattr(request.user, 'cart', None)
            if not cart:
                return []
 
            items = []
            for cart_item in cart.items.select_related(
                'product__seller', 'variant'
            ).all():
                items.append({
                    'product':    cart_item.product,
                    'variant':    getattr(cart_item, 'variant', None),
                    'quantity':   cart_item.quantity,
                    'subtotal':   cart_item.subtotal,
                    'unit_price': cart_item.unit_price,
                    'savings':    cart_item.savings,
                    'in_stock':   cart_item.product.stock >= cart_item.quantity,
                })
            return items
 
        else:
            # Session cart — keys may be "pid" or "pid_vid"
            cart = request.session.get('cart', {})
            if not cart:
                return []
 
            # Collect all product IDs
            product_ids = set()
            for key in cart.keys():
                product_ids.add(int(key.split('_')[0]))
 
            products = {
                p.id: p
                for p in Product.objects.filter(
                    id__in=product_ids, status='published'
                ).select_related('seller')
            }
 
            items = []
            for key, qty in cart.items():
                if qty <= 0:
                    continue
                pid = int(key.split('_')[0])
                product = products.get(pid)
                if not product:
                    continue
                unit_price = (
                    product.discount_price
                    if product.discount_percent > 0
                    else product.price
                )
                items.append({
                    'product':    product,
                    'variant':    None,
                    'quantity':   qty,
                    'subtotal':   unit_price * qty,
                    'unit_price': unit_price,
                    'savings':    (product.mrp - unit_price) * qty if product.mrp else 0,
                    'in_stock':   True,
                })
            return items
 
    # ------------------------------------------------------------------ #
    #  MERGE GUEST CART ON LOGIN                                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def merge_guest_cart(request, user):
        session_cart = request.session.get('cart', {})
        if not session_cart or not user.is_authenticated:
            return
 
        cart, _ = Cart.objects.get_or_create(user=user)
 
        for key, qty in session_cart.items():
            parts = key.split('_')
            pid = int(parts[0])
            vid = int(parts[1]) if len(parts) > 1 else None
 
            try:
                product = Product.objects.get(
                    id=pid, status='published', stock__gt=0
                )
                cart_item, created = CartItem.objects.get_or_create(
                    cart=cart,
                    product=product,
                    variant_id=vid,
                    defaults={'quantity': qty},
                )
                if not created:
                    cart_item.quantity += qty
                    cart_item.save()
            except Product.DoesNotExist:
                continue
 
        request.session['cart'] = {}
        return cart.total_items