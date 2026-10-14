from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal
from items.models import Category, Product, ProductVariant, SellerProfile
from items.forms import ProductForm

User = get_user_model()

class ProductCalculationAndStockTests(TestCase):
    def setUp(self):
        # Create a verified seller user
        self.seller_user = User.objects.create_user(
            phone="8888888888",
            password="sellerpassword",
            role="seller",
            full_name="Test Seller"
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Test Shop",
            is_verified=True
        )
        
        # Create a category with a commission percentage
        self.category = Category.objects.create(
            name="Clothing", 
            commision_percentage=15.0  # 15% commission
        )

    def test_product_calculations_and_margins(self):
        """Test final price, savings, and profit margin calculations with and without discounts."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Classic Tee",
            price=Decimal("100.00"),
            mrp=Decimal("150.00"),
            cost_price=Decimal("50.00"),
            discount_percent=20,  # 20% off
            stock=10,
            status="published"
        )
        
        # 1. Final Price: 100 - 20% = 80.00
        self.assertEqual(product.final_price, Decimal("80.00"))
        
        # 2. Savings: MRP (150) - Final Price (80) = 70.00
        self.assertEqual(product.savings, Decimal("70.00"))
        self.assertEqual(product.calculate_savings(3), Decimal("210.00"))
        
        # 3. Commission: 15% of Final Price (80.00) = 12.00
        self.assertEqual(product.admin_commission, Decimal("12.00"))
        
        # 4. Net Profit: Final Price (80) - Commission (12) - Cost Price (50) = 18.00
        self.assertEqual(product.seller_profit, Decimal("18.00"))
        
        # 5. Seller Profit Margin: Profit (18) / Final Price (80) * 100 = 22.5%
        self.assertEqual(product.seller_profit_margin, Decimal("22.5"))
        
        # 6. Simple Profit Margin (based on discounted final price): (80 - 50) / 80 * 100 = 37.5%
        self.assertEqual(product.profit_margin, Decimal("37.5"))

    def test_stock_sync_with_variants(self):
        """Verify parent product stock updates dynamically on variant creation, modification, and deletion."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Sneakers",
            price=Decimal("100.00"),
            stock=0,
            status="draft"
        )
        
        # Initially 0 stock
        self.assertEqual(product.stock, 0)
        
        # 1. Add variant 1 (size M, stock 5)
        variant1 = ProductVariant.objects.create(
            product=product,
            size_value="M",
            stock=5,
            is_active=True
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, 5)
        self.assertEqual(product.status, "draft") # draft state remains preserved
        
        # 2. Add variant 2 (size L, stock 8)
        variant2 = ProductVariant.objects.create(
            product=product,
            size_value="L",
            stock=8,
            is_active=True
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, 13)
        
        # 3. Update variant stock
        variant1.stock = 10
        variant1.save()
        product.refresh_from_db()
        self.assertEqual(product.stock, 18)
        
        # 4. Deactivating variant removes its stock from parent sum
        variant2.is_active = False
        variant2.save()
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)
        
        # 5. Delete variant and assert parent stock updates correctly
        variant1.delete()
        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertEqual(product.status, "out_of_stock")

    def test_product_base_save_keeps_variant_stock(self):
        """Saving base product details without touching variants should not corrupt variants-derived stock."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Jeans",
            price=Decimal("120.00"),
            stock=0,
            status="published"
        )
        
        ProductVariant.objects.create(
            product=product,
            size_value="32",
            stock=15,
            is_active=True
        )
        
        product.refresh_from_db()
        self.assertEqual(product.stock, 15)
        
        # Simulate form save of base product details
        product.name = "Premium Jeans"
        product.save()
        
        product.refresh_from_db()
        # Stock should remain 15, not be reset to 0 or manual value
        self.assertEqual(product.stock, 15)

    def test_variant_pricing_and_discount_calculations(self):
        """Verify variant pricing, mrp, discount percentage, and savings calculations."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Cotton T-Shirt",
            price=Decimal("100.00"),
            mrp=Decimal("100.00"),
            discount_percent=55,
            cost_price=Decimal("43.00"),
            stock=0,
            status="published"
        )
        
        # Base product pricing assertions
        self.assertEqual(product.price, Decimal("100.00"))
        self.assertEqual(product.mrp, Decimal("100.00"))
        self.assertEqual(product.discount_percent, 55)
        self.assertEqual(product.final_price, Decimal("45.00"))
        self.assertEqual(product.savings_per_unit, Decimal("55.00"))
        
        # Variant 1: Inherits base price (no override)
        v1 = ProductVariant.objects.create(
            product=product,
            size_value="80 cm",
            stock=10,
            is_active=True
        )
        self.assertEqual(v1.effective_price, Decimal("100.00"))
        self.assertEqual(v1.mrp, Decimal("100.00"))
        self.assertEqual(v1.discount_percent, 55)
        self.assertEqual(v1.final_price, Decimal("45.00"))
        self.assertEqual(v1.savings_per_unit, Decimal("55.00"))
        
        # Variant 2: Custom price override (e.g., larger size costs 120 base)
        v2 = ProductVariant.objects.create(
            product=product,
            size_value="95 cm",
            price_override=Decimal("120.00"),
            stock=10,
            is_active=True
        )
        self.assertEqual(v2.effective_price, Decimal("120.00"))
        self.assertEqual(v2.mrp, Decimal("120.00"))
        self.assertEqual(v2.discount_percent, 55)
        self.assertEqual(v2.final_price, Decimal("54.00"))
        self.assertEqual(v2.savings_per_unit, Decimal("66.00"))

    def test_product_variant_deletion_via_formset(self):
        """Verify that a variant can be marked for deletion and saved successfully via product edit/formset."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Tshirt",
            price=Decimal("10.00"),
            stock=10,
            status="published"
        )
        
        v1 = ProductVariant.objects.create(
            product=product,
            size_value="M",
            stock=4,
            is_active=True
        )
        v2 = ProductVariant.objects.create(
            product=product,
            size_value="L",
            stock=6,
            is_active=True
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)
        self.assertEqual(product.variants.count(), 2)
        
        # Simulate POST request to edit product with variant deletion
        # In Django formsets, to delete a form, we set DELETE=on and provide the id
        post_data = {
            'name': 'Tshirt',
            'category': self.category.id,
            'price': '4.00',
            'cost_price': '1.00',
            'discount_percent': '0',
            'stock': '4',  # Set base stock to 4 (sum of remaining active variants)
            'low_stock_threshold': '1',
            'status': 'published',
            'description': 'Product description long enough...',
            'variants-TOTAL_FORMS': '2',
            'variants-INITIAL_FORMS': '2',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
            
            # Form 0: keep active
            'variants-0-id': str(v1.id),
            'variants-0-size_value': 'M',
            'variants-0-size_type': 'clothing',
            'variants-0-color': '',
            'variants-0-price_override': '',
            'variants-0-stock': '4',
            'variants-0-is_active': 'on',
            'variants-0-DELETE': '',
            
            # Form 1: delete
            'variants-1-id': str(v2.id),
            'variants-1-size_value': 'L',
            'variants-1-size_type': 'clothing',
            'variants-1-color': '',
            'variants-1-price_override': '',
            'variants-1-stock': '6',
            'variants-1-is_active': 'on',
            'variants-1-DELETE': 'on',
        }
        
        self.client.login(phone="8888888888", password="sellerpassword")
        response = self.client.post(f'/items/product/{product.id}/edit/', post_data)
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        
        product.refresh_from_db()
        # v2 should be deleted, so only 1 variant left
        self.assertEqual(product.variants.count(), 1)
        self.assertFalse(ProductVariant.objects.filter(id=v2.id).exists())
        self.assertTrue(ProductVariant.objects.filter(id=v1.id).exists())
        
        # Stock should sync to v1's stock, i.e., 4
        self.assertEqual(product.stock, 4)

    def test_product_variant_protected_delete(self):
        """Verify that a variant referenced by an OrderItem is soft-deleted instead of raising ProtectedError."""
        # 1. Create a product and two variants
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Sweater",
            price=Decimal("20.00"),
            stock=10,
            status="published"
        )
        v1 = ProductVariant.objects.create(
            product=product,
            size_value="M",
            stock=4,
            is_active=True
        )
        v2 = ProductVariant.objects.create(
            product=product,
            size_value="L",
            stock=6,
            is_active=True
        )
        
        # 2. Place an order containing v2 (to trigger ProtectedError on delete)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        customer = User.objects.create_user(phone="9999999999", password="customerpassword")
        
        from orders.models import Order, OrderItem
        order = Order.objects.create(
            user=customer,
            unique_order_id="ORD-TEST-12345",
            total_amount=Decimal("120.00"),
            payment_status="paid"
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            variant=v2,
            seller=self.seller_profile,
            quantity=1,
            price=Decimal("20.00"),
            total=Decimal("20.00")
        )
        
        # 3. POST to delete both variants: v1 (no orders) and v2 (ordered)
        post_data = {
            'name': 'Sweater',
            'category': self.category.id,
            'price': '20.00',
            'cost_price': '10.00',
            'discount_percent': '0',
            'stock': '0',  # v1 deleted, v2 soft-deleted and deactivated, so active variants stock sum is 0
            'low_stock_threshold': '1',
            'status': 'published',
            'description': 'Product description long enough...',
            'variants-TOTAL_FORMS': '2',
            'variants-INITIAL_FORMS': '2',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
            
            # v1: delete
            'variants-0-id': str(v1.id),
            'variants-0-size_value': 'M',
            'variants-0-size_type': 'clothing',
            'variants-0-color': '',
            'variants-0-price_override': '',
            'variants-0-stock': '4',
            'variants-0-is_active': 'on',
            'variants-0-DELETE': 'on',
            
            # v2: delete
            'variants-1-id': str(v2.id),
            'variants-1-size_value': 'L',
            'variants-1-size_type': 'clothing',
            'variants-1-color': '',
            'variants-1-price_override': '',
            'variants-1-stock': '6',
            'variants-1-is_active': 'on',
            'variants-1-DELETE': 'on',
        }
        
        self.client.login(phone="8888888888", password="sellerpassword")
        response = self.client.post(f'/items/product/{product.id}/edit/', post_data)
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        
        # v1 (no orders) should be hard deleted
        self.assertFalse(ProductVariant.objects.filter(id=v1.id).exists())
        
        # v2 (ordered) should still exist, but be soft-deleted
        # ProductVariant.objects filters by is_deleted=False, so v2 is not visible in standard queries
        self.assertFalse(ProductVariant.objects.filter(id=v2.id).exists())
        
        # But ProductVariant.all_objects should contain it
        v2_from_db = ProductVariant.all_objects.get(id=v2.id)
        self.assertTrue(v2_from_db.is_deleted)
        self.assertFalse(v2_from_db.is_active)
        self.assertIn("deleted-", v2_from_db.size_value)

    def test_cost_price_validation(self):
        """Form must reject negative cost prices."""
        form_data = {
            'name': 'Invalid Cost Product',
            'description': 'This is a description of the sneakers.',
            'price': 100.00,
            'cost_price': -10.00,  # Negative, should fail
            'discount_percent': 0,
            'stock': 10,
            'low_stock_threshold': 3,
            'status': 'draft',
            'category': self.category.id,
        }
        form = ProductForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('cost_price', form.errors)
        self.assertEqual(form.errors['cost_price'][0], 'Cost price must be greater than 0.')

        # Correct cost price should pass
        form_data['cost_price'] = 60.00
        form = ProductForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_product_variant_inactive_via_formset(self):
        """Verify that an inactive variant's stock is excluded from sum validation and parent stock updates."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Boot",
            price=Decimal("15.00"),
            stock=10,
            status="published"
        )
        v1 = ProductVariant.objects.create(
            product=product,
            size_value="9",
            stock=4,
            is_active=True
        )
        v2 = ProductVariant.objects.create(
            product=product,
            size_value="10",
            stock=6,
            is_active=True
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, 10)

        # POST data marking v2 as inactive, base stock set to 4 (sum of active M=4)
        post_data = {
            'name': 'Boot',
            'category': self.category.id,
            'price': '15.00',
            'cost_price': '5.00',
            'discount_percent': '0',
            'stock': '4',  # sum of active variants (v1 stock = 4, v2 is inactive so ignored)
            'low_stock_threshold': '1',
            'status': 'published',
            'description': 'Description text long enough...',
            'variants-TOTAL_FORMS': '2',
            'variants-INITIAL_FORMS': '2',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
            
            # Form 0: v1 remains active
            'variants-0-id': str(v1.id),
            'variants-0-size_value': '9',
            'variants-0-size_type': 'footwear',
            'variants-0-color': '',
            'variants-0-price_override': '',
            'variants-0-stock': '4',
            'variants-0-is_active': 'on',
            'variants-0-DELETE': '',
            
            # Form 1: v2 is inactive (is_active is not 'on')
            'variants-1-id': str(v2.id),
            'variants-1-size_value': '10',
            'variants-1-size_type': 'footwear',
            'variants-1-color': '',
            'variants-1-price_override': '',
            'variants-1-stock': '6',
            'variants-1-is_active': '',  # Inactive
            'variants-1-DELETE': '',
        }
        self.client.login(phone="8888888888", password="sellerpassword")
        response = self.client.post(f'/items/product/{product.id}/edit/', post_data)
        
        # Should succeed and redirect
        self.assertEqual(response.status_code, 302)
        
        product.refresh_from_db()
        v1.refresh_from_db()
        v2.refresh_from_db()
        
        # Parent stock should only include active variants (v1 only = 4)
        self.assertEqual(product.stock, 4)
        self.assertTrue(v1.is_active)
        self.assertFalse(v2.is_active)

    def test_variant_empty_attributes_formset_save(self):
        """Verify that submitting an empty/blank attributes field on a variant does not raise IntegrityError."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Boot",
            price=Decimal("15.00"),
            stock=4,
            status="published"
        )
        v1 = ProductVariant.objects.create(
            product=product,
            size_value="9",
            stock=4,
            is_active=True
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, 4)

        # POST data sending empty attributes string (e.g. from seller form hidden input)
        post_data = {
            'name': 'Boot',
            'category': self.category.id,
            'price': '15.00',
            'cost_price': '5.00',
            'discount_percent': '0',
            'stock': '4',
            'low_stock_threshold': '1',
            'status': 'published',
            'description': 'Description text long enough...',
            'variants-TOTAL_FORMS': '1',
            'variants-INITIAL_FORMS': '1',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
            
            'variants-0-id': str(v1.id),
            'variants-0-size_value': '9',
            'variants-0-size_type': 'footwear',
            'variants-0-color': '',
            'variants-0-price_override': '',
            'variants-0-stock': '4',
            'variants-0-is_active': 'on',
            'variants-0-attributes': '',  # Submitted as empty string
            'variants-0-DELETE': '',
        }
        self.client.login(phone="8888888888", password="sellerpassword")
        response = self.client.post(f'/items/product/{product.id}/edit/', post_data)
        
        # Should succeed and redirect
        self.assertEqual(response.status_code, 302)
        
        v1.refresh_from_db()
        # attributes should default/fallback to an empty dictionary
        self.assertEqual(v1.attributes, {})

    def test_variant_custom_attributes_formset_save(self):
        """Verify that submitting a valid JSON custom attribute on a variant saves it successfully in the DB."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Saree",
            price=Decimal("990.00"),
            stock=3,
            status="published"
        )
        v1 = ProductVariant.objects.create(
            product=product,
            size_value="Free Size",
            stock=3,
            is_active=True,
            attributes={"fabric": "Premium Silk"}
        )
        
        post_data = {
            'seller': str(self.seller_profile.id),
            'name': 'Saree',
            'category': self.category.id,
            'price': '990.00',
            'cost_price': '500.00',
            'discount_percent': '0',
            'stock': '3',
            'low_stock_threshold': '1',
            'status': 'published',
            'description': 'Elegant purple shimmer saree...',
            'variants-TOTAL_FORMS': '1',
            'variants-INITIAL_FORMS': '1',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
            
            'variants-0-id': str(v1.id),
            'variants-0-size_value': 'Free Size',
            'variants-0-size_type': 'clothing',
            'variants-0-color': 'Purple',
            'variants-0-price_override': '',
            'variants-0-stock': '3',
            'variants-0-is_active': 'on',
            'variants-0-attributes': '{"fabric": "Premium Shimmer Fabric", "fit": "Free Size"}',
            'variants-0-DELETE': '',
        }
        
        admin_user = User.objects.create_superuser(
            phone="7777777777",
            password="adminpassword",
            role="admin",
            full_name="Admin User"
        )
        self.client.login(phone="7777777777", password="adminpassword")
        response = self.client.post(f'/items/product/{product.id}/edit/', post_data)
        
        # Should succeed and redirect
        self.assertEqual(response.status_code, 302)
        
        v1.refresh_from_db()
        # attributes should be updated to the new JSON dictionary
        self.assertEqual(v1.attributes, {"fabric": "Premium Shimmer Fabric", "fit": "Free Size"})

    def test_variant_delete_and_add_stock_sync_in_views(self):
        """Verify that when editing a product, deleting an old variant and adding a new variant works successfully, and parent stock is correctly updated to match only the active variants in the DB (preventing stale prefetch/cache issues)."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Kurti",
            price=Decimal("499.00"),
            stock=5,
            status="published"
        )
        v1 = ProductVariant.objects.create(
            product=product,
            size_value="M",
            stock=5,
            is_active=True
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, 5)

        # POST data: delete v1 (M, stock 5) and add new variant v2 (L, stock 3)
        # Total active variant stock will be 3, so base stock should be 3
        post_data = {
            'name': 'Kurti',
            'category': self.category.id,
            'price': '499.00',
            'cost_price': '200.00',
            'discount_percent': '0',
            'stock': '3',  # New expected base stock
            'low_stock_threshold': '1',
            'status': 'published',
            'description': 'Description text long enough...',
            'variants-TOTAL_FORMS': '2',
            'variants-INITIAL_FORMS': '1',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '1000',
            
            # v1 (deleted)
            'variants-0-id': str(v1.id),
            'variants-0-size_value': 'M',
            'variants-0-size_type': 'clothing',
            'variants-0-color': '',
            'variants-0-price_override': '',
            'variants-0-stock': '5',
            'variants-0-is_active': 'on',
            'variants-0-DELETE': 'on',  # Check DELETE
            
            # v2 (new)
            'variants-1-id': '',
            'variants-1-size_value': 'L',
            'variants-1-size_type': 'clothing',
            'variants-1-color': '',
            'variants-1-price_override': '',
            'variants-1-stock': '3',
            'variants-1-is_active': 'on',
            'variants-1-DELETE': '',
        }
        self.client.login(phone="8888888888", password="sellerpassword")
        response = self.client.post(f'/items/product/{product.id}/edit/', post_data)
        
        # Should succeed and redirect
        self.assertEqual(response.status_code, 302)
        
        # Verify database state
        self.assertFalse(ProductVariant.objects.filter(id=v1.id).exists()) # v1 is hard-deleted
        self.assertEqual(ProductVariant.objects.filter(product=product).count(), 1) # only v2 exists
        
        v2 = ProductVariant.objects.get(product=product)
        self.assertEqual(v2.size_value, "L")
        self.assertEqual(v2.stock, 3)
        
        product.refresh_from_db()
        self.assertEqual(product.stock, 3)
        self.assertEqual(product.status, "published")

    def test_mobile_price_display_order_in_product_list_and_home(self):
        """Verify that product cards display selling price BEFORE MRP so mobile view displays selling price first."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Wireless Mouse",
            price=Decimal("798.00"),
            mrp=Decimal("798.00"),
            discount_percent=50,
            stock=5,
            status="published"
        )
        response = self.client.get('/products/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        # In HTML, price-current (399) should appear before price-mrp (798)
        current_pos = content.find('price-current">₹399')
        mrp_pos = content.find('price-mrp">₹798')
        self.assertNotEqual(current_pos, -1)
        self.assertNotEqual(mrp_pos, -1)
        self.assertLess(current_pos, mrp_pos, "Selling price must be rendered before MRP in price-row")

    def test_customer_pays_preview_in_product_form(self):
        """Verify that product form renders customer price preview box and no redundant customerPaysInput field."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Smart Keyboard",
            price=Decimal("1000.00"),
            mrp=Decimal("1000.00"),
            discount_percent=20,
            stock=5,
            status="published"
        )
        self.client.login(phone="8888888888", password="sellerpassword")
        response = self.client.get(f'/items/product/{product.id}/edit/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        # Preview elements must exist
        self.assertIn('id="pricePreview"', content)
        self.assertIn('id="previewPrice"', content)
        self.assertIn('Customer Pays:', content)
        # Redundant customerPaysInput should NOT exist
        self.assertNotIn('id="customerPaysInput"', content)
        self.assertNotIn('name="customer_pay"', content)
        # Verify model calculates discount_price correctly
        self.assertEqual(product.discount_price, Decimal("800.00"))



class ProductAndSellerReviewTests(TestCase):
    def setUp(self):
        # Create a verified seller user
        self.seller_user = User.objects.create_user(
            phone="9999999999",
            password="sellerpassword",
            role="seller",
            full_name="Review Seller"
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Review Shop",
            is_verified=True
        )
        self.category = Category.objects.create(
            name="Electronics",
            commision_percentage=10.0
        )
        self.product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Smartphone",
            price=Decimal("500.00"),
            stock=10,
            status="published"
        )
        self.customer = User.objects.create_user(
            phone="7777777777",
            password="customerpassword",
            role="customer",
            full_name="Customer User"
        )

    def test_validate_video_size(self):
        """Test that validate_video_size allows small videos and raises ValidationError for > 20MB."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from items.models import validate_video_size
        
        # Small file (1MB)
        small_file = SimpleUploadedFile("small.mp4", b"x" * (1 * 1024 * 1024))
        try:
            validate_video_size(small_file)
        except ValidationError:
            self.fail("validate_video_size raised ValidationError on 1MB file unexpectedly.")
            
        # Large file (21MB)
        large_file = SimpleUploadedFile("large.mp4", b"x" * (21 * 1024 * 1024))
        with self.assertRaises(ValidationError) as ctx:
            validate_video_size(large_file)
        self.assertEqual(str(ctx.exception.messages[0]), "Video file size cannot exceed 20MB.")

    def test_product_review_cache(self):
        """Test Product rating_avg and review_count are updated on save and delete."""
        from items.models import ProductReview
        
        self.assertEqual(self.product.rating_avg, Decimal("0.0"))
        self.assertEqual(self.product.review_count, 0)
        
        # Add a review
        review1 = ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=4,
            title="Good",
            review="This is a good product with more than twenty characters."
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_avg, Decimal("4.00"))
        self.assertEqual(self.product.review_count, 1)
        
        # Add another user and review
        another_customer = User.objects.create_user(
            phone="6666666666",
            password="customerpassword",
            role="customer",
            full_name="Another Customer"
        )
        review2 = ProductReview.objects.create(
            product=self.product,
            user=another_customer,
            rating=5,
            title="Excellent",
            review="This is an excellent product with more than twenty characters."
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_avg, Decimal("4.50"))
        self.assertEqual(self.product.review_count, 2)
        
        # Delete first review
        review1.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.rating_avg, Decimal("5.00"))
        self.assertEqual(self.product.review_count, 1)

    def test_seller_review_cache(self):
        """Test SellerProfile rating is updated on save and delete."""
        from items.models import SellerReview
        
        self.assertEqual(self.seller_profile.rating, Decimal("0.0"))
        
        # Add seller review
        review1 = SellerReview.objects.create(
            seller=self.seller_profile,
            user=self.customer,
            rating=3,
            title="Fair seller",
            review="The packaging was good and seller was nice enough."
        )
        self.seller_profile.refresh_from_db()
        self.assertEqual(self.seller_profile.rating, Decimal("3.0"))
        
        # Add another user and review
        another_customer = User.objects.create_user(
            phone="5555555555",
            password="customerpassword",
            role="customer",
            full_name="Yet Another Customer"
        )
        review2 = SellerReview.objects.create(
            seller=self.seller_profile,
            user=another_customer,
            rating=5,
            title="Great seller",
            review="Perfect communication, very fast shipping. Thank you!"
        )
        self.seller_profile.refresh_from_db()
        self.assertEqual(self.seller_profile.rating, Decimal("4.0"))
        
        # Delete first review
        review1.delete()
        self.seller_profile.refresh_from_db()
        self.assertEqual(self.seller_profile.rating, Decimal("5.0"))

    def test_verified_purchase_checks(self):
        """Test that is_verified_purchase checks if user actually bought/delivered from the product/seller."""
        from items.models import ProductReview, SellerReview
        from orders.models import Order, OrderItem
        
        # Scenario 1: Review without purchase
        p_review = ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=4,
            review="I never bought this item but I can write a review anyway."
        )
        self.assertFalse(p_review.is_verified_purchase)
        
        s_review = SellerReview.objects.create(
            seller=self.seller_profile,
            user=self.customer,
            rating=4,
            review="I never bought from this seller but I am rating them."
        )
        self.assertFalse(s_review.is_verified_purchase)
        
        # Clean up
        p_review.delete()
        s_review.delete()
        
        # Scenario 2: Review with delivered order
        order = Order.objects.create(
            user=self.customer,
            total_amount=Decimal("500.00"),
            payment_status="paid",
            status="delivered"
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            seller=self.seller_profile,
            quantity=1,
            price=Decimal("500.00"),
            total=Decimal("500.00")
        )
        
        # Now review
        p_review = ProductReview.objects.create(
            product=self.product,
            user=self.customer,
            rating=5,
            review="This smartphone is absolutely amazing. Highly recommended!"
        )
        self.assertTrue(p_review.is_verified_purchase)
        
        s_review = SellerReview.objects.create(
            seller=self.seller_profile,
            user=self.customer,
            rating=5,
            review="Seller packed it very securely. Fast delivery!"
        )
        self.assertTrue(s_review.is_verified_purchase)

    def test_review_forms_validation(self):
        """Test forms validate rating and character lengths."""
        from items.forms import ProductReviewForm, SellerReviewForm
        
        # Form check: review too short (< 20 chars)
        form = ProductReviewForm(data={
            'rating': 4,
            'title': 'Short review',
            'review': 'Too short'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('review', form.errors)
        self.assertEqual(form.errors['review'][0], 'Review must be at least 20 characters')
        
        # Form check: correct review passes
        form = ProductReviewForm(data={
            'rating': 4,
            'title': 'Long enough review',
            'review': 'This is a long enough review that has more than twenty characters.'
        })
        self.assertTrue(form.is_valid())
        
        # Seller form check: review too short
        s_form = SellerReviewForm(data={
            'rating': 3,
            'title': 'Short',
            'review': 'Not enough'
        })
        self.assertFalse(s_form.is_valid())
        self.assertIn('review', s_form.errors)
        
        # Seller form check: correct review passes
        s_form = SellerReviewForm(data={
            'rating': 3,
            'title': 'Long enough',
            'review': 'This is a long enough seller review with at least 20 characters.'
        })
        self.assertTrue(s_form.is_valid())


class CategoryIconTests(TestCase):
    def test_category_icon_field(self):
        """Test that Category model accepts an icon and slugifies name successfully."""
        category = Category.objects.create(
            name="Accessories",
            commision_percentage=5.0
        )
        self.assertEqual(category.slug, "accessories")
        self.assertFalse(category.icon)
        
        # Test updating icon
        from django.core.files.uploadedfile import SimpleUploadedFile
        icon_file = SimpleUploadedFile("icon.png", b"file_content", content_type="image/png")
        category.icon = icon_file
        category.save()
        
        category.refresh_from_db()
        self.assertTrue(category.icon)
        self.assertTrue(category.icon.name.startswith("category_icons/icon"))


class SellerBankDetailsRestrictionTests(TestCase):
    def setUp(self):
        self.seller_user = User.objects.create_user(
            phone="9000000000",
            password="sellerpassword",
            role="seller",
            full_name="Dashboard Seller"
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Seller Shop Ltd",
            pan_verification_status="verified"
        )
        self.category = Category.objects.create(
            name="Toys",
            commision_percentage=10.0
        )

    def test_seller_without_bank_details_is_restricted(self):
        """Test that a seller without bank details is blocked from product creation views/endpoints."""
        self.client.login(phone="9000000000", password="sellerpassword")
        
        # 1. Accessing product_create view should redirect to profile
        response = self.client.get('/items/product/add/')
        self.assertRedirects(response, '/accounts/profile/')
        
        # 2. AJAX endpoint save_product should return 400 Bad Request
        save_response = self.client.post('/items/seller/dashboard/save/', {
            'name': 'Toy Car',
            'category': self.category.id,
            'price': '99.99',
            'stock': '10',
            'status': 'draft',
            'description': 'This is a description of the toy car.',
            'discount_percent': '0',
            'low_stock_threshold': '5'
        })
        self.assertEqual(save_response.status_code, 400)
        self.assertEqual(save_response.json()['status'], 'error')
        self.assertIn('bank details', save_response.json()['message'].lower())

    def test_seller_with_bank_details_can_create_product(self):
        """Test that a seller who completed bank details can create/save products."""
        self.seller_profile.refresh_from_db()
        
        # Add bank details
        self.seller_profile.bank_name = "State Bank of India"
        self.seller_profile.account_number = "12345678901"
        self.seller_profile.ifsc_code = "SBIN0001234"
        self.seller_profile.account_holder_name = "Dashboard Seller"
        self.seller_profile.save()
        
        self.seller_profile.refresh_from_db()

        self.client.login(phone="9000000000", password="sellerpassword")

        # 1. Accessing product_create view should return 200 OK
        response = self.client.get('/items/product/add/')
        self.assertEqual(response.status_code, 200)

        # 2. AJAX endpoint save_product should return 200 OK / success
        save_response = self.client.post('/items/seller/dashboard/save/', {
            'name': 'Toy Plane',
            'category': self.category.id,
            'price': '199.99',
            'stock': '5',
            'status': 'draft',
            'description': 'This is a description of the toy plane.',
            'discount_percent': '0',
            'low_stock_threshold': '5'
        })
        self.assertEqual(save_response.status_code, 200)
        self.assertEqual(save_response.json()['status'], 'success')


class ProductListPaginationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        from items.models import Category, SellerProfile, Product
        from django.urls import reverse
        
        from common.models import _thread_locals
        _thread_locals.user = None
        
        self.seller_user = User.objects.create_user(
            phone="9000000000",
            password="sellerpassword",
            role="seller",
            full_name="Dashboard Seller"
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Seller Shop Ltd",
            is_verified=True,
            bank_name="SBI",
            account_number="123456",
            ifsc_code="SBIN0001234",
            account_holder_name="Dashboard Seller"
        )
        self.category = Category.objects.create(
            name="Toys",
            commision_percentage=10.0
        )
        
        # Create 20 published, in-stock products
        for i in range(20):
            Product.objects.create(
                seller=self.seller_profile,
                category=self.category,
                name=f"Product {i}",
                price=10.0 + i,
                stock=5,
                status="published"
            )
            
    def test_admin_dashboard_pagination(self):
        from django.urls import reverse
        self.client.login(phone="9000000000", password="sellerpassword")
        url = reverse('items:admin_dashboard')
        
        # Default page size is 10
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['products']), 10)
        self.assertEqual(response.context['products'].paginator.count, 20)
        
        # Request page 2
        response = self.client.get(f"{url}?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['products']), 10)
        
    def test_public_product_list_pagination(self):
        from django.urls import reverse
        url = reverse('items:product_list')
        
        # Default page size is 15 for public product_list
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['products']), 15)
        self.assertEqual(response.context['page_obj'].paginator.count, 20)
        self.assertTrue(response.context['is_paginated'])
        
        # Request page 2
        response = self.client.get(f"{url}?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['products']), 5)


class ProductSlugLengthAndUniquenessTests(TestCase):
    def setUp(self):
        # Create a verified seller user
        self.seller_user = User.objects.create_user(
            phone="8888888888",
            password="sellerpassword",
            role="seller",
            full_name="Test Seller"
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Test Shop",
            is_verified=True
        )
        
        # Create a category with a commission percentage
        self.category = Category.objects.create(
            name="Clothing", 
            commision_percentage=15.0  # 15% commission
        )

    def test_extremely_long_product_name_slug_truncation(self):
        """Verify that a product with a name longer than 255 characters is saved with a truncated slug without crashing."""
        long_name = "A" * 300
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name=long_name,
            price=Decimal("100.00"),
            stock=10,
            status="published"
        )
        # Verify it saved successfully and length of slug is <= 255
        self.assertTrue(product.slug)
        self.assertLessEqual(len(product.slug), 255)
        # It should start with 'a'
        self.assertTrue(product.slug.startswith("a"))

    def test_duplicate_extremely_long_product_names(self):
        """Verify that multiple products with the same extremely long name receive unique truncated slugs without clashing or overflowing."""
        long_name = "B" * 300
        p1 = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name=long_name,
            price=Decimal("100.00"),
            stock=10,
            status="published"
        )
        p2 = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name=long_name,
            price=Decimal("120.00"),
            stock=5,
            status="published"
        )
        p3 = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name=long_name,
            price=Decimal("150.00"),
            stock=1,
            status="published"
        )
        
        self.assertNotEqual(p1.slug, p2.slug)
        self.assertNotEqual(p1.slug, p3.slug)
        self.assertNotEqual(p2.slug, p3.slug)
        
        self.assertLessEqual(len(p1.slug), 255)
        self.assertLessEqual(len(p2.slug), 255)
        self.assertLessEqual(len(p3.slug), 255)

    def test_extremely_long_category_name_slug_truncation(self):
        """Verify that a category with an extremely long name is saved with a truncated slug."""
        long_name = "C" * 300
        category = Category.objects.create(
            name=long_name,
            commision_percentage=5.0
        )
        self.assertTrue(category.slug)
        self.assertLessEqual(len(category.slug), 255)





