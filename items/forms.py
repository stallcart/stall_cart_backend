# items/forms.py
from django import forms
from django.core.validators import FileExtensionValidator
from .models import *
from django.forms import inlineformset_factory, BaseInlineFormSet
# Custom widget for multiple file uploads
# class MultiFileInput(forms.ClearableFileInput):
#     allow_multiple_selected = True
#     template_name = 'django/forms/widgets/clearable_file_input.html'  # Use default template

# class ProductForm(forms.ModelForm):
#     # ✅ Separate field for additional images (not in Meta.fields)
#     additional_images = forms.FileField(
#         required=False,
#         widget=MultiFileInput(attrs={
#             'class': 'form-input',
#             'multiple': 'multiple',
#             'accept': 'image/*'
#         }),
#         validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
#         help_text="Upload up to 5 additional images (JPG, PNG, WebP)"
#     )
    
#     class Meta:
#         model = Product
#         fields = [
#             'name', 'slug', 'short_description', 'description',
#             'price', 'mrp', 'cost_price', 'discount_percent',
#             'stock', 'low_stock_threshold', 'status',
#             'gender', 'primary_image', 'brand', 'sku', 
#             'weight', 'dimensions', 'meta_title', 
#             'meta_description', 'is_featured', 'is_hot_deal',
#             'category',
#             # ❌ Do NOT include 'seller' here - we add it conditionally below
#         ]
#         widgets = {
#             'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Product name'}),
#             'slug': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'product-name'}),
#             'short_description': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Brief description'}),
#             'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 6, 'placeholder': 'Detailed description...'}),
#             'price': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
#             'mrp': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
#             'cost_price': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
#             'discount_percent': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100, 'placeholder': '0-100'}),
#             'stock': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'placeholder': '0'}),
#             'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'placeholder': '5'}),
#             'status': forms.Select(attrs={'class': 'form-select'}),
#             'gender': forms.Select(attrs={'class': 'form-select'}),
#             'primary_image': forms.ClearableFileInput(attrs={
#                 'class': 'form-input',
#                 'accept': 'image/*'
#             }),
#             'brand': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Brand name'}),
#             'sku': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'SKU-123'}),
#             'weight': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': 'in grams'}),
#             'dimensions': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'L x W x H in cm'}),
#             'meta_title': forms.TextInput(attrs={'class': 'form-input', 'maxlength': 200, 'placeholder': 'SEO title'}),
#             'meta_description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'maxlength': 160, 'placeholder': 'SEO description'}),
#             'category': forms.Select(attrs={'class': 'form-select'}),
#         }
    
#     def __init__(self, *args, **kwargs):
#         self.is_superuser = kwargs.pop('is_superuser', False)
#         self.request_user = kwargs.pop('request_user', None)
        
#         super().__init__(*args, **kwargs)
        
#         # Make required fields explicitly required
#         for field_name in ['name', 'price', 'stock', 'category', 'status']:
#             self.fields[field_name].required = True
        
#         # ✅ Add seller field for superusers only
#         if self.is_superuser:
#             self.fields['seller'] = forms.ModelChoiceField(
#                 queryset=SellerProfile.objects.filter(is_verified=True).select_related('user'),
#                 required=True,
#                 label='👑 Admin Control: Assign to Seller',
#                 empty_label='Select a verified seller...',
#                 widget=forms.Select(attrs={
#                     'class': 'form-select seller-select',
#                     'style': 'border-color: #2874f0; font-weight: 600;'
#                 })
#             )
#             if self.instance.pk and self.instance.seller:
#                 self.fields['seller'].initial = self.instance.seller
#         else:
#             # Auto-assign seller for non-superusers
#             if self.instance.pk and not self.instance.seller and self.request_user and hasattr(self.request_user, 'seller_profile'):
#                 self.instance.seller = self.request_user.seller_profile
    
#     # Validation methods
#     def clean_price(self):
#         price = self.cleaned_data.get('price')
#         if price is not None and price <= 0:
#             raise forms.ValidationError('Price must be greater than 0.')
#         return price

#     def clean_discount_percent(self):
#         discount = self.cleaned_data.get('discount_percent')
#         if discount is not None and not (0 <= discount <= 100):
#             raise forms.ValidationError('Discount must be between 0 and 100.')
#         return discount

#     def clean(self):
#         cleaned = super().clean()
#         price = cleaned.get('price')
#         mrp = cleaned.get('mrp')
#         if price and mrp and mrp < price:
#             self.add_error('mrp', 'MRP should be ≥ selling price.')
#         return cleaned


# ── Custom widget that enables multiple file selection ──────────────────────
class MultiFileInput(forms.ClearableFileInput):
    """File input widget that allows selecting multiple files at once."""
    allow_multiple_selected = True

    def __init__(self, attrs=None):
        default_attrs = {'multiple': True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)


