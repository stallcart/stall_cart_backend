from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
from items.models import *
from orders.models import Order, OrderItem
from common.models import SiteSettings
from django.conf import settings
from shop.models import *
from .services import CartService
from common.decorators import *
import logging
import razorpay
from decimal import Decimal
from django.db import transaction, models
from django.http import JsonResponse
from django.conf import settings
from items.models import Product, ProductVariant
from accounts.models import User
logger = logging.getLogger(__name__)

def home(request):
    """Main shop page - matches index.html"""
    # Only show published, in-stock products
    products = Product.objects.filter(
        status='published',  # ✅ Use status field
        stock__gt=0,
        is_active=True
    ).select_related('category', 'seller').prefetch_related('product_image_product')
    
    categories = Category.objects.filter(is_active=True)
    cart_count = 0
    # Cart count from session (only for customers)
    customer_count = User.objects.filter(is_active = True,role = 'customer').count()
    if request.user.is_authenticated and request.user.role == 'customer':
        try:
            cart = Cart.objects.get(user=request.user)
            cart_count = cart.total_items   # uses @property from model
        except Cart.DoesNotExist:
            cart_count = 0
    
    context = {
        'products': products,
        'categories': categories,
        'cart_count': cart_count,
        'user_role': request.user.role if request.user.is_authenticated else None,
        'show_category_nav': True,
        'customer_count':customer_count,
        'product_count':products.count() if products else 0
    }
    return render(request, 'shop/home.html', context)

def product_detail(request, slug):
    """Product detail page"""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    related = Product.objects.filter(
        category=product.category, 
        is_active=True, 
        stock__gt=0
    ).exclude(id=product.id)[:4]
    print(related)
    print('product', product)
    cart = request.session.get('cart', {})
    context = {
        'product': product,
        'related_products': related,
        'cart_quantity': cart.get(str(product.id), 0),
    }
    return render(request, 'shop/product_detail.html', context)

# @customer_only
# @require_POST
# def add_to_cart(request):
#     """AJAX: Add product to session cart"""
#     try:
#         if request.user.is_authenticated and request.user.role != 'customer':
#             return JsonResponse({'status': 'error', 'message': 'Only customers can add items to cart'}, status=403)
    
#         data = json.loads(request.body)
#         product_id = str(data.get('product_id'))
#         quantity = int(data.get('quantity', 1))
#         variant_id = data.get('variant_id')  # ✅ New optional field
#         if variant_id:
#             variant = get_object_or_404(ProductVariant, pk=variant_id, product=product, is_active=True)
#             if variant.stock < quantity:
#                 return JsonResponse({'status': 'error', 'message': f'Only {variant.stock} available'}, status=400)
#         else:
#             if product.stock < quantity:
#                 return JsonResponse({'status': 'error', 'message': f'Only {product.stock} available'}, status=400)
        
#         cart = request.session.get('cart', {})
#         cart[product_id] = cart.get(product_id, 0) + quantity
#         request.session['cart'] = cart
#         request.session.modified = True
        
#         return JsonResponse({
#             'status': 'success', 
#             'cart_count': sum(cart.values()),
#             'message': 'Added to cart!'
#         })
#     except Exception as e:
#         return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@customer_only
def cart_view(request):
    """Cart page - DB only, variant-aware"""
    cart_items = CartService.get_cart_items(request)
    summary = CartService.get_cart_summary(request)
    
    # Get user addresses for checkout
    user_addresses = []
    default_address = None
    if request.user.is_authenticated and request.user.role == 'customer':
        from accounts.models import Address
        user_addresses = Address.objects.filter(
            user=request.user, 
            is_active=True
        ).order_by('-is_default', '-created_at')
        default_address = user_addresses.filter(is_default=True).first()
        if not default_address and user_addresses:
            default_address = user_addresses[0]
    
    context = {
        'cart_items': cart_items,
        'cart_count': summary['item_count'],
        'subtotal': summary['subtotal'],
        'total_savings': summary['total_savings'],
        'delivery_charge': summary['delivery_charge'],
        'grand_total': summary['grand_total'],
        'free_delivery_eligible': summary['free_delivery_eligible'],
        'remaining_for_free_delivery': summary['remaining_for_free'],
        'default_address': default_address,
        'user_addresses': user_addresses,
    }
    return render(request, 'shop/cart.html', context)

