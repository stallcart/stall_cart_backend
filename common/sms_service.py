import logging
import requests
from django.conf import settings

import socket

# Force requests/urllib3 to use IPv4 to prevent IPv6 whitelist mismatch with 2Factor API
try:
    import urllib3.util.connection as urllib3_connection
    urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

try:
    import requests.packages.urllib3.util.connection as urllib3_connection
    urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

logger = logging.getLogger(__name__)

def send_sms_via_2factor(recipient_phone: str, otp: str) -> bool:
    """
    Sends an OTP SMS using 2Factor.in manual OTP API.
    Auto-prefixes 10-digit Indian phone numbers with country code '91'.
    Uses custom template name from settings if configured.
    """
    try:
        api_key = getattr(settings, 'TWOFACTOR_API_KEY', None)
        if not api_key:
            logger.error("TWOFACTOR_API_KEY is not configured. SMS sending skipped.")
            return False
            
        # Clean phone number: remove spaces, dashes, +
        clean_phone = ''.join(c for c in recipient_phone if c.isdigit())
        
        # If it's a standard 10-digit Indian number, prefix it with country code '91'
        if len(clean_phone) == 10:
            clean_phone = "91" + clean_phone
            
        template_name = getattr(settings, 'TWOFACTOR_TEMPLATE_NAME', 'Account Verification OTP')
        
        import urllib.parse
        encoded_template = urllib.parse.quote(template_name)
        url = f"https://2factor.in/API/V1/{api_key}/SMS/{clean_phone}/{otp}/{encoded_template}"
        
        response = requests.get(url, timeout=10)
        data = response.json()
        if response.status_code == 200 and data.get('Status') == 'Success':
            logger.info(f"SMS OTP successfully sent to {clean_phone} via 2Factor. Session: {data.get('Details')}")
            return True
        else:
            logger.error(f"2Factor SMS API sending error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send SMS via 2Factor: {e}", exc_info=True)
        return False


def send_sms_via_brevo(recipient_phone: str, content: str) -> bool:
    """
    Wrapper for compatibility with legacy calls.
    Parses the 6-digit OTP from content and routes it to 2Factor.
    """
    import re
    match = re.search(r'\b\d{6}\b', content)
    otp = match.group(0) if match else ""
    if not otp:
        logger.warning(f"Could not extract OTP from content string: '{content}'. SMS skipped.")
        return False
    return send_sms_via_2factor(recipient_phone, otp)
