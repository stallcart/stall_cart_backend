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

