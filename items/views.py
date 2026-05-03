# items/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum , F
from .models import Product, Category, SellerProfile, ProductImage
from .forms import ProductForm
from common.decorators import *

# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def is_seller_or_superuser(user):
    return user.is_admin or user.is_verified_seller

def is_verified_seller(user):
    return user.is_verified_seller


def _get_product_for_user(user, product_id):
    """
    Return a Product the user is allowed to edit/delete.
    - Superuser  → any product
    - Seller     → only their own product
    Raises 404 if not found or not permitted.
    """
    if user.is_superuser:
        return get_object_or_404(Product, pk=product_id)
    return get_object_or_404(Product, pk=product_id, seller__user=user)


# ---------------------------------------------------------------------------
# Unified Admin / Seller Dashboard
# ---------------------------------------------------------------------------

@seller_or_admin_only
def admin_dashboard(request):
    """
    Unified dashboard:
    - Superuser  → sees ALL products from ALL sellers, can manage any
    - Seller     → sees ONLY their own products
    - Others     → redirected with error
    """
    if request.user.is_superuser:
        products = (
            Product.objects
            .select_related('seller', 'category')
            .prefetch_related('product_image_product')
        )
        title = "👑 Superuser Item Management"

    elif hasattr(request.user, 'seller_profile'):
        if not request.user.seller_profile.is_verified:
            messages.error(request, "Your seller account is pending verification.")
            return redirect('shop:home')
        products = (
            Product.objects
            .filter(seller=request.user.seller_profile)
            .select_related('category')
        )
        title = f"🏪 {request.user.seller_profile.shop_name} Dashboard"

    else:
        messages.error(request, "Access denied. Seller or Admin access required.")
        return redirect('shop:home')

    # ── Filters ──────────────────────────────────────────────────────────────
    search   = request.GET.get('search', '').strip()
    status   = request.GET.get('status', '').strip()
    cat_id   = request.GET.get('category', '').strip()
    seller_id = request.GET.get('seller', '').strip()   # superuser only

    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(sku__icontains=search) |
            Q(brand__icontains=search)
        )
    if status:
        products = products.filter(status=status)
    if cat_id:
        products = products.filter(category_id=cat_id)
    if seller_id and request.user.is_superuser:
        products = products.filter(seller_id=seller_id)

    # ── Stats ─────────────────────────────────────────────────────────────────
    # Use a fresh unfiltered queryset for stats so filters don't skew them
    if request.user.is_superuser:
        base_qs = Product.objects.all()
    else:
        base_qs = Product.objects.filter(seller=request.user.seller_profile)

    stats = {
        'total':        base_qs.count(),
        'published':    base_qs.filter(status='published').count(),
        'draft':        base_qs.filter(status='draft').count(),
        'out_of_stock': base_qs.filter(stock=0).count(),
        'low_stock':    base_qs.filter(stock__lte=5, stock__gt=0).count(),
        'total_value':  base_qs.aggregate(total=Sum('price'))['total'] or 0,
    }

    sellers = SellerProfile.objects.all() if request.user.is_superuser else None

    context = {
        'products':     products.order_by('-created_at'),
        'stats':        stats,
        'categories':   Category.objects.filter(is_active=True),
        'sellers':      sellers,
        'is_superuser': request.user.is_superuser,
        'page_title':   title,
        'filters': {
            'search':   search,
            'status':   status,
            'category': cat_id,
            'seller':   seller_id,
        },
    }
    return render(request, 'items/admin_dashboard.html', context)


# ---------------------------------------------------------------------------
# Seller Dashboard (separate, seller-only view)
# ---------------------------------------------------------------------------

