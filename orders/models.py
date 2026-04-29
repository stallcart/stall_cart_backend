from django.db import models
from django.conf import settings
import uuid
from common.models import BaseModel

class Order(BaseModel):
    STATUS_CHOICES = [('Pending','Pending'), ('Processing','Processing'), ('Shipped','Shipped'), ('Out for Delivery','Out for Delivery'), ('Delivered','Delivered'), ('Cancelled','Cancelled')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    address = models.JSONField()
    payment_method = models.CharField(max_length=50, default='COD')
    payment_status = models.CharField(max_length=20, default='Pending')
    def __str__(self): return f"Order #{str(self.id)[:8]} | {self.status}"

class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('items.Product', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    def __str__(self): return f"{self.product.name} x{self.quantity}"