# ──────────────────────────────────────────────────────────────────────────────
# Gender Applicability & show_gender Tests
# ──────────────────────────────────────────────────────────────────────────────

class CategoryGenderApplicabilityTests(TestCase):
    """
    Tests for Category.is_gender_applicable property.
    Verifies that fashion/apparel categories return True and non-fashion
    categories (Electronics, Furniture, Mobiles, etc.) return False.

    NOTE: is_gender_applicable is a pure Python property — no DB save needed.
    We construct Category objects without saving to avoid unique constraint issues.
    """

    def _make_category(self, name, slug=None):
        """Build an unsaved Category instance for pure-Python property testing."""
        cat = Category(name=name, commision_percentage=10.0)
        if slug:
            cat.slug = slug
        else:
            # Simulate what save() would generate
            from django.utils.text import slugify
            cat.slug = slugify(name)
        return cat

    # ── Categories that SHOULD be gender-applicable ──────────────────────────

    def test_cloth_category_is_gender_applicable(self):
        """Cloth category slug matches 'cloth' keyword → gender applicable."""
        cat = self._make_category("Cloth")
        self.assertTrue(cat.is_gender_applicable)

    def test_clothing_name_is_gender_applicable(self):
        """Category named 'Clothing' matches 'clothing' keyword."""
        cat = self._make_category("Clothing & Apparel")
        self.assertTrue(cat.is_gender_applicable)

    def test_jewellery_category_is_gender_applicable(self):
        """Jewellery matches 'jewel' keyword."""
        cat = self._make_category("Jewellery")
        self.assertTrue(cat.is_gender_applicable)

    def test_footwear_category_is_gender_applicable(self):
        """Footwear matches 'footwear' keyword."""
        cat = self._make_category("Footwear")
        self.assertTrue(cat.is_gender_applicable)

    def test_accessories_category_is_gender_applicable(self):
        """Accessories matches 'accessory' keyword."""
        cat = self._make_category("Accessories")
        self.assertTrue(cat.is_gender_applicable)

    def test_beauty_category_is_gender_applicable(self):
        """Beauty matches 'beauty' keyword."""
        cat = self._make_category("Beauty & Skincare")
        self.assertTrue(cat.is_gender_applicable)

    def test_cosmetics_category_is_gender_applicable(self):
        """Cosmetics matches 'cosmetic' keyword."""
        cat = self._make_category("Cosmetics")
        self.assertTrue(cat.is_gender_applicable)

    def test_saree_category_is_gender_applicable(self):
        """Saree matches 'saree' keyword."""
        cat = self._make_category("Sarees & Ethnic Wear")
        self.assertTrue(cat.is_gender_applicable)

    # ── Categories that should NOT be gender-applicable ──────────────────────

    def test_electronics_category_not_gender_applicable(self):
        """Electronics category has no fashion keywords → not gender applicable."""
        cat = self._make_category("Electronics")
        self.assertFalse(cat.is_gender_applicable)

    def test_furniture_category_not_gender_applicable(self):
        """Furniture has no fashion keywords → not gender applicable."""
        cat = self._make_category("Furniture")
        self.assertFalse(cat.is_gender_applicable)

    def test_laptops_category_not_gender_applicable(self):
        """Laptops has no fashion keywords → not gender applicable."""
        cat = self._make_category("Laptops")
        self.assertFalse(cat.is_gender_applicable)

    def test_mobiles_category_not_gender_applicable(self):
        """Mobiles & Smartphones has no fashion keywords → not gender applicable."""
        cat = self._make_category("Mobiles & Smartphones")
        self.assertFalse(cat.is_gender_applicable)

    def test_food_beverages_not_gender_applicable(self):
        """Food & Beverages has no fashion keywords → not gender applicable."""
        cat = self._make_category("Food & Beverages")
        self.assertFalse(cat.is_gender_applicable)

    def test_gifts_hampers_not_gender_applicable(self):
        """Gifts & Hampers has no fashion keywords → not gender applicable."""
        cat = self._make_category("Gifts & Hampers")
        self.assertFalse(cat.is_gender_applicable)



