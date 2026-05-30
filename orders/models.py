# orders/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from common.models import BaseModel
import uuid
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
class Order(BaseModel):
    
    STATUS_CHOICES = [
        ('pending', '🟡 Order Placed'),
        ('confirmed', '🔵 Order Confirmed'),
        ('processing', '🟠 Processing'),
        ('shipped', '🟣 Shipped'),
        ('out_for_delivery', '🔵 Out for Delivery'),
        ('delivered', '🟢 Delivered'),
        ('cancelled', '🔴 Cancelled'),
        ('returned', '🔄 Returned'),
        ('refund_initiated', '💰 Refund Initiated'),
        ('refunded', '✅ Refunded'),

    ]
    
    # Payment Status
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    # Cancellation/Return Reasons
    CANCELLATION_REASONS = [
        ('changed_mind', 'Changed my mind'),
        ('found_cheaper', 'Found cheaper elsewhere'),
        ('delivery_delay', 'Delivery delay'),
        ('wrong_address', 'Wrong address'),
        ('other', 'Other'),
    ]
    
    RETURN_REASONS = [
        ('damaged', 'Damaged/Defective'),
        ('wrong_item', 'Wrong item sent'),
        ('not_as_described', 'Not as described'),
        ('size_issue', 'Size/Color issue'),
        ('late_delivery', 'Late delivery'),
        ('other', 'Other'),
    ]

    # Core Fields
    unique_order_id = models.CharField(max_length=20, unique=True, editable=False,db_index=True )  # e.g., ORD-2026-001234
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='orders'
    )
    guest_email = models.EmailField(blank=True, null=True)  # For guest checkout
    guest_phone = models.CharField(max_length=15, blank=True, null=True)
    
    # Address (JSON for flexibility)
    shipping_address = models.JSONField(default=dict)  # {name, phone, address, city, state, pincode, landmark}
    billing_address = models.JSONField(default=dict, blank=True)
    
    # Payment
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=50, choices=[
        ('cod', 'Cash on Delivery'),
        ('razorpay', 'Razorpay (UPI/Card/NetBanking)'),
        ('wallet', 'Wallet'),
    ], default='cod')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)
    
    # Order Tracking
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    status_updated_at = models.DateTimeField(auto_now=True)
    
    # Delivery Tracking
    tracking_number = models.CharField(max_length=100, blank=True, null=True)  # Shiprocket/Awbl
    courier_name = models.CharField(max_length=100, blank=True, null=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)

    
    # Cancellation & Returns
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=50, choices=CANCELLATION_REASONS, blank=True, null=True)
    cancellation_remarks = models.TextField(blank=True)
    
    returned_at = models.DateTimeField(null=True, blank=True)
    return_reason = models.CharField(max_length=50, choices=RETURN_REASONS, blank=True, null=True)
    return_remarks = models.TextField(blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_at = models.DateTimeField(null=True, blank=True)
    razorpay_refund_id = models.CharField(max_length=100, blank=True, null=True)
 
   
    # Metadata
    notes = models.TextField(blank=True)
    
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            # models.Index(fields=['order_id']),
        ]
    
    def save(self, *args, **kwargs):
        # Auto-generate order ID
        # Auto-generate order_id only if not already set
        if not self.unique_order_id:
            date_str = timezone.now().strftime('%Y%m%d')
            last_order = Order.objects.filter(
                unique_order_id__startswith=f'ORD-{date_str}-'
            ).order_by('unique_order_id').last()
            
            if last_order:
                last_num = int(last_order.unique_order_id.split('-')[-1])
                new_num = last_num + 1
            else:
                new_num = 1
            self.unique_order_id= f'ORD-{date_str}-{new_num:06d}'
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.unique_order_id} | {self.user.phone if self.user else self.guest_email} | {self.get_status_display()}"
    
    @property
    def is_cancellable(self):
        """Check if order can be cancelled (only before shipped)"""
        return self.status in ['pending', 'confirmed', 'processing']
    
    @property
    def is_returnable(self):
        """Returns allowed within 7 days of delivery, only if delivered."""
        if self.status != 'delivered' or not self.delivered_at:
            return False
        return (timezone.now() - self.delivered_at).days <= 7
 
    @property
    def tracking_url(self):
        if self.courier_name == 'Shiprocket' and self.tracking_number:
            return f"https://track.shiprocket.in/tracking/{self.tracking_number}"
        elif self.courier_name == 'Delhivery' and self.tracking_number:
            return f"https://tracking.delhivery.com/{self.tracking_number}"
        return None
 
    @property
    def can_be_refunded(self):
        """True when payment was made via Razorpay and not yet refunded."""
        return (
            self.payment_method == 'razorpay'
            and self.payment_status == 'paid'
            and self.razorpay_payment_id
            and self.status not in ('refund_initiated', 'refunded')
        )