@customer_only
@require_POST
def add_to_cart(request):
    """AJAX: Add product to cart (DB only, with variant support)"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        variant_id = data.get('variant_id')  # Optional
        
        if not product_id or quantity < 1:
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
        
        success, message, cart_count = CartService.add_to_cart(
            request, product_id, quantity, variant_id
        )
        
        if success:
            return JsonResponse({
                'status': 'success',
                'message': message,
                'cart_count': cart_count
            })
        else:
            return JsonResponse({'status': 'error', 'message': message}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Add to cart error: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=500)

@customer_only
@require_POST
def update_cart(request):
    """AJAX: Update cart item quantity or remove (DB only, variant-aware)"""
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 0))
        variant_id = data.get('variant_id')  # Optional - crucial for variants
        action = data.get('action', 'update')
        
        if not product_id:
            return JsonResponse({'status': 'error', 'message': 'Product ID required'}, status=400)
        
        # Remove action overrides quantity
        if action == 'remove':
            quantity = 0
        
        success, message, cart_count = CartService.update_cart_item(
            request, product_id, quantity, variant_id
        )
        
        if success:
            return JsonResponse({
                'status': 'success',
                'message': message,
                'cart_count': cart_count
            })
        else:
            return JsonResponse({'status': 'error', 'message': message}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Update cart error: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': 'Server error'}, status=500)

@customer_only
def checkout(request):
    """Checkout page"""
    cart_items = CartService.get_cart_items(request)
    
    if not cart_items:
        messages.warning(request, "Your cart is empty.")
        return redirect('shop:cart')
    
    summary = CartService.get_cart_summary(request)
    
    # Get addresses
    from accounts.models import Address
    user_addresses = Address.objects.filter(
        user=request.user, is_active=True
    ).order_by('-is_default', '-created_at')
    
    selected_addr_id = request.GET.get('address')
    selected_address = None
    if selected_addr_id:
        selected_address = user_addresses.filter(id=selected_addr_id).first()
    if not selected_address:
        selected_address = user_addresses.filter(is_default=True).first()
    if not selected_address and user_addresses:
        selected_address = user_addresses.first()
    
    from django.conf import settings
    context = {
        'cart_items': cart_items,
        'user_addresses': user_addresses,
        'selected_address': selected_address,
        'subtotal': summary['subtotal'],
        'total_savings': summary['total_savings'],
        'delivery_charge': summary['delivery_charge'],
        'grand_total': summary['grand_total'],
        'remaining_for_free_delivery': summary['remaining_for_free'],
        'razorpay_key': getattr(settings, 'RAZORPAY_KEY_ID', ''),
    }
    return render(request, 'shop/checkout.html', context)



@customer_only
@require_POST
def create_order(request):
    """Create order from cart with comprehensive stock validation"""
   
    
    try:
        # ── Parse Request ──────────────────────────────────
        data = json.loads(request.body)
        address = data.get('address', {})
        payment_method = data.get('payment_method', 'cod').lower()
        
        # ── Get Cart ───────────────────────────────────────
        try:
            cart = Cart.objects.select_related('user').get(user=request.user)
        except Cart.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Cart not found'
            }, status=400)
        
        if not cart.items.exists():
            return JsonResponse({
                'status': 'error',
                'message': 'Cart is empty'
            }, status=400)
        
        # Prefetch related data for stock checks
        cart_items = cart.items.select_related(
            'product',
            'product__seller',
            'product__category',
            'variant'
        ).all()
        
        # ── ✅ STOCK VALIDATION (CRITICAL) ─────────────────
        unavailable_items = []
        
        for item in cart_items:
            product = item.product
            variant = item.variant
            
            # Check if product is published and active
            if product.status != 'published' or not product.is_active:
                unavailable_items.append({
                    'name': product.name,
                    'variant': f"{variant.size_value} / {variant.color}".strip(" / ") if variant else None,
                    'reason': 'Product is no longer available',
                    'requested': item.quantity,
                    'available': 0
                })
                continue
            
            # Determine available stock (variant or product level)
            available_stock = variant.stock if variant else product.stock
            
            # Check stock availability
            if available_stock < item.quantity:
                unavailable_items.append({
                    'name': product.name,
                    'variant': f"{variant.size_value} / {variant.color}".strip(" / ") if variant else None,
                    'reason': 'Insufficient stock',
                    'requested': item.quantity,
                    'available': available_stock
                })
        
        # If any items are unavailable, return detailed error
        if unavailable_items:
            # Build user-friendly message
            if len(unavailable_items) == 1:
                item = unavailable_items[0]
                msg = f"'{item['name']}'"
                if item.get('variant'):
                    msg += f" ({item['variant']})"
                msg += f" - Only {item['available']} available (you requested {item['requested']})"
            else:
                msg = f"{len(unavailable_items)} items are no longer available. Please review your cart."
            
            return JsonResponse({
                'status': 'error',
                'message': msg,
                'unavailable_items': unavailable_items  # For frontend highlighting
            }, status=400)
        
        # ── Calculate Totals ───────────────────────────────
        subtotal = sum(Decimal(str(item.subtotal)) for item in cart_items)
        delivery_charge = Decimal('0') if subtotal >= Decimal('499') else Decimal('40')
        total_amount = subtotal + delivery_charge
        
        # ── Create Razorpay Order (if online payment) ──────
        razorpay_order = None
        if payment_method != 'cod':
            try:
                client = razorpay.Client(auth=(
                    settings.RAZORPAY_KEY_ID,
                    settings.RAZORPAY_KEY_SECRET
                ))
                razorpay_order = client.order.create({
                    'amount': int(total_amount * 100),
                    'currency': 'INR',
                    'payment_capture': 1,
                    'notes': {
                        'user_id': str(request.user.id),
                        'email': request.user.email or ''
                    }
                })
            except Exception as e:
                logger.error(f"Razorpay order creation failed: {e}", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': 'Unable to initialize payment gateway'
                }, status=500)
        
        # ── ✅ CREATE ORDER (Atomic Transaction) ───────────
        with transaction.atomic():
            # 🔒 Re-check stock WITHIN transaction to prevent race conditions
            for item in cart_items:
                product = item.product
                variant = item.variant
                available_stock = variant.stock if variant else product.stock
                
                if available_stock < item.quantity:
                    raise ValueError(
                        f"Stock changed for {product.name}. Only {available_stock} available."
                    )
            
            # Create the order
            order = Order.objects.create(
                user=request.user,
                total_amount=total_amount,
                delivery_charge=delivery_charge,
                shipping_address=address,
                payment_method='razorpay' if payment_method != 'cod' else 'cod',
                payment_status='pending',
                status='pending',
                razorpay_order_id=razorpay_order['id'] if razorpay_order else None,
                notes=json.dumps({
                    'cart_items': [
                        {
                            'product': item.product.name,
                            'qty': item.quantity,
                            'price': float(item.price if hasattr(item, 'price') else item.unit_price),
                            'subtotal': float(item.subtotal)
                        }
                        for item in cart_items
                    ],
                    'subtotal': float(subtotal),
                    'delivery_charge': float(delivery_charge),
                    'total_amount': float(total_amount)
                })
            )
            
            # Create order items
            for item in cart_items:
                item_price = item.price if hasattr(item, 'price') else item.unit_price
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    seller=item.product.seller,
                    quantity=item.quantity,
                    price=item_price,
                    total=item.subtotal,
                    variant=item.variant  # ✅ Save variant reference
                )
            
            # ✅ FOR COD: Reduce stock immediately
            if payment_method == 'cod':
                for item in cart_items:
                    product = item.product
                    variant = item.variant
                    
                    if variant:
                        # Update variant stock
                        variant.stock -= item.quantity
                        variant.save(update_fields=['stock'])
                        # Recalculate product stock from variants
                        product.stock = product.variants.filter(
                            is_active=True
                        ).aggregate(total=models.Sum('stock'))['total'] or 0
                        product.save(update_fields=['stock'])
                    else:
                        # Update product stock directly
                        product.stock -= item.quantity
                        product.save(update_fields=['stock'])
                
                # Clear cart after successful order
                cart.items.all().delete()
                
                # Update order status for COD
                order.payment_status = 'pending'
                order.status = 'confirmed'
                order.save(update_fields=['payment_status', 'status'])
        
        # ── Return Response ────────────────────────────────
        if payment_method != 'cod':
            # Online payment: return Razorpay config
            return JsonResponse({
                'status': 'success',
                'payment_method': 'razorpay',
                'order_id': order.unique_order_id,
                'razorpay_order_id': razorpay_order['id'],
                'key': settings.RAZORPAY_KEY_ID,
                'amount': int(total_amount * 100),
                'currency': 'INR',
                'name': getattr(settings, 'SITE_NAME', 'StallCart'),
                'description': f'Order #{order.unique_order_id}',
                'prefill': {
                    'name': getattr(request.user, 'full_name', '') or '',
                    'email': request.user.email or '',
                    'contact': getattr(request.user, 'phone', '') or ''
                },
                'theme': {'color': '#2874F0'}
            })
        
        # COD: Order confirmed
        return JsonResponse({
            'status': 'success',
            'payment_method': 'cod',
            'order_id': order.unique_order_id,
            'message': 'Order placed successfully.'
        })
        
    except ValueError as e:
        # Stock changed during transaction
        logger.warning(f"Stock validation failed during order creation: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
        
    except Exception as e:
        logger.error(f"Order creation failed: {e}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'Order creation failed. Please try again.'
        }, status=500)



# @customer_only
# @require_POST
# def create_order(request):
#     """
#     Create an order from the cart.
 