class ProductShowGenderTests(TestCase):
    """
    Tests for Product.show_gender property and the automatic gender-clear
    logic in Product.save() when a non-fashion category is assigned.
    """

    def setUp(self):
        self.seller_user = User.objects.create_user(
            phone="7777777701",
            password="pass1234",
            role="seller",
            full_name="Gender Test Seller"
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Gender Test Shop",
            is_verified=True
        )
        # Gender-applicable category — use distinct name to avoid unique clashes
        self.fashion_cat = Category.objects.create(
            name="Test-Cloth-Fashion", commision_percentage=10.0
        )
        # Non-gender-applicable categories
        self.furniture_cat = Category.objects.create(
            name="Test-Furniture-NG", commision_percentage=8.0
        )
        self.electronics_cat = Category.objects.create(
            name="Test-Electronics-NG", commision_percentage=8.0
        )

    # ── show_gender property ─────────────────────────────────────────────────

    def test_show_gender_true_for_fashion_product_with_gender(self):
        """A fashion product with gender set → show_gender is True."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.fashion_cat,
            name="Summer Saree",
            price=Decimal("500.00"),
            stock=10,
            status="published",
            gender="women"
        )
        self.assertTrue(product.show_gender)

    def test_show_gender_false_when_no_gender_set(self):
        """A product with no gender → show_gender is False regardless of category."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.fashion_cat,
            name="Ethnic Kurta",
            price=Decimal("400.00"),
            stock=5,
            status="published",
            gender=None
        )
        self.assertFalse(product.show_gender)

    def test_show_gender_false_for_electronics_even_with_gender(self):
        """
        Electronics product with gender set → show_gender must be False
        because Electronics is not gender-applicable.
        """
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.electronics_cat,
            name="Bluetooth Speaker",
            price=Decimal("1500.00"),
            stock=20,
            status="published",
            gender="unisex"
        )
        # On save, gender should be auto-cleared; show_gender must be False
        self.assertFalse(product.show_gender)

    def test_show_gender_false_for_furniture_even_with_gender(self):
        """
        Furniture product with gender set → gender is auto-cleared on save
        and show_gender is False.
        """
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.furniture_cat,
            name="Wooden Sofa",
            price=Decimal("25000.00"),
            stock=2,
            status="published",
            gender="unisex"
        )
        self.assertFalse(product.show_gender)

    def test_show_gender_false_when_no_category(self):
        """Product with no category but gender set → show_gender is True (gender is shown when category is unknown)."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=None,
            name="Mystery Item",
            price=Decimal("100.00"),
            stock=1,
            status="draft",
            gender="men"
        )
        # No category → can't determine non-applicability → show gender
        self.assertTrue(product.show_gender)

    # ── Auto-clear gender on save ─────────────────────────────────────────────

    def test_gender_auto_cleared_on_save_for_furniture(self):
        """
        When a product is saved with a Furniture category and gender='men',
        the gender field must be automatically cleared to None.
        """
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.furniture_cat,
            name="Oak Dining Table",
            price=Decimal("18000.00"),
            stock=3,
            status="published",
            gender="men"
        )
        product.refresh_from_db()
        self.assertIsNone(product.gender)

    def test_gender_auto_cleared_on_save_for_electronics(self):
        """
        Electronics product gender must be auto-cleared on save.
        """
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.electronics_cat,
            name="Smart TV 55 inch",
            price=Decimal("45000.00"),
            stock=5,
            status="published",
            gender="unisex"
        )
        product.refresh_from_db()
        self.assertIsNone(product.gender)

    def test_gender_preserved_on_save_for_fashion(self):
        """
        Fashion/Cloth product gender must NOT be cleared on save.
        """
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.fashion_cat,
            name="Cotton Kurti",
            price=Decimal("799.00"),
            stock=15,
            status="published",
            gender="women"
        )
        product.refresh_from_db()
        self.assertEqual(product.gender, "women")

    def test_gender_change_after_category_switch_to_non_fashion(self):
        """
        When a fashion product (with gender) switches category to Furniture,
        gender should be cleared on the next save.
        """
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.fashion_cat,
            name="Convertible Jacket",
            price=Decimal("2500.00"),
            stock=8,
            status="published",
            gender="men"
        )
        self.assertEqual(product.gender, "men")

        # Switch category to Furniture
        product.category = self.furniture_cat
        product.save()
        product.refresh_from_db()
        self.assertIsNone(product.gender)
        self.assertFalse(product.show_gender)

    def test_gender_change_after_category_switch_to_fashion(self):
        """
        When a non-fashion product switches to a fashion category and
        gender is explicitly set, it should be preserved.
        """
        # Start as electronics (no gender)
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.electronics_cat,
            name="Wireless Mouse",
            price=Decimal("999.00"),
            stock=25,
            status="published",
            gender="unisex"
        )
        product.refresh_from_db()
        self.assertIsNone(product.gender)  # auto-cleared

        # Switch to fashion + set gender
        product.category = self.fashion_cat
        product.gender = "unisex"
        product.save()
        product.refresh_from_db()
        self.assertEqual(product.gender, "unisex")
        self.assertTrue(product.show_gender)

    # ── __str__ representation ────────────────────────────────────────────────

    def test_str_includes_gender_for_fashion_product(self):
        """__str__ should include gender label for fashion products."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.fashion_cat,
            name="Silk Saree",
            price=Decimal("3000.00"),
            stock=5,
            status="published",
            gender="women"
        )
        self.assertIn("Women", str(product))

    def test_str_excludes_gender_for_electronics(self):
        """__str__ should NOT include gender label for Electronics products."""
        product = Product.objects.create(
            seller=self.seller_profile,
            category=self.electronics_cat,
            name="Smart Bulb",
            price=Decimal("250.00"),
            stock=50,
            status="published",
            gender="unisex"
        )
        # gender auto-cleared → no gender in str
        self.assertNotIn("Unisex", str(product))
        self.assertNotIn("Men", str(product))
        self.assertNotIn("Women", str(product))


