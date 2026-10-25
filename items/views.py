# items/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import F, Avg, Count, Q, Sum, ProtectedError
from .models import *
from .forms import *
from common.decorators import *
from PIL import Image
import io
import json
from orders.models import *
from django.core.serializers.json import DjangoJSONEncoder
from .utils import *
import os
import uuid
import shutil
from django.conf import settings
from django.core.files import File

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
    - Admin (staff/superuser)  → any product
    - Seller                 → only their own product
    Raises 404 if not found or not permitted.
    """
    if user.is_admin:
        return get_object_or_404(Product, pk=product_id)
    return get_object_or_404(Product, pk=product_id, seller__user=user)


# ---------------------------------------------------------------------------
# Temporary Upload & Image Persistence Helpers
# ---------------------------------------------------------------------------

def _is_safe_temp_path(rel_path, user_id):
    """Ensure relative path is within user's designated temp folder and has no directory traversal."""
    if not rel_path or '..' in rel_path or rel_path.startswith('/'):
        return False
    expected_prefix = f"temp_uploads/user_{user_id}/"
    return rel_path.startswith(expected_prefix)


def _handle_temp_upload_on_validation_failure(request):
    """
    Persists uploaded primary and additional image files in TemporaryProductImage (Database Model)
    when form validation fails so the seller never has to re-upload them.
    Returns: (temp_primary_dict, temp_additional_list)
    """
    # 1. Primary image
    temp_primary = None
    new_primary = request.FILES.get('primary_image')
    cached_primary_id = request.POST.get('cached_temp_primary_id')
    cached_primary_rel = request.POST.get('cached_temp_primary_image')

    if new_primary:
        # Clear prior primary temp image for this user in DB
        TemporaryProductImage.objects.filter(user=request.user, is_primary=True).delete()
        temp_obj = TemporaryProductImage.objects.create(
            user=request.user,
            image=new_primary,
            is_primary=True,
            original_filename=new_primary.name,
        )
        temp_primary = {
            'id': temp_obj.id,
            'rel_path': temp_obj.image.name,
            'url': temp_obj.image.url,
            'filename': new_primary.name,
        }
    elif cached_primary_id:
        temp_obj = TemporaryProductImage.objects.filter(id=cached_primary_id, user=request.user, is_primary=True).first()
        if temp_obj and temp_obj.image:
            temp_primary = {
                'id': temp_obj.id,
                'rel_path': temp_obj.image.name,
                'url': temp_obj.image.url,
                'filename': temp_obj.original_filename or os.path.basename(temp_obj.image.name),
            }
    elif cached_primary_rel and _is_safe_temp_path(cached_primary_rel, request.user.id):
        full_path = os.path.join(settings.MEDIA_ROOT, cached_primary_rel)
        if os.path.exists(full_path):
            temp_primary = {
                'id': None,
                'rel_path': cached_primary_rel,
                'url': f"{settings.MEDIA_URL}{cached_primary_rel}",
                'filename': os.path.basename(cached_primary_rel),
            }

    # 2. Additional images
    temp_additional = []
    # Keep existing cached that were not removed
    cached_additional_ids = request.POST.getlist('cached_temp_additional_ids')
    if cached_additional_ids:
        existing_objs = TemporaryProductImage.objects.filter(
            id__in=cached_additional_ids, user=request.user, is_primary=False
        )
        for obj in existing_objs:
            if obj.image:
                temp_additional.append({
                    'id': obj.id,
                    'rel_path': obj.image.name,
                    'url': obj.image.url,
                    'filename': obj.original_filename or os.path.basename(obj.image.name),
                })
    else:
        # Fallback to rel_paths if present
        for rel in request.POST.getlist('cached_temp_additional_images'):
            if _is_safe_temp_path(rel, request.user.id):
                full_path = os.path.join(settings.MEDIA_ROOT, rel)
                if os.path.exists(full_path):
                    temp_additional.append({
                        'id': None,
                        'rel_path': rel,
                        'url': f"{settings.MEDIA_URL}{rel}",
                        'filename': os.path.basename(rel),
                    })

    # Save newly uploaded additional images to DB
    new_additional = request.FILES.getlist('additional_images')
    start_order = len(temp_additional)
    for i, add_file in enumerate(new_additional):
        temp_obj = TemporaryProductImage.objects.create(
            user=request.user,
            image=add_file,
            is_primary=False,
            display_order=start_order + i,
            original_filename=add_file.name,
        )
        temp_additional.append({
            'id': temp_obj.id,
            'rel_path': temp_obj.image.name,
            'url': temp_obj.image.url,
            'filename': add_file.name,
        })

    return temp_primary, temp_additional


def _cleanup_user_temp_uploads(user_id):
    """Cleans up temporary uploaded database records and files for this user."""
    TemporaryProductImage.objects.filter(user_id=user_id).delete()
    user_temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads', f'user_{user_id}')
    if os.path.exists(user_temp_dir):
        try:
            shutil.rmtree(user_temp_dir)
        except Exception:
            pass


def _apply_cached_images_to_product(request, product, is_new=True):
    """
    Applies any cached primary and additional images from TemporaryProductImage DB model
    to the product if not superseded by new uploads.
    """
    # 1. Primary image: if not uploaded in request.FILES, check cached DB ID
    if not request.FILES.get('primary_image'):
        cached_primary_id = request.POST.get('cached_temp_primary_id')
        temp_primary = None
        if cached_primary_id:
            temp_primary = TemporaryProductImage.objects.filter(id=cached_primary_id, user=request.user, is_primary=True).first()
        elif request.POST.get('cached_temp_primary_image'):
            rel = request.POST.get('cached_temp_primary_image')
            if _is_safe_temp_path(rel, request.user.id):
                full_path = os.path.join(settings.MEDIA_ROOT, rel)
                if os.path.exists(full_path):
                    with open(full_path, 'rb') as f:
                        product.primary_image.save(os.path.basename(full_path), File(f), save=False)
                    product.save(update_fields=['primary_image'])

        if temp_primary and temp_primary.image:
            product.primary_image.save(os.path.basename(temp_primary.image.name), temp_primary.image.file, save=False)
            product.save(update_fields=['primary_image'])

    # 2. Additional images from DB
    cached_additional_ids = request.POST.getlist('cached_temp_additional_ids')
    from django.db.models import Max
    max_order = product.product_image_product.aggregate(
        max_order=Max('display_order')
    )['max_order']
    max_order = -1 if max_order is None else max_order

    if cached_additional_ids:
        temp_additional_objs = TemporaryProductImage.objects.filter(
            id__in=cached_additional_ids, user=request.user, is_primary=False
        )
        for i, obj in enumerate(temp_additional_objs):
            if obj.image:
                ProductImage.objects.create(
                    product=product,
                    image=obj.image,
                    is_primary=(not product.primary_image and i == 0),
                    display_order=max_order + i + 1,
                    alt_text=product.name,
                )
    elif request.POST.getlist('cached_temp_additional_images'):
        for i, rel in enumerate(request.POST.getlist('cached_temp_additional_images')):
            if _is_safe_temp_path(rel, request.user.id):
                full_path = os.path.join(settings.MEDIA_ROOT, rel)
                if os.path.exists(full_path):
                    with open(full_path, 'rb') as f:
                        ProductImage.objects.create(
                            product=product,
                            image=File(f, name=os.path.basename(full_path)),
                            is_primary=(not product.primary_image and i == 0),
                            display_order=max_order + i + 1,
                            alt_text=product.name,
                        )



