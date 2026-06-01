from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import AnnouncementBanner

class AnnouncementBannerTest(TestCase):
    def setUp(self):
        from common.models import _thread_locals
        _thread_locals.user = None
        self.client = Client()
        self.target_time = timezone.now() + timedelta(days=2)
        
    def test_announcement_banner_creation(self):
        banner = AnnouncementBanner.objects.create(
            title="Independence Day Sale!",
            subtitle="Great Indian Festival is here.",
            coupon_code="IND50",
            btn_text="Grab Deal",
            link_url="/items/?category=electronics",
            end_datetime=self.target_time,
            is_active=True
        )
        self.assertEqual(banner.title, "Independence Day Sale!")
        self.assertEqual(banner.coupon_code, "IND50")
        self.assertTrue(banner.is_active)
        self.assertEqual(str(banner), "Independence Day Sale! (Active: True)")

    def test_homepage_context_with_active_banner(self):
        banner = AnnouncementBanner.objects.create(
            title="Independence Day Sale!",
            subtitle="Great Indian Festival is here.",
            coupon_code="IND50",
            btn_text="Grab Deal",
            link_url="/items/?category=electronics",
            end_datetime=self.target_time,
            is_active=True
        )
        
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('announcement_banner', response.context)
        self.assertEqual(response.context['announcement_banner'].id, banner.id)
        self.assertContains(response, "Independence Day Sale!")
        self.assertContains(response, "IND50")
        self.assertContains(response, "Grab Deal")

    def test_homepage_context_with_inactive_banner(self):
        banner = AnnouncementBanner.objects.create(
            title="Inactive Sale",
            end_datetime=self.target_time,
            is_active=False
        )
        
        response = self.client.get(reverse('shop:home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('announcement_banner', response.context)
        self.assertIsNone(response.context['announcement_banner'])
        self.assertNotContains(response, "Inactive Sale")
