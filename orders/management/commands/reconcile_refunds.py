# orders/management/commands/reconcile_refunds.py
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import logging

from orders.models import Order, OrderItem, OrderStatusLog
from orders.views import get_razorpay_client

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Find and settle under-refunded prepaid orders where all items are cancelled or returned"

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("Starting StallCart Refund Reconciliation & Settlement...")
        self.stdout.write("=" * 60)

        # Fetch prepaid orders
        eligible_orders = Order.objects.filter(
            payment_status__in=['paid', 'refunded', 'failed']
        ).distinct()

        self.stdout.write(f"Scanning {eligible_orders.count()} order(s) for refund discrepancies...")

        razorpay_client = get_razorpay_client()
        reconciled_count = 0

        for order in eligible_orders:
            # Check if all items are cancelled or returned
            total_items = order.items.count()
            if total_items == 0:
                continue

            cancelled_or_refunded_items = order.items.filter(
                status__in=['cancelled', 'returned', 'returned_to_source', 'refund_initiated', 'refunded', 'courier_failed_pickup', 'seller_unresponsive']
            ).count()

            if total_items == cancelled_or_refunded_items:
                # Order is fully cancelled/returned. It must be fully refunded.
                remaining_to_refund = order.total_amount - (order.refund_amount or Decimal('0.00'))
                if remaining_to_refund > 0:
                    self.stdout.write(f"Order {order.unique_order_id}: Grand Total = ₹{order.total_amount}, Refunded = ₹{order.refund_amount or '0.00'}. Pending Refund = ₹{remaining_to_refund}.")
                    
                    payment_method = order.payment_method.lower()
                    if payment_method == 'razorpay':
                        if razorpay_client and order.razorpay_payment_id:
                            try:
                                razorpay_refund = razorpay_client.refund.create({
                                    'payment_id': order.razorpay_payment_id,
                                    'amount': int(remaining_to_refund * 100),
                                    'notes': {
                                        'order_id': order.unique_order_id,
                                        'reason': 'Refund reconciliation/settlement for remaining grand total'
                                    }
                                })
                                order.razorpay_refund_id = razorpay_refund.get('id')
                                order.refund_amount = (order.refund_amount or Decimal('0.00')) + remaining_to_refund
                                order.refund_at = timezone.now()
                                order.payment_status = 'refunded'
                                
                                # Update overall status if not already refund/cancelled terminal state
                                if order.status not in ['refunded', 'cancelled', 'seller_unresponsive', 'courier_failed_pickup']:
                                    order.status = 'refunded'
                                
                                order.save(update_fields=['payment_status', 'refund_amount', 'refund_at', 'razorpay_refund_id', 'status', 'updated_at'])
                                
                                OrderStatusLog.objects.create(
                                    order=order,
                                    old_status=order.status,
                                    new_status=order.status,
                                    remarks=f"💰 Settle Refund: Refunded remaining grand total of Rs. {remaining_to_refund} (Razorpay ID: {razorpay_refund.get('id')})."
                                )
                                self.stdout.write(self.style.SUCCESS(f"  Successfully processed Razorpay refund for Order {order.unique_order_id}."))
                                reconciled_count += 1
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f"  Failed to process Razorpay refund for Order {order.unique_order_id}: {e}"))
                                logger.error(f"Reconcile refund error for Order {order.unique_order_id}: {e}", exc_info=True)
                        else:
                            self.stdout.write(self.style.ERROR(f"  Razorpay client not configured or missing payment ID for Order {order.unique_order_id}."))
                    
                    elif payment_method == 'wallet':
                        try:
                            from accounts.models import Wallet
                            wallet, created = Wallet.objects.get_or_create(user=order.user)
                            wallet.balance += remaining_to_refund
                            wallet.save()

                            order.refund_amount = (order.refund_amount or Decimal('0.00')) + remaining_to_refund
                            order.refund_at = timezone.now()
                            order.payment_status = 'refunded'
                            
                            if order.status not in ['refunded', 'cancelled', 'seller_unresponsive', 'courier_failed_pickup']:
                                order.status = 'refunded'
                                
                            order.save(update_fields=['payment_status', 'refund_amount', 'refund_at', 'status', 'updated_at'])

                            OrderStatusLog.objects.create(
                                order=order,
                                old_status=order.status,
                                new_status=order.status,
                                remarks=f"💰 Settle Refund: Refunded remaining grand total of Rs. {remaining_to_refund} to StallCart Wallet."
                            )
                            self.stdout.write(self.style.SUCCESS(f"  Successfully processed Wallet refund for Order {order.unique_order_id}."))
                            reconciled_count += 1
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  Failed to process Wallet refund for Order {order.unique_order_id}: {e}"))
                            logger.error(f"Reconcile wallet refund error for Order {order.unique_order_id}: {e}", exc_info=True)

        self.stdout.write(f"Reconciliation complete. Settle down {reconciled_count} order(s).")
