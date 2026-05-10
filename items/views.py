# items/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Sum , F
from .models import *
from .forms import *
from common.decorators import *
from PIL import Image
import io
import json
from django.core.serializers.json import DjangoJSONEncoder
from .utils import *
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



# @seller_or_admin_only
# def product_create(request):
#     if request.method == 'POST':
#         form = ProductForm(
#             request.POST, 
#             request.FILES, 
#             is_superuser=request.user.is_superuser,
#             request_user=request.user
#         )
#         if form.is_valid():
#             product = form.save(commit=False)
            
#             if not request.user.is_superuser:
#                 product.seller = request.user.seller_profile
            
#             product.created_by = request.user
#             product.save()
            
#             # ✅ Handle Primary Image
#             if form.cleaned_data.get('primary_image'):
#                 product.primary_image = form.cleaned_data['primary_image']
#                 product.save(update_fields=['primary_image'])
            
#             # ✅ Handle Additional Images
#             additional_images = form.cleaned_data.get('additional_images')
#             if additional_images:
#                 for i, img_file in enumerate(additional_images):
#                     ProductImage.objects.create(
#                         product=product,
#                         image=img_file,
#                         is_primary=(i == 0 and not product.primary_image),  # First as primary if none set
#                         display_order=i,
#                         alt_text=product.name
#                     )
            
#             messages.success(request, f'✅ Product "{product.name}" created successfully!')
#             return redirect('items:admin_dashboard')
#         else:
#             print("❌ Form errors:", form.errors)
#             for field, errors in form.errors.items():
#                 messages.error(request, f"{field}: {errors[0]}")
#     else:
#         form = ProductForm(
#             is_superuser=request.user.is_superuser,
#             request_user=request.user
#         )
    
#     return render(request, 'items/product_form.html', {
#         'form': form,
#         'title': 'Add New Product',
#         'action': 'Create',
#         'is_superuser': request.user.is_superuser,
#     })

# # ---------------------------------------------------------------------------
# # Product Edit
# # ---------------------------------------------------------------------------

# @seller_or_admin_only
# def product_edit(request, product_id):
#     product = _get_product_for_user(request.user, product_id)
    
#     if request.method == 'POST':
#         # ✅ Pass request.FILES to handle image uploads
#         form = ProductForm(
#             request.POST, 
#             request.FILES, 
#             instance=product,
#             is_superuser=request.user.is_superuser,
#             request_user=request.user
#         )
        
#         if form.is_valid():
#             # Save form data to instance but don't commit to DB yet
#             updated = form.save(commit=False)
            
#             # Handle seller assignment
#             if request.user.is_superuser:
#                 # Superuser can change seller via form
#                 updated.seller = form.cleaned_data.get('seller')
#             else:
#                 # Seller can only edit their own products
#                 updated.seller = request.user.seller_profile
            
#             updated.updated_by = request.user
#             updated.save()  # Now commit to DB
            
#             # ✅ Handle Primary Image Change
#             # If primary_image was changed in form, update it
#             if 'primary_image' in form.changed_data and form.cleaned_data.get('primary_image'):
#                 updated.primary_image = form.cleaned_data['primary_image']
#                 updated.save(update_fields=['primary_image'])
            
#             # ✅ Handle Additional Images Upload
#             additional_images = form.cleaned_data.get('additional_images')
#             if additional_images:
#                 # Get current max display_order
#                 max_order = product.product_image_product.aggregate(
#                     models.Max('display_order')
#                 )['display_order__max'] or -1
                
#                 for i, img_file in enumerate(additional_images):
#                     ProductImage.objects.create(
#                         product=updated,
#                         image=img_file,
#                         is_primary=False,  # Additional images are never primary
#                         display_order=max_order + i + 1,
#                         alt_text=updated.name
#                     )
            
#             messages.success(request, f'✅ Product "{updated.name}" updated successfully!')
#             return redirect('items:admin_dashboard')
#         else:
#             # ✅ Show form errors for debugging
#             print("❌ Form errors:", form.errors)
#             for field, errors in form.errors.items():
#                 messages.error(request, f"{field}: {errors[0]}")
#     else:
#         # GET request - populate form with existing data
#         form = ProductForm(
#             instance=product,
#             is_superuser=request.user.is_superuser,
#             request_user=request.user
#         )
    
