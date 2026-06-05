# common/notification_service.py
import logging
from dataclasses import dataclass, field
from typing import Optional
from django.utils import timezone
from firebase_admin import messaging
from fcm_django.models import FCMDevice

logger = logging.getLogger(__name__)


@dataclass
class NotificationPayload:
    title: str
    body: str
    icon: str = '/static/images/logo-fallback.png'
    image: Optional[str] = None
    click_action: str = '/'
    tag: str = 'stallcart'
    data: dict = field(default_factory=dict)


def _build_message(token: str, payload: NotificationPayload) -> messaging.Message:
    """Build a FCM Message object for a web device."""
    extra_data = {
        'click_action': payload.click_action,
        'tag': payload.tag,
        **{k: str(v) for k, v in payload.data.items()},
    }
    return messaging.Message(
        token=token,
        notification=messaging.Notification(
            title=payload.title,
            body=payload.body,
            image=payload.image,
        ),
        webpush=messaging.WebpushConfig(
            notification=messaging.WebpushNotification(
                title=payload.title,
                body=payload.body,
                icon=payload.icon,
                image=payload.image,
                tag=payload.tag,
                require_interaction=False,
                actions=[
                    messaging.WebpushNotificationAction(action='open',  title='View'),
                    messaging.WebpushNotificationAction(action='close', title='Dismiss'),
                ],
            ),
            fcm_options=messaging.WebpushFCMOptions(link=payload.click_action),
        ),
        data=extra_data,
    )


def send_to_user(user, payload: NotificationPayload) -> dict:
    """
    Send a notification to every active web device of a user.
    Automatically deactivates stale tokens.
    Returns {'sent': int, 'failed': int, 'deactivated': int}
    """
    devices = FCMDevice.objects.filter(user=user, active=True, type='web')
    sent = failed = deactivated = 0

    for device in devices:
        try:
            msg = _build_message(device.registration_id, payload)
            messaging.send(msg)
            sent += 1
            logger.info(f"[FCM] Sent to user={user.id} device={device.id}")
        except messaging.UnregisteredError:
            device.active = False
            device.save(update_fields=['active'])
            deactivated += 1
            logger.warning(f"[FCM] Deactivated stale token device={device.id}")
        except Exception as e:
            failed += 1
            logger.error(f"[FCM] Failed device={device.id}: {e}")

    return {'sent': sent, 'failed': failed, 'deactivated': deactivated}


def send_to_token(token: str, payload: NotificationPayload) -> bool:
    """Send directly to a single raw token (used for test-on-login)."""
    try:
        msg = _build_message(token, payload)
        messaging.send(msg)
        return True
    except messaging.UnregisteredError:
        logger.warning(f"[FCM] Token unregistered: {token[:20]}...")
        return False
    except Exception as e:
        logger.error(f"[FCM] Direct send failed: {e}")
        return False


# ── Notification Templates ────────────────────────────────────────────────────

# common/notification_service.py
def notify_login_welcome(user, token: str):
    payload = NotificationPayload(
        title=f'Welcome back, {user.full_name or user.phone}! 👋',
        body='You\'re now signed in to StallCart. Tap to explore latest deals.',
        icon='/static/images/logo-fallback.png',
        click_action='/',  # Opens homepage
        tag='login-welcome',
        data={'event': 'login', 'user_id': user.id},
    )
    return send_to_token(token, payload)  # Sends to single token


