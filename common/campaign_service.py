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
            from common.models import EmailTemplate
            rank_map = {1: '1st Prize', 2: '2nd Prize', 3: '3rd Prize'}
            rank_display = rank_map.get(prize.rank, f'Rank #{prize.rank}')
            
            context = {
                'customer_name': user.full_name or 'Valued Customer',
                'campaign_title': campaign.title,
                'prize_title': prize.title,
                'prize_subtitle': prize.subtitle or '',
                'prize_rank_display': rank_display,
                'approx_value': prize.approx_value or '',
                'phone': user.phone or '',
                'ticket_number': winner.ticket_number or (getattr(winner.participant, 'ticket_number', '') if getattr(winner, 'participant', None) else ''),
                'event_date': '17 October 2026',
                'profile_url': 'https://stallcart.in/accounts/profile/',
                'campaign_url': f"https://stallcart.in/campaign/{campaign.slug}/",
            }

            # Check if event-specific template exists (e.g. campaign_winner_dandiya_nights_2026)
            event_template_name = f"campaign_winner_{campaign.slug.replace('-', '_')}"
            if EmailTemplate.objects.filter(name=event_template_name, is_active=True, is_deleted=False).exists():
                chosen_template = event_template_name
            else:
                chosen_template = 'campaign_winner_notification'

            results['email_sent'] = send_dynamic_email(chosen_template, [user.email], context)
            if results['email_sent']:
                logger.info(f"Winner notification email sent to {user.email} using template '{chosen_template}' for '{campaign.title}'.")
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

    # Eligible candidate pool: strictly active CUSTOMER accounts registered newly during the campaign (exclude sellers, staff, superusers)
    filter_kwargs = {
        'is_eligible': True,
        'is_deleted': False,
        'user__is_active': True,
        'user__role': 'customer',
        'user__is_staff': False,
        'user__is_superuser': False,
    }
    if campaign.start_datetime:
        filter_kwargs['user__created_at__gte'] = campaign.start_datetime

    eligible_participants = list(
        campaign.participants.filter(
            **filter_kwargs
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


def declare_fixed_campaign_winners(campaign, prize_winner_map: dict, executed_by=None):
    """
    Directly assigns designated fixed winners to configured campaign prizes,
    updates participant tickets, marks results as published, sets campaign to 'winners_declared',
    and immediately sends email + push notifications to each selected winner.
    
    Args:
        campaign: Campaign instance
        prize_winner_map: dict mapping prize_id (int or str) -> User instance or user_id
        executed_by: staff user who triggered the action
        
    Returns:
        (success: bool, created_winners: list, error_message: str or None, notification_summary: dict)
    """
    from django.db import transaction
    from django.contrib.auth import get_user_model
    from common.models import CampaignWinner, CampaignParticipant, CampaignPrize
    
    User = get_user_model()
    prizes = list(campaign.prizes.filter(is_deleted=False).order_by('rank', 'display_order'))
    if not prizes:
        return False, [], "No prizes found for this campaign. Please add prizes in Admin first.", {}

    resolved_assignments = []
    seen_users = set()

    for prize in prizes:
        winner_val = prize_winner_map.get(prize.id) or prize_winner_map.get(str(prize.id))
        if not winner_val and prize.fixed_winner:
            winner_val = prize.fixed_winner

        if not winner_val:
            return False, [], f"Winner missing for {prize.ordinal_rank} ({prize.title}). Please select a customer for every configured prize.", {}

        # Resolve user
        if isinstance(winner_val, User):
            user = winner_val
        else:
            try:
                user = User.objects.get(pk=int(winner_val))
            except (User.DoesNotExist, ValueError):
                return False, [], f"Invalid user selected for prize {prize.title}.", {}

        if user.id in seen_users:
            return False, [], f"User {user.full_name or user.phone} cannot win multiple prizes in the same campaign ({prize.title}). Please select distinct winners for each prize.", {}

        seen_users.add(user.id)
        resolved_assignments.append((prize, user))

    created_winners = []
    with transaction.atomic():
        # Clear any prior winners for these prizes in this campaign
        campaign.winners.all().delete()
        campaign.participants.update(is_winner=False)

        for prize, user in resolved_assignments:
            # Ensure participant record exists
            participant = CampaignParticipant.objects.filter(campaign=campaign, user=user).first()
            if not participant:
                ticket = f"{campaign.slug.upper()[:12]}-{user.id:04d}"
                participant = CampaignParticipant.objects.create(
                    campaign=campaign,
                    user=user,
                    ticket_number=ticket,
                    is_eligible=True,
                    created_by=executed_by or user
                )

            participant.is_winner = True
            participant.save(update_fields=['is_winner'])

            winner = CampaignWinner.objects.create(
                campaign=campaign,
                prize=prize,
                participant=participant,
                user=user,
                ticket_number=participant.ticket_number or f"{campaign.slug.upper()}-{participant.id}",
                is_published=True,
                created_by=executed_by or user
            )

            # Persist fixed_winner on prize record as well
            if prize.fixed_winner_id != user.id:
                prize.fixed_winner = user
                prize.save(update_fields=['fixed_winner'])

            created_winners.append(winner)

        campaign.status = 'winners_declared'
        campaign.save(update_fields=['status'])

    # Send notifications (emails and push) to each winner immediately
    notif_summary = {'emails_sent': 0, 'emails_failed': 0, 'push_sent': 0}
    for winner in created_winners:
        try:
            res = notify_campaign_winner(winner)
            if res.get('email_sent'):
                notif_summary['emails_sent'] += 1
            else:
                notif_summary['emails_failed'] += 1
            if res.get('push_sent'):
                notif_summary['push_sent'] += 1
        except Exception as e:
            logger.error(f"Error notifying fixed winner {winner.user.phone}: {e}")
            notif_summary['emails_failed'] += 1

    return True, created_winners, None, notif_summary