#     return render(request, 'items/product_form.html', {
#         'form': form,
#         'product': product,
#         'title': f'Edit: {product.name}',
#         'action': 'Update',
#         'is_superuser': request.user.is_superuser,
#     })

# @seller_or_admin_only
# def product_create(request):
#     if request.method == 'POST':
#         form = ProductForm(
#             request.POST,
#             request.FILES,
#             is_superuser=request.user.is_superuser,
#             request_user=request.user,
#         )
#         if form.is_valid():
#             product = form.save(commit=False)

#             # ✅ Assign seller BEFORE save() so models.py line 145 doesn't blow up
#             if request.user.is_superuser:
#                 product.seller = form.cleaned_data.get('seller')
#             else:
#                 product.seller = request.user.seller_profile

#             product.created_by = request.user
#             product.save()  # seller is set now — safe

#             # if form.cleaned_data.get('primary_image'):
#             #     product.primary_image = form.cleaned_data['primary_image']
#             #     product.save(update_fields=['primary_image'])

#             additional_images = form.cleaned_data.get('additional_images') or []
#             for i, img_file in enumerate(additional_images):
#                 ProductImage.objects.create(
#                     product=product,
#                     image=img_file,
#                     is_primary=(i == 0 and not product.primary_image),
#                     display_order=i,
#                     alt_text=product.name,
#                 )

#             messages.success(request, f'✅ Product "{product.name}" created successfully!')
#             return redirect('items:admin_dashboard')
#         else:
#             for field, errors in form.errors.items():
#                 messages.error(request, f"{field}: {errors[0]}")
#     else:
#         form = ProductForm(
#             is_superuser=request.user.is_superuser,
#             request_user=request.user,
#         )

#     return render(request, 'items/product_form.html', {
#         'form':         form,
#         'title':        'Add New Product',
#         'action':       'Create',
#         'is_superuser': request.user.is_superuser,
#     })
# # ---------------------------------------------------------------------------
# # Product Edit  (FIXED: same list-iteration fix + proper max_order fallback)
# # ---------------------------------------------------------------------------
 
# @seller_or_admin_only
# def product_edit(request, product_id):
#     product = _get_product_for_user(request.user, product_id)
 
#     if request.method == 'POST':
#         form = ProductForm(
#             request.POST,
#             request.FILES,
#             instance=product,
#             is_superuser=request.user.is_superuser,
#             request_user=request.user,
#         )
 
#         if form.is_valid():
#             updated = form.save(commit=False)
 
#             if request.user.is_superuser:
#                 updated.seller = form.cleaned_data.get('seller')
#             else:
#                 updated.seller = request.user.seller_profile
 
#             updated.updated_by = request.user
#             updated.save()
 
#             # ── Primary Image ────────────────────────────────────────────
#             # if 'primary_image' in form.changed_data and form.cleaned_data.get('primary_image'):
#             #     updated.primary_image = form.cleaned_data['primary_image']
#             #     updated.save(update_fields=['primary_image'])
 
#             # ── Additional Images ────────────────────────────────────────
#             # MultipleFileField always gives us a list (empty list when nothing chosen).
#             additional_images = form.cleaned_data.get('additional_images') or []
#             if additional_images:
#                 from django.db.models import Max
#                 max_order = (
#                     product.product_image_product
#                     .aggregate(max_order=Max('display_order'))['max_order']
#                 )
#                                 # aggregate returns None when there are no rows yet
#                 if max_order is None:
#                     max_order = -1
 
#                 for i, img_file in enumerate(additional_images):
#                     ProductImage.objects.create(
#                         product=updated,
#                         image=img_file,
#                         is_primary=False,
#                         display_order=max_order + i + 1,
#                         alt_text=updated.name,
#                     )
 
#             messages.success(request, f'✅ Product "{updated.name}" updated successfully!')
#             return redirect('items:admin_dashboard')
#         else:
#             for field, errors in form.errors.items():
#                 messages.error(request, f"{field}: {errors[0]}")
#     else:
#         form = ProductForm(
#             instance=product,
#             is_superuser=request.user.is_superuser,
#             request_user=request.user,
#         )
 
#     return render(request, 'items/product_form.html', {
#         'form':         form,
#         'product':      product,
#         'title':        f'Edit: {product.name}',
#         'action':       'Update',
#         'is_superuser': request.user.is_superuser,
#     })


