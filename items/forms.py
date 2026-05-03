# items/forms.py
from django import forms
from .models import Product, Category, SellerProfile


# items/forms.py

class ProductForm(forms.ModelForm):
    """
    Shared form for both sellers and superusers.
    
    - Sellers: seller field is hidden (auto-assigned)
    - Superusers: seller field is a clean dropdown with search-ready styling
    """

    class Meta:
        model = Product
        fields = [
            # ── shown to everyone ──────────────────────────────────────────
            'name', 'slug', 'short_description', 'description',
            'price', 'mrp', 'cost_price', 'discount_percent',
            'stock', 'low_stock_threshold', 'status',
            'gender',
            'primary_image',
            'brand', 'sku', 'weight', 'dimensions',
            'meta_title', 'meta_description',
            'is_featured', 'is_hot_deal',
            'category',
            # ❌ REMOVE 'seller' from here - we handle it separately below
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Product name'}),
            'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'product-name'}),
            'short_description': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Brief description'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 6, 'placeholder': 'Detailed description...'}),
            'price': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
            'mrp': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100, 'placeholder': '0-100'}),
            'stock': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'placeholder': '0'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'placeholder': '5'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'primary_image': forms.ClearableFileInput(attrs={'class': 'form-input'}),
            'brand': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Brand name'}),
            'sku': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'SKU-123'}),
            'weight': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': 'in grams'}),
            'dimensions': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'L x W x H in cm'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-input', 'maxlength': 200, 'placeholder': 'SEO title'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'maxlength': 160, 'placeholder': 'SEO description'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Pop custom kwargs before calling super()
        self.is_superuser = kwargs.pop('is_superuser', False)
        self.request_user = kwargs.pop('request_user', None)
        
        super().__init__(*args, **kwargs)
        
        # ✅ Only add seller field for superusers
        if self.is_superuser:
            from .models import SellerProfile
            self.fields['seller'] = forms.ModelChoiceField(
                queryset=SellerProfile.objects.filter(is_verified=True).select_related('user'),
                required=True,
                label='👑 Admin Control: Assign to Seller',
                empty_label='Select a verified seller...',
                widget=forms.Select(attrs={
                    'class': 'form-select seller-select',  # ✅ Custom class for styling
                    'style': 'border-color: #2874f0; font-weight: 600;'
                })
            )
            # Pre-select current seller if editing
            if self.instance.pk and self.instance.seller:
                self.fields['seller'].initial = self.instance.seller
        else:
            # For sellers, ensure seller is set but not shown in form
            if self.instance.pk and not self.instance.seller and self.request_user and hasattr(self.request_user, 'seller_profile'):
                self.instance.seller = self.request_user.seller_profile
    
    # ── validation ────────────────────────────────────────────────────────────
    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price <= 0:
            raise forms.ValidationError('Price must be greater than 0.')
        return price

    def clean_discount_percent(self):
        discount = self.cleaned_data.get('discount_percent')
        if discount is not None and not (0 <= discount <= 100):
            raise forms.ValidationError('Discount must be between 0 and 100.')
        return discount

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get('price')
        mrp   = cleaned.get('mrp')
        if price and mrp and mrp < price:
            self.add_error('mrp', 'MRP should be ≥ selling price.')
        return cleaned