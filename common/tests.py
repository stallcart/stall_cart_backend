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