@seller_or_admin_only
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(
            request.POST,
            request.FILES,
            is_superuser=request.user.is_superuser,
            request_user=request.user,
        )
        variant_formset = ProductVariantFormSet(
            request.POST, 
            prefix='variants'
        )
        
        if form.is_valid() and variant_formset.is_valid():
            product = form.save(commit=False)

            if request.user.is_superuser:
                product.seller = form.cleaned_data.get('seller')
            else:
                product.seller = request.user.seller_profile

            product.created_by = request.user
            product.save()

            # Handle images
            additional_images = form.cleaned_data.get('additional_images') or []
            for i, img_file in enumerate(additional_images):
                ProductImage.objects.create(
                    product=product,
                    image=img_file,
                    is_primary=(i == 0 and not product.primary_image),
                    display_order=i,
                    alt_text=product.name,
                )

            # ✅ Save variants with SKU generation
            variants = variant_formset.save(commit=False)
            for variant in variants:
                variant.product = product
                
                # Generate SKU for new variants only
                if not variant.sku and product.sku:
                    base_sku = product.sku.replace(' ', '-').upper()
                    size_part = variant.size_value.replace(' ', '-').upper()
                    color_part = variant.color.replace(' ', '-').upper() if variant.color else ''
                    
                    candidate_sku = f"{base_sku}-{size_part}"
                    if color_part:
                        candidate_sku += f"-{color_part}"
                    
                    # Check for duplicates
                    final_sku = candidate_sku
                    counter = 1
                    while ProductVariant.objects.filter(sku=final_sku).exists():
                        final_sku = f"{candidate_sku}-{counter}"
                        counter += 1
                    
                    variant.sku = final_sku
                
                variant.save()
            
            for obj in variant_formset.deleted_objects:
                obj.delete()

            messages.success(request, f'✅ Product "{product.name}" created successfully!')
            return redirect('items:admin_dashboard')
        else:
            if not form.is_valid():
                for field, errors in form.errors.items():
                    messages.error(request, f"{field}: {errors[0]}")
            if not variant_formset.is_valid():
                for err in variant_formset.non_form_errors():
                    messages.error(request, f"Variants: {err}")
                for form_err in variant_formset.forms:
                    if form_err.errors:
                        messages.error(request, f"Variant errors: {form_err.errors}")
    else:
        form = ProductForm(
            is_superuser=request.user.is_superuser,
            request_user=request.user,
        )
        variant_formset = ProductVariantFormSet(prefix='variants')

    return render(request, 'items/product_form.html', {
        'form': form,
        'variant_formset': variant_formset,
        'title': 'Add New Product',
        'action': 'Create',
        'is_superuser': request.user.is_superuser,
    })