# ---------------------------------------------------------------------------
# Unified Admin / Seller Dashboard
# ---------------------------------------------------------------------------

@seller_or_admin_only
def admin_dashboard(request):
    """
    Unified dashboard:
    - Admin (staff/superuser)  → sees ALL products from ALL sellers, can manage any
    - Seller                 → sees ONLY their own products
    - Others                 → redirected with error
    """
    if request.user.is_admin:
        products = (
            Product.objects
            .select_related('seller', 'category')
            .prefetch_related('product_image_product')
        )
        title = "👑 Admin Item Management"
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
    seller_id = request.GET.get('seller', '').strip()   # admin only

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
    if seller_id and request.user.is_admin:
        products = products.filter(seller_id=seller_id)

    # ── Stats ─────────────────────────────────────────────────────────────────
    # Use a fresh unfiltered queryset for stats so filters don't skew them
    if request.user.is_admin:
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

    sellers = SellerProfile.objects.all() if request.user.is_admin else None

    has_bank_details = True
    if not request.user.is_admin and hasattr(request.user, 'seller_profile'):
        sel = request.user.seller_profile
        has_bank_details = bool(sel.bank_name and sel.account_number and sel.ifsc_code and sel.account_holder_name)

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(products.order_by('-created_at'), 10)
    try:
        paginated_products = paginator.page(page)
    except PageNotAnInteger:
        paginated_products = paginator.page(1)
    except EmptyPage:
        paginated_products = paginator.page(paginator.num_pages)

    context = {
        'products':     paginated_products,
        'stats':        stats,
        'categories':   Category.objects.filter(is_active=True),
        'sellers':      sellers,
        'is_superuser': request.user.is_admin,
        'page_title':   title,
        'has_bank_details': has_bank_details,
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
    products = Product.objects.filter(seller=seller).select_related('category').annotate(variants_count=Count('variants'))

    # Apply search and filtering
    search   = request.GET.get('search', '').strip()
    status   = request.GET.get('status', '').strip()
    cat_id   = request.GET.get('category', '').strip()

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

    # Base queryset for stats cards (unfiltered to keep stats stable)
    base_qs = Product.objects.filter(seller=seller)
    stats = {
        'total':          base_qs.count(),
        'published':      base_qs.filter(status='published').count(),
        'draft':          base_qs.filter(status='draft').count(),
        'out_of_stock':   base_qs.filter(stock=0).count(),
        'low_stock':      base_qs.filter(stock__lte=5, stock__gt=0).count(),
        'total_views':    base_qs.aggregate(total=Sum('views_count'))['total'] or 0,
        'total_sold':     base_qs.aggregate(total=Sum('sold_count'))['total'] or 0,
    }

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(products.order_by('-created_at'), 10)
    try:
        paginated_products = paginator.page(page)
    except PageNotAnInteger:
        paginated_products = paginator.page(1)
    except EmptyPage:
        paginated_products = paginator.page(paginator.num_pages)

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

    has_bank_details = bool(seller.bank_name and seller.account_number and seller.ifsc_code and seller.account_holder_name)

    context = {
        'seller':        seller,
        'products':      paginated_products,
        'stats':         stats,
        'recent_orders': recent_orders,
        'categories':    Category.objects.filter(is_active=True),
        'has_bank_details': has_bank_details,
        'filters': {
            'search':   search,
            'status':   status,
            'category': cat_id,
        },
    }

    # AJAX rendering check
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1':
        return render(request, 'items/seller_dashboard_table.html', context)
    return render(request, 'items/seller_dashboard.html', context)


@require_POST
@login_required
@user_passes_test(is_seller_or_superuser, login_url='shop:home')
def save_product(request):
    """AJAX endpoint to create or update a product for a seller."""
    if not request.user.is_admin:
        sel = request.user.seller_profile
        if not (sel.bank_name and sel.account_number and sel.ifsc_code and sel.account_holder_name):
            return JsonResponse({
                'status': 'error', 
                'message': 'You must complete your bank details in your profile before you can add or list products.'
            }, status=400)
            
    product_id = request.POST.get('product_id')
    if product_id:
        product = get_object_or_404(Product, id=product_id)
        if not request.user.is_admin and product.seller != request.user.seller_profile:
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        form = ProductForm(request.POST, request.FILES, instance=product, is_superuser=request.user.is_admin, request_user=request.user)
    else:
        form = ProductForm(request.POST, request.FILES, is_superuser=request.user.is_admin, request_user=request.user)

    if form.is_valid():
        product = form.save(commit=False)
        if not product_id:
            if request.user.is_admin:
                product.seller = form.cleaned_data.get('seller')
            else:
                product.seller = request.user.seller_profile
            product.created_by = request.user
        product.save()
        return JsonResponse({'status': 'success', 'message': 'Product saved successfully'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Validation failed', 'errors': form.errors}, status=400)


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
    if not request.user.is_admin:
        sel = request.user.seller_profile
        if not (sel.bank_name and sel.account_number and sel.ifsc_code and sel.account_holder_name):
            messages.warning(request, "⚠️ You must complete your bank details in your profile before you can add products.")
            return redirect('accounts:profile')
            
    temp_primary = None
    temp_additional = []

    if request.method == 'POST':
        form = ProductForm(
            request.POST,
            request.FILES,
            is_superuser=request.user.is_admin,
            request_user=request.user,
        )
        variant_formset = ProductVariantFormSet(
            request.POST, 
            prefix='variants'
        )
        
        if form.is_valid() and variant_formset.is_valid():
            product = form.save(commit=False)

            if request.user.is_admin:
                product.seller = form.cleaned_data.get('seller')
            else:
                product.seller = request.user.seller_profile

            product.created_by = request.user
            product.save()

            # Handle newly uploaded images
            additional_images = form.cleaned_data.get('additional_images') or []
            for i, img_file in enumerate(additional_images):
                ProductImage.objects.create(
                    product=product,
                    image=img_file,
                    is_primary=(i == 0 and not product.primary_image),
                    display_order=i,
                    alt_text=product.name,
                )

            # ✅ Apply any cached images from previous failed attempts
            _apply_cached_images_to_product(request, product, is_new=True)
            _cleanup_user_temp_uploads(request.user.id)

            # ✅ Save variants with SKU generation (commit=False to populate deleted_objects)
            variants = variant_formset.save(commit=False)
            
            # ✅ Handle deleted variants first
            soft_deleted_count = 0
            for obj in variant_formset.deleted_objects:
                try:
                    obj.delete()
                except ProtectedError:
                    # Soft delete variant if referenced by existing order items
                    obj.is_active = False
                    obj.is_deleted = True
                    
                    # Prevent unique constraint violations
                    suffix = f" (deleted-{obj.id})"
                    max_len = 50 - len(suffix)
                    obj.size_value = f"{obj.size_value[:max_len]}{suffix}"
                    
                    if obj.sku:
                        sku_suffix = f"-deleted-{obj.id}"
                        sku_max_len = 50 - len(sku_suffix)
                        obj.sku = f"{obj.sku[:sku_max_len]}{sku_suffix}"
                    
                    obj.save()
                    soft_deleted_count += 1
            
            if soft_deleted_count > 0:
                messages.warning(
                    request,
                    f"⚠️ {soft_deleted_count} variant(s) could not be permanently deleted because they have been ordered by customers. They have been deactivated and hidden instead."
                )

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

            messages.success(request, f'✅ Product "{product.name}" created successfully!')
            if request.user.is_admin:
                return redirect('items:admin_dashboard')
            else:
                return redirect('items:seller_dashboard')
        else:
            # ✅ Cache uploaded images so they aren't lost on reload
            temp_primary, temp_additional = _handle_temp_upload_on_validation_failure(request)

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
            is_superuser=request.user.is_admin,
            request_user=request.user,
        )
        variant_formset = ProductVariantFormSet(prefix='variants')

    category_commissions = {
        str(c.id): c.commision_percentage for c in Category.objects.filter(is_active=True)
    }

    return render(request, 'items/product_form.html', {
        'form': form,
        'variant_formset': variant_formset,
        'title': 'Add New Product',
        'action': 'Create',
        'is_superuser': request.user.is_admin,
        'temp_primary_image': temp_primary,
        'temp_additional_images': temp_additional,
        'category_commissions_json': json.dumps(category_commissions),
    })

@seller_or_admin_only  
def product_edit(request, product_id):
    product = _get_product_for_user(request.user, product_id)
 
    temp_primary = None
    temp_additional = []

    if request.method == 'POST':
        form = ProductForm(
            request.POST,
            request.FILES,
            instance=product,
            is_superuser=request.user.is_admin,
            request_user=request.user,
        )
        variant_formset = ProductVariantFormSet(
            request.POST, 
            instance=product,
            prefix='variants'
        )
 
        if form.is_valid() and variant_formset.is_valid():
            updated = form.save(commit=False)
            if request.user.is_admin:
                updated.seller = form.cleaned_data.get('seller')
            else:
                updated.seller = request.user.seller_profile
            updated.updated_by = request.user
            updated.save()

            # Handle newly uploaded images
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

            # ✅ Apply any cached images from previous failed attempts
            _apply_cached_images_to_product(request, updated, is_new=False)
            _cleanup_user_temp_uploads(request.user.id)

            # ✅ Save variants (commit=False to populate deleted_objects)
            variants = variant_formset.save(commit=False)
            
            # ✅ Handle deleted variants first
            soft_deleted_count = 0
            for obj in variant_formset.deleted_objects:
                try:
                    obj.delete()
                except ProtectedError:
                    # Soft delete variant if referenced by existing order items
                    obj.is_active = False
                    obj.is_deleted = True
                    
                    # Prevent unique constraint violations
                    suffix = f" (deleted-{obj.id})"
                    max_len = 50 - len(suffix)
                    obj.size_value = f"{obj.size_value[:max_len]}{suffix}"
                    
                    if obj.sku:
                        sku_suffix = f"-deleted-{obj.id}"
                        sku_max_len = 50 - len(sku_suffix)
                        obj.sku = f"{obj.sku[:sku_max_len]}{sku_suffix}"
                    
                    obj.save()
                    soft_deleted_count += 1
            
            if soft_deleted_count > 0:
                messages.warning(
                    request,
                    f"⚠️ {soft_deleted_count} variant(s) could not be permanently deleted because they have been ordered by customers. They have been deactivated and hidden instead."
                )

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

            messages.success(request, f'✅ Product "{updated.name}" updated successfully!')
            if request.user.is_admin:
                return redirect('items:admin_dashboard')
            else:
                return redirect('items:seller_dashboard')
        else:
            # ✅ Cache uploaded images so they aren't lost on reload
            temp_primary, temp_additional = _handle_temp_upload_on_validation_failure(request)

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
            is_superuser=request.user.is_admin,
            request_user=request.user,
        )
        # ✅ Initialize formset with instance and prefix for GET request
        variant_formset = ProductVariantFormSet(instance=product, prefix='variants')

    category_commissions = {
        str(c.id): c.commision_percentage for c in Category.objects.filter(is_active=True)
    }

    return render(request, 'items/product_form.html', {
        'form': form,
        'product': product,
        'variant_formset': variant_formset,
        'title': f'Edit: {product.name}',
        'action': 'Update',
        'is_superuser': request.user.is_admin,
        'temp_primary_image': temp_primary,
        'temp_additional_images': temp_additional,
        'category_commissions_json': json.dumps(category_commissions),
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

    # Calculate stats for the user's dashboard response
    if request.user.is_admin:
        base_qs = Product.objects.all()
    else:
        base_qs = Product.objects.filter(seller=request.user.seller_profile)
        
    stats = {
        'total':        base_qs.count(),
        'published':    base_qs.filter(status='published').count(),
        'draft':        base_qs.filter(status='draft').count(),
        'out_of_stock': base_qs.filter(stock=0).count(),
        'low_stock':    base_qs.filter(stock__lte=5, stock__gt=0).count(),
    }

    return JsonResponse({
        'status':     'success',
        'new_status': product.status,
        'message':    f'Product is now {product.status}.',
        'stats':      stats
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

    # Calculate stats for the user's dashboard response
    if request.user.is_admin:
        base_qs = Product.objects.all()
    else:
        base_qs = Product.objects.filter(seller=request.user.seller_profile)
        
    stats = {
        'total':        base_qs.count(),
        'published':    base_qs.filter(status='published').count(),
        'draft':        base_qs.filter(status='draft').count(),
        'out_of_stock': base_qs.filter(stock=0).count(),
        'low_stock':    base_qs.filter(stock__lte=5, stock__gt=0).count(),
    }

    return JsonResponse({
        'status':  'success',
        'message': f'"{product.name}" has been archived.',
        'stats':   stats
    })


@require_POST
@login_required
@user_passes_test(is_seller_or_superuser, login_url='shop:home')
def product_update_stock(request, product_id):
    """
    AJAX POST endpoint to quick-update stock of non-variant products.
    """
    product = _get_product_for_user(request.user, product_id)
    
    if product.variants.exists():
        return JsonResponse({
            'status': 'error', 
            'message': 'Cannot update stock directly: this product has variants. Please update variant stock instead.'
        }, status=400)
    
    try:
        stock_raw = request.POST.get('stock')
        if stock_raw is None:
            return JsonResponse({'status': 'error', 'message': 'Stock value is required'}, status=400)
        stock = int(stock_raw)
        if stock < 0:
            return JsonResponse({'status': 'error', 'message': 'Stock cannot be negative'}, status=400)
        
        product.stock = stock
        product.save(update_fields=['stock', 'updated_at'])
        
        # Calculate stats for response
        if request.user.is_admin:
            base_qs = Product.objects.all()
        else:
            base_qs = Product.objects.filter(seller=request.user.seller_profile)
            
        stats = {
            'total':        base_qs.count(),
            'published':    base_qs.filter(status='published').count(),
            'draft':        base_qs.filter(status='draft').count(),
            'out_of_stock': base_qs.filter(stock=0).count(),
            'low_stock':    base_qs.filter(stock__lte=5, stock__gt=0).count(),
        }
        
        return JsonResponse({
            'status': 'success', 
            'message': 'Stock updated successfully',
            'new_stock': product.stock,
            'stats': stats
        })
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid stock value'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


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
        'is_returnable':     product.is_returnable,
        'primary_image_url': product.primary_image.url if product.primary_image else '',
    })


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------


def product_list(request, seller_identifier=None):
    """Public product catalog – all published, in-stock products with category, gender, price, search, and seller filters."""
    products = (
        Product.objects
        .filter(status='published', stock__gt=0)
        .select_related('seller', 'category')
        .prefetch_related('product_image_product')
    )

    # Filters
    category_slugs = request.GET.getlist('category')
    if not category_slugs and request.GET.get('category'):
        category_slugs = [request.GET.get('category')]
        
    genders = request.GET.getlist('gender')
    if not genders and request.GET.get('gender'):
        genders = [request.GET.get('gender')]

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    search = request.GET.get('search')
    sort = request.GET.get('sort', '-created_at')

    # Seller Filter (from URL path or query params ?seller=... or ?seller_id=...)
    seller_param = seller_identifier or request.GET.get('seller') or request.GET.get('seller_id')
    current_seller = None
    if seller_param:
        from django.utils.text import slugify
        seller_param_str = str(seller_param).strip()

        # 1. If seller_param is a numeric database ID (e.g. seller=20 or /store/20/)
        # Safely resolve seller and redirect to canonical slug storefront so sequential database ID is NEVER exposed in production!
        if seller_param_str.isdigit():
            current_seller = SellerProfile.objects.filter(id=int(seller_param_str)).first()
            if current_seller:
                query_dict = request.GET.copy()
                query_dict.pop('seller', None)
                query_dict.pop('seller_id', None)
                target_url = current_seller.get_store_url()
                if query_dict:
                    target_url = f"{target_url}?{query_dict.urlencode()}"
                return redirect(target_url)

        # 2. Match by shop_name or slug
        if not current_seller:
            current_seller = SellerProfile.objects.filter(shop_name__iexact=seller_param_str).first()
        if not current_seller:
            candidate_name = seller_param_str.replace('-', ' ').replace('_', ' ')
            current_seller = SellerProfile.objects.filter(shop_name__iexact=candidate_name).first()
        if not current_seller:
            param_slug = slugify(seller_param_str)
            for sp in SellerProfile.objects.filter(is_active=True):
                if sp.slug == param_slug or slugify(sp.shop_name) == param_slug:
                    current_seller = sp
                    break

        # 3. If accessed on /products/?seller=<slug> or /items/products/?seller=<slug> without filters, redirect to clean /store/<slug>/
        if current_seller and seller_identifier is None and not category_slugs and not genders and not min_price and not max_price and not search:
            sort_param = request.GET.get('sort')
            target_url = current_seller.get_store_url()
            if sort_param:
                target_url = f"{target_url}?sort={sort_param}"
            return redirect(target_url)

    show_gender_filter = True
    if category_slugs:
        selected_cats = Category.objects.filter(slug__in=category_slugs)
        if selected_cats.exists() and not any(c.is_gender_applicable for c in selected_cats):
            show_gender_filter = False
            genders = []

    if category_slugs:
        products = products.filter(category__slug__in=category_slugs)
    if genders:
        products = products.filter(gender__in=genders)    
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)
    if current_seller:
        products = products.filter(seller=current_seller)

    matched_seller = None
    if search:
        search_term = search.strip()
        products = products.filter(
            Q(name__icontains=search_term) |
            Q(description__icontains=search_term) |
            Q(brand__icontains=search_term) |
            Q(seller__shop_name__icontains=search_term)
        )
        # If search matches a seller shop name and no specific seller was already filtered
        if not current_seller:
            from django.utils.text import slugify
            matched_seller = SellerProfile.objects.filter(shop_name__iexact=search_term, is_active=True).first()
            if not matched_seller:
                matched_sellers = list(SellerProfile.objects.filter(shop_name__icontains=search_term, is_active=True)[:2])
                if len(matched_sellers) == 1:
                    matched_seller = matched_sellers[0]
            if not matched_seller:
                sq_slug = slugify(search_term)
                for sp in SellerProfile.objects.filter(is_active=True):
                    if sq_slug and (sq_slug in slugify(sp.shop_name)):
                        matched_seller = sp
                        break

    # Seller location lookup for storefront banner
    seller_location = ""
    target_seller = current_seller or matched_seller
    if target_seller:
        try:
            from accounts.models import SellerShopAddress
            shop_addr = SellerShopAddress.objects.filter(seller=target_seller).first()
            if shop_addr:
                parts = [p for p in [shop_addr.city, shop_addr.state] if p]
                seller_location = ", ".join(parts)
        except Exception:
            pass
        if not seller_location and isinstance(target_seller.address, dict):
            parts = [p for p in [target_seller.address.get('city'), target_seller.address.get('state')] if p]
            seller_location = ", ".join(parts)

    # Top active verified sellers for sidebar filter
    top_sellers = (
        SellerProfile.objects
        .filter(is_verified=True, is_active=True, products__status='published', products__stock__gt=0)
        .distinct()
        .order_by('shop_name')[:25]
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

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(products, 15)  # 15 items per page for clean grid alignment
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    canonical_store_url = ""
    if current_seller:
        canonical_store_url = request.build_absolute_uri(current_seller.get_store_url())
    elif matched_seller:
        canonical_store_url = request.build_absolute_uri(matched_seller.get_store_url())

    context = {
        'products': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'categories': Category.objects.filter(is_active=True),
        'genders': Product.GENDER_CHOICES,
        'show_gender_filter': show_gender_filter,
        'filters': request.GET.dict(),
        'selected_categories': category_slugs,
        'selected_genders': genders,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
        'current_seller': current_seller,
        'matched_seller': matched_seller,
        'seller_location': seller_location,
        'canonical_store_url': canonical_store_url,
        'top_sellers': top_sellers,
        'search': search,
    }
    return render(request, 'shop/product_list.html', context)


def seller_storefront(request, seller_identifier):
    """Public storefront page for a specific seller/store."""
    return product_list(request, seller_identifier=seller_identifier)


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

def get_related_products(product, limit=10):
    """
    Flipkart/Myntra style backend recommendation logic.
    Returns up to `limit` related products based on category, target gender, brand, and price proximity.
    """
    # Exclude self, and only fetch published, in-stock products
    base_qs = Product.objects.filter(status='published', stock__gt=0).exclude(pk=product.pk)
    
    # 1. Look for same category + same gender (if applicable)
    if product.show_gender:
        qs_same_cat_gender = base_qs.filter(category=product.category, gender=product.gender)
        qs_same_cat_other = base_qs.filter(category=product.category).exclude(gender=product.gender)
    else:
        qs_same_cat_gender = base_qs.filter(category=product.category)
        qs_same_cat_other = base_qs.none()
    
    # Combine lists while maintaining order (same cat & gender first)
    candidates = list(qs_same_cat_gender.select_related('seller').prefetch_related('product_image_product')[:limit * 2])
    if len(candidates) < limit:
        additional = list(qs_same_cat_other.select_related('seller').prefetch_related('product_image_product')[:limit - len(candidates)])
        candidates.extend(additional)
        
    # If still not enough, fall back to any trending/featured items
    if len(candidates) < limit:
        trending = list(base_qs.order_by('-views_count').select_related('seller').prefetch_related('product_image_product')[:limit - len(candidates)])
        candidates.extend(trending)
        
    # Remove duplicates while preserving order
    seen = set()
    unique_candidates = []
    for item in candidates:
        if item.pk not in seen:
            seen.add(item.pk)
            unique_candidates.append(item)
            
    # Rank candidates by:
    # 1. Brand match (current brand first)
    # 2. Price proximity (nearer price first)
    # 3. Popularity (views/sold count)
    def rank_score(item):
        score = 0
        # Brand match
        if product.brand and item.brand == product.brand:
            score += 10
        # Price proximity (within 25% price range is good)
        price_diff = abs(item.price - product.price)
        if product.price > 0:
            ratio = price_diff / product.price
            if ratio <= 0.25:
                score += 5
            elif ratio <= 0.5:
                score += 2
        # Popularity bonus
        score += min(5, float(item.views_count) / 1000.0)
        return score

    # Sort candidates by descending score
    unique_candidates.sort(key=rank_score, reverse=True)
    return unique_candidates[:limit]


def product_detail(request, slug):
    """Product detail page with reviews (customer-only visibility)"""
    
    product = get_object_or_404(
        Product.objects.select_related('seller', 'category')
        .prefetch_related('product_image_product', 'variants'),
        slug=slug,
        status='published',
    )
    
    # Increment views
    Product.objects.filter(pk=product.pk).update(views_count=F('views_count') + 1)
    product.refresh_from_db()

    # ─────────────────────────────────────────────
    # Images
    # ─────────────────────────────────────────────
    images = list(product.product_image_product.all().order_by('display_order', '-is_primary'))
    if product.primary_image:
        primary_exists = any(img.image.name == product.primary_image.name for img in images)
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
    variants_queryset = product.variants.filter(is_active=True).order_by('size_value')
    has_variants = variants_queryset.exists()
    variants_data = []
    total_variant_stock = 0
    
    for v in variants_queryset:
        total_variant_stock += v.stock
        variants_data.append({
            'id': v.id, 'size_value': v.size_value, 'size_type': v.size_type,
            'color': v.color, 'price': str(v.effective_price), 'stock': v.stock,
            'is_in_stock': v.is_in_stock, 'attributes': v.attributes,
        })

    # ─────────────────────────────────────────────
    # Stock Logic
    # ─────────────────────────────────────────────
    if has_variants:
        total_stock = total_variant_stock
        is_in_stock = total_variant_stock > 0
    else:
        total_stock = product.stock
        is_in_stock = product.stock > 0

    # ─────────────────────────────────────────────
    # ✅ REVIEWS & RATINGS (Customer-Only)
    # ─────────────────────────────────────────────
    
    # Check if user is a customer (reviews only visible to customers)
    is_customer = request.user.is_authenticated and request.user.role == 'customer'
    
    if is_customer:
        # Get approved reviews for this product
        reviews = product.reviews.filter(
            is_approved=True
        ).select_related('user').order_by('-created_at')[:10]  # Latest 10
        
        # Rating statistics
        rating_stats = product.reviews.filter(is_approved=True).aggregate(
            average=Avg('rating'),
            count=Count('id'),
            five_star=Count('id', filter=Q(rating=5)),
            four_star=Count('id', filter=Q(rating=4)),
            three_star=Count('id', filter=Q(rating=3)),
            two_star=Count('id', filter=Q(rating=2)),
            one_star=Count('id', filter=Q(rating=1)),
        )
        
        # User's existing review (if any)
        user_review = product.reviews.filter(user=request.user).first()
        
        # Check if user can review (purchased & not already reviewed)
        can_review = False
        if not user_review:
            has_purchased = OrderItem.objects.filter(
                product=product,
                order__user=request.user,
                order__status='delivered'
            ).exists()
            can_review = has_purchased
    else:
        # Non-customers see placeholder data
        reviews = []
        rating_stats = {'average': None, 'count': 0}
        user_review = None
        can_review = False

    # ─────────────────────────────────────────────
    # Related Products
    # ─────────────────────────────────────────────
    related = get_related_products(product, limit=10)

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
        request.user.is_admin or product.seller.user_id == request.user.pk
    )

    # ─────────────────────────────────────────────
    # Reorder Context
    # ─────────────────────────────────────────────
    reorder_context = None
    if request.user.is_authenticated:
        reorder_from_order = request.GET.get('reorder_from')
        if reorder_from_order:
            order_item = OrderItem.objects.filter(
                order__unique_order_id=reorder_from_order,
                order__user=request.user,
                product=product
            ).first()
            if order_item:
                reorder_context = {
                    'order_id': reorder_from_order,
                    'original_qty': order_item.quantity,
                    'original_price': order_item.price
                }

    # ─────────────────────────────────────────────
    # Context
    # ─────────────────────────────────────────────
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
        'variants_json': json.dumps(variants_data, cls=DjangoJSONEncoder),
        'has_variants': has_variants,
        
        # ✅ Review Context
        'is_customer': is_customer,
        'reviews': reviews if is_customer else [],
        'rating_stats': rating_stats if is_customer else {'average': None, 'count': 0},
        'user_review': user_review if is_customer else None,
        'can_review': can_review if is_customer else False,
        'reorder_context': reorder_context,
    }

    return render(request, 'shop/product_detail.html', context)
@require_POST
@seller_or_admin_only
def delete_product_image(request, image_id):
    """Delete a product image (AJAX)"""
    image = get_object_or_404(ProductImage, pk=image_id)
    
    # Check permissions
    if not request.user.is_admin and image.product.seller.user != request.user:
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



@login_required
@require_POST
def submit_review(request, product_slug):
    """Handle review submission via AJAX or form"""
    product = get_object_or_404(Product, slug=product_slug)
    
    # Check if user can review
    from orders.models import OrderItem
    has_purchased = OrderItem.objects.filter(
        product=product,
        order__user=request.user,
        order__status='delivered'
    ).exists()
    
    if not has_purchased:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Only verified purchasers can review'}, status=403)
        messages.error(request, 'Only verified purchasers can review this product')
        return redirect('items:product_detail', slug=product_slug)
    
    # Check if already reviewed
    existing_review = product.reviews.filter(user=request.user).first()
    if existing_review:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'You have already reviewed this product'}, status=400)
        messages.warning(request, 'You have already reviewed this product')
        return redirect('items:product_detail', slug=product_slug)
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json'
    
    form = ProductReviewForm(request.POST, request.FILES)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.is_verified_purchase = True
        review.save()  # Auto updates rating cache
        
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'message': 'Review submitted! Thank you for your feedback.',
                'review': {
                    'id': review.id,
                    'rating': review.rating,
                    'title': review.title,
                    'review': review.review,
                    'user_name': request.user.full_name or request.user.phone,
                    'created_at': review.created_at.strftime('%b %d, %Y'),
                    'is_verified_purchase': review.is_verified_purchase,
                }
            })
        else:
            messages.success(request, 'Review submitted! Thank you for your feedback.')
            return redirect('items:product_detail', slug=product_slug)
    else:
        if is_ajax:
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        else:
            messages.error(request, 'Please correct the errors below')
            return redirect('items:product_detail', slug=product_slug)

