# shop/services.py
from django.db import transaction, IntegrityError
from django.db.models import F, Q
from .models import Cart, CartItem
from items.models import Product, ProductVariant
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class CartService:
    """
    Centralized cart logic - DATABASE ONLY (no session fallback).
    Fully variant-aware with stock validation and race-condition protection.
    """
    
    # ─────────────────────────────────────────────────────────────
    # CORE CART ACCESS
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def get_cart(request):
        """Get cart object for authenticated customer only"""
        if request.user.is_authenticated and request.user.role == 'customer':
            cart, _ = Cart.objects.get_or_create(user=request.user)
            return cart
        return None
    
    # ─────────────────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def _check_stock(product, quantity, variant=None):
        """
        Internal: Validate stock availability.
        Returns: (is_available: bool, error_message: str or None)
        """
        if variant:
            if variant.stock < quantity:
                variant_info = f"{variant.size_value}{f' / {variant.color}' if variant.color else ''}".strip()
                return False, f"Only {variant.stock} {'available' if not variant_info else variant_info + ' available'}"
        else:
            if product.stock < quantity:
                return False, f"Only {product.stock} available"
        return True, None
    
    @staticmethod
    def _get_unit_price(product):
        """Get the effective unit price (with discount applied)"""
        if product.discount_percent > 0 and product.discount_price:
            return product.discount_price
        return product.price
    
    @staticmethod
    def _calculate_savings(product, quantity):
        """Calculate total savings for a cart item"""
        if product.mrp and product.discount_percent > 0:
            original = product.mrp
            discounted = product.discount_price if product.discount_price else product.price
            return (original - discounted) * quantity
        return Decimal('0')
    
    # ─────────────────────────────────────────────────────────────
    # ADD TO CART
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def add_to_cart(request, product_id, quantity=1, variant_id=None):
        """
        Add product to cart (DB only, variant-aware).
        
        Args:
            request: Django request object
            product_id: Product primary key
            quantity: Quantity to add (default: 1)
            variant_id: Optional ProductVariant primary key
        
        Returns:
            tuple: (success: bool, message: str, cart_count: int)
        """
        # Auth check
        if not request.user.is_authenticated or request.user.role != 'customer':
            return False, "Please login to add items to cart", 0
        
        # Validate quantity
        if quantity < 1:
            return False, "Quantity must be at least 1", 0
        
        # Fetch product
        try:
            product = Product.objects.select_related('seller').get(
                id=product_id, 
                status='published',
                is_active=True
            )
        except Product.DoesNotExist:
            return False, "Product not found or unavailable", 0
        
        # Fetch variant if specified
        variant = None
        if variant_id:
            try:
                variant = ProductVariant.objects.get(
                    id=variant_id, 
                    product=product, 
                    is_active=True
                )
            except ProductVariant.DoesNotExist:
                return False, "Selected variant not available", 0
        
        # Stock validation BEFORE database operations
        is_available, error_msg = CartService._check_stock(product, quantity, variant)
        if not is_available:
            return False, error_msg, 0
        
        # Get or create cart
        cart, _ = Cart.objects.get_or_create(user=request.user)
        
        # ✅ CRITICAL: Wrap select_for_update in transaction.atomic()
        with transaction.atomic():
            # Lock the cart item row to prevent race conditions
            cart_item, created = CartItem.objects.select_for_update().get_or_create(
                cart=cart,
                product=product,
                variant=variant,  # None for non-variant products
                defaults={'quantity': quantity}
            )
            
            if not created:
                # Item exists - update quantity
                new_qty = cart_item.quantity + quantity
                
                # Re-validate stock for the NEW total quantity
                is_available, error_msg = CartService._check_stock(product, new_qty, variant)
                if not is_available:
                    return False, error_msg, cart.total_items
                
                cart_item.quantity = new_qty
                cart_item.save()
        
        return True, "Added to cart!", cart.total_items
    
    # ─────────────────────────────────────────────────────────────
    # UPDATE CART ITEM (Quantity Change or Remove)
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def update_cart_item(request, product_id, quantity, variant_id=None):
        """
        Update cart item quantity or remove item (DB only, variant-aware).
        
        Args:
            request: Django request object
            product_id: Product primary key
            quantity: New quantity (0 or negative = remove item)
            variant_id: Optional ProductVariant primary key
        
        Returns:
            tuple: (success: bool, message: str, cart_count: int)
        """
        # Auth check
        if not request.user.is_authenticated or request.user.role != 'customer':
            return False, "Login required", 0
        
        # Fetch cart
        try:
            cart = Cart.objects.select_related('user').get(user=request.user)
        except Cart.DoesNotExist:
            return False, "Cart not found", 0
        
        # Build filters for the specific cart item
        filters = {'cart': cart, 'product_id': product_id}
        if variant_id:
            filters['variant_id'] = variant_id
        else:
            # For non-variant items, variant must be NULL
            filters['variant__isnull'] = True
        
        # ✅ CRITICAL: Wrap select_for_update in transaction.atomic()
        with transaction.atomic():
            try:
                # Lock the row for update
                cart_item = CartItem.objects.select_for_update().get(**filters)
            except CartItem.DoesNotExist:
                return False, "Item not in cart", cart.total_items
            
            # Handle removal
            if quantity <= 0:
                cart_item.delete()
                return True, "Item removed", cart.total_items
            
            # Validate new quantity against stock
            product = cart_item.product
            variant = cart_item.variant
            
            is_available, error_msg = CartService._check_stock(product, quantity, variant)
            if not is_available:
                return False, error_msg, cart.total_items
            
            # Update quantity
            cart_item.quantity = quantity
            cart_item.save()
        
        return True, "Cart updated", cart.total_items
    
    # ─────────────────────────────────────────────────────────────
    # REMOVE FROM CART (Convenience Wrapper)
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def remove_from_cart(request, product_id, variant_id=None):
        """
        Remove item from cart (convenience wrapper).
        
        Returns:
            tuple: (success: bool, message: str, cart_count: int)
        """
        return CartService.update_cart_item(request, product_id, 0, variant_id)
    
    # ─────────────────────────────────────────────────────────────
    # GET CART ITEMS FOR TEMPLATE
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def get_cart_items(request):
        """
        Get cart items with full details for template rendering.
        
        Returns:
            list: List of dicts with product, variant, pricing, stock info.
        """
        if not request.user.is_authenticated or request.user.role != 'customer':
            return []
        
        # Fetch cart with related data (prevent N+1 queries)
        try:
            cart = Cart.objects.prefetch_related(
                'items__product__seller',
                'items__product__category',
                'items__product__product_image_product',
                'items__variant'
            ).get(user=request.user)
        except Cart.DoesNotExist:
            return []
        
        items = []
        for cart_item in cart.items.all():
            product = cart_item.product
            variant = cart_item.variant
            
            # Calculate pricing
            unit_price = CartService._get_unit_price(product)
            original_price = product.mrp or product.price
            savings = CartService._calculate_savings(product, cart_item.quantity)
            
            # Stock availability for this specific variant/product
            available_stock = variant.stock if variant else product.stock
            is_in_stock = available_stock >= cart_item.quantity
            
            # Build variant display string
            variant_display = None
            if variant:
                parts = []
                if variant.size_value:
                    parts.append(variant.size_value)
                if variant.color:
                    parts.append(variant.color)
                variant_display = ' / '.join(parts) if parts else None
            
            items.append({
                # Identifiers
                'id': cart_item.id,
                'product': product,
                'variant': variant,
                
                # Quantities
                'quantity': cart_item.quantity,
                'available_stock': available_stock,
                'is_in_stock': is_in_stock,
                
                # Pricing
                'unit_price': unit_price,
                'original_price': original_price,
                'subtotal': unit_price * cart_item.quantity,
                'savings': savings,
                
                # Display helpers
                'variant_display': variant_display,
            })
        
        return items
    
    # ─────────────────────────────────────────────────────────────
    # CLEAR ENTIRE CART
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def clear_cart(request):
        """
        Empty the entire cart.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        if not request.user.is_authenticated or request.user.role != 'customer':
            return False
        
        try:
            cart = Cart.objects.get(user=request.user)
            # Use delete() for efficiency (single query)
            cart.items.all().delete()
            return True
        except Cart.DoesNotExist:
            return False
    
    # ─────────────────────────────────────────────────────────────
    # GET CART SUMMARY FOR CHECKOUT
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def get_cart_summary(request):
        """
        Get cart totals for checkout page.
        
        Returns:
            dict: Summary with subtotal, savings, delivery, grand total.
        """
        items = CartService.get_cart_items(request)
        
        if not items:
            return {
                'subtotal': Decimal('0'),
                'total_savings': Decimal('0'),
                'delivery_charge': Decimal('0'),
                'grand_total': Decimal('0'),
                'item_count': 0,
                'free_delivery_eligible': False,
                'remaining_for_free': Decimal('500'),
            }
        
        # Calculate aggregates
        subtotal = sum(item['subtotal'] for item in items)
        total_savings = sum(item['savings'] for item in items)
        item_count = sum(item['quantity'] for item in items)
        
        # Free delivery threshold
        FREE_DELIVERY_THRESHOLD = Decimal('499')
        delivery_charge = Decimal('0') if subtotal >= FREE_DELIVERY_THRESHOLD else Decimal('40')
        grand_total = subtotal + delivery_charge
        
        return {
            'subtotal': subtotal,
            'total_savings': total_savings,
            'delivery_charge': delivery_charge,
            'grand_total': grand_total,
            'item_count': item_count,
            'free_delivery_eligible': subtotal >= FREE_DELIVERY_THRESHOLD,
            'remaining_for_free': max(Decimal('0'), FREE_DELIVERY_THRESHOLD - subtotal),
        }
    
    # ─────────────────────────────────────────────────────────────
    # MERGE GUEST CART ON LOGIN (Optional - if you add session support later)
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def merge_guest_cart(request, user):
        """
        Merge guest session cart into user's DB cart on login.
        Only used if you implement session-based guest carts.
        
        Returns:
            int: New total cart item count, or None if not applicable.
        """
        # Skip if not authenticated or not a customer
        if not user.is_authenticated or user.role != 'customer':
            return None
        
        # Skip if no session cart
        session_cart = request.session.get('cart', {})
        if not session_cart:
            return None
        
        # Get user's DB cart
        cart, _ = Cart.objects.get_or_create(user=user)
        
        merged_count = 0
        
        for key, qty in session_cart.items():
            # Parse key: "pid" or "pid_vid"
            parts = key.split('_')
            pid = int(parts[0])
            vid = int(parts[1]) if len(parts) > 1 else None
            
            try:
                # Fetch product
                product = Product.objects.get(
                    id=pid, 
                    status='published', 
                    is_active=True,
                    stock__gt=0
                )
                
                # Fetch variant if specified
                variant = None
                if vid:
                    variant = ProductVariant.objects.get(
                        id=vid,
                        product=product,
                        is_active=True
                    )
                
                # Stock check
                is_available, _ = CartService._check_stock(product, qty, variant)
                if not is_available:
                    continue  # Skip unavailable items
                
                # Add to DB cart (with transaction for safety)
                with transaction.atomic():
                    cart_item, created = CartItem.objects.select_for_update().get_or_create(
                        cart=cart,
                        product=product,
                        variant=variant,
                        defaults={'quantity': qty}
                    )
                    if not created:
                        new_qty = cart_item.quantity + qty
                        is_available, _ = CartService._check_stock(product, new_qty, variant)
                        if is_available:
                            cart_item.quantity = new_qty
                            cart_item.save()
                
                merged_count += qty
                
            except (Product.DoesNotExist, ProductVariant.DoesNotExist):
                continue  # Skip invalid items
        
        # Clear session cart after successful merge
        if merged_count > 0:
            request.session['cart'] = {}
            request.session.modified = True
        
        return cart.total_items if merged_count > 0 else None