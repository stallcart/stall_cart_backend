# orders/management/commands/auto_settle_sellers.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from orders.models import OrderItem, SellerSettlement
from orders.razorpayx_service import initiate_payout
from common.models import SiteSettings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Automatically settle and pay out sellers for delivered orders after 10 days"

    def handle(self, *args, **options):
        # Check SiteSettings global toggle
        settings_obj = SiteSettings.get_singleton()
        if not settings_obj.enable_background_jobs:
            self.stdout.write(self.style.WARNING("Background jobs are globally disabled in Site Settings. Exiting..."))
            return

        self.stdout.write("=" * 60)
        self.stdout.write("Starting StallCart Automatic Seller Settlements & Payouts...")
        self.stdout.write("=" * 60)

        # 10 days safety window (after delivery)
        safety_date = timezone.now() - timedelta(days=10)

        # Find eligible order items:
        # - Delivered at least 10 days ago (past the 7-day return window)
        # - Not returned and no active return request
        # - Not already in any settlement
        from django.db.models import Q
        eligible_items = OrderItem.objects.filter(
            Q(status='delivered') | Q(order__status='delivered'),
            is_returned=False
        ).filter(
            Q(delivered_at__lte=safety_date) | Q(order__delivered_at__lte=safety_date)
        ).exclude(
            settlements__isnull=False
        ).exclude(
            status__in=['cancelled', 'rto', 'rto_in_transit', 'rto_delivered', 'returned', 'failed']
        ).exclude(
            order__status__in=['cancelled', 'failed']
        ).exclude(
            return_requests__status__in=[
                'requested', 'approved', 'pickup_scheduled', 'picked_up', 
                'received', 'refund_initiated', 'completed'
            ]
        ).select_related('seller', 'product', 'order')

        if not eligible_items.exists():
            self.stdout.write("No eligible order items found for auto-settlement (10 days past delivery with no returns).")
            return

        self.stdout.write(f"Found {eligible_items.count()} order item(s) eligible for settlement.")

        # Group items by seller
        seller_to_items = {}
        for item in eligible_items:
            seller = item.seller
            if seller not in seller_to_items:
                seller_to_items[seller] = []
            seller_to_items[seller].append(item)

        for seller, items in seller_to_items.items():
            self.stdout.write(f"Creating settlement for seller: {seller.shop_name} ({len(items)} items)...")
            try:
                with transaction.atomic():
                    # Acquire select_for_update lock on items to prevent race conditions with admin actions
                    item_ids = [item.id for item in items]
                    locked_items = list(OrderItem.objects.select_for_update().filter(
                        id__in=item_ids
                    ).exclude(
                        settlements__isnull=False
                    ).exclude(
                        status__in=['cancelled', 'rto', 'rto_in_transit', 'rto_delivered', 'returned', 'failed']
                    ).exclude(
                        order__status__in=['cancelled', 'failed']
                    ))
                    
                    if not locked_items:
                        self.stdout.write(self.style.WARNING(f"  Skipping {seller.shop_name}: items already settled in another transaction."))
                        continue
                    
                    # Create the settlement record
                    settlement = SellerSettlement.objects.create(
                        seller=seller,
                        status='pending'
                    )
                    # Add items to the settlement
                    settlement.order_items.add(*locked_items)

                # Ensure fresh instance from DB with updated amounts from m2m_changed
                settlement.refresh_from_db()

                # Guard: Ensure settlement has not been processed or settled concurrently
                if settlement.status == 'processed' or settlement.settled_at or settlement.razorpay_payout_id:
                    self.stdout.write(self.style.WARNING(f"  Settlement {settlement.settlement_id} is already processed/settled. Skipping payout."))
                    continue

                # Now trigger the payout
                success, msg = initiate_payout(settlement)
                if success:
                    self.stdout.write(self.style.SUCCESS(f"  Successfully processed payout for {seller.shop_name}: {msg}"))
                else:
                    self.stdout.write(self.style.WARNING(f"  Created pending settlement {settlement.settlement_id} for {seller.shop_name}. Payout pending: {msg}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error processing settlement for {seller.shop_name}: {e}"))
                logger.error(f"Auto-settlement error for seller {seller.id}: {e}", exc_info=True)

        self.stdout.write("Automatic seller settlements complete.")
