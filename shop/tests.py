from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import AnnouncementBanner, Cart, CartItem
from orders.models import Order
from decimal import Decimal
import json

class AnnouncementBannerTest(TestCase):
    def setUp(self):
        from common.models import _thread_locals
        _thread_locals.user = None
        self.client = Client()
        self.target_time = timezone.now() + timedelta(days=2)
        
    def test_announcement_banner_creation(self):
        banner = AnnouncementBanner.objects.create(
            title="Independence Day Sale!",
            subtitle="Great Indian Festival is here.",
            coupon_code="IND50",
            btn_text="Grab Deal",
            link_url="/items/?category=electronics",
            end_datetime=self.target_time,
            is_active=True
        )
        self.assertEqual(banner.title, "Independence Day Sale!")
        self.assertEqual(banner.coupon_code, "IND50")
        self.assertTrue(banner.is_active)
        self.assertEqual(str(banner), "Independence Day Sale! (Active: True)")

    def test_homepage_context_with_active_banner(self):
        banner = AnnouncementBanner.objects.create(
            title="Independence Day Sale!",
            subtitle="Great Indian Festival is here.",
            coupon_code="IND50",
            btn_text="Grab Deal",
            link_url="/items/?category=electronics",
            end_datetime=self.target_time,
            is_active=True
        )
        
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('announcement_banner', response.context)
        self.assertEqual(response.context['announcement_banner'].id, banner.id)
        self.assertContains(response, "Independence Day Sale!")
        self.assertContains(response, "IND50")
        self.assertContains(response, "Grab Deal")

    def test_homepage_context_with_inactive_banner(self):
        banner = AnnouncementBanner.objects.create(
            title="Inactive Sale",
            end_datetime=self.target_time,
            is_active=False
        )
        
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('announcement_banner', response.context)
        self.assertIsNone(response.context['announcement_banner'])
        self.assertNotContains(response, "Inactive Sale")


class ProductOpenGraphTest(TestCase):
    def setUp(self):
        from common.models import _thread_locals
        _thread_locals.user = None
        
        from items.models import Category, SellerProfile, Product
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        self.seller_user = User.objects.create_user(phone="7777777777", password="sellerpassword")
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Test Store",
            is_verified=True
        )
        
        self.category = Category.objects.create(
            name="Clothing",
            slug="clothing"
        )
        
        self.product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Modern Polo Shirt",
            price=19.99,
            stock=10,
            status="published",
            meta_title="Modern Polo Shirt SEO Title",
            meta_description="Detailed description for social media."
        )

    def test_product_detail_open_graph_meta_tags(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        customer = User.objects.create_user(phone="9999999999", password="customerpassword", role="customer")
        self.client.login(phone="9999999999", password="customerpassword")
        
        response = self.client.get(reverse('items:product_detail', kwargs={'slug': self.product.slug}))
        self.assertEqual(response.status_code, 200)
        
        # Verify custom meta tags are present in HTML response
        self.assertContains(response, '<meta property="og:type" content="product">')
        self.assertContains(response, 'Modern Polo Shirt')
        self.assertContains(response, 'Detailed description for social media.')

    def test_product_detail_guest_access_and_open_graph_meta_tags(self):
        # Access product detail page without logging in
        response = self.client.get(reverse('items:product_detail', kwargs={'slug': self.product.slug}))
        self.assertEqual(response.status_code, 200)
        
        # Verify custom meta tags are present in HTML response
        self.assertContains(response, '<meta property="og:type" content="product">')
        self.assertContains(response, 'Modern Polo Shirt')
        self.assertContains(response, 'Detailed description for social media.')



class HomepageProductSlicingTests(TestCase):
    def setUp(self):
        from common.models import _thread_locals
        _thread_locals.user = None
        
        from items.models import Category, SellerProfile, Product
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        self.seller_user = User.objects.create_user(phone="8888888888", password="sellerpassword")
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Test Store 2",
            is_verified=True
        )
        
        self.category = Category.objects.create(
            name="Clothing 2",
            slug="clothing-2"
        )
        
        # Create 15 published, in-stock products
        for i in range(15):
            Product.objects.create(
                seller=self.seller_profile,
                category=self.category,
                name=f"Product {i}",
                price=10.0 + i,
                stock=5,
                status="published"
            )

    def test_homepage_product_slicing(self):
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.status_code, 200)
        
        # Context products should contain exactly 12 products
        self.assertEqual(len(response.context['products']), 12)
        
        # Context product_count should be 15
        self.assertEqual(response.context['product_count'], 15)


