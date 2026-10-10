import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template import Template, Context
from .models import EmailTemplate

logger = logging.getLogger(__name__)

# Default templates to automatically populate the database if not already created
DEFAULT_TEMPLATES = {
    'registration_email_otp': {
        'subject': "StallCart - Registration Verification OTP",
        'body': "Welcome to StallCart! Your verification OTP is: {{ otp }}. Valid for 10 minutes.",
        'description': "OTP sent to verify customer or seller email address during registration"
    },
    'update_email_otp': {
        'subject': "StallCart - Email Update OTP",
        'body': "Your verification OTP to update your email is: {{ otp }}. Valid for 10 minutes.",
        'description': "OTP sent to verify user's new email address when updating profile email"
    },
    'change_password_otp': {
        'subject': "StallCart - Password Change OTP",
        'body': "Your verification OTP to change your password is: {{ otp }}. Valid for 10 minutes.",
        'description': "OTP sent to logged-in user to verify identity before password change"
    },
    'forgot_password_otp': {
        'subject': "StallCart - Password Reset OTP",
        'body': "Your verification OTP to reset your password is: {{ otp }}. Valid for 10 minutes.",
        'description': "OTP sent to retrieve/reset password for forgotten accounts"
    },
    'order_status_update': {
        'subject': "StallCart - Order {{ order_id }} Update: {{ status }}",
        'body': "Hello {{ customer_name }},\n\nYour order #{{ order_id }} status has been updated to: {{ status }}.\n\n{% if courier_name %}Courier: {{ courier_name }}{% endif %}\n{% if tracking_number %}Tracking AWB: {{ tracking_number }}{% endif %}\n\nThank you for shopping with StallCart!",
        'description': "Status update notification email sent to customer"
    },
    'seller_verified': {
        'subject': "StallCart - Seller Account Verified!",
        'body': "Congratulations {{ seller_name }}!\n\nYour seller account and shop '{{ shop_name }}' have been verified by our admin team. You can now login and start listing products on StallCart!\n\nBest Regards,\nStallCart Team",
        'description': "Email sent to seller when their profile is verified by an admin"
    },
    'admin_notify_verification': {
        'subject': "StallCart Admin - New Seller Registration: {{ shop_name }}",
        'body': "Hello Admin,\n\nA new seller has registered on StallCart and is pending verification:\n\nShop Name: {{ shop_name }}\nSeller Name: {{ seller_name }}\nPhone: {{ phone }}\nEmail: {{ email }}\n\nPlease review and take action from the admin dashboard: {{ dashboard_url }}.",
        'description': "Email notification sent to admins when a new seller registers"
    },
    'customer_order_placed': {
        'subject': "StallCart - Order {{ order_id }} Placed Successfully",
        'body': "Hello {{ customer_name }},\n\nYour order #{{ order_id }} has been placed successfully!\n\n--- Items ---\n{{ items_list }}\n\n--- Delivery Address ---\n{{ shipping_address }}\n\nPayment Method: {{ payment_method }}\nGrand Total: ₹{{ total_amount }}\n\nThank you for shopping with StallCart!",
        'description': "Email confirmation sent to customer when order is successfully placed"
    },
    'seller_new_order': {
        'subject': "StallCart Seller - New Order {{ order_id }} Received",
        'body': "Hello {{ seller_name }},\n\nYou have received a new order #{{ order_id }} containing your products.\n\n--- Items to Prepare ---\n{{ items_list }}\n\n--- Shipping Address ---\n{{ shipping_address }}\n\nPlease prepare the items for pickup/shipping.\n\nBest Regards,\nStallCart Team",
        'description': "Email notification sent to seller when a customer orders their products"
    },
    'admin_seller_awb_alert': {
        'subject': "StallCart Action Required - Update Tracking AWB for Order {{ order_id }}",
        'body': "Hello,\n\nOrder #{{ order_id }} is currently in '{{ status }}' status but does not have a tracking AWB number assigned in StallCart.\n\nResolved Pickup Location: {{ pickup_location }}\nCustomer Name: {{ customer_name }}\n\nPlease update the tracking/AWB number for this order in the admin portal to keep the customer updated.\n\nLink to Order: {{ admin_order_url }}\n\nBest Regards,\nStallCart Team",
        'description': "Alert sent to admin or seller when an order is processing/confirmed but has no tracking/AWB assigned"
    },
    'awb_assigned_notification': {
        'subject': "StallCart - Tracking AWB assigned for Order {{ order_id }}",
        'body': "Hello,\n\nTracking AWB number {{ tracking_number }} ({{ courier_name }}) has been assigned to Order #{{ order_id }}.\n\nLink to Order: {{ admin_order_url }}\n\nBest Regards,\nStallCart Team",
        'description': "Notification sent to admin/seller when AWB tracking is automatically synced"
    },
    'customer_payment_success': {
        'subject': "StallCart - Payment Received for Order {{ order_id }}",
        'body': "Hello {{ customer_name }},\n\nWe have successfully received payment of ₹{{ amount }} for your order #{{ order_id }}.\n\nPayment Method: {{ payment_method }}\n{% if payment_id %}Transaction ID: {{ payment_id }}{% endif %}\n\nThank you for shopping with StallCart!",
        'description': "Payment success notification sent to customer"
    },
    'seller_payment_success': {
        'subject': "StallCart Seller - Payment Confirmed for Order {{ order_id }}",
        'body': "Hello {{ seller_name }},\n\nPayment has been successfully received/confirmed for order #{{ order_id }}.\n\n--- Items ---\n{{ items_list }}\n\nPlatform Commission: ₹{{ commission_amount }}\nYour Net Earnings: ₹{{ net_earnings }}\n\nBest Regards,\nStallCart Team",
        'description': "Payment success notification sent to seller"
    },
    'customer_payment_refunded': {
        'subject': "StallCart - Refund Processed for Order {{ order_id }}",
        'body': "Hello {{ customer_name }},\n\nA refund of ₹{{ refund_amount }} has been processed for your order #{{ order_id }}.\n\n{% if refund_id %}Refund ID: {{ refund_id }}{% endif %}\n\nIt should reflect in your account within 3-5 business days.\n\nBest Regards,\nStallCart Team",
        'description': "Refund confirmation email sent to customer"
    },
    'seller_payment_refunded': {
        'subject': "StallCart Seller - Refund Processed for Order {{ order_id }}",
        'body': "Hello {{ seller_name }},\n\nA refund has been processed for order #{{ order_id }}.\n\n--- Items ---\n{{ items_list }}\n\nRefunded Amount: ₹{{ refund_amount }}\nThe earnings adjustment will be reflected in your next settlement.\n\nBest Regards,\nStallCart Team",
        'description': "Refund notification email sent to seller"
    },
    'seller_order_status_update': {
        'subject': "StallCart Seller - Order {{ order_id }} Update: {{ status }}",
        'body': "Hello {{ seller_name }},\n\nOrder #{{ order_id }} status has been updated to: {{ status }}.\n\n{% if courier_name %}Courier: {{ courier_name }}{% endif %}\n{% if tracking_number %}Tracking AWB: {{ tracking_number }}{% endif %}\n\nBest Regards,\nStallCart Team",
        'description': "Order status update notification sent to seller"
    },
    'admin_notify_pan_verification': {
        'subject': "StallCart Admin - Seller PAN Submitted for Verification: {{ shop_name }}",
        'body': "Hello Admin,\n\nSeller '{{ seller_name }}' (Shop: '{{ shop_name }}') has submitted or updated their PAN details for verification:\n\nPAN Number: {{ pan_number }}\n\nPlease review the PAN details and document in the admin dashboard: {{ dashboard_url }}.\n\nBest Regards,\nStallCart Team",
        'description': "Email notification sent to admins when a seller submits or updates their PAN details for verification"
    },
    'seller_pan_verified': {
        'subject': "StallCart - PAN Verification Successful!",
        'body': "Hello {{ seller_name }},\n\nYour PAN Card (PAN Number: {{ pan_number }}) for your shop '{{ shop_name }}' has been successfully verified by our admin team!\n\nYour seller profile is now verified, and you can access all seller features.\n\nBest Regards,\nStallCart Team",
        'description': "Email notification sent to the seller when their PAN card is verified"
    },
    'seller_pan_rejected': {
        'subject': "StallCart - PAN Verification Rejected",
        'body': "Hello {{ seller_name }},\n\nYour PAN Card verification request for your shop '{{ shop_name }}' has been rejected by our admin team.\n\nReason: {{ rejection_reason }}\n\nPlease update your PAN details and upload a valid document in your profile page: {{ profile_url }}.\n\nBest Regards,\nStallCart Team",
        'description': "Email notification sent to the seller when their PAN card is rejected"
    },
    'seller_settlement_processed': {
        'subject': "StallCart Seller - Settlement {{ settlement_id }} Processed Successfully",
        'body': "Hello {{ seller_name }},\n\nWe are pleased to inform you that your settlement #{{ settlement_id }} has been processed successfully.\n\nYour net earnings of ₹{{ settlement_amount }} have been transferred to your registered bank account.\n\n--- Settlement Details ---\n{% for item in items_details %}\n- Product: {{ item.product_name }}\n  Order ID: {{ item.order_id }}\n  Item Total: ₹{{ item.total_amount }}\n  Platform Commission ({{ item.commission_rate }}%): -₹{{ item.commission_amount }}\n  Your Profit / Net Earnings: ₹{{ item.seller_earnings }}\n{% endfor %}\n\nTotal Transferred Amount: ₹{{ settlement_amount }}\nCommission Deducted (Admin Account): ₹{{ total_commission }}\n\nReference / Payout ID: {{ payment_reference }}\n\nBest Regards,\nStallCart Team",
        'description': "Email notification sent to seller when a settlement and payout are successfully processed"
    },
    'campaign_winner_notification': {
        'subject': "🎉 Congratulations! You won {{ prize_title }} in StallCart {{ campaign_title }}!",
        'body': "Hello {{ customer_name }},\n\n🎉 Heartiest Congratulations! 🎉\n\nYou have been selected as a winner in the StallCart '{{ campaign_title }}' Lucky Draw!\n\n🏆 Prize Won: {{ prize_title }}\n{% if prize_subtitle %}{{ prize_subtitle }}\n{% endif %}\n{% if approx_value %}Approx Value: ₹{{ approx_value }}\n{% endif %}\n{% if ticket_number %}Winning Ticket: {{ ticket_number }}\n{% endif %}\nOur team will contact you shortly on your registered mobile number ({{ phone }}) to coordinate your prize handover.\n\nYou can also log in to StallCart anytime to view your won prize in your Profile.\n\nBest Regards,\nStallCart Team",
        'description': "Default notification sent to user when they win a lucky draw campaign prize"
    },
    'campaign_winner_dandiya_nights_2026': {
        'subject': "🎉 Congratulations {{ customer_name }}! You Won {{ prize_title }} in Dandiya Nights 2026!",
        'body': """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎉 You Won in StallCart Dandiya Nights 2026!</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 20px; color: #1e293b; }
  .email-container { max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }
  .header { background: linear-gradient(135deg, #be123c 0%, #881337 50%, #1e1b4b 100%); padding: 36px 24px; text-align: center; color: #ffffff; }
  .header-pill { background: rgba(255,255,255,0.22); color: #fff; font-size: 11px; font-weight: 800; padding: 4px 12px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.08em; display: inline-block; margin-bottom: 12px; }
  .header h1 { margin: 0; font-size: 24px; font-weight: 900; letter-spacing: -0.01em; color: #ffffff; }
  .header p { margin: 8px 0 0 0; font-size: 14px; opacity: 0.92; color: #fecdd3; }
  .content { padding: 32px 28px; }
  .greeting { font-size: 17px; font-weight: 700; color: #0f172a; margin-bottom: 14px; }
  .winner-box { background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%); border: 2px solid #f59e0b; border-radius: 14px; padding: 22px; text-align: center; margin: 24px 0; }
  .winner-badge { font-size: 13px; font-weight: 800; color: #b45309; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }
  .prize-title { font-size: 22px; font-weight: 900; color: #0f172a; margin: 0 0 8px 0; }
  .prize-subtitle { font-size: 13px; color: #78350f; margin: 0 0 14px 0; }
  .ticket-chip { background: #1e1b4b; color: #f8fafc; display: inline-block; font-family: monospace; font-size: 15px; font-weight: 800; padding: 6px 16px; border-radius: 8px; letter-spacing: 0.05em; }
  .steps-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin: 24px 0; }
  .steps-title { font-size: 14px; font-weight: 800; color: #0f172a; margin-bottom: 12px; }
  .step-item { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; font-size: 13px; color: #475569; line-height: 1.5; }
  .step-num { background: #be123c; color: #fff; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; flex-shrink: 0; }
  .btn-dashboard { display: block; background: #e11d48; color: #ffffff !important; text-align: center; font-weight: 800; font-size: 14px; padding: 12px 24px; border-radius: 8px; text-decoration: none; margin: 24px 0 16px 0; box-shadow: 0 2px 10px rgba(225,29,72,0.35); }
  .footer { background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px; text-align: center; font-size: 12px; color: #64748b; line-height: 1.6; }
</style>
</head>
<body>
<div class="email-container">
  <div class="header">
    <span class="header-pill">🎉 Dandiya Nights Mega Lucky Draw 2026</span>
    <h1>CONGRATULATIONS! YOU WON!</h1>
    <p>17 October 2026 Festive Celebration Prize</p>
  </div>
  <div class="content">
    <div class="greeting">Dear {{ customer_name }},</div>
    <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 16px 0;">
      We are overjoyed to announce that you have won a grand prize in the <strong>StallCart {{ campaign_title }}</strong>!
    </p>
    <div class="winner-box">
      <div class="winner-badge">🏆 {{ prize_rank_display }} Winner</div>
      <div class="prize-title">{{ prize_title }}</div>
      {% if prize_subtitle %}<div class="prize-subtitle">{{ prize_subtitle }}</div>{% endif %}
      <div style="font-size: 12px; color: #78350f; margin-bottom: 6px;">Winning Ticket Number:</div>
      <div class="ticket-chip">{{ ticket_number }}</div>
    </div>
    <div class="steps-card">
      <div class="steps-title">🎁 Next Steps for Prize Handover:</div>
      <div class="step-item">
        <span class="step-num">1</span>
        <span><strong>Verification Call:</strong> Our StallCart representative will contact you on your registered mobile number (<strong>{{ phone }}</strong>) to verify your delivery address.</span>
      </div>
      <div class="step-item">
        <span class="step-num">2</span>
        <span><strong>Doorstep Delivery / Handover:</strong> Your prize will be securely dispatched to your verified address or handed over at the Dandiya Night celebration on <strong>17 October 2026</strong>.</span>
      </div>
      <div class="step-item">
        <span class="step-num">3</span>
        <span><strong>Profile Verification:</strong> You can view your winning prize status anytime in your VIP StallCart Dashboard.</span>
      </div>
    </div>
    <a href="{{ profile_url }}" class="btn-dashboard">View Won Prize in Your Dashboard →</a>
    <p style="font-size: 13px; color: #64748b; line-height: 1.5; text-align: center; margin: 0;">
      Thank you for shopping and celebrating with <strong>StallCart</strong>!
    </p>
  </div>
  <div class="footer">
    <div><strong>StallCart</strong> &bull; India's Premier Online Fashion & Lifestyle Marketplace</div>
    <div style="margin-top: 4px;">Need assistance? Contact our VIP Support: <a href="mailto:support@stallcart.in" style="color: #e11d48; text-decoration: none;">support@stallcart.in</a></div>
  </div>
</div>
</body>
</html>""",
        'description': "Event-specific winner notification email for Dandiya Nights 2026 (17 Oct event)"
    }
}