@login_required
@require_POST
def update_review(request, review_id):
    """Update an existing review"""
    review = get_object_or_404(ProductReview, id=review_id, user=request.user)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    form = ProductReviewForm(request.POST, request.FILES, instance=review)
    if form.is_valid():
        form.save()  # Auto updates rating cache
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'Review updated'})
        else:
            messages.success(request, 'Review updated')
    else:
        if is_ajax:
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        else:
            messages.error(request, 'Failed to update review')
            
    return redirect('items:product_detail', slug=review.product.slug)

@login_required
@require_POST
def delete_review(request, review_id):
    """Delete a review"""
    review = get_object_or_404(ProductReview, id=review_id, user=request.user)
    product_slug = review.product.slug
    review.delete()  # Auto updates rating cache
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'Review deleted'})
    
    messages.success(request, 'Review deleted')
    return redirect('items:product_detail', slug=product_slug)

@login_required
@require_POST
def mark_helpful(request, review_id):
    """Mark a review as helpful"""
    review = get_object_or_404(ProductReview, id=review_id)
    review.helpful_count = F('helpful_count') + 1
    review.save(update_fields=['helpful_count'])
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Refresh to get evaluated value of F() expression
        review.refresh_from_db()
        return JsonResponse({'status': 'success', 'helpful_count': review.helpful_count})
    
    return redirect('items:product_detail', slug=review.product.slug)


