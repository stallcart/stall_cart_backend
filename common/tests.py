from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from common.models import SiteSettings
from PIL import Image
import io
import os

class SiteSettingsBrandingTests(TestCase):
    def setUp(self):
        # Clean up any existing singleton instance so tests run in isolation
        SiteSettings.objects.all().delete()

    def test_logo_auto_optimization_on_save(self):
        """Verify that when a large logo image is uploaded, it is automatically compressed and resized to fit layout limits."""
        # Create a large 800x800 red image with transparent channel in memory
        large_image_data = io.BytesIO()
        img = Image.new('RGBA', (800, 800), (255, 0, 0, 255))
        img.save(large_image_data, format='PNG')
        large_image_data.seek(0)

        # Build SimpleUploadedFile
        uploaded_logo = SimpleUploadedFile(
            name="large_logo.png",
            content=large_image_data.read(),
            content_type="image/png"
        )

        # Create settings record
        settings = SiteSettings.objects.create(
            site_name="Test Shop",
            logo_primary=uploaded_logo
        )

        # Verify that the image file exists on disk
        self.assertTrue(settings.logo_primary)
        logo_path = settings.logo_primary.path
        self.assertTrue(os.path.exists(logo_path))

        # Open the saved image from disk and verify its dimensions are constrained
        saved_img = Image.open(logo_path)
        self.assertLessEqual(saved_img.width, 400)
        self.assertLessEqual(saved_img.height, 120)
        # Ensure it maintains transparency mode
        self.assertEqual(saved_img.mode, 'RGBA')

        # Clean up files created during test
        if os.path.exists(logo_path):
            os.remove(logo_path)


from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest import mock

User = get_user_model()