def send_dynamic_email(template_name: str, recipient_list: list, context_data: dict) -> bool:
    """
    Sends an email using templates stored dynamically in the EmailTemplate model.
    Auto-populates templates if not found in the DB. Supports both rich HTML and plain text emails.
    """
    try:
        # Get or create the template in DB
        template_obj = EmailTemplate.objects.filter(name=template_name).first()
        if not template_obj:
            default_data = DEFAULT_TEMPLATES.get(template_name)
            if default_data:
                template_obj = EmailTemplate.objects.create(
                    name=template_name,
                    subject=default_data['subject'],
                    body=default_data['body'],
                    description=default_data['description']
                )
            else:
                logger.error(f"Email template '{template_name}' not defined in defaults.")
                return False

        # Render subject and body with Django Template engine
        subject_tpl = Template(template_obj.subject)
        body_tpl = Template(template_obj.body)
        
        context = Context(context_data)
        
        rendered_subject = subject_tpl.render(context).strip().replace("\n", " ").replace("\r", "")
        rendered_body = body_tpl.render(context)
        
        is_html = '<html' in rendered_body.lower() or '<div' in rendered_body.lower() or '<table' in rendered_body.lower()
        
        if not is_html:
            # Append support contact footer dynamically for plain text
            try:
                from .models import SiteSettings
                site_settings = SiteSettings.get_singleton()
                phone = site_settings.contact_phone or "+91 8004096954"
                email = site_settings.contact_email or "stallcart.in@gmail.com"
            except Exception:
                phone = "+91 8004096954"
                email = "stallcart.in@gmail.com"
                
            footer_text = f"\n\n---\n📞 Need Support? Contact us at {phone} or email us at {email}\n✨ Thank you for choosing StallCart!"
            plain_message = rendered_body + footer_text
            html_message = None
        else:
            plain_message = rendered_body
            html_message = rendered_body
        
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'StallCart <ad4b11001@smtp-brevo.com>')
        
        send_mail(
            subject=rendered_subject,
            message=plain_message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Successfully sent dynamic email '{template_name}' to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Failed to send dynamic email '{template_name}' to {recipient_list}: {e}", exc_info=True)
        return False
