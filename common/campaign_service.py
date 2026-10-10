import logging
from common.email_service import send_dynamic_email
from common.notification_service import send_to_user, NotificationPayload

logger = logging.getLogger(__name__)

def notify_campaign_winner(winner) -> dict:
    """
    Sends multi-channel notifications (Email, Web Push / FCM) to a lucky draw winner.
    """
    results = {
        'email_sent': False,
        'push_sent': False,
    }
    user = winner.user
    campaign = winner.campaign
    prize = winner.prize

    # 1. Send Dynamic Email Notification (if user has email)
    if user.email:
        try:
            rank_map = {1: '1st Prize', 2: '2nd Prize', 3: '3rd Prize'}
            rank_display = rank_map.get(prize.rank, f'Rank #{prize.rank}')
            
            context = {
                'customer_name': user.full_name or 'Valued Customer',
                'campaign_title': campaign.title,
                'prize_title': prize.title,
                'prize_subtitle': prize.subtitle,
                'prize_rank_display': rank_display,
                'approx_value': prize.approx_value,
                'phone': user.phone,
            }
            results['email_sent'] = send_dynamic_email('campaign_winner_notification', [user.email], context)
            if results['email_sent']:
                logger.info(f"Winner notification email sent to {user.email} for '{campaign.title}'.")
        except Exception as e:
            logger.error(f"Failed to send winner notification email to {user.email}: {e}")

    # 2. Send Push Notification (FCM)
    try:
        payload = NotificationPayload(
            title="🎉 You Won A Lucky Draw Prize!",
            body=f"Congratulations! You won '{prize.title}' in the {campaign.title} Lucky Draw!",
            click_action=f"/campaign/{campaign.slug}/",
            tag=f"campaign-winner-{campaign.id}"
        )
        send_to_user(user, payload)
        results['push_sent'] = True
        logger.info(f"Winner push notification sent to user {user.phone} for '{campaign.title}'.")
    except Exception as e:
        logger.warning(f"FCM push notification failed for winner {user.phone}: {e}")

    return results
