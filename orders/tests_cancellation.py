from django.test import TestCase
from django.urls import reverse
from unittest import mock
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import json

from accounts.models import Wallet
from items.models import Category, Product, SellerProfile
from orders.models import Order, OrderItem, OrderStatusLog, SystemActivityLog

User = get_user_model()

class CancellationTests(TestCase):
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
            total=Decimal("100.00"),
            status="confirmed"
        )

    def test_seller_cancel_own_items_success(self):
        """Seller cancels their own item successfully, updating stocks and overall status."""
        self.client.login(phone="8888888888", password="sellerpassword")
        
        url = reverse('orders:authorized_cancel_order', args=[self.order1.unique_order_id])
        data = {
            "item_ids": [self.item1_1.id],
            "reason": "out_of_stock",
            "remarks": "Not able to process this order item"
        }
        
        with mock.patch('delivery.delivery_services.ShiprocketService.cancel_shipment') as mock_cancel:
            mock_cancel.return_value = {"success": True}
            
            response = self.client.post(url, data=json.dumps(data), content_type="application/json")
            self.assertEqual(response.status_code, 200)
            
            # Verify response message
            res_data = response.json()
            self.assertEqual(res_data['status'], 'success')
            
            # Verify stock was restocked: 10 + 1 = 11
            self.product1.refresh_from_db()
            self.assertEqual(self.product1.stock, 11)
            
            # Verify item status is cancelled
            self.item1_1.refresh_from_db()
            self.assertEqual(self.item1_1.status, 'cancelled')
            
            # Verify other item is unaffected
            self.item1_2.refresh_from_db()
            self.assertEqual(self.item1_2.status, 'pending')
            
            # Verify overall status of order 1 remains 'pending' because item1_2 is still 'pending'
            self.order1.refresh_from_db()
            self.assertEqual(self.order1.status, 'pending')

    def test_seller_cancel_unauthorized_item(self):
        """Seller tries to cancel an item belonging to another seller, returns 403."""
        self.client.login(phone="8888888888", password="sellerpassword")
        
        url = reverse('orders:authorized_cancel_order', args=[self.order1.unique_order_id])
        data = {
            "item_ids": [self.item1_2.id],  # item1_2 belongs to seller 2
            "reason": "out_of_stock",
            "remarks": "Attempting to cancel someone else's item"
        }
        
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertIn("not authorized", response.json()['message'])

    def test_seller_cancel_invalid_status(self):
        """Seller tries to cancel an item that is already shipped, returns 400."""
        self.client.login(phone="8888888888", password="sellerpassword")
        
        # Change item status to shipped
        self.item1_1.status = 'shipped'
        self.item1_1.save()
        
        url = reverse('orders:authorized_cancel_order', args=[self.order1.unique_order_id])
        data = {
            "item_ids": [self.item1_1.id],
            "reason": "out_of_stock",
            "remarks": "Try to cancel shipped item"
        }
        
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("already", response.json()['message'])

    def test_admin_cancel_any_status_success(self):
        """Admin can cancel items at any active status (e.g. shipped)."""
        self.client.login(phone="9999999999", password="adminpassword")
        
        # Change item status to shipped
        self.item1_1.status = 'shipped'
        self.item1_1.save()
        
        url = reverse('orders:authorized_cancel_order', args=[self.order1.unique_order_id])
        data = {
            "item_ids": [self.item1_1.id],
            "reason": "changed_mind",
            "remarks": "Admin overrides and cancels shipped item"
        }
        
        with mock.patch('delivery.delivery_services.ShiprocketService.cancel_shipment') as mock_cancel:
            mock_cancel.return_value = {"success": True}
            
            response = self.client.post(url, data=json.dumps(data), content_type="application/json")
            self.assertEqual(response.status_code, 200)
            
            self.item1_1.refresh_from_db()
            self.assertEqual(self.item1_1.status, 'cancelled')

    def test_prepaid_wallet_refund(self):
        """Prepaid wallet order cancellation instantly refunds the customer's wallet balance."""
        self.client.login(phone="9999999999", password="adminpassword")
        
        # Create user wallet
        wallet = Wallet.objects.create(user=self.customer, balance=Decimal("10.00"))
        
        url = reverse('orders:authorized_cancel_order', args=[self.order2.unique_order_id])
        data = {
            "item_ids": [self.item2_1.id],
            "reason": "changed_mind",
            "remarks": "Cancel wallet paid order"
        }
        
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        
        # Verify wallet balance was updated: 10 + 100 = 110
        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal("110.00"))
        
        # Verify order refund amount and status
        self.order2.refresh_from_db()
        self.assertEqual(self.order2.refund_amount, Decimal("100.00"))
        self.assertEqual(self.order2.payment_status, 'refunded')
        self.assertEqual(self.order2.status, 'cancelled')

    @mock.patch('orders.views.get_razorpay_client')
    def test_prepaid_razorpay_refund(self, mock_get_client):
        """Prepaid razorpay order cancellation triggers live Razorpay API refund."""
        self.client.login(phone="9999999999", password="adminpassword")
        
        # Set order2 to razorpay paid
        self.order2.payment_method = 'razorpay'
        self.order2.razorpay_payment_id = 'pay_mock123'
        self.order2.save()
        
        # Setup razorpay mock client
        mock_client = mock.MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.refund.create.return_value = {'id': 'rfnd_mock999'}
        
        url = reverse('orders:authorized_cancel_order', args=[self.order2.unique_order_id])
        data = {
            "item_ids": [self.item2_1.id],
            "reason": "changed_mind",
            "remarks": "Cancel razorpay paid order"
        }
        
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        
        # Verify Razorpay refund API was called with the correct parameters
        mock_client.refund.create.assert_called_once_with({
            'payment_id': 'pay_mock123',
            'amount': 10000,  # 100.00 * 100
            'notes': {
                'order_id': self.order2.unique_order_id,
                'reason': 'Cancelled by Admin: changed_mind',
                'initiated_by': self.admin_user.phone
            }
        })
        
        # Verify order refund id and amount
        self.order2.refresh_from_db()
        self.assertEqual(self.order2.razorpay_refund_id, 'rfnd_mock999')
        self.assertEqual(self.order2.refund_amount, Decimal("100.00"))
        self.assertEqual(self.order2.payment_status, 'refunded')
        self.assertEqual(self.order2.status, 'cancelled')
