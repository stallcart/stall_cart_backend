# update_order_shipment.py
import os
import django

# Initialize Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stall_cart.settings")
django.setup()

from orders.models import Order, OrderStatusLog
from delivery.delivery_services import ShiprocketService

def main():
    order_id = "ORD-20260605-000002"
    shipment_id = 1379235656
    
    order = Order.objects.filter(unique_order_id=order_id).first()
    if not order:
        print(f"Order {order_id} not found in database.")
        return
        
    srv = ShiprocketService()
    print(f"Assigning AWB courier for shipment ID {shipment_id}...")
    awb_data = srv._assign_awb(shipment_id)
    print(f"AWB Assignment Result: {awb_data}")
    
    if awb_data.get("awb_code"):
        order.tracking_number = awb_data.get("awb_code")
        order.courier_name = awb_data.get("courier_name") or "Shiprocket"
        if awb_data.get("estimated_delivery"):
            from datetime import datetime
            try:
                order.estimated_delivery = datetime.strptime(awb_data["estimated_delivery"], "%Y-%m-%d").date()
            except Exception:
                pass
        order.status = "processing"
        order.save()
        
        OrderStatusLog.objects.create(
            order=order,
            old_status=order.status,
            new_status=order.status,
            remarks=f"Successfully linked to existing Shiprocket shipment {shipment_id} (AWB: {order.tracking_number}, Courier: {order.courier_name})"
        )
        print("Success! Order updated successfully in database.")
    else:
        print("Could not assign AWB. Please verify if your Shiprocket account has enough recharge balance and the customer pincode is serviceable.")

if __name__ == "__main__":
    main()
