from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    # Role selection
    ROLE_CHOICES = [
        ('customer', '🛍️ Customer - I want to purhcase product'),
        ('seller', '🏪 Seller - I want to sell products'),
    ]
    user_role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'role-selector'}),
        label='I want to join as:',
        initial='customer'
    )
    
    # Customer fields (always shown)
    phone = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'Mobile Number *',
            'class': 'form-input',
            'pattern': '[0-9]{10}',
            'maxlength': '10',
            'inputmode': 'numeric'
        }),
        label='Mobile Number'
    )
    full_name = forms.CharField(
        widget=forms.TextInput(attrs={
            'placeholder': 'Full Name *',
            'class': 'form-input'
        }),
        label='Full Name'
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Email * (Required for password reset)',
            'class': 'form-input'
        }),
        label='Email Address'
    )
    
    # Seller-specific fields (shown conditionally)
    shop_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Shop Name *',
            'class': 'form-input seller-field'
        }),
        label='Shop Name'
    )
    shop_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Brief description of your shop (optional)',
            'class': 'form-input seller-field',
            'rows': '3'
        }),
        label='Shop Description'
    )
    gst_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'GST Number (optional)',
            'class': 'form-input seller-field',
            'maxlength': '15'
        }),
        label='GST Number'
    )
    pan_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'PAN Number *',
            'class': 'form-input seller-field',
            'maxlength': '10'
        }),
        label='PAN Number'
    )
    pan_card_file = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input seller-field',
            'accept': 'image/*,application/pdf'
        }),
        label='PAN Card Document'
    )
    
    # Password fields
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password * (Min 6 characters)',
            'class': 'form-input'
        }),
        label='Password'
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm Password *',
            'class': 'form-input'
        }),
        label='Confirm Password'
    )

    class Meta:
        model = User
        fields = ('phone', 'full_name', 'email', 'user_role', 
                  'shop_name', 'shop_description', 'gst_number',
                  'pan_number', 'pan_card_file',
                  'password1', 'password2')

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not phone:
            raise ValidationError("Mobile number is required.")
        if not phone.isdigit():
            raise ValidationError("Mobile number must contain only digits.")
        if len(phone) != 10:
            raise ValidationError("Mobile number must be exactly 10 digits.")
        if User.objects.filter(phone=phone).exists():
            raise ValidationError("This mobile number is already registered.")
        return phone

    def clean_shop_name(self):
        """Validate shop name only if user is registering as seller"""
        shop_name = self.cleaned_data.get('shop_name', '').strip()
        user_role = self.cleaned_data.get('user_role')
        
        if user_role == 'seller' and not shop_name:
            raise ValidationError("Shop name is required for seller accounts.")
        
        # Check uniqueness only for sellers
        if user_role == 'seller' and shop_name:
            from items.models import SellerProfile
            if SellerProfile.objects.filter(shop_name__iexact=shop_name).exists():
                raise ValidationError("A shop with this name already exists.")
        
        return shop_name

    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        user_role = cleaned_data.get('user_role')
        
        # If seller, ensure required seller fields are present
        if user_role == 'seller':
            if not cleaned_data.get('shop_name'):
                self.add_error('shop_name', 'Shop name is required for seller accounts.')
            
            # Validate PAN number presence
            pan_number = cleaned_data.get('pan_number', '').strip().upper()
            if not pan_number:
                self.add_error('pan_number', 'PAN number is required for seller accounts.')
            else:
                import re
                if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan_number):
                    self.add_error('pan_number', 'Invalid PAN number format. Format must be e.g. ABCDE1234F')
                else:
                    cleaned_data['pan_number'] = pan_number
                    # Check uniqueness of PAN number
                    from items.models import SellerProfile
                    if SellerProfile.objects.filter(pan_number=pan_number).exists():
                        self.add_error('pan_number', 'This PAN number is already registered by another seller.')
        
        return cleaned_data

class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Mobile Number",
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter 10-digit mobile number',
            'class': 'form-input',
            'pattern': '[0-9]{10}',
            'maxlength': '10',
            'inputmode': 'numeric',
            'id': 'id_username'
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Password',
            'class': 'form-input',
            'id': 'id_password'
        })
    )

    def clean_username(self):
        phone = self.cleaned_data.get('username')

        if not phone:
            raise ValidationError("Mobile number is required")

        if not phone.isdigit():
            raise ValidationError("Mobile number must contain only digits.")

        if len(phone) != 10:
            raise ValidationError("Mobile number must be exactly 10 digits.")

        return phone