from django.core.mail.backends.base import BaseEmailBackend
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class BrevoAPIBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        """
        Sends one or more EmailMessage objects via Brevo API v3.
        Returns the number of successfully sent messages.
        """
        if not email_messages:
            return 0
            
        api_key = getattr(settings, 'BREVO_API_KEY', None)
        if not api_key:
            logger.error("BREVO_API_KEY settings is not configured. Brevo API email sending skipped.")
            return 0
            
        num_sent = 0
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        }
        
        for message in email_messages:
            try:
                # Extract sender name and email
                from_email = message.from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'StallCart <ad4b11001@smtp-brevo.com>')
                sender_name = "StallCart"
                sender_email = from_email
                if '<' in from_email and '>' in from_email:
                    parts = from_email.split('<')
                    sender_name = parts[0].strip()
                    sender_email = parts[1].replace('>', '').strip()
                
                payload = {
                    "sender": {"name": sender_name, "email": sender_email},
                    "to": [{"email": to_addr} for to_addr in message.to],
                    "subject": message.subject,
                }
                
                # Check for HTML alternatives or subtype
                html_content = None
                if getattr(message, 'alternatives', None):
                    for alt in message.alternatives:
                        if alt[1] == 'text/html':
                            html_content = alt[0]
                            break
                            
                if html_content:
                    payload["htmlContent"] = html_content
                    payload["textContent"] = message.body
                elif getattr(message, 'content_subtype', None) == 'html':
                    payload["htmlContent"] = message.body
                else:
                    payload["textContent"] = message.body
                
                response = requests.post(url, json=payload, headers=headers, timeout=10)
                if response.status_code in [200, 201]:
                    num_sent += 1
                else:
                    logger.error(f"Brevo API sending error: {response.status_code} - {response.text}")
                    if not self.fail_silently:
                        response.raise_for_status()
            except Exception as e:
                logger.error(f"Error sending message via Brevo API: {e}", exc_info=True)
                if not self.fail_silently:
                    raise
                    
        return num_sent
