# orders/management/commands/process_refunds.py
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
import logging
from decimal import Decimal

from orders.models import Order, OrderStatusLog
from orders.views import get_razorpay_client

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Process automatic refunds for orders in 'refund_initiated' status"

    def handle(self, *args, **options):
        # Check SiteSettings global toggle
        from common.models import SiteSettings
        if not SiteSettings.get_singleton().enable_background_jobs:
            self.stdout.write(self.style.WARNING("Background jobs are globally disabled in Site Settings. Exiting..."))
            return

        self.stdout.write("=" * 60)
        self.stdout.write("Starting StallCart Background Refunds Processing...")
        self.stdout.write("=" * 60)

        # 1. Razorpay Refunds
        refund_orders = Order.objects.filter(
            status='refund_initiated',
            payment_status='paid',
            payment_method='razorpay'
        ).distinct()

        self.stdout.write(f"Found {refund_orders.count()} order(s) pending Razorpay refund...")

        client = get_razorpay_client()
        for order in refund_orders:
            remaining_to_refund = order.total_amount - (order.refund_amount or Decimal('0.00'))
            if remaining_to_refund <= 0:
                self.stdout.write(self.style.WARNING(f"  Order {order.unique_order_id} already fully refunded (Amount: {order.refund_amount}). Skipping refund API call."))
                order.payment_status = 'refunded'
                order.status = 'refunded'
                order.save(update_fields=['payment_status', 'status', 'updated_at'])
                continue

            self.stdout.write(f"Processing refund for Order {order.unique_order_id} (Remaining Amount: ₹{remaining_to_refund})...")
            try:
                if client and order.razorpay_payment_id:
                    # Trigger refund via Razorpay API
                    razorpay_refund = client.refund.create({
                        'payment_id': order.razorpay_payment_id,
                        'amount': int(remaining_to_refund * 100),
                        'notes': {
                            'order_id': order.unique_order_id,
                            'reason': 'Auto-refund initiated via background job'
                        }
                    })
                    
                    # Update order database fields
                    order.payment_status = 'refunded'
                    order.refund_amount = (order.refund_amount or Decimal('0.00')) + remaining_to_refund
                    order.refund_at = timezone.now()
                    order.razorpay_refund_id = razorpay_refund.get('id')
                    order.status = 'refunded'
                    order.save(update_fields=['payment_status', 'refund_amount', 'refund_at', 'razorpay_refund_id', 'status', 'updated_at'])

                    # Log the status change
                    OrderStatusLog.objects.create(
                        order=order,
                        old_status='refund_initiated',
                        new_status='refunded',
                        remarks=f"💰 Refund processed automatically to source account via background job. Amount: Rs. {remaining_to_refund}."
                    )
                    self.stdout.write(self.style.SUCCESS(f"  Successfully processed Razorpay refund for Order {order.unique_order_id}."))
                else:
                    self.stdout.write(self.style.ERROR(f"  Failed: Razorpay client not initialized or missing payment ID for Order {order.unique_order_id}."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Razorpay refund API call failed for Order {order.unique_order_id}: {e}"))
                logger.error(f"Razorpay refund error for Order {order.unique_order_id}: {e}", exc_info=True)

        # 2. Wallet Refunds
        wallet_orders = Order.objects.filter(
            status='refund_initiated',
            payment_status='paid',
            payment_method='wallet'
        ).distinct()

        self.stdout.write(f"Found {wallet_orders.count()} order(s) pending Wallet refund...")

        for order in wallet_orders:
            remaining_to_refund = order.total_amount - (order.refund_amount or Decimal('0.00'))
            if remaining_to_refund <= 0:
                self.stdout.write(self.style.WARNING(f"  Order {order.unique_order_id} already fully refunded (Amount: {order.refund_amount}). Skipping wallet refund."))
                order.payment_status = 'refunded'
                order.status = 'refunded'
                order.save(update_fields=['payment_status', 'status', 'updated_at'])
                continue

            self.stdout.write(f"Processing wallet refund for Order {order.unique_order_id} (Remaining Amount: ₹{remaining_to_refund})...")
            try:
                # StallCart Wallet refund
                from accounts.models import Wallet
                wallet, created = Wallet.objects.get_or_create(user=order.user)
                wallet.balance += remaining_to_refund
                wallet.save()

                order.payment_status = 'refunded'
                order.refund_amount = (order.refund_amount or Decimal('0.00')) + remaining_to_refund
                order.refund_at = timezone.now()
                order.status = 'refunded'
                order.save(update_fields=['payment_status', 'refund_amount', 'refund_at', 'status', 'updated_at'])

                # Log status change
                OrderStatusLog.objects.create(
                    order=order,
                    old_status='refund_initiated',
                    new_status='refunded',
                    remarks=f"💰 Refund processed automatically to StallCart Wallet via background job. Amount: Rs. {remaining_to_refund}."
                )
                self.stdout.write(self.style.SUCCESS(f"  Successfully processed wallet refund for Order {order.unique_order_id}."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Wallet refund failed for Order {order.unique_order_id}: {e}"))
                logger.error(f"Wallet refund error for Order {order.unique_order_id}: {e}", exc_info=True)

        self.stdout.write("Refund processing complete.")
