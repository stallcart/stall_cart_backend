# orders/management/commands/sync_shiprocket_awb.py
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
import requests
import logging

from orders.models import Order, OrderStatusLog
from accounts.models import User
from delivery.delivery_services import ShiprocketService
from common.email_service import send_dynamic_email
from common.notification_service import notify_order_status_change

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Sync missing Shiprocket AWB numbers and auto-update tracking status for active shipments"

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("Starting Shiprocket AWB & Status Sync Job...")
        self.stdout.write("=" * 60)

        # Initialize Shiprocket service and authenticate
        srv = ShiprocketService()
        try:
            token = srv._get_token()
            self.stdout.write("Authenticated with Shiprocket API successfully.")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Shiprocket authentication failed: {e}"))
            return

        # ── PART 1: Sync Missing AWBs ──────────────────────────────────────────
        orders_missing_awb = Order.objects.filter(
            status__in=['confirmed', 'processing'],
            tracking_number__isnull=True
        ) | Order.objects.filter(
            status__in=['confirmed', 'processing'],
            tracking_number=''
        )
        orders_missing_awb = orders_missing_awb.distinct()

        self.stdout.write(f"\n[Part 1] Checking {orders_missing_awb.count()} order(s) missing AWB tracking numbers...")

        for order in orders_missing_awb:
            self.stdout.write(f"Checking Order {order.unique_order_id} for AWB...")
            try:
                res = requests.get(
                    "https://apiv2.shiprocket.in/v1/external/orders",
                    params={
                        "filter_by": "channel_order_id",
                        "filter": order.unique_order_id
                    },
                    headers=srv._headers(),
                    timeout=15
                )

                if res.status_code != 200:
                    self.stdout.write(self.style.WARNING(f"Shiprocket API returned status {res.status_code} for order {order.unique_order_id}"))
                    continue

                orders_list = res.json().get("data", [])
                sr_order = None
                for o in orders_list:
                    if o.get("channel_order_id") == order.unique_order_id:
                        sr_order = o
                        break

                if not sr_order:
                    self.stdout.write(f"  Order {order.unique_order_id} not found on Shiprocket system yet.")
                    continue

                awb_code = sr_order.get("awb_code") or sr_order.get("awb")
                courier_name = sr_order.get("courier_name")
                
                # Check nested shipments array if flat fields are empty
                if not awb_code:
                    shipments = sr_order.get("shipments", [])
                    if shipments:
                        first_shipment = shipments[0]
                        awb_code = first_shipment.get("awb_code") or first_shipment.get("awb")
                        courier_name = first_shipment.get("courier_name") or first_shipment.get("courier_company_name")

                # Setup recipient list (Sellers & Admin)
                seller_emails = set()
                for item in order.items.all():
                    if item.product.seller and item.product.seller.user.email:
                        seller_emails.add(item.product.seller.user.email.strip())

                admin_emails = list(User.objects.filter(is_superuser=True).exclude(email='').values_list('email', flat=True))
                if not admin_emails:
                    admin_emails = [getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@stallcart.in')]
                
                recipient_list = list(seller_emails) + admin_emails
                recipient_list = [email for email in recipient_list if email]

                if awb_code and str(awb_code).strip():
                    awb_code = str(awb_code).strip()
                    courier_name = str(courier_name or "Shiprocket").strip()
                    self.stdout.write(self.style.SUCCESS(f"  AWB detected: {awb_code} ({courier_name}). Updating database..."))

                    # Update order AWB
                    old_status = order.status
                    order.tracking_number = awb_code
                    order.courier_name = courier_name
                    order.status = 'processing'
                    order.save(update_fields=['tracking_number', 'courier_name', 'status', 'updated_at'])

                    # Log the status change
                    OrderStatusLog.objects.create(
                        order=order,
                        old_status=old_status,
                        new_status=order.status,
                        remarks=f"🔄 Automatically synced tracking details from Shiprocket (AWB: {awb_code}, Courier: {courier_name})"
                    )

                    # Send AWB Assignment notification email
                    context = {
                        "order_id": order.unique_order_id,
                        "tracking_number": awb_code,
                        "courier_name": courier_name,
                        "admin_order_url": f"https://stallcart.in/orders/admin/order/{order.unique_order_id}/"
                    }
                    send_dynamic_email('awb_assigned_notification', recipient_list, context)
                    
                    # Trigger customer app notifications
                    try:
                        notify_order_status_change(order, old_status, order.status)
                    except Exception as ex:
                        logger.error(f"Failed to send customer status change notification: {ex}")

                else:
                    self.stdout.write(f"  Order exists in Shiprocket but has no tracking AWB assigned yet.")

                    # Check if alert email has already been sent
                    alert_exists = OrderStatusLog.objects.filter(
                        order=order,
                        remarks__contains="Sent manual AWB update alert email"
                    ).exists()

                    if not alert_exists:
                        self.stdout.write("  Dispatching manual AWB update notification to seller/admin...")
                        pickup_loc = "Primary"
                        try:
                            first_item = order.items.first()
                            if first_item and first_item.product.seller:
                                seller = first_item.product.seller
                                if hasattr(seller, 'shop_address') and seller.shop_address:
                                    sa = seller.shop_address
                                    pickup_loc = f"Seller_{seller.id} ({sa.shop_name} - {sa.city}, {sa.state})"
                        except Exception:
                            pass

                        context = {
                            "order_id": order.unique_order_id,
                            "status": order.get_status_display(),
                            "pickup_location": pickup_loc,
                            "customer_name": order.shipping_address.get('name', 'Customer'),
                            "admin_order_url": f"https://stallcart.in/orders/admin/order/{order.unique_order_id}/"
                        }

                        email_sent = send_dynamic_email('admin_seller_awb_alert', recipient_list, context)
                        if email_sent:
                            OrderStatusLog.objects.create(
                                order=order,
                                old_status=order.status,
                                new_status=order.status,
                                remarks="⚠️ Sent manual AWB update alert email to seller/admin. Awaiting tracking details."
                            )
                            self.stdout.write("  Alert email dispatched and logged.")
                    else:
                        self.stdout.write("  Manual AWB update alert email already sent. Skipping.")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error checking AWB for order {order.unique_order_id}: {e}"))
                logger.error(f"AWB Sync error for order {order.unique_order_id}: {e}", exc_info=True)

        # ── PART 2: Sync Delivery Statuses ─────────────────────────────────────
        active_tracked_orders = Order.objects.filter(
            status__in=['confirmed', 'processing', 'shipped', 'out_for_delivery'],
            tracking_number__isnull=False
        ).exclude(tracking_number='').distinct()

        self.stdout.write(f"\n[Part 2] Checking {active_tracked_orders.count()} active tracked order(s) for status updates...")

        status_map = {
            'AWB Assigned': 'confirmed',
            'Manifested': 'processing',
            'In Transit': 'shipped',
            'Shipped': 'shipped',
            'Out for Delivery': 'out_for_delivery',
            'Delivered': 'delivered',
            'RTO': 'returned_to_source',
            'Returned to Source': 'returned_to_source',
            'Cancelled': 'cancelled'
        }

        for order in active_tracked_orders:
            self.stdout.write(f"Querying status for Order {order.unique_order_id} (AWB: {order.tracking_number})...")
            try:
                tracking_data = srv.get_tracking(order.tracking_number)
                sr_status = tracking_data.get("current_status")

                if not sr_status:
                    self.stdout.write(f"  No tracking status returned from Shiprocket for AWB {order.tracking_number}.")
                    continue

                sr_status = sr_status.strip()
                new_local_status = status_map.get(sr_status)
                self.stdout.write(f"  Shiprocket Status: '{sr_status}' -> Mapped Local Status: '{new_local_status}'")

                if new_local_status and new_local_status != order.status:
                    old_status = order.status
                    order.status = new_local_status
                    update_fields = ['status', 'updated_at']

                    if new_local_status == 'delivered':
                        order.delivered_at = timezone.now()
                        update_fields.append('delivered_at')
                    elif new_local_status == 'shipped' and not order.shipped_at:
                        order.shipped_at = timezone.now()
                        update_fields.append('shipped_at')

                    order.save(update_fields=update_fields)

                    # Log the automatic status update
                    OrderStatusLog.objects.create(
                        order=order,
                        old_status=old_status,
                        new_status=new_local_status,
                        remarks=f"🔄 Automatically updated status via Shiprocket Sync (Status: {sr_status})"
                    )

                    self.stdout.write(self.style.SUCCESS(f"  Successfully updated status from '{old_status}' to '{new_local_status}'!"))

                    # Trigger push notifications & emails
                    try:
                        notify_order_status_change(order, old_status, order.status)
                    except Exception as ex:
                        logger.error(f"Failed to trigger status change notification: {ex}")
                else:
                    self.stdout.write("  Status is already up-to-date. No changes made.")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error querying tracking status for order {order.unique_order_id}: {e}"))
                logger.error(f"Status sync error for order {order.unique_order_id}: {e}", exc_info=True)

        self.stdout.write("\nShiprocket sync job complete.")
