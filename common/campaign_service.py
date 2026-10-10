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


def execute_campaign_lucky_draw(campaign, executed_by=None):
    """
    Executes the Lucky Draw for a Campaign with strict mathematical guarantees:
    1. The number of winners is EXACTLY equal to the number of configured prizes (neither more nor less).
    2. Every selected winner is a distinct unique active user (no user wins twice in the same campaign).
    3. Uses cryptographically secure random selection (secrets.SystemRandom).
    4. Wrapped in an atomic transaction to prevent partial/conflicted states.
    5. Dispatches notifications to all winners.
    
    Returns:
        (success: bool, winners: list, error_message: str or None)
    """
    import secrets
    from django.db import transaction
    from common.models import CampaignWinner

    prizes = list(campaign.prizes.filter(is_deleted=False).order_by('rank', 'display_order'))
    if not prizes:
        return False, [], "No prizes configured for this campaign. Please add prizes in Django Admin first."

    # Check if all prizes already have winners
    existing_winner_prize_ids = set(campaign.winners.filter(is_deleted=False).values_list('prize_id', flat=True))
    unassigned_prizes = [p for p in prizes if p.id not in existing_winner_prize_ids]
    
    if not unassigned_prizes:
        return False, [], "All configured prizes for this campaign have already been awarded."

    # Existing winners user IDs to exclude from future wins in this campaign
    existing_winner_user_ids = set(campaign.winners.filter(is_deleted=False).values_list('user_id', flat=True))

    # Eligible candidate pool (distinct users who are active and not deleted)
    eligible_participants = list(
        campaign.participants.filter(
            is_eligible=True,
            is_deleted=False,
            user__is_active=True
        ).exclude(
            user_id__in=existing_winner_user_ids
        ).select_related('user')
    )

    # Deduplicate participants by user_id to ensure strict 1-ticket-per-user fairness
    unique_candidates = []
    seen_users = set()
    for p in eligible_participants:
        if p.user_id not in seen_users:
            seen_users.add(p.user_id)
            unique_candidates.append(p)

    target_winner_count = len(unassigned_prizes)
    if len(unique_candidates) < target_winner_count:
        return False, [], f"Insufficient eligible participants ({len(unique_candidates)}) for {target_winner_count} unassigned prize(s). Need at least {target_winner_count} eligible participants."

    # Cryptographically secure random shuffle
    rng = secrets.SystemRandom()
    rng.shuffle(unique_candidates)

    created_winners = []
    with transaction.atomic():
        for idx, prize in enumerate(unassigned_prizes):
            participant = unique_candidates[idx]
            winner = CampaignWinner.objects.create(
                campaign=campaign,
                prize=prize,
                participant=participant,
                user=participant.user,
                ticket_number=participant.ticket_number or f"{campaign.slug.upper()}-{participant.id}",
                is_published=True,
                created_by=executed_by or participant.user
            )
            participant.is_winner = True
            participant.save()
            created_winners.append(winner)

        # STRICT INTEGRITY CHECK: Exact winner count check
        if len(created_winners) != target_winner_count:
            raise ValueError(f"Winner count mismatch: expected {target_winner_count}, but created {len(created_winners)}")

        campaign.status = 'winners_declared'
        campaign.save()

    # Dispatch notifications after transaction commits
    for winner in created_winners:
        try:
            notify_campaign_winner(winner)
        except Exception as e:
            logger.error(f"Failed to notify winner {winner.user.phone}: {e}")

    return True, created_winners, None