@login_required
@require_POST
def submit_seller_review(request, seller_id):
    """Handle seller review submission via AJAX or form"""
    seller = get_object_or_404(SellerProfile, id=seller_id)
    
    # Check if user can review (only verified purchasers from this seller)
    from orders.models import OrderItem
    has_purchased = OrderItem.objects.filter(
        seller=seller,
        order__user=request.user,
        order__status='delivered'
    ).exists()
    
    if not has_purchased:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Only customers who purchased from this seller can review'}, status=403)
        messages.error(request, 'Only customers who purchased from this seller can review')
        return redirect('shop:home')
        
    # Check if already reviewed
    existing_review = SellerReview.objects.filter(seller=seller, user=request.user).first()
    if existing_review:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'You have already reviewed this seller'}, status=400)
        messages.warning(request, 'You have already reviewed this seller')
        return redirect('shop:home')
        
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json'
    
    form = SellerReviewForm(request.POST, request.FILES)
    if form.is_valid():
        review = form.save(commit=False)
        review.seller = seller
        review.user = request.user
        review.is_verified_purchase = True
        review.save()  # Auto updates seller rating cache
        
        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'message': 'Seller review submitted! Thank you for your feedback.',
                'review': {
                    'id': review.id,
                    'rating': review.rating,
                    'title': review.title,
                    'review': review.review,
                    'user_name': request.user.full_name or request.user.phone,
                    'created_at': review.created_at.strftime('%b %d, %Y'),
                    'is_verified_purchase': review.is_verified_purchase,
                }
            })
        else:
            messages.success(request, 'Seller review submitted! Thank you for your feedback.')
            return redirect('shop:home')
    else:
        if is_ajax:
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        else:
            messages.error(request, 'Please correct the errors below')
            return redirect('shop:home')


