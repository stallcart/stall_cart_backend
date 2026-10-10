import logging
from django.core.mail import send_mail
from django.conf import settings
from django.template import Template, Context
from .models import EmailTemplate

logger = logging.getLogger(__name__)

def _base_email_wrapper(title, header_pill, header_h1, header_sub, content_html):
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
  .email-wrapper {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
  .email-header {{ background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); padding: 30px 24px; text-align: center; color: #ffffff; }}
  .header-pill {{ background: rgba(255,255,255,0.18); color: #f8fafc; font-size: 11px; font-weight: 800; padding: 4px 12px; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.06em; display: inline-block; margin-bottom: 8px; }}
  .header-brand {{ margin: 0; font-size: 22px; font-weight: 900; letter-spacing: -0.01em; color: #ffffff; }}
  .header-tag {{ margin: 4px 0 0 0; font-size: 13px; color: #94a3b8; }}
  .email-body {{ padding: 30px 24px; }}
  .greeting {{ font-size: 16px; font-weight: 700; color: #0f172a; margin-bottom: 12px; }}
  .info-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin: 18px 0; }}
  .highlight-badge {{ background: linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%); border: 1px solid #bfdbfe; border-radius: 12px; padding: 18px; text-align: center; margin: 20px 0; }}
  .otp-display {{ font-family: monospace; font-size: 32px; font-weight: 900; letter-spacing: 8px; color: #2563eb; margin: 8px 0; }}
  .btn-primary {{ display: inline-block; background: #e11d48; color: #ffffff !important; font-weight: 800; font-size: 14px; padding: 11px 24px; border-radius: 8px; text-decoration: none; box-shadow: 0 2px 8px rgba(225,29,72,0.3); margin: 16px 0; }}
  .email-footer {{ background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px; text-align: center; font-size: 12px; color: #64748b; line-height: 1.6; }}
  .detail-table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  .detail-table td {{ padding: 8px 0; border-bottom: 1px solid #f1f5f9; font-size: 13px; }}
  .detail-table td.lbl {{ color: #64748b; font-weight: 600; width: 40%; }}
  .detail-table td.val {{ color: #0f172a; font-weight: 700; text-align: right; }}
</style>
</head>
<body>
<div class="email-wrapper">
  <div class="email-header">
    <span class="header-pill">{header_pill}</span>
    <h1 class="header-brand">{header_h1}</h1>
    <p class="header-tag">{header_sub}</p>
  </div>
  <div class="email-body">
    {content_html}
  </div>
  <div class="email-footer">
    <div><strong>StallCart</strong> &bull; India's Premier Fashion & Lifestyle Marketplace</div>
    <div style="margin-top: 4px;">Need help? Call +91 8004096954 or email <a href="mailto:stallcart.in@gmail.com" style="color: #e11d48; text-decoration: none;">stallcart.in@gmail.com</a></div>
    <div style="margin-top: 4px; font-size: 11px; color: #94a3b8;">&copy; 2026 StallCart. All rights reserved.</div>
  </div>
</div>
</body>
</html>"""

# Default templates to automatically populate the database
DEFAULT_TEMPLATES = {
    'registration_email_otp': {
        'subject': "StallCart - Registration Verification OTP",
        'body': _base_email_wrapper(
            "StallCart - Email Verification",
            "🔐 Account Verification",
            "Welcome to StallCart",
            "Verify your email address to get started",
            """<div class="greeting">Hello,</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              Thank you for signing up on <strong>StallCart</strong>! Please use the following One-Time Password (OTP) to verify your account registration.
            </p>
            <div class="highlight-badge">
              <div style="font-size: 12px; color: #64748b; font-weight: 700; text-transform: uppercase;">Your Verification OTP</div>
              <div class="otp-display">{{ otp }}</div>
              <div style="font-size: 12px; color: #64748b;">⏱️ Valid for 10 minutes. Do not share this OTP with anyone.</div>
            </div>
            <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin: 16px 0 0 0;">
              If you did not request this registration, please safely ignore this email.
            </p>"""
        ),
        'description': "OTP sent to verify customer or seller email address during registration"
    },
    'update_email_otp': {
        'subject': "StallCart - Email Update OTP",
        'body': _base_email_wrapper(
            "StallCart - Email Update",
            "✉️ Email Change Verification",
            "Update Your Email",
            "Confirm your new StallCart email address",
            """<div class="greeting">Hello,</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              We received a request to update your registered email address on <strong>StallCart</strong>. Use the OTP below to confirm this change:
            </p>
            <div class="highlight-badge">
              <div style="font-size: 12px; color: #64748b; font-weight: 700; text-transform: uppercase;">Your Verification OTP</div>
              <div class="otp-display">{{ otp }}</div>
              <div style="font-size: 12px; color: #64748b;">⏱️ Valid for 10 minutes. Keep this confidential.</div>
            </div>
            <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin: 16px 0 0 0;">
              If you did not initiate this request, please change your password immediately.
            </p>"""
        ),
        'description': "OTP sent to verify user's new email address when updating profile email"
    },
    'change_password_otp': {
        'subject': "StallCart - Password Change OTP",
        'body': _base_email_wrapper(
            "StallCart - Security Verification",
            "🔒 Security Alert",
            "Password Change Request",
            "Verify your identity to update your password",
            """<div class="greeting">Hello,</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              A request was made to change the password for your <strong>StallCart</strong> account. Please use this OTP to proceed:
            </p>
            <div class="highlight-badge">
              <div style="font-size: 12px; color: #64748b; font-weight: 700; text-transform: uppercase;">Password Change OTP</div>
              <div class="otp-display">{{ otp }}</div>
              <div style="font-size: 12px; color: #64748b;">⏱️ Valid for 10 minutes. Never share this code.</div>
            </div>
            <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin: 16px 0 0 0;">
              If you didn't request a password change, contact support immediately at stallcart.in@gmail.com.
            </p>"""
        ),
        'description': "OTP sent to logged-in user to verify identity before password change"
    },
    'forgot_password_otp': {
        'subject': "StallCart - Password Reset OTP",
        'body': _base_email_wrapper(
            "StallCart - Reset Password",
            "🔑 Account Recovery",
            "Reset Your Password",
            "Verification code to recover your account",
            """<div class="greeting">Hello,</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              You requested a password reset for your <strong>StallCart</strong> account. Enter the OTP below on the reset page:
            </p>
            <div class="highlight-badge">
              <div style="font-size: 12px; color: #64748b; font-weight: 700; text-transform: uppercase;">Password Reset OTP</div>
              <div class="otp-display">{{ otp }}</div>
              <div style="font-size: 12px; color: #64748b;">⏱️ Valid for 10 minutes.</div>
            </div>
            <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin: 16px 0 0 0;">
              If you remembered your password or didn't request this reset, you can safely disregard this email.
            </p>"""
        ),
        'description': "OTP sent to retrieve/reset password for forgotten accounts"
    },
    'order_status_update': {
        'subject': "StallCart - Order {{ order_id }} Update: {{ status }}",
        'body': _base_email_wrapper(
            "StallCart - Order Status Update",
            "📦 Order Tracking",
            "Order Status Update",
            "Order #{{ order_id }}",
            """<div class="greeting">Hello {{ customer_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              Your order <strong>#{{ order_id }}</strong> has a new status update:
            </p>
            <div class="info-box">
              <table class="detail-table">
                <tr><td class="lbl">Order ID</td><td class="val">#{{ order_id }}</td></tr>
                <tr><td class="lbl">Current Status</td><td class="val"><span style="color: #2563eb; text-transform: uppercase;">{{ status }}</span></td></tr>
                {% if courier_name %}<tr><td class="lbl">Courier Partner</td><td class="val">{{ courier_name }}</td></tr>{% endif %}
                {% if tracking_number %}<tr><td class="lbl">Tracking AWB</td><td class="val">{{ tracking_number }}</td></tr>{% endif %}
              </table>
            </div>
            <div style="text-align: center;">
              <a href="https://stallcart.in/accounts/profile/" class="btn-primary">Track Order in Dashboard &rarr;</a>
            </div>
            <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin: 14px 0 0 0;">
              Thank you for shopping with StallCart!
            </p>"""
        ),
        'description': "Status update notification email sent to customer"
    },
    'customer_order_placed': {
        'subject': "StallCart - Order {{ order_id }} Placed Successfully",
        'body': _base_email_wrapper(
            "StallCart - Order Confirmation",
            "🎉 Order Confirmed",
            "Thank You for Your Order!",
            "Order #{{ order_id }} placed successfully",
            """<div class="greeting">Hello {{ customer_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              We have received your order <strong>#{{ order_id }}</strong>! Our team is preparing your package for dispatch.
            </p>
            <div class="info-box">
              <div style="font-weight: 800; font-size: 14px; color: #0f172a; margin-bottom: 8px;">Order Details</div>
              <div style="font-size: 13px; color: #334155; line-height: 1.6; white-space: pre-line; margin-bottom: 12px;">{{ items_list }}</div>
              <table class="detail-table">
                <tr><td class="lbl">Payment Method</td><td class="val">{{ payment_method }}</td></tr>
                <tr><td class="lbl">Grand Total</td><td class="val" style="color: #16a34a; font-size: 15px;">₹{{ total_amount }}</td></tr>
              </table>
              <div style="margin-top: 10px; font-size: 12px; color: #64748b;">
                <strong>Shipping Address:</strong><br>{{ shipping_address }}
              </div>
            </div>
            <div style="text-align: center;">
              <a href="https://stallcart.in/accounts/profile/" class="btn-primary">View Order & Status &rarr;</a>
            </div>"""
        ),
        'description': "Email confirmation sent to customer when order is successfully placed"
    },
    'customer_payment_success': {
        'subject': "StallCart - Payment Received for Order {{ order_id }}",
        'body': _base_email_wrapper(
            "StallCart - Payment Confirmation",
            "💳 Payment Success",
            "Payment Confirmed",
            "Payment for Order #{{ order_id }}",
            """<div class="greeting">Hello {{ customer_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              We have successfully received your payment of <strong>₹{{ amount }}</strong> for order <strong>#{{ order_id }}</strong>.
            </p>
            <div class="info-box">
              <table class="detail-table">
                <tr><td class="lbl">Order ID</td><td class="val">#{{ order_id }}</td></tr>
                <tr><td class="lbl">Amount Paid</td><td class="val" style="color: #16a34a;">₹{{ amount }}</td></tr>
                <tr><td class="lbl">Payment Method</td><td class="val">{{ payment_method }}</td></tr>
                {% if payment_id %}<tr><td class="lbl">Transaction ID</td><td class="val">{{ payment_id }}</td></tr>{% endif %}
              </table>
            </div>
            <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin: 14px 0 0 0;">
              Your order is now being processed for shipping. Thank you for choosing StallCart!
            </p>"""
        ),
        'description': "Payment success notification sent to customer"
    },
    'customer_payment_refunded': {
        'subject': "StallCart - Refund Processed for Order {{ order_id }}",
        'body': _base_email_wrapper(
            "StallCart - Refund Notification",
            "💸 Refund Processed",
            "Refund Confirmation",
            "Order #{{ order_id }}",
            """<div class="greeting">Hello {{ customer_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              A refund of <strong>₹{{ refund_amount }}</strong> has been successfully processed for your order <strong>#{{ order_id }}</strong>.
            </p>
            <div class="info-box">
              <table class="detail-table">
                <tr><td class="lbl">Order ID</td><td class="val">#{{ order_id }}</td></tr>
                <tr><td class="lbl">Refund Amount</td><td class="val" style="color: #16a34a;">₹{{ refund_amount }}</td></tr>
                {% if refund_id %}<tr><td class="lbl">Refund Reference ID</td><td class="val">{{ refund_id }}</td></tr>{% endif %}
              </table>
              <div style="font-size: 12px; color: #64748b; margin-top: 8px;">
                💡 Online refunds typically reflect in your bank account / source payment mode within <strong>3-5 business days</strong>.
              </div>
            </div>"""
        ),
        'description': "Refund confirmation email sent to customer"
    },
    'seller_verified': {
        'subject': "StallCart - Seller Account Verified!",
        'body': _base_email_wrapper(
            "StallCart - Seller Account Verified",
            "✅ Seller Approval",
            "Welcome to StallCart Seller Hub",
            "Your shop '{{ shop_name }}' is now verified",
            """<div class="greeting">Congratulations {{ seller_name }}!</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              Your seller account and shop <strong>'{{ shop_name }}'</strong> have been officially verified by our admin team!
            </p>
            <div class="info-box" style="background: #f0fdf4; border-color: #bbf7d0;">
              <div style="font-weight: 800; color: #166534; font-size: 14px; margin-bottom: 6px;">🚀 You're Ready to Sell Across India</div>
              <div style="font-size: 13px; color: #15803d; line-height: 1.5;">
                You can now log in to the Seller Portal, list your catalog items, manage inventory, and receive orders.
              </div>
            </div>
            <div style="text-align: center;">
              <a href="https://stallcart.in/accounts/profile/" class="btn-primary">Go to Seller Dashboard &rarr;</a>
            </div>"""
        ),
        'description': "Email sent to seller when their profile is verified by an admin"
    },
    'seller_new_order': {
        'subject': "StallCart Seller - New Order {{ order_id }} Received",
        'body': _base_email_wrapper(
            "StallCart - New Order Received",
            "🛍️ New Order Alert",
            "You Received a New Order!",
            "Order #{{ order_id }}",
            """<div class="greeting">Hello {{ seller_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              Great news! A customer has placed a new order containing your products:
            </p>
            <div class="info-box">
              <div style="font-weight: 800; font-size: 14px; color: #0f172a; margin-bottom: 8px;">Items to Prepare</div>
              <div style="font-size: 13px; color: #334155; line-height: 1.6; white-space: pre-line; margin-bottom: 12px;">{{ items_list }}</div>
              <div style="font-size: 12px; color: #64748b;">
                <strong>Shipping Address:</strong><br>{{ shipping_address }}
              </div>
            </div>
            <div style="text-align: center;">
              <a href="https://stallcart.in/accounts/profile/" class="btn-primary">View & Process Order &rarr;</a>
            </div>"""
        ),
        'description': "Email notification sent to seller when a customer orders their products"
    },
    'seller_order_status_update': {
        'subject': "StallCart Seller - Order {{ order_id }} Update: {{ status }}",
        'body': _base_email_wrapper(
            "StallCart - Order Status",
            "📦 Shipment Status",
            "Order Status Update",
            "Order #{{ order_id }}",
            """<div class="greeting">Hello {{ seller_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              Order <strong>#{{ order_id }}</strong> status has been updated to: <strong style="color: #2563eb; text-transform: uppercase;">{{ status }}</strong>.
            </p>
            <div class="info-box">
              <table class="detail-table">
                <tr><td class="lbl">Order ID</td><td class="val">#{{ order_id }}</td></tr>
                <tr><td class="lbl">Status</td><td class="val">{{ status }}</td></tr>
                {% if courier_name %}<tr><td class="lbl">Courier Partner</td><td class="val">{{ courier_name }}</td></tr>{% endif %}
                {% if tracking_number %}<tr><td class="lbl">Tracking AWB</td><td class="val">{{ tracking_number }}</td></tr>{% endif %}
              </table>
            </div>"""
        ),
        'description': "Order status update notification sent to seller"
    },
    'admin_notify_verification': {
        'subject': "StallCart Admin - New Seller Registration: {{ shop_name }}",
        'body': _base_email_wrapper(
            "StallCart Admin - New Seller",
            "🛡️ Admin Alert",
            "New Seller Registration",
            "Pending Verification",
            """<div class="greeting">Hello Admin,</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              A new seller has registered on StallCart and is pending verification:
            </p>
            <div class="info-box">
              <table class="detail-table">
                <tr><td class="lbl">Shop Name</td><td class="val">{{ shop_name }}</td></tr>
                <tr><td class="lbl">Seller Name</td><td class="val">{{ seller_name }}</td></tr>
                <tr><td class="lbl">Mobile</td><td class="val">{{ phone }}</td></tr>
                <tr><td class="lbl">Email</td><td class="val">{{ email }}</td></tr>
              </table>
            </div>
            <div style="text-align: center;">
              <a href="{{ dashboard_url }}" class="btn-primary">Review Seller in Admin &rarr;</a>
            </div>"""
        ),
        'description': "Email notification sent to admins when a new seller registers"
    },
    'admin_notify_pan_verification': {
        'subject': "StallCart Admin - Seller PAN Submitted for Verification: {{ shop_name }}",
        'body': _base_email_wrapper(
            "StallCart Admin - PAN Verification",
            "🛡️ Compliance Alert",
            "Seller PAN Verification",
            "Shop: {{ shop_name }}",
            """<div class="greeting">Hello Admin,</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              Seller <strong>'{{ seller_name }}'</strong> (Shop: <strong>'{{ shop_name }}'</strong>) has submitted PAN details for verification:
            </p>
            <div class="info-box">
              <table class="detail-table">
                <tr><td class="lbl">Shop Name</td><td class="val">{{ shop_name }}</td></tr>
                <tr><td class="lbl">Seller Name</td><td class="val">{{ seller_name }}</td></tr>
                <tr><td class="lbl">PAN Number</td><td class="val">{{ pan_number }}</td></tr>
              </table>
            </div>
            <div style="text-align: center;">
              <a href="{{ dashboard_url }}" class="btn-primary">Review & Verify PAN in Admin &rarr;</a>
            </div>"""
        ),
        'description': "Email notification sent to admins when a seller submits or updates their PAN details for verification"
    },
    'seller_pan_verified': {
        'subject': "StallCart - PAN Verification Successful!",
        'body': _base_email_wrapper(
            "StallCart - PAN Verified",
            "✅ Document Verified",
            "PAN Verification Approved",
            "Shop: {{ shop_name }}",
            """<div class="greeting">Hello {{ seller_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              Your PAN Card (PAN: <strong>{{ pan_number }}</strong>) for shop <strong>'{{ shop_name }}'</strong> has been successfully verified!
            </p>
            <div class="info-box" style="background: #f0fdf4; border-color: #bbf7d0;">
              <div style="font-weight: 800; color: #166534; font-size: 14px;">✅ Full Selling & Settlement Access Enabled</div>
              <div style="font-size: 13px; color: #15803d; margin-top: 4px;">
                Your payouts and settlements will now be processed automatically to your verified bank account.
              </div>
            </div>"""
        ),
        'description': "Email notification sent to the seller when their PAN card is verified"
    },
    'seller_pan_rejected': {
        'subject': "StallCart - PAN Verification Rejected",
        'body': _base_email_wrapper(
            "StallCart - PAN Verification Status",
            "⚠️ Action Required",
            "PAN Verification Unsuccessful",
            "Shop: {{ shop_name }}",
            """<div class="greeting">Hello {{ seller_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              Your PAN Card verification request for <strong>'{{ shop_name }}'</strong> could not be approved.
            </p>
            <div class="info-box" style="background: #fef2f2; border-color: #fecaca;">
              <div style="font-weight: 800; color: #991b1b; font-size: 13px;">Reason for Rejection:</div>
              <div style="font-size: 13px; color: #b91c1c; margin-top: 4px;">{{ rejection_reason }}</div>
            </div>
            <div style="text-align: center;">
              <a href="{{ profile_url }}" class="btn-primary">Re-upload Valid PAN &rarr;</a>
            </div>"""
        ),
        'description': "Email notification sent to the seller when their PAN card is rejected"
    },
    'seller_settlement_processed': {
        'subject': "StallCart Seller - Settlement {{ settlement_id }} Processed Successfully",
        'body': _base_email_wrapper(
            "StallCart - Seller Settlement",
            "💰 Payout Dispatched",
            "Settlement Processed",
            "Settlement #{{ settlement_id }}",
            """<div class="greeting">Hello {{ seller_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              We have processed your settlement <strong>#{{ settlement_id }}</strong>. Net earnings of <strong style="color: #16a34a;">₹{{ settlement_amount }}</strong> have been transferred to your registered bank account.
            </p>
            <div class="info-box">
              <table class="detail-table">
                <tr><td class="lbl">Settlement ID</td><td class="val">#{{ settlement_id }}</td></tr>
                <tr><td class="lbl">Payout Amount</td><td class="val" style="color: #16a34a; font-size: 15px;">₹{{ settlement_amount }}</td></tr>
                <tr><td class="lbl">Platform Commission</td><td class="val">₹{{ total_commission }}</td></tr>
                {% if payment_reference %}<tr><td class="lbl">Payout Ref ID</td><td class="val">{{ payment_reference }}</td></tr>{% endif %}
              </table>
            </div>"""
        ),
        'description': "Email notification sent to seller when a settlement and payout are successfully processed"
    },
    'campaign_winner_notification': {
        'subject': "🎉 Congratulations! You won {{ prize_title }} in StallCart {{ campaign_title }}!",
        'body': _base_email_wrapper(
            "🎉 StallCart Lucky Draw Winner",
            "🏆 Winner Announcement",
            "Congratulations! You Won!",
            "{{ campaign_title }}",
            """<div class="greeting">Dear {{ customer_name }},</div>
            <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 14px 0;">
              🎉 Heartiest Congratulations! You have been selected as an official winner in the <strong>StallCart {{ campaign_title }}</strong> Lucky Draw!
            </p>
            <div class="info-box" style="background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%); border: 2px solid #f59e0b; text-align: center;">
              <div style="font-size: 13px; font-weight: 800; color: #b45309; text-transform: uppercase;">🏆 {{ prize_rank_display }} Winner</div>
              <div style="font-size: 20px; font-weight: 900; color: #0f172a; margin: 6px 0;">{{ prize_title }}</div>
              {% if prize_subtitle %}<div style="font-size: 13px; color: #78350f;">{{ prize_subtitle }}</div>{% endif %}
              {% if ticket_number %}<div style="margin-top: 10px; font-family: monospace; font-size: 14px; font-weight: 800; background: #1e1b4b; color: #fff; padding: 4px 12px; border-radius: 6px; display: inline-block;">Ticket: {{ ticket_number }}</div>{% endif %}
            </div>
            <p style="font-size: 13px; color: #475569; line-height: 1.6;">
              Our team will reach out to you on <strong>{{ phone }}</strong> to coordinate your prize delivery.
            </p>
            <div style="text-align: center;">
              <a href="{{ profile_url }}" class="btn-primary">View Won Prize in Dashboard &rarr;</a>
            </div>"""
        ),
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
