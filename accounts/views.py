from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from .forms import UserRegistrationForm, UserLoginForm
import json
from items.models import SellerProfile
def login_view(request):
    if request.user.is_authenticated:
        return redirect('shop:home')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)  # ✅ FIXED
        
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'redirect': request.POST.get('next', '/')
                })
            
            return redirect(request.POST.get('next', 'shop:home'))
        
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

# accounts/views.py
@login_required
def profile_view(request):
    """User profile management - handles both page render and AJAX updates"""
    
    # Handle AJAX POST requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            data = json.loads(request.body)
            action = data.get('action')
            
            if action == 'update_profile':
                # Update personal info
                request.user.full_name = data.get('full_name', request.user.full_name)
                request.user.email = data.get('email', request.user.email)
                request.user.save()
                return JsonResponse({'status': 'success', 'message': 'Profile updated'})
            
            elif action == 'update_address':
                # Update shipping address
                address = data.get('address', {})
                request.user.address = address  # Assuming address is a JSONField
                request.user.save()
                return JsonResponse({'status': 'success', 'message': 'Address saved'})
            
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    # GET request: render profile page
    context = {
        'user': request.user,
        # Add any extra context needed
    }
    return render(request, 'accounts/profile.html', context)

def redirect_by_role(user):
    if user.is_admin:
        return redirect('admin_dashboard')
    elif user.is_seller:
        return redirect('seller_dashboard')
    return redirect('shop:home')