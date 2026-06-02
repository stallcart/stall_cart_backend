import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def send_sms_via_brevo(recipient_phone: str, content: str) -> bool:
    """
    Sends a transactional SMS using Brevo's Transactional SMS API.
    Auto-prefixes 10-digit Indian phone numbers with country code '91'.
    """
    try:
        api_key = getattr(settings, 'BREVO_API_KEY', None)
        if not api_key:
            logger.error("BREVO_API_KEY is not configured. SMS sending skipped.")
            return False
            
        # Clean phone number: remove spaces, dashes, +
        clean_phone = ''.join(c for c in recipient_phone if c.isdigit())
        
        # If it's a standard 10-digit Indian number, prefix it with country code '91'
        if len(clean_phone) == 10:
            clean_phone = "91" + clean_phone
            
        url = "https://api.brevo.com/v3/transactionalSMS/sms"
        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        }
        
        payload = {
            "content": content,
            "recipient": clean_phone,
            "sender": "StallCart",
            "type": "transactional"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            logger.info(f"SMS successfully sent to {clean_phone}")
            return True
        else:
            logger.error(f"Brevo SMS API sending error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send SMS via Brevo: {e}", exc_info=True)
        return False
