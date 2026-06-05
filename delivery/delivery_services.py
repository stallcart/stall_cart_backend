
import requests
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
 
logger = logging.getLogger(__name__)
 
SHIPROCKET_API = "https://apiv2.shiprocket.in/v1/external"

import re

def repair_address(addr, order=None):
    """
    Attempts to repair missing fields in the address dictionary
    by extracting them from other fields or looking up the user's default address.
    """
    if not isinstance(addr, dict):
        addr = {}
    else:
        addr = addr.copy()

    # Clean up keys and values
    for k, v in list(addr.items()):
        if isinstance(v, str):
            addr[k] = v.strip()

    # 1. If user is present and we have missing critical fields, try to get them from their active addresses
    if order and order.user and (not addr.get("postal_code") or not addr.get("city") or not addr.get("state")):
        try:
            default_addr = order.user.addresses.filter(is_active=True).first()
            if default_addr:
                if not addr.get("name"): addr["name"] = default_addr.name
                if not addr.get("phone"): addr["phone"] = default_addr.phone
                if not addr.get("address_line1"): addr["address_line1"] = default_addr.address_line1
                if not addr.get("address_line2"): addr["address_line2"] = default_addr.address_line2
                if not addr.get("city"): addr["city"] = default_addr.city
                if not addr.get("state"): addr["state"] = default_addr.state
                if not addr.get("postal_code"): addr["postal_code"] = default_addr.postal_code
                if not addr.get("country"): addr["country"] = default_addr.country
        except Exception as e:
            logger.warning(f"Failed to load user addresses for fallback: {e}")

    # 2. Clean up state if it got contaminated with pincode (e.g. "Uttar Pradesh - 221005" or "UP – 221001")
    if addr.get("state"):
        state_val = str(addr["state"])
        for separator in ["-", "–"]:
            if separator in state_val:
                parts = state_val.split(separator)
                if len(parts) > 1 and parts[1].strip().isdigit() and len(parts[1].strip()) == 6:
                    if not addr.get("postal_code"):
                        addr["postal_code"] = parts[1].strip()
                    addr["state"] = parts[0].strip()
                    break

    # 3. Try to extract postal code (6-digit pincode for India) from any address fields if still missing
    if not addr.get("postal_code"):
        full_text = " ".join([str(addr.get(k, "")) for k in ["address_line1", "address_line2", "city", "state"] if addr.get(k)])
        pincode_match = re.search(r"\b\d{6}\b", full_text)
        if pincode_match:
            addr["postal_code"] = pincode_match.group(0)

    # Clean up keys and values again after any edits
    for k, v in list(addr.items()):
        if isinstance(v, str):
            addr[k] = v.strip()
            
    return addr


