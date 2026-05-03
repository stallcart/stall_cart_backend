from django.shortcuts import render, redirect , get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db import models  # ✅ ADD THIS LINE
from django.db.models import Sum, Avg, Count
from decimal import Decimal
from django.views.decorators.http import require_http_methods
from .forms import UserRegistrationForm, UserLoginForm
import json
from items.models import SellerProfile , Product

# def login_view(request):
#     if request.user.is_authenticated:
#         return redirect('shop:home')
    
#     if request.method == 'POST':
#         form = UserLoginForm(request, data=request.POST)  # ✅ FIXED
        
#         if form.is_valid():
#             user = form.get_user()
#             login(request, user)
            
#             if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#                 return JsonResponse({
#                     'status': 'success',
#                     'redirect': request.POST.get('next', '/')
#                 })
            
#             return redirect(request.POST.get('next', 'shop:home'))
        
#         messages.error(request, "Invalid mobile number or password.")
#     else:
#         form = UserLoginForm()
    
#     return render(request, 'accounts/login.html', {'form': form})
# accounts/views.py
# accounts/views.py
def login_view(request):
    if request.user.is_authenticated:
        return redirect('shop:home')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # ✅ AJAX response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'redirect': request.POST.get('next', '/')
                })
            
            return redirect(request.POST.get('next', 'shop:home'))
        
        # ✅ AJAX error response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid mobile number or password.',
                'errors': form.errors
            }, status=400)
        
        messages.error(request, "Invalid mobile number or password.")
    
    else:
        form = UserLoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

# @require_POST
def register_view(request):
    """Handle user registration with role selection (customer/seller)"""
    
    # Handle AJAX submission from modal
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            form = UserRegistrationForm(data)
            
            if form.is_valid():
                # Create user
                user = form.save(commit=False)
                user.role = form.cleaned_data['user_role']  # Set role from form
                user.save()
                
                # If seller, create SellerProfile
                if user.role == 'seller':
                    SellerProfile.objects.create(
                        user=user,
                        shop_name=form.cleaned_data['shop_name'],
                        shop_description=form.cleaned_data.get('shop_description', ''),
                        gst_number=form.cleaned_data.get('gst_number'),
                        phone=user.phone,  # Use same phone as user
                        is_verified=False,  # Pending admin verification
                        created_by=user
                    )
                    messages.success(request, f"Seller account created! Your shop '{form.cleaned_data['shop_name']}' is pending verification.")
                else:
                    messages.success(request, "Account created successfully! Welcome to StallCart.")
                
                # Auto-login
                login(request, user)
                
                return JsonResponse({
                    'status': 'success', 
                    'redirect': '/',
                    'role': user.role
                })
            
            return JsonResponse({
                'status': 'error', 
                'errors': form.errors
            }, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
    
    # Handle regular form submission (non-AJAX)
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            # Create user
            user = form.save(commit=False)
            user.role = form.cleaned_data['user_role']
            user.save()
            
            # If seller, create SellerProfile
            if user.role == 'seller':
                SellerProfile.objects.create(
                    user=user,
                    shop_name=form.cleaned_data['shop_name'],
                    shop_description=form.cleaned_data.get('shop_description', ''),
                    gst_number=form.cleaned_data.get('gst_number'),
                    phone=user.phone,
                    is_verified=False,
                    created_by=user
                )
                messages.success(request, f"🎉 Seller account created! Your shop '{form.cleaned_data['shop_name']}' is pending admin verification. You can start adding products once verified.")
            else:
                messages.success(request, "✅ Account created successfully! Welcome to StallCart.")
            
            # Auto-login
            login(request, user)
            return redirect('shop:home')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('shop:home')

@login_required
def change_password_view(request):
    from django.contrib.auth.forms import PasswordChangeForm
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully!")
            return redirect('accounts:profile')
        else:
            # Debug: Print form errors to console/PythonAnywhere logs
            print("❌ PasswordChangeForm errors:", form.errors)
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})

# Custom Password Reset Views (Email-based)
class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/forgot_password.html'
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = '/accounts/password-reset/done/'
    html_email_template_name = 'accounts/password_reset_email.html'

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = '/accounts/password-reset/complete/'

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'

# accounts/views.py - Update profile_view function

# accounts/views.py
@login_required
def profile_view(request):
    """User profile management - role-based sections"""
    
    # Handle AJAX POST requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'update_profile':
                request.user.full_name = data.get('full_name', request.user.full_name)
                request.user.email = data.get('email', request.user.email)
                request.user.save()
                return JsonResponse({'status': 'success', 'message': 'Profile updated'})
            
            elif action == 'add_address':
                if request.user.role != 'customer':
                    return JsonResponse({'status': 'error', 'message': 'Only customers can add addresses'}, status=403)
                
                addr_data = data.get('address', {})
                is_default = data.get('is_default', False)
                
                from accounts.models import Address
                Address.objects.create(
                    user=request.user,
                    name=addr_data.get('name'),
                    phone=addr_data.get('phone'),
                    address_line1=addr_data.get('address_line1'),
                    address_line2=addr_data.get('address_line2', ''),
                    city=addr_data.get('city'),
                    state=addr_data.get('state'),
                    postal_code=addr_data.get('postal_code'),
                    country=addr_data.get('country', 'India'),
                    address_type=addr_data.get('address_type', 'shipping'),
                    is_default=is_default
                )
                return JsonResponse({'status': 'success', 'message': 'Address added'})
            
            elif action == 'update_address':
                if request.user.role != 'customer':
                    return JsonResponse({'status': 'error', 'message': 'Only customers can update addresses'}, status=403)
                
                addr_id = data.get('address_id')
                addr_data = data.get('address', {})
                
                from accounts.models import Address
                address = get_object_or_404(Address, id=addr_id, user=request.user)
                address.name = addr_data.get('name', address.name)
                address.phone = addr_data.get('phone', address.phone)
                address.address_line1 = addr_data.get('address_line1', address.address_line1)
                address.address_line2 = addr_data.get('address_line2', address.address_line2)
                address.city = addr_data.get('city', address.city)
                address.state = addr_data.get('state', address.state)
                address.postal_code = addr_data.get('postal_code', address.postal_code)
                address.country = addr_data.get('country', address.country)
                address.address_type = addr_data.get('address_type', address.address_type)
                # Handle is_default separately to trigger model save logic
                if data.get('is_default') is not None:
                    address.is_default = data.get('is_default')
                address.save()
                return JsonResponse({'status': 'success', 'message': 'Address updated'})
            
            elif action == 'delete_address':
                if request.user.role != 'customer':
                    return JsonResponse({'status': 'error', 'message': 'Only customers can delete addresses'}, status=403)
                
                addr_id = data.get('address_id')
                from accounts.models import Address
                address = get_object_or_404(Address, id=addr_id, user=request.user)
                address.delete()
                return JsonResponse({'status': 'success', 'message': 'Address deleted'})
            
            elif action == 'set_default_address':
                if request.user.role != 'customer':
                    return JsonResponse({'status': 'error', 'message': 'Only customers can set default address'}, status=403)
                
                addr_id = data.get('address_id')
                from accounts.models import Address
                address = get_object_or_404(Address, id=addr_id, user=request.user)
                address.is_default = True
                address.save()  # This will unset others via model save()
                return JsonResponse({'status': 'success', 'message': 'Default address updated'})
            
            elif action == 'update_shop':
                if request.user.role != 'seller' or not hasattr(request.user, 'seller_profile'):
                    return JsonResponse({'status': 'error', 'message': 'Only sellers can update shop details'}, status=403)
                
                shop_data = data.get('shop', {})
                seller = request.user.seller_profile
                seller.shop_name = shop_data.get('shop_name', seller.shop_name)
                seller.shop_description = shop_data.get('shop_description', seller.shop_description)
                seller.gst_number = shop_data.get('gst_number', seller.gst_number)
                seller.save()
                return JsonResponse({'status': 'success', 'message': 'Shop details updated'})
            
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    # GET request: render profile page with role-based context
    is_customer = request.user.role == 'customer'
    is_seller = request.user.role == 'seller' and hasattr(request.user, 'seller_profile')
    is_admin = request.user.is_superuser
    
    # Customer-specific data
    user_orders = []
    wishlist_count = 0
    customer_addresses = []
    
    if is_customer:
        from orders.models import Order
        from accounts.models import Address
        user_orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
        customer_addresses = Address.objects.filter(user=request.user, is_active=True)
        # wishlist_count = request.user.wishlist_items.count()  # If you have wishlist model
    
    # Seller-specific data
    seller_stats = None
    seller_orders = []
    shop_address = None
    
    if is_seller:
        from items.models import Product
        from orders.models import OrderItem
        from accounts.models import SellerShopAddress
        seller = request.user.seller_profile
        
        # Seller stats
        seller_stats = {
            'total_products': seller.products.count(),
            'published': seller.products.filter(status='published').count(),
            'draft': seller.products.filter(status='draft').count(),
            'total_sales': seller.products.aggregate(total=models.Sum('sold_count'))['total'] or 0,
            'total_revenue': OrderItem.objects.filter(
                product__seller=seller,
                order__status='delivered'
            ).aggregate(total=models.Sum('total'))['total'] or 0,
            'rating': seller.rating,
            # 'rating_count': seller.rating_count if seller.rating_count else 0,
        }
        
        # Seller's recent orders
        seller_orders = OrderItem.objects.filter(
            product__seller=seller
        ).select_related('order', 'product', 'order__user').prefetch_related(
            'order__items__product'
        ).order_by('-order__created_at')[:5]
        
        # Shop address
        try:
            shop_address = seller.shop_address
        except SellerShopAddress.DoesNotExist:
            shop_address = None
    
    context = {
        'user': request.user,
        'is_customer': is_customer,
        'is_seller': is_seller,
        'is_admin': is_admin,
        # Customer data
        'user_orders': user_orders,
        'wishlist_count': wishlist_count,
        'customer_addresses': customer_addresses,  # ✅ NEW: Multiple addresses
        # Seller data
        'seller_stats': seller_stats,
        'seller_profile': request.user.seller_profile if is_seller else None,
        'seller_orders': seller_orders,
        'shop_address': shop_address,  # ✅ NEW: Shop address
    }
    return render(request, 'accounts/profile.html', context)
def redirect_by_role(user):
    if user.is_admin:
        return redirect('admin_dashboard')
    elif user.is_seller:
        return redirect('seller_dashboard')
    return redirect('shop:home')


# accounts/views.py
@login_required
@require_http_methods(["GET"])
def get_address_json(request, address_id):
    """Return address details as JSON for edit modal"""
    from accounts.models import Address
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    return JsonResponse({
        'id': address.id,
        'name': address.name,
        'phone': address.phone,
        'address_line1': address.address_line1,
        'address_line2': address.address_line2,
        'city': address.city,
        'state': address.state,
        'postal_code': address.postal_code,
        'country': address.country,
        'address_type': address.address_type,
        'is_default': address.is_default,
    })