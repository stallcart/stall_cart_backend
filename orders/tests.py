# orders/tests.py
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date
import json

from accounts.models import Wallet
from items.models import Category, Product, SellerProfile
from orders.models import Order, OrderItem, ReturnRequest, OrderStatusLog

User = get_user_model()

class OrderManagementTests(TestCase):
    def setUp(self):
        # Create users
        self.admin_user = User.objects.create_superuser(
            phone="9999999999",
            password="adminpassword",
            full_name="Admin User"
        )
        
        self.seller_user1 = User.objects.create_user(
            phone="8888888888",
            password="sellerpassword",
            role="seller",
            full_name="Seller One"
        )
        self.seller_profile1 = SellerProfile.objects.create(
            user=self.seller_user1,
            shop_name="Shop One",
            is_verified=True
        )
        
        self.seller_user2 = User.objects.create_user(
            phone="7777777777",
            password="sellerpassword",
            role="seller",
            full_name="Seller Two"
        )
        self.seller_profile2 = SellerProfile.objects.create(
            user=self.seller_user2,
            shop_name="Shop Two",
            is_verified=True
        )
        
        self.customer = User.objects.create_user(
            phone="6666666666",
            password="customerpassword",
            role="customer",
            full_name="Customer User"
        )
        
        # Create Category & Products
        self.category = Category.objects.create(name="Clothing", commision_percentage=10.0)
        
        self.product1 = Product.objects.create(
            seller=self.seller_profile1,
            category=self.category,
            name="Seller One Shirt",
            price=Decimal("100.00"),
            stock=10
        )
        self.product2 = Product.objects.create(
            seller=self.seller_profile2,
            category=self.category,
            name="Seller Two Jeans",
            price=Decimal("200.00"),
            stock=5
        )
        
        # Setup Address
        self.address = {
            "name": "Customer User",
            "phone": "6666666666",
            "address_line1": "123 Street",
            "city": "Mumbai",
            "state": "Maharashtra",
            "postal_code": "400001"
        }
        
        # Create Order 1 (COD, products from both sellers)
        self.order1 = Order.objects.create(
            user=self.customer,
            shipping_address=self.address,
            total_amount=Decimal("300.00"),
            payment_method="cod",
            payment_status="pending",
            status="pending"
        )
        self.item1_1 = OrderItem.objects.create(
            order=self.order1,
            product=self.product1,
            seller=self.seller_profile1,
            quantity=1,
            price=Decimal("100.00"),
            total=Decimal("100.00")
        )
        self.item1_2 = OrderItem.objects.create(
            order=self.order1,
            product=self.product2,
            seller=self.seller_profile2,
            quantity=1,
            price=Decimal("200.00"),
            total=Decimal("200.00")
        )
        # Add a second item for Seller 1 to Order 1 to test multiple items same seller scenario
        self.item1_3 = OrderItem.objects.create(
            order=self.order1,
            product=self.product1,
            seller=self.seller_profile1,
            quantity=2,
            price=Decimal("100.00"),
            total=Decimal("200.00")
        )
        
        # Create Order 2 (Wallet, only seller 1's product)
        self.order2 = Order.objects.create(
            user=self.customer,
            shipping_address=self.address,
            total_amount=Decimal("100.00"),
            payment_method="wallet",
            payment_status="paid",
            status="confirmed"
        )
        self.item2_1 = OrderItem.objects.create(
            order=self.order2,
            product=self.product1,
            seller=self.seller_profile1,
            quantity=1,
            price=Decimal("100.00"),
            total=Decimal("100.00")
        )

    def test_seller_orders_isolation(self):
        """Sellers should only see order items containing their products."""
        # Log in as Seller 1
        self.client.login(phone="8888888888", password="sellerpassword")
        response = self.client.get(reverse('orders:seller_orders'))
        self.assertEqual(response.status_code, 200)
        
        # Seller 1 should see item1_1 and item2_1, but not item1_2
        order_items = response.context['order_items']
        self.assertIn(self.item1_1, order_items)
        self.assertIn(self.item2_1, order_items)
        self.assertNotIn(self.item1_2, order_items)
        
        # Log in as Seller 2
        self.client.login(phone="7777777777", password="sellerpassword")
        response = self.client.get(reverse('orders:seller_orders'))
        self.assertEqual(response.status_code, 200)
        
        # Seller 2 should only see item1_2
        order_items = response.context['order_items']
        self.assertIn(self.item1_2, order_items)
        self.assertNotIn(self.item1_1, order_items)
        self.assertNotIn(self.item2_1, order_items)

    def test_admin_orders_system_wide(self):
        """Admin should see all orders system-wide."""
        self.client.login(phone="9999999999", password="adminpassword")
        response = self.client.get(reverse('orders:admin_orders'))
        self.assertEqual(response.status_code, 200)
        
        orders = response.context['orders']
        self.assertIn(self.order1, orders)
        self.assertIn(self.order2, orders)

    def test_seller_orders_search_and_filters(self):
        """Test the search and filter options in seller orders list."""
        self.client.login(phone="8888888888", password="sellerpassword")
        
        # Search by Order ID
        response = self.client.get(reverse('orders:seller_orders'), {'q': self.order1.unique_order_id})
        self.assertIn(self.item1_1, response.context['order_items'])
        self.assertNotIn(self.item2_1, response.context['order_items'])
        
        # Search by Customer Name
        response = self.client.get(reverse('orders:seller_orders'), {'q': "Customer User"})
        self.assertIn(self.item1_1, response.context['order_items'])
        self.assertIn(self.item2_1, response.context['order_items'])
        
        # Filter by Status
        response = self.client.get(reverse('orders:seller_orders'), {'status': 'confirmed'})
        self.assertIn(self.item2_1, response.context['order_items'])
        self.assertNotIn(self.item1_1, response.context['order_items'])
        
        # Filter by Date (today)
        from django.utils.timezone import localtime
        today_str = localtime(self.order1.created_at).strftime("%Y-%m-%d")
        response = self.client.get(reverse('orders:seller_orders'), {'date': today_str})
        self.assertIn(self.item1_1, response.context['order_items'])
        self.assertIn(self.item2_1, response.context['order_items'])

    def test_admin_orders_search_and_filters(self):
        """Test the search and filter options in admin orders list."""
        self.client.login(phone="9999999999", password="adminpassword")
        
        # Search by Order ID
        response = self.client.get(reverse('orders:admin_orders'), {'q': self.order2.unique_order_id})
        self.assertIn(self.order2, response.context['orders'])
        self.assertNotIn(self.order1, response.context['orders'])
        
        # Filter by Status
        response = self.client.get(reverse('orders:admin_orders'), {'status': 'pending'})
        self.assertIn(self.order1, response.context['orders'])
        self.assertNotIn(self.order2, response.context['orders'])

    def test_approve_return_permissions(self):
        """Only the owner seller or admin can approve/reject return requests."""
        # Create return request for seller 1's product (item1_1)
        return_req = ReturnRequest.objects.create(
            order_item=self.item1_1,
            user=self.customer,
            quantity=1,
            reason="wrong_item",
            remarks="Wrong color",
            status="requested",
            refund_amount=Decimal("100.00")
        )
        
        # Attempt to approve using Seller 2 (unauthorized)
        self.client.login(phone="7777777777", password="sellerpassword")
        response = self.client.post(
            reverse('orders:approve_return', args=[return_req.id]),
            data=json.dumps({"action": "approve"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        return_req.refresh_from_db()
        self.assertEqual(return_req.status, 'requested')  # Status unchanged
        
        # Approve using Seller 1 (authorized owner)
        self.client.login(phone="8888888888", password="sellerpassword")
        response = self.client.post(
            reverse('orders:approve_return', args=[return_req.id]),
            data=json.dumps({"action": "approve"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        return_req.refresh_from_db()
        self.assertEqual(return_req.status, 'approved')
        
        # Create another return request for item1_2 (owned by seller 2)
        return_req2 = ReturnRequest.objects.create(
            order_item=self.item1_2,
            user=self.customer,
            quantity=1,
            reason="wrong_item",
            remarks="Damaged",
            status="requested",
            refund_amount=Decimal("200.00")
        )
        
        # Approve using Admin (authorized system-wide)
        self.client.login(phone="9999999999", password="adminpassword")
        response = self.client.post(
            reverse('orders:approve_return', args=[return_req2.id]),
            data=json.dumps({"action": "approve"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        return_req2.refresh_from_db()
        self.assertEqual(return_req2.status, 'approved')

    def test_cod_return_refund_handling(self):
        """COD returns must be marked for manual bank transfer instead of wallet deposit."""
        return_req = ReturnRequest.objects.create(
            order_item=self.item1_1,  # Belongs to order1, which is COD
            user=self.customer,
            quantity=1,
            reason="damaged",
            status="requested",
            refund_amount=Decimal("100.00")
        )
        
        # Verify initial stock
        initial_stock = self.product1.stock
        
        # Approve using Admin
        self.client.login(phone="9999999999", password="adminpassword")
        response = self.client.post(
            reverse('orders:approve_return', args=[return_req.id]),
            data=json.dumps({"action": "approve"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify return request status and refund status/method
        return_req.refresh_from_db()
        self.assertEqual(return_req.status, 'approved')
        self.assertEqual(return_req.refund_status, 'manual_pending')
        self.assertEqual(return_req.refund_method, 'bank')
        
        # Verify stock was replenished
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock, initial_stock + 1)
        
        # Verify customer wallet has NOT been credited
        wallet = Wallet.objects.filter(user=self.customer).first()
        if wallet:
            self.assertEqual(wallet.balance, Decimal("0.00"))

    def test_wallet_return_refund_handling(self):
        """Wallet payments return refund amount via manual bank transfer since wallet is disabled."""
        return_req = ReturnRequest.objects.create(
            order_item=self.item2_1,  # Belongs to order2, which is Wallet-paid
            user=self.customer,
            quantity=1,
            reason="damaged",
            status="requested",
            refund_amount=Decimal("100.00")
        )
        
        # Create wallet and add initial balance
        wallet, _ = Wallet.objects.get_or_create(user=self.customer)
        wallet.balance = Decimal("50.00")
        wallet.save()
        
        # Approve using Admin
        self.client.login(phone="9999999999", password="adminpassword")
        response = self.client.post(
            reverse('orders:approve_return', args=[return_req.id]),
            data=json.dumps({"action": "approve"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify return request status and refund status/method (redirected to manual bank transfer)
        return_req.refresh_from_db()
        self.assertEqual(return_req.status, 'approved')
        self.assertEqual(return_req.refund_status, 'manual_pending')
        self.assertEqual(return_req.refund_method, 'bank')
        
        # Verify wallet has NOT been credited
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("50.00"))

    def test_seller_order_detail_multiple_items_same_seller(self):
        """Seller order details page should load successfully when the order contains multiple items from the same seller."""
        # Log in as Seller 1
        self.client.login(phone="8888888888", password="sellerpassword")
        
        # Access order detail for order1 (which has item1_1 and item1_3 for seller1)
        response = self.client.get(reverse('orders:seller_order_detail', args=[self.order1.unique_order_id]))
        self.assertEqual(response.status_code, 200)
        
        # Check that both seller items are in the context
        seller_items = response.context['seller_items']
        self.assertEqual(seller_items.count(), 2)
        self.assertIn(self.item1_1, seller_items)
        self.assertIn(self.item1_3, seller_items)

    def test_shiprocket_webhook_success(self):
        """Shiprocket tracking webhook updates order status and logs the event."""
        # Setup an order with tracking number
        self.order1.tracking_number = "SR123456789"
        self.order1.status = "confirmed"
        self.order1.save()
        
        # Call Shiprocket Webhook
        url = reverse('orders:shiprocket_webhook')
        payload = {
            "awb": "SR123456789",
            "current_status": "Out for Delivery"
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify status updated
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, "out_for_delivery")
        
        # Verify log entry created
        log = OrderStatusLog.objects.filter(order=self.order1).order_by('-timestamp').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.new_status, "out_for_delivery")
        self.assertIn("Shiprocket Webhook", log.remarks)

    def test_seller_update_status_success(self):
        """Seller can successfully update order status to processing and shipped."""
        self.client.login(phone="8888888888", password="sellerpassword")
        
        # Test transition to processing
        url = reverse('orders:seller_update_status', args=[self.order1.unique_order_id])
        response = self.client.post(
            url,
            data=json.dumps({"status": "processing"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, "processing")
        
        # Test transition to shipped
        response = self.client.post(
            url,
            data=json.dumps({"status": "shipped"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, "shipped")

    def test_admin_update_status_success(self):
        """Admin can successfully update any order status."""
        self.client.login(phone="9999999999", password="adminpassword")
        url = reverse('orders:admin_update_status', args=[self.order1.unique_order_id])
        response = self.client.post(
            url,
            data=json.dumps({"status": "confirmed"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.status, "confirmed")

    def test_admin_order_change_page_loads(self):
        """Standard Django admin order detail page should load successfully."""
        self.client.login(phone="9999999999", password="adminpassword")
        url = reverse('admin:orders_order_change', args=[self.order1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