def notify_order_placed(order):
    """
    Called when an order is placed (created/confirmed).
    Sends notifications to Customer, Sellers, and Admins.
    """
    from accounts.models import User
    from django.db.models import Q
    import logging
    logger = logging.getLogger(__name__)

    # 1. Customer notification
    if order.user:
        cust_payload = NotificationPayload(
            title='🛍️ Order Placed!',
            body=f'Your order #{order.unique_order_id} has been placed successfully. Thank you for shopping with StallCart!',
            click_action=f'/orders/order/{order.unique_order_id}/',
            tag=f'order-{order.id}',
            data={'order_id': str(order.id), 'event': 'order_placed'}
        )
        send_to_user(order.user, cust_payload)
    
    # 2. Seller notifications
    sellers = []
    try:
        seller_ids = list(order.items.values_list('seller', flat=True).distinct())
        sellers = list(User.objects.filter(role='seller', seller_profile__id__in=seller_ids))
        for seller in sellers:
            seller_payload = NotificationPayload(
                title='📦 New Order Received!',
                body=f'A new order #{order.unique_order_id} has been placed containing your products. Please process it.',
                click_action=f'/orders/seller/order/{order.unique_order_id}/',
                tag=f'order-{order.id}-seller',
                data={'order_id': str(order.id), 'event': 'order_placed'}
            )
            send_to_user(seller, seller_payload)
    except Exception as e:
        logger.error(f"[FCM] Failed to send order placed notification to sellers: {e}")
        
    # 3. Admin notifications
    try:
        admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True), is_active=True)
        for admin in admins:
            admin_payload = NotificationPayload(
                title='🔔 New Order Placed',
                body=f'Order #{order.unique_order_id} has been placed for ₹{order.total_amount}.',
                click_action=f'/orders/admin/order/{order.unique_order_id}/',
                tag=f'order-{order.id}-admin',
                data={'order_id': str(order.id), 'event': 'order_placed'}
            )
            send_to_user(admin, admin_payload)
    except Exception as e:
        logger.error(f"[FCM] Failed to send order placed notification to admins: {e}")

    # 4. Email notifications to Customer and Sellers
    try:
        from common.email_service import send_dynamic_email
        
        # Format shipping address nicely
        addr = order.shipping_address or {}
        addr_parts = [
            addr.get("name", ""),
            addr.get("address_line1", ""),
            addr.get("address_line2", ""),
            f"{addr.get('city', '')}, {addr.get('state', '')} - {addr.get('postal_code', '')}",
            f"Phone: {addr.get('phone', '')}"
        ]
        shipping_address_str = "\n".join([p.strip() for p in addr_parts if p.strip()])

        # Customer Email
        cust_email = order.user.email if (order.user and order.user.email) else order.guest_email
        if cust_email:
            # Build customer items list
            cust_items_str = ""
            for item in order.items.select_related('product', 'variant').all():
                variant_info = f" ({item.variant.size_value} / {item.variant.color})" if item.variant else ""
                cust_items_str += f"- {item.product.name}{variant_info} x {item.quantity} (₹{item.price:.2f} each)\n"
            
            send_dynamic_email(
                'customer_order_placed',
                [cust_email],
                {
                    'customer_name': (order.user.full_name or order.user.phone) if order.user else "Customer",
                    'order_id': order.unique_order_id,
                    'items_list': cust_items_str,
                    'shipping_address': shipping_address_str,
                    'payment_method': order.get_payment_method_display() if hasattr(order, 'get_payment_method_display') else order.payment_method.upper(),
                    'total_amount': str(order.total_amount),
                }
            )

        # Seller Emails
        for seller in sellers:
            if seller.email:
                # Build items list specifically for this seller
                seller_items = order.items.filter(seller=seller.seller_profile).select_related('product', 'variant')
                seller_items_str = ""
                for item in seller_items:
                    variant_info = f" ({item.variant.size_value} / {item.variant.color})" if item.variant else ""
                    seller_items_str += f"- {item.product.name}{variant_info} x {item.quantity}\n"
                
                send_dynamic_email(
                    'seller_new_order',
                    [seller.email],
                    {
                        'seller_name': seller.full_name or seller.seller_profile.shop_name or "Seller",
                        'order_id': order.unique_order_id,
                        'items_list': seller_items_str,
                        'shipping_address': shipping_address_str,
                    }
                )
    except Exception as e:
        logger.error(f"Failed to send order placed emails: {e}", exc_info=True)


