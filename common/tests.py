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
