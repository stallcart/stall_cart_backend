from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Address
from delivery.delivery_services import repair_address, ShiprocketService
from unittest.mock import MagicMock

User = get_user_model()

class RepairAddressTests(TestCase):
    def test_strip_whitespace(self):
        addr = {
            "name": "  John Doe  ",
            "city": " Varanasi ",
            "state": " Uttar Pradesh ",
            "postal_code": " 221005 ",
            "phone": " 9999999999 "
        }
        repaired = repair_address(addr)
        self.assertEqual(repaired["name"], "John Doe")
        self.assertEqual(repaired["city"], "Varanasi")
        self.assertEqual(repaired["state"], "Uttar Pradesh")
        self.assertEqual(repaired["postal_code"], "221005")
        self.assertEqual(repaired["phone"], "9999999999")

    def test_state_pincode_contamination_hyphen(self):
        addr = {
            "state": "Uttar Pradesh - 221005",
            "postal_code": ""
        }
        repaired = repair_address(addr)
        self.assertEqual(repaired["state"], "Uttar Pradesh")
        self.assertEqual(repaired["postal_code"], "221005")

    def test_state_pincode_contamination_endash(self):
        addr = {
            "state": "UP – 221001",
            "postal_code": ""
        }
        repaired = repair_address(addr)
        self.assertEqual(repaired["state"], "UP")
        self.assertEqual(repaired["postal_code"], "221001")

    def test_pincode_extraction_from_address_lines(self):
        addr = {
            "address_line1": "Varanasi, Uttar Pradesh 221005",
            "postal_code": ""
        }
        repaired = repair_address(addr)
        self.assertEqual(repaired["postal_code"], "221005")

    def test_fallback_to_user_default_address(self):
        user = User.objects.create_user(phone="9999999999", password="password123")
        default_addr = Address.objects.create(
            user=user,
            name="Jane Doe",
            phone="9876543210",
            address_line1="Default Line 1",
            city="Varanasi",
            state="UP",
            postal_code="221005",
            country="India",
            is_default=True,
            is_active=True
        )
        
        # Test case: missing critical fields
        addr = {
            "name": "",
            "postal_code": "",
            "city": ""
        }
        
        order = MagicMock()
        order.user = user
        
        repaired = repair_address(addr, order=order)
        self.assertEqual(repaired["name"], "Jane Doe")
        self.assertEqual(repaired["postal_code"], "221005")
        self.assertEqual(repaired["city"], "Varanasi")
        self.assertEqual(repaired["phone"], "9876543210")

from django.core import mail
from decimal import Decimal
from orders.models import Order, OrderItem
from items.models import Product, Category, SellerProfile
from common.notification_service import notify_order_placed

class OrderPlacedEmailNotificationTests(TestCase):
    def setUp(self):
        # Clean users if already exist to prevent duplicate phone errors
        User.objects.filter(phone__in=["9998887776", "8887776665"]).delete()

        self.user = User.objects.create_user(phone="9998887776", email="customer@example.com", password="password123")
        
        # Create a seller
        self.seller_user = User.objects.create_user(phone="8887776665", email="seller@example.com", password="password123", role="seller")
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Test Shop",
            bank_name="Test Bank",
            account_number="1234567890",
            ifsc_code="ABCD0123456",
            account_holder_name="Test Holder",
            is_verified=True
        )

        # Create Category and Product
        self.category, _ = Category.objects.get_or_create(name="Apparel", slug="apparel", defaults={"commision_percentage": Decimal("10.00")})
        self.product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Cool T-Shirt",
            description="Description",
            price=Decimal("500.00"),
            mrp=Decimal("600.00"),
            stock=10,
            status="published",
            is_active=True
        )

        # Create Order
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal("500.00"),
            delivery_charge=Decimal("0.00"),
            shipping_address={
                "name": "John Customer",
                "phone": "9998887776",
                "address_line1": "123 Main Street",
                "city": "Varanasi",
                "state": "Uttar Pradesh",
                "postal_code": "221005",
                "country": "India"
            },
            payment_method="cod",
            payment_status="pending",
            status="pending"
        )
        
        # Create OrderItem
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            seller=self.seller_profile,
            quantity=1,
            price=Decimal("500.00"),
            total=Decimal("500.00")
        )

    def test_notify_order_placed_sends_emails(self):
        # Clear outbox
        mail.outbox = []

        # Trigger order placed notifications
        notify_order_placed(self.order)

        # We expect two emails: one to the customer, one to the seller
        emails = [m for m in mail.outbox]
        self.assertGreaterEqual(len(emails), 2)
        
        # Check customer email contents
        customer_email = next((m for m in emails if "customer@example.com" in m.to), None)
        self.assertIsNotNone(customer_email)
        self.assertIn("Placed Successfully", customer_email.subject)
        self.assertIn("Cool T-Shirt", customer_email.body)
        self.assertIn("John Customer", customer_email.body)
        self.assertIn("Varanasi", customer_email.body)
        self.assertIn("221005", customer_email.body)

        # Check seller email contents
        seller_email = next((m for m in emails if "seller@example.com" in m.to), None)
        self.assertIsNotNone(seller_email)
        self.assertIn("New Order", seller_email.subject)
        self.assertIn("Cool T-Shirt", seller_email.body)


from unittest.mock import patch

class ShiprocketServiceTests(TestCase):
    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta
        self.srv = ShiprocketService()
        self.srv._token = "dummy-token"
        self.srv._token_expiry = timezone.now() + timedelta(days=9)

    @patch('requests.get')
    def test_fetch_shipment_details_exact_match(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "channel_order_id": "ORD-555",
                    "id": 77777,
                    "shipments": []
                },
                {
                    "channel_order_id": "ORD-123",
                    "id": 99999,
                    "shipments": [
                        {
                            "id": 88888,
                            "awb": "AWB-1234",
                            "courier": "Delhivery"
                        }
                    ]
                }
            ]
        }
        mock_get.return_value = mock_response

        # Correctly matches only ORD-123
        details = self.srv.fetch_shipment_details_by_channel_order_id("ORD-123")
        self.assertIsNotNone(details)
        self.assertEqual(details["shiprocket_order_id"], 99999)
        self.assertEqual(details["awb"], "AWB-1234")
        self.assertEqual(details["courier_name"], "Delhivery")

        # Returns None because ORD-999 is not in the data list
        details_none = self.srv.fetch_shipment_details_by_channel_order_id("ORD-999")
        self.assertIsNone(details_none)

    @patch('requests.get')
    def test_get_tracking_safely_handles_nulls(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Simulated response where tracking_data is null, and shipment_track_activities is null or missing
        mock_response.json.return_value = {
            "tracking_data": None
        }
        mock_get.return_value = mock_response

        tracking = self.srv.get_tracking("AWB-1234")
        self.assertEqual(tracking["activities"], [])

        # Test where tracking_data is a dict but activities and shipment_track are null
        mock_response.json.return_value = {
            "tracking_data": {
                "shipment_track": None,
                "shipment_track_activities": None
            }
        }
        tracking2 = self.srv.get_tracking("AWB-1234")
        self.assertEqual(tracking2["activities"], [])