def notify_order_status_change(order, old_status, new_status):
    """
    Called when an order status changes (after creation).
    Sends notifications to Customer, Sellers, and Admins.
    """
    from accounts.models import User
    from django.db.models import Q
    import logging
    logger = logging.getLogger(__name__)

    if not order or not new_status or old_status == new_status:
        return

    # Don't trigger if old_status is empty/None or transitions pending -> confirmed on creation
    # because notify_order_placed handles it.
    if not old_status or (old_status == 'pending' and new_status == 'confirmed' and (timezone.now() - order.created_at).total_seconds() < 5):
        return

    cust_title = cust_body = None
    seller_title = seller_body = None
    admin_title = admin_body = None

    if new_status == 'confirmed':
        cust_title = '✅ Order Confirmed'
        cust_body = f'Your order #{order.unique_order_id} has been confirmed.'
        
        seller_title = '🔵 Order Confirmed'
        seller_body = f'Order #{order.unique_order_id} is confirmed. Please prepare items for shipping.'
        
        admin_title = '🔵 Order Confirmed'
        admin_body = f'Order #{order.unique_order_id} has been confirmed.'
        
    elif new_status == 'processing':
        cust_title = '🟠 Order Processing'
        cust_body = f'Your order #{order.unique_order_id} is being processed and prepared for shipping.'
        
        seller_title = '🟠 Order Processing'
        seller_body = f'Order #{order.unique_order_id} status is updated to Processing. Prepare for pickup.'
        
        admin_title = '🟠 Order Processing'
        admin_body = f'Order #{order.unique_order_id} is now processing.'
        
    elif new_status == 'shipped':
        courier_info = f" via {order.courier_name}" if order.courier_name else ""
        tracking_info = f" (AWB: {order.tracking_number})" if order.tracking_number else ""
        
        cust_title = '🚚 Order Shipped!'
        cust_body = f'Your order #{order.unique_order_id} has been picked up by our delivery partner and shipped{courier_info}{tracking_info}.'
        
        seller_title = '🚚 Order Dispatched'
        seller_body = f'Order #{order.unique_order_id} has been picked up by the delivery partner.'
        
        admin_title = '🚚 Order Shipped'
        admin_body = f'Order #{order.unique_order_id} has been shipped{courier_info}{tracking_info}.'
        
    elif new_status == 'out_for_delivery':
        cust_title = '🛵 Out for Delivery'
        cust_body = f'Your order #{order.unique_order_id} is out for delivery. Keep your phone handy!'
        
        seller_title = '🛵 Out for Delivery'
        seller_body = f'Order #{order.unique_order_id} is out for delivery.'
        
        admin_title = '🛵 Out for Delivery'
        admin_body = f'Order #{order.unique_order_id} is out for delivery.'
        
    elif new_status == 'delivered':
        cust_title = '🎉 Order Delivered!'
        cust_body = f'Your order #{order.unique_order_id} has been delivered successfully. Thank you!'
        
        seller_title = '🟢 Order Delivered'
        seller_body = f'Order #{order.unique_order_id} has been delivered. Net earnings have been credited.'
        
        admin_title = '🟢 Order Delivered'
        admin_body = f'Order #{order.unique_order_id} has been delivered.'
        
    elif new_status == 'cancelled':
        cust_title = '🔴 Order Cancelled'
        cust_body = f'Your order #{order.unique_order_id} has been cancelled.'
        
        seller_title = '🔴 Order Cancelled'
        seller_body = f'Order #{order.unique_order_id} has been cancelled.'
        
        admin_title = '🔴 Order Cancelled'
        admin_body = f'Order #{order.unique_order_id} has been cancelled.'
        
    elif new_status in ('returned', 'returned_to_source'):
        label = 'Returned' if new_status == 'returned' else 'Returned to Source (RTO)'
        cust_title = f'🔄 Order {label}'
        cust_body = f'Your order #{order.unique_order_id} status has been updated to {label}.'
        
        seller_title = f'🔄 Order {label}'
        seller_body = f'Order #{order.unique_order_id} is marked as {label}.'
        
        admin_title = f'🔄 Order {label}'
        admin_body = f'Order #{order.unique_order_id} status updated to {label}.'
        
    elif new_status in ('refund_initiated', 'refunded'):
        label = 'Refund Initiated' if new_status == 'refund_initiated' else 'Refunded'
        cust_title = f'💰 Order {label}'
        cust_body = f'Refund of ₹{order.total_amount} for order #{order.unique_order_id} has been {label.lower()}.'
        
        seller_title = f'💰 Order {label}'
        seller_body = f'Order #{order.unique_order_id} refund: {label}.'
        
        admin_title = f'💰 Order {label}'
        admin_body = f'Order #{order.unique_order_id} refund: {label}.'

    # Get distinct sellers
    try:
        seller_ids = order.items.values_list('seller', flat=True).distinct()
        sellers = User.objects.filter(role='seller', seller_profile__id__in=seller_ids)
    except Exception as e:
        logger.error(f"[FCM] Failed to query sellers for status change: {e}")
        sellers = []

    # Get admins
    try:
        admins = User.objects.filter(Q(role='admin') | Q(is_superuser=True), is_active=True)
    except Exception as e:
        logger.error(f"[FCM] Failed to query admins for status change: {e}")
        admins = []

    # Send notifications
    if cust_title and cust_body and order.user:
        try:
            send_to_user(order.user, NotificationPayload(
                title=cust_title,
                body=cust_body,
                click_action=f'/orders/order/{order.unique_order_id}/',
                tag=f'order-{order.id}',
                data={'order_id': str(order.id), 'status': new_status}
            ))
        except Exception as e:
            logger.error(f"[FCM] Failed to notify customer on status change: {e}")
        
        # Send dynamic email notification to the customer
        try:
            from common.email_service import send_dynamic_email
            if order.user.email:
                send_dynamic_email('order_status_update', [order.user.email], {
                    'customer_name': order.user.full_name or order.user.phone,
                    'order_id': order.unique_order_id,
                    'status': new_status.replace('_', ' ').title(),
                    'courier_name': order.courier_name,
                    'tracking_number': order.tracking_number,
                })
        except Exception as e:
            logger.error(f"Failed to send order status update email: {e}")
        
    if seller_title and seller_body:
        for seller in sellers:
            try:
                send_to_user(seller, NotificationPayload(
                    title=seller_title,
                    body=seller_body,
                    click_action=f'/orders/seller/order/{order.unique_order_id}/',
                    tag=f'order-{order.id}-seller',
                    data={'order_id': str(order.id), 'status': new_status}
                ))
            except Exception as e:
                logger.error(f"[FCM] Failed to notify seller {seller.id} on status change: {e}")
            
    if admin_title and admin_body:
        for admin in admins:
            try:
                send_to_user(admin, NotificationPayload(
                    title=admin_title,
                    body=admin_body,
                    click_action=f'/orders/admin/order/{order.unique_order_id}/',
                    tag=f'order-{order.id}-admin',
                    data={'order_id': str(order.id), 'status': new_status}
                ))
            except Exception as e:
                logger.error(f"[FCM] Failed to notify admin {admin.id} on status change: {e}")


def notify_order_shipped(order, tracking_id=None):
    if tracking_id:
        order.tracking_number = tracking_id
    return notify_order_status_change(order, order.status, 'shipped')


def notify_order_out_for_delivery(order):
    return notify_order_status_change(order, order.status, 'out_for_delivery')


def notify_order_delivered(order):
    return notify_order_status_change(order, order.status, 'delivered')