class ShiprocketService:
    """Handles Shiprocket API operations."""

    def __init__(self):
        self._token = None
        self._token_expiry = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _get_token(self):
        """Get/refresh Shiprocket JWT token (valid 10 days)."""
        if self._token and self._token_expiry and timezone.now() < self._token_expiry:
            return self._token

        try:
            res = requests.post(
                f"{SHIPROCKET_API}/auth/login",
                json={
                    "email": settings.SHIPROCKET_EMAIL,
                    "password": settings.SHIPROCKET_PASSWORD,
                },
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            self._token = data["token"]
            self._token_expiry = timezone.now() + timedelta(days=9)
            return self._token
        except Exception as e:
            logger.error(f"Shiprocket auth failed: {e}")
            raise

    def _headers(self):
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    # ── Create Order + Shipment ────────────────────────────────────────────────

    def create_shipment(self, order):
        """
        Create a Shiprocket order and request AWB + courier assignment.
        Returns dict with shiprocket_order_id, shipment_id, awb, courier_name.
        Call this when order status moves to 'processing' or 'confirmed'.
        """
        # Try to repair and clean the address
        addr = repair_address(order.shipping_address, order)
        if addr != order.shipping_address:
            order.shipping_address = addr
            order.save(update_fields=["shipping_address"])

        items = order.items.select_related("product")
 
        order_payload = {
            "order_id": order.unique_order_id,
            "order_date": order.created_at.strftime("%Y-%m-%d %H:%M"),
            "channel_id": getattr(settings, "SHIPROCKET_CHANNEL_ID", ""),
            "pickup_location": getattr(settings, "SHIPROCKET_PICKUP_LOCATION", "Primary"),
            "billing_customer_name": addr.get("name", ""),
            "billing_last_name": "",
            "billing_address": addr.get("address_line1", ""),
            "billing_address_2": addr.get("address_line2", ""),
            "billing_city": addr.get("city", ""),
            "billing_pincode": addr.get("postal_code", ""),
            "billing_state": addr.get("state", ""),
            "billing_country": addr.get("country", "India"),
            "billing_email": order.user.email if order.user else order.guest_email or "",
            "billing_phone": addr.get("phone", ""),
            "shipping_is_billing": True,
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
            "length": 10,   # cm — update with real product dimensions
            "breadth": 10,
            "height": 10,
            "weight": 0.5,  # kg — update with real product weight
        }

        # Validate that all required fields are present for Shiprocket
        required_fields = {
            "billing_customer_name": order_payload["billing_customer_name"],
            "billing_address": order_payload["billing_address"],
            "billing_city": order_payload["billing_city"],
            "billing_pincode": order_payload["billing_pincode"],
            "billing_state": order_payload["billing_state"],
            "billing_phone": order_payload["billing_phone"],
        }
        missing = [k for k, v in required_fields.items() if not str(v).strip()]
        if missing:
            err_msg = f"Missing required address fields: {', '.join(missing)}"
            logger.error(f"Cannot push order {order.unique_order_id} to Shiprocket. {err_msg}")
            return {"success": False, "error": err_msg}

        try:
            res = requests.post(
                f"{SHIPROCKET_API}/orders/create/adhoc",
                json=order_payload,
                headers=self._headers(),
                timeout=15,
            )
            res.raise_for_status()
            data = res.json()
            logger.info(f"Shiprocket order created: {data}")
 
            shiprocket_order_id = data.get("order_id")
            shipment_id = data.get("shipment_id")
 
            # Auto-assign best courier
            awb_data = self._assign_awb(shipment_id)
 
            return {
                "success": True,
                "shiprocket_order_id": shiprocket_order_id,
                "shipment_id": shipment_id,
                "awb": awb_data.get("awb_code"),
                "courier_name": awb_data.get("courier_name"),
                "courier_id": awb_data.get("courier_id"),
                "estimated_delivery": awb_data.get("etd"),
            }
 
        except requests.exceptions.HTTPError as e:
            logger.error(f"Shiprocket create order HTTP error: {e.response.text}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Shiprocket create order error: {e}")
            return {"success": False, "error": str(e)}
 
    def _assign_awb(self, shipment_id):
        """Auto-assign best courier and get AWB number."""
        try:
            res = requests.post(
                f"{SHIPROCKET_API}/courier/assign/awb",
                json={"shipment_id": str(shipment_id)},
                headers=self._headers(),
                timeout=15,
            )
            res.raise_for_status()
            data = res.json()
            response = data.get("response", {}).get("data", {})
            return {
                "awb_code": response.get("awb_code"),
                "courier_name": response.get("courier_name"),
                "courier_id": response.get("courier_company_id"),
                "etd": response.get("etd"),
            }
        except Exception as e:
            logger.error(f"Shiprocket AWB assignment failed: {e}")
            return {}
 
    # ── Tracking ──────────────────────────────────────────────────────────────
 
    def get_tracking(self, awb_code):
        """
        Get real-time tracking info for an AWB.
        Returns list of tracking events.
        """
        try:
            res = requests.get(
                f"{SHIPROCKET_API}/courier/track/awb/{awb_code}",
                headers=self._headers(),
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            tracking_data = data.get("tracking_data", {})
            shipment_track = tracking_data.get("shipment_track", [{}])
            activities = tracking_data.get("shipment_track_activities", [])
 
            current = shipment_track[0] if shipment_track else {}
            return {
                "current_status": current.get("current_status"),
                "delivered_date": current.get("delivered_date"),
                "etd": current.get("etd"),
                "activities": [
                    {
                        "date": a.get("date"),
                        "activity": a.get("activity"),
                        "location": a.get("location"),
                        "status": a.get("sr-status-label"),
                    }
                    for a in activities
                ],
            }
        except Exception as e:
            logger.error(f"Shiprocket tracking error for {awb_code}: {e}")
            return {}
 
    # ── Cancel Shipment ───────────────────────────────────────────────────────
 
    def cancel_shipment(self, shiprocket_order_ids: list):
        """Cancel one or more Shiprocket orders."""
        try:
            res = requests.post(
                f"{SHIPROCKET_API}/orders/cancel",
                json={"ids": shiprocket_order_ids},
                headers=self._headers(),
                timeout=10,
            )
            res.raise_for_status()
            return {"success": True, "data": res.json()}
        except Exception as e:
            logger.error(f"Shiprocket cancel error: {e}")
            return {"success": False, "error": str(e)}
 
    # ── Generate Pickup Request ────────────────────────────────────────────────
 
    def generate_pickup(self, shipment_ids: list):
        """Schedule pickup for given shipment IDs."""
        try:
            res = requests.post(
                f"{SHIPROCKET_API}/courier/generate/pickup",
                json={"shipment_id": shipment_ids},
                headers=self._headers(),
                timeout=10,
            )
            res.raise_for_status()
            return {"success": True, "data": res.json()}
        except Exception as e:
            logger.error(f"Shiprocket pickup error: {e}")
            return {"success": False, "error": str(e)}
 
    # ── Print Label ───────────────────────────────────────────────────────────
 
    def get_label_url(self, shipment_id):
        """Get PDF label URL for printing."""
        try:
            res = requests.post(
                f"{SHIPROCKET_API}/courier/generate/label",
                json={"shipment_id": [shipment_id]},
                headers=self._headers(),
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            return data.get("label_url")
        except Exception as e:
            logger.error(f"Shiprocket label error: {e}")
            return None

    # ── Check Serviceability ──────────────────────────────────────────────────

    def check_serviceability(self, delivery_postcode, pickup_postcode="110001", weight=0.5, cod=True):
        """
        Check courier serviceability and get estimated delivery days.
        Returns dict with:
          - 'success': bool
          - 'delivery_days': int
          - 'courier_name': str
          - 'etd': str
          - 'rate': float
        """
        try:
            params = {
                "pickup_postcode": pickup_postcode,
                "delivery_postcode": delivery_postcode,
                "weight": weight,
                "cod": 1 if cod else 0,
            }
            res = requests.get(
                f"{SHIPROCKET_API}/courier/serviceability/",
                params=params,
                headers=self._headers(),
                timeout=10,
            )
            res.raise_for_status()
            data = res.json()
            
            company_data = data.get("data", {}).get("available_courier_companies", [])
            if not company_data:
                raise ValueError("No courier company available for this pincode")
                
            best_courier = company_data[0]
            etd = best_courier.get("etd")
            
            delivery_days = 4
            if etd:
                from datetime import datetime
                try:
                    etd_date = datetime.strptime(etd, "%Y-%m-%d").date()
                    delta = (etd_date - timezone.now().date()).days
                    if delta > 0:
                        delivery_days = delta
                except Exception:
                    pass
                    
            return {
                "success": True,
                "delivery_days": delivery_days,
                "courier_name": best_courier.get("courier_company_name", best_courier.get("courier_name")),
                "etd": etd,
                "rate": float(best_courier.get("rate", 0)),
            }
        except Exception as e:
            logger.warning(f"Shiprocket serviceability query failed for {delivery_postcode}: {e}")
            # Fallback estimation based on India's pincode zones
            try:
                pin_prefix = int(str(delivery_postcode)[:2])
            except Exception:
                pin_prefix = 11
                
            # Rule-based calculation (Delhi region = 3 days, Metros = 4 days, others = 6 days)
            if pin_prefix in [11, 12, 13, 20, 21, 22, 23, 24, 25, 26, 27, 28, 30]:
                delivery_days = 3
            elif pin_prefix in [40, 41, 42, 56, 57, 58, 60, 61, 62, 70]:
                delivery_days = 4
            else:
                delivery_days = 6
                
            return {
                "success": False,
                "delivery_days": delivery_days,
                "estimated_date": (timezone.now() + timedelta(days=delivery_days)).strftime("%d %b"),
                "is_fallback": True
            }


def auto_push_order_to_shiprocket(order):
    """
    Checks if Shiprocket credentials are set, and pushes the order if confirmed.
    Saves AWB and courier info.
    """
    from django.conf import settings
    email = getattr(settings, 'SHIPROCKET_EMAIL', None)
    password = getattr(settings, 'SHIPROCKET_PASSWORD', None)
    if not email or not password:
        logger.warning("Shiprocket credentials not configured. Skipping auto-push.")
        return
        
    if order.status in ['confirmed', 'processing'] and not order.tracking_number:
        try:
            srv = ShiprocketService()
            res = srv.create_shipment(order)
            if res.get('success') and res.get('awb'):
                order.tracking_number = res.get('awb')
                order.courier_name = res.get('courier_name', 'Shiprocket')
                if res.get('estimated_delivery'):
                    from datetime import datetime
                    try:
                        order.estimated_delivery = datetime.strptime(res['estimated_delivery'], "%Y-%m-%d").date()
                    except Exception:
                        pass
                order.save(update_fields=['tracking_number', 'courier_name', 'estimated_delivery', 'updated_at'])
                logger.info(f"Automatically pushed order {order.unique_order_id} to Shiprocket. AWB: {order.tracking_number}")
                
                # Create a status log for tracing the Shiprocket push
                from orders.models import OrderStatusLog
                OrderStatusLog.objects.create(
                    order=order,
                    old_status=order.status,
                    new_status=order.status,
                    remarks=f"Automatically pushed to Shiprocket (AWB: {order.tracking_number}, Courier: {order.courier_name})"
                )
            else:
                logger.error(f"Failed to auto-push order {order.unique_order_id} to Shiprocket: {res.get('error')}")
        except Exception as e:
            logger.error(f"Error during auto-pushing order to Shiprocket: {e}", exc_info=True)