class CategoryStringAndDropdownDisplayTests(TestCase):
    """
    Tests that Category.__str__ returns the category's human-readable name,
    and that ProductForm category dropdown renders the category name (e.g. 'Electronics')
    instead of raw model string 'Category object (1)'.
    """

    def setUp(self):
        self.seller_user = User.objects.create_user(
            phone="7777777799",
            password="pass1234",
            role="seller",
            full_name="Category Dropdown Seller"
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Category Dropdown Shop",
            is_verified=True
        )
        self.cat1 = Category.objects.create(
            name="Test Clothing Display",
            commision_percentage=10.0
        )
        self.cat2 = Category.objects.create(
            name="Test Electronics Display",
            commision_percentage=15.0
        )

    def test_category_str_returns_name(self):
        """Category.__str__ must return the category name, not 'Category object (id)'."""
        self.assertEqual(str(self.cat1), "Test Clothing Display")
        self.assertEqual(str(self.cat2), "Test Electronics Display")
        self.assertNotIn("Category object", str(self.cat1))
        self.assertNotIn("Category object", str(self.cat2))

    def test_product_form_category_dropdown_renders_name_not_object(self):
        """
        ProductForm category dropdown field must display human-readable category names,
        never 'Category object (id)'.
        """
        form = ProductForm(request_user=self.seller_user)
        self.assertEqual(form.fields['category'].empty_label, 'Select Category')

        rendered_html = str(form['category'])
        # Category names must be present in the dropdown options
        self.assertIn("Test Clothing Display", rendered_html)
        self.assertIn("Test Electronics Display", rendered_html)
        self.assertIn("Select Category", rendered_html)

        # 'Category object' must NEVER appear
        self.assertNotIn("Category object", rendered_html)