# ── Custom field that returns a LIST of validated files ─────────────────────
class MultipleFileField(forms.FileField):
    """
    A FileField that accepts multiple files and returns them as a list.
    Django's built-in FileField only returns a single file even when
    `multiple` is set on the widget. This subclass overrides value_from_datadict
    to call getlist() instead of get(), giving us all selected files.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultiFileInput(attrs={
            'class': 'form-input',
            'accept': 'image/*',
        }))
        super().__init__(*args, **kwargs)

    def value_from_datadict(self, data, files, name):
        # Return the full list; parent class would only return files.get(name)
        return files.getlist(name)

    def clean(self, data, initial=None):
        # `data` is now a list (possibly empty)
        if not data:
            if self.required:
                raise forms.ValidationError(self.error_messages['required'])
            return []

        validated = []
        single_file_field = forms.FileField(
            validators=[
                FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])
            ]
        )
        for f in data:
            validated.append(single_file_field.clean(f))
        return validated


# ── Main ProductForm ─────────────────────────────────────────────────────────
class ProductForm(forms.ModelForm):

    # Uses our custom MultipleFileField so the view receives a list
    additional_images = MultipleFileField(
        required=False,
        help_text="Upload up to 5 additional images (JPG, PNG, WebP)",
    )

    class Meta:
        model = Product
        fields = [
            'name','short_description', 'description',
            'price', 'mrp', 'cost_price', 'discount_percent',
            'stock', 'low_stock_threshold', 'status',
            'gender', 'primary_image', 'brand', 
            'weight', 'dimensions', 'meta_title',
            'meta_description', 'is_featured', 'is_hot_deal',
            'category',
            # ❌ Do NOT include 'seller' here – added conditionally below
        ]
        widgets = {
            'name':              forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Product name'}),
            # 'slug':              forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'product-name'}),
            'short_description': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Brief description'}),
            'description':       forms.Textarea(attrs={'class': 'form-input', 'rows': 6, 'placeholder': 'Detailed description...'}),
            'price':             forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
            'mrp':               forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
            'cost_price':        forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': '0.00'}),
            'discount_percent':  forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'max': 100, 'placeholder': '0-100'}),
            'stock':             forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'placeholder': '0'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'placeholder': '5'}),
            'status':            forms.Select(attrs={'class': 'form-select'}),
            'gender':            forms.Select(attrs={'class': 'form-select'}),
            'primary_image':     forms.ClearableFileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
            'brand':             forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Brand name'}),
            # 'sku':               forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'SKU-123'}),
            'weight':            forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'placeholder': 'in grams'}),
            'dimensions':        forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'L x W x H in cm'}),
            'meta_title':        forms.TextInput(attrs={'class': 'form-input', 'maxlength': 200, 'placeholder': 'SEO title'}),
            'meta_description':  forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'maxlength': 160, 'placeholder': 'SEO description'}),
            'category':          forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.is_superuser  = kwargs.pop('is_superuser', False)
        self.request_user  = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)

        # Make required fields explicitly required
        for field_name in ['name', 'price', 'stock', 'category', 'status']:
            self.fields[field_name].required = True

        # ✅ Add seller field for superusers only
        if self.is_superuser:
            self.fields['seller'] = forms.ModelChoiceField(
                queryset=SellerProfile.objects.filter(is_verified=True).select_related('user'),
                required=True,
                label='👑 Admin Control: Assign to Seller',
                empty_label='Select a verified seller...',
                widget=forms.Select(attrs={
                    'class': 'form-select seller-select',
                    'style': 'border-color: #2874f0; font-weight: 600;',
                })
            )
            if self.instance.pk and self.instance.seller:
                self.fields['seller'].initial = self.instance.seller
        else:
            # Auto-assign seller for non-superusers on new products
            if (
                self.instance.pk is None
                and self.request_user
                and hasattr(self.request_user, 'seller_profile')
            ):
                self.instance.seller = self.request_user.seller_profile

    # ── Validation ───────────────────────────────────────────────────────────

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price <= 0:
            raise forms.ValidationError('Price must be greater than 0.')
        return price

    def clean_cost_price(self):
        cost = self.cleaned_data.get('cost_price')
        if cost is not None and cost <= 0:
            raise forms.ValidationError('Cost price must be greater than 0.')
        return cost

    def clean_discount_percent(self):
        discount = self.cleaned_data.get('discount_percent')
        if discount is not None and not (0 <= discount <= 100):
            raise forms.ValidationError('Discount must be between 0 and 100.')
        return discount

    def clean_additional_images(self):
        images = self.cleaned_data.get('additional_images') or []

        # Count existing images already saved against this product
        existing_count = 0
        if self.instance and self.instance.pk:
            existing_count = self.instance.product_image_product.count()

        max_allowed = 5
        available_slots = max_allowed - existing_count

        if len(images) > available_slots:
            raise forms.ValidationError(
                f'You can upload at most {available_slots} more image(s) '
                f'(maximum {max_allowed} total per product).'
            )

        max_size = 5 * 1024 * 1024  # 5 MB
        allowed_types = {'image/jpeg', 'image/png', 'image/webp'}

        for img in images:
            if img.size > max_size:
                raise forms.ValidationError(
                    f'"{img.name}" exceeds the 5 MB size limit.'
                )
            if img.content_type not in allowed_types:
                raise forms.ValidationError(
                    f'"{img.name}" must be a JPG, PNG, or WebP file.'
                )

        return images

    def clean(self):
        cleaned = super().clean()
        price = cleaned.get('price')
        mrp   = cleaned.get('mrp')
        if price and mrp and mrp < price:
            self.add_error('mrp', 'MRP should be ≥ selling price.')
        return cleaned
    



class ProductVariantForm(forms.ModelForm):
    """Form for individual product variant"""
    class Meta:
        model = ProductVariant
        fields = ['size_value', 'size_type', 'color', 'price_override', 'stock', 'is_active', 'attributes']
        widgets = {
            'size_value': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': 'e.g., M, 6, 24x36',
                'required': 'required'
            }),
            'size_type': forms.Select(attrs={'class': 'form-select'}),
            'color': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': 'Optional: Red, Gold, Walnut'
            }),
            'price_override': forms.NumberInput(attrs={
                'class': 'form-input', 
                'step': '0.01', 
                'placeholder': 'Leave blank to use product price'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'form-input', 
                'min': '0', 
                'placeholder': '0',
                'required': 'required'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'attributes': forms.Textarea(attrs={
                'class': 'form-input', 
                'rows': 2,
                'placeholder': 'JSON: {"material": "Cotton", "fit": "Slim"}'
            }),
        }
        labels = {
            'size_value': 'Size/Variant Value *',
            'size_type': 'Variant Type',
            'color': 'Color/Finish',
            'price_override': 'Price Override (₹)',
            'stock': 'Stock *',
            'is_active': 'Active',
            'attributes': 'Custom Attributes (JSON)',
        }
        help_texts = {
            'size_value': 'e.g., S/M/L, 6/7/8, 24x36 inches',
            'size_type': 'Helps with filtering and display',
            'price_override': 'Leave blank to use base product price',
            'attributes': 'Optional JSON for extra specs',
        }

    def clean_price_override(self):
        price = self.cleaned_data.get('price_override')
        if price is not None and price <= 0:
            raise forms.ValidationError('Price override must be greater than 0.')
        return price

    def clean_stock(self):
        stock = self.cleaned_data.get('stock')
        if stock is not None and stock < 0:
            raise forms.ValidationError('Stock cannot be negative.')
        return stock


class BaseVariantFormSet(BaseInlineFormSet):
    """Custom formset validation"""

    def clean(self):
        super().clean()

        seen = set()

        for form in self.forms:

            # Skip empty/deleted forms
            if not hasattr(form, 'cleaned_data'):
                continue

            if form.cleaned_data.get('DELETE'):
                continue

            if not form.cleaned_data:
                continue

            size = (
                form.cleaned_data.get('size_value', '')
                .strip()
                .lower()
            )

            color = (
                form.cleaned_data.get('color', '')
                .strip()
                .lower()
            )

            key = (size, color)

            if key in seen:
                raise forms.ValidationError(
                    f'Duplicate variant: "{size}"'
                    f'{f" / {color}" if color else ""} already exists.'
                )

            seen.add(key)


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    formset=BaseVariantFormSet,
    fields=[
        'size_value',
        'size_type',
        'color',
        'price_override',
        'stock',
        'is_active',
        'attributes'
    ],
    extra=1,
    can_delete=True,
)

class ProductReviewForm(forms.ModelForm):
    class Meta:
        model = ProductReview
        fields = ['rating', 'title', 'review', 'images', 'video']
        widgets = {
            'rating': forms.RadioSelect(attrs={'class': 'rating-input'}),
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Summarize your experience (optional)',
                'maxlength': '200'
            }),
            'review': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Share details about quality, fit, value...',
                'rows': '4',
                'maxlength': '2000'
            }),
            'images': forms.ClearableFileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*'
            }),
            'video': forms.ClearableFileInput(attrs={
                'class': 'form-input',
                'accept': 'video/*'
            }),
        }
    
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating and not (1 <= rating <= 5):
            raise forms.ValidationError('Rating must be between 1 and 5 stars')
        return rating
    
    def clean_review(self):
        review = self.cleaned_data.get('review')
        if review and len(review.strip()) < 20:
            raise forms.ValidationError('Review must be at least 20 characters')
        return review.strip()


class SellerReviewForm(forms.ModelForm):
    class Meta:
        model = SellerReview
        fields = ['rating', 'title', 'review', 'images', 'video']
        widgets = {
            'rating': forms.RadioSelect(attrs={'class': 'rating-input'}),
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Summarize your experience (optional)',
                'maxlength': '200'
            }),
            'review': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Share details about packaging, delivery, service...',
                'rows': '4',
                'maxlength': '2000'
            }),
            'images': forms.ClearableFileInput(attrs={
                'class': 'form-input',
                'accept': 'image/*'
            }),
            'video': forms.ClearableFileInput(attrs={
                'class': 'form-input',
                'accept': 'video/*'
            }),
        }
    
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating and not (1 <= rating <= 5):
            raise forms.ValidationError('Rating must be between 1 and 5 stars')
        return rating
    
    def clean_review(self):
        review = self.cleaned_data.get('review')
        if review and len(review.strip()) < 20:
            raise forms.ValidationError('Review must be at least 20 characters')
        return review.strip()