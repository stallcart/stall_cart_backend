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
        """Triggering registration OTP works successfully and creates OTP requests in db."""
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
        
        # Verify OTPRequest instances exist
        phone_otp = OTPRequest.objects.filter(phone="9998887776", purpose="register_phone").first()
        self.assertIsNotNone(phone_otp)
        email_otp = OTPRequest.objects.filter(phone="newreg@example.com", purpose="register_email").first()
        self.assertIsNotNone(email_otp)

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
        """Registering with correct OTPs succeeds and creates a user in db."""
        url = reverse('accounts:register')
        # Trigger sending first
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
        
        phone_otp = OTPRequest.objects.filter(phone="9998887776", purpose="register_phone").first().otp
        email_otp = OTPRequest.objects.filter(phone="newreg@example.com", purpose="register_email").first().otp
        
        payload = {
            "action": "register",
            "phone": "9998887776",
            "email": "newreg@example.com",
            "full_name": "New Registrant",
            "password1": "testpass123",
            "password2": "testpass123",
            "user_role": "customer",
            "phone_otp": phone_otp,
            "email_otp": email_otp
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


