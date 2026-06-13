# orders/management/commands/sync_shiprocket_awb.py
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
import requests
import logging

from orders.models import Order, OrderStatusLog, SystemActivityLog, SHIPROCKET_STATUS_MAP
from accounts.models import User
from delivery.delivery_services import ShiprocketService
from common.email_service import send_dynamic_email
from common.notification_service import notify_order_status_change

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Sync missing Shiprocket AWB numbers and auto-update tracking status for active shipments"

    def handle(self, *args, **options):
        # Check global background jobs status
        from common.models import SiteSettings
        if not SiteSettings.get_singleton().enable_background_jobs:
            self.stdout.write(self.style.WARNING("Background jobs are globally disabled in Site Settings. Exiting..."))
            return

        self.stdout.write("=" * 60)
        self.stdout.write("Starting StallCart Background Jobs & Sync...")
        self.stdout.write("=" * 60)

        # Log background job start
        SystemActivityLog.log(
            event_type='system_job',
            description="Background System Job 'sync_shiprocket_awb' started.",
            status='success'
        )

        # Initialize Shiprocket service and authenticate
        srv = ShiprocketService()
        try:
            token = srv._get_token()
            self.stdout.write("Authenticated with Shiprocket API successfully. Starting Sync...")
            self.run_shiprocket_sync(srv, token)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Shiprocket sync skipped/failed: {e}"))
            SystemActivityLog.log(
                event_type='system_job',
                description=f"Shiprocket sync sub-task failed: {e}",
                status='failed'
            )

        self.run_email_retry()

        # Run automatic refund processing job
        try:
            from django.core.management import call_command
            call_command('process_refunds')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Refund processing command execution failed: {e}"))

        # Run automatic seller settlements job
        try:
            from django.core.management import call_command
            call_command('auto_settle_sellers')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Automatic seller settlements command execution failed: {e}"))

        # Log background job completion
        SystemActivityLog.log(
            event_type='system_job',
            description="Background System Job 'sync_shiprocket_awb' completed successfully.",
            status='success'
        )

    def run_shiprocket_sync(self, srv, token):

        # ── PART 1: Sync Missing AWBs & Ensure Consistency ──────────────────────
        from orders.models import OrderItem
        active_items = OrderItem.objects.filter(
            order__status__in=['confirmed', 'processing']
        )
        
        # Get distinct (order_id, seller_id) pairs
        distinct_pairs = list(active_items.values_list('order_id', 'seller_id').distinct())

        self.stdout.write(f"\n[Part 1] Checking {len(distinct_pairs)} active seller shipment(s) for AWBs and consistency...")

        for order_id, seller_id in distinct_pairs:
            try:
                order = Order.objects.get(pk=order_id)
                from items.models import SellerProfile
                seller = SellerProfile.objects.get(pk=seller_id)
            except Exception:
                continue

            # Check if this shipment currently has a tracking number assigned locally
            seller_items = order.items.filter(seller=seller)
            has_local_tracking = seller_items.exclude(tracking_number__isnull=True).exclude(tracking_number='').exists()

            self.stdout.write(f"Checking Order {order.unique_order_id} - Seller {seller.shop_name} (has local tracking: {has_local_tracking})...")
            try:
                # Try query with seller suffix first
                sr_order_id_to_query = f"{order.unique_order_id}-S{seller.id}"
                res = requests.get(
                    "https://apiv2.shiprocket.in/v1/external/orders",
                    params={
                        "filter_by": "channel_order_id",
                        "filter": sr_order_id_to_query
                    },
                    headers=srv._headers(),
                    timeout=15
                )

                orders_list = []
                api_success = False

                if res.status_code == 200:
                    orders_list = res.json().get("data", [])
                    api_success = True
                
                # If not found, fallback to order.unique_order_id
                if res.status_code == 200 and not orders_list:
                    res_fallback = requests.get(
                        "https://apiv2.shiprocket.in/v1/external/orders",
                        params={
                            "filter_by": "channel_order_id",
                            "filter": order.unique_order_id
                        },
                        headers=srv._headers(),
                        timeout=15
                    )
                    if res_fallback.status_code == 200:
                        orders_list = res_fallback.json().get("data", [])
                        api_success = True
                    else:
                        api_success = False

                sr_order = None
                for o in orders_list:
                    if str(o.get("channel_order_id")) in [sr_order_id_to_query, order.unique_order_id]:
                        sr_order = o
                        break

                if not sr_order:
                    if not api_success:
                        self.stdout.write(self.style.WARNING(
                            f"  Failed to query Shiprocket API successfully (status: {res.status_code}). "
                            f"Skipping consistency verification for order {order.unique_order_id}."
                        ))
                        continue

                    if has_local_tracking:
                        self.stdout.write(self.style.WARNING(
                            f"  [Self-Healing] Mismatch detected: Local database has tracking number for "
                            f"{order.unique_order_id} (Seller: {seller.shop_name}), but the order does "
                            f"not exist on Shiprocket. Clearing invalid local tracking and pushing..."
                        ))
                        # Get tracking numbers of seller items before clearing them
                        local_tracking_numbers = list(seller_items.exclude(tracking_number__isnull=True).exclude(tracking_number='').values_list('tracking_number', flat=True))

                        # Clear invalid tracking fields on items of this seller
                        seller_items.update(
                            tracking_number=None,
                            courier_name=None,
                            shiprocket_order_id=None,
                            shipment_id=None,
                            shiprocket_status=None,
                            updated_at=timezone.now()
                        )
                        # Clear parent order tracking if it matches
                        if order.tracking_number in local_tracking_numbers:
                            order.tracking_number = None
                            order.courier_name = None
                            order.shiprocket_order_id = None
                            order.shipment_id = None
                            order.shiprocket_status = None
                            order.save(update_fields=['tracking_number', 'courier_name', 'shiprocket_order_id', 'shipment_id', 'shiprocket_status', 'updated_at'])
                            order.refresh_from_db()

                    self.stdout.write(f"  Shipment not found on Shiprocket system yet. Attempting to push to Shiprocket...")
                    from delivery.delivery_services import push_seller_items_to_shiprocket
                    success, err = push_seller_items_to_shiprocket(order, seller)
                    if success:
                        self.stdout.write(self.style.SUCCESS(f"  Successfully pushed seller {seller.shop_name} items to Shiprocket."))
                    else:
                        self.stdout.write(self.style.ERROR(f"  Failed to push seller {seller.shop_name} items: {err}"))
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
                recipient_list = []
                if seller.user.email:
                    recipient_list.append(seller.user.email.strip())

                admin_emails = list(User.objects.filter(is_superuser=True).exclude(email='').values_list('email', flat=True))
                if not admin_emails:
                    admin_emails = [getattr(settings, 'DEFAULT_FROM_EMAIL', 'admin@stallcart.in')]
                
                recipient_list = list(set(recipient_list + admin_emails))
                recipient_list = [email for email in recipient_list if email]

                if awb_code and str(awb_code).strip():
                    awb_code = str(awb_code).strip()
                    courier_name = str(courier_name or "Shiprocket").strip()
                    self.stdout.write(self.style.SUCCESS(f"  AWB detected: {awb_code} ({courier_name}). Updating database..."))

                    # Update order items of this seller if they don't match the Shiprocket AWB
                    items_to_update = order.items.filter(seller=seller).exclude(tracking_number=awb_code)
                    
                    if items_to_update.exists() or order.tracking_number != awb_code:
                        first_item = items_to_update.first()
                        old_item_status = first_item.status if first_item else (order.items.filter(seller=seller).first().status if order.items.filter(seller=seller).exists() else 'confirmed')
                        
                        sr_shipment_id = None
                        shipments = sr_order.get("shipments", [])
                        if shipments:
                            sr_shipment_id = shipments[0].get("id") or shipments[0].get("shipment_id")

                        if items_to_update.exists():
                            items_to_update.update(
                                tracking_number=awb_code,
                                courier_name=courier_name,
                                shiprocket_order_id=sr_order.get("order_id"),
                                shipment_id=sr_shipment_id,
                                status='processing',
                                updated_at=timezone.now()
                            )

                        # Update overall status
                        old_status = order.status
                        order.update_overall_status()

                        # Fallback update on parent Order if not set or mismatched (only if single seller)
                        seller_count = order.items.values_list('seller_id', flat=True).distinct().count()
                        if seller_count == 1 and order.tracking_number != awb_code:
                            order.tracking_number = awb_code
                            order.courier_name = courier_name
                            order.shiprocket_order_id = sr_order.get("order_id")
                            order.shipment_id = sr_shipment_id
                            order.save(update_fields=['tracking_number', 'courier_name', 'shiprocket_order_id', 'shipment_id', 'updated_at'])

                        # Log the status change
                        OrderStatusLog.objects.create(
                            order=order,
                            old_status=old_item_status,
                            new_status=order.status,
                            remarks=f"🔄 Synced tracking for {seller.shop_name} items from Shiprocket (AWB: {awb_code}, Courier: {courier_name})"
                        )

                        SystemActivityLog.log(
                            event_type='delivery_status',
                            description=f"Synced AWB '{awb_code}' ({courier_name}) from Shiprocket for Order {order.unique_order_id} (Seller: {seller.shop_name}).",
                            order=order,
                            metadata={'awb': awb_code, 'courier': courier_name, 'shiprocket_order_id': sr_order.get("order_id") if sr_order else None}
                        )

                        # Send AWB Assignment notification email
                        context = {
                            "order_id": f"{order.unique_order_id} (Seller: {seller.shop_name})",
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
                    self.stdout.write(f"  Shipment exists in Shiprocket but has no tracking AWB assigned yet.")

                    # Check if alert email has already been sent
                    alert_exists = OrderStatusLog.objects.filter(
                        order=order,
                        remarks__contains=f"Sent manual AWB update alert email for {seller.shop_name}"
                    ).exists()

                    if not alert_exists:
                        self.stdout.write(f"  Dispatching manual AWB update notification for {seller.shop_name}...")
                        pickup_loc = "Primary"
                        if hasattr(seller, 'shop_address') and seller.shop_address:
                            sa = seller.shop_address
                            pickup_loc = f"Seller_{seller.id} ({sa.shop_name} - {sa.city}, {sa.state})"

                        context = {
                            "order_id": f"{order.unique_order_id} (Seller: {seller.shop_name})",
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
                                remarks=f"⚠️ Sent manual AWB update alert email for {seller.shop_name}. Awaiting tracking details."
                            )
                            self.stdout.write("  Alert email dispatched and logged.")
                    else:
                        self.stdout.write(f"  Manual AWB update alert email already sent for {seller.shop_name}. Skipping.")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error checking AWB for order {order.unique_order_id}: {e}"))
                logger.error(f"AWB Sync error for order {order.unique_order_id}: {e}", exc_info=True)

        # ── PART 2: Sync Delivery Statuses ─────────────────────────────────────
        terminal_statuses = [
            'delivered', 'cancelled', 'returned', 'returned_to_source', 
            'courier_failed_pickup', 'seller_unresponsive', 'refund_initiated', 'refunded'
        ]
        
        active_tracked_items = OrderItem.objects.exclude(
            status__in=terminal_statuses
        ).filter(
            tracking_number__isnull=False
        ).exclude(tracking_number='')

        distinct_tracking_numbers = list(active_tracked_items.values_list('tracking_number', flat=True).distinct())

        self.stdout.write(f"\n[Part 2] Checking {len(distinct_tracking_numbers)} active tracking number(s) for status updates...")

        status_map = SHIPROCKET_STATUS_MAP

        affected_orders = {}

        for tracking_number in distinct_tracking_numbers:
            self.stdout.write(f"Querying status for AWB {tracking_number}...")
            try:
                tracking_data = srv.get_tracking(tracking_number)
                sr_status = tracking_data.get("current_status")

                if not sr_status:
                    self.stdout.write(f"  No tracking status returned from Shiprocket for AWB {tracking_number}.")
                    continue

                sr_status = sr_status.strip()
                new_local_status = status_map.get(sr_status.lower())
                self.stdout.write(f"  Shiprocket Status: '{sr_status}' -> Mapped Local Status: '{new_local_status}'")

                items_to_update = OrderItem.objects.filter(tracking_number=tracking_number)
                for item in items_to_update:
                    item_updated = False

                    if item.shiprocket_status != sr_status:
                        item.shiprocket_status = sr_status
                        item_updated = True
                        
                        # Also sync parent order's shiprocket_status
                        if item.order.shiprocket_status != sr_status:
                            item.order.shiprocket_status = sr_status
                            item.order.save(update_fields=['shiprocket_status', 'updated_at'])

                    if new_local_status and item.status != new_local_status:
                        old_item_status = item.status
                        item.status = new_local_status
                        if new_local_status == 'delivered':
                            item.delivered_at = timezone.now()
                        elif new_local_status == 'shipped' and not item.shipped_at:
                            item.shipped_at = timezone.now()
                        item_updated = True

                        if item.order_id not in affected_orders:
                            affected_orders[item.order_id] = (item.order, item.order.status)

                    if item_updated:
                        item.save()
                        self.stdout.write(self.style.SUCCESS(f"  Updated item {item.id} ({item.product.name}) status to {item.status}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error querying tracking status for AWB {tracking_number}: {e}"))
                logger.error(f"Status sync error for AWB {tracking_number}: {e}", exc_info=True)

        # Update overall status and log/notify for all affected orders
        for order_id, (order, old_order_status) in affected_orders.items():
            try:
                order.update_overall_status()
                # Reload status
                order.refresh_from_db()

                if order.status != old_order_status:
                    OrderStatusLog.objects.create(
                        order=order,
                        old_status=old_order_status,
                        new_status=order.status,
                        remarks=f"🔄 Automatically updated status via Shiprocket Sync of item shipments."
                    )

                    SystemActivityLog.log(
                        event_type='delivery_status',
                        description=f"Order status updated via Shiprocket Sync for Order {order.unique_order_id}: mapped to local '{order.status}'.",
                        order=order,
                        metadata={'mapped_status': order.status}
                    )

                    self.stdout.write(self.style.SUCCESS(f"  Successfully updated order status from '{old_order_status}' to '{order.status}'!"))

                    try:
                        notify_order_status_change(order, old_order_status, order.status)
                    except Exception as ex:
                        logger.error(f"Failed to trigger status change notification for order {order.unique_order_id}: {ex}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error updating overall status for order {order.unique_order_id}: {e}"))

    def run_email_retry(self):
        # ── PART 3: Email Sync & Retry ──────────────────────────────────────────
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("[Part 3] Starting Pending Email Dispatch & Retry Job...")
        self.stdout.write("=" * 60)
        
        from django.db.models import Q
        from common.notification_service import (
            send_order_placed_email_customer,
            send_order_placed_email_sellers,
            send_payment_email_customer,
            send_payment_email_sellers,
            send_refund_email_customer,
            send_refund_email_sellers,
            send_status_email_customer,
            send_status_email_sellers
        )
        
        # 1. Retry Placed/Confirmed Order Emails
        pending_placed_cust = Order.objects.filter(customer_placed_email_sent=False)
        self.stdout.write(f"Found {pending_placed_cust.count()} pending customer order confirmation email(s).")
        for order in pending_placed_cust:
            self.stdout.write(f"  Sending order placement email to customer for Order {order.unique_order_id}...")
            if send_order_placed_email_customer(order):
                order.customer_placed_email_sent = True
                order.save(update_fields=['customer_placed_email_sent'])
                self.stdout.write(self.style.SUCCESS(f"    Sent successfully."))
                
        pending_placed_seller = Order.objects.filter(seller_placed_email_sent=False)
        self.stdout.write(f"Found {pending_placed_seller.count()} pending seller order placement email(s).")
        for order in pending_placed_seller:
            self.stdout.write(f"  Sending order placement email to sellers for Order {order.unique_order_id}...")
            if send_order_placed_email_sellers(order):
                order.seller_placed_email_sent = True
                order.save(update_fields=['seller_placed_email_sent'])
                self.stdout.write(self.style.SUCCESS(f"    Sent successfully."))

        # 2. Retry Payment Emails
        pending_pay_cust = Order.objects.filter(payment_status='paid', customer_payment_email_sent=False)
        self.stdout.write(f"Found {pending_pay_cust.count()} pending customer payment confirmation email(s).")
        for order in pending_pay_cust:
            self.stdout.write(f"  Sending payment success email to customer for Order {order.unique_order_id}...")
            if send_payment_email_customer(order):
                order.customer_payment_email_sent = True
                order.save(update_fields=['customer_payment_email_sent'])
                self.stdout.write(self.style.SUCCESS(f"    Sent successfully."))
                
        pending_pay_seller = Order.objects.filter(payment_status='paid', seller_payment_email_sent=False)
        self.stdout.write(f"Found {pending_pay_seller.count()} pending seller payment confirmation email(s).")
        for order in pending_pay_seller:
            self.stdout.write(f"  Sending payment success email to sellers for Order {order.unique_order_id}...")
            if send_payment_email_sellers(order):
                order.seller_payment_email_sent = True
                order.save(update_fields=['seller_payment_email_sent'])
                self.stdout.write(self.style.SUCCESS(f"    Sent successfully."))

        # 3. Retry Refund Emails
        pending_ref_cust = Order.objects.filter(payment_status='refunded', customer_refund_email_sent=False)
        self.stdout.write(f"Found {pending_ref_cust.count()} pending customer refund confirmation email(s).")
        for order in pending_ref_cust:
            self.stdout.write(f"  Sending refund email to customer for Order {order.unique_order_id}...")
            if send_refund_email_customer(order):
                order.customer_refund_email_sent = True
                order.save(update_fields=['customer_refund_email_sent'])
                self.stdout.write(self.style.SUCCESS(f"    Sent successfully."))
                
        pending_ref_seller = Order.objects.filter(payment_status='refunded', seller_refund_email_sent=False)
        self.stdout.write(f"Found {pending_ref_seller.count()} pending seller refund confirmation email(s).")
        for order in pending_ref_seller:
            self.stdout.write(f"  Sending refund email to sellers for Order {order.unique_order_id}...")
            if send_refund_email_sellers(order):
                order.seller_refund_email_sent = True
                order.save(update_fields=['seller_refund_email_sent'])
                self.stdout.write(self.style.SUCCESS(f"    Sent successfully."))

        # 4. Retry Status Change Log Emails
        pending_logs = OrderStatusLog.objects.filter(
            Q(customer_email_sent=False) | Q(seller_email_sent=False)
        ).select_related('order', 'order__user').order_by('timestamp')
        
        self.stdout.write(f"Found {pending_logs.count()} status transition logs pending emails.")
        for log in pending_logs:
            # Skip logs where old_status == new_status (debug/alert logs)
            if log.old_status == log.new_status:
                continue
                
            self.stdout.write(f"  Processing log: Order {log.order.unique_order_id} ({log.old_status} -> {log.new_status})...")
            
            if not log.customer_email_sent:
                self.stdout.write(f"    Sending status update email to customer...")
                if send_status_email_customer(log):
                    log.customer_email_sent = True
                    log.save(update_fields=['customer_email_sent'])
                    self.stdout.write(self.style.SUCCESS(f"      Customer email sent successfully."))
                    
            if not log.seller_email_sent:
                self.stdout.write(f"    Sending status update email to sellers...")
                if send_status_email_sellers(log):
                    log.seller_email_sent = True
                    log.save(update_fields=['seller_email_sent'])
                    self.stdout.write(self.style.SUCCESS(f"      Seller email sent successfully."))

        self.stdout.write("\nShiprocket sync job complete.")
