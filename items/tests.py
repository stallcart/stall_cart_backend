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
