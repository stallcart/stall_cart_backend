# items/forms.py
from django import forms
from .models import Product, Category, SellerProfile


class ProductForm(forms.ModelForm):
    """
    Shared form for both sellers and superusers.

    Pass `is_superuser=True` when instantiating for a superuser so the
    `seller` field is included and required; for regular sellers it is
    excluded entirely (the view hard-codes their profile instead).
    """

    class Meta:
        model  = Product
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
        
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'slug': forms.TextInput(attrs={'class': 'form-input'}),
            'short_description': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 6}),
            'price': forms.NumberInput(attrs={'class': 'form-input'}),
            'mrp': forms.NumberInput(attrs={'class': 'form-input'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-input'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-input'}),
            'stock': forms.NumberInput(attrs={'class': 'form-input'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),  # ✅ Gender dropdown

            'primary_image': forms.ClearableFileInput(attrs={'class': 'form-input'}),
            'brand': forms.TextInput(attrs={'class': 'form-input'}),
            'sku': forms.TextInput(attrs={'class': 'form-input'}),
            'weight': forms.NumberInput(attrs={'class': 'form-input'}),
            'dimensions': forms.TextInput(attrs={'class': 'form-input'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-input'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-input'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }
    def __init__(self, *args, is_superuser=False, **kwargs):
        super().__init__(*args, **kwargs)

        if not is_superuser:
            self.fields.pop('seller', None)
        else:
            self.fields['seller'].queryset = SellerProfile.objects.filter(is_verified=True)
            self.fields['seller'].required = True
            self.fields['seller'].label = "Assign to Seller"

        self.fields['slug'].required = False

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