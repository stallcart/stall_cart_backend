# orders/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from common.models import BaseModel
import uuid
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from decimal import Decimal

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
        ('returned_to_source', '🔄 Returned to Source (RTO)'),
        ('refund_initiated', '💰 Refund Initiated'),
        ('refunded', '✅ Refunded'),
        ('courier_failed_pickup', '🔴 Pickup Failed (Courier)'),
        ('seller_unresponsive', '🔴 Seller Unresponsive / Cancelled'),
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
    shiprocket_order_id = models.CharField(max_length=100, blank=True, null=True)
    shipment_id = models.CharField(max_length=100, blank=True, null=True)
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
 
    # Email tracking flags
    customer_placed_email_sent = models.BooleanField(default=False)
    seller_placed_email_sent = models.BooleanField(default=False)
    customer_payment_email_sent = models.BooleanField(default=False)
    seller_payment_email_sent = models.BooleanField(default=False)
    customer_refund_email_sent = models.BooleanField(default=False)
    seller_refund_email_sent = models.BooleanField(default=False)
   
    # Metadata
    notes = models.TextField(blank=True)
    
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            # models.Index(fields=['order_id']),
        ]
    
    def restock_items(self):
        """Restock all items in the order, handling variants correctly and preventing double-restocking."""
        for item in self.items.all():
            if not item.is_returned:
                product = item.product
                variant = item.variant
                qty = item.quantity
                if variant:
                    variant.stock = (variant.stock or 0) + qty
                    variant.save(update_fields=['stock', 'updated_at'])
                    product.stock = product.variants.filter(is_active=True).aggregate(
                        total=models.Sum('stock')
                    )['total'] or 0
                    product.save(update_fields=['stock', 'updated_at'])
                else:
                    product.stock = (product.stock or 0) + qty
                    product.save(update_fields=['stock', 'updated_at'])
                
                item.is_returned = True
                item.returned_quantity = qty
                item.save(update_fields=['is_returned', 'returned_quantity', 'updated_at'])

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
        
        # Detect status and payment status changes
        is_new = self._state.adding
        old_status = None
        status_changed = False
        old_payment_status = None
        payment_status_changed = False
        if not is_new:
            try:
                old_obj = type(self).objects.filter(pk=self.pk).values('status', 'payment_status').first()
                if old_obj:
                    old_status = old_obj.get('status')
                    if old_status != self.status:
                        status_changed = True
                    old_payment_status = old_obj.get('payment_status')
                    if old_payment_status != self.payment_status:
                        payment_status_changed = True
            except Exception:
                pass
                
        super().save(*args, **kwargs)
        
        # Immediate dispatch of payment/refund emails if status has changed
        if payment_status_changed or (is_new and self.payment_status == 'paid'):
            if self.payment_status == 'paid':
                try:
                    from common.notification_service import send_payment_email_customer, send_payment_email_sellers
                    if not self.customer_payment_email_sent:
                        self.customer_payment_email_sent = send_payment_email_customer(self)
                    if not self.seller_payment_email_sent:
                        self.seller_payment_email_sent = send_payment_email_sellers(self)
                    type(self).objects.filter(pk=self.pk).update(
                        customer_payment_email_sent=self.customer_payment_email_sent,
                        seller_payment_email_sent=self.seller_payment_email_sent
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Failed to send payment success emails on save for order {self.unique_order_id}: {e}")
            elif self.payment_status == 'refunded':
                try:
                    from common.notification_service import send_refund_email_customer, send_refund_email_sellers
                    if not self.customer_refund_email_sent:
                        self.customer_refund_email_sent = send_refund_email_customer(self)
                    if not self.seller_refund_email_sent:
                        self.seller_refund_email_sent = send_refund_email_sellers(self)
                    type(self).objects.filter(pk=self.pk).update(
                        customer_refund_email_sent=self.customer_refund_email_sent,
                        seller_refund_email_sent=self.seller_refund_email_sent
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Failed to send refund emails on save for order {self.unique_order_id}: {e}")
        
        if status_changed:
            # Handle restocking and refunding automatically if status transitions to cancelled/returned/RTO/failed_pickup/unresponsive
            cancelled_states = ('cancelled', 'returned', 'returned_to_source', 'courier_failed_pickup', 'seller_unresponsive')
            if self.status in cancelled_states and old_status not in cancelled_states:
                self.restock_items()
                
                # Auto-refund if paid and eligible (Razorpay)
                if self.can_be_refunded:
                    try:
                        # Lazy import to avoid circular dependencies
                        from orders.views import get_razorpay_client
                        client = get_razorpay_client()
                        if client:
                            razorpay_refund = client.refund.create({
                                'payment_id': self.razorpay_payment_id,
                                'amount': int(self.total_amount * 100),
                                'notes': {'order_id': self.unique_order_id, 'reason': 'Auto-refund on cancellation/return'}
                            })
                            self.payment_status = 'refunded'
                            self.refund_amount = self.total_amount
                            self.refund_at = timezone.now()
                            type(self).objects.filter(pk=self.pk).update(
                                payment_status='refunded',
                                refund_amount=self.total_amount,
                                refund_at=self.refund_at,
                                razorpay_refund_id=razorpay_refund.get('id')
                            )
                        else:
                            self.payment_status = 'failed'
                            type(self).objects.filter(pk=self.pk).update(payment_status='failed')
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Auto-refund failed for cancelled/returned order {self.unique_order_id}: {e}")
                        self.payment_status = 'failed'
                        type(self).objects.filter(pk=self.pk).update(payment_status='failed')
                elif self.payment_method == 'wallet' and self.payment_status == 'paid':
                    self.payment_status = 'refunded'
                    self.refund_amount = self.total_amount
                    type(self).objects.filter(pk=self.pk).update(
                        payment_status='refunded',
                        refund_amount=self.total_amount
                    )

            try:
                from common.notification_service import notify_order_status_change
                notify_order_status_change(self, old_status, self.status)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to trigger status change notification for order {self.unique_order_id}: {e}")
    
    def __str__(self):
        return f"{self.unique_order_id} | {self.user.phone if self.user else self.guest_email} | {self.get_status_display()}"
    
    @property
    def is_cancellable(self):
        """Check if order can be cancelled (only before shipped)"""
        # return self.status in ['pending', 'confirmed', 'processing']
        return False
    
    @property
    def subtotal(self):
        """Calculate subtotal from items"""
        return sum((item.total for item in self.items.all()), Decimal('0.00'))
    
    @property
    def mrp_subtotal(self):
        """Calculate original subtotal before discounts (MRP subtotal)"""
        discount = self.discount_amount or Decimal('0.00')
        return self.subtotal + discount
    
    @property
    def is_returnable(self):
        """Returns allowed within 7 days of delivery, only if delivered."""
        if self.status != 'delivered' or not self.delivered_at:
            return False
        return (timezone.now() - self.delivered_at).days <= 7
 
    @property
    def tracking_url(self):
        if not self.tracking_number:
            return None
        # Default to Shiprocket tracking if tracking number is present
        if self.courier_name == 'Delhivery':
            return f"https://tracking.delhivery.com/{self.tracking_number}"
        return f"https://shiprocket.co/tracking/{self.tracking_number}"

    @property
    def cleaned_status_logs(self):
        """Returns only the status logs that represent real status transitions, excluding debug/alert logs."""
        logs = self.status_logs.all().order_by('timestamp')
        return [log for log in logs if log.old_status != log.new_status]
 
    @property
    def can_be_refunded(self):
        """True when payment was made via Razorpay and not yet refunded."""
        return (
            self.payment_method == 'razorpay'
            and self.payment_status == 'paid'
            and self.razorpay_payment_id
            and self.status not in ('refund_initiated', 'refunded')
        )

    def update_overall_status(self):
        """Recalculate overall order status based on item statuses."""
        items = self.items.all()
        if not items.exists():
            return
            
        active_items = items.exclude(status__in=['cancelled', 'returned', 'returned_to_source', 'refund_initiated', 'refunded', 'courier_failed_pickup', 'seller_unresponsive'])
        
        status_ranks = {
            'pending': 1,
            'confirmed': 2,
            'processing': 3,
            'shipped': 4,
            'out_for_delivery': 5,
            'delivered': 6,
        }
        
        if active_items.exists():
            min_item = min(active_items, key=lambda item: status_ranks.get(item.status, 1))
            new_overall_status = min_item.status
        else:
            all_statuses = set(item.status for item in items)
            if 'refunded' in all_statuses:
                new_overall_status = 'refunded'
            elif 'refund_initiated' in all_statuses:
                new_overall_status = 'refund_initiated'
            elif 'returned_to_source' in all_statuses:
                new_overall_status = 'returned_to_source'
            elif 'returned' in all_statuses:
                new_overall_status = 'returned'
            elif 'courier_failed_pickup' in all_statuses:
                new_overall_status = 'courier_failed_pickup'
            elif 'seller_unresponsive' in all_statuses:
                new_overall_status = 'seller_unresponsive'
            else:
                new_overall_status = 'cancelled'
                
        if self.status != new_overall_status:
            old_status = self.status
            self.status = new_overall_status
            if new_overall_status == 'shipped' and not self.shipped_at:
                self.shipped_at = timezone.now()
            elif new_overall_status == 'delivered' and not self.delivered_at:
                self.delivered_at = timezone.now()
            self.save(update_fields=['status', 'shipped_at', 'delivered_at', 'status_updated_at'])
            
            # Create status log
            OrderStatusLog.objects.create(
                order=self,
                old_status=old_status,
                new_status=new_overall_status,
                remarks='Overall status updated dynamically based on item statuses.'
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
    
    # Fulfillment tracking per item (ensures multiple sellers can fulfill independently)
    status = models.CharField(max_length=30, choices=Order.STATUS_CHOICES, default='pending')
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    courier_name = models.CharField(max_length=100, blank=True, null=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
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
    def commission_rate(self):
        """Commission rate from the product's category as a Decimal (e.g. 0.05 for 5%)"""
        if self.product and self.product.category:
            pct = self.product.category.commision_percentage
            if pct:
                return Decimal(str(pct)) / Decimal('100')
        return Decimal('0')

    @property
    def commission_amount(self):
        """Total commission for this order item"""
        price = self.price if self.price is not None else Decimal('0.00')
        quantity = self.quantity or 0
        return (price * self.commission_rate * quantity).quantize(Decimal('0.01'))

    @property
    def seller_earnings(self):
        """
        Seller's net earnings for this item.
        If item is cancelled or returned/refunded, earnings are 0.
        Otherwise, it is total - commission.
        """
        if self.status in ('cancelled', 'returned', 'returned_to_source', 'refund_initiated', 'refunded', 'courier_failed_pickup', 'seller_unresponsive') or self.is_returned:
            return Decimal('0.00')
        
        active_qty = self.remaining_quantity
        if active_qty <= 0:
            return Decimal('0.00')
            
        price = self.price if self.price is not None else Decimal('0.00')
        item_total = price * active_qty
        commission = (item_total * self.commission_rate).quantize(Decimal('0.01'))
        return (item_total - commission).quantize(Decimal('0.01'))

    
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

    @property
    def tracking_url(self):
        if not self.tracking_number:
            return None
        if self.courier_name == 'Delhivery':
            return f"https://tracking.delhivery.com/{self.tracking_number}"
        return f"https://shiprocket.co/tracking/{self.tracking_number}"



class OrderStatusLog(BaseModel):
    """Track every status change for audit & tracking timeline"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs')
    old_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30, choices=Order.STATUS_CHOICES)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Email tracking flags
    customer_email_sent = models.BooleanField(default=False)
    seller_email_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.order.unique_order_id}: {self.old_status} → {self.new_status}"

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


class SellerSettlement(BaseModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
    ]

    seller = models.ForeignKey(
        'items.SellerProfile',
        on_delete=models.CASCADE,
        related_name='settlements'
    )
    settlement_id = models.CharField(max_length=20, unique=True, editable=False, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Net amount paid to seller")
    commission_deducted = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text="Platform commission deducted")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True, null=True, help_text="Transaction reference ID")
    settled_at = models.DateTimeField(blank=True, null=True)
    order_items = models.ManyToManyField(OrderItem, related_name='settlements', blank=True)
    razorpay_payout_id = models.CharField(max_length=100, blank=True, null=True, unique=True, help_text="RazorpayX Payout ID")

    def save(self, *args, **kwargs):
        if not self.settlement_id:
            date_str = timezone.now().strftime('%Y%m%d')
            last_settlement = SellerSettlement.objects.filter(
                settlement_id__startswith=f'SET-{date_str}-'
            ).order_by('settlement_id').last()
            
            if last_settlement:
                try:
                    last_num = int(last_settlement.settlement_id.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            self.settlement_id = f'SET-{date_str}-{new_num:04d}'
        
        if self.status == 'processed' and not self.settled_at:
            self.settled_at = timezone.now()
        elif self.status != 'processed':
            self.settled_at = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.settlement_id} | {self.seller.shop_name} | {self.get_status_display()}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Seller Settlement'
        verbose_name_plural = 'Seller Settlements'


from django.db.models.signals import m2m_changed
from django.dispatch import receiver

@receiver(m2m_changed, sender=SellerSettlement.order_items.through)
def update_settlement_totals(sender, instance, action, **kwargs):
    if action in ('post_add', 'post_remove', 'post_clear'):
        total_earnings = Decimal('0.00')
        total_commission = Decimal('0.00')
        for item in instance.order_items.all():
            total_earnings += item.seller_earnings
            total_commission += item.commission_amount
        
        SellerSettlement.objects.filter(pk=instance.pk).update(
            amount=total_earnings,
            commission_deducted=total_commission
        )
        instance.amount = total_earnings
        instance.commission_deducted = total_commission