@seller_or_admin_only  
def product_edit(request, product_id):
    product = _get_product_for_user(request.user, product_id)
 
    if request.method == 'POST':
        form = ProductForm(
            request.POST,
            request.FILES,
            instance=product,
            is_superuser=request.user.is_superuser,
            request_user=request.user,
        )
        variant_formset = ProductVariantFormSet(
            request.POST, 
            instance=product,
            prefix='variants'
        )
 
        if form.is_valid() and variant_formset.is_valid():
            updated = form.save(commit=False)
            if request.user.is_superuser:
                updated.seller = form.cleaned_data.get('seller')
            else:
                updated.seller = request.user.seller_profile
            updated.updated_by = request.user
            updated.save()

            # Handle images
            additional_images = form.cleaned_data.get('additional_images') or []
            if additional_images:
                from django.db.models import Max
                max_order = product.product_image_product.aggregate(
                    max_order=Max('display_order')
                )['max_order'] or -1
                for i, img_file in enumerate(additional_images):
                    ProductImage.objects.create(
                        product=updated,
                        image=img_file,
                        is_primary=False,
                        display_order=max_order + i + 1,
                        alt_text=updated.name,
                    )

            # ✅ Save variants
            variants = variant_formset.save(commit=False)
            for variant in variants:
                variant.product = updated
                
                # ✅ Generate SKU only if blank AND this is a new variant (no pk)
                if not variant.sku and not variant.pk and updated.sku:
                    base_sku = updated.sku.replace(' ', '-').upper()
                    size_part = variant.size_value.replace(' ', '-').upper()
                    color_part = variant.color.replace(' ', '-').upper() if variant.color else ''
                    
                    # Build candidate SKU
                    candidate_sku = f"{base_sku}-{size_part}"
                    if color_part:
                        candidate_sku += f"-{color_part}"
                    
                    # ✅ Check for duplicates and add counter if needed
                    final_sku = candidate_sku
                    counter = 1
                    while ProductVariant.objects.filter(
                        sku=final_sku
                    ).exclude(pk=variant.pk).exists():
                        final_sku = f"{candidate_sku}-{counter}"
                        counter += 1
                    
                    variant.sku = final_sku
                
                variant.save()
            
            # ✅ Handle deleted variants
            for obj in variant_formset.deleted_objects:
                obj.delete()

            messages.success(request, f'✅ Product "{updated.name}" updated successfully!')
            return redirect('items:admin_dashboard')
        else:
            if not form.is_valid():
                for field, errors in form.errors.items():
                    messages.error(request, f"{field}: {errors[0]}")
            if not variant_formset.is_valid():
                for err in variant_formset.non_form_errors():
                    messages.error(request, f"Variants: {err}")
                # Also show field errors for debugging
                for form_err in variant_formset.forms:
                    if form_err.errors:
                        messages.error(request, f"Variant errors: {form_err.errors}")
    else:
        form = ProductForm(
            instance=product,
            is_superuser=request.user.is_superuser,
            request_user=request.user,
        )
        # ✅ Initialize formset with instance and prefix for GET request
        variant_formset = ProductVariantFormSet(instance=product, prefix='variants')
 
    return render(request, 'items/product_form.html', {
        'form': form,
        'product': product,
        'variant_formset': variant_formset,
        'title': f'Edit: {product.name}',
        'action': 'Update',
        'is_superuser': request.user.is_superuser,
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


# def product_detail(request, slug):
#     """Public product detail page — Amazon/Flipkart style."""
#     cart_count = 0

#     product = get_object_or_404(
#         Product.objects.select_related('seller', 'category')
#                        .prefetch_related('product_image_product'),
#         slug=slug,
#         status='published',
#     )

#     # Increment view count (atomic update)
#     Product.objects.filter(pk=product.pk).update(
#         views_count=F('views_count') + 1
#     )
#     product.refresh_from_db()

  
#     # Get all images for gallery
#     images = list(product.product_image_product.all().order_by('display_order', '-is_primary'))
    
#     # Add primary_image to gallery if not already included
#     if product.primary_image:
#         primary_exists = any(img.image.name == product.primary_image.name for img in images)
#         if not primary_exists:
#             # Create a simple object to hold primary image
#             class PrimaryImage:
#                 def __init__(self, image):
#                     self.image = image
#                     self.is_primary = True
#                     self.alt_text = product.name
#             images.insert(0, PrimaryImage(product.primary_image))

#     # Related products (same category, published, in stock)
#     related = (
#         Product.objects
#         .filter(category=product.category, status='published', stock__gt=0)
#         .exclude(pk=product.pk)
#         .select_related('seller')
#         .prefetch_related('product_image_product')[:4]
#     )
#     cart_count = 0
#     if request.user.is_authenticated and request.user.role == 'customer':
#         cart = getattr(request.user, 'cart', None)
#         if cart:
#             cart_count = cart.total_items
#     else:
#         cart = request.session.get('cart', {})
#         cart_count = sum(cart.values()) 
        
#     context = {
#         'product': product,
#         'images': images,
#         'related_products': related,
#         'is_in_stock': product.stock > 0,
#         'cart_count': cart_count, 
#         'show_category_nav': True,
#     }
#     return render(request, 'shop/product_detail.html', context)
# def product_detail(request, slug):
#     product = get_object_or_404(
#         Product.objects.select_related('seller', 'category')
#                        .prefetch_related('product_image_product','variants',),
#         slug=slug,
#         status='published',
#     )

#     Product.objects.filter(pk=product.pk).update(views_count=F('views_count') + 1)
#     product.refresh_from_db()

#     images = list(product.product_image_product.all().order_by('display_order', '-is_primary'))
#     if product.primary_image:
#         primary_exists = any(img.image.name == product.primary_image.name for img in images)
#         if not primary_exists:
#             class PrimaryImage:
#                 def __init__(self, image):
#                     self.image = image
#                     self.is_primary = True
#                     self.alt_text = product.name
#             images.insert(0, PrimaryImage(product.primary_image))

#     related = (
#         Product.objects
#         .filter(category=product.category, status='published', stock__gt=0)
#         .exclude(pk=product.pk)
#         .select_related('seller')
#         .prefetch_related('product_image_product')[:4]
#     )

#     cart_count = 0
#     if request.user.is_authenticated and request.user.role == 'customer':
#         cart = getattr(request.user, 'cart', None)
#         if cart:
#             cart_count = cart.total_items
#     else:
#         cart = request.session.get('cart', {})
#         cart_count = sum(cart.values())

#     # ✅ superuser OR the seller whose user account matches request.user
#     can_manage = request.user.is_authenticated and (
#         request.user.is_superuser or
#         product.seller.user_id == request.user.pk
#     )
#     variants_data = []
#     for v in product.variants.filter(is_active=True).order_by('size_value'):
#         variants_data.append({
#             'id': v.id,
#             'size_value': v.size_value,
#             'size_type': v.size_type,
#             'color': v.color,
#             'price': str(v.effective_price),
#             'stock': v.stock,
#             'is_in_stock': v.is_in_stock,
#             'attributes': v.attributes,
#         })
#     context = {
#         'product':           product,
#         'images':            images,
#         'related_products':  related,
#         'is_in_stock':       product.stock > 0,
#         'cart_count':        cart_count,
#         'show_category_nav': True,
#         'can_manage':        can_manage,
#         'variants': product.variants.filter(is_active=True).order_by('size_value'),
#         'variants_json': json.dumps(variants_data, cls=DjangoJSONEncoder),  # For JS
#         'has_variants': product.variants.filter(is_active=True, stock__gt=0).exists(),
#     }
#     return render(request, 'shop/product_detail.html', context)
@login_required
def product_detail(request, slug):

    product = get_object_or_404(
        Product.objects.select_related(
            'seller',
            'category'
        ).prefetch_related(
            'product_image_product',
            'variants',
        ),
        slug=slug,
        status='published',
    )
    print(product)
    # Increment views
    Product.objects.filter(pk=product.pk).update(
        views_count=F('views_count') + 1
    )

    product.refresh_from_db()

    # ─────────────────────────────────────────────
    # Images
    # ─────────────────────────────────────────────
    images = list(
        product.product_image_product.all().order_by(
            'display_order',
            '-is_primary'
        )
    )

    # Add primary image if missing
    if product.primary_image:
        primary_exists = any(
            img.image.name == product.primary_image.name
            for img in images
        )

        if not primary_exists:

            class PrimaryImage:
                def __init__(self, image):
                    self.image = image
                    self.is_primary = True
                    self.alt_text = product.name

            images.insert(0, PrimaryImage(product.primary_image))

    # ─────────────────────────────────────────────
    # Variants
    # ─────────────────────────────────────────────
    variants_queryset = product.variants.filter(
        is_active=True
    ).order_by('size_value')
    print(variants_queryset)
    has_variants = variants_queryset.exists()

    variants_data = []

    total_variant_stock = 0

    for v in variants_queryset:

        total_variant_stock += v.stock
        print(v.is_in_stock)
        variants_data.append({
            'id': v.id,
            'size_value': v.size_value,
            'size_type': v.size_type,
            'color': v.color,
            'price': str(v.effective_price),
            'stock': v.stock,
            'is_in_stock': v.is_in_stock,
            'attributes': v.attributes,
        })

    # ─────────────────────────────────────────────
    # Stock Logic
    # ─────────────────────────────────────────────

    # If product has variants → use variant stock
    # Else use product stock

    if has_variants:
        total_stock = total_variant_stock
        is_in_stock = total_variant_stock > 0
    else:
        total_stock = product.stock
        is_in_stock = product.stock > 0

    # ─────────────────────────────────────────────
    # Related Products
    # ─────────────────────────────────────────────

    related = (
        Product.objects
        .filter(
            category=product.category,
            status='published'
        )
        .exclude(pk=product.pk)
        .select_related('seller')
        .prefetch_related('product_image_product')[:4]
    )

    # ─────────────────────────────────────────────
    # Cart Count
    # ─────────────────────────────────────────────

    cart_count = 0

    if request.user.is_authenticated and request.user.role == 'customer':

        cart = getattr(request.user, 'cart', None)

        if cart:
            cart_count = cart.total_items

    else:
        cart = request.session.get('cart', {})
        cart_count = sum(cart.values())

    # ─────────────────────────────────────────────
    # Permissions
    # ─────────────────────────────────────────────

    can_manage = request.user.is_authenticated and (
        request.user.is_superuser or
        product.seller.user_id == request.user.pk
    )

    # ─────────────────────────────────────────────
    # Context
    # ─────────────────────────────────────────────
    print(is_in_stock)
    print(total_stock)
    context = {
        'product': product,
        'images': images,
        'related_products': related,

        'is_in_stock': is_in_stock,
        'total_stock': total_stock,

        'cart_count': cart_count,
        'show_category_nav': True,
        'can_manage': can_manage,

        'variants': variants_queryset,
        'variants_json': json.dumps(
            variants_data,
            cls=DjangoJSONEncoder
        ),

        # IMPORTANT
        'has_variants': has_variants,
    }

    return render(
        request,
        'shop/product_detail.html',
        context
    )
@require_POST
@seller_or_admin_only
def delete_product_image(request, image_id):
    """Delete a product image (AJAX)"""
    image = get_object_or_404(ProductImage, pk=image_id)
    
    # Check permissions
    if not request.user.is_superuser and image.product.seller.user != request.user:
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
    
    # Delete image file and record
    if image.image:
        image.image.delete(save=False)  # Delete file from storage
    image.delete()
    
    return JsonResponse({'status': 'success', 'message': 'Image deleted'})

def compress_image(image_file, max_size=1024):
    """Compress image to max_size pixels while maintaining aspect ratio"""
    img = Image.open(image_file)
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    
    # Convert to RGB if necessary (for JPEG)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    
    # Save to bytes
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=85, optimize=True)
    output.seek(0)
    
    # Create a new InMemoryUploadedFile
    from django.core.files.uploadedfile import InMemoryUploadedFile
    return InMemoryUploadedFile(
        output, 'image', f"{image_file.name.rsplit('.', 1)[0]}.jpg",
        'image/jpeg', output.getbuffer().nbytes, None
    )


# items/views.py - Example wishlist toggle view

@customer_only 
@require_POST
def toggle_wishlist(request, product_id):
    product = get_object_or_404(Product, pk=product_id, status='published')

    variant_id = request.POST.get('variant_id') or None
    variant = None
    if variant_id:
        variant = get_object_or_404(ProductVariant, pk=variant_id, is_active=True)

    wishlist, _ = Wishlist.objects.get_or_create(
        user=request.user,
        defaults={'name': 'My Wishlist'}
    )

    # Check for existing non-deleted item
    existing = wishlist.items.filter(
        product=product, variant=variant, is_deleted=False
    ).first()

    if existing:
        existing.is_deleted = True
        existing.save(update_fields=['is_deleted'])
        return JsonResponse({'status': 'removed', 'message': 'Removed from wishlist'})
    else:
        # Check if a soft-deleted record exists — restore it instead of creating duplicate
        deleted_item = wishlist.items.filter(
            product=product, variant=variant, is_deleted=True
        ).first()
        if deleted_item:
            deleted_item.is_deleted = False
            deleted_item.save(update_fields=['is_deleted'])
        else:
            add_to_wishlist(user=request.user, product=product, variant=variant, priority=2)
        return JsonResponse({'status': 'added', 'message': 'Added to wishlist'})
    
@customer_only
def wishlist_status(request, product_id):
    """Check if a product is in the user's wishlist (for page load state)."""
    in_wishlist = False
    try:
        wishlist = request.user.wishlist
        in_wishlist = wishlist.items.filter(
            product_id=product_id,
            is_deleted=False
        ).exists()
    except Exception:
        pass
    return JsonResponse({'in_wishlist': in_wishlist})    

@customer_only
def wishlist_page(request):
    if request.user.role != 'customer':
        messages.error(request, 'Access denied.')
        return redirect('shop:home')
    
    try:
        wishlist = request.user.wishlist
        items = wishlist.items.filter(
            is_deleted=False
        ).select_related(
            'product', 'product__seller', 'product__category', 'variant'
        ).order_by('-created_at')
    except Wishlist.DoesNotExist:
        items = []
    
    return render(request, 'items/wishlist.html', {
        'wishlist_items': items,
    })