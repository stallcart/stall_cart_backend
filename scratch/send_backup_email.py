import os
import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.text import MIMEText

# Initialize Django to access SiteSettings model
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stall_cart.settings")
sys.path.append("/var/www/stall_cart_project")
django.setup()

from common.models import SiteSettings

def main():
    if len(sys.argv) < 2:
        print("Usage: send_backup_email.py <path_to_backup_file>")
        sys.exit(1)
        
    backup_file = sys.argv[1]
    if not os.path.exists(backup_file):
        print(f"Error: File {backup_file} does not exist.")
        sys.exit(1)
        
    # Check if Email Backups are enabled in Django Admin Panel
    try:
        site_settings = SiteSettings.get_singleton()
        if not site_settings.enable_email_backup:
            print("Daily Email Backups are DISABLED in the Django Admin Panel. Skipping email dispatch.")
            sys.exit(0)
    except Exception as e:
        print(f"Warning: Could not query SiteSettings from database ({e}). Proceeding to send backup email anyway...")

    # Read settings from .env file
    env_path = "/var/www/stall_cart_project/.env"
    env_data = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_data[key.strip()] = val.strip()

    smtp_host = env_data.get("EMAIL_HOST", "smtp-relay.brevo.com")
    smtp_port = int(env_data.get("EMAIL_PORT", 2525))
    smtp_user = env_data.get("EMAIL_HOST_USER")
    smtp_pass = env_data.get("EMAIL_HOST_PASSWORD")
    sender_email = "stallcart.in@gmail.com"
    receiver_email = "stallcart.in@gmail.com"

    if not smtp_user or not smtp_pass:
        print("Error: SMTP credentials not found in .env file.")
        sys.exit(1)

    print(f"Sending backup email using host: {smtp_host}:{smtp_port}, user: {smtp_user}...")

    # Create message
    msg = MIMEMultipart()
    msg['From'] = f"StallCart Backup <{sender_email}>"
    msg['To'] = receiver_email
    msg['Subject'] = f"StallCart Database Backup - {os.path.basename(backup_file)}"

    body = "Please find attached the daily database backup for StallCart.\n\nBest regards,\nStallCart Server Backup System"
    msg.attach(MIMEText(body, 'plain'))

    # Attach file
    with open(backup_file, "rb") as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(backup_file)}")
        msg.attach(part)

    # Send mail
    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print("Backup email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
