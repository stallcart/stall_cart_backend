# update_order_shipment.py
import os
import django
import requests
import json

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
    
    headers = srv._headers()
    
    # Let's call the API directly and print the response
    try:
        res = requests.post(
            "https://apiv2.shiprocket.in/v1/external/courier/assign/awb",
            json={"shipment_id": str(shipment_id)},
            headers=headers,
            timeout=15
        )
        print(f"AWB API Status Code: {res.status_code}")
        print(f"AWB API Response Body: {res.text}")
        
        if res.status_code == 200:
            data = res.json()
            response = data.get("response", {}).get("data", {})
            awb_code = response.get("awb_code")
            courier_name = response.get("courier_name")
            
            if awb_code:
                order.tracking_number = awb_code
                order.courier_name = courier_name or "Shiprocket"
                if response.get("etd"):
                    from datetime import datetime
                    try:
                        order.estimated_delivery = datetime.strptime(response["etd"], "%Y-%m-%d").date()
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
                return
            else:
                print("No AWB code in response data.")
        else:
            print("API call returned non-200 status.")
            
    except Exception as e:
        print(f"Exception during AWB assignment call: {e}")
        
    # Fallback/alternative if auto-assign is not working (e.g. because they need to choose a courier first)
    # Let's print a manual linking option
    print("\n--- ALTERNATIVE MANUAL UPDATE ---")
    print(f"If you see the order in your Shiprocket panel, you can click 'Ship Now' to generate the AWB manually.")
    print(f"Once you have the AWB and Courier name, you can update this order in your admin panel or we can link it.")

if __name__ == "__main__":
    main()