from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.conf import settings
import os
import shutil
from items.views import _is_safe_temp_path


class TemporaryUploadPersistenceTests(TestCase):
    """
    Tests that uploaded images are safely preserved when product creation/editing
    fails validation, and that preserved images are successfully applied when the form
    is re-submitted.
    """

    def setUp(self):
        self.seller_user = User.objects.create_user(
            phone="7777777788",
            password="pass1234",
            role="seller",
            full_name="Temp Upload Seller"
        )
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Temp Upload Shop",
            is_verified=True,
            bank_name="Test Bank",
            account_number="1234567890",
            ifsc_code="TEST0123456",
            account_holder_name="Temp Upload Seller"
        )
        self.category = Category.objects.create(
            name="Test Apparel Cat",
            commision_percentage=10.0
        )
        self.user_temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads', f'user_{self.seller_user.id}')
        os.makedirs(self.user_temp_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.user_temp_dir):
            shutil.rmtree(self.user_temp_dir, ignore_errors=True)

    def test_safe_temp_path_validation(self):
        """_is_safe_temp_path must prevent directory traversal and cross-user access."""
        valid_path = f"temp_uploads/user_{self.seller_user.id}/primary_test.jpg"
        self.assertTrue(_is_safe_temp_path(valid_path, self.seller_user.id))

        # Cross-user access
        other_user_path = f"temp_uploads/user_99999/primary_test.jpg"
        self.assertFalse(_is_safe_temp_path(other_user_path, self.seller_user.id))

        # Directory traversal
        self.assertFalse(_is_safe_temp_path(f"temp_uploads/user_{self.seller_user.id}/../../etc/passwd", self.seller_user.id))
        self.assertFalse(_is_safe_temp_path("/etc/passwd", self.seller_user.id))
        self.assertFalse(_is_safe_temp_path("", self.seller_user.id))

    def test_temp_upload_cached_on_form_validation_failure(self):
        """
        When a seller submits a product with an image but validation fails (e.g. missing name),
        the uploaded image must be cached to disk and passed back to context without being lost.
        """
        self.client.login(phone="7777777788", password="pass1234")

        # Create a small valid test image (1x1 PNG)
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00'
            b'\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        test_file = SimpleUploadedFile("my_sample_photo.png", png_bytes, content_type="image/png")

        # Submit with missing name to trigger validation error
        post_data = {
            'name': '',  # Required field missing
            'short_description': 'Short desc',
            'description': 'Full description',
            'price': '499.00',
            'stock': '10',
            'status': 'published',
            'category': str(self.category.id),
            'primary_image': test_file,
            'variants-TOTAL_FORMS': '0',
            'variants-INITIAL_FORMS': '0',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '10',
        }

        response = self.client.post(reverse('items:product_create'), post_data)
        # Form re-rendered with validation error
        self.assertEqual(response.status_code, 200)

        # Context must contain temp_primary_image
        temp_img = response.context.get('temp_primary_image')
        self.assertIsNotNone(temp_img)
        self.assertTrue(temp_img['rel_path'].startswith(f"temp_uploads/user_{self.seller_user.id}/"))

        # File must actually exist on disk in the temp directory
        full_disk_path = os.path.join(settings.MEDIA_ROOT, temp_img['rel_path'])
        self.assertTrue(os.path.exists(full_disk_path))

        # Rendered HTML must contain the hidden input for cached image
        self.assertIn('cached_temp_primary_image', response.content.decode())

    def test_product_created_using_cached_temp_primary_image(self):
        """
        When a seller resubmits with valid data and cached_temp_primary_image (without re-uploading),
        the product must be created with that primary image attached.
        """
        self.client.login(phone="7777777788", password="pass1234")

        # Pre-seed a file in user's temp directory
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00'
            b'\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        filename = "primary_preset123.png"
        filepath = os.path.join(self.user_temp_dir, filename)
        with open(filepath, 'wb') as f:
            f.write(png_bytes)
        rel_path = f"temp_uploads/user_{self.seller_user.id}/{filename}"

        # Submit valid product data WITH cached_temp_primary_image, WITHOUT primary_image file
        post_data = {
            'name': 'Silk Saree Preserved',
            'short_description': 'Gorgeous saree',
            'description': 'Traditional pure silk saree',
            'price': '1499.00',
            'stock': '5',
            'discount_percent': '0',
            'low_stock_threshold': '5',
            'status': 'published',
            'category': str(self.category.id),
            'cached_temp_primary_image': rel_path,
            'variants-TOTAL_FORMS': '0',
            'variants-INITIAL_FORMS': '0',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '10',
        }

        response = self.client.post(reverse('items:product_create'), post_data)
        # Should redirect on success
        self.assertEqual(response.status_code, 302)

        # Check product created
        product = Product.objects.filter(name='Silk Saree Preserved').first()
        self.assertIsNotNone(product)
        self.assertTrue(bool(product.primary_image))
        self.assertTrue(os.path.exists(product.primary_image.path))

        # Cleanup: delete created media file
        if os.path.exists(product.primary_image.path):
            os.remove(product.primary_image.path)

    def test_db_model_temporary_product_image_lifecycle(self):
        """
        Test that TemporaryProductImage records are created, queried, and attached
        using cached_temp_primary_id and cached_temp_additional_ids.
        """
        from items.models import TemporaryProductImage
        self.client.login(phone="7777777788", password="pass1234")

        # 1. Create TemporaryProductImage records for primary and gallery
        png_bytes = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
            b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00'
            b'\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        temp_primary = TemporaryProductImage.objects.create(
            user=self.seller_user,
            image=SimpleUploadedFile("db_primary.png", png_bytes, content_type="image/png"),
            is_primary=True,
            original_filename="db_primary.png",
        )
        temp_gallery = TemporaryProductImage.objects.create(
            user=self.seller_user,
            image=SimpleUploadedFile("db_gallery.png", png_bytes, content_type="image/png"),
            is_primary=False,
            original_filename="db_gallery.png",
        )

        self.assertEqual(TemporaryProductImage.objects.filter(user=self.seller_user).count(), 2)

        # 2. Submit product referencing these DB model IDs
        post_data = {
            'name': 'DB Preserved Product',
            'short_description': 'Short description',
            'description': 'Detailed product description',
            'price': '899.00',
            'mrp': '1299.00',
            'stock': '15',
            'discount_percent': '10',
            'low_stock_threshold': '2',
            'status': 'published',
            'category': str(self.category.id),
            'cached_temp_primary_id': str(temp_primary.id),
            'cached_temp_additional_ids': [str(temp_gallery.id)],
            'variants-TOTAL_FORMS': '0',
            'variants-INITIAL_FORMS': '0',
            'variants-MIN_NUM_FORMS': '0',
            'variants-MAX_NUM_FORMS': '10',
        }

        response = self.client.post(reverse('items:product_create'), post_data)
        self.assertEqual(response.status_code, 302)

        # Verify product created with primary and additional images
        product = Product.objects.filter(name='DB Preserved Product').first()
        self.assertIsNotNone(product)
        self.assertTrue(bool(product.primary_image))
        self.assertEqual(product.product_image_product.count(), 1)

        # Verify TemporaryProductImage table cleanup
        self.assertEqual(TemporaryProductImage.objects.filter(user=self.seller_user).count(), 0)

    def test_form_auto_sync_mrp_to_price(self):
        """
        When seller inputs MRP and discount but leaves base price blank,
        clean() should auto-populate price from mrp to avoid customer pays ₹0.00.
        """
        form_data = {
            'name': 'Sofa Chair',
            'short_description': 'Solid wood chair',
            'description': 'Premium single seater sofa chair',
            'mrp': '5500.00',
            'discount_percent': '50',
            'cost_price': '1792.00',
            'stock': '5',
            'category': self.category.id,
            'status': 'published',
            'low_stock_threshold': '1',
        }
        form = ProductForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['price'], Decimal('5500.00'))

    def test_form_and_backend_profit_calculation_when_mrp_discount_cost_entered(self):
        """
        Verify that when MRP (5500), Discount (50%), and Cost Price (1792) are entered,
        the form saves cleanly and backend properties (final_price, savings, profit, margin)
        calculate and update accurately.
        """
        form_data = {
            'name': 'Luxury Wood Sofa',
            'short_description': 'Teak Wood Single Seater',
            'description': 'Handcrafted premium sofa chair',
            'mrp': '5500.00',
            'discount_percent': '50',
            'cost_price': '1792.00',
            'stock': '10',
            'category': self.category.id,
            'status': 'published',
            'low_stock_threshold': '2',
        }
        form = ProductForm(data=form_data, request_user=self.seller_user)
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save(commit=False)
        product.seller = self.seller_profile
        product.save()

        # 1. Base price is MRP (5500.00)
        self.assertEqual(product.price, Decimal('5500.00'))
        self.assertEqual(product.mrp, Decimal('5500.00'))
        self.assertEqual(product.discount_percent, 50)
        self.assertEqual(product.cost_price, Decimal('1792.00'))

        # 2. Customer pays final_price: 5500 - 50% = 2750.00
        self.assertEqual(product.final_price, Decimal('2750.00'))

        # 3. Customer savings: 5500 - 2750 = 2750.00
        self.assertEqual(product.savings_per_unit, Decimal('2750.00'))

        # 4. Commission: 10% of 2750 = 275.00 (self.category commision_percentage is 10.0)
        self.assertEqual(product.admin_commission, Decimal('275.00'))

        # 5. Net Profit: 2750 - 275 - 1792 = 683.00
        self.assertEqual(product.seller_profit, Decimal('683.00'))

        # 6. Profit Margin: 683 / 2750 * 100 = 24.84%
        self.assertAlmostEqual(float(product.seller_profit_margin), 24.836, places=2)

    def test_home_view_category_filter_and_sorting(self):
        """
        Verify home page view supports ?category= and ?sort= query parameters.
        """
        cat_laptops = Category.objects.create(name="Laptops", slug="laptops", commision_percentage=5.0)
        p1 = Product.objects.create(
            seller=self.seller_profile,
            category=self.category,
            name="Cloth Shirt",
            price=Decimal("500.00"),
            stock=10,
            status="published",
            is_active=True
        )
        p2 = Product.objects.create(
            seller=self.seller_profile,
            category=cat_laptops,
            name="Acer Aspire Laptop",
            price=Decimal("35000.00"),
            stock=5,
            status="published",
            is_active=True
        )

        # Filter by laptops category
        response = self.client.get(reverse('shop:home') + '?category=laptops')
        self.assertEqual(response.status_code, 200)
        self.assertIn('products', response.context)
        products = list(response.context['products'])
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].name, "Acer Aspire Laptop")

        # Sort by price ascending
        response_sort = self.client.get(reverse('shop:home') + '?sort=price_asc')
        self.assertEqual(response_sort.status_code, 200)
        products_sorted = list(response_sort.context['products'])
        self.assertGreaterEqual(len(products_sorted), 2)
        self.assertEqual(products_sorted[0].price, Decimal("500.00"))


