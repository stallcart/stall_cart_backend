from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from .models import User, OTPRequest

class OTPRequestTests(TestCase):
    def setUp(self):
        self.phone = "9876543210"
        self.user = User.objects.create_user(
            phone=self.phone,
            password="testpassword123",
            full_name="Test User"
        )

    def test_create_otp_success(self):
        otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'change_password')
        self.assertIsNone(err)
        self.assertIsNotNone(otp_req)
        self.assertEqual(len(otp_req.otp), 6)
        self.assertEqual(otp_req.phone, self.phone)
        self.assertFalse(otp_req.is_expired())

    def test_daily_rate_limit(self):
        # Generate 5 OTP requests
        for i in range(5):
            otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'forgot_password')
            self.assertIsNone(err)
            self.assertIsNotNone(otp_req)

        # 6th request should fail
        otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'forgot_password')
        self.assertIsNotNone(err)
        self.assertIn("exceeded the limit of 5 SMS OTP requests per day", err)
        self.assertIsNone(otp_req)

    def test_custom_daily_rate_limit(self):
        from common.models import SiteSettings
        site_settings = SiteSettings.get_singleton()
        site_settings.daily_sms_otp_limit = 3
        site_settings.daily_email_otp_limit = 3
        site_settings.save()

        # Generate 3 OTP requests
        for i in range(3):
            otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'forgot_password')
            self.assertIsNone(err)
            self.assertIsNotNone(otp_req)

        # 4th request should fail
        otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'forgot_password')
        self.assertIsNotNone(err)
        self.assertIn("exceeded the limit of 3 SMS OTP requests per day", err)
        self.assertIsNone(otp_req)

    def test_rolling_rate_limit(self):
        # Generate 5 OTP requests, but set 3 of them to 25 hours ago
        for i in range(3):
            otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'forgot_password')
            otp_req.created_at = timezone.now() - timedelta(hours=25)
            otp_req.save()

        # We can still make 5 more requests (as only those 5 will be in the last 24 hours)
        for i in range(5):
            otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'forgot_password')
            self.assertIsNone(err)

        # 6th active request in the rolling 24 hour period should fail
        otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'forgot_password')
        self.assertIsNotNone(err)
        self.assertIsNone(otp_req)

    def test_otp_expiry(self):
        otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'change_password', expiry_minutes=-1)
        self.assertTrue(otp_req.is_expired())

    def test_custom_otp_expiry_from_settings(self):
        from common.models import SiteSettings
        site_settings = SiteSettings.get_singleton()
        site_settings.otp_expiry_minutes = 25
        site_settings.save()

        otp_req, err = OTPRequest.check_and_create_otp(self.phone, 'change_password')
        self.assertIsNone(err)
        self.assertIsNotNone(otp_req)
        
        # Checking if expires_at is approximately 25 minutes from now
        from django.utils import timezone
        from datetime import timedelta
        diff = otp_req.expires_at - timezone.now()
        # The difference should be around 25 minutes (e.g. between 24 and 26 minutes)
        self.assertTrue(timedelta(minutes=24) <= diff <= timedelta(minutes=26))



from django.urls import reverse
import json

