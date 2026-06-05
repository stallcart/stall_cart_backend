# debug_shiprocket.py
import os
import django
import json
import requests
from django.utils import timezone

# Initialize Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stall_cart.settings")
django.setup()

from django.conf import settings
from orders.models import Order
from delivery.delivery_services import ShiprocketService, repair_address

def run_debug():
    print("=" * 60)
    print("SHIPROCKET API DIAGNOSTICS")
    print("=" * 60)
    
    # 1. Fetch the order
    order_id = "ORD-20260605-000002"
    order = Order.objects.filter(unique_order_id=order_id).first()
    
    if not order:
        print(f"Order {order_id} not found in this database.")
        recent_orders = list(Order.objects.order_by('-created_at')[:5].values_list('unique_order_id', 'status'))
        print(f"Recent orders in database: {recent_orders}")
        if recent_orders:
            order_id = recent_orders[0][0]
            print(f"Falling back to test with recent order: {order_id}")
            order = Order.objects.get(unique_order_id=order_id)
        else:
            print("No orders found in database to test with.")
            return

    print(f"\nOrder Details:")
    print(f"  Order ID: {order.unique_order_id}")
    print(f"  Status: {order.status}")
    print(f"  Payment Method: {order.payment_method}")
    print(f"  Total Amount: {order.total_amount}")
    print(f"  Shipping Address (Raw): {order.shipping_address}")

    # 2. Repair shipping address
    addr = repair_address(order.shipping_address, order)
    print(f"  Shipping Address (Repaired): {addr}")

    # 3. Resolve seller and pickup location
    items = order.items.select_related("product")
    first_item = items.first()
    seller = None
    shop_addr = None
    pickup_loc_name = getattr(settings, "SHIPROCKET_PICKUP_LOCATION", "Primary")
    
    if first_item and first_item.product.seller:
        seller = first_item.product.seller
        print(f"\nSeller Details:")
        print(f"  Seller ID: {seller.id}")
        print(f"  Shop Name: {seller.shop_name}")
        if hasattr(seller, 'shop_address') and seller.shop_address:
            shop_addr = seller.shop_address
            print(f"  Shop Address: line1='{shop_addr.address_line1}', city='{shop_addr.city}', state='{shop_addr.state}', pincode='{shop_addr.postal_code}', phone='{shop_addr.shop_phone}'")
            if shop_addr.address_line1 and shop_addr.city and shop_addr.state and shop_addr.postal_code:
                pickup_loc_name = f"Seller_{seller.id}"
            else:
                print("  WARNING: Shop address has missing fields (line1, city, state, or pincode). Will default to settings.SHIPROCKET_PICKUP_LOCATION")
        else:
            print("  WARNING: Seller has no shop_address profile.")
    else:
        print("\nNo seller/item found in order.")

    print(f"\nResolved Pickup Location Nickname: '{pickup_loc_name}'")

    # 4. Initialize ShiprocketService and get auth token
    srv = ShiprocketService()
    try:
        token = srv._get_token()
        print(f"Shiprocket Auth: SUCCESS (Token starts with {token[:15]}...)")
    except Exception as e:
        print(f"Shiprocket Auth: FAILED: {e}")
        return

    # 5. Register/Ensure Pickup Location
    if seller and shop_addr and pickup_loc_name.startswith("Seller_"):
        print(f"\nAttempting to register pickup location '{pickup_loc_name}' in Shiprocket:")
        # Clean up phone
        clean_phone = "".join(c for c in str(shop_addr.shop_phone or seller.user.phone) if c.isdigit())
        if len(clean_phone) >= 10:
            clean_phone = clean_phone[-10:]
        else:
            clean_phone = "9999999999"
            
        # Clean up pincode
        clean_pincode = "".join(c for c in str(shop_addr.postal_code) if c.isdigit()).strip()
        if len(clean_pincode) != 6:
            clean_pincode = "221005"
            
        # Ensure address contains at least one digit (Shiprocket requires house/flat/road number)
        address_line = (shop_addr.address_line1 or "").strip()
        if not any(c.isdigit() for c in address_line):
            address_line = f"Shop No. 1, {address_line}"
            
        pickup_payload = {
            "pickup_location": pickup_loc_name[:36],
            "name": (shop_addr.shop_name or seller.shop_name or "Seller")[:40],
            "email": shop_addr.shop_email or seller.user.email or "seller@stallcart.in",
            "phone": clean_phone,
            "address": address_line[:80],
            "address_2": shop_addr.address_line2[:80] if shop_addr.address_line2 else "",
            "city": shop_addr.city[:50].strip(),
            "state": shop_addr.state[:50].strip(),
            "pin_code": clean_pincode,
            "pincode": clean_pincode,
            "country": shop_addr.country or "India"
        }
        
        print(f"  Pickup Payload: {json.dumps(pickup_payload, indent=2)}")
        
        try:
            res = requests.post(
                f"https://apiv2.shiprocket.in/v1/external/settings/company/addpickup",
                json=pickup_payload,
                headers=srv._headers(),
                timeout=10
            )
            print(f"  Status Code: {res.status_code}")
            print(f"  Response Body: {res.text}")
        except Exception as e:
            print(f"  Pickup Registration Request Exception: {e}")

    # 6. Test Adhoc Order Creation Payload
    full_name = addr.get("name", "").strip()
    name_parts = full_name.split(None, 1)
    first_name = name_parts[0] if name_parts else "Customer"
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    email_val = ""
    if order.user and order.user.email:
        email_val = order.user.email.strip()
    elif order.guest_email:
        email_val = order.guest_email.strip()
    if not email_val or "@" not in email_val:
        email_val = "customer@stallcart.in"

    order_payload = {
        "order_id": order.unique_order_id,
        "order_date": order.created_at.strftime("%Y-%m-%d %H:%M"),
        "channel_id": getattr(settings, "SHIPROCKET_CHANNEL_ID", ""),
        "pickup_location": pickup_loc_name,
        
        "billing_customer_name": first_name,
        "billing_last_name": last_name,
        "billing_address": addr.get("address_line1", ""),
        "billing_address_2": addr.get("address_line2", ""),
        "billing_city": addr.get("city", ""),
        "billing_pincode": addr.get("postal_code", ""),
        "billing_state": addr.get("state", ""),
        "billing_country": addr.get("country", "India"),
        "billing_email": email_val,
        "billing_phone": addr.get("phone", ""),
        
        "shipping_is_billing": True,
        "shipping_customer_name": first_name,
        "shipping_last_name": last_name,
        "shipping_address": addr.get("address_line1", ""),
        "shipping_address_2": addr.get("address_line2", ""),
        "shipping_city": addr.get("city", ""),
        "shipping_pincode": addr.get("postal_code", ""),
        "shipping_state": addr.get("state", ""),
        "shipping_country": addr.get("country", "India"),
        "shipping_email": email_val,
        "shipping_phone": addr.get("phone", ""),
        
        "order_items": [
            {
                "name": item.product.name,
                "sku": str(item.product.id),
                "units": item.quantity,
                "selling_price": float(item.price),
            }
            for item in items
        ],
        "payment_method": "Prepaid" if order.payment_method == "razorpay" else "COD",
        "sub_total": float(order.total_amount - order.delivery_charge),
        "length": 10,
        "breadth": 10,
        "height": 10,
        "weight": 0.5,
    }

    print(f"\nOrder Creation Payload:")
    print(json.dumps(order_payload, indent=2))

    print(f"\nSending Order Creation Request to Shiprocket:")
    try:
        res = requests.post(
            f"https://apiv2.shiprocket.in/v1/external/orders/create/adhoc",
            json=order_payload,
            headers=srv._headers(),
            timeout=15
        )
        print(f"  Status Code: {res.status_code}")
        print(f"  Response Body: {res.text}")
    except Exception as e:
        print(f"  Order Creation Request Exception: {e}")

if __name__ == "__main__":
    run_debug()
