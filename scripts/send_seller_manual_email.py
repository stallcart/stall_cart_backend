import os
import sys
import django

# Setup django environment
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stall_cart.settings')
django.setup()

from django.core.mail import EmailMessage
from django.conf import settings
from common.models import SiteSettings

def send_manual_email(recipients=None):
    if not recipients:
        recipients = ['stallcart.in@gmail.com', 'jaiswalmanish9866@gmail.com']
    
    site_settings = SiteSettings.objects.first()
    support_phone = getattr(site_settings, 'contact_phone', '+91 7307383046') if site_settings else '+91 7307383046'
    support_email = getattr(site_settings, 'contact_email', 'stallcartsupport@gmail.com') if site_settings else 'stallcartsupport@gmail.com'
    site_name = getattr(site_settings, 'site_name', 'StallCart') if site_settings else 'StallCart'

    pdf_path = os.path.join(BASE_DIR, 'static', 'docs', 'StallCart_Seller_Manual.pdf')
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found at {pdf_path}. Please run scripts/build_seller_manual.py first.")

    subject = f"📘 StallCart Official Seller Operations Manual (Bilingual: Hindi & English) - StallCart Partner Program"
    
    body_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
  .box {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; }}
  .header {{ background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); padding: 32px 24px; text-align: center; color: #ffffff; }}
  .badge {{ background: rgba(255,255,255,0.2); padding: 4px 14px; border-radius: 20px; font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.08em; display: inline-block; margin-bottom: 10px; }}
  .content {{ padding: 28px 24px; line-height: 1.6; font-size: 14px; }}
  .module-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #4f46e5; border-radius: 8px; padding: 12px 16px; margin: 10px 0; }}
  .footer {{ background: #f1f5f9; padding: 20px; text-align: center; font-size: 12px; color: #64748b; }}
</style>
</head>
<body>
<div class="box">
  <div class="header">
    <span class="badge">Official Partner Document</span>
    <h1 style="margin: 0; font-size: 24px; font-weight: 800;">StallCart Seller Operations Manual</h1>
    <p style="margin: 6px 0 0; color: #c7d2fe; font-size: 13px;">विक्रेता संचालन नियमावली • Bilingual: Hindi & English SOP Guide</p>
  </div>
  <div class="content">
    <p>Namaste Manish ji & StallCart Operations Team,</p>
    <p>As requested, here is the complete <strong>Bilingual (Hindi + English) Seller Operations Manual</strong> with high-resolution UI walkthrough screenshots from our actual StallCart platform.</p>

    <h3 style="color: #1e1b4b; margin-top: 20px;">📘 Manual Content Modules / मैनुअल अध्याय:</h3>
    <div class="module-card">
      <strong>Module 1: Seller Onboarding & KYC</strong><br>
      दुकान पंजीकरण, बैंक खाता (Bank of Baroda), IFSC कोड, और एडमिन KYC सत्यापन।
    </div>
    <div class="module-card">
      <strong>Module 2: Product Listing & Cataloging</strong><br>
      उत्पाद लिस्टिंग, 15% कैटेगरी कमीशन, MRP vs सेलिंग प्राइस, और वेरियंट्स (Color/Size/Multi-pack)।
    </div>
    <div class="module-card">
      <strong>Module 3: Order Lifecycle Management</strong><br>
      नया ऑर्डर अलर्ट, 24 घंटे की SLA पैकिंग समयसीमा, टैक्स इनवॉइस (Print Invoice), और Accept & Pack।
    </div>
    <div class="module-card">
      <strong>Module 4: Packaging Standard Operating Procedure (SOP)</strong><br>
      5-स्टेप सुरक्षित पैकिंग गाइड, वॉटरप्रूफ बबल रैप, इनवॉइस पाउच, और AWB बारकोड लेबलिंग।
    </div>
    <div class="module-card">
      <strong>Module 5: Courier Dispatch & OTP Delivery</strong><br>
      Shiprocket / Delhivery कूरियर पिकअप टोकन, AWB ट्रैकिंग, और 4-अंकों का सीक्रेट OTP सुरक्षा कोड।
    </div>
    <div class="module-card">
      <strong>Module 6: Transactional Emails & Notifications</strong><br>
      ईमेल अलर्ट्स, ऑर्डर समरी, पिकअप स्लिप, और सेटलमेंट पेमेंट पुष्टिकरण।
    </div>
    <div class="module-card">
      <strong>Module 7: Settlements, Commission & Bank Payouts</strong><br>
      डिलीवरी के बाद नेट पेआउट, 15% पारदर्शी कमीशन कटौती, UTR रेफरेंस नंबर, और डायरेक्ट बैंक क्रेडिट।
    </div>
    <div class="module-card">
      <strong>Module 8: Returns (RTO), Quality Control & Seller Support</strong><br>
      7-दिन की रिटर्न पॉलिसी, RTO रिटर्न हैंडलिंग, डैमेज क्लेम SOP, और हेल्पडेस्क सपोर्ट।
    </div>

    <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; margin: 20px 0; color: #065f46;">
      <strong>✅ Attached Document:</strong> StallCart_Seller_Manual.pdf (Attached below, ~470 KB)<br>
      <strong>🌐 Live Download Link:</strong> <a href="https://stallcart.in/download/seller-manual/" style="color: #059669; font-weight: 700;">https://stallcart.in/download/seller-manual/</a>
    </div>

    <p style="font-size: 13px; color: #64748b;">This PDF manual is also available via one-click download directly inside the <strong>StallCart Admin Panel</strong> (Header, Verify Sellers, Orders, and Settlements dashboard) and the <strong>Seller Dashboard</strong>.</p>
  </div>
  <div class="footer">
    <strong>{site_name}</strong> &bull; India's Premier Online Marketplace<br>
    Helpdesk: {support_phone} &bull; Email: {support_email}<br>
    &copy; 2026 StallCart. All rights reserved.
  </div>
</div>
</body>
</html>"""

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'StallCart <stallcart.in@gmail.com>')
    msg = EmailMessage(
        subject=subject,
        body=body_html,
        from_email=from_email,
        to=recipients
    )
    msg.content_subtype = "html"
    
    with open(pdf_path, 'rb') as f:
        msg.attach('StallCart_Seller_Manual.pdf', f.read(), 'application/pdf')

    print(f"Sending email with attached PDF to {recipients} from {from_email}...")
    sent = msg.send(fail_silently=False)
    print(f"Email sent successfully! Result: {sent}")
    return sent

if __name__ == '__main__':
    send_manual_email()
