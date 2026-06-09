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

        # 10 days safety window
        safety_date = timezone.now() - timedelta(days=10)

        # Find eligible order items
        eligible_items = OrderItem.objects.filter(
            order__status='delivered',
            order__delivered_at__lte=safety_date,
            is_returned=False
        ).exclude(
            settlements__isnull=False
        ).exclude(
            return_requests__status__in=['requested', 'approved', 'completed']
        ).select_related('seller', 'product')

        if not eligible_items.exists():
            self.stdout.write("No eligible order items found for auto-settlement.")
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

                # Now trigger the payout
                success, msg = initiate_payout(settlement)
                if success:
                    self.stdout.write(self.style.SUCCESS(f"  Successfully processed payout for {seller.shop_name}: {msg}"))
                else:
                    self.stdout.write(self.style.ERROR(f"  Failed to process payout for {seller.shop_name}: {msg}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error processing settlement for {seller.shop_name}: {e}"))
                logger.error(f"Auto-settlement error for seller {seller.id}: {e}", exc_info=True)

        self.stdout.write("Automatic seller settlements complete.")
