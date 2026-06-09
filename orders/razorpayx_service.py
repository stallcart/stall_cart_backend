import requests
import logging
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)

def get_razorpayx_credentials():
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', None)
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
    account_number = getattr(settings, 'RAZORPAYX_ACCOUNT_NUMBER', None)
    return key_id, key_secret, account_number

def create_razorpay_contact(seller_profile):
    """Create a contact for the seller in RazorpayX."""
    key_id, key_secret, _ = get_razorpayx_credentials()
    if not key_id or not key_secret:
        logger.error("Razorpay credentials not configured.")
        return None

    url = "https://api.razorpay.com/v1/contacts"
    payload = {
        "name": seller_profile.account_holder_name or seller_profile.shop_name,
        "email": seller_profile.user.email or "",
        "contact": seller_profile.phone or "",
        "type": "vendor",
        "reference_id": str(seller_profile.id)
    }

    try:
        response = requests.post(url, json=payload, auth=(key_id, key_secret), timeout=10)
        if response.status_code in (200, 201):
            data = response.json()
            contact_id = data.get("id")
            seller_profile.razorpay_contact_id = contact_id
            seller_profile.save(update_fields=["razorpay_contact_id"])
            return contact_id
        else:
            logger.error(f"Failed to create RazorpayX contact: {response.status_code} - {response.text}")
    except Exception as e:
        logger.exception(f"Error creating RazorpayX contact: {e}")
    return None

def create_razorpay_fund_account(seller_profile):
    """Create a bank fund account for the seller contact in RazorpayX."""
    key_id, key_secret, _ = get_razorpayx_credentials()
    if not key_id or not key_secret:
        return None

    contact_id = seller_profile.razorpay_contact_id
    if not contact_id:
        contact_id = create_razorpay_contact(seller_profile)
        if not contact_id:
            return None

    if not seller_profile.account_number or not seller_profile.ifsc_code:
        logger.error("Seller bank details are missing.")
        return None

    url = "https://api.razorpay.com/v1/fund_accounts"
    payload = {
        "contact_id": contact_id,
        "account_type": "bank_account",
        "bank_account": {
            "name": seller_profile.account_holder_name or seller_profile.shop_name,
            "ifsc": seller_profile.ifsc_code,
            "account_number": seller_profile.account_number
        }
    }

    try:
        response = requests.post(url, json=payload, auth=(key_id, key_secret), timeout=10)
        if response.status_code in (200, 201):
            data = response.json()
            fund_account_id = data.get("id")
            seller_profile.razorpay_fund_account_id = fund_account_id
            seller_profile.save(update_fields=["razorpay_fund_account_id"])
            return fund_account_id
        else:
            logger.error(f"Failed to create RazorpayX fund account: {response.status_code} - {response.text}")
    except Exception as e:
        logger.exception(f"Error creating RazorpayX fund account: {e}")
    return None

def initiate_payout(settlement):
    """Initiate payout via RazorpayX."""
    key_id, key_secret, account_number = get_razorpayx_credentials()
    if not key_id or not key_secret or not account_number:
        logger.error("RazorpayX credentials or Account Number not configured.")
        return False, "RazorpayX not fully configured in settings."

    if settlement.razorpay_payout_id:
        return False, "Payout has already been initiated for this settlement."

    seller = settlement.seller
    fund_account_id = seller.razorpay_fund_account_id
    if not fund_account_id:
        fund_account_id = create_razorpay_fund_account(seller)
        if not fund_account_id:
            return False, "Could not setup Fund Account for the seller. Make sure bank details are valid."

    amount_in_paise = int(settlement.amount * Decimal('100'))
    if amount_in_paise <= 0:
        return False, "Settlement amount must be greater than 0."

    url = "https://api.razorpay.com/v1/payouts"
    payload = {
        "account_number": account_number,
        "fund_account_id": fund_account_id,
        "amount": amount_in_paise,
        "currency": "INR",
        "mode": "IMPS",
        "purpose": "payout",
        "queue_if_low_balance": True,
        "reference_id": settlement.settlement_id,
        "narration": f"Settlement {settlement.settlement_id[:15]}"
    }

    try:
        response = requests.post(url, json=payload, auth=(key_id, key_secret), timeout=10)
        data = response.json()
        if response.status_code in (200, 201):
            payout_id = data.get("id")
            settlement.razorpay_payout_id = payout_id
            
            payout_status = data.get("status")
            if payout_status == "failed":
                settlement.status = "failed"
            else:
                # Keep status as processed if it went through or queued
                settlement.status = "processed"
            
            settlement.payment_reference = payout_id
            settlement.save()
            if settlement.status == 'processed':
                settlement.send_notification_email()
            return True, f"Payout initiated successfully. Payout ID: {payout_id}"
        else:
            error_msg = data.get("error", {}).get("description", response.text)
            logger.error(f"RazorpayX payout request failed: {response.status_code} - {response.text}")
            return False, f"Razorpay API Error: {error_msg}"
    except Exception as e:
        logger.exception("Error initiating RazorpayX payout")
        return False, f"Exception during payout request: {str(e)}"