#     COD  → stock deducted immediately, cart cleared, order confirmed.
#     Online (Razorpay) → order row created with status=pending,
#                         stock NOT deducted yet (happens in verify_payment/webhook),
#                         returns Razorpay config for frontend modal.
#     """
#     try:
#         data = json.loads(request.body)
#     except json.JSONDecodeError:
#         return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
 
#     address = data.get('address', {})
#     payment_method = data.get('payment_method', 'cod').lower()
 
#     # ── Fetch cart ────────────────────────────────────────────────────────────
#     try:
#         cart = Cart.objects.select_related('user').get(user=request.user)
#     except Cart.DoesNotExist:
#         return JsonResponse({'status': 'error', 'message': 'Cart not found'}, status=400)
 
#     if not cart.items.exists():
#         return JsonResponse({'status': 'error', 'message': 'Cart is empty'}, status=400)
 
#     cart_items = cart.items.select_related(
#         'product', 'product__seller', 'product__category', 'variant'
#     ).all()
 
#     # ── Stock validation (pre-check) ─────────────────────────────────────────
#     unavailable = []
#     for item in cart_items:
#         product = item.product
#         variant = item.variant
 
#         if product.status != 'published' or not product.is_active:
#             unavailable.append({
#                 'name': product.name,
#                 'reason': 'Product is no longer available',
#                 'requested': item.quantity,
#                 'available': 0,
#             })
#             continue
 
