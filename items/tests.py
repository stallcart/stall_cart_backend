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
