from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Address
from delivery.delivery_services import repair_address
from unittest.mock import MagicMock

User = get_user_model()

class RepairAddressTests(TestCase):
    def test_strip_whitespace(self):
        addr = {
            "name": "  John Doe  ",
            "city": " Varanasi ",
            "state": " Uttar Pradesh ",
            "postal_code": " 221005 ",
            "phone": " 9999999999 "
        }
        repaired = repair_address(addr)
        self.assertEqual(repaired["name"], "John Doe")
        self.assertEqual(repaired["city"], "Varanasi")
        self.assertEqual(repaired["state"], "Uttar Pradesh")
        self.assertEqual(repaired["postal_code"], "221005")
        self.assertEqual(repaired["phone"], "9999999999")

    def test_state_pincode_contamination_hyphen(self):
        addr = {
            "state": "Uttar Pradesh - 221005",
            "postal_code": ""
        }
        repaired = repair_address(addr)
        self.assertEqual(repaired["state"], "Uttar Pradesh")
        self.assertEqual(repaired["postal_code"], "221005")

    def test_state_pincode_contamination_endash(self):
        addr = {
            "state": "UP – 221001",
            "postal_code": ""
        }
        repaired = repair_address(addr)
        self.assertEqual(repaired["state"], "UP")
        self.assertEqual(repaired["postal_code"], "221001")

    def test_pincode_extraction_from_address_lines(self):
        addr = {
            "address_line1": "Varanasi, Uttar Pradesh 221005",
            "postal_code": ""
        }
        repaired = repair_address(addr)
        self.assertEqual(repaired["postal_code"], "221005")

    def test_fallback_to_user_default_address(self):
        user = User.objects.create_user(phone="9999999999", password="password123")
        default_addr = Address.objects.create(
            user=user,
            name="Jane Doe",
            phone="9876543210",
            address_line1="Default Line 1",
            city="Varanasi",
            state="UP",
            postal_code="221005",
            country="India",
            is_default=True,
            is_active=True
        )
        
        # Test case: missing critical fields
        addr = {
            "name": "",
            "postal_code": "",
            "city": ""
        }
        
        order = MagicMock()
        order.user = user
        
        repaired = repair_address(addr, order=order)
        self.assertEqual(repaired["name"], "Jane Doe")
        self.assertEqual(repaired["postal_code"], "221005")
        self.assertEqual(repaired["city"], "Varanasi")
        self.assertEqual(repaired["phone"], "9876543210")
