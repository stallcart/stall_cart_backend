from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
from items.models import Product, Category
from orders.models import Order, OrderItem
from common.models import SiteSettings
from django.conf import settings
from shop.models import *
from .services import CartService
from common.decorators import *

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

@customer_only
@require_POST
def add_to_cart(request):
    """AJAX: Add product to session cart"""
    try:
        if request.user.is_authenticated and request.user.role != 'customer':
            return JsonResponse({'status': 'error', 'message': 'Only customers can add items to cart'}, status=403)
    
        data = json.loads(request.body)
        product_id = str(data.get('product_id'))
        quantity = int(data.get('quantity', 1))
        
        cart = request.session.get('cart', {})
        cart[product_id] = cart.get(product_id, 0) + quantity
        request.session['cart'] = cart
        request.session.modified = True
        
        return JsonResponse({
            'status': 'success', 
            'cart_count': sum(cart.values()),
            'message': 'Added to cart!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

# shop/views.py
def cart_view(request):
    """Cart page - works for both guests and authenticated users"""
    cart_items = CartService.get_cart_items(request)
    
    if not cart_items:
        return render(request, 'shop/cart.html', {
            'cart_items': [],
            'total': 0,
            'delivery_charge': 0,
            'total_savings': 0,
            'default_address': None,
            'user_addresses': [],
        })
    
    # Calculate totals
    total = sum(item['subtotal'] for item in cart_items)
    total_savings = sum(item['savings'] for item in cart_items)
    delivery_charge = 0 if total >= 499 else 40
    
    # Get addresses for authenticated customers
    default_address = None
    user_addresses = []
    if request.user.is_authenticated and request.user.role == 'customer':
        from accounts.models import Address
        user_addresses = Address.objects.filter(
            user=request.user, 
            is_active=True
        ).order_by('-is_default', '-created_at')
        default_address = user_addresses.filter(is_default=True).first()
        if not default_address and user_addresses:
            default_address = user_addresses[0]
    remaining_amount_for_free_delivery = 0        
    if total <500 :
        remaining_amount_for_free_delivery = 500 - total
    context = {
        'cart_items': cart_items,
        'total': total,
        'delivery_charge': delivery_charge,
        'total_savings': total_savings,
        'default_address': default_address,
        'user_addresses': user_addresses,
        'cart_count': sum(item['quantity'] for item in cart_items),
        'remaining_amount_for_free_delivery':remaining_amount_for_free_delivery 
    }
    
    return render(request, 'shop/cart.html', context)

@customer_only
@require_POST
def add_to_cart(request):
    """AJAX: Add product to cart"""
    import json
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 1))
        
        if not product_id or quantity < 1:
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
        
        cart_count = CartService.add_to_cart(request, product_id, quantity)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Added to cart!',
            'cart_count': cart_count
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@customer_only
@require_POST
def update_cart(request):
    """AJAX: Update cart item quantity or remove"""
    import json
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = int(data.get('quantity', 0))
        action = data.get('action', 'update')
        
        if not product_id:
            return JsonResponse({'status': 'error', 'message': 'Product ID required'}, status=400)
        
        if action == 'remove':
            quantity = 0
        
        cart_count = CartService.update_cart_item(request, product_id, quantity)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Cart updated',
            'cart_count': cart_count
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@customer_only    
def checkout(request):
    """Checkout page - address + payment selection"""
    if request.user.role != 'customer':
        messages.error(request, "Only customers can proceed to checkout.")
        return redirect('shop:home')
    cart = request.session.get('cart', {})
    if not cart:
        return redirect('shop:cart')
    
    # Calculate order total
    from items.models import Product
    products = Product.objects.filter(id__in=cart.keys(), is_active=True)
    total = sum(p.price * cart[str(p.id)] for p in products if p.stock >= cart[str(p.id)])
    
    context = {
        'total': total,
        'user_address': request.user.address if hasattr(request.user, 'address') else {},
    }
    return render(request, 'shop/checkout.html', context)

# shop/views.py

# shop/views.py - create_order function

@customer_only
@require_POST
def create_order(request):
    """Create order - CUSTOMERS ONLY"""
    import json
    from django.db import transaction
    
    try:
        data = json.loads(request.body)
        address = data.get('address', {})
        payment_method = data.get('payment_method', 'cod').lower()
        
        # Get cart from DB
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            return JsonResponse({'error': 'Cart not found'}, status=400)
        
        if not cart.items.exists():
            return JsonResponse({'error': 'Cart is empty'}, status=400)
        
        cart_items = cart.items.select_related('product', 'product__seller')
        
        # Stock validation
        for item in cart_items:
            if item.quantity > item.product.stock:
                return JsonResponse({'error': f'Not enough stock for {item.product.name}'}, status=400)
        
        total = sum(item.subtotal for item in cart_items)
        
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user, total_amount=total,
                shipping_address=address, payment_method=payment_method,
                payment_status='pending',
            )
            
            for item in cart_items:
                OrderItem.objects.create(
                    order=order, product=item.product, seller=item.product.seller,
                    quantity=item.quantity, price=item.unit_price, total=item.subtotal
                )
                item.product.stock -= item.quantity
                item.product.save()
            
            cart.items.all().delete()
        
        # Razorpay for non-COD
        if payment_method != 'cod':
            import razorpay
            razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            razorpay_order = razorpay_client.order.create({
                'amount': int(total * 100), 'currency': 'INR',
                'receipt': order.unique_order_id, 'payment_capture': 1
            })
            order.razorpay_order_id = razorpay_order['id']
            order.save()
            
            return JsonResponse({
                'status': 'success', 'order_id': order.unique_order_id,
                'razorpay_order_id': razorpay_order['id'],
                'key': settings.RAZORPAY_KEY_ID, 'amount': int(total * 100), 'currency': 'INR',
            })
        
        return JsonResponse({'status': 'success', 'order_id': order.unique_order_id})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
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