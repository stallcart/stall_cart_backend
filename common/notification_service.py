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
    payload = NotificationPayload(
        title='🛍️ Order Confirmed!',
        body=f'Order #{order.id} is confirmed. We\'ll notify you when it ships.',
        click_action=f'/orders/{order.id}/',
        tag=f'order-{order.id}',
        data={'order_id': order.id},
    )
    return send_to_user(order.user, payload)


def notify_order_shipped(order, tracking_id=None):
    body = f'Order #{order.id} is on its way!'
    if tracking_id:
        body += f' Track: {tracking_id}'
    payload = NotificationPayload(
        title='🚚 Order Shipped',
        body=body,
        click_action=f'/orders/{order.id}/',
        tag=f'order-{order.id}',
        data={'order_id': order.id},
    )
    return send_to_user(order.user, payload)


def notify_order_out_for_delivery(order):
    payload = NotificationPayload(
        title='🛵 Out for Delivery!',
        body=f'Your order #{order.id} is out for delivery. Keep your phone handy!',
        click_action=f'/orders/{order.id}/',
        tag=f'order-{order.id}',
        data={'order_id': order.id},
    )
    return send_to_user(order.user, payload)


def notify_order_delivered(order):
    payload = NotificationPayload(
        title='✅ Delivered!',
        body=f'Order #{order.id} delivered. Enjoy your purchase!',
        click_action=f'/orders/{order.id}/',
        tag=f'order-{order.id}',
    )
    return send_to_user(order.user, payload)