@seller_only
def seller_dashboard(request):
    """Seller's personal dashboard – orders + product overview."""
    seller   = request.user.seller_profile
    products = Product.objects.filter(seller=seller).select_related('category')

    stats = {
        'total_products': products.count(),
        'published':      products.filter(status='published').count(),
        'draft':          products.filter(status='draft').count(),
        'out_of_stock':   products.filter(stock=0).count(),
        'low_stock':      products.filter(stock__lte=5, stock__gt=0).count(),
        'total_views':    products.aggregate(total=Sum('views_count'))['total'] or 0,
        'total_sold':     products.aggregate(total=Sum('sold_count'))['total'] or 0,
    }

    try:
        from orders.models import OrderItem
        recent_orders = (
            OrderItem.objects
            .filter(
                product__seller=seller,
                order__status__in=['Pending', 'Processing', 'Out for Delivery']
            )
            .select_related('order', 'product')
            .order_by('-order__created_at')[:10]
        )
    except Exception:
        recent_orders = []

    context = {
        'seller':        seller,
        'products':      products,
        'stats':         stats,
        'recent_orders': recent_orders,
        'categories':    Category.objects.filter(is_active=True),
    }
    return render(request, 'items/seller_dashboard.html', context)


# ---------------------------------------------------------------------------
# Product Create
# ---------------------------------------------------------------------------


@seller_or_admin_only
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, is_superuser=request.user.is_superuser,request_user=request.user )
        if form.is_valid():
            product = form.save(commit=False)

            if not request.user.is_superuser:
                product.seller = request.user.seller_profile

            product.created_by = request.user
            product.save()

            # Handle multiple additional images
            files = request.FILES.getlist('images')
            if files:
                for i, img in enumerate(files):
                    ProductImage.objects.create(
                        product=product,
                        image=img,
                        # If no primary image set, make the first uploaded image primary
                        is_primary=(i == 0 and not product.primary_image),
                        display_order=i,
                    )

            messages.success(request, f'Product "{product.name}" created successfully!')
            return redirect('items:admin_dashboard')
    else:
        form = ProductForm(is_superuser=request.user.is_superuser,request_user=request.user )

    return render(request, 'items/product_form.html', {
        'form': form, 'title': 'Add New Product', 'action': 'Create',
    })


# ---------------------------------------------------------------------------
# Product Edit
# ---------------------------------------------------------------------------

@seller_or_admin_only
def product_edit(request, product_id):
    product = _get_product_for_user(request.user, product_id)
    print(product)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product,
            is_superuser=request.user.is_superuser,request_user=request.user)
        if form.is_valid():
            updated = form.save(commit=False)

            if not request.user.is_superuser:
                updated.seller = request.user.seller_profile

            updated.updated_by = request.user
            updated.save()

            # Handle Additional Images:
            # If user uploads new images, delete old additional images first to prevent duplicates
            files = request.FILES.getlist('images')
            if files:
                product.product_image_product.all().delete()
                for i, img in enumerate(files):
                    ProductImage.objects.create(
                        product=updated,
                        image=img,
                        is_primary=False, # Additional images are not primary by default in edit mode
                        display_order=i,
                    )

            messages.success(request, f'Product "{updated.name}" updated!')
            return redirect('items:admin_dashboard')
    else:
        form = ProductForm(instance=product, is_superuser=request.user.is_superuser,request_user=request.user)

    return render(request, 'items/product_form.html', {
        'form': form, 'product': product, 'title': f'Edit: {product.name}', 'action': 'Update',
    })

# ---------------------------------------------------------------------------
# Product Toggle Status (AJAX)
# ---------------------------------------------------------------------------

@require_POST
@login_required
@user_passes_test(is_seller_or_superuser, login_url='shop:home')
def product_toggle_status(request, product_id):
    """
    Toggle published ↔ draft.
    Superuser can toggle any product; seller only their own.
    """
    product = _get_product_for_user(request.user, product_id)

    if product.status == 'discontinued':
        return JsonResponse({
            'status':  'error',
            'message': 'Cannot toggle a discontinued product.',
        }, status=400)

    product.status = 'published' if product.status == 'draft' else 'draft'
    product.save(update_fields=['status'])

    return JsonResponse({
        'status':     'success',
        'new_status': product.status,
        'message':    f'Product is now {product.status}.',
    })


# ---------------------------------------------------------------------------
# Product Delete / Archive (AJAX)
# ---------------------------------------------------------------------------

