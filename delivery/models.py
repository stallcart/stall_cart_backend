from django.db import models
from django.conf import settings
import uuid
from common.models import BaseModel

class DeliveryPartner(BaseModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delivery_profile')
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
    aadhar_id = models.CharField(max_length=20, unique=True)
    current_address = models.TextField()
    status = models.CharField(max_length=20, default='Pending', choices=[('Pending','Pending'), ('Active','Active'), ('Suspended','Suspended')])
    delivered_count = models.PositiveIntegerField(default=0)
    def __str__(self): return f"{self.full_name} ({self.phone})"

class DeliveryTask(BaseModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='delivery_task')
    partner = models.ForeignKey(DeliveryPartner, on_delete=models.SET_NULL, null=True, related_name='tasks')
    status = models.CharField(max_length=20, default='Assigned', choices=[('Assigned','Assigned'), ('Out for Delivery','Out for Delivery'), ('Delivered','Delivered')])
    delivery_otp = models.CharField(max_length=6, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    def save(self, *args, **kwargs):
        if not self.delivery_otp:
            import random
            self.delivery_otp = str(random.randint(100000, 999999))
        super().save(*args, **kwargs)
    def __str__(self): return f"Task #{str(self.id)[:8]}"