from unittest.mock import patch, MagicMock

class CheckoutSecurityTests(TestCase):
    def setUp(self):
        from common.models import _thread_locals, SiteSettings
        _thread_locals.user = None
        
        from items.models import Category, SellerProfile, Product
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        self.customer = User.objects.create_user(phone="9999999999", password="customerpassword", role="customer")
        self.seller_user = User.objects.create_user(phone="7777777777", password="sellerpassword")
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Test Store",
            is_verified=True
        )
        self.category = Category.objects.create(
            name="Clothing",
            slug="clothing"
        )
        self.product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Test Polo Shirt",
            price=Decimal("500.00"),
            stock=10,
            status="published"
        )
        
        # Ensure SiteSettings exists for delivery calculations in tests
        SiteSettings.objects.all().delete()
        self.site_settings = SiteSettings.objects.create(
            site_name="StallCart",
            free_delivery_threshold=Decimal("499.00"),
            delivery_charge=Decimal("40.00")
        )
        
        self.cart = Cart.objects.create(user=self.customer)
        self.cart_item = CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.client.login(phone="9999999999", password="customerpassword")

    @patch('razorpay.Client')
    def test_verify_payment_recalculates_price_and_ignores_tampered_payload(self, mock_razorpay):
        mock_client = MagicMock()
        mock_razorpay.return_value = mock_client
        mock_client.payment.fetch.return_value = {
            'order_id': 'order_123',
            'amount': 50000,
            'status': 'captured'
        }
        
        import hmac, hashlib
        from django.conf import settings
        
        razorpay_order_id = "order_123"
        payment_id = "pay_123"
        message = f"{razorpay_order_id}|{payment_id}"
        sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        tampered_cart_payload = json.dumps({
            'address': {'name': 'John'},
            'subtotal': 0.80,
            'discount_amount': 0.00,
            'delivery_charge': 40.00,
            'total_amount': 40.80,
            'items': [{
                'product_id': self.product.id,
                'quantity': 1
            }]
        })
        
        response = self.client.post(
            reverse('shop:verify_payment'),
            data=json.dumps({
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_signature': sig,
                'cart_payload': tampered_cart_payload
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        order = Order.objects.latest('created_at')
        self.assertEqual(order.total_amount, Decimal("500.00"))

    @patch('razorpay.Client')
    def test_verify_payment_detects_razorpay_amount_tampering(self, mock_razorpay):
        mock_client = MagicMock()
        mock_razorpay.return_value = mock_client
        mock_client.payment.fetch.return_value = {
            'order_id': 'order_123',
            'amount': 4080,
            'status': 'captured'
        }
        
        import hmac, hashlib
        from django.conf import settings
        
        razorpay_order_id = "order_123"
        payment_id = "pay_123"
        message = f"{razorpay_order_id}|{payment_id}"
        sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        tampered_cart_payload = json.dumps({
            'address': {'name': 'John'},
            'subtotal': 0.80,
            'discount_amount': 0.00,
            'delivery_charge': 40.00,
            'total_amount': 40.80,
            'items': [{
                'product_id': self.product.id,
                'quantity': 1
            }]
        })
        
        response = self.client.post(
            reverse('shop:verify_payment'),
            data=json.dumps({
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_signature': sig,
                'cart_payload': tampered_cart_payload
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Payment amount mismatch", response.json()['message'])

    @patch('razorpay.Client')
    def test_verify_payment_rejects_negative_quantities(self, mock_razorpay):
        mock_client = MagicMock()
        mock_razorpay.return_value = mock_client
        
        import hmac, hashlib
        from django.conf import settings
        
        razorpay_order_id = "order_123"
        payment_id = "pay_123"
        message = f"{razorpay_order_id}|{payment_id}"
        sig = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        tampered_cart_payload = json.dumps({
            'address': {'name': 'John'},
            'subtotal': -500.00,
            'discount_amount': 0.00,
            'delivery_charge': 40.00,
            'total_amount': -460.00,
            'items': [{
                'product_id': self.product.id,
                'quantity': -1
            }]
        })
        
        response = self.client.post(
            reverse('shop:verify_payment'),
            data=json.dumps({
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': razorpay_order_id,
                'razorpay_signature': sig,
                'cart_payload': tampered_cart_payload
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid item quantity", response.json()['message'])