class OrderItem(BaseModel):
    """Individual items in an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('items.Product', on_delete=models.PROTECT)
    
    # ✅ ADD THIS LINE — Variant support (nullable for products without variants)
    variant = models.ForeignKey(
        'items.ProductVariant', 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True, 
        related_name='order_items'
    )
    
    seller = models.ForeignKey('items.SellerProfile', on_delete=models.PROTECT)  # Denormalized for performance
    
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order
    total = models.DecimalField(max_digits=10, decimal_places=2)  # quantity * price
    
    # Return tracking per item
    is_returned = models.BooleanField(default=False)
    returned_quantity = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['id']
    
    def __str__(self):
        variant_str = f" ({self.variant.size_value})" if self.variant else ""
        return f"{self.product.name}{variant_str} x{self.quantity} in {self.order.unique_order_id}"
    
    @property
    def remaining_quantity(self):
        """Quantity not yet returned"""
        return self.quantity - self.returned_quantity
    
    @property
    def variant_display(self):
        """Human-readable variant info for templates"""
        if not self.variant:
            return None
        parts = []
        if self.variant.size_value:
            parts.append(self.variant.size_value)
        if self.variant.color:
            parts.append(self.variant.color)
        return ' • '.join(parts) if parts else None


class OrderStatusLog(BaseModel):
    """Track every status change for audit & tracking timeline"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs')
    old_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30, choices=Order.STATUS_CHOICES)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.order.order_id}: {self.old_status} → {self.new_status}"

def validate_image_size(value):
    """Limit upload size to 5MB"""
    filesize = value.size
    if filesize > 5 * 1024 * 1024:
        raise ValidationError("Image size cannot exceed 5MB")



class ReturnRequest(BaseModel):
    """Return request raised by customer after delivery."""
 
    RETURN_STATUS_CHOICES = [
        ('requested', '🟡 Return Requested'),
        ('approved', '🔵 Approved'),           # seller or admin approved
        ('rejected', '❌ Rejected'),            # seller or admin rejected
        ('pickup_scheduled', '🟠 Pickup Scheduled'),
        ('picked_up', '🟣 Picked Up'),
        ('received', '🟢 Received at Warehouse'),
        ('refund_initiated', '💰 Refund Initiated'),
        ('completed', '✅ Completed'),
    ]
 
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='return_requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
 
    quantity = models.PositiveIntegerField(default=1)
    reason = models.CharField(max_length=50, choices=Order.RETURN_REASONS)
    remarks = models.TextField(blank=True)
 
    status = models.CharField(max_length=30, choices=RETURN_STATUS_CHOICES, default='requested')
    pickup_date = models.DateField(null=True, blank=True)
    pickup_address = models.JSONField(default=dict)
 
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('manual_pending', 'Manual Transfer Pending'),
        ],
        default='pending'
    )
    refund_method = models.CharField(max_length=50, blank=True, choices=[
        ('original', 'Original Payment Method'),
        ('wallet', 'StallCart Wallet'),
        ('bank', 'Bank Transfer'),
    ])
    razorpay_refund_id = models.CharField(max_length=100, blank=True, null=True)
    refund_initiated_at = models.DateTimeField(null=True, blank=True)
    refund_failure_reason = models.TextField(blank=True)
    refund_instructions = models.TextField(blank=True, help_text="For manual COD refunds")
    
    # Who actioned it
    actioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='actioned_returns'
    )
    actioned_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
 
    class Meta:
        ordering = ['-created_at']
 
    def __str__(self):
        return f"Return #{self.id} for {self.order_item.product.name}"
 

class OrderReturnImage(BaseModel):
    """Customer-uploaded evidence images for return requests."""
    return_request = models.ForeignKey(
        'orders.ReturnRequest',
        on_delete=models.CASCADE,
        related_name='return_images',
    )
    image = models.ImageField(
        upload_to='returns/%Y/%m/',
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp']),
            validate_image_size
        ],
    )
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
 
    class Meta:
        ordering = ['-created_at', '-is_primary']
        verbose_name = "Return Evidence Image"
        verbose_name_plural = "Return Evidence Images"
 
    def __str__(self):
        filename = self.image.name.split('/')[-1] if self.image else 'No Image'
        unique_order_id = getattr(self.return_request.order_item.order, 'unique_order_id', 'N/A')
        return f"Return #{unique_order_id} - {filename}"
 
    def save(self, *args, **kwargs):
        if self.is_primary:
            OrderReturnImage.objects.filter(
                return_request=self.return_request
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)