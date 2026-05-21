# common/models.py
import os
import threading
from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator 
from PIL import Image

# Thread-local storage for tracking the current request user
_thread_locals = threading.local()

def get_current_user():
    """Retrieve authenticated user from thread-local storage"""
    return getattr(_thread_locals, 'user', None)


class BaseModel(models.Model):
    """
    Abstract base model providing audit fields and auto-user tracking.
    Inherit this in any model to get created_at, updated_at, created_by, updated_by, is_active.
    """
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='%(class)s_created_by', verbose_name="Created By"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='%(class)s_updated_by', verbose_name="Updated By"
    )
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    is_deleted = models.BooleanField(default=False,verbose_name="Is Deleted")
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        user = get_current_user()
        if user and user.is_authenticated:
            if not self.pk:
                self.created_by = user
            self.updated_by = user
        super().save(*args, **kwargs)


# ==========================================
# 🌐 DYNAMIC SITE BRANDING & SETTINGS
# ==========================================
class SiteSettings(models.Model):
    """
    Global singleton model for dynamic logos, brand colors, contact info, and SEO defaults.
    Automatically injected into all templates via context processor.
    """
    site_name = models.CharField(max_length=100, default='StallCart')
    site_tagline = models.CharField(max_length=255, blank=True, default='India\'s Premium Fashion Destination')
    about_us = models.TextField(blank=True, null=True)

    # Logo Variants
    logo_primary = models.ImageField(
        upload_to='branding/logos/',
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg', 'svg', 'webp'])],
        help_text='Primary logo (header/footer). Recommended: PNG with transparent background, max 400px wide.'
    )
    logo_dark = models.ImageField(
        upload_to='branding/logos/',
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg', 'svg', 'webp'])],
        blank=True, null=True,
        help_text='Logo for dark backgrounds or dark mode (optional)'
    )
    logo_mobile = models.ImageField(
        upload_to='branding/logos/',
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg', 'svg', 'webp'])],
        blank=True, null=True,
        help_text='Compact/square logo for mobile header (optional)'
    )
    favicon = models.ImageField(
        upload_to='branding/icons/',
        validators=[FileExtensionValidator(allowed_extensions=['png', 'ico', 'svg'])],
        blank=True, null=True,
        help_text='Browser tab icon. Recommended: 32x32px PNG'
    )
    apple_touch_icon = models.ImageField(
        upload_to='branding/icons/',
        validators=[FileExtensionValidator(allowed_extensions=['png'])],
        blank=True, null=True,
        help_text='iOS home screen icon. Recommended: 180x180px PNG'
    )

    # Brand Colors (used as CSS variables in templates)
    primary_color = models.CharField(max_length=7, default='#2874f0', help_text='Primary hex color (e.g., #2874f0)')
    secondary_color = models.CharField(max_length=7, default='#1a56c4', help_text='Secondary/hover hex color')

    # Contact & Social
    contact_phone = models.CharField(max_length=20, default='+91 8004096954')
    contact_email = models.EmailField(default='stallcart.in@gmail.com')
    contact_whatsapp = models.CharField(max_length=20, blank=True, default='8004096954')
    social_instagram = models.URLField(blank=True, help_text='Full Instagram profile URL')
    social_facebook = models.URLField(blank=True)
    social_twitter = models.URLField(blank=True)
    social_youtube = models.URLField(blank=True, help_text='Full YouTube channel URL')     # ✅ ADD THIS


    # SEO Defaults
    meta_description = models.TextField(
        max_length=160,
        blank=True,
        default='Shop premium fashion for men & women. Free delivery, easy returns, 100% original products.'
    )

    # Site Status
    is_maintenance_mode = models.BooleanField(default=False, help_text='Enable maintenance mode for non-admins')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f'{self.site_name} - Branding Settings'

    def save(self, *args, **kwargs):
        # 🔒 Enforce singleton pattern (only 1 record allowed)
        if not self.pk and SiteSettings.objects.exists():
            raise ValueError('SiteSettings is a singleton. Please edit the existing record in Admin.')

        # 🖼️ Optimize uploaded images for faster page loads
        self._optimize_image(self.logo_primary)
        self._optimize_image(self.logo_dark)
        self._optimize_image(self.logo_mobile)

        super().save(*args, **kwargs)

    def _optimize_image(self, image_field):
        """Compress & resize uploaded logos automatically"""
        if image_field and hasattr(image_field, 'path') and os.path.exists(image_field.path):
            try:
                img = Image.open(image_field.path)
                
                # Handle transparency safely
                if img.mode in ('RGBA', 'P', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'RGBA':
                        background.paste(img, mask=img.split()[-1])
                    elif img.mode == 'LA':
                        background.paste(img, mask=img.split()[-1])
                    else:
                        background.paste(img.convert('RGBA'), mask=img.split()[-1])
                    img = background

                # Resize if too wide
                max_width = 400
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

                # Save with compression
                if image_field.path.lower().endswith(('.jpg', '.jpeg')):
                    img.save(image_field.path, quality=85, optimize=True)
                elif image_field.path.lower().endswith('.png'):
                    img.save(image_field.path, optimize=True)
                elif image_field.path.lower().endswith('.webp'):
                    img.save(image_field.path, quality=85, optimize=True)
            except Exception:
                pass  # Fail gracefully to avoid breaking uploads

    @classmethod
    def get_singleton(cls):
        """Get or create the single SiteSettings instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def logo_url(self):
        """Safe URL accessor with fallback to static placeholder"""
        return self.logo_primary.url if self.logo_primary else '/static/images/logo-fallback.png'

    @property
    def whatsapp_link(self):
        """Formatted WhatsApp click-to-chat link"""
        if self.contact_whatsapp:
            clean = ''.join(c for c in self.contact_whatsapp if c.isdigit() or c == '+')
            return f'https://wa.me/{clean}'
        return '#'
    @property
    def logo_absolute_url(self):
        """Return absolute URL for Open Graph tags"""
        if self.logo_primary:
            from django.contrib.sites.shortcuts import get_current_site
            site = get_current_site(None)  # Requires django.contrib.sites
            return f"https://{site.domain}{self.logo_primary.url}"
        return ''
    def clean_logo_url(self):
        if self.logo_url:
            # Optional: Check image dimensions using PIL
            from PIL import Image
            import io
            try:
                img = Image.open(io.BytesIO(self.logo_url.read()))
                width, height = img.size
                if width > 500 or height > 100:
                    raise ValidationError("Logo should be max 500×100px for best display.")
                self.logo_url.seek(0)  # Reset file pointer
            except:
                pass  # Skip validation if PIL not available
        return self.logo_url
    
    
    @property
    def has_social_links(self):
        """Check if any social media is configured"""
        return any([
            self.social_instagram,
            self.social_facebook, 
            self.social_twitter,
            self.social_youtube
        ])

    @property
    def social_links(self):
        """Return dict of configured social links for easy iteration"""
        links = {}
        if self.social_instagram:
            links['instagram'] = {'url': self.social_instagram, 'icon': 'fab fa-instagram', 'color': '#E4405F', 'label': 'Instagram'}
        if self.social_facebook:
            links['facebook'] = {'url': self.social_facebook, 'icon': 'fab fa-facebook', 'color': '#1877F2', 'label': 'Facebook'}
        if self.social_twitter:
            links['twitter'] = {'url': self.social_twitter, 'icon': 'fab fa-twitter', 'color': '#1DA1F2', 'label': 'Twitter'}
        if self.social_youtube:
            links['youtube'] = {'url': self.social_youtube, 'icon': 'fab fa-youtube', 'color': '#FF0000', 'label': 'YouTube'}
        return links
    

class UserFCMToken(BaseModel):

    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    token=models.TextField()

    