#         available_stock = variant.stock if variant else product.stock
#         if available_stock < item.quantity:
#             unavailable.append({
#                 'name': product.name,
#                 'variant': f"{variant.size_value} / {variant.color}".strip(' /') if variant else None,
#                 'reason': 'Insufficient stock',
#                 'requested': item.quantity,
#                 'available': available_stock,
#             })
 
#     if unavailable:
#         if len(unavailable) == 1:
#             item_info = unavailable[0]
#             msg = f"'{item_info['name']}'"
#             if item_info.get('variant'):
#                 msg += f" ({item_info['variant']})"
#             msg += f" — Only {item_info['available']} available (you requested {item_info['requested']})"
#         else:
#             msg = f"{len(unavailable)} items are no longer available. Please review your cart."
#         return JsonResponse({'status': 'error', 'message': msg, 'unavailable_items': unavailable}, status=400)
 
#     # ── Totals ────────────────────────────────────────────────────────────────
#     subtotal = sum(Decimal(str(item.subtotal)) for item in cart_items)
#     delivery_charge = Decimal('0') if subtotal >= Decimal('499') else Decimal('40')
#     total_amount = subtotal + delivery_charge
 
#     # ── Razorpay order (for online payments) ─────────────────────────────────
#     razorpay_order = None
#     if payment_method != 'cod':
#         try:
#             client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
#             razorpay_order = client.order.create({
#                 'amount': int(total_amount * 100),
#                 'currency': 'INR',
#                 'payment_capture': 1,
#                 'notes': {
#                     'user_id': str(request.user.id),
#                     'email': request.user.email or '',
#                 }
#             })
#         except Exception as e:
#             logger.error(f"Razorpay order creation failed: {e}", exc_info=True)
#             return JsonResponse({'status': 'error', 'message': 'Unable to initialize payment gateway'}, status=500)
 
#     # ── Atomic order creation ─────────────────────────────────────────────────
#     try:
#         with transaction.atomic():
#             # Re-check stock inside transaction (race-condition guard)
#             for item in cart_items:
#                 available_stock = item.variant.stock if item.variant else item.product.stock
#                 if available_stock < item.quantity:
#                     raise ValueError(
#                         f"Stock changed for {item.product.name}. Only {available_stock} available."
#                     )
 
#             order = Order.objects.create(
#                 user=request.user,
#                 total_amount=total_amount,
#                 delivery_charge=delivery_charge,
#                 shipping_address=address,
#                 payment_method='razorpay' if payment_method != 'cod' else 'cod',
#                 payment_status='pending',
#                 status='pending',
#                 razorpay_order_id=razorpay_order['id'] if razorpay_order else None,
#                 notes=json.dumps({
#                     'subtotal': float(subtotal),
#                     'delivery_charge': float(delivery_charge),
#                     'total_amount': float(total_amount),
#                 })
#             )
 