class FCMNotificationTests(TestCase):
    def setUp(self):
        self.phone = "9876543210"
        self.user = User.objects.create_user(
            phone=self.phone,
            password="testpassword123",
            full_name="Test FCM User"
        )
        self.client.login(phone=self.phone, password="testpassword123")
        self.register_url = reverse('common:fcm_register')

    @mock.patch('common.views.notify_login_welcome')
    def test_welcome_notification_only_sent_once_per_session(self, mock_notify):
        mock_notify.return_value = True

        payload = {
            'token': 'test-fcm-token-12345678901234567890',
            'device_id': 'device-1',
            'device_name': 'Test Browser'
        }
        # First registration in session
        response = self.client.post(
            self.register_url,
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(mock_notify.call_count, 1)
        mock_notify.assert_called_once_with(self.user, 'test-fcm-token-12345678901234567890')

        # Reset mock
        mock_notify.reset_mock()

        # Second registration in the same session (simulates navigation/re-registration)
        response2 = self.client.post(
            self.register_url,
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 200)
        # Should NOT be called again because of session key check
        self.assertEqual(mock_notify.call_count, 0)

        # Clear session/logout and login again to verify it gets called again on a new session
        self.client.logout()
        self.client.login(phone=self.phone, password="testpassword123")
        
        mock_notify.reset_mock()
        response3 = self.client.post(
            self.register_url,
            data=payload,
            content_type='application/json'
        )
        # Note: update_or_create won't create a new record now (so status_code 200),
        # but since it's a new session, it should notify again.
        self.assertEqual(response3.status_code, 200)
        self.assertEqual(mock_notify.call_count, 1)


from django.contrib.admin.sites import AdminSite
from common.admin import SiteSettingsAdmin

class SiteSettingsAdminPermissionsTests(TestCase):
    def setUp(self):
        SiteSettings.objects.all().delete()
        self.settings = SiteSettings.objects.create(site_name="Test Shop")
        self.site = AdminSite()
        self.admin = SiteSettingsAdmin(SiteSettings, self.site)
        self.superuser = User.objects.create_superuser(phone="9999999990", password="pass", full_name="Superuser")
        self.admin_user = User.objects.create_user(phone="9999999991", password="pass", full_name="Admin", role="admin")
        self.staff_user = User.objects.create_user(phone="9999999992", password="pass", full_name="Staff", role="staff")

    def test_superuser_sees_all_fields(self):
        request = mock.Mock()
        request.user = self.superuser
        fieldsets = self.admin.get_fieldsets(request, self.settings)
        fields = []
        for name, opts in fieldsets:
            fields.extend(opts.get('fields', []))
        self.assertIn('enable_background_jobs', fields)
        self.assertIn('jobs_status_control', fields)

        list_display = self.admin.get_list_display(request)
        self.assertIn('enable_background_jobs', list_display)

    def test_admin_user_sees_all_fields(self):
        request = mock.Mock()
        request.user = self.admin_user
        fieldsets = self.admin.get_fieldsets(request, self.settings)
        fields = []
        for name, opts in fieldsets:
            fields.extend(opts.get('fields', []))
        self.assertIn('enable_background_jobs', fields)
        self.assertIn('jobs_status_control', fields)

        list_display = self.admin.get_list_display(request)
        self.assertIn('enable_background_jobs', list_display)

    def test_staff_user_does_not_see_job_fields(self):
        request = mock.Mock()
        request.user = self.staff_user
        fieldsets = self.admin.get_fieldsets(request, self.settings)
        fields = []
        for name, opts in fieldsets:
            fields.extend(opts.get('fields', []))
        self.assertNotIn('enable_background_jobs', fields)
        self.assertNotIn('jobs_status_control', fields)

        list_display = self.admin.get_list_display(request)
        self.assertNotIn('enable_background_jobs', list_display)

    def test_toggle_jobs_view_permissions(self):
        # 1. Staff user gets blocked from toggle_jobs_view url
        request = mock.Mock()
        request.user = self.staff_user
        request.META = {'HTTP_REFERER': '/admin/'}
        # mock messages framework
        with mock.patch('django.contrib.messages.error') as mock_error:
            response = self.admin.toggle_jobs_view(request)
            self.assertEqual(response.status_code, 302)
            mock_error.assert_called_once()
            self.assertTrue(self.settings.enable_background_jobs)  # remains unchanged

        # 2. Superuser is allowed to toggle background jobs
        request.user = self.superuser
        with mock.patch('django.contrib.messages.success') as mock_success:
            response = self.admin.toggle_jobs_view(request)
            self.assertEqual(response.status_code, 302)
            mock_success.assert_called_once()
            self.settings.refresh_from_db()
            self.assertFalse(self.settings.enable_background_jobs)  # toggled from True to False


class SupportEnquiryTests(TestCase):
    def setUp(self):
        self.submit_url = reverse('common:submit_support_enquiry')

    def test_model_creation(self):
        """Verify that SupportEnquiry is correctly created in DB"""
        from common.models import SupportEnquiry
        enquiry = SupportEnquiry.objects.create(
            name="Alice",
            phone="9876543210",
            message="Need help with returns"
        )
        self.assertEqual(enquiry.name, "Alice")
        self.assertEqual(enquiry.phone, "9876543210")
        self.assertEqual(enquiry.message, "Need help with returns")
        self.assertFalse(enquiry.is_resolved)

    def test_ajax_submission_success(self):
        """Verify AJAX view saves and returns success with valid data"""
        from common.models import SupportEnquiry
        payload = {
            'name': 'Bob',
            'phone': '9876543210',
            'message': 'Where is my order?'
        }
        response = self.client.post(
            self.submit_url,
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('ok'))
        
        # Verify db insert
        enquiry = SupportEnquiry.objects.latest('id')
        self.assertEqual(enquiry.name, 'Bob')
        self.assertEqual(enquiry.phone, '9876543210')
        self.assertEqual(enquiry.message, 'Where is my order?')

    def test_ajax_submission_missing_phone(self):
        """Verify request fails when phone is missing"""
        payload = {
            'name': 'Bob',
            'message': 'No phone number'
        }
        response = self.client.post(
            self.submit_url,
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('required', response.json().get('error', ''))

    def test_ajax_submission_invalid_phone(self):
        """Verify request fails when phone digits are too short or long"""
        payload = {
            'name': 'Bob',
            'phone': '123',
            'message': 'Short phone'
        }
        response = self.client.post(
            self.submit_url,
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('valid', response.json().get('error', ''))

    def test_ajax_submission_logged_in_prefill(self):
        """Verify that when a user is logged in, name/phone are prefilled from user object"""
        from django.contrib.auth import get_user_model
        from common.models import SupportEnquiry
        User = get_user_model()
        user = User.objects.create_user(
            phone="9998887776",
            password="testpassword123",
            full_name="LoggedIn Bob"
        )
        self.client.login(phone="9998887776", password="testpassword123")
        
        payload = {
            'message': 'Enquiry from logged in user'
        }
        response = self.client.post(
            self.submit_url,
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify db insert populated with logged in user phone/name
        enquiry = SupportEnquiry.objects.latest('id')
        self.assertEqual(enquiry.name, 'LoggedIn Bob')
        self.assertEqual(enquiry.phone, '9998887776')
        self.assertEqual(enquiry.message, 'Enquiry from logged in user')

    def test_resolve_enquiry_permissions(self):
        """Verify resolve endpoint requires staff/superuser permissions"""
        from common.models import SupportEnquiry
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        enquiry = SupportEnquiry.objects.create(
            name="Alice",
            phone="9876543210",
            message="Support needed"
        )
        
        resolve_url = reverse('common:resolve_support_enquiry', kwargs={'enquiry_id': enquiry.id})
        
        # 1. Unauthenticated -> 302 redirect
        response = self.client.post(resolve_url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 302)
        
        # 2. Logged in customer -> 403 Forbidden
        customer = User.objects.create_user(phone="9990001111", password="pass", role="customer")
        self.client.login(phone="9990001111", password="pass")
        response = self.client.post(resolve_url, data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 403)
        
        # 3. Logged in staff -> 200 OK
        staff = User.objects.create_user(phone="9990002222", password="pass", role="staff")
        self.client.login(phone="9990002222", password="pass")
        response = self.client.post(resolve_url, data='{"notes": "Done"}', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        enquiry.refresh_from_db()
        self.assertTrue(enquiry.is_resolved)
        self.assertEqual(enquiry.resolved_notes, 'Done')

    def test_custom_email_backend_reply_to(self):
        """Verify that StallCartEmailBackend automatically adds Reply-To header if absent"""
        from django.core.mail import EmailMessage
        from common.email_backend import StallCartEmailBackend
        
        # Test the list modification logic directly
        backend = StallCartEmailBackend(fail_silently=True)
        msg1 = EmailMessage('Subject 1', 'Body 1', 'from@test.com', ['to@test.com'])
        msg2 = EmailMessage('Subject 2', 'Body 2', 'from@test.com', ['to@test.com'], reply_to=['custom@test.com'])
        
        try:
            backend.send_messages([msg1, msg2])
        except Exception:
            # We catch connection errors since there is no running SMTP server during test,
            # but we verify that the headers were modified successfully before connection.
            pass
            
        self.assertEqual(msg1.reply_to, ['stallcart.in@gmail.com'])
        self.assertEqual(msg2.reply_to, ['custom@test.com'])

    def test_send_dynamic_email_includes_support_info(self):
        """Verify that send_dynamic_email appends the support contact footer to the email body"""
        from django.core import mail
        from common.email_service import send_dynamic_email
        from common.models import SiteSettings
        
        # Ensure SiteSettings exists
        settings_obj = SiteSettings.get_singleton()
        settings_obj.contact_phone = "+91 9999999999"
        settings_obj.contact_email = "customsupport@stallcart.in"
        settings_obj.save()
        
        # Send dynamic email
        send_dynamic_email('registration_email_otp', ['testuser@example.com'], {'otp': '998877'})
        
        # Check outbox
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("+91 9999999999", sent_email.body)
        self.assertIn("customsupport@stallcart.in", sent_email.body)
        self.assertIn("Need Support?", sent_email.body)


from common.models import Campaign, CampaignPrize, CampaignParticipant, CampaignWinner
from django.utils import timezone
from datetime import timedelta

class CampaignAndLuckyDrawTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.campaign = Campaign.objects.create(
            title="Dandiya Mahotsav Lucky Draw 2026",
            slug="dandiya-2026",
            badge_text="🔥 Dandiya Special",
            start_datetime=self.now - timedelta(hours=1),
            end_datetime=self.now + timedelta(days=2),
            target_registrations=500,
            status='active',
            is_active=True,
            show_on_homepage=True,
            show_on_register_page=True,
        )
        self.prize1 = CampaignPrize.objects.create(
            campaign=self.campaign,
            rank=1,
            title="1st Prize: Smart 4K TV",
            approx_value=25000,
            display_order=1
        )
        self.prize2 = CampaignPrize.objects.create(
            campaign=self.campaign,
            rank=2,
            title="2nd Prize: 5G Smartphone",
            approx_value=15000,
            display_order=2
        )
        self.prize3 = CampaignPrize.objects.create(
            campaign=self.campaign,
            rank=3,
            title="3rd Prize: Smartwatch",
            approx_value=5000,
            display_order=3
        )

        self.users = []
        for i in range(5):
            u = User.objects.create_user(
                phone=f"987650000{i}",
                email=f"contestuser{i}@example.com",
                password="password123",
                full_name=f"Contest User {i}"
            )
            self.users.append(u)

    def test_campaign_is_live_and_active(self):
        """Verify active campaign is detected as live"""
        self.assertTrue(self.campaign.is_live)
        self.assertEqual(Campaign.get_active_campaign(), self.campaign)

    def test_campaign_deactivation_switches_off_completely(self):
        """Verify that setting is_active=False disables campaign everywhere"""
        self.campaign.is_active = False
        self.campaign.save()

        self.assertFalse(self.campaign.is_live)
        self.assertIsNone(Campaign.get_active_campaign())

        # Public detail view should redirect
        response = self.client.get(reverse('common:campaign_detail', args=[self.campaign.slug]))
        self.assertEqual(response.status_code, 302)

    def test_campaign_auto_enroll_user(self):
        """Verify new users are automatically enrolled with unique tickets"""
        p1 = Campaign.auto_enroll_user(self.users[0])
        self.assertIsNotNone(p1)
        self.assertTrue(p1.ticket_number.startswith('DANDIY'))
        self.assertEqual(p1.campaign, self.campaign)
        self.assertEqual(p1.user, self.users[0])

        # Enrolling same user again returns existing participant
        p1_again = Campaign.auto_enroll_user(self.users[0])
        self.assertEqual(p1.id, p1_again.id)

        # Enrolling next user creates distinct ticket
        p2 = Campaign.auto_enroll_user(self.users[1])
        self.assertNotEqual(p1.ticket_number, p2.ticket_number)

    def test_auto_enroll_disabled_when_campaign_inactive(self):
        """When campaign is inactive, auto_enroll_user returns None"""
        self.campaign.is_active = False
        self.campaign.save()

        p = Campaign.auto_enroll_user(self.users[0])
        self.assertIsNone(p)

    def test_lucky_draw_winner_selection(self):
        """Verify admin lucky draw picks distinct winners for 1st, 2nd, 3rd prizes"""
        # Enroll all 5 users
        for u in self.users:
            Campaign.auto_enroll_user(u)

        self.assertEqual(self.campaign.participants_count, 5)

        # Log in as superuser
        admin_user = User.objects.create_superuser(
            phone="9999999999", email="admin@test.com", password="adminpassword"
        )
        self.client.login(phone="9999999999", password="adminpassword")

        draw_url = reverse('admin:common_campaign_run_lucky_draw', args=[self.campaign.pk])
        
        # GET draw page
        get_res = self.client.get(draw_url)
        self.assertEqual(get_res.status_code, 200)

        # POST execute draw
        post_res = self.client.post(draw_url, {'execute_draw': '1'}, follow=True)
        self.assertEqual(post_res.status_code, 200)

        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, 'winners_declared')

        # Check winners
        winners = list(self.campaign.winners.all().order_by('prize__rank'))
        self.assertEqual(len(winners), 3)

        winner_user_ids = [w.user_id for w in winners]
        # Ensure all 3 winners are distinct
        self.assertEqual(len(set(winner_user_ids)), 3)

        # Check rank mapping
        self.assertEqual(winners[0].prize.rank, 1)
        self.assertEqual(winners[1].prize.rank, 2)
        self.assertEqual(winners[2].prize.rank, 3)

        # Public campaign page now shows winners
        public_res = self.client.get(reverse('common:campaign_detail', args=[self.campaign.slug]))
        self.assertEqual(public_res.status_code, 200)
        self.assertIn("Lucky Draw Winners Announced!", public_res.content.decode('utf-8'))

    def test_exact_winner_count_strictly_matches_configured_prizes(self):
        """Verify winner count is EXACTLY equal to configured prizes (neither more nor less)"""
        from common.campaign_service import execute_campaign_lucky_draw
        
        # Test 1: 3 Prizes with 10 Participants -> EXACTLY 3 winners
        extra_users = [
            User.objects.create_user(phone=f"980000000{i}", email=f"extra{i}@test.com", password="pass")
            for i in range(5)
        ]
        all_users = self.users + extra_users
        for u in all_users:
            Campaign.auto_enroll_user(u)

        self.assertEqual(self.campaign.participants.count(), 10)
        self.assertEqual(self.campaign.prizes.count(), 3)

        success, winners, err = execute_campaign_lucky_draw(self.campaign)
        self.assertTrue(success)
        self.assertEqual(len(winners), 3)  # EXACTLY 3, NOT MORE, NOT LESS
        self.assertEqual(self.campaign.winners.count(), 3)
        
        # Ensure 3 distinct users
        winner_user_ids = {w.user_id for w in winners}
        self.assertEqual(len(winner_user_ids), 3)

    def test_exact_winner_count_for_custom_5_prizes(self):
        """Verify that when Admin configures 5 prizes, EXACTLY 5 winners are chosen"""
        from common.campaign_service import execute_campaign_lucky_draw
        
        # Add 4th and 5th prizes
        CampaignPrize.objects.create(campaign=self.campaign, rank=4, title="4th Prize: Bluetooth Speaker", approx_value=2500)
        CampaignPrize.objects.create(campaign=self.campaign, rank=5, title="5th Prize: StallCart Gift Card", approx_value=1000)

        self.assertEqual(self.campaign.prizes.count(), 5)

        # Enroll 12 users
        extra_users = [
            User.objects.create_user(phone=f"970000000{i}", email=f"contestant{i}@test.com", password="pass")
            for i in range(7)
        ]
        for u in (self.users + extra_users):
            Campaign.auto_enroll_user(u)

        success, winners, err = execute_campaign_lucky_draw(self.campaign)
        self.assertTrue(success)
        self.assertEqual(len(winners), 5)  # EXACTLY 5 WINNERS
        self.assertEqual(self.campaign.winners.count(), 5)
        
        # Check all 5 winners are distinct users
        self.assertEqual(len({w.user_id for w in winners}), 5)

    def test_insufficient_candidates_prevents_draw_execution(self):
        """If eligible participants < configured prizes, draw must NOT run and 0 winners created"""
        from common.campaign_service import execute_campaign_lucky_draw
        
        # Only 2 users enrolled for 3 prizes
        Campaign.auto_enroll_user(self.users[0])
        Campaign.auto_enroll_user(self.users[1])

        self.assertEqual(self.campaign.participants.count(), 2)
        self.assertEqual(self.campaign.prizes.count(), 3)

        success, winners, err = execute_campaign_lucky_draw(self.campaign)
        self.assertFalse(success)
        self.assertEqual(len(winners), 0)
        self.assertEqual(self.campaign.winners.count(), 0)
        self.assertIn("Insufficient eligible participants", err)

    def test_prevent_duplicate_draw_runs(self):
        """Cannot re-run draw once all prizes have been awarded"""
        from common.campaign_service import execute_campaign_lucky_draw
        
        for u in self.users:
            Campaign.auto_enroll_user(u)

        # First run succeeds
        success1, winners1, err1 = execute_campaign_lucky_draw(self.campaign)
        self.assertTrue(success1)
        self.assertEqual(len(winners1), 3)

        # Second run should refuse to execute
        success2, winners2, err2 = execute_campaign_lucky_draw(self.campaign)
        self.assertFalse(success2)
        self.assertEqual(len(winners2), 0)
        self.assertIn("All configured prizes for this campaign have already been awarded", err2)
        self.assertEqual(self.campaign.winners.count(), 3)





