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
    }
}

def send_dynamic_email(template_name: str, recipient_list: list, context_data: dict) -> bool:
    """
    Sends an email using templates stored dynamically in the EmailTemplate model.
    Auto-populates templates if not found in the DB.
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
        
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'StallCart <ad4b11001@smtp-brevo.com>')
        
        send_mail(
            subject=rendered_subject,
            message=rendered_body,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Successfully sent dynamic email '{template_name}' to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Failed to send dynamic email '{template_name}' to {recipient_list}: {e}", exc_info=True)
        return False
