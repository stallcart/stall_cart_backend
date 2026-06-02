from django.db import migrations

def populate_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('common', 'EmailTemplate')
    
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
        }
    }
    
    for name, data in DEFAULT_TEMPLATES.items():
        EmailTemplate.objects.get_or_create(
            name=name,
            defaults={
                'subject': data['subject'],
                'body': data['body'],
                'description': data['description']
            }
        )

def remove_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('common', 'EmailTemplate')
    EmailTemplate.objects.filter(name__in=[
        'registration_email_otp',
        'update_email_otp',
        'change_password_otp',
        'forgot_password_otp',
        'order_status_update',
        'seller_verified',
        'admin_notify_verification'
    ]).delete()

class Migration(migrations.Migration):

    dependencies = [
        ('common', '0008_sitesettings_daily_otp_limit'),
    ]

    operations = [
        migrations.RunPython(populate_templates, remove_templates),
    ]