class ProfileUpdateOTPTests(TestCase):
    def setUp(self):
        self.phone = "9876543210"
        self.user = User.objects.create_user(
            phone=self.phone,
            password="testpassword123",
            full_name="Test User",
            email="test@example.com"
        )
        self.client.login(phone=self.phone, password="testpassword123")
        
        from unittest.mock import patch
        self.sms_patcher = patch('common.sms_service.send_sms_via_2factor')
        self.mock_send_sms = self.sms_patcher.start()
        self.mock_send_sms.return_value = True

    def tearDown(self):
        self.sms_patcher.stop()

    def test_profile_update_trigger_otp(self):
        """Requesting to change email or phone triggers OTP send."""
        url = reverse('accounts:profile')
        payload = {
            "action": "send_profile_update_otps",
            "email": "newemail@example.com",
            "phone": "9998887776"
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['email_sent'])
        self.assertTrue(data['phone_sent'])

        # Verify OTP requests created
        email_otp = OTPRequest.objects.filter(phone="newemail@example.com", purpose="update_email").first()
        phone_otp = OTPRequest.objects.filter(phone="9998887776", purpose="update_phone").first()
        self.assertIsNotNone(email_otp)
        self.assertIsNotNone(phone_otp)

    def test_profile_update_verification_failure(self):
        """Updating email/phone fails if incorrect/missing OTP is provided."""
        url = reverse('accounts:profile')
        payload = {
            "action": "update_profile",
            "full_name": "Test User Updated",
            "email": "newemail@example.com",
            "phone": "9998887776",
            "email_otp": "000000",
            "phone_otp": "000000"
        }
        # First trigger OTP sending to create request objects in DB
        self.client.post(
            url,
            data=json.dumps({"action": "send_profile_update_otps", "email": "newemail@example.com", "phone": "9998887776"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')

    def test_profile_update_verification_success(self):
        """Updating email/phone succeeds with correct OTPs."""
        url = reverse('accounts:profile')
        # First trigger OTP sending
        self.client.post(
            url,
            data=json.dumps({"action": "send_profile_update_otps", "email": "newemail@example.com", "phone": "9998887776"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        # Retrieve generated OTPs
        email_otp = OTPRequest.objects.filter(phone="newemail@example.com", purpose="update_email").first().otp
        phone_otp = OTPRequest.objects.filter(phone="9998887776", purpose="update_phone").first().otp

        payload = {
            "action": "update_profile",
            "full_name": "Test User Updated",
            "email": "newemail@example.com",
            "phone": "9998887776",
            "email_otp": email_otp,
            "phone_otp": phone_otp
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')

        # Verify fields updated in db
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Test User Updated")
        self.assertEqual(self.user.email, "newemail@example.com")
        self.assertEqual(self.user.phone, "9998887776")

    def test_profile_update_only_email(self):
        """Updating only the email requires email OTP; phone OTP is not required."""
        url = reverse('accounts:profile')
        # Trigger sending OTP for email change only
        self.client.post(
            url,
            data=json.dumps({"action": "send_profile_update_otps", "email": "onlyemail@example.com", "phone": self.phone}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        
        email_otp = OTPRequest.objects.filter(phone="onlyemail@example.com", purpose="update_email").first().otp
        
        payload = {
            "action": "update_profile",
            "full_name": "Test User",
            "email": "onlyemail@example.com",
            "phone": self.phone,
            "email_otp": email_otp
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "onlyemail@example.com")
        self.assertEqual(self.user.phone, self.phone)

    def test_profile_update_only_phone(self):
        """Updating only the phone requires phone OTP; email OTP is not required."""
        url = reverse('accounts:profile')
        # Trigger sending OTP for phone change only
        self.client.post(
            url,
            data=json.dumps({"action": "send_profile_update_otps", "email": "test@example.com", "phone": "9991112223"}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        
        phone_otp = OTPRequest.objects.filter(phone="9991112223", purpose="update_phone").first().otp
        
        payload = {
            "action": "update_profile",
            "full_name": "Test User",
            "email": "test@example.com",
            "phone": "9991112223",
            "phone_otp": phone_otp
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "test@example.com")
        self.assertEqual(self.user.phone, "9991112223")

    def test_profile_update_name_only_no_otp(self):
        """Updating only non-restricted fields (like full_name) does not require any OTP."""
        url = reverse('accounts:profile')
        payload = {
            "action": "update_profile",
            "full_name": "Just Name Updated",
            "email": "test@example.com",
            "phone": self.phone
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Just Name Updated")
        self.assertEqual(self.user.email, "test@example.com")
        self.assertEqual(self.user.phone, self.phone)


class UserRegistrationOTPTests(TestCase):
    def setUp(self):
        self.phone = "9876543210"
        self.email = "test@example.com"
        
        from unittest.mock import patch
        self.sms_patcher = patch('common.sms_service.send_sms_via_2factor')
        self.mock_send_sms = self.sms_patcher.start()
        self.mock_send_sms.return_value = True

    def tearDown(self):
        self.sms_patcher.stop()

    def test_registration_trigger_otp(self):
        """Triggering registration OTP works successfully and creates only email OTP request in db first."""
        url = reverse('accounts:register')
        payload = {
            "action": "send_register_otps",
            "phone": "9998887776",
            "email": "newreg@example.com",
            "full_name": "New Registrant",
            "password1": "testpass123",
            "password2": "testpass123",
            "user_role": "customer"
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn("Verification OTP sent to email", data['message'])
        
        # Verify email OTPRequest exists but phone OTPRequest does not yet
        email_otp = OTPRequest.objects.filter(phone="newreg@example.com", purpose="register_email").first()
        self.assertIsNotNone(email_otp)
        phone_otp = OTPRequest.objects.filter(phone="9998887776", purpose="register_phone").first()
        self.assertIsNone(phone_otp)

        # Now verify email OTP to trigger phone OTP
        verify_payload = {
            "action": "verify_email_otp",
            "email": "newreg@example.com",
            "phone": "9998887776",
            "email_otp": email_otp.otp
        }
        verify_response = self.client.post(
            url,
            data=json.dumps(verify_payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(verify_response.status_code, 200)
        verify_data = verify_response.json()
        self.assertEqual(verify_data['status'], 'success')
        self.assertIn("Verification OTP sent to mobile", verify_data['message'])

        # Verify phone OTPRequest is now created
        phone_otp = OTPRequest.objects.filter(phone="9998887776", purpose="register_phone").first()
        self.assertIsNotNone(phone_otp)

    def test_registration_validation_fails(self):
        """Form validation failures (e.g. mismatched passwords) return 400 and form errors."""
        url = reverse('accounts:register')
        payload = {
            "action": "send_register_otps",
            "phone": "9998887776",
            "email": "newreg@example.com",
            "full_name": "New Registrant",
            "password1": "testpass123",
            "password2": "differentpass",
            "user_role": "customer"
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('errors', data)

    def test_registration_verification_success(self):
        """Registering with correct sequential steps succeeds and creates a user in db."""
        url = reverse('accounts:register')
        # 1. Trigger email OTP sending first
        self.client.post(
            url,
            data=json.dumps({
                "action": "send_register_otps",
                "phone": "9998887776",
                "email": "newreg@example.com",
                "full_name": "New Registrant",
                "password1": "testpass123",
                "password2": "testpass123",
                "user_role": "customer"
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        
        email_otp = OTPRequest.objects.filter(phone="newreg@example.com", purpose="register_email").first().otp
        
        # 2. Verify Email OTP to generate Phone OTP
        self.client.post(
            url,
            data=json.dumps({
                "action": "verify_email_otp",
                "email": "newreg@example.com",
                "phone": "9998887776",
                "email_otp": email_otp
            }),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        
        phone_otp = OTPRequest.objects.filter(phone="9998887776", purpose="register_phone").first().otp
        
        # 3. Submit final registration payload containing the Phone OTP
        payload = {
            "action": "register",
            "phone": "9998887776",
            "email": "newreg@example.com",
            "full_name": "New Registrant",
            "password1": "testpass123",
            "password2": "testpass123",
            "user_role": "customer",
            "phone_otp": phone_otp
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        
        # Verify user created
        new_user = User.objects.filter(phone="9998887776").first()
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.email, "newreg@example.com")
        self.assertEqual(new_user.full_name, "New Registrant")
        self.assertEqual(new_user.role, "customer")


class ChangePasswordOTPTests(TestCase):
    def setUp(self):
        self.phone = "9876543210"
        self.user = User.objects.create_user(
            phone=self.phone,
            password="testpassword123",
            full_name="Test User",
            email="test@example.com"
        )
        self.client.login(phone=self.phone, password="testpassword123")
        
        from unittest.mock import patch
        self.sms_patcher = patch('common.sms_service.send_sms_via_2factor')
        self.mock_send_sms = self.sms_patcher.start()
        self.mock_send_sms.return_value = True

    def tearDown(self):
        self.sms_patcher.stop()

    def test_send_change_password_otp_success(self):
        url = reverse('accounts:send_change_password_otp')
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn("OTP sent successfully to your registered mobile", data['message'])
        
        # Verify SMS OTPRequest was created for the phone
        otp_req = OTPRequest.objects.filter(phone=self.phone, purpose="change_password").first()
        self.assertIsNotNone(otp_req)
        self.mock_send_sms.assert_called_once_with(self.phone, otp_req.otp)

    def test_change_password_verify_success(self):
        # First send OTP
        self.client.post(reverse('accounts:send_change_password_otp'), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        otp_code = OTPRequest.objects.filter(phone=self.phone, purpose="change_password").first().otp
        
        # Submit password change form
        url = reverse('accounts:change_password')
        payload = {
            'old_password': 'testpassword123',
            'new_password1': 'newsecurepass123',
            'new_password2': 'newsecurepass123',
            'otp': otp_code
        }
        response = self.client.post(url, data=payload)
        self.assertEqual(response.status_code, 302) # Redirect to profile
        
        # Verify password actually changed
        self.assertTrue(self.user.check_password('testpassword123')) # Check user instance in DB
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newsecurepass123'))


from django.core import mail
from common.models import EmailTemplate
from common.email_service import send_dynamic_email

class DynamicEmailTemplateTests(TestCase):
    def setUp(self):
        # Clear the database of pre-populated templates to isolate unit tests
        EmailTemplate.objects.all().delete()
        mail.outbox.clear()
        # Clear thread-local user to prevent leakage from other tests
        from common.models import _thread_locals
        if hasattr(_thread_locals, 'user'):
            del _thread_locals.user

    def test_send_dynamic_email_creation(self):
        # 1. Test that sending a template creates the default in the DB
        self.assertFalse(EmailTemplate.objects.filter(name='registration_email_otp').exists())
        
        success = send_dynamic_email('registration_email_otp', ['test@example.com'], {'otp': '123456'})
        self.assertTrue(success)
        
        # Check that it got created in DB
        tpl = EmailTemplate.objects.filter(name='registration_email_otp').first()
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.subject, "StallCart - Registration Verification OTP")
        
        # Check that the mail is in locmem outbox with rendered content
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.subject, "StallCart - Registration Verification OTP")
        self.assertIn("123456", sent_email.body)

    def test_send_dynamic_email_customized(self):
        # Create template in DB
        EmailTemplate.objects.create(
            name='seller_verified',
            subject='Welcome Seller {{ seller_name }}!',
            body='Hello, your shop {{ shop_name }} is verified.'
        )
        
        success = send_dynamic_email('seller_verified', ['seller@example.com'], {
            'seller_name': 'John Doe',
            'shop_name': 'My Shop'
        })
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Welcome Seller John Doe!")
        self.assertEqual(mail.outbox[0].body, "Hello, your shop My Shop is verified.")


from items.models import SellerProfile

class UserManagementTests(TestCase):
    def setUp(self):
        # Create users for testing
        self.superuser = User.objects.create_superuser(phone="9999999990", password="pass", full_name="Superuser")
        self.admin_user = User.objects.create_user(phone="9999999991", password="pass", full_name="Admin", role="admin")
        self.staff_user = User.objects.create_user(phone="9999999992", password="pass", full_name="Staff", role="staff")
        self.customer_user = User.objects.create_user(phone="9999999993", password="pass", full_name="Customer", role="customer")
        
        self.target_user = User.objects.create_user(phone="8888888880", password="pass", full_name="Target Staff", role="staff")
        self.seller_user = User.objects.create_user(phone="8888888881", password="pass", full_name="Target Seller", role="seller")
        self.seller_profile = SellerProfile.objects.create(
            user=self.seller_user,
            shop_name="Test Shop",
            gst_number="27AAAAA1111A1Z1",
            is_verified=False
        )

    def test_access_restrictions(self):
        url = reverse('accounts:admin_user_management')
        
        # 1. Customer blocked
        self.client.login(phone="9999999993", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # 2. Staff blocked (only superuser/admin can manage users)
        self.client.login(phone="9999999992", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # 3. Admin user allowed
        self.client.login(phone="9999999991", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # 4. Superuser allowed
        self.client.login(phone="9999999990", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_ajax_get_user_details(self):
        self.client.login(phone="9999999990", password="pass")
        url = reverse('accounts:admin_user_management')
        
        # Test standard user details
        payload = {'action': 'get_user', 'user_id': self.target_user.id}
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['user']['full_name'], 'Target Staff')
        
        # Test seller details (with shop fields)
        payload = {'action': 'get_user', 'user_id': self.seller_user.id}
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['user']['shop_name'], 'Test Shop')
        self.assertEqual(data['user']['gst_number'], '27AAAAA1111A1Z1')

    def test_ajax_create_staff(self):
        self.client.login(phone="9999999990", password="pass")
        url = reverse('accounts:admin_user_management')
        
        # 1. Success case
        payload = {
            'action': 'create_staff',
            'full_name': 'New Staff',
            'phone': '7777777777',
            'email': 'newstaff@example.com',
            'password': 'securepassword'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        
        new_staff = User.objects.filter(phone='7777777777').first()
        self.assertIsNotNone(new_staff)
        self.assertEqual(new_staff.role, 'staff')
        self.assertTrue(new_staff.is_staff)
        
        # 2. Validation: duplicate phone
        payload['phone'] = '9999999990' # superuser phone
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)
        
        # 3. Validation: short/invalid phone
        payload['phone'] = '123'
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)

    def test_ajax_update_user(self):
        self.client.login(phone="9999999990", password="pass")
        url = reverse('accounts:admin_user_management')
        
        # 1. Update Staff credentials
        payload = {
            'action': 'update_user',
            'user_id': self.target_user.id,
            'full_name': 'Updated Target Staff',
            'phone': '8888888882',
            'email': 'updated_staff@example.com',
            'password': 'newpassword123'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.full_name, 'Updated Target Staff')
        self.assertEqual(self.target_user.phone, '8888888882')
        self.assertEqual(self.target_user.email, 'updated_staff@example.com')
        self.assertTrue(self.target_user.check_password('newpassword123'))
        
        # 2. Update Seller and SellerProfile
        payload = {
            'action': 'update_user',
            'user_id': self.seller_user.id,
            'full_name': 'Updated Owner',
            'phone': '8888888881',
            'email': 'seller@example.com',
            'shop_name': 'Updated Shop',
            'gst_number': '27BBBBB1111B1Z2',
            'is_verified': True,
            'password': '' # no change
        }
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        
        self.seller_user.refresh_from_db()
        self.seller_profile.refresh_from_db()
        self.assertEqual(self.seller_user.full_name, 'Updated Owner')
        self.assertEqual(self.seller_profile.shop_name, 'Updated Shop')
        self.assertEqual(self.seller_profile.gst_number, '27BBBBB1111B1Z2')
        self.assertTrue(self.seller_profile.is_verified)

    def test_ajax_delete_user(self):
        self.client.login(phone="9999999990", password="pass")
        url = reverse('accounts:admin_user_management')
        
        # 1. Success case
        payload = {'action': 'delete_user', 'user_id': self.target_user.id}
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(id=self.target_user.id).exists())
        
        # 2. Block self deletion
        payload = {'action': 'delete_user', 'user_id': self.superuser.id}
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)

    def test_ajax_toggle_active(self):
        self.client.login(phone="9999999990", password="pass")
        url = reverse('accounts:admin_user_management')
        
        # 1. Success case
        self.assertTrue(self.target_user.is_active)
        payload = {'action': 'toggle_active', 'user_id': self.target_user.id}
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        
        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_active)
        
        # 2. Block self deactivation
        payload = {'action': 'toggle_active', 'user_id': self.superuser.id}
        response = self.client.post(url, data=json.dumps(payload), content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 400)


class AdminBusinessDashboardTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(phone="9999999990", password="pass", full_name="Superuser", role="admin")
        self.admin_user = User.objects.create_user(phone="9999999991", password="pass", full_name="Admin", role="admin")
        self.staff_user = User.objects.create_user(phone="9999999992", password="pass", full_name="Staff", role="staff")
        self.customer_user = User.objects.create_user(phone="9999999993", password="pass", full_name="Customer", role="customer")
        self.seller_user = User.objects.create_user(phone="9999999994", password="pass", full_name="Seller", role="seller")

    def test_homepage_redirection_for_admins(self):
        url = reverse('shop:home')
        
        # 1. Unauthenticated -> 200 storefront
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'shop/home.html')
        
        # 2. Customer -> 200 storefront
        self.client.login(phone="9999999993", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # 3. Seller -> 200 storefront
        self.client.login(phone="9999999994", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # 4. Superuser -> 302 redirect to dashboard
        self.client.login(phone="9999999990", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:admin_business_dashboard'))
        
        # 5. Admin role -> 302 redirect to dashboard
        self.client.login(phone="9999999991", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:admin_business_dashboard'))

    def test_dashboard_access_restrictions(self):
        url = reverse('accounts:admin_business_dashboard')
        
        # 1. Unauthenticated -> redirect to login
        self.client.logout()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # 2. Customer -> redirect to storefront home
        self.client.login(phone="9999999993", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # 3. Staff -> redirect to storefront home
        self.client.login(phone="9999999992", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        # 4. Admin user -> 200 OK
        self.client.login(phone="9999999991", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/admin_business_dashboard.html')
        
        # 5. Superuser -> 200 OK
        self.client.login(phone="9999999990", password="pass")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_context_metrics(self):
        self.client.login(phone="9999999990", password="pass")
        url = reverse('accounts:admin_business_dashboard')
        
        # Create an order
        from orders.models import Order
        Order.objects.create(
            user=self.customer_user,
            total_amount=1250.00,
            status='delivered',
            payment_method='cod'
        )
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Verify context metrics
        self.assertEqual(response.context['total_sales'], 1250.00)
        self.assertEqual(response.context['total_orders_count'], 1)
        self.assertEqual(response.context['total_customers'], 1)
        self.assertEqual(response.context['total_sellers'], 1)
        self.assertEqual(response.context['total_staff'], 1)
        self.assertIn('daily_sales', response.context)
        self.assertEqual(len(response.context['daily_sales']), 7)

    def test_staff_seller_panel_access(self):
        # 1. Access seller dashboard as staff
        self.client.login(phone="9999999992", password="pass")
        dashboard_url = reverse('items:seller_dashboard')
        
        # Verify no seller profile exists initially
        self.assertFalse(hasattr(self.staff_user, 'seller_profile'))
        
        response = self.client.get(dashboard_url)
        # Should auto-create profile and return 200 OK
        self.assertEqual(response.status_code, 200)
        self.staff_user.refresh_from_db()
        self.assertTrue(hasattr(self.staff_user, 'seller_profile'))
        self.assertTrue(self.staff_user.seller_profile.is_verified)
        
        # 2. Access seller orders view as staff
        orders_url = reverse('orders:seller_orders')
        response = self.client.get(orders_url)
        self.assertEqual(response.status_code, 200)

        # 3. Access unified dashboard as staff (without seller_profile initially)
        # Let's delete the seller profile first to test auto-creation on the unified dashboard decorator
        self.staff_user.seller_profile.delete()
        self.staff_user.refresh_from_db()
        self.assertFalse(hasattr(self.staff_user, 'seller_profile'))

        unified_url = reverse('items:admin_dashboard')
        response = self.client.get(unified_url)
        self.assertEqual(response.status_code, 200)
        self.staff_user.refresh_from_db()
        self.assertTrue(hasattr(self.staff_user, 'seller_profile'))

        # 4. Access product creation view as staff and ensure is_superuser context parameter is True
        product_create_url = reverse('items:product_create')
        response = self.client.get(product_create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_superuser'])


class SellerPANVerificationTests(TestCase):
    def setUp(self):
        from unittest.mock import patch
        self.sms_patcher = patch('common.sms_service.send_sms_via_2factor')
        self.mock_send_sms = self.sms_patcher.start()
        self.mock_send_sms.return_value = True

        self.email_patcher = patch('common.email_service.send_dynamic_email')
        self.mock_send_email = self.email_patcher.start()
        self.mock_send_email.return_value = True

    def tearDown(self):
        self.sms_patcher.stop()
        self.email_patcher.stop()

    def test_seller_registration_requires_pan(self):
        """UserRegistrationForm requires PAN for sellers, validates format and uniqueness."""
        from accounts.forms import UserRegistrationForm
        
        # 1. Missing PAN for seller
        form_data = {
            'phone': '9876543210',
            'email': 'seller@example.com',
            'full_name': 'Test Seller',
            'user_role': 'seller',
            'shop_name': 'My Shop',
            'password1': 'pass123',
            'password2': 'pass123',
            'pan_number': ''
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('pan_number', form.errors)

        # 2. Invalid PAN format
        form_data['pan_number'] = 'INVALID123'
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('pan_number', form.errors)

        # 3. Valid PAN format
        form_data['pan_number'] = 'ABCDE1234F'
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())

        # Save to test uniqueness
        user = form.save(commit=False)
        user.role = 'seller'
        user.save()
        from items.models import SellerProfile
        SellerProfile.objects.create(
            user=user,
            shop_name=form.cleaned_data['shop_name'],
            pan_number=form.cleaned_data['pan_number'],
            phone=user.phone
        )

        # 4. Duplicate PAN
        form_data2 = {
            'phone': '9876543211',
            'email': 'seller2@example.com',
            'full_name': 'Test Seller 2',
            'user_role': 'seller',
            'shop_name': 'My Shop 2',
            'password1': 'pass123',
            'password2': 'pass123',
            'pan_number': 'ABCDE1234F' # duplicate
        }
        form2 = UserRegistrationForm(data=form_data2)
        self.assertFalse(form2.is_valid())
        self.assertIn('pan_number', form2.errors)

    def test_seller_profile_update_resets_verification(self):
        """Updating PAN details resets verification status and sends email notification."""
        # Create an active admin with email to receive notification
        User.objects.create_user(phone="9999999990", password="pass", role="admin", email="admin@example.com")
        
        user = User.objects.create_user(phone="9998887771", password="pass", role="seller")
        from items.models import SellerProfile
        profile = SellerProfile.objects.create(
            user=user,
            shop_name="Unique Shop",
            pan_number="ABCDE1234F",
            pan_verification_status="verified",
            is_verified=True
        )
        self.assertTrue(profile.is_verified)

        # Update PAN number
        profile.pan_number = "WXYZR9876Q"
        profile.save()

        profile.refresh_from_db()
        self.assertFalse(profile.is_verified)
        self.assertEqual(profile.pan_verification_status, 'pending')
        # Check that admin notification email was triggered
        self.assertTrue(self.mock_send_email.called)

    def test_admin_verify_and_reject_actions(self):
        """Admin actions correctly update status and triggers notifications."""
        admin = User.objects.create_superuser(phone="9999999999", password="pass", role="admin")
        self.client.login(phone="9999999999", password="pass")

        seller_user = User.objects.create_user(phone="9998887772", password="pass", role="seller", email="seller@example.com")
        from items.models import SellerProfile
        profile = SellerProfile.objects.create(
            user=seller_user,
            shop_name="Verification Shop",
            pan_number="ABCDE1234F",
            pan_verification_status="pending",
            is_verified=False
        )

        # 1. Verify seller
        action_url = reverse('items:verify_seller_action', kwargs={'seller_id': profile.id})
        response = self.client.post(
            action_url,
            data=json.dumps({'action': 'verify'}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertTrue(profile.is_verified)
        self.assertEqual(profile.pan_verification_status, 'verified')

        # 2. Reject seller
        response = self.client.post(
            action_url,
            data=json.dumps({'action': 'reject', 'reason': 'Documents are blurry'}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertFalse(profile.is_verified)
        self.assertEqual(profile.pan_verification_status, 'rejected')
        self.assertEqual(profile.pan_rejection_reason, 'Documents are blurry')


from django.test import RequestFactory, SimpleTestCase
from django.http import HttpResponse, JsonResponse
from stall_cart.middleware import AjaxExceptionMiddleware

class AjaxExceptionMiddlewareTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_ajax_unhandled_exception_returns_json_500(self):
        # A view that raises an error
        def view_raising_error(request):
            raise ValueError("Test database error")

        middleware = AjaxExceptionMiddleware(view_raising_error)
        
        # Non-AJAX request raises exception as usual
        request_non_ajax = self.factory.get('/some-url/')
        with self.assertRaises(ValueError):
            middleware(request_non_ajax)

        # AJAX request intercepts exception and returns JsonResponse with status 500
        request_ajax = self.factory.get('/some-url/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        response = middleware(request_ajax)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 500)
        
        import json
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Something went wrong on our server. Please try again later.')

    def test_ajax_explicit_500_html_returns_json_500(self):
        # A view that returns explicit 500 HTML page
        def view_500_html(request):
            return HttpResponse("<html><body>Server Error</body></html>", status=500, content_type="text/html")

        middleware = AjaxExceptionMiddleware(view_500_html)
        
        # Non-AJAX gets HTML 500
        request_non_ajax = self.factory.get('/some-url/')
        response = middleware(request_non_ajax)
        self.assertEqual(response.status_code, 500)
        self.assertIn('text/html', response.headers['Content-Type'])

        # AJAX gets JsonResponse 500
        request_ajax = self.factory.get('/some-url/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        response = middleware(request_ajax)
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 500)
        
        import json
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertEqual(data['message'], 'Something went wrong on our server. Please try again later.')


class AdminUserManagementPaginationTests(TestCase):
    def setUp(self):
        from django.test import Client
        from common.models import _thread_locals
        _thread_locals.user = None
        
        self.client = Client()
        self.superuser = User.objects.create_superuser(phone="9999999990", password="pass", role="admin")
        
        # Create 15 staff members, 15 sellers, and 15 customers
        for i in range(15):
            User.objects.create_user(phone=f"90000000{i:02d}", password="pass", role="staff", full_name=f"Staff {i}")
            
            seller = User.objects.create_user(phone=f"91000000{i:02d}", password="pass", role="seller", full_name=f"Seller {i}")
            from items.models import SellerProfile
            SellerProfile.objects.create(user=seller, shop_name=f"Shop {i}", is_verified=True)
            
            User.objects.create_user(phone=f"92000000{i:02d}", password="pass", role="customer", full_name=f"Customer {i}")

    def test_pagination_independent_pages(self):
        self.client.login(phone="9999999990", password="pass")
        url = reverse('accounts:admin_user_management')
        
        # Test default first page (page size 10)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Context lists should only contain 10 items
        self.assertEqual(len(response.context['staff_list']), 10)
        self.assertEqual(len(response.context['seller_list']), 10)
        self.assertEqual(len(response.context['customer_list']), 10)
        
        # Tab counts should show the total count (15 staff, 15 sellers, 15 customers)
        self.assertEqual(response.context['staff_list'].paginator.count, 15)
        self.assertEqual(response.context['seller_list'].paginator.count, 15)
        self.assertEqual(response.context['customer_list'].paginator.count, 15)
        
        # Request second page of staff
        response = self.client.get(f"{url}?staff_page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['staff_list']), 5)
        self.assertEqual(len(response.context['seller_list']), 10) # seller is still page 1
        
        # Request second page of seller and customer
        response = self.client.get(f"{url}?seller_page=2&customer_page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['staff_list']), 10) # staff resets to default page 1 or keeps page 1
        self.assertEqual(len(response.context['seller_list']), 5)
        self.assertEqual(len(response.context['customer_list']), 5)