class AdminSellerManagementTests(TestCase):
    def setUp(self):
        from accounts.models import SellerShopAddress
        self.admin_user = User.objects.create_user(
            phone="9999999999",
            password="adminpassword123",
            role="admin",
            full_name="Admin Boss",
            is_staff=True,
            is_superuser=True
        )
        self.customer_user = User.objects.create_user(
            phone="7777777777",
            password="customerpassword123",
            role="customer",
            full_name="Normal Customer"
        )
        self.seller1_user = User.objects.create_user(
            phone="8888888881",
            email="alice@example.com",
            password="alicepassword123",
            role="seller",
            full_name="Alice Trader"
        )
        self.seller1_profile = SellerProfile.objects.create(
            user=self.seller1_user,
            shop_name="Alpha Store",
            is_verified=False,
            pan_verification_status="pending"
        )
        self.seller1_address = SellerShopAddress.objects.create(
            seller=self.seller1_profile,
            shop_name="Alpha Store",
            shop_phone=self.seller1_user.phone,
            shop_email=self.seller1_user.email,
            address_line1="Old Street 1",
            city="Delhi",
            state="Delhi",
            postal_code="110001",
            country="India"
        )

        self.seller2_user = User.objects.create_user(
            phone="8888888882",
            email="bob@example.com",
            password="bobpassword123",
            role="seller",
            full_name="Bob Vendor"
        )
        self.seller2_profile = SellerProfile.objects.create(
            user=self.seller2_user,
            shop_name="Beta Fashion",
            is_verified=True,
            pan_verification_status="verified"
        )

    def test_admin_seller_management_redirect(self):
        self.client.login(phone="9999999999", password="adminpassword123")
        response = self.client.get(reverse('accounts:admin_seller_management'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('items:verify_sellers'), response.url)

    def test_verify_sellers_view_admin_access_and_search(self):
        self.client.login(phone="9999999999", password="adminpassword123")
        
        # All sellers list
        response = self.client.get(reverse('items:verify_sellers'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Store")
        self.assertContains(response, "Beta Fashion")

        # Search by shop name
        res_search_alpha = self.client.get(reverse('items:verify_sellers') + '?q=Alpha')
        self.assertEqual(res_search_alpha.status_code, 200)
        self.assertContains(res_search_alpha, "Alpha Store")
        self.assertNotContains(res_search_alpha, "Beta Fashion")

        # Search by owner name
        res_search_bob = self.client.get(reverse('items:verify_sellers') + '?q=Bob')
        self.assertEqual(res_search_bob.status_code, 200)
        self.assertContains(res_search_bob, "Beta Fashion")
        self.assertNotContains(res_search_bob, "Alpha Store")

        # Search by city
        res_search_city = self.client.get(reverse('items:verify_sellers') + '?q=Delhi')
        self.assertEqual(res_search_city.status_code, 200)
        self.assertContains(res_search_city, "Alpha Store")

    def test_non_admin_restricted_access(self):
        self.client.login(phone="7777777777", password="customerpassword123")
        
        # Verify sellers list should redirect non-admins
        res_list = self.client.get(reverse('items:verify_sellers'))
        self.assertEqual(res_list.status_code, 302)

        # Seller edit should redirect non-admins
        res_edit = self.client.get(reverse('items:seller_edit', args=[self.seller1_profile.id]))
        self.assertEqual(res_edit.status_code, 302)

    def test_seller_edit_view_multi_table_atomic_update(self):
        self.client.login(phone="9999999999", password="adminpassword123")
        
        post_data = {
            # User table
            'owner_name': 'Alice Super Trader',
            'owner_phone': '8888888889',
            'owner_email': 'alice_new@example.com',
            'new_password': 'BrandNewPassword123!',
            'is_active': 'on',
            # SellerProfile table
            'shop_name': 'Alpha Grand Mart',
            'shop_description': 'Finest goods in town',
            'gst_number': '27ABCDE1234F1Z5',
            'pan_number': 'ABCDE1234F',
            'pan_verification_status': 'verified',
            'pan_rejection_reason': '',
            'bank_name': 'HDFC Bank',
            'account_number': '987654321012',
            'ifsc_code': 'HDFC0001234',
            'account_holder_name': 'Alice Super Trader',
            'razorpay_contact_id': 'cont_12345',
            'razorpay_fund_account_id': 'fa_67890',
            'is_verified': 'on',
            # SellerShopAddress table
            'address_line1': '100 Commercial Blvd',
            'address_line2': 'Floor 3',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'postal_code': '400001',
            'country': 'India',
            'pickup_instructions': 'Ring bell at entrance',
        }

        response = self.client.post(reverse('items:seller_edit', args=[self.seller1_profile.id]), data=post_data)
        self.assertEqual(response.status_code, 302)

        # Verify User table updated
        self.seller1_user.refresh_from_db()
        self.assertEqual(self.seller1_user.full_name, 'Alice Super Trader')
        self.assertEqual(self.seller1_user.phone, '8888888889')
        self.assertEqual(self.seller1_user.email, 'alice_new@example.com')
        self.assertTrue(self.seller1_user.check_password('BrandNewPassword123!'))

        # Verify SellerProfile table updated
        self.seller1_profile.refresh_from_db()
        self.assertEqual(self.seller1_profile.shop_name, 'Alpha Grand Mart')
        self.assertEqual(self.seller1_profile.shop_description, 'Finest goods in town')
        self.assertEqual(self.seller1_profile.gst_number, '27ABCDE1234F1Z5')
        self.assertEqual(self.seller1_profile.pan_number, 'ABCDE1234F')
        self.assertEqual(self.seller1_profile.pan_verification_status, 'verified')
        self.assertEqual(self.seller1_profile.bank_name, 'HDFC Bank')
        self.assertEqual(self.seller1_profile.account_number, '987654321012')
        self.assertEqual(self.seller1_profile.ifsc_code, 'HDFC0001234')
        self.assertEqual(self.seller1_profile.account_holder_name, 'Alice Super Trader')
        self.assertEqual(self.seller1_profile.razorpay_contact_id, 'cont_12345')
        self.assertEqual(self.seller1_profile.razorpay_fund_account_id, 'fa_67890')
        self.assertTrue(self.seller1_profile.is_verified)

        # Verify SellerShopAddress table updated
        self.seller1_address.refresh_from_db()
        self.assertEqual(self.seller1_address.shop_name, 'Alpha Grand Mart')
        self.assertEqual(self.seller1_address.address_line1, '100 Commercial Blvd')
        self.assertEqual(self.seller1_address.address_line2, 'Floor 3')
        self.assertEqual(self.seller1_address.city, 'Mumbai')
        self.assertEqual(self.seller1_address.state, 'Maharashtra')
        self.assertEqual(self.seller1_address.postal_code, '400001')
        self.assertEqual(self.seller1_address.pickup_instructions, 'Ring bell at entrance')
        self.assertTrue(self.seller1_address.is_verified)

    def test_seller_edit_validation_errors(self):
        self.client.login(phone="9999999999", password="adminpassword123")
        
        # Test 1: Duplicate shop name (Beta Fashion already belongs to seller 2)
        res_dup_shop = self.client.post(reverse('items:seller_edit', args=[self.seller1_profile.id]), data={
            'owner_name': 'Alice Trader',
            'owner_phone': self.seller1_user.phone,
            'shop_name': 'Beta Fashion',
        })
        self.assertEqual(res_dup_shop.status_code, 302)
        self.seller1_profile.refresh_from_db()
        self.assertNotEqual(self.seller1_profile.shop_name, 'Beta Fashion')

        # Test 2: Duplicate phone number (8888888882 already belongs to seller 2)
        res_dup_phone = self.client.post(reverse('items:seller_edit', args=[self.seller1_profile.id]), data={
            'owner_name': 'Alice Trader',
            'owner_phone': '8888888882',
            'shop_name': 'Alpha Store',
        })
        self.assertEqual(res_dup_phone.status_code, 302)
        self.seller1_user.refresh_from_db()
        self.assertNotEqual(self.seller1_user.phone, '8888888882')