@login_required
@require_POST
def update_seller_review(request, review_id):
    """Update an existing seller review"""
    review = get_object_or_404(SellerReview, id=review_id, user=request.user)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    form = SellerReviewForm(request.POST, request.FILES, instance=review)
    if form.is_valid():
        form.save()  # Auto updates seller rating cache
        if is_ajax:
            return JsonResponse({'status': 'success', 'message': 'Review updated'})
        messages.success(request, 'Review updated')
    else:
        if is_ajax:
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        messages.error(request, 'Failed to update review')
        
    return redirect('shop:home')


@login_required
@require_POST
def delete_seller_review(request, review_id):
    """Delete a seller review"""
    review = get_object_or_404(SellerReview, id=review_id, user=request.user)
    review.delete()  # Auto updates seller rating cache
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'Review deleted'})
    
    messages.success(request, 'Review deleted')
    return redirect('shop:home')

@admin_only
def verify_sellers_view(request):
    """Admin dashboard for viewing, searching, and managing all sellers"""
    
    # Filters - default to 'all' so admin sees all sellers listed
    status_filter = request.GET.get('status', 'all')  # pending, verified, rejected, all
    search_query = (request.GET.get('search') or request.GET.get('q') or '').strip()
    
    # Base queryset with relations
    sellers = SellerProfile.objects.select_related('user', 'shop_address').prefetch_related('products')
    
    # Apply filters
    if status_filter == 'pending':
        sellers = sellers.filter(is_verified=False, is_active=True)
    elif status_filter == 'verified':
        sellers = sellers.filter(is_verified=True, is_active=True)
    elif status_filter == 'rejected':
        sellers = sellers.filter(is_active=False)
    # 'all' shows everything
    
    # Comprehensive search across all seller related fields
    if search_query:
        sellers = sellers.filter(
            Q(shop_name__icontains=search_query) |
            Q(user__full_name__icontains=search_query) |
            Q(user__phone__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(gst_number__icontains=search_query) |
            Q(pan_number__icontains=search_query) |
            Q(bank_name__icontains=search_query) |
            Q(account_number__icontains=search_query) |
            Q(shop_address__city__icontains=search_query) |
            Q(shop_address__state__icontains=search_query) |
            Q(shop_address__postal_code__icontains=search_query)
        ).distinct()
    
    # Annotate with stats
    sellers = sellers.annotate(
        product_count=Count('products', filter=Q(products__status='published'), distinct=True),
        total_orders=Count('products__orderitem', filter=Q(products__orderitem__order__status='Delivered'), distinct=True)
    ).order_by('-created_at')
    
    total_count = SellerProfile.objects.count()
    pending_count = SellerProfile.objects.filter(is_verified=False, is_active=True).count()
    verified_count = SellerProfile.objects.filter(is_verified=True, is_active=True).count()
    rejected_count = SellerProfile.objects.filter(is_active=False).count()

    # Pagination
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(sellers, 15)
    try:
        paginated_sellers = paginator.page(page)
    except PageNotAnInteger:
        paginated_sellers = paginator.page(1)
    except EmptyPage:
        paginated_sellers = paginator.page(paginator.num_pages)
    
    context = {
        'sellers': paginated_sellers,
        'total_count': total_count,
        'pending_count': pending_count,
        'admin_verified_sellers': verified_count,
        'rejected_count': rejected_count,
        'current_filter': status_filter,
        'search_query': search_query,
        'page': paginated_sellers.number,
        'has_next': paginated_sellers.has_next(),
        'has_prev': paginated_sellers.has_previous(),
        'paginator': paginator,
    }
    
    return render(request, 'items/verify_sellers.html', context)


@require_POST
@admin_only
def verify_seller_action(request, seller_id):
    """AJAX endpoint to verify/reject a seller"""
    is_adm = (
        request.user.is_superuser or 
        request.user.is_staff or 
        getattr(request.user, 'role', None) in ['admin', 'staff'] or 
        getattr(request.user, 'is_admin', False)
    )
    if not is_adm:
        return JsonResponse({'status': 'error', 'message': 'Permission denied. Only Admins can verify/reject sellers.'}, status=403)
        
    try:
        data = json.loads(request.body)
        action = data.get('action')  # 'verify' or 'reject'
        reason = data.get('reason', '').strip()
        
        seller = get_object_or_404(SellerProfile, id=seller_id)
        
        if action == 'verify':
            seller.pan_verification_status = 'verified'
            seller.pan_rejection_reason = None
            seller.is_verified = True
            seller.is_active = True
            seller._admin_updating = True
            seller.save()

            if seller.user:
                seller.user.is_verified = True
                seller.user.is_active = True
                seller.user.save(update_fields=['is_verified', 'is_active', 'updated_at'])
            
            # Send welcome email using dynamic template
            try:
                from common.email_service import send_dynamic_email
                if seller.user and seller.user.email:
                    send_dynamic_email('seller_verified', [seller.user.email], {
                        'seller_name': seller.user.full_name or seller.shop_name,
                        'shop_name': seller.shop_name
                    })
            except Exception as e:
                logger.error(f"Failed to send seller verification email: {e}")
            
            return JsonResponse({
                'status': 'success',
                'message': f'✅ {seller.shop_name} is now verified!',
                'seller_id': seller.id
            })
            
        elif action == 'reject':
            seller.pan_verification_status = 'rejected'
            seller.pan_rejection_reason = reason
            seller.is_verified = False
            seller.is_active = False
            seller.save()

            if seller.user:
                seller.user.is_verified = False
                seller.user.save(update_fields=['is_verified', 'updated_at'])
            
            return JsonResponse({
                'status': 'success',
                'message': f'❌ {seller.shop_name} has been rejected',
                'seller_id': seller.id
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

@admin_only
def seller_detail_api(request, seller_id):
    """JSON API for seller modal details across all related tables"""
    seller = get_object_or_404(SellerProfile.objects.select_related('user', 'shop_address'), id=seller_id)
    shop_addr = getattr(seller, 'shop_address', None)
    
    addr_line1 = ''
    addr_city = ''
    addr_state = ''
    addr_pincode = ''
    
    if shop_addr:
        addr_line1 = shop_addr.address_line1 or ''
        addr_city = shop_addr.city or ''
        addr_state = shop_state = shop_addr.state or ''
        addr_pincode = shop_addr.postal_code or ''
    elif isinstance(seller.address, dict):
        addr_line1 = seller.address.get('address', '')
        addr_city = seller.address.get('city', '')
        addr_state = seller.address.get('state', '')
        addr_pincode = seller.address.get('postalCode', '')

    data = {
        'id': seller.id,
        'user_id': seller.user.id,
        'shop_name': seller.shop_name,
        'owner_name': seller.user.full_name or seller.user.phone,
        'user_phone': seller.user.phone,
        'user_email': seller.user.email or '',
        'user_is_active': seller.user.is_active,
        'phone': seller.phone or seller.user.phone,
        'gst_number': seller.gst_number or '',
        'description': seller.shop_description or '',
        'product_count': seller.products.filter(status='published').count(),
        'is_verified': seller.is_verified,
        'is_active': seller.is_active,
        'pan_number': seller.pan_number or '',
        'pan_verification_status': seller.pan_verification_status,
        'pan_rejection_reason': seller.pan_rejection_reason or '',
        'pan_card_file_url': seller.pan_card_file.url if seller.pan_card_file else None,
        'bank_name': seller.bank_name or '',
        'account_number': seller.account_number or '',
        'ifsc_code': seller.ifsc_code or '',
        'account_holder_name': seller.account_holder_name or '',
        'razorpay_contact_id': seller.razorpay_contact_id or '',
        'razorpay_fund_account_id': seller.razorpay_fund_account_id or '',
        'address_line1': addr_line1,
        'address_line2': shop_addr.address_line2 if shop_addr else '',
        'city': addr_city,
        'state': addr_state,
        'postal_code': addr_pincode,
        'country': shop_addr.country if shop_addr else 'India',
        'pickup_instructions': shop_addr.pickup_instructions if shop_addr else '',
        'rating': float(seller.rating) if seller.rating else 0.0,
        'registered_date': seller.created_at.strftime('%b %d, %Y'),
    }
    return JsonResponse(data)    


@admin_only
def seller_edit_view(request, seller_id):
    """
    Admin-only page to view & edit ANY information of a seller across all related tables:
    - User account (Owner name, Phone, Email, Password reset, Active status)
    - SellerProfile (Shop name, description, GST, PAN, KYC status, Bank details, Payout IDs, Verified status)
    - SellerShopAddress (Address lines, City, State, Pincode, Country, Pickup instructions)
    """
    from django.db import transaction
    from accounts.models import User, SellerShopAddress

    seller = get_object_or_404(SellerProfile.objects.select_related('user', 'shop_address'), id=seller_id)
    is_admin = (
        request.user.is_superuser or 
        request.user.is_staff or 
        getattr(request.user, 'role', None) in ['admin', 'staff'] or 
        getattr(request.user, 'is_admin', False)
    )
    
    if not is_admin:
        messages.error(request, 'Permission denied. Only Admins can edit seller details.')
        return redirect('items:verify_sellers')

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'

    if request.method == 'POST':
        try:
            with transaction.atomic():
                user = seller.user
                
                # 1. Update User Account Information
                owner_name = request.POST.get('owner_name', '').strip()
                owner_phone = request.POST.get('owner_phone', '').strip()
                owner_email = request.POST.get('owner_email', '').strip().lower()
                new_password = request.POST.get('new_password', '').strip()
                is_active = request.POST.get('is_active') == 'on'

                if owner_phone and owner_phone != user.phone:
                    if User.objects.filter(phone=owner_phone).exclude(pk=user.pk).exists():
                        err = f"Phone number '{owner_phone}' is already registered with another account."
                        if is_ajax:
                            return JsonResponse({'status': 'error', 'message': err}, status=400)
                        messages.error(request, err)
                        return redirect('items:seller_edit', seller_id=seller.id)
                    user.phone = owner_phone
                    seller.phone = owner_phone

                if owner_name:
                    user.full_name = owner_name

                if owner_email:
                    if User.objects.filter(email__iexact=owner_email).exclude(pk=user.pk).exists():
                        err = f"Email '{owner_email}' is already registered with another account."
                        if is_ajax:
                            return JsonResponse({'status': 'error', 'message': err}, status=400)
                        messages.error(request, err)
                        return redirect('items:seller_edit', seller_id=seller.id)
                    user.email = owner_email
                elif 'owner_email' in request.POST:
                    user.email = None

                if new_password:
                    user.set_password(new_password)
                    messages.info(request, "Seller login password has been reset.")

                user.is_active = is_active
                user.save()

                # 2. Update SellerProfile Information
                shop_name = request.POST.get('shop_name', '').strip()
                if not shop_name:
                    err = 'Shop Name is required.'
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': err}, status=400)
                    messages.error(request, err)
                    return redirect('items:seller_edit', seller_id=seller.id)

                if SellerProfile.objects.filter(shop_name__iexact=shop_name).exclude(pk=seller.pk).exists():
                    err = f"Shop Name '{shop_name}' is already taken by another seller."
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': err}, status=400)
                    messages.error(request, err)
                    return redirect('items:seller_edit', seller_id=seller.id)

                seller.shop_name = shop_name
                seller.shop_description = request.POST.get('shop_description', '').strip()
                seller.gst_number = request.POST.get('gst_number', '').strip().upper() or None
                seller.pan_number = request.POST.get('pan_number', '').strip().upper() or None
                
                pan_status = request.POST.get('pan_verification_status', seller.pan_verification_status)
                if pan_status in ['pending', 'verified', 'rejected']:
                    seller.pan_verification_status = pan_status
                seller.pan_rejection_reason = request.POST.get('pan_rejection_reason', '').strip() or None

                if 'pan_card_file' in request.FILES:
                    seller.pan_card_file = request.FILES['pan_card_file']

                # Bank details
                seller.bank_name = request.POST.get('bank_name', '').strip()
                seller.account_number = request.POST.get('account_number', '').strip()
                seller.ifsc_code = request.POST.get('ifsc_code', '').strip().upper()
                seller.account_holder_name = request.POST.get('account_holder_name', '').strip()

                # Razorpay Payout IDs
                seller.razorpay_contact_id = request.POST.get('razorpay_contact_id', '').strip() or None
                seller.razorpay_fund_account_id = request.POST.get('razorpay_fund_account_id', '').strip() or None

                # Status
                is_verified = request.POST.get('is_verified') == 'on'
                seller.is_verified = is_verified
                seller.is_active = is_active

                # Sync verification status
                if seller.is_verified:
                    seller.pan_verification_status = 'verified'
                    seller.pan_rejection_reason = None
                elif seller.pan_verification_status == 'verified' and not seller.is_verified:
                    seller.pan_verification_status = 'pending'

                seller._admin_updating = True
                seller.save()

                user.is_verified = seller.is_verified
                user.is_active = is_active
                user.save(update_fields=['is_verified', 'is_active', 'updated_at'])

                # 3. Update SellerShopAddress (related table)
                shop_addr, _ = SellerShopAddress.objects.get_or_create(
                    seller=seller,
                    defaults={'shop_name': seller.shop_name, 'shop_phone': user.phone}
                )
                shop_addr.shop_name = seller.shop_name
                shop_addr.shop_phone = seller.phone or user.phone
                shop_addr.shop_email = user.email or ''
                shop_addr.address_line1 = request.POST.get('address_line1', '').strip()
                shop_addr.address_line2 = request.POST.get('address_line2', '').strip()
                shop_addr.city = request.POST.get('city', '').strip()
                shop_addr.state = request.POST.get('state', '').strip()
                shop_addr.postal_code = request.POST.get('postal_code', '').strip()
                shop_addr.country = request.POST.get('country', 'India').strip() or 'India'
                shop_addr.gst_number = seller.gst_number or ''
                shop_addr.pickup_instructions = request.POST.get('pickup_instructions', '').strip()
                shop_addr.is_verified = seller.is_verified
                shop_addr.save()

                # Sync address dictionary JSON field
                seller.address = {
                    'address': f"{shop_addr.address_line1} {shop_addr.address_line2}".strip(),
                    'city': shop_addr.city,
                    'state': shop_addr.state,
                    'postalCode': shop_addr.postal_code,
                }
                seller.save(update_fields=['address'])

            success_msg = f"✅ All seller details for '{seller.shop_name}' have been updated across User, Profile, and Shop Address tables!"
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': success_msg})

            messages.success(request, success_msg)
            return redirect('items:seller_edit', seller_id=seller.id)

        except Exception as e:
            err_msg = f"Failed to update seller: {str(e)}"
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': err_msg}, status=500)
            messages.error(request, err_msg)
            return redirect('items:seller_edit', seller_id=seller.id)

    # GET request: render edit form with all related data
    seller.product_count = seller.products.filter(status='published').count()
    shop_address = getattr(seller, 'shop_address', None)
    if not shop_address:
        from accounts.models import SellerShopAddress
        shop_address = SellerShopAddress.objects.filter(seller=seller).first()
        
    if not shop_address:
        seller_addr = seller.address if isinstance(seller.address, dict) else {}
        from accounts.models import SellerShopAddress
        shop_address = SellerShopAddress(
            seller=seller,
            shop_name=seller.shop_name,
            shop_phone=seller.phone or (seller.user.phone if hasattr(seller, 'user') else ''),
            shop_email=seller.user.email if hasattr(seller, 'user') and seller.user.email else '',
            address_line1=seller_addr.get('address', '') or '',
            city=seller_addr.get('city', '') or '',
            state=seller_addr.get('state', '') or '',
            postal_code=seller_addr.get('postalCode', '') or '',
            country='India'
        )
    
    from orders.models import SellerSettlement, OrderItem
    from django.utils import timezone
    from datetime import timedelta
    
    safety_date = timezone.now() - timedelta(days=10)
    seller_settlements = SellerSettlement.objects.filter(seller=seller).order_by('-created_at')[:10]
    from django.db.models import Q
    unsettled_order_items = OrderItem.objects.filter(
        seller=seller,
        is_returned=False
    ).filter(
        Q(status='delivered') | Q(order__status='delivered')
    ).filter(
        Q(delivered_at__lte=safety_date) | Q(order__delivered_at__lte=safety_date)
    ).exclude(
        settlements__isnull=False
    ).exclude(
        status__in=['cancelled', 'rto', 'rto_in_transit', 'rto_delivered', 'returned', 'failed']
    ).exclude(
        order__status__in=['cancelled', 'failed']
    ).exclude(
        return_requests__status__in=[
            'requested', 'approved', 'pickup_scheduled', 'picked_up', 
            'received', 'refund_initiated', 'completed'
        ]
    ).select_related('order', 'product')[:15]

    context = {
        'seller': seller,
        'user': seller.user,
        'shop_address': shop_address,
        'seller_settlements': seller_settlements,
        'unsettled_order_items': unsettled_order_items,
        'is_admin': is_admin,
    }
    return render(request, 'items/seller_edit.html', context)