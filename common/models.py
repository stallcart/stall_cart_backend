# common/models.py
import os
import threading
from decimal import Decimal
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
    daily_otp_limit = models.IntegerField(default=5, help_text='Maximum OTP requests allowed per recipient in a 24-hour window')
    slider_autoplay_seconds = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('1.0'), help_text='Autoplay interval for homepage slider in seconds (e.g. 1.0 or 1.5)')

    # Delivery Settings
    delivery_charge = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('40.00'), 
        help_text="Flat delivery charge for orders under threshold (₹)"
    )
    free_delivery_threshold = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('499.00'), 
        help_text="Minimum order amount to qualify for free delivery (₹)"
    )

    # Policies (Rich Text managed via Admin)
    cancellation_policy = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Cancellation Policy",
        default="""
            <h4>1. Order Cancellation by Customer</h4>
            <p>You can cancel your order at any time before it has been shipped by the seller. To cancel, please visit the "My Orders" section in your Profile panel, locate the order, and click the "Cancel Order" button. Once an order is marked as "Shipped" or "Out for Delivery", cancellation is not permitted. However, you can refuse to accept the shipment at the time of delivery.</p>

            <h4>2. Refund on Cancellation</h4>
            <p>For prepaid orders cancelled before shipping, the full transaction amount (including delivery charges) will be refunded to the original payment source (credit/debit card, UPI, net banking) within 3-5 business days from the cancellation date.</p>

            <h4>3. Order Cancellation by Seller / StallCart</h4>
            <p>Occasionally, an order may be cancelled by the seller or StallCart due to unforeseen reasons such as:</p>
            <ul>
              <li>Product being out of stock or inventory discrepancies.</li>
              <li>Errors in product information or listed pricing.</li>
              <li>Inability to deliver to the customer's PIN code by courier partners.</li>
              <li>Identification of fraudulent transactions or security flags.</li>
            </ul>
            <p>In all such cases, a complete refund will be automatically processed back to your source account.</p>
        """
    )
    return_policy = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Return Policy",
        default="""
            <h4>1. 7-Day Easy Returns</h4>
            <p>We want you to love your fashion choices! Items purchased on StallCart are eligible for return <strong>within 7 days of delivery</strong>. To initiate a return, go to your "My Orders" section under your Profile and create a return request.</p>

            <h4>2. Return Conditions</h4>
            <p>To ensure a successful pickup and refund, please keep the following conditions in mind:</p>
            <ul>
              <li><strong>Tags & Labels:</strong> Brand tags, price labels, and barcodes must remain intact and attached to the product.</li>
              <li><strong>Unused Condition:</strong> Products must be unworn, unwashed, unaltered, and without any stains or odors.</li>
              <li><strong>Original Packaging:</strong> The item must be returned in its original brand box/packaging along with any manuals or freebies.</li>
            </ul>
            <p>Our courier agent will perform a quality check at the time of pickup.</p>

            <h4>3. Return Exceptions (Hygiene Products)</h4>
            <p>For hygiene and health safety reasons, the following categories are strictly non-returnable:</p>
            <ul>
              <li>Innerwear, lingerie, swimwear, and socks.</li>
              <li>Cosmetics and personal care items.</li>
              <li>Custom-made or personalized clothing.</li>
            </ul>
            <p>If you receive a defective or damaged product in these categories, please contact support within 24 hours of delivery.</p>

            <h4>4. Refunds & Replacements</h4>
            <p>Once the product is successfully picked up and passes quality checks at our warehouse, the refund will be credited back to your original payment source within 5-7 business days.</p>
        """
    )
    terms_conditions = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Terms & Conditions",
        default="""
            <h4>1. StallCart Platform Usage</h4>
            <p>Welcome to StallCart. These Terms and Conditions govern your use of our platform, website, and services. By accessing or using StallCart, you agree to comply with and be bound by these terms. Please read them carefully.</p>

            <h4>2. User Accounts</h4>
            <p>You are responsible for maintaining the confidentiality of your account credentials, password, and mobile number. You agree to accept responsibility for all activities that occur under your account.</p>

            <h4>3. Pricing and Listings</h4>
            <p>Sellers on StallCart strive to provide accurate product information, including sizing, description, images, and pricing. However, typographical errors or technical glitches can occur. In the event of a price mismatch, the seller reserves the right to cancel the order. All prices are displayed in Indian Rupees (INR) and are inclusive of GST unless specified otherwise.</p>

            <h4>4. Payments & Transactions</h4>
            <p>All online payments are securely processed via Razorpay. StallCart does not store credit/debit card numbers or UPI PINs. You agree to use valid payment instruments and authorize deductions for orders placed on the platform.</p>

            <h4>5. Limitation of Liability</h4>
            <p>StallCart acts as a marketplace platform connecting independent sellers with customers. StallCart is not directly liable for quality variations, logistics delays by third-party courier services, or seller-side contract breaches, but we will mediate to resolve disputes under our return and refund policies.</p>
        """
    )
    privacy_policy = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Privacy Policy",
        default="""
            <h4>1. Information Collection</h4>
            <p>StallCart collects personal information when you register, place an order, or browse our site. This includes your name, delivery address, phone number, email address, and device metadata. This information is essential to fulfill orders, process payments, and improve your shopping experience.</p>

            <h4>2. Use of Information</h4>
            <p>We use your personal data to:</p>
            <ul>
              <li>Deliver products and send shipping updates.</li>
              <li>Secure transactions and prevent fraudulent activity.</li>
              <li>Send promotional offers, recommendations, and newsletters (with your consent, which you can opt-out of at any time).</li>
              <li>Provide customer support and resolve order disputes.</li>
            </ul>

            <h4>3. Information Sharing</h4>
            <p>We do not sell or rent your personal information to third parties. We only share necessary details with trusted partners who assist in our operations:</p>
            <ul>
              <li><strong>Payment Gateways:</strong> Sharing order totals and transaction markers with Razorpay to secure checkouts.</li>
              <li><strong>Logistics Partners:</strong> Sharing your name, phone number, and address with courier agents to deliver your shipments.</li>
            </ul>

            <h4>4. Data Security</h4>
            <p>Your data is protected using secure server architectures and SSL encryption. We implement industrial-grade safeguards to protect against unauthorized access, loss, or alteration of user records.</p>
        """
    )

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

        super().save(*args, **kwargs)

        # 🖼️ Optimize uploaded images for faster page loads after they are saved to disk
        self._optimize_image(self.logo_primary)
        self._optimize_image(self.logo_dark)
        self._optimize_image(self.logo_mobile)

    def _optimize_image(self, image_field):
        """Compress & resize uploaded logos automatically while preserving transparency for PNG/WebP"""
        if image_field and hasattr(image_field, 'path') and os.path.exists(image_field.path):
            try:
                img = Image.open(image_field.path)
                
                # Resize if too wide or too high to fit header layout cleanly
                max_width = 400
                max_height = 120
                
                width, height = img.size
                if width > max_width or height > max_height:
                    ratio = min(max_width / width, max_height / height)
                    new_width = int(width * ratio)
                    new_height = int(height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Save with compression
                ext = os.path.splitext(image_field.path)[1].lower()
                if ext in ('.jpg', '.jpeg'):
                    # Convert transparent background to white for JPEGs
                    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                        bg = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'RGBA':
                            bg.paste(img, mask=img.split()[-1])
                        else:
                            bg.paste(img.convert('RGBA'), mask=img.split()[-1])
                        img = bg
                    img.save(image_field.path, quality=85, optimize=True)
                elif ext == '.png':
                    img.save(image_field.path, optimize=True)
                elif ext == '.webp':
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
            links['twitter'] = {'url': self.social_twitter, 'icon': 'fab fa-x-twitter', 'color': '#000000', 'label': 'X'}
        if self.social_youtube:
            links['youtube'] = {'url': self.social_youtube, 'icon': 'fab fa-youtube', 'color': '#FF0000', 'label': 'YouTube'}
        return links
    

class UserFCMToken(BaseModel):

    user=models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    token=models.TextField()


class EmailTemplate(BaseModel):
    name = models.CharField(max_length=100, unique=True, help_text="Unique template name (e.g. registration_email_otp)")
    subject = models.CharField(max_length=255, help_text="Email subject template (e.g. StallCart - Verification OTP)")
    body = models.TextField(help_text="Email body template (HTML and plain text template. E.g. Your OTP is {{ otp }})")
    description = models.TextField(blank=True, null=True, help_text="Purpose of this email template")

    def __str__(self):
        return f"{self.name} - {self.subject}"

    