#             # Create order items
#             for item in cart_items:
#                 item_price = getattr(item, 'price', None) or item.unit_price
#                 OrderItem.objects.create(
#                     order=order,
#                     product=item.product,
#                     seller=item.product.seller,
#                     variant=item.variant,
#                     quantity=item.quantity,
#                     price=item_price,
#                     total=item.subtotal,
#                 )
 
#             # COD: deduct stock + confirm immediately
#             if payment_method == 'cod':
#                 _deduct_stock_for_order_items(cart_items)
#                 cart.items.all().delete()
#                 order.payment_status = 'pending'
#                 order.status = 'confirmed'
#                 order.save(update_fields=['payment_status', 'status'])
#                 OrderStatusLog.objects.create(
#                     order=order, old_status='pending', new_status='confirmed',
#                     changed_by=request.user, remarks='COD order confirmed'
#                 )
 
#             # Online: DO NOT deduct stock yet. verify_payment / webhook handles it.
 
#     except ValueError as e:
#         logger.warning(f"Stock changed during order creation: {e}")
#         return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
#     except Exception as e:
#         logger.error(f"Order creation failed: {e}", exc_info=True)
#         return JsonResponse({'status': 'error', 'message': 'Order creation failed. Please try again.'}, status=500)
 
#     # ── Response ──────────────────────────────────────────────────────────────
#     if payment_method != 'cod':
#         return JsonResponse({
#             'status': 'success',
#             'payment_method': 'razorpay',
#             'order_id': order.unique_order_id,
#             'razorpay_order_id': razorpay_order['id'],
#             'key': settings.RAZORPAY_KEY_ID,
#             'amount': int(total_amount * 100),
#             'currency': 'INR',
#             'name': getattr(settings, 'SITE_NAME', 'StallCart'),
#             'description': f'Order #{order.unique_order_id}',
#             'prefill': {
#                 'name': getattr(request.user, 'full_name', '') or '',
#                 'email': request.user.email or '',
#                 'contact': getattr(request.user, 'phone', '') or '',
#             },
#             'theme': {'color': '#2874F0'},
#         })
 
#     return JsonResponse({
#         'status': 'success',
#         'payment_method': 'cod',
#         'order_id': order.unique_order_id,
#         'message': 'Order placed successfully.',
#     })
 
 
def _deduct_stock_for_order_items(cart_items):
    """Deduct stock from a list of CartItem objects (call inside atomic transaction)."""
    from django.db.models import Sum
    for item in cart_items:
        product = item.product
        variant = item.variant
        if variant:
            variant.stock = max(0, variant.stock - item.quantity)
            variant.save(update_fields=['stock'])
            product.stock = product.variants.filter(is_active=True).aggregate(
                total=Sum('stock')
            )['total'] or 0
            product.save(update_fields=['stock'])
        else:
            product.stock = max(0, product.stock - item.quantity)
            product.save(update_fields=['stock'])

# @login_required
# def order_success(request, order_id):
#     """Order confirmation page"""
#     try:
#         order = Order.objects.get(id=order_id, user=request.user)
#         return render(request, 'shop/order_success.html', {'order': order})
#     except Order.DoesNotExist:
#         return redirect('shop:home')


@login_required
def order_success(request, order_id):
    """Order confirmation"""
    try:
        order = Order.objects.get(unique_order_id=order_id, user=request.user)
        return render(request, 'shop/order_success.html', {'order': order})
    except Order.DoesNotExist:
        return redirect('shop:home')
    

# shop/views.py - Add this new view

@customer_only
@require_POST
def verify_payment(request):
    import json, hmac, hashlib
    from django.conf import settings
    try:
        data = json.loads(request.body)
        payment_id = data.get('razorpay_payment_id')
        order_id = data.get('razorpay_order_id')
        signature = data.get('razorpay_signature')
        internal_order_id = data.get('order_id')
        
        message = f"{order_id}|{payment_id}"
        expected_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if signature == expected_signature:
            from orders.models import Order
            order = Order.objects.get(unique_order_id=internal_order_id, user=request.user)
            order.payment_status = 'completed'
            order.razorpay_payment_id = payment_id
            order.save(update_fields=['payment_status', 'razorpay_payment_id'])
            return JsonResponse({'status': 'success', 'message': 'Payment verified'})
        return JsonResponse({'status': 'error', 'message': 'Signature mismatch'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Verification failed'}, status=500)
