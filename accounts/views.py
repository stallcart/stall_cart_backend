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
from orders.models import *
from .models import *
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

def register_view(request):
    """Handle user registration with role selection (customer/seller) and OTP verification"""
    
    is_ajax = request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Handle AJAX submissions
    if is_ajax:
        try:
            if request.content_type.startswith('application/json'):
                data = json.loads(request.body)
            else:
                data = request.POST
            action = data.get('action')
            
            # Action 1: Send Email OTP for registration
            if action == 'send_register_otps':
                phone = data.get('phone', '').strip()
                email = data.get('email', '').strip().lower()
                full_name = data.get('full_name', '').strip()
                password1 = data.get('password1', '')
                password2 = data.get('password2', '')
                user_role = data.get('user_role', 'customer')
                shop_name = data.get('shop_name', '').strip()
                shop_description = data.get('shop_description', '').strip()
                gst_number = data.get('gst_number', '').strip()
                pan_number = data.get('pan_number', '').strip()
                
                # Check uniqueness and validate form first
                form_data = {
                    'phone': phone,
                    'email': email,
                    'full_name': full_name,
                    'password1': password1,
                    'password2': password2,
                    'user_role': user_role,
                    'shop_name': shop_name if user_role == 'seller' else '',
                    'shop_description': shop_description if user_role == 'seller' else '',
                    'gst_number': gst_number if user_role == 'seller' else '',
                    'pan_number': pan_number if user_role == 'seller' else '',
                }
                form = UserRegistrationForm(form_data)
                if not form.is_valid():
                    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
                
                # Generate and send email OTP
                otp_email_req, err = OTPRequest.check_and_create_otp(email, 'register_email')
                if err:
                    return JsonResponse({'status': 'error', 'message': err}, status=400)
                
                # Try sending email OTP via dynamic template
                try:
                    from common.email_service import send_dynamic_email
                    send_dynamic_email('registration_email_otp', [email], {'otp': otp_email_req.otp})
                except Exception as e:
                    logger.error(f"Failed to send registration email OTP: {e}")
                
                print(f"📧 [EMAIL OTP DEMO] Sent OTP to {email} for registration: {otp_email_req.otp}")
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Verification OTP sent to email: {email}.'
                })
            
            # Action 1.5: Verify Email OTP and Send Mobile OTP
            elif action == 'verify_email_otp':
                phone = data.get('phone', '').strip()
                email = data.get('email', '').strip().lower()
                email_otp = data.get('email_otp', '').strip()
                
                if not email or not email_otp:
                    return JsonResponse({'status': 'error', 'message': 'Email address and verification code are required.'}, status=400)
                
                # Check uniqueness
                if User.objects.filter(email=email).exists():
                    return JsonResponse({'status': 'error', 'message': 'Email address already registered by another user.'}, status=400)
                if User.objects.filter(phone=phone).exists():
                    return JsonResponse({'status': 'error', 'message': 'Mobile number already registered by another user.'}, status=400)
                
                from django.utils import timezone
                # Verify Email OTP
                otp_email_req = OTPRequest.objects.filter(
                    phone=email,
                    purpose='register_email',
                    otp=email_otp,
                    is_verified=False,
                    expires_at__gt=timezone.now()
                ).first()
                
                if not otp_email_req:
                    return JsonResponse({'status': 'error', 'message': 'Invalid or expired Email OTP'}, status=400)
                
                # Mark Email OTP as verified
                otp_email_req.is_verified = True
                otp_email_req.save()
                
                # Generate and send phone OTP
                otp_phone_req, err = OTPRequest.check_and_create_otp(phone, 'register_phone')
                if err:
                    return JsonResponse({'status': 'error', 'message': err}, status=400)
                
                # Try sending phone SMS OTP via 2Factor API
                try:
                    from common.sms_service import send_sms_via_2factor
                    send_sms_via_2factor(phone, otp_phone_req.otp)
                except Exception as e:
                    logger.error(f"Failed to send registration SMS OTP: {e}")
                    
                print(f"📱 [PHONE OTP DEMO] Sent OTP to {phone} for registration: {otp_phone_req.otp}")
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Email verified successfully. Verification OTP sent to mobile: {phone}.'
                })
            
            # Action 2: Verify Phone OTP and complete registration
            elif action == 'register':
                from django.db import transaction
                with transaction.atomic():
                    if request.content_type.startswith('application/json'):
                        form = UserRegistrationForm(data)
                    else:
                        form = UserRegistrationForm(data, request.FILES)
                    if not form.is_valid():
                        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
                    
                    phone_otp = data.get('phone_otp', '').strip()
                    
                    if not phone_otp:
                        return JsonResponse({'status': 'error', 'message': 'Mobile OTP is required to verify and create account.'}, status=400)
                    
                    phone = form.cleaned_data['phone']
                    email = form.cleaned_data['email']
                    from django.utils import timezone
                    
                    # Verify Email OTP request was previously verified
                    from datetime import timedelta
                    otp_email_verified = OTPRequest.objects.filter(
                        phone=email,
                        purpose='register_email',
                        is_verified=True,
                        updated_at__gt=timezone.now() - timedelta(minutes=30)
                    ).exists()
                    
                    if not otp_email_verified:
                        return JsonResponse({'status': 'error', 'message': 'Email address must be verified first.'}, status=400)
                    
                    # Verify Phone OTP
                    otp_phone_req = OTPRequest.objects.filter(
                        phone=phone,
                        purpose='register_phone',
                        otp=phone_otp,
                        is_verified=False,
                        expires_at__gt=timezone.now()
                    ).first()
                    
                    if not otp_phone_req:
                        return JsonResponse({'status': 'error', 'message': 'Invalid or expired Mobile OTP'}, status=400)
                    
                    # Mark Phone OTP as verified
                    otp_phone_req.is_verified = True
                    otp_phone_req.save()
                    
                    # Create user
                    user = form.save(commit=False)
                    user.role = form.cleaned_data['user_role']
                    user.save()
                    
                    # If seller, create SellerProfile
                    if user.role == 'seller':
                        profile = SellerProfile.objects.create(
                            user=user,
                            shop_name=form.cleaned_data['shop_name'],
                            shop_description=form.cleaned_data.get('shop_description', ''),
                            gst_number=form.cleaned_data.get('gst_number'),
                            pan_number=form.cleaned_data.get('pan_number'),
                            pan_card_file=form.cleaned_data.get('pan_card_file'),
                            phone=user.phone,
                            is_verified=False,
                            created_by=user
                        )
                        # Notify admin of new seller pending verification via dynamic template
                        try:
                            from common.email_service import send_dynamic_email
                            from accounts.models import User as AuthUser
                            admins = AuthUser.objects.filter(role='admin', is_active=True)
                            admin_emails = [admin.email for admin in admins if admin.email]
                            if admin_emails:
                                send_dynamic_email('admin_notify_verification', admin_emails, {
                                    'shop_name': profile.shop_name,
                                    'seller_name': user.full_name or user.phone,
                                    'phone': user.phone,
                                    'email': user.email,
                                    'dashboard_url': request.build_absolute_uri('/items/admin/verify-sellers/')
                                })
                        except Exception as e:
                            logger.error(f"Failed to notify admins of new seller: {e}")

                        messages.success(request, f"🎉 Seller account created! Your shop '{form.cleaned_data['shop_name']}' is pending verification.")
                    else:
                        messages.success(request, "✅ Account created successfully! Welcome to StallCart.")
                    
                    # Auto-login
                    login(request, user)
                    
                    return JsonResponse({
                        'status': 'success', 
                        'redirect': '/'
                    })
            
            return JsonResponse({'status': 'error', 'message': 'Invalid AJAX action'}, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON request'}, status=400)
        except Exception as e:
            logger.error(f"Registration AJAX error: {e}")
            return JsonResponse({'status': 'error', 'message': 'Internal server error'}, status=500)
            
    # Handle regular form submission (Fallback, enforces AJAX/OTP verification)
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        form.add_error(None, "OTP Verification is required to create an account. Please enable JavaScript to verify.")
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('shop:home')

import logging
logger = logging.getLogger(__name__)


@login_required
def send_change_password_otp(request):
    """AJAX endpoint to send OTP for password change"""
    user = request.user
    recipient = user.phone
    if not recipient:
        return JsonResponse({'status': 'error', 'message': 'A registered mobile number is required to change password.'}, status=400)
    
    otp_req, err = OTPRequest.check_and_create_otp(recipient, 'change_password')
    if err:
        return JsonResponse({'status': 'error', 'message': err}, status=400)
    
    # Try sending phone SMS OTP via 2Factor API
    try:
        from common.sms_service import send_sms_via_2factor
        send_sms_via_2factor(recipient, otp_req.otp)
    except Exception as e:
        logger.error(f"Failed to send change password SMS OTP: {e}")
        
    print(f"📱 [PHONE OTP DEMO] Sent OTP to {recipient} for password change: {otp_req.otp}")
    
    return JsonResponse({
        'status': 'success',
        'message': f'OTP sent successfully to your registered mobile: {recipient}.'
    })


@login_required
def change_password_view(request):
    from django.contrib.auth.forms import PasswordChangeForm
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        otp_code = request.POST.get('otp')
        
        # Verify OTP
        if not otp_code:
            form.add_error(None, "Verification OTP is required.")
        else:
            # Check latest unexpired unverified OTP
            recipient = request.user.phone
            from django.utils import timezone
            otp_req = OTPRequest.objects.filter(
                phone=recipient,
                purpose='change_password',
                otp=otp_code.strip(),
                is_verified=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if not otp_req:
                form.add_error(None, "Invalid or expired OTP.")
            else:
                # Mark as verified
                otp_req.is_verified = True
                otp_req.save()
                
        if form.is_valid() and not form.errors:
            user = form.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully!")
            return redirect('accounts:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})


def forgot_password_view(request):
    """Step 1 of forgot password: submit mobile number"""
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        if not phone:
            messages.error(request, "Mobile number is required.")
            return render(request, 'accounts/forgot_password.html')
            
        user = User.objects.filter(phone=phone).first()
        if not user:
            messages.error(request, "Mobile number not registered.")
            return render(request, 'accounts/forgot_password.html')
            
        # Create OTP request on the phone number
        otp_req, err = OTPRequest.check_and_create_otp(phone, 'forgot_password')
        if err:
            messages.error(request, err)
            return render(request, 'accounts/forgot_password.html')
            
        # Send OTP via 2Factor SMS
        sms_sent = False
        try:
            from common.sms_service import send_sms_via_2factor
            sms_sent = send_sms_via_2factor(phone, otp_req.otp)
        except Exception as e:
            logger.error(f"Failed to send forgot password SMS OTP: {e}")
            
        print(f"📱 [PHONE OTP DEMO] Sent OTP to {phone} for password reset: {otp_req.otp}")
        
        # Also try sending via dynamic email if user has email
        email_sent = False
        recipient = user.email
        if recipient:
            try:
                from common.email_service import send_dynamic_email
                email_sent = send_dynamic_email('forgot_password_otp', [recipient], {'otp': otp_req.otp, 'user': user})
            except Exception as e:
                logger.error(f"Dynamic email OTP send failed: {e}")
            print(f"🔑 [EMAIL OTP DEMO] Sent OTP to {recipient} for password reset: {otp_req.otp}")

        # Save to session
        request.session['forgot_phone'] = phone
        
        if email_sent:
            messages.success(request, f"OTP sent successfully via SMS to {phone} and email to {recipient}.")
        else:
            messages.success(request, f"OTP sent successfully via SMS to {phone}.")
            
        return redirect('accounts:forgot_password_verify')
        
    return render(request, 'accounts/forgot_password.html')


def forgot_password_verify_view(request):
    """Step 2 of forgot password: submit and verify OTP"""
    phone = request.session.get('forgot_phone')
    if not phone:
        messages.error(request, "Session expired. Please enter your mobile number again.")
        return redirect('accounts:forgot_password')
        
    if request.method == 'POST':
        otp_code = request.POST.get('otp', '').strip()
        if not otp_code:
            messages.error(request, "OTP is required.")
            return render(request, 'accounts/forgot_password_verify.html', {'phone': phone})
            
        from django.utils import timezone
        otp_req = OTPRequest.objects.filter(
            phone=phone,
            purpose='forgot_password',
            otp=otp_code,
            is_verified=False,
            expires_at__gt=timezone.now()
        ).first()
        
        if not otp_req:
            messages.error(request, "Invalid or expired OTP.")
            return render(request, 'accounts/forgot_password_verify.html', {'phone': phone})
            
        # Mark as verified
        otp_req.is_verified = True
        otp_req.save()
        
        request.session['forgot_verified'] = True
        messages.success(request, "OTP verified successfully. Please choose a new password.")
        return redirect('accounts:forgot_password_reset')
        
    return render(request, 'accounts/forgot_password_verify.html', {'phone': phone})


def forgot_password_reset_view(request):
    """Step 3 of forgot password: enter new password"""
    phone = request.session.get('forgot_phone')
    verified = request.session.get('forgot_verified')
    
    if not phone or not verified:
        messages.error(request, "Session expired. Please start over.")
        return redirect('accounts:forgot_password')
        
    if request.method == 'POST':
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if not password or not confirm_password:
            messages.error(request, "Both password fields are required.")
            return render(request, 'accounts/forgot_password_reset.html')
            
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/forgot_password_reset.html')
            
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, 'accounts/forgot_password_reset.html')
            
        user = User.objects.filter(phone=phone).first()
        if not user:
            messages.error(request, "User not found.")
            return redirect('accounts:forgot_password')
            
        user.set_password(password)
        user.save()
        
        # Clear session
        request.session.pop('forgot_phone', None)
        request.session.pop('forgot_verified', None)
        
        messages.success(request, "Password reset successfully! Please login with your new password.")
        return redirect('accounts:login')
        
    return render(request, 'accounts/forgot_password_reset.html')

# accounts/views.py - Update profile_view function

# accounts/views.py
# @login_required
# def profile_view(request):
#     """User profile management - role-based sections"""
    
#     # Handle AJAX POST requests
#     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#         try:
#             data = json.loads(request.body)
#             action = data.get('action')
            
#             if action == 'update_profile':
#                 request.user.full_name = data.get('full_name', request.user.full_name)
#                 request.user.email = data.get('email', request.user.email)
#                 request.user.save()
#                 return JsonResponse({'status': 'success', 'message': 'Profile updated'})
            
#             elif action == 'add_address':
#                 if request.user.role != 'customer':
#                     return JsonResponse({'status': 'error', 'message': 'Only customers can add addresses'}, status=403)
                
#                 addr_data = data.get('address', {})
#                 is_default = data.get('is_default', False)
                
#                 from accounts.models import Address
#                 Address.objects.create(
#                     user=request.user,
#                     name=addr_data.get('name'),
#                     phone=addr_data.get('phone'),
#                     address_line1=addr_data.get('address_line1'),
#                     address_line2=addr_data.get('address_line2', ''),
#                     city=addr_data.get('city'),
#                     state=addr_data.get('state'),
#                     postal_code=addr_data.get('postal_code'),
#                     country=addr_data.get('country', 'India'),
#                     address_type=addr_data.get('address_type', 'shipping'),
#                     is_default=is_default
#                 )
#                 return JsonResponse({'status': 'success', 'message': 'Address added'})
            
#             elif action == 'update_address':
#                 if request.user.role != 'customer':
#                     return JsonResponse({'status': 'error', 'message': 'Only customers can update addresses'}, status=403)
                
#                 addr_id = data.get('address_id')
#                 addr_data = data.get('address', {})
                
#                 from accounts.models import Address
#                 address = get_object_or_404(Address, id=addr_id, user=request.user)
#                 address.name = addr_data.get('name', address.name)
#                 address.phone = addr_data.get('phone', address.phone)
#                 address.address_line1 = addr_data.get('address_line1', address.address_line1)
#                 address.address_line2 = addr_data.get('address_line2', address.address_line2)
#                 address.city = addr_data.get('city', address.city)
#                 address.state = addr_data.get('state', address.state)
#                 address.postal_code = addr_data.get('postal_code', address.postal_code)
#                 address.country = addr_data.get('country', address.country)
#                 address.address_type = addr_data.get('address_type', address.address_type)
#                 # Handle is_default separately to trigger model save logic
#                 if data.get('is_default') is not None:
#                     address.is_default = data.get('is_default')
#                 address.save()
#                 return JsonResponse({'status': 'success', 'message': 'Address updated'})
            
#             elif action == 'delete_address':
#                 if request.user.role != 'customer':
#                     return JsonResponse({'status': 'error', 'message': 'Only customers can delete addresses'}, status=403)
                
#                 addr_id = data.get('address_id')
#                 from accounts.models import Address
#                 address = get_object_or_404(Address, id=addr_id, user=request.user)
#                 address.delete()
#                 return JsonResponse({'status': 'success', 'message': 'Address deleted'})
            
#             elif action == 'set_default_address':
#                 if request.user.role != 'customer':
#                     return JsonResponse({'status': 'error', 'message': 'Only customers can set default address'}, status=403)
                
#                 addr_id = data.get('address_id')
#                 from accounts.models import Address
#                 address = get_object_or_404(Address, id=addr_id, user=request.user)
#                 address.is_default = True
#                 address.save()  # This will unset others via model save()
#                 return JsonResponse({'status': 'success', 'message': 'Default address updated'})
            
#             elif action == 'update_shop':
#                 if request.user.role != 'seller' or not hasattr(request.user, 'seller_profile'):
#                     return JsonResponse({'status': 'error', 'message': 'Only sellers can update shop details'}, status=403)
                
#                 shop_data = data.get('shop', {})
#                 seller = request.user.seller_profile
#                 seller.shop_name = shop_data.get('shop_name', seller.shop_name)
#                 seller.shop_description = shop_data.get('shop_description', seller.shop_description)
#                 seller.gst_number = shop_data.get('gst_number', seller.gst_number)
#                 seller.save()
#                 return JsonResponse({'status': 'success', 'message': 'Shop details updated'})
            
#             return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
            
#         except json.JSONDecodeError:
#             return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
#         except Exception as e:
#             return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
#     # GET request: render profile page with role-based context
#     is_customer = request.user.role == 'customer'
#     is_seller = request.user.role == 'seller' and hasattr(request.user, 'seller_profile')
#     is_admin = request.user.is_superuser
    
#     # Customer-specific data
#     user_orders = []
#     wishlist_count = 0
#     customer_addresses = []
    
#     if is_customer:
#         from orders.models import Order
#         from accounts.models import Address
#         user_orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
#         customer_addresses = Address.objects.filter(user=request.user, is_active=True)
#         # wishlist_count = request.user.wishlist_items.count()  # If you have wishlist model
    
#     # Seller-specific data
#     seller_stats = None
#     seller_orders = []
#     shop_address = None
    
#     if is_seller:
#         from items.models import Product
#         from orders.models import OrderItem
#         from accounts.models import SellerShopAddress
#         seller = request.user.seller_profile
        
#         # Seller stats
#         seller_stats = {
#             'total_products': seller.products.count(),
#             'published': seller.products.filter(status='published').count(),
#             'draft': seller.products.filter(status='draft').count(),
#             'total_sales': seller.products.aggregate(total=models.Sum('sold_count'))['total'] or 0,
#             'total_revenue': OrderItem.objects.filter(
#                 product__seller=seller,
#                 order__status='delivered'
#             ).aggregate(total=models.Sum('total'))['total'] or 0,
#             'rating': seller.rating,
#             # 'rating_count': seller.rating_count if seller.rating_count else 0,
#         }
        
#         # Seller's recent orders
#         seller_orders = OrderItem.objects.filter(
#             product__seller=seller
#         ).select_related('order', 'product', 'order__user').prefetch_related(
#             'order__items__product'
#         ).order_by('-order__created_at')[:5]
        
#         # Shop address
#         try:
#             shop_address = seller.shop_address
#         except SellerShopAddress.DoesNotExist:
#             shop_address = None
    
#     context = {
#         'user': request.user,
#         'is_customer': is_customer,
#         'is_seller': is_seller,
#         'is_admin': is_admin,
#         # Customer data
#         'user_orders': user_orders,
#         'wishlist_count': wishlist_count,
#         'customer_addresses': customer_addresses,  # ✅ NEW: Multiple addresses
#         # Seller data
#         'seller_stats': seller_stats,
#         'seller_profile': request.user.seller_profile if is_seller else None,
#         'seller_orders': seller_orders,
#         'shop_address': shop_address,  # ✅ NEW: Shop address
#     }
#     return render(request, 'accounts/profile.html', context)



# @login_required
# def profile_view(request):
#     """User profile management - role-based sections with AJAX support"""
    
#     # Handle AJAX POST requests
#     if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#         try:
#             data = json.loads(request.body)
#             action = data.get('action')
            
#             # ===== UPDATE PERSONAL PROFILE =====
#             if action == 'update_profile':
#                 request.user.full_name = data.get('full_name', request.user.full_name)
#                 request.user.email = data.get('email', request.user.email)
#                 request.user.save()
#                 return JsonResponse({'status': 'success', 'message': 'Profile updated'})
            
#             # ===== ADDRESS MANAGEMENT (Customers Only) =====
#             elif action in ['add_address', 'update_address']:
#                 if request.user.role != 'customer':
#                     return JsonResponse(
#                         {'status': 'error', 'message': 'Only customers can manage addresses'}, 
#                         status=403
#                     )
                
#                 # Extract address fields (flat format for simplicity)
#                 addr_data = {
#                     'name': data.get('name'),
#                     'phone': data.get('phone'),
#                     'address_line1': data.get('address_line1'),
#                     'address_line2': data.get('address_line2', ''),
#                     'city': data.get('city'),
#                     'state': data.get('state'),
#                     'postal_code': data.get('postal_code'),
#                     'country': data.get('country', 'India'),
#                     'address_type': data.get('address_type', 'shipping'),
#                     'is_default': data.get('is_default', False),
#                 }
                
#                 # Validate required fields
#                 required = ['name', 'phone', 'address_line1', 'city', 'state', 'postal_code']
#                 missing = [f for f in required if not addr_data.get(f)]
#                 if missing:
#                     return JsonResponse({
#                         'status': 'error', 
#                         'message': f'Missing required fields: {", ".join(missing)}'
#                     }, status=400)
                
#                 if action == 'add_address':
#                     Address.objects.create(user=request.user, **addr_data)
#                     return JsonResponse({'status': 'success', 'message': 'Address added'})
                
#                 elif action == 'update_address':
#                     addr_id = data.get('address_id')
#                     if not addr_id:
#                         return JsonResponse(
#                             {'status': 'error', 'message': 'Address ID required'}, 
#                             status=400
#                         )
                    
#                     address = get_object_or_404(Address, id=addr_id, user=request.user)
#                     for key, value in addr_data.items():
#                         setattr(address, key, value)
#                     address.save()  # Triggers model's save() logic for is_default
#                     return JsonResponse({'status': 'success', 'message': 'Address updated'})
            
#             # ===== DELETE ADDRESS =====
#             elif action == 'delete_address':
#                 if request.user.role != 'customer':
#                     return JsonResponse(
#                         {'status': 'error', 'message': 'Only customers can delete addresses'}, 
#                         status=403
#                     )
                
#                 addr_id = data.get('address_id')
#                 address = get_object_or_404(Address, id=addr_id, user=request.user)
#                 address.delete()
#                 return JsonResponse({'status': 'success', 'message': 'Address deleted'})
            
#             # ===== SET DEFAULT ADDRESS =====
#             elif action == 'set_default_address':
#                 if request.user.role != 'customer':
#                     return JsonResponse(
#                         {'status': 'error', 'message': 'Only customers can set default address'}, 
#                         status=403
#                     )
                
#                 addr_id = data.get('address_id')
#                 address = get_object_or_404(Address, id=addr_id, user=request.user)
#                 address.is_default = True
#                 address.save()  # Model's save() will unset others
#                 return JsonResponse({'status': 'success', 'message': 'Default address updated'})
            
#             # ===== UPDATE SHOP ADDRESS (Sellers Only) =====
#             elif action == 'update_shop_address':
#                 if request.user.role != 'seller' or not hasattr(request.user, 'seller_profile'):
#                     return JsonResponse(
#                         {'status': 'error', 'message': 'Only sellers can update shop details'}, 
#                         status=403
#                     )
                
#                 shop_data = data.get('shop_address', {})
#                 seller = request.user.seller_profile
                
#                 # Get or create shop address
#                 shop_address, created = SellerShopAddress.objects.get_or_create(
#                     seller=seller,
#                     defaults={
#                         'shop_name': shop_data.get('shop_name'),
#                         'shop_phone': shop_data.get('shop_phone'),
#                         'shop_email': shop_data.get('shop_email', seller.user.email),
#                         'address_line1': shop_data.get('address_line1'),
#                         'address_line2': shop_data.get('address_line2', ''),
#                         'city': shop_data.get('city'),
#                         'state': shop_data.get('state'),
#                         'postal_code': shop_data.get('postal_code'),
#                         'country': shop_data.get('country', 'India'),
#                         'gst_number': shop_data.get('gst_number', ''),
#                         'pickup_instructions': shop_data.get('pickup_instructions', ''),
#                     }
#                 )
                
#                 if not created:
#                     # Update existing
#                     for key, value in shop_data.items():
#                         if hasattr(shop_address, key):
#                             setattr(shop_address, key, value)
#                     shop_address.save()
                
#                 return JsonResponse({'status': 'success', 'message': 'Shop address saved'})
            
#             # ===== INVALID ACTION =====
#             return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
            
#         except json.JSONDecodeError:
#             return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
#         except Exception as e:
#             import traceback
#             traceback.print_exc()  # Log to console/server logs
#             return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
#     # ===== GET REQUEST: Render Profile Page =====
#     is_customer = request.user.role == 'customer'
#     is_seller = request.user.role == 'seller' and hasattr(request.user, 'seller_profile')
#     is_admin = request.user.is_superuser
    
#     # Customer-specific data
#     user_orders = []
#     wishlist_count = 0
#     customer_addresses = []
    
#     if is_customer:
#         user_orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
#         customer_addresses = Address.objects.filter(user=request.user, is_active=True)
#         # wishlist_count = request.user.wishlist_items.count()  # Uncomment if you have wishlist
    
#     # Seller-specific data
#     seller_stats = None
#     seller_orders = []
#     shop_address = None
    
#     if is_seller:
#         seller = request.user.seller_profile
#         order_ids = set(
#             OrderItem.objects.filter(product__seller=seller)
#             .values_list('order_id', flat=True)
#         )
#         total_orders_count = len(order_ids)
#         # Seller stats
#         seller_stats = {
#             'total_products': seller.products.count(),
#             'published': seller.products.filter(status='published').count(),
#             'draft': seller.products.filter(status='draft').count(),
#             'total_sales': seller.products.aggregate(total=Sum('sold_count'))['total'] or 0,
#             'total_revenue': OrderItem.objects.filter(
#                 product__seller=seller,
#                 order__status='delivered'
#             ).aggregate(total=Sum('total'))['total'] or 0,
#             # 'total_orders': OrderItem.objects.filter(
#             #     product__seller=seller
#             # ).select_related('order').distinct('order').count(),
#             'total_orders': total_orders_count,  # ✅ Fixed: SQLite compatible

#         }

        
#         # Seller's recent orders
#         seller_orders = OrderItem.objects.filter(
#             product__seller=seller
#         ).select_related('order', 'product', 'order__user').prefetch_related(
#             'order__items__product'
#         ).order_by('-order__created_at')[:5]
        
#         # Shop address
#         try:
#             shop_address = seller.shop_address
#         except SellerShopAddress.DoesNotExist:
#             shop_address = None
    
#     context = {
#         'user': request.user,
#         'is_customer': is_customer,
#         'is_seller': is_seller,
#         'is_admin': is_admin,
#         # Customer data
#         'user_orders': user_orders,
#         'wishlist_count': wishlist_count,
#         'customer_addresses': customer_addresses,
#         # Seller data
#         'seller_stats': seller_stats,
#         'seller_profile': request.user.seller_profile if is_seller else None,
#         'seller_orders': seller_orders,
#         'shop_address': shop_address,
#     }
#     return render(request, 'accounts/profile.html', context)

@login_required
def profile_view(request):
    """User profile management - role-based sections with AJAX support"""
    
    # ✅ Compatible AJAX detection for all Django versions
    is_ajax = request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
    
    if is_ajax:
        try:
            if request.content_type.startswith('application/json'):
                data = json.loads(request.body)
            else:
                data = request.POST
            action = data.get('action')
            
            # ===== SEND OTPs FOR PROFILE UPDATE =====
            if action == 'send_profile_update_otps':
                new_email = data.get('email', '').strip().lower()
                new_phone = data.get('phone', '').strip()
                
                email_changed = (new_email and new_email != request.user.email)
                phone_changed = (new_phone and new_phone != request.user.phone)
                
                if not email_changed and not phone_changed:
                    return JsonResponse({'status': 'error', 'message': 'No changes detected'}, status=400)
                    
                email_sent = False
                phone_sent = False
                
                email_otp_req = None
                phone_otp_req = None
                
                # Check email duplicate & send OTP
                if email_changed:
                    if not new_email or '@' not in new_email or '.' not in new_email.split('@')[-1]:
                        return JsonResponse({'status': 'error', 'message': 'Invalid email format'}, status=400)
                    if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
                        return JsonResponse({'status': 'error', 'message': 'Email address already registered by another user'}, status=400)
                    
                    email_otp_req, err = OTPRequest.check_and_create_otp(new_email, 'update_email')
                    if err:
                        return JsonResponse({'status': 'error', 'message': err}, status=400)
                        
                    # Try sending via email (dynamic template)
                    from common.email_service import send_dynamic_email
                    send_dynamic_email('update_email_otp', [new_email], {'otp': email_otp_req.otp})
                    print(f"📧 [EMAIL OTP DEMO] Sent OTP to {new_email} for email change: {email_otp_req.otp}")
                    email_sent = True
                    
                # Check phone duplicate & send OTP
                if phone_changed:
                    if not new_phone or not new_phone.isdigit() or len(new_phone) != 10:
                        return JsonResponse({'status': 'error', 'message': 'Invalid phone number format. Must be 10 digits.'}, status=400)
                    if User.objects.filter(phone=new_phone).exclude(pk=request.user.pk).exists():
                        return JsonResponse({'status': 'error', 'message': 'Mobile number already registered by another user'}, status=400)
                        
                    phone_otp_req, err = OTPRequest.check_and_create_otp(new_phone, 'update_phone')
                    if err:
                        return JsonResponse({'status': 'error', 'message': err}, status=400)
                        
                    # Send via FCM
                    try:
                        from common.notification_service import send_to_user, NotificationPayload
                        payload = NotificationPayload(
                            title="🔑 Mobile Update OTP",
                            body=f"Your OTP to update your mobile number is {phone_otp_req.otp}. Valid for 10 minutes.",
                            tag="update-phone-otp"
                        )
                        send_to_user(request.user, payload)
                    except Exception as e:
                        logger.error(f"FCM OTP send failed: {e}")
                        
                    # Send via SMS (2Factor API)
                    try:
                        from common.sms_service import send_sms_via_2factor
                        send_sms_via_2factor(new_phone, phone_otp_req.otp)
                    except Exception as e:
                        logger.error(f"Failed to send update mobile SMS OTP: {e}")
                        
                    print(f"📱 [PHONE OTP DEMO] Sent OTP to {new_phone} for phone change: {phone_otp_req.otp}")
                    phone_sent = True
                    
                # Generate user-friendly success message
                msg_parts = []
                if email_sent:
                    msg_parts.append(f"OTP sent to new email: {new_email}")
                if phone_sent:
                    msg_parts.append(f"OTP sent to new mobile: {new_phone}")
                
                return JsonResponse({
                    'status': 'success',
                    'message': " & ".join(msg_parts) + ".",
                    'email_sent': email_sent,
                    'phone_sent': phone_sent
                })

            # ===== UPDATE PERSONAL PROFILE =====
            elif action == 'update_profile':
                # Always initialize variables FIRST to avoid UnboundLocalError
                new_full_name = request.user.full_name
                new_email = request.user.email
                new_phone = request.user.phone
                
                # Safely extract from request data
                if 'full_name' in data and data['full_name'] is not None:
                    new_full_name = str(data['full_name']).strip()
                if 'email' in data and data['email'] is not None:
                    new_email = str(data['email']).strip().lower()
                if 'phone' in data and data['phone'] is not None:
                    new_phone = str(data['phone']).strip()
                
                email_changed = (new_email != request.user.email)
                phone_changed = (new_phone != request.user.phone)
                
                from django.utils import timezone
                
                # Verify Email OTP
                if email_changed:
                    if not new_email or '@' not in new_email or '.' not in new_email.split('@')[-1]:
                        return JsonResponse({'status': 'error', 'message': 'Invalid email format'}, status=400)
                    if User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists():
                        return JsonResponse({'status': 'error', 'message': 'Email address already registered by another user'}, status=400)
                        
                    email_otp = data.get('email_otp')
                    if not email_otp:
                        return JsonResponse({'status': 'error', 'message': 'Email OTP is required to verify changes'}, status=400)
                        
                    otp_req = OTPRequest.objects.filter(
                        phone=new_email,
                        purpose='update_email',
                        otp=email_otp.strip(),
                        is_verified=False,
                        expires_at__gt=timezone.now()
                    ).first()
                    
                    if not otp_req:
                        return JsonResponse({'status': 'error', 'message': 'Invalid or expired Email OTP'}, status=400)
                    
                    otp_req.is_verified = True
                    otp_req.save()
                    
                # Verify Phone OTP
                if phone_changed:
                    if not new_phone or not new_phone.isdigit() or len(new_phone) != 10:
                        return JsonResponse({'status': 'error', 'message': 'Invalid phone number format'}, status=400)
                    if User.objects.filter(phone=new_phone).exclude(pk=request.user.pk).exists():
                        return JsonResponse({'status': 'error', 'message': 'Mobile number already registered by another user'}, status=400)
                        
                    phone_otp = data.get('phone_otp')
                    if not phone_otp:
                        return JsonResponse({'status': 'error', 'message': 'Mobile OTP is required to verify changes'}, status=400)
                        
                    otp_req = OTPRequest.objects.filter(
                        phone=new_phone,
                        purpose='update_phone',
                        otp=phone_otp.strip(),
                        is_verified=False,
                        expires_at__gt=timezone.now()
                    ).first()
                    
                    if not otp_req:
                        return JsonResponse({'status': 'error', 'message': 'Invalid or expired Mobile OTP'}, status=400)
                    
                    otp_req.is_verified = True
                    otp_req.save()
                
                # Update and save User profile
                request.user.full_name = new_full_name
                request.user.email = new_email
                request.user.phone = new_phone
                request.user.save(update_fields=['full_name', 'email', 'phone', 'updated_at'])
                
                # If role is seller, also update SellerProfile
                if request.user.role == 'seller' and hasattr(request.user, 'seller_profile'):
                    sp = request.user.seller_profile
                    sp.phone = new_phone
                    sp.save(update_fields=['phone', 'updated_at'])
                
                return JsonResponse({
                    'status': 'success', 
                    'message': 'Profile updated successfully!',
                    'email': request.user.email,
                    'phone': request.user.phone,
                    'full_name': request.user.full_name
                })
            
            # ===== ADDRESS MANAGEMENT (Customers Only) =====
            elif action in ['add_address', 'update_address']:
                if request.user.role != 'customer':
                    return JsonResponse({'status': 'error', 'message': 'Only customers can manage addresses'}, status=403)
                
                addr_data = {
                    'name': data.get('name'),
                    'phone': data.get('phone'),
                    'address_line1': data.get('address_line1'),
                    'address_line2': data.get('address_line2', ''),
                    'city': data.get('city'),
                    'state': data.get('state'),
                    'postal_code': data.get('postal_code'),
                    'country': data.get('country', 'India'),
                    'address_type': data.get('address_type', 'shipping'),
                    'is_default': data.get('is_default', False),
                }
                
                required = ['name', 'phone', 'address_line1', 'city', 'state', 'postal_code']
                missing = [f for f in required if not addr_data.get(f)]
                if missing:
                    return JsonResponse({'status': 'error', 'message': f'Missing: {", ".join(missing)}'}, status=400)
                
                if action == 'add_address':
                    Address.objects.create(user=request.user, **addr_data)
                    return JsonResponse({'status': 'success', 'message': 'Address added'})
                
                elif action == 'update_address':
                    addr_id = data.get('address_id')
                    if not addr_id:
                        return JsonResponse({'status': 'error', 'message': 'Address ID required'}, status=400)
                    address = get_object_or_404(Address, id=addr_id, user=request.user)
                    for key, value in addr_data.items():
                        setattr(address, key, value)
                    address.save()
                    return JsonResponse({'status': 'success', 'message': 'Address updated'})
            
            # ===== DELETE ADDRESS =====
            elif action == 'delete_address':
                if request.user.role != 'customer':
                    return JsonResponse({'status': 'error', 'message': 'Only customers can delete addresses'}, status=403)
                addr_id = data.get('address_id')
                address = get_object_or_404(Address, id=addr_id, user=request.user)
                address.delete()
                return JsonResponse({'status': 'success', 'message': 'Address deleted'})
            
            # ===== SET DEFAULT ADDRESS =====
            elif action == 'set_default_address':
                if request.user.role != 'customer':
                    return JsonResponse({'status': 'error', 'message': 'Only customers can set default'}, status=403)
                addr_id = data.get('address_id')
                address = get_object_or_404(Address, id=addr_id, user=request.user)
                address.is_default = True
                address.save()
                return JsonResponse({'status': 'success', 'message': 'Default updated'})
            
            # ===== UPDATE SHOP ADDRESS (Sellers Only) =====
            elif action == 'update_shop_address':
                if request.user.role != 'seller' or not hasattr(request.user, 'seller_profile'):
                    return JsonResponse({'status': 'error', 'message': 'Only sellers can update shop'}, status=403)
                
                shop_data = data.get('shop_address', {})
                seller = request.user.seller_profile
                
                shop_address, created = SellerShopAddress.objects.get_or_create(
                    seller=seller,
                    defaults={
                        'shop_name': shop_data.get('shop_name'),
                        'shop_phone': shop_data.get('shop_phone'),
                        'shop_email': shop_data.get('shop_email', seller.user.email),
                        'address_line1': shop_data.get('address_line1'),
                        'address_line2': shop_data.get('address_line2', ''),
                        'city': shop_data.get('city'),
                        'state': shop_data.get('state'),
                        'postal_code': shop_data.get('postal_code'),
                        'country': shop_data.get('country', 'India'),
                        'gst_number': shop_data.get('gst_number', ''),
                        'pickup_instructions': shop_data.get('pickup_instructions', ''),
                    }
                )
                
                if not created:
                    for key, value in shop_data.items():
                        if hasattr(shop_address, key):
                            setattr(shop_address, key, value)
                    shop_address.save()
                
                return JsonResponse({'status': 'success', 'message': 'Shop address saved'})
            
            # ===== UPDATE BANK DETAILS (Sellers Only) =====
            elif action == 'update_bank_details':
                if request.user.role != 'seller' or not hasattr(request.user, 'seller_profile'):
                    return JsonResponse({'status': 'error', 'message': 'Only sellers can update bank details'}, status=403)
                
                bank_name = data.get('bank_name', '').strip()
                account_number = data.get('account_number', '').strip()
                ifsc_code = data.get('ifsc_code', '').strip()
                account_holder_name = data.get('account_holder_name', '').strip()
                
                if not bank_name or not account_number or not ifsc_code or not account_holder_name:
                    return JsonResponse({'status': 'error', 'message': 'All bank details fields are required'}, status=400)
                
                seller = request.user.seller_profile
                
                # Check if critical bank details have changed
                details_changed = (
                    seller.account_number != account_number or
                    seller.ifsc_code != ifsc_code or
                    seller.account_holder_name != account_holder_name
                )
                
                seller.bank_name = bank_name
                seller.account_number = account_number
                seller.ifsc_code = ifsc_code
                seller.account_holder_name = account_holder_name
                
                update_fields = ['bank_name', 'account_number', 'ifsc_code', 'account_holder_name', 'updated_at']
                if details_changed:
                    # Clear cached RazorpayX fund account so it regenerates on the next payout
                    seller.razorpay_fund_account_id = None
                    update_fields.append('razorpay_fund_account_id')
                
                seller.save(update_fields=update_fields)
                
                return JsonResponse({'status': 'success', 'message': 'Bank details updated successfully!'})
            
            # ===== UPDATE PAN DETAILS (Sellers Only) =====
            elif action == 'update_pan_details':
                if request.user.role != 'seller' or not hasattr(request.user, 'seller_profile'):
                    return JsonResponse({'status': 'error', 'message': 'Only sellers can update PAN details'}, status=403)
                
                pan_number = data.get('pan_number', '').strip().upper()
                pan_card_file = request.FILES.get('pan_card_file')
                
                if not pan_number:
                    return JsonResponse({'status': 'error', 'message': 'PAN number is required.'}, status=400)
                
                import re
                if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan_number):
                    return JsonResponse({'status': 'error', 'message': 'Invalid PAN number format. Format must be e.g. ABCDE1234F'}, status=400)
                
                seller = request.user.seller_profile
                if SellerProfile.objects.filter(pan_number=pan_number).exclude(pk=seller.pk).exists():
                    return JsonResponse({'status': 'error', 'message': 'This PAN number is already registered by another seller.'}, status=400)
                
                seller.pan_number = pan_number
                if pan_card_file:
                    seller.pan_card_file = pan_card_file
                seller.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'PAN details updated successfully and submitted for verification.',
                    'pan_number': seller.pan_number,
                    'pan_verification_status': seller.pan_verification_status,
                    'is_verified': seller.is_verified,
                })
            
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            import logging, traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Profile AJAX error: {str(e)}\n{traceback.format_exc()}")
            return JsonResponse({'status': 'error', 'message': 'Server error'}, status=500)
    
    # ===== GET REQUEST: Render Profile Page =====
    # ... (rest of your GET logic remains unchanged) ...
    is_customer = request.user.role == 'customer'
    
    # Auto-heal: Create a default SellerProfile if it was missed during registration (e.g. database migration delay)
    if request.user.role == 'seller' and not hasattr(request.user, 'seller_profile'):
        try:
            SellerProfile.objects.create(
                user=request.user,
                shop_name=f"Shop_{request.user.phone}",
                phone=request.user.phone,
                is_verified=False,
                created_by=request.user
            )
        except Exception as e:
            logger.error(f"Failed to auto-heal/create SellerProfile in profile view: {e}")

    is_seller = request.user.role == 'seller' and hasattr(request.user, 'seller_profile')
    is_admin = request.user.is_admin
    
    user_orders = []
    wishlist_count = 0
    customer_addresses = []
    wallet = None
    wallet_transactions = []
    
    if is_customer:
        user_orders = Order.objects.filter(user=request.user).order_by('-created_at')[:5]
        customer_addresses = Address.objects.filter(user=request.user, is_active=True)
        from accounts.models import Wallet
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        wallet_transactions = wallet.transactions.all()[:10]
    
    seller_stats = None
    seller_orders = []
    shop_address = None
    
    if is_seller:
        seller = request.user.seller_profile
        order_ids = set(OrderItem.objects.filter(product__seller=seller).values_list('order_id', flat=True))
        seller_stats = {
            'total_products': seller.products.count(),
            'published': seller.products.filter(status='published').count(),
            'draft': seller.products.filter(status='draft').count(),
            'total_sales': seller.products.aggregate(total=Sum('sold_count'))['total'] or 0,
            'total_revenue': OrderItem.objects.filter(product__seller=seller, order__status='delivered').aggregate(total=Sum('total'))['total'] or 0,
            'total_orders': len(order_ids),
        }
        seller_orders = OrderItem.objects.filter(product__seller=seller).select_related('order', 'product', 'order__user').prefetch_related('order__items__product').order_by('-order__created_at')[:5]
        try:
            shop_address = seller.shop_address
        except SellerShopAddress.DoesNotExist:
            shop_address = None
            
        from orders.models import SellerSettlement
        seller_settlements = SellerSettlement.objects.filter(seller=seller).order_by('-created_at')
    
    context = {
        'user': request.user, 'is_customer': is_customer, 'is_seller': is_seller, 'is_admin': is_admin,
        'user_orders': user_orders, 'wishlist_count': wishlist_count, 'customer_addresses': customer_addresses,
        'seller_stats': seller_stats, 'seller_profile': request.user.seller_profile if is_seller else None,
        'seller_orders': seller_orders, 'shop_address': shop_address,
        'wallet': wallet, 'wallet_transactions': wallet_transactions,
        'seller_settlements': seller_settlements if is_seller else None,
    }
    return render(request, 'accounts/profile.html', context)
