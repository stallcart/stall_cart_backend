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

def home(request):
    """Main shop page - matches index.html"""
    # Only show published, in-stock products
    products = Product.objects.filter(
        status='published',  # ✅ Use status field
        stock__gt=0,
        is_active=True
    ).select_related('category', 'seller').prefetch_related('product_image_product')
    
    categories = Category.objects.filter(is_active=True)
    
    # Cart count from session (only for customers)
    cart_count = 0
    if request.user.is_authenticated and request.user.role == 'customer':
        cart = request.session.get('cart', {})
        cart_count = sum(cart.values())
    
    context = {
        'products': products,
        'categories': categories,
        'cart_count': cart_count,
        'user_role': request.user.role if request.user.is_authenticated else None,
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

def cart_view(request):
    """Cart page with items from session"""

    if request.user.is_authenticated and request.user.role != 'customer':
        messages.info(request, "🛍️ You're logged in as a seller/admin. Switch to a customer account to shop, or visit your dashboard to manage products.")
        if request.user.is_seller:
            return redirect('items:admin_dashboard')
        elif request.user.is_superuser:
            return redirect('/admin/')
        return redirect('shop:home')
    cart = request.session.get('cart', {})
    
    if not cart:
        return render(request, 'shop/cart.html', {
            'cart_items': [], 
            'total': 0,
            'delivery_charge': 0,
        })
    
    # Fetch products in cart
    from items.models import Product
    product_ids = list(cart.keys())
    products = Product.objects.filter(id__in=product_ids, is_active=True)
    
    cart_items = []
    total = 0
    for p in products:
        qty = cart.get(str(p.id), 0)
        if qty > 0 and p.stock >= qty:
            subtotal = p.price * qty
            total += subtotal
            cart_items.append({
                'product': p,
                'quantity': qty,
                'subtotal': subtotal,
                'in_stock': True
            })
    
    # Calculate delivery charge
    delivery_charge = 0 if total >= 499 else 40
    
    context = {
        'cart_items': cart_items,
        'total': total,
        'delivery_charge': delivery_charge,
        'cart_count': sum(cart.values()),  # For header cart count
    }
    
    # Add user address if authenticated
    if request.user.is_authenticated and hasattr(request.user, 'address') and request.user.address:
        context['user_address'] = request.user.address
    
    return render(request, 'shop/cart.html', context)

@require_POST
def update_cart(request):
    """AJAX: Update cart quantity or remove item"""
    try:
        if request.user.is_authenticated and request.user.role != 'customer':
            return JsonResponse({'status': 'error', 'message': 'Only customers can update cart'}, status=403)
    
        data = json.loads(request.body)
        product_id = str(data.get('product_id'))
        action = data.get('action')  # 'update' or 'remove'
        
        cart = request.session.get('cart', {})
        
        if action == 'remove':
            cart.pop(product_id, None)
        elif action == 'update':
            qty = int(data.get('quantity', 1))
            if qty <= 0:
                cart.pop(product_id, None)
            else:
                cart[product_id] = qty
        
        request.session['cart'] = cart
        request.session.modified = True
        
        # Recalculate total
        from items.models import Product
        total = 0
        for pid, qty in cart.items():
            try:
                p = Product.objects.get(id=pid, is_active=True)
                if p.stock >= qty:
                    total += p.price * qty
            except:
                pass
        
        return JsonResponse({
            'status': 'success',
            'cart_count': sum(cart.values()),
            'total': total
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
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

@login_required
@require_POST
def create_order(request):
    """Create order + Razorpay payment"""
    cart = request.session.get('cart', {})
    if not cart:
        return JsonResponse({'error': 'Cart is empty'}, status=400)
    
    # Calculate totals
    products = Product.objects.filter(id__in=cart.keys(), status='published')
    total = sum(p.price * cart[str(p.id)] for p in products if p.stock >= cart[str(p.id)])
    
    # Create Order
    order = Order.objects.create(
        user=request.user,
        total_amount=total,
        shipping_address=request.user.address if hasattr(request.user, 'address') else {},
        payment_method='razorpay',
        payment_status='pending',
    )
    
    # Create OrderItems
    for p in products:
        qty = cart[str(p.id)]
        if p.stock >= qty:
            OrderItem.objects.create(
                order=order,
                product=p,
                seller=p.seller,
                quantity=qty,
                price=p.price,
                total=p.price * qty
            )
    
    # Create Razorpay Order
    razorpay_order = razorpay_client.order.create({
        'amount': int(total * 100),  # paise
        'currency': 'INR',
        'receipt': order.order_id,
        'payment_capture': 1,
        'notes': {
            'order_id': order.order_id,
            'user_id': request.user.id,
        }
    })
    
    # Save Razorpay IDs
    order.razorpay_order_id = razorpay_order['id']
    order.save()
    
    # Clear cart
    request.session['cart'] = {}
    
    return JsonResponse({
        'status': 'success',
        'order_id': order.order_id,
        'razorpay_order_id': razorpay_order['id'],
        'razorpay_key': settings.RAZORPAY_KEY_ID,
        'amount': int(total * 100),
        'currency': 'INR',
        'name': SiteSettings.SITE_NAME,
        'description': f'Order {order.order_id}',
        'prefill': {
            'name': request.user.full_name,
            'email': request.user.email or '',
            'contact': request.user.phone
        }
    })

@login_required
def order_success(request, order_id):
    """Order confirmation page"""
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        return render(request, 'shop/order_success.html', {'order': order})
    except Order.DoesNotExist:
        return redirect('shop:home')