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
    help = "Sync missing Shiprocket AWB tracking numbers for processing/confirmed orders and send email alerts if needed"

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("Starting Shiprocket AWB Sync Job...")
        self.stdout.write("=" * 60)

        # 1. Initialize Shiprocket service and authenticate
        srv = ShiprocketService()
        try:
            token = srv._get_token()
            self.stdout.write(f"Authenticated with Shiprocket API successfully.")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Shiprocket authentication failed: {e}"))
            return

        # 2. Query orders pending AWB tracking numbers
        orders = Order.objects.filter(
            status__in=['confirmed', 'processing'],
            tracking_number__isnull=True
        ) | Order.objects.filter(
            status__in=['confirmed', 'processing'],
            tracking_number=''
        )
        # Remove duplicate querysets and fetch unique list
        orders = orders.distinct()

        self.stdout.write(f"Found {orders.count()} order(s) requiring AWB synchronization.")

        for order in orders:
            self.stdout.write("-" * 50)
            self.stdout.write(f"Checking Order {order.unique_order_id} (Status: {order.status})...")

            try:
                # 3. Query Shiprocket for the order details using channel_order_id
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
                    self.stdout.write(self.style.WARNING(f"Shiprocket API returned status {res.status_code} for order {order.unique_order_id}: {res.text}"))
                    continue

                orders_list = res.json().get("data", [])
                if not orders_list:
                    self.stdout.write(f"Order {order.unique_order_id} not found on Shiprocket system yet.")
                    continue

                # Parse the matching order object
                sr_order = None
                for o in orders_list:
                    if o.get("channel_order_id") == order.unique_order_id:
                        sr_order = o
                        break

                if not sr_order:
                    self.stdout.write(f"No exact channel order matching {order.unique_order_id} found in Shiprocket results.")
                    continue

                self.stdout.write(f"Found order in Shiprocket (Shiprocket ID: {sr_order.get('id')}). Checking shipment tracking details...")

                # 4. Extract AWB and Courier details
                awb_code = sr_order.get("awb_code") or sr_order.get("awb")
                courier_name = sr_order.get("courier_name")
                
                # Check nested shipments array if flat fields are empty
                if not awb_code:
                    shipments = sr_order.get("shipments", [])
                    if shipments:
                        first_shipment = shipments[0]
                        awb_code = first_shipment.get("awb_code") or first_shipment.get("awb")
                        courier_name = first_shipment.get("courier_name") or first_shipment.get("courier_company_name")

                # Recipient list setup (Sellers & Admin)
                seller_emails = set()
                for item in order.items.all():
                    if item.product.seller and item.product.seller.user.email:
                        seller_emails.add(item.product.seller.user.email.strip())

                admin_emails = list(User.objects.filter(is_superuser=True).exclude(email='').values_list('email', flat=True))
                if not admin_emails:
                    admin_emails = [getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@stallcart.in')]
                
                recipient_list = list(seller_emails) + admin_emails
                recipient_list = [email for email in recipient_list if email]

                # 5. Handle tracking assignment/alerts
                if awb_code and str(awb_code).strip():
                    awb_code = str(awb_code).strip()
                    courier_name = str(courier_name or "Shiprocket").strip()
                    self.stdout.write(self.style.SUCCESS(f"Tracking AWB detected: {awb_code} ({courier_name}). Updating database..."))

                    # Update order
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
                    self.stdout.write(f"Order exists in Shiprocket but has no tracking AWB assigned yet.")

                    # Check if alert email has already been sent
                    alert_exists = OrderStatusLog.objects.filter(
                        order=order,
                        remarks__contains="Sent manual AWB update alert email"
                    ).exists()

                    if not alert_exists:
                        self.stdout.write("No previous alert email sent. Dispatching manual update notification to seller/admin...")

                        # Resolve pickup location label
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

                        # Send the alert email
                        email_sent = send_dynamic_email('admin_seller_awb_alert', recipient_list, context)
                        if email_sent:
                            # Log that the alert was sent to prevent repeating on next runs
                            OrderStatusLog.objects.create(
                                order=order,
                                old_status=order.status,
                                new_status=order.status,
                                remarks="⚠️ Sent manual AWB update alert email to seller/admin. Awaiting tracking details."
                            )
                            self.stdout.write("Alert email dispatched successfully and logged.")
                    else:
                        self.stdout.write("Manual AWB update alert email was already sent previously. Skipping email dispatch to avoid spam.")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error checking order {order.unique_order_id}: {e}"))
                logger.error(f"AWB Sync command error for order {order.unique_order_id}: {e}", exc_info=True)

        self.stdout.write("\nAWB sync job complete.")