def redirect_by_role(user):
    if user.is_admin:
        return redirect('items:admin_dashboard')
    elif user.is_seller:
        return redirect('items:seller_dashboard')
    return redirect('shop:home')


# accounts/views.py
@login_required
@require_http_methods(["GET"])
def api_address_detail(request, address_id):
    """Return address details as JSON for edit modal"""
    try:

        address = get_object_or_404(Address, id=address_id, user=request.user)
        print('address',address)
        return JsonResponse({
            'status': 'success',  # ✅ ADD THIS
            'address': {          # ✅ WRAP ADDRESS DATA IN 'address' KEY
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
                'full_address': f"{address.address_line1}{', ' + address.address_line2 if address.address_line2 else ''}, {address.city}, {address.state} – {address.postal_code}, {address.country}"
            }
        })
    except Address.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Address not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def latest_otp_view(request):
    """Temporary helper view for developers/users to grab OTPs during demo/testing."""
    from .models import OTPRequest
    from django.utils import timezone
    
    # Fetch 10 latest active/unexpired OTP requests
    otps = OTPRequest.objects.filter(
        is_verified=False,
        expires_at__gt=timezone.now()
    )[:10]
    
    return render(request, 'accounts/latest_otp.html', {'otps': otps})


@login_required
def admin_user_management(request):
    # Enforce admin permission: only superusers or users with the 'admin' role
    if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
        messages.error(request, "🔐 Access Denied: Only administrators can manage users.")
        return redirect('shop:home')

    is_ajax = request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if is_ajax and request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'get_user':
                user_id = data.get('user_id')
                user = get_object_or_404(User, id=user_id)
                user_data = {
                    'id': user.id,
                    'full_name': user.full_name,
                    'phone': user.phone,
                    'email': user.email or '',
                    'role': user.role,
                    'is_active': user.is_active,
                }
                if user.role == 'seller' and hasattr(user, 'seller_profile'):
                    sp = user.seller_profile
                    user_data.update({
                        'shop_name': sp.shop_name,
                        'gst_number': sp.gst_number or '',
                        'is_verified': sp.is_verified,
                    })
                return JsonResponse({'status': 'success', 'user': user_data})
                
            elif action == 'create_staff':
                full_name = data.get('full_name', '').strip()
                phone = data.get('phone', '').strip()
                email = data.get('email', '').strip().lower()
                password = data.get('password', '')
                
                if not full_name or not phone or not password:
                    return JsonResponse({'status': 'error', 'message': 'Full Name, Phone Number, and Password are required.'}, status=400)
                
                if not phone.isdigit() or len(phone) != 10:
                    return JsonResponse({'status': 'error', 'message': 'Phone number must be a 10-digit number.'}, status=400)
                
                if User.objects.filter(phone=phone).exists():
                    return JsonResponse({'status': 'error', 'message': 'Mobile number already registered.'}, status=400)
                
                if email and User.objects.filter(email__iexact=email).exists():
                    return JsonResponse({'status': 'error', 'message': 'Email address already registered.'}, status=400)
                
                user = User.objects.create_user(
                    phone=phone,
                    email=email or None,
                    password=password,
                    role='staff',
                    full_name=full_name
                )
                return JsonResponse({'status': 'success', 'message': f'Staff member "{full_name}" created successfully!'})
                
            elif action == 'update_user':
                user_id = data.get('user_id')
                user = get_object_or_404(User, id=user_id)
                
                full_name = data.get('full_name', '').strip()
                phone = data.get('phone', '').strip()
                email = data.get('email', '').strip().lower()
                password = data.get('password', '')
                
                if not full_name or not phone:
                    return JsonResponse({'status': 'error', 'message': 'Full Name and Phone Number are required.'}, status=400)
                
                if not phone.isdigit() or len(phone) != 10:
                    return JsonResponse({'status': 'error', 'message': 'Phone number must be a 10-digit number.'}, status=400)
                
                if User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
                    return JsonResponse({'status': 'error', 'message': 'Mobile number already registered by another user.'}, status=400)
                
                if email and User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    return JsonResponse({'status': 'error', 'message': 'Email address already registered by another user.'}, status=400)
                
                user.full_name = full_name
                user.phone = phone
                user.email = email or None
                
                if password:
                    user.set_password(password)
                    
                user.save()
                
                if user.role == 'seller':
                    shop_name = data.get('shop_name', '').strip()
                    gst_number = data.get('gst_number', '').strip() or None
                    is_verified = bool(data.get('is_verified', False))
                    
                    if not shop_name:
                        return JsonResponse({'status': 'error', 'message': 'Shop Name is required for sellers.'}, status=400)
                    
                    if SellerProfile.objects.filter(shop_name__iexact=shop_name).exclude(user=user).exists():
                        return JsonResponse({'status': 'error', 'message': 'Shop Name is already taken.'}, status=400)
                    
                    sp, created = SellerProfile.objects.get_or_create(
                        user=user,
                        defaults={
                            'shop_name': shop_name,
                            'gst_number': gst_number,
                            'is_verified': is_verified,
                            'phone': phone
                        }
                    )
                    if not created:
                        sp.shop_name = shop_name
                        sp.gst_number = gst_number
                        sp.is_verified = is_verified
                        sp.phone = phone
                        sp.save()
                        
                return JsonResponse({'status': 'success', 'message': 'Account updated successfully!'})
                
            elif action == 'delete_user':
                user_id = data.get('user_id')
                if int(user_id) == request.user.id:
                    return JsonResponse({'status': 'error', 'message': 'You cannot delete your own admin account.'}, status=400)
                
                user = get_object_or_404(User, id=user_id)
                name = user.full_name or user.phone
                user.delete()
                return JsonResponse({'status': 'success', 'message': f'User "{name}" has been deleted.'})
                
            elif action == 'toggle_active':
                user_id = data.get('user_id')
                if int(user_id) == request.user.id:
                    return JsonResponse({'status': 'error', 'message': 'You cannot deactivate your own admin account.'}, status=400)
                
                user = get_object_or_404(User, id=user_id)
                user.is_active = not user.is_active
                user.save()
                status_str = "activated" if user.is_active else "deactivated"
                return JsonResponse({'status': 'success', 'message': f'Account "{user.full_name or user.phone}" has been {status_str}.'})
                
            return JsonResponse({'status': 'error', 'message': 'Invalid action.'}, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data.'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    # For standard GET requests, render user management view with search / filters
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('is_active', '').strip()
    
    # Querysets for staff, sellers, customers
    staff_qs = User.objects.filter(role='staff')
    seller_qs = User.objects.filter(role='seller').select_related('seller_profile')
    customer_qs = User.objects.filter(role='customer')
    
    # Apply search filter
    if search_query:
        q_filter = Q(full_name__icontains=search_query) | Q(phone__icontains=search_query) | Q(email__icontains=search_query)
        staff_qs = staff_qs.filter(q_filter)
        seller_qs = seller_qs.filter(q_filter | Q(seller_profile__shop_name__icontains=search_query))
        customer_qs = customer_qs.filter(q_filter)
        
    # Apply status filter
    if status_filter:
        is_active_val = status_filter == 'true'
        staff_qs = staff_qs.filter(is_active=is_active_val)
        seller_qs = seller_qs.filter(is_active=is_active_val)
        customer_qs = customer_qs.filter(is_active=is_active_val)
        
    context = {
        'staff_list': staff_qs.order_by('-created_at'),
        'seller_list': seller_qs.order_by('-created_at'),
        'customer_list': customer_qs.order_by('-created_at'),
        'search_query': search_query,
        'status_filter': status_filter,
    }
    return render(request, 'accounts/admin_user_management.html', context)


@login_required
def admin_business_dashboard(request):
    if not request.user.is_superuser and getattr(request.user, 'role', None) != 'admin':
        messages.error(request, "🔐 Access Denied: Admin privileges required.")
        return redirect('shop:home')

    # Fetch models
    from decimal import Decimal
    from django.db.models import Sum, Count, Q
    from django.utils import timezone
    from datetime import timedelta
    from orders.models import Order, OrderItem
    from accounts.models import User, OTPRequest
    from common.models import SiteSettings, EmailTemplate

    # 1. Financial / Revenue Stats
    total_sales = Order.objects.filter(status='delivered').aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    pending_sales = Order.objects.exclude(status__in=['delivered', 'cancelled', 'returned']).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    total_orders_count = Order.objects.count()
    
    # Order Status Breakdown
    order_statuses = Order.objects.values('status').annotate(count=Count('id')).order_by('-count')
    status_data = {item['status']: item['count'] for item in order_statuses}
    
    # 2. Users Stats
    total_customers = User.objects.filter(role='customer').count()
    active_customers = User.objects.filter(role='customer', is_active=True).count()
    
    total_sellers = User.objects.filter(role='seller').count()
    active_sellers = User.objects.filter(role='seller', is_active=True).count()
    pending_sellers = User.objects.filter(role='seller', seller_profile__is_verified=False).count()
    
    total_staff = User.objects.filter(role='staff').count()
    active_staff = User.objects.filter(role='staff', is_active=True).count()

    # 3. OTP Stats
    total_otps = OTPRequest.objects.count()
    verified_otps = OTPRequest.objects.filter(is_verified=True).count()
    otp_success_rate = (verified_otps / total_otps * 100) if total_otps > 0 else 0.0

    # 4. Email Templates
    total_email_templates = EmailTemplate.objects.count()
    email_templates = EmailTemplate.objects.all().order_by('name')

    # 5. Site Settings Singleton
    site_settings = SiteSettings.get_singleton()

    # 6. Recent Orders for Quick Management
    recent_orders = Order.objects.all().order_by('-created_at')[:5]

    # 7. Recent OTP Requests for Developers/Admins
    recent_otps = OTPRequest.objects.all().order_by('-created_at')[:8]

    # 8. Business Trends (Last 7 Days Sales)
    today = timezone.now().date()
    
    daily_sales = []
    # Loop over last 7 days
    for i in range(7):
        day = today - timedelta(days=i)
        day_start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        day_end = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.max.time()))
        sales_sum = Order.objects.filter(
            created_at__range=(day_start, day_end),
            status='delivered'
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        daily_sales.append({
            'date': day.strftime('%b %d'),
            'amount': float(sales_sum)
        })
    daily_sales.reverse()

    context = {
        'total_sales': total_sales,
        'pending_sales': pending_sales,
        'total_orders_count': total_orders_count,
        'status_data': status_data,
        
        'total_customers': total_customers,
        'active_customers': active_customers,
        'total_sellers': total_sellers,
        'active_sellers': active_sellers,
        'pending_sellers': pending_sellers,
        'total_staff': total_staff,
        'active_staff': active_staff,
        
        'total_otps': total_otps,
        'verified_otps': verified_otps,
        'otp_success_rate': otp_success_rate,
        
        'total_email_templates': total_email_templates,
        'email_templates': email_templates,
        
        'site_settings': site_settings,
        'recent_orders': recent_orders,
        'recent_otps': recent_otps,
        'daily_sales': daily_sales,
    }
    return render(request, 'accounts/admin_business_dashboard.html', context)