@require_POST
@login_required
@user_passes_test(is_seller_or_superuser, login_url='shop:home')
def product_delete(request, product_id):
    """
    Soft-delete (archive) a product by setting status='discontinued'.
    Superuser can archive any product; seller only their own.
    """
    product = _get_product_for_user(request.user, product_id)
    product.status = 'discontinued'
    product.save(update_fields=['status'])

    return JsonResponse({
        'status':  'success',
        'message': f'"{product.name}" has been archived.',
    })


# ---------------------------------------------------------------------------
# Product API (for edit modal fetch)
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(is_seller_or_superuser, login_url='shop:home')
def product_api_detail(request, product_id):
    """
    JSON endpoint used by the edit modal to pre-populate fields.
    """
    product = _get_product_for_user(request.user, product_id)
    return JsonResponse({
        'id':                product.pk,
        'name':              product.name,
        'category':          product.category_id,
        'seller':            product.seller_id,
        'price':             str(product.price),
        'mrp':               str(product.mrp) if product.mrp else '',
        'cost_price':        str(product.cost_price) if product.cost_price else '',
        'discount_percent':  product.discount_percent,
        'stock':             product.stock,
        'low_stock_threshold': product.low_stock_threshold,
        'status':            product.status,
        'short_description': product.short_description,
        'description':       product.description,
        'brand':             product.brand,
        'sku':               product.sku or '',
        'weight':            str(product.weight) if product.weight else '',
        'dimensions':        product.dimensions,
        'meta_title':        product.meta_title,
        'meta_description':  product.meta_description,
        'is_featured':       product.is_featured,
        'is_hot_deal':       product.is_hot_deal,
        'primary_image_url': product.primary_image.url if product.primary_image else '',
    })


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------


def product_list(request):
    """Public product catalog – all published, in-stock products."""
    products = (
        Product.objects
        .filter(status='published', stock__gt=0)
        .select_related('seller', 'category')
        .prefetch_related('product_image_product')
    )

    # Filters
    category_slug = request.GET.get('category')
    gender = request.GET.get('gender')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    search = request.GET.get('search')
    sort = request.GET.get('sort', '-created_at')

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if gender:  # ✅ Apply gender filter
        products = products.filter(gender=gender)    
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(brand__icontains=search)
        )

    # Sorting
    sort_options = {
        'newest': '-created_at',
        'price_asc': 'price',
        'price_desc': '-price',
        'popular': '-views_count',
        'name_asc': 'name',
    }
    order_by = sort_options.get(sort, '-created_at')
    products = products.order_by(order_by)

    context = {
        'products': products,
        'categories': Category.objects.filter(is_active=True),
        'genders': Product.GENDER_CHOICES,
        'filters': request.GET.dict(),
        'sort': sort,
    }
    return render(request, 'shop/product_list.html', context)


def product_detail(request, slug):
    """Public product detail page — Amazon/Flipkart style."""
    cart_count = 0

    product = get_object_or_404(
        Product.objects.select_related('seller', 'category')
                       .prefetch_related('product_image_product'),
        slug=slug,
        status='published',
    )

    # Increment view count (atomic update)
    Product.objects.filter(pk=product.pk).update(
        views_count=F('views_count') + 1
    )
    product.refresh_from_db()

  
    # Get all images for gallery
    images = list(product.product_image_product.all().order_by('display_order', '-is_primary'))
    
    # Add primary_image to gallery if not already included
    if product.primary_image:
        primary_exists = any(img.image.name == product.primary_image.name for img in images)
        if not primary_exists:
            # Create a simple object to hold primary image
            class PrimaryImage:
                def __init__(self, image):
                    self.image = image
                    self.is_primary = True
                    self.alt_text = product.name
            images.insert(0, PrimaryImage(product.primary_image))

    # Related products (same category, published, in stock)
    related = (
        Product.objects
        .filter(category=product.category, status='published', stock__gt=0)
        .exclude(pk=product.pk)
        .select_related('seller')
        .prefetch_related('product_image_product')[:4]
    )
    if request.user.is_authenticated and request.user.role == 'customer':
        cart = request.session.get('cart', {})
        cart_count = sum(cart.values())
        
    context = {
        'product': product,
        'images': images,
        'related_products': related,
        'is_in_stock': product.stock > 0,
        'cart_count': cart_count, 
    }
    return render(request, 'shop/product_detail.html', context)