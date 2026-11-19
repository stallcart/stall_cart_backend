#!/usr/bin/env python3
"""
StallCart Official Seller Operations Manual & Handbook Generator (Bilingual: Hindi & English)
Generates:
1. High-resolution pixel-perfect UI mockup screenshots for each step in the seller workflow.
2. Comprehensive, bilingual (Hindi & English) multi-page PDF document with ReportLab.
"""

import os
import sys
import shutil
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont

# Define Output Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, 'static', 'docs', 'screenshots')
PDF_OUTPUT_PATH = os.path.join(PROJECT_ROOT, 'static', 'docs', 'StallCart_Seller_Manual.pdf')
MEDIA_PDF_PATH = os.path.join(PROJECT_ROOT, 'media', 'manuals', 'StallCart_Seller_Manual.pdf')

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(os.path.dirname(PDF_OUTPUT_PATH), exist_ok=True)
os.makedirs(os.path.dirname(MEDIA_PDF_PATH), exist_ok=True)

# ─────────────────────────────────────────────────────────────
# 1. HELPER: FONT LOADER FOR PILLOW & REPORTLAB
# ─────────────────────────────────────────────────────────────
def get_pillow_font(size=14, bold=False):
    font_candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in font_candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def register_reportlab_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    
    font_candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
        "/usr/share/fonts/truetype/Gargi/Gargi.ttf",
        "/Library/Fonts/Arial Unicode.ttf"
    ]
    for p in font_candidates:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont('DevFont', p))
                return 'DevFont'
            except Exception:
                pass
    return 'Helvetica'


# ─────────────────────────────────────────────────────────────
# 2. SCREENSHOT GENERATORS (Pillow UI Mockups)
# ─────────────────────────────────────────────────────────────

def draw_browser_frame(d, width, height, title, url):
    d.rectangle([(0, 0), (width, 42)], fill=(241, 245, 249))
    d.line([(0, 42), (width, 42)], fill=(203, 213, 225), width=1)
    d.ellipse([(14, 15), (26, 27)], fill=(239, 68, 68))
    d.ellipse([(34, 15), (46, 27)], fill=(245, 158, 11))
    d.ellipse([(54, 15), (66, 27)], fill=(34, 197, 94))
    
    url_box_left = 85
    url_box_right = width - 20
    d.rounded_rectangle([(url_box_left, 8), (url_box_right, 34)], radius=6, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    font_url = get_pillow_font(12, bold=False)
    d.text((url_box_left + 12, 12), f"🔒 {url}", fill=(100, 116, 139), font=font_url)


def generate_screen_1_registration():
    """Screenshot 1: Seller Onboarding & KYC Form"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart - Seller Registration", "https://stallcart.in/accounts/seller/register/")
    
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "StallCart", fill=(15, 23, 42), font=get_pillow_font(22, bold=True))
    d.text((135, 60), "Seller Partner Onboarding Portal (विक्रेता पंजीकरण)", fill=(5, 150, 105), font=get_pillow_font(14, bold=True))
    d.rounded_rectangle([(w - 180, 55), (w - 30, 85)], radius=6, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((w - 165, 62), "● KYC Approved ✓", fill=(4, 120, 87), font=get_pillow_font(12, bold=True))

    d.rounded_rectangle([(30, 115), (w - 30, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.text((55, 135), "1. Business & Pickup Store Details (दुकान एवं पिकअप पता)", fill=(30, 41, 59), font=get_pillow_font(15, bold=True))
    
    d.text((55, 175), "Shop / Legal Business Name (दुकान का नाम) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(55, 195), (450, 230)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((70, 203), "AyurSattva Herbal Care", fill=(15, 23, 42), font=get_pillow_font(13, bold=False))
    
    d.text((480, 175), "Registered Phone / WhatsApp (मोबाइल नंबर) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(480, 195), (875, 230)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((495, 203), "+91 6355588582 (OTP Verified ✓)", fill=(5, 150, 105), font=get_pillow_font(13, bold=True))

    d.text((55, 245), "Courier Pickup Warehouse Address (कूरियर पिकअप पता) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(55, 265), (580, 300)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((70, 273), "Plot 42, Herbal Industrial Estate, Khasur, Surat", fill=(15, 23, 42), font=get_pillow_font(13, bold=False))
    
    d.text((610, 245), "Pickup Pincode (पिनकोड) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(610, 265), (875, 300)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((625, 273), "395004 (Delhivery Serviceable ✓)", fill=(5, 150, 105), font=get_pillow_font(13, bold=True))

    d.text((55, 325), "2. Bank Account Details for Payouts (बैंक खाता विवरण)", fill=(30, 41, 59), font=get_pillow_font(15, bold=True))
    
    d.text((55, 355), "Bank Name (बैंक का नाम) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(55, 375), (320, 410)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((70, 383), "Bank of Baroda", fill=(15, 23, 42), font=get_pillow_font(13, bold=False))
    
    d.text((345, 355), "Account Number (खाता संख्या) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(345, 375), (610, 410)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((360, 383), "446487269828611 (Valid)", fill=(15, 23, 42), font=get_pillow_font(13, bold=False))

    d.text((635, 355), "IFSC Code (आईएफएससी कोड) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(635, 375), (875, 410)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((650, 383), "BARB0KHASUR (Verified ✓)", fill=(5, 150, 105), font=get_pillow_font(13, bold=True))

    d.rounded_rectangle([(55, 440), (320, 485)], radius=8, fill=(5, 150, 105))
    d.text((75, 452), "✓ Save & Submit Profile (जमा करें)", fill=(255, 255, 255), font=get_pillow_font(13, bold=True))
    d.text((345, 455), "🔒 StallCart ensures bank details are 256-bit encrypted for automated payouts.", fill=(100, 116, 139), font=get_pillow_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_1_registration.png')
    img.save(path)
    return path


def generate_screen_2_product_listing():
    """Screenshot 2: Add Product & Variant Cataloging Form"""
    w, h = 950, 600
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller - Add New Product", "https://stallcart.in/items/seller/products/add/")
    
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "Seller Panel", fill=(15, 23, 42), font=get_pillow_font(20, bold=True))
    d.text((170, 60), "›  Add New Product Listing (नया उत्पाद जोड़ें)", fill=(100, 116, 139), font=get_pillow_font(14, bold=False))
    
    d.rounded_rectangle([(30, 115), (550, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.text((50, 135), "Product Information (उत्पाद का विवरण)", fill=(30, 41, 59), font=get_pillow_font(15, bold=True))
    
    d.text((50, 175), "Product Title (उत्पाद का नाम) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(50, 195), (530, 230)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((65, 203), "AyurSattva Charcoal Detox Herbal Soap (100g)", fill=(15, 23, 42), font=get_pillow_font(13, bold=False))
    
    d.text((50, 245), "Category (श्रेणी) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(50, 265), (280, 300)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((65, 273), "Personal Care & Wellness", fill=(15, 23, 42), font=get_pillow_font(13, bold=False))
    d.text((295, 273), "Commission: 15%", fill=(37, 99, 235), font=get_pillow_font(12, bold=True))
    
    d.text((50, 315), "MRP (अधिकतम मूल्य) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(50, 335), (200, 370)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((65, 343), "₹ 120.00", fill=(15, 23, 42), font=get_pillow_font(13, bold=False))
    
    d.text((220, 315), "Selling Price (बिक्री मूल्य) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(220, 335), (370, 370)], radius=6, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((235, 343), "₹ 89.00 (25% OFF)", fill=(4, 120, 87), font=get_pillow_font(13, bold=True))

    d.text((390, 315), "Stock Qty (स्टॉक) *", fill=(71, 85, 105), font=get_pillow_font(12, bold=True))
    d.rounded_rectangle([(390, 335), (530, 370)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((405, 343), "50 Units", fill=(15, 23, 42), font=get_pillow_font(13, bold=False))

    d.text((50, 395), "Variants (साइज / वजन वेरिएंट्स)", fill=(30, 41, 59), font=get_pillow_font(14, bold=True))
    d.rectangle([(50, 425), (530, 465)], fill=(241, 245, 249))
    d.text((60, 435), "1 Bar (100g)  —  ₹89.00  —  Stock: 50 Units", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))
    d.rectangle([(50, 470), (530, 510)], fill=(248, 250, 252))
    d.text((60, 480), "Pack of 3 (300g) —  ₹239.00 —  Stock: 25 Units", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))

    d.rounded_rectangle([(580, 115), (w - 30, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.text((605, 135), "Product Images (उत्पाद की फोटो)", fill=(30, 41, 59), font=get_pillow_font(15, bold=True))
    d.text((605, 160), "Upload clean white-background photos (min 800x800 px)", fill=(100, 116, 139), font=get_pillow_font(11, bold=False))

    d.rounded_rectangle([(605, 190), (745, 330)], radius=8, fill=(241, 245, 249), outline=(167, 243, 208), width=2)
    d.text((630, 250), "📷 Primary Photo", fill=(5, 150, 105), font=get_pillow_font(12, bold=True))
    d.text((645, 270), "(मुख्य फोटो)", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    d.rounded_rectangle([(765, 190), (905, 330)], radius=8, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((795, 250), "📷 Angle Photo 2", fill=(71, 85, 105), font=get_pillow_font(12, bold=False))

    d.rounded_rectangle([(605, 350), (745, 450)], radius=8, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((635, 395), "📷 Ingredients / Box", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))

    d.rounded_rectangle([(765, 350), (905, 450)], radius=8, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((800, 395), "📷 + Add More", fill=(37, 99, 235), font=get_pillow_font(12, bold=True))

    d.rounded_rectangle([(605, 480), (905, 530)], radius=8, fill=(5, 150, 105))
    d.text((660, 495), "🚀 Publish (प्रकाशित करें)", fill=(255, 255, 255), font=get_pillow_font(15, bold=True))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_2_product_listing.png')
    img.save(path)
    return path


def generate_screen_3_orders_dashboard():
    """Screenshot 3: Seller Orders Dashboard with Status Lifecycle"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller Orders", "https://stallcart.in/orders/seller/orders/")
    
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "Manage Orders (ऑर्डर प्रबंधन)", fill=(15, 23, 42), font=get_pillow_font(20, bold=True))
    d.text((310, 60), "Real-time Order Processing & Fulfillment", fill=(100, 116, 139), font=get_pillow_font(13, bold=False))
    
    tabs = [("All Orders (8)", False), ("Pending / New (1)", True), ("Ready for Pickup (2)", False), ("In Transit (3)", False), ("Delivered (2)", False)]
    cur_x = 30
    for label, active in tabs:
        box_w = 150
        if active:
            d.rounded_rectangle([(cur_x, 115), (cur_x + box_w, 150)], radius=6, fill=(236, 253, 245), outline=(5, 150, 105), width=2)
            d.text((cur_x + 12, 126), label, fill=(4, 120, 87), font=get_pillow_font(12, bold=True))
        else:
            d.rounded_rectangle([(cur_x, 115), (cur_x + box_w, 150)], radius=6, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
            d.text((cur_x + 12, 126), label, fill=(100, 116, 139), font=get_pillow_font(12, bold=False))
        cur_x += box_w + 12

    d.rounded_rectangle([(30, 175), (w - 30, 340)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 175), (w - 30, 220)], fill=(248, 250, 252))
    d.line([(30, 220), (w - 30, 220)], fill=(226, 232, 240), width=1)
    d.text((50, 188), "ORDER #ORD-20261120-000001", fill=(15, 23, 42), font=get_pillow_font(14, bold=True))
    d.text((360, 190), "Placed: 20 Nov 2026, 09:30 AM", fill=(100, 116, 139), font=get_pillow_font(12, bold=False))
    
    d.rounded_rectangle([(w - 240, 185), (w - 50, 212)], radius=12, fill=(254, 243, 199))
    d.text((w - 225, 190), "⚡ ACTION REQUIRED (नया ऑर्डर)", fill=(180, 83, 9), font=get_pillow_font(11, bold=True))

    d.text((50, 235), "Customer: Amit Sharma  |  Shipping: Varanasi, UP - 221001", fill=(71, 85, 105), font=get_pillow_font(12, bold=False))
    d.text((50, 260), "Item: AyurSattva Charcoal Detox Herbal Soap (100g) x 1", fill=(15, 23, 42), font=get_pillow_font(15, bold=True))
    d.text((50, 285), "Item Total: ₹89.00  |  Platform Comm: 15% (₹13.35)  |  Your Net Earnings: ₹75.65", fill=(5, 150, 105), font=get_pillow_font(13, bold=True))

    d.rounded_rectangle([(w - 240, 240), (w - 50, 275)], radius=6, fill=(5, 150, 105))
    d.text((w - 225, 248), "✓ Accept & Pack (स्वीकार करें)", fill=(255, 255, 255), font=get_pillow_font(11, bold=True))

    d.rounded_rectangle([(w - 240, 285), (w - 50, 320)], radius=6, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.text((w - 225, 294), "📄 Print Tax Invoice (इनवॉइस)", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))

    d.rounded_rectangle([(30, 360), (w - 30, 520)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 360), (w - 30, 405)], fill=(248, 250, 252))
    d.line([(30, 405), (w - 30, 405)], fill=(226, 232, 240), width=1)
    d.text((50, 373), "ORDER #ORD-20261020-000001", fill=(15, 23, 42), font=get_pillow_font(14, bold=True))
    d.rounded_rectangle([(w - 240, 370), (w - 50, 397)], radius=12, fill=(239, 246, 255))
    d.text((w - 225, 375), "🚚 READY FOR PICKUP (पिकअप हेतु तैयार)", fill=(29, 78, 216), font=get_pillow_font(11, bold=True))
    
    d.text((50, 420), "Courier: Delhivery  |  AWB: 143289028129  |  Token: PKP-98210", fill=(37, 99, 235), font=get_pillow_font(13, bold=True))
    d.text((50, 445), "Item: AyurSattva Herbal Shampoo (200ml) x 1  |  Disbursement: ₹145.00", fill=(15, 23, 42), font=get_pillow_font(14, bold=True))
    d.text((50, 470), "Status: Hand package to courier rider upon OTP verification.", fill=(100, 116, 139), font=get_pillow_font(12, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_3_orders_dashboard.png')
    img.save(path)
    return path


def generate_screen_4_packing_sop():
    """Screenshot 4: Packaging SOP & Invoice Printing"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart - Packaging & Dispatch SOP", "https://stallcart.in/orders/order/ORD-20261120-000001/invoice/")
    
    d.rounded_rectangle([(30, 60), (450, h - 30)], radius=8, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.text((50, 75), "TAX INVOICE / PACKING SLIP (टैक्स इनवॉइस)", fill=(15, 23, 42), font=get_pillow_font(13, bold=True))
    d.text((50, 95), "StallCart Retail Platform", fill=(100, 116, 139), font=get_pillow_font(11, bold=False))
    d.line([(50, 115), (430, 115)], fill=(226, 232, 240), width=1)
    
    d.text((50, 125), "Order ID: #ORD-20261120-000001", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))
    d.text((50, 145), "Invoice No: SC-INV-2026-9021", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((50, 165), "Seller: AyurSattva Herbal Care", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((50, 185), "Buyer: Amit Sharma, Varanasi UP", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    
    d.rectangle([(50, 210), (430, 235)], fill=(241, 245, 249))
    d.text((55, 217), "Item Description", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((280, 217), "Qty", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((340, 217), "Total", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    
    d.text((55, 245), "AyurSattva Charcoal Soap (100g)", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((285, 245), "1", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((340, 245), "₹89.00", fill=(15, 23, 42), font=get_pillow_font(10, bold=True))

    d.rectangle([(50, 310), (430, 380)], fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    for bx in range(70, 410, 6):
        d.line([(bx, 320), (bx, 360)], fill=(0, 0, 0), width=3 if bx % 4 == 0 else 1)
    d.text((150, 365), "* 143289028129 *", fill=(0, 0, 0), font=get_pillow_font(11, bold=True))

    d.text((50, 400), "Note: Fold and insert Invoice INSIDE package pouch.", fill=(180, 83, 9), font=get_pillow_font(11, bold=True))

    d.rounded_rectangle([(480, 60), (w - 30, h - 30)], radius=8, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.text((505, 80), "Packaging Guidelines (पैकिंग के 5 नियम)", fill=(4, 120, 87), font=get_pillow_font(16, bold=True))
    
    steps = [
        ("Step 1: Quality Check (क्वालिटी जांचें)", "उत्पाद की सही जांच करें। सही साइज और कलर वेरिएंट सुनिश्चित करें।"),
        ("Step 2: Bubble Wrap (सुरक्षित रैपिंग)", "कम से कम 2 लेयर बबल रैप लगाएं ताकि रास्ते में सामान टूटे या लीक न हो।"),
        ("Step 3: Sturdy Outer Box (मजबूत बॉक्स)", "स्टॉलकार्ट टेंपर-प्रूफ बैग या 3-प्लाई कोरुगेटेड बॉक्स में पैक करें।"),
        ("Step 4: Barcode Label (बारकोड लेबल)", "दिल्लीवरी/शिपरोकेट का शिपिंग लेबल बाहर चिपकाएं। बारकोड पर टेप न लगाएं।"),
        ("Step 5: Courier Handover (कूरियर हैंडओवर)", "राइडर का आईडी देखें, पैकेट स्कैन करवाएं और डिलीवरी टोकन नोट करें।")
    ]
    sy = 125
    for s_title, s_desc in steps:
        d.ellipse([(505, sy), (525, sy + 20)], fill=(5, 150, 105))
        d.text((511, sy + 2), "✓", fill=(255, 255, 255), font=get_pillow_font(12, bold=True))
        d.text((535, sy), s_title, fill=(15, 23, 42), font=get_pillow_font(13, bold=True))
        d.text((535, sy + 20), s_desc, fill=(100, 116, 139), font=get_pillow_font(11, bold=False))
        sy += 75

    path = os.path.join(SCREENSHOTS_DIR, 'screen_4_packing_sop.png')
    img.save(path)
    return path


def generate_screen_5_shiprocket_pickup():
    """Screenshot 5: Shiprocket Courier Dispatch & Tracking Flow"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Logistics - Shiprocket Courier Dispatch", "https://stallcart.in/orders/track/ORD-20261120-000001/")
    
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "Automated Logistics & Tracking (कूरियर पिकअप ट्रैकिंग)", fill=(15, 23, 42), font=get_pillow_font(18, bold=True))
    d.text((470, 60), "Integrated with Shiprocket & Delhivery Express", fill=(5, 150, 105), font=get_pillow_font(13, bold=True))

    d.rounded_rectangle([(30, 115), (w - 30, 210)], radius=12, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    d.text((50, 130), "COURIER PARTNER: DELHIVERY EXPRESS (कूरियर पार्टनर)", fill=(29, 78, 216), font=get_pillow_font(15, bold=True))
    d.text((50, 155), "AWB / Tracking Number: 143289028129", fill=(15, 23, 42), font=get_pillow_font(13, bold=True))
    d.text((450, 155), "Pickup Token: PKP-98210-SC", fill=(15, 23, 42), font=get_pillow_font(13, bold=True))
    d.text((50, 180), "Scheduled Slot: Today, 02:00 PM - 05:00 PM  |  Rider Phone: +91 98765 43210", fill=(71, 85, 105), font=get_pillow_font(12, bold=False))

    d.rounded_rectangle([(30, 230), (w - 30, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.text((50, 250), "Complete Order Shipping Journey (शिपिंग के 6 चरण)", fill=(30, 41, 59), font=get_pillow_font(15, bold=True))

    stages = [
        ("1. Order Placed", "ऑर्डर प्राप्त हुआ", True),
        ("2. Packed & Ready", "पैक हो गया", True),
        ("3. Courier Picked", "कूरियर ने उठाया", True),
        ("4. In Transit", "रास्ते में है", True),
        ("5. Out for Delivery", "डिलीवरी पर निकला", True),
        ("6. Delivered (OTP)", "ओटीपी डिलीवरी सफल", True)
    ]
    step_x = 50
    step_width = 140
    for idx, (st_name, st_sub, is_done) in enumerate(stages):
        d.ellipse([(step_x + 35, 300), (step_x + 75, 340)], fill=(5, 150, 105) if is_done else (203, 213, 225))
        d.text((step_x + 48, 312), "✓", fill=(255, 255, 255), font=get_pillow_font(15, bold=True))
        if idx < len(stages) - 1:
            d.line([(step_x + 75, 320), (step_x + 75 + step_width - 40, 320)], fill=(5, 150, 105), width=3)
        d.text((step_x, 355), st_name, fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
        d.text((step_x, 375), st_sub, fill=(100, 116, 139), font=get_pillow_font(10, bold=False))
        step_x += step_width

    d.rounded_rectangle([(50, 430), (w - 50, 500)], radius=8, fill=(254, 242, 242), outline=(254, 202, 202), width=1)
    d.text((70, 445), "🛡️ 4-Digit Secret Delivery OTP Guarantee (सुरक्षित ओटीपी डिलीवरी):", fill=(185, 28, 28), font=get_pillow_font(13, bold=True))
    d.text((70, 468), "ग्राहक द्वारा 4-अंकीय गुप्त ओटीपी दिए बिना राइडर पैकेट नहीं दे सकता।", fill=(153, 27, 27), font=get_pillow_font(12, bold=False))
    d.text((70, 485), "इससे गलत या झूठी डिलीवरी क्लेम से विक्रेता को 100% सुरक्षा मिलती है।", fill=(153, 27, 27), font=get_pillow_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_5_shiprocket_pickup.png')
    img.save(path)
    return path


def generate_screen_6_notification_emails():
    """Screenshot 6: Transactional Emails Sample (New Order, Pickup, Settlement)"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "Seller Email Notifications - StallCart Automated Alerts", "https://mail.google.com/seller-inbox")

    d.rounded_rectangle([(30, 60), (460, h - 30)], radius=10, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.rectangle([(30, 60), (460, 110)], fill=(5, 150, 105))
    d.text((50, 75), "StallCart: New Order! नया ऑर्डर प्राप्त 📦", fill=(255, 255, 255), font=get_pillow_font(14, bold=True))

    d.text((50, 125), "Dear AyurSattva Herbal Care,", fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
    d.text((50, 145), "बधाई! आपको एक नया ऑर्डर प्राप्त हुआ है।", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    
    d.rounded_rectangle([(50, 175), (440, 290)], radius=6, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((65, 190), "Order ID: #ORD-20261120-000001", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))
    d.text((65, 212), "Product: AyurSattva Charcoal Soap (100g)", fill=(15, 23, 42), font=get_pillow_font(11, bold=False))
    d.text((65, 234), "Quantity: 1 Pc  |  Price: ₹89.00", fill=(15, 23, 42), font=get_pillow_font(11, bold=False))
    d.text((65, 256), "Your Earnings: ₹75.65 (Comm 15% deducted)", fill=(5, 150, 105), font=get_pillow_font(11, bold=True))

    d.text((50, 310), "Action Required (तत्काल कदम):", fill=(180, 83, 9), font=get_pillow_font(12, bold=True))
    d.text((50, 330), "कृपया इस ऑर्डर को तुरंत पैक करें और सेलर पोर्टल में", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((50, 350), "'Ready for Pickup' मार्क करें ताकि कूरियर आज पिकअप कर सके।", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))

    d.rounded_rectangle([(50, 385), (280, 420)], radius=6, fill=(5, 150, 105))
    d.text((75, 395), "Go to Seller Portal (पोर्टल जाएं) →", fill=(255, 255, 255), font=get_pillow_font(11, bold=True))

    d.text((50, 440), "Support Hotline: +91 7307383046", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    d.rounded_rectangle([(490, 60), (920, h - 30)], radius=10, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.rectangle([(490, 60), (920, 110)], fill=(37, 99, 235))
    d.text((510, 75), "StallCart: Payout Disbursed! पेआउट सफल 💸", fill=(255, 255, 255), font=get_pillow_font(14, bold=True))

    d.text((510, 125), "Dear AyurSattva Herbal Care,", fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
    d.text((510, 145), "आपके बैंक खाते में पेआउट ट्रांसफर कर दिया गया है।", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))

    d.rounded_rectangle([(510, 175), (900, 310)], radius=6, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    d.text((525, 188), "Settlement Batch: SET-20261119-0001", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))
    d.text((525, 210), "Amount Disbursed: ₹75.65", fill=(4, 120, 87), font=get_pillow_font(15, bold=True))
    d.text((525, 235), "Bank: Bank of Baroda (••••8611)", fill=(15, 23, 42), font=get_pillow_font(11, bold=False))
    d.text((525, 255), "IFSC Code: BARB0KHASUR", fill=(15, 23, 42), font=get_pillow_font(11, bold=False))
    d.text((525, 278), "Bank UTR: T2611131350345249750598", fill=(37, 99, 235), font=get_pillow_font(12, bold=True))

    d.text((510, 330), "Order Settled:", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))
    d.text((510, 350), "• #ORD-20261020-000001 : AyurSattva Soap x1", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((510, 370), "Status: राशि आपके खाते में क्रेडिट हो चुकी है।", fill=(5, 150, 105), font=get_pillow_font(11, bold=True))

    d.rounded_rectangle([(510, 400), (710, 435)], radius=6, fill=(37, 99, 235))
    d.text((535, 410), "Download Tax Invoice", fill=(255, 255, 255), font=get_pillow_font(12, bold=True))

    d.text((510, 455), "Need help? WhatsApp: 7307383046", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_6_notification_emails.png')
    img.save(path)
    return path


def generate_screen_7_settlement_statement():
    """Screenshot 7: Payout Audit & Settlement History with UTR"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller Finance - Settlements & Payouts", "https://stallcart.in/orders/seller/payouts/")
    
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "Seller Financial Ledger & Disbursements (पेआउट और सेटलमेंट)", fill=(15, 23, 42), font=get_pillow_font(18, bold=True))
    d.text((530, 60), "100% Transparent Platform Audit", fill=(5, 150, 105), font=get_pillow_font(13, bold=True))

    cards = [
        ("Total Net Settled (कुल भुगतान)", "₹ 75.65", "Direct credited to bank", (5, 150, 105)),
        ("Platform Commission (कमीशन)", "₹ 13.35", "Avg 15% category fee", (37, 99, 235)),
        ("Pending Next Cycle (बकाया)", "₹ 0.00", "All batches cleared", (180, 83, 9)),
    ]
    cx = 30
    for title, val, sub, col in cards:
        d.rounded_rectangle([(cx, 115), (cx + 280, 195)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        d.text((cx + 18, 128), title, fill=(100, 116, 139), font=get_pillow_font(11, bold=False))
        d.text((cx + 18, 146), val, fill=col, font=get_pillow_font(20, bold=True))
        d.text((cx + 18, 172), sub, fill=(148, 163, 184), font=get_pillow_font(10, bold=False))
        cx += 300

    d.rounded_rectangle([(30, 220), (w - 30, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 220), (w - 30, 260)], fill=(241, 245, 249))
    d.text((50, 234), "Batch ID", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((200, 234), "Orders & Items", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((420, 234), "Gross Sale", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((520, 234), "Commission", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((640, 234), "Net Paid", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((740, 234), "Bank Ref / UTR", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))

    d.text((50, 280), "SET-20261119-0001", fill=(37, 99, 235), font=get_pillow_font(12, bold=True))
    d.text((50, 300), "19 Nov 2026, 11:53 PM", fill=(148, 163, 184), font=get_pillow_font(10, bold=False))

    d.text((200, 280), "#ORD-20261020-000001", fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
    d.text((200, 300), "AyurSattva Charcoal Soap x1", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    d.text((420, 280), "₹ 89.00", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))
    d.text((520, 280), "-₹ 13.35 (15%)", fill=(220, 38, 38), font=get_pillow_font(12, bold=False))
    d.text((640, 280), "₹ 75.65", fill=(5, 150, 105), font=get_pillow_font(14, bold=True))

    d.rounded_rectangle([(740, 275), (900, 315)], radius=6, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((748, 282), "UTR: T261113...598", fill=(4, 120, 87), font=get_pillow_font(11, bold=True))
    d.text((748, 298), "● Disbursed to BoB", fill=(4, 120, 87), font=get_pillow_font(9, bold=False))

    d.line([(40, 330), (w - 40, 330)], fill=(241, 245, 249), width=1)

    d.rounded_rectangle([(50, 360), (w - 50, 500)], radius=8, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((70, 375), "💡 पारदर्शी कमाई और बैंक ट्रांसफर सूत्र (Earning Formula):", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))
    d.text((70, 400), "Net Payout = Product Final Selling Price  -  (Product Price × Category Commission Rate)", fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
    d.text((70, 425), "• उदाहरण: ₹89.00 - 15% (₹13.35) = ₹75.65 शुद्ध भुगतान (Net Bank Credit).", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((70, 445), "• कोई छिपा हुआ शुल्क नहीं। पेमेंट गेटवे या लिस्टिंग चार्ज बिल्कुल शून्य (Zero Hidden Fees).", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((70, 465), "• हर भुगतान का बैंक यूटीआर नंबर (UTR No) उपलब्ध कराया जाता है जिसे आप अपने बैंक खाते में देख सकते हैं।", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_7_settlement_statement.png')
    img.save(path)
    return path


# ─────────────────────────────────────────────────────────────
# 3. REPORTLAB NUMBERED CANVAS (Running Header & Footer)
# ─────────────────────────────────────────────────────────────
from reportlab.pdfgen import canvas
from reportlab.lib import colors

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            return

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#0f172a"))

        self.drawString(36, 810, "STALLCART · SELLER OPERATIONS MANUAL (हिंदी एवं अंग्रेजी)")
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawRightString(559, 810, "Bilingual Partner Handbook v2.0")
        
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.75)
        self.line(36, 802, 559, 802)

        self.line(36, 45, 559, 45)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(36, 32, "© 2026 StallCart Platform · विक्रेता हेल्पलाइन: +91 7307383046 · stallcartsupport@gmail.com")
        self.drawRightString(559, 32, f"Page {self._pageNumber} of {page_count}")

        self.restoreState()


# ─────────────────────────────────────────────────────────────
# 4. BUILD BILINGUAL REPORTLAB PDF DOCUMENT
# ─────────────────────────────────────────────────────────────
def build_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    dev_font = register_reportlab_fonts()
    print(f"Registered ReportLab Font for Devanagari: {dev_font}")

    doc = SimpleDocTemplate(
        PDF_OUTPUT_PATH,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    brand_emerald = colors.HexColor("#059669")
    brand_navy = colors.HexColor("#0f172a")
    text_dark = colors.HexColor("#1e293b")
    text_muted = colors.HexColor("#64748b")

    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName=dev_font,
        fontSize=23,
        leading=28,
        textColor=brand_navy,
        spaceAfter=10
    )

    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName=dev_font,
        fontSize=11,
        leading=16,
        textColor=text_muted,
        spaceAfter=18
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName=dev_font,
        fontSize=15,
        leading=20,
        textColor=brand_navy,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName=dev_font,
        fontSize=11.5,
        leading=15,
        textColor=brand_emerald,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName=dev_font,
        fontSize=9,
        leading=13.5,
        textColor=text_dark,
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=15,
        bulletIndent=5,
        spaceAfter=3.5
    )

    caption_style = ParagraphStyle(
        'ImageCaption',
        parent=styles['Normal'],
        fontName=dev_font,
        fontSize=8,
        leading=11,
        textColor=text_muted,
        alignment=1,
        spaceBefore=4,
        spaceAfter=10
    )

    story = []

    # ── COVER PAGE ──
    story.append(Spacer(1, 30))
    
    badge_table = Table(
        [[Paragraph("<b>STALLCART PARTNER ECOSYSTEM · विक्रेता सहयोग पोर्टल</b>", ParagraphStyle('Badge', fontName=dev_font, fontSize=9, textColor=colors.HexColor('#047857')))]],
        colWidths=[270]
    )
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ecfdf5')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#a7f3d0')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("विक्रेता संचालन नियमावली और संपूर्ण गाइड<br/>Seller Operations Manual &amp; Partner Handbook", title_style))
    story.append(Paragraph(
        "<b>द्विभाषी संस्करण (Bilingual Hindi &amp; English Edition):</b> "
        "स्टॉलकार्ट (stallcart.in) पर विक्रेता पंजीकरण, उत्पाद लिस्टिंग, ऑर्डर पैकिंग मानक प्रक्रिया (SOP), "
        "शिपरोकेट कूरियर पिकअप और बैंक सेटलमेंट (UTR नंबर सहित) की संपूर्ण सचित्र मार्गदर्शिका।",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=brand_emerald, spaceBefore=4, spaceAfter=18))

    meta_data = [
        [
            Paragraph("<b>संस्करण / Edition:</b> Version 2.0 (Official Standard)", body_style),
            Paragraph("<b>वेबसाइट / Portal:</b> https://stallcart.in", body_style)
        ],
        [
            Paragraph("<b>लक्षित पाठक / Audience:</b> सभी रजिस्टर्ड एवं नए विक्रेता", body_style),
            Paragraph("<b>लॉजिस्टिक्स पार्टनर:</b> Shiprocket &amp; Delhivery Express", body_style)
        ],
        [
            Paragraph("<b>व्हाट्सएप हेल्पलाइन:</b> +91 7307383046", body_style),
            Paragraph("<b>सपोर्ट ईमेल:</b> stallcartsupport@gmail.com", body_style)
        ],
        [
            Paragraph("<b>भुगतान का माध्यम:</b> बैंक ट्रांसफर (NEFT / UPI / UTR)", body_style),
            Paragraph("<b>सेटलमेंट चक्र:</b> डिलीवरी सत्यापन के तुरंत बाद", body_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
        ('PADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 24))

    index_data = [
        [
            Paragraph("<b>विषय सूची / Table of Contents</b>", ParagraphStyle('IdxH', fontName=dev_font, fontSize=10, textColor=brand_navy))
        ],
        [
            Paragraph("<b>मॉड्यूल 1:</b> विक्रेता खाता पंजीकरण, दुकान विवरण एवं बैंक केवाईसी सत्यापन<br/>"
                      "<b>मॉड्यूल 2:</b> उत्पाद लिस्टिंग, फोटोग्राफी नियम, मूल्य निर्धारण एवं वेरिएंट सेटअप<br/>"
                      "<b>मॉड्यूल 3:</b> ऑर्डर प्राप्ति चक्र एवं विक्रेता डैशबोर्ड का उपयोग<br/>"
                      "<b>मॉड्यूल 4:</b> सुरक्षित पैकेजिंग मानक प्रक्रिया (SOP) एवं टैक्स इनवॉइस मुद्रण<br/>"
                      "<b>मॉड्यूल 5:</b> शिपरोकेट कूरियर पिकअप, टोकन, बारकोड एवं सुरक्षित डिलीवरी ओटीपी<br/>"
                      "<b>मॉड्यूल 6:</b> स्वचालित ईमेल सूचनाएं, एसएमएस एवं व्हाट्सएप अलर्ट के नमूने<br/>"
                      "<b>मॉड्यूल 7:</b> पारदर्शी कमीशन कटौती, बैंक भुगतान एवं UTR ऑडिट ट्रेल<br/>"
                      "<b>मॉड्यूल 8:</b> ग्राहक रिटर्न, RTO प्रबंधन एवं विक्रेता सहायता केंद्र",
                      body_style)
        ]
    ]
    index_table = Table(index_data, colWidths=[520])
    index_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffffff')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 9),
    ]))
    story.append(index_table)
    story.append(PageBreak())

    # ── MODULE 1 ──
    story.append(Paragraph("मॉड्यूल 1: विक्रेता खाता पंजीकरण और बैंक KYC सत्यापन<br/>Module 1: Seller Onboarding &amp; Bank KYC Verification", h1_style))
    story.append(Paragraph(
        "<b>English:</b> To begin selling on StallCart, every merchant must complete the verified seller registration. "
        "This establishes an encrypted link for automated seller payouts directly into your bank account.<br/>"
        "<b>हिंदी:</b> स्टॉलकार्ट पर सामान बेचने के लिए सबसे पहले विक्रेता पंजीकरण पूरा करना अनिवार्य है। "
        "यह आपके बैंक खाते को सुरक्षित रूप से जोड़ता है ताकि आपकी बिक्री का पैसा सीधे आपके खाते में पहुंच सके।",
        body_style
    ))
    story.append(Paragraph("<b>चरणबद्ध प्रक्रिया / Step-by-Step Workflow:</b>", h2_style))
    story.append(Paragraph("• <b>पंजीकरण लिंक / Registration Portal:</b> <code>https://stallcart.in/accounts/seller/register/</code> पर जाएं या होमपेज पर 'Become a Seller' पर क्लिक करें।", bullet_style))
    story.append(Paragraph("• <b>दुकान एवं संपर्क / Business Identity:</b> अपनी दुकान का नाम (Shop Name), रजिस्टर्ड फोन नंबर और ईमेल दर्ज करें।", bullet_style))
    story.append(Paragraph("• <b>पिकअप पता और पिनकोड / Pickup Address:</b> वह सटीक गोदाम/दुकान का पता और 6-अंकीय पिनकोड दर्ज करें जहां से कूरियर राइडर पैकेट उठाएगा।", bullet_style))
    story.append(Paragraph("• <b>बैंक खाता विवरण / Bank Details for Payout:</b> बैंक का नाम, खाता संख्या (Account Number), और IFSC कोड दर्ज करें। सभी भुगतान इसी खाते में जाएंगे।", bullet_style))
    story.append(Paragraph("• <b>केवाईसी सत्यापन / KYC Verification:</b> स्टॉलकार्ट एडमिन 24 घंटे के भीतर विवरण सत्यापित करता है और आपका खाता <b>KYC Approved ✓</b> हो जाता है।", bullet_style))
    story.append(Spacer(1, 6))

    s1_path = os.path.join(SCREENSHOTS_DIR, 'screen_1_registration.png')
    story.append(RLImage(s1_path, width=520, height=295))
    story.append(Paragraph("चित्र 1.1: स्टॉलकार्ट विक्रेता पंजीकरण एवं बैंक खाता सत्यापन स्क्रीन (Seller Registration Screen)", caption_style))
    story.append(PageBreak())

    # ── MODULE 2 ──
    story.append(Paragraph("मॉड्यूल 2: उत्पाद लिस्टिंग, फोटो नियम और वेरिएंट सेटअप<br/>Module 2: Product Cataloging, Images &amp; Variant Setup", h1_style))
    story.append(Paragraph(
        "<b>English:</b> Listing attractive products with accurate pricing and high-definition photography is essential to maximize sales.<br/>"
        "<b>हिंदी:</b> उत्पाद की सही जानकारी, उचित मूल्य और साफ फोटो डालने से ग्राहक का भरोसा बढ़ता है और बिक्री तेज होती है।",
        body_style
    ))
    story.append(Paragraph("<b>मुख्य नियम एवं दिशानिर्देश / Listing Guidelines:</b>", h2_style))
    story.append(Paragraph("• <b>उत्पाद का शीर्षक (Title):</b> ब्रांड नाम, प्रमुख सामग्री या साइज स्पष्ट लिखें (उदा. <i>AyurSattva Charcoal Detox Herbal Soap - 100g</i>)।", bullet_style))
    story.append(Paragraph("• <b>श्रेणी एवं कमीशन (Category &amp; Commission):</b> सही केटेगरी चुनें। उस केटेगरी का स्टॉलकार्ट कमीशन प्रतिशत (जैसे 15%) स्क्रीन पर दिखेगा।", bullet_style))
    story.append(Paragraph("• <b>MRP बनाम सेलिंग प्राइस (Pricing):</b> अधिकतम खुदरा मूल्य (MRP) और अपना अंतिम बिक्री मूल्य (Selling Price) दर्ज करें। 15%-25% की छूट ग्राहकों को आकर्षित करती है।", bullet_style))
    story.append(Paragraph("• <b>स्टॉक (Inventory):</b> अपने पास उपलब्ध स्टॉक दर्ज करें। स्टॉक 0 होने पर सिस्टम ऑटोमैटिक 'Out of Stock' दिखाएगा।", bullet_style))
    story.append(Paragraph("• <b>वेरिएंट्स मैट्रिक्स (Variants):</b> कपड़ों के लिए साइज (S, M, L, XL) और रंग चुनें। अन्य सामानों के लिए पैक साइज (1 पीस, 3 का पैक) के अलग मूल्य सेट करें।", bullet_style))
    story.append(Paragraph("• <b>फोटो नियम (Photography SOP):</b> साफ सफेद या हल्के बैकग्राउंड में चौकोर (1:1 अनुपात) में न्यूनतम 3 साफ तस्वीरें अपलोड करें।", bullet_style))
    story.append(Spacer(1, 6))

    s2_path = os.path.join(SCREENSHOTS_DIR, 'screen_2_product_listing.png')
    story.append(RLImage(s2_path, width=520, height=310))
    story.append(Paragraph("चित्र 2.1: उत्पाद लिस्टिंग फॉर्म, लाइव वेरिएंट मैट्रिक्स और फोटो अपलोड (Product Listing Form)", caption_style))
    story.append(PageBreak())

    # ── MODULE 3 ──
    story.append(Paragraph("मॉड्यूल 3: ऑर्डर प्राप्ति चक्र और विक्रेता डैशबोर्ड<br/>Module 3: Order Receiving Lifecycle &amp; Seller Dashboard", h1_style))
    story.append(Paragraph(
        "<b>English:</b> When a shopper purchases your product, the order is immediately dispatched to your dedicated seller dashboard at <code>/orders/seller/orders/</code>.<br/>"
        "<b>हिंदी:</b> जब भी कोई ग्राहक आपका सामान खरीदेगा, ऑर्डर तुरंत आपके सेलर डैशबोर्ड पर आ जाएगा और आपको तुरंत ईमेल/एसएमएस प्राप्त होगा।",
        body_style
    ))
    story.append(Paragraph("<b>ऑर्डर के विभिन्न चरण / Order Status Stages:</b>", h2_style))

    status_data = [
        [Paragraph("<b>Status / स्थिति</b>", ParagraphStyle('SH', fontName=dev_font, fontSize=9, textColor=brand_navy)),
         Paragraph("<b>अर्थ एवं विक्रेता द्वारा की जाने वाली कार्रवाई (Action Required)</b>", ParagraphStyle('SH', fontName=dev_font, fontSize=9, textColor=brand_navy))],
        [Paragraph("<b>Pending / New</b><br/>(नया ऑर्डर)", body_style),
         Paragraph("ग्राहक ने भुगतान कर दिया है। विक्रेता को 2 घंटे के भीतर <b>Accept &amp; Pack Order</b> पर क्लिक करना चाहिए।", body_style)],
        [Paragraph("<b>Ready for Pickup</b><br/>(पिकअप हेतु तैयार)", body_style),
         Paragraph("विक्रेता ने पैकेट तैयार कर लिया है। सिस्टम कूरियर राइडर असाइन करता है और पिकअप टोकन जारी करता है।", body_style)],
        [Paragraph("<b>In Transit</b><br/>(रास्ते में)", body_style),
         Paragraph("कूरियर राइडर ने पैकेट स्कैन करके उठा लिया है। पैकेट मुख्य हब से होते हुए ग्राहक के शहर जा रहा है।", body_style)],
        [Paragraph("<b>Out for Delivery</b><br/>(डिलीवरी पर)", body_style),
         Paragraph("पैकेट ग्राहक के नजदीकी हब पहुंच चुका है और डिलीवरी बॉय आज ग्राहक के पते पर डिलीवर करेगा।", body_style)],
        [Paragraph("<b>Delivered (OTP)</b><br/>(डिलीवरी सफल)", body_style),
         Paragraph("ग्राहक ने 4-अंकीय गुप्त ओटीपी दिया और डिलीवरी पूरी हुई। ऑर्डर अब बैंक सेटलमेंट सूची में शामिल हो गया है।", body_style)]
    ]
    status_table = Table(status_data, colWidths=[120, 400])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(status_table)
    story.append(Spacer(1, 8))

    s3_path = os.path.join(SCREENSHOTS_DIR, 'screen_3_orders_dashboard.png')
    story.append(RLImage(s3_path, width=520, height=290))
    story.append(Paragraph("चित्र 3.1: विक्रेता ऑर्डर डैशबोर्ड, स्टेटस टैब एवं ग्राहक विवरण (Seller Orders Dashboard)", caption_style))
    story.append(PageBreak())

    # ── MODULE 4 ──
    story.append(Paragraph("मॉड्यूल 4: सुरक्षित पैकेजिंग मानक प्रक्रिया (SOP) और टैक्स इनवॉइस<br/>Module 4: Packaging Standard Operating Procedure (SOP)", h1_style))
    story.append(Paragraph(
        "<b>English:</b> Proper packaging protects items during transit, minimizes returns, and creates a five-star unboxing experience.<br/>"
        "<b>हिंदी:</b> सही तरीके से पैकिंग करने से रास्ते में सामान सुरक्षित रहता है, ग्राहक संतुष्ट होता है और डैमेज रिटर्न की संभावना खत्म हो जाती है।",
        body_style
    ))
    story.append(Paragraph("<b>पैकिंग के 5 सुनहरे नियम / 5-Step Packing Protocol:</b>", h2_style))
    story.append(Paragraph("<b>1. क्वालिटी और साइज जांच (Quality Verification):</b> पैकेट पैक करने से पहले चेक करें कि सही साइज (उदा. Size M, न कि L) और सही खुशबू/कलर का डिफेक्ट-फ्री सामान है।", bullet_style))
    story.append(Paragraph("<b>2. बबल रैप सुरक्षा (Bubble Wrap Layer):</b> कॉस्मेटिक, लिक्विड या नाजुक सामान को कम से कम 2 परत बबल रैप में लपेटें और टेप लगाएं।", bullet_style))
    story.append(Paragraph("<b>3. मजबूत बाहरी बॉक्स/बैग (Outer Box):</b> स्टॉलकार्ट टेंपर-एविडेंट प्लास्टिक बैग या 3-प्लाई वाले मजबूत कार्डबोर्ड बॉक्स में पैक करें।", bullet_style))
    story.append(Paragraph("<b>4. टैक्स इनवॉइस अंदर रखें (Insert Tax Invoice):</b> सेलर पोर्टल से टैक्स इनवॉइस (Tax Invoice) डाउनलोड करके प्रिंट करें और पैकेट के अंदर डालें।", bullet_style))
    story.append(Paragraph("<b>5. कूरियर बारकोड लेबल चिपकाएं (Affix AWB Label):</b> दिल्लीवरी/शिपरोकेट का AWB बारकोड लेबल बॉक्स के ऊपर सपाट चिपकाएं। बारकोड पर कभी टेप न लगाएं ताकि स्कैनर आसानी से पढ़ सके।", bullet_style))
    story.append(Spacer(1, 6))

    s4_path = os.path.join(SCREENSHOTS_DIR, 'screen_4_packing_sop.png')
    story.append(RLImage(s4_path, width=520, height=295))
    story.append(Paragraph("चित्र 4.1: स्टॉलकार्ट पैकेजिंग मानक प्रक्रिया और टैक्स इनवॉइस व बारकोड चिपकाने का सही तरीका", caption_style))
    story.append(PageBreak())

    # ── MODULE 5 ──
    story.append(Paragraph("मॉड्यूल 5: शिपरोकेट कूरियर पिकअप, टोकन और सुरक्षित डिस्पैच<br/>Module 5: Courier Pickup Scheduling &amp; Dispatch", h1_style))
    story.append(Paragraph(
        "<b>English:</b> StallCart integrates directly with Shiprocket &amp; Delhivery Express. Sellers do not need separate courier contracts.<br/>"
        "<b>हिंदी:</b> स्टॉलकार्ट सीधे शिपरोकेट और दिल्लीवरी एक्सप्रेस से जुड़ा हुआ है। आपको कूरियर कंपनी से अलग से बात करने की जरूरत नहीं होती।",
        body_style
    ))
    story.append(Paragraph("<b>पिकअप हैंडओवर दिशानिर्देश / Handover Protocol:</b>", h2_style))
    story.append(Paragraph("• <b>स्वचालित पिकअप असाइनमेंट:</b> जब आप 'Ready for Pickup' पर क्लिक करते हैं, तो सिस्टम कूरियर राइडर असाइन करके एक <b>पिकअप टोकन</b> (उदा. <code>PKP-98210-SC</code>) जारी करता है।", bullet_style))
    story.append(Paragraph("• <b>राइडर की जानकारी:</b> आपको कूरियर राइडर का नाम, मोबाइल नंबर और आगमन का समय डैशबोर्ड और एसएमएस पर मिल जाता है।", bullet_style))
    story.append(Paragraph("• <b>बारकोड स्कैन करवाएं:</b> जब राइडर आपके पते पर आए, तो उसका पहचान पत्र देखें और पैकेट सौंपकर अपने सामने बारकोड स्कैन करवाएं।", bullet_style))
    story.append(Paragraph("• <b>पिकअप रसीद (Manifest):</b> राइडर से डिजिटल या कागजी मैनिफेस्ट पर साइन लें।", bullet_style))
    story.append(Paragraph("• <b>सुरक्षित डिलीवरी ओटीपी (Secret 4-Digit OTP):</b> डिलीवरी के समय ग्राहक द्वारा राइडर को 4-अंकीय गुप्त ओटीपी देना अनिवार्य है। इससे झूठी डिलीवरी क्लेम से विक्रेता को 100% सुरक्षा मिलती है।", bullet_style))
    story.append(Spacer(1, 6))

    s5_path = os.path.join(SCREENSHOTS_DIR, 'screen_5_shiprocket_pickup.png')
    story.append(RLImage(s5_path, width=520, height=295))
    story.append(Paragraph("चित्र 5.1: कूरियर डिस्पैच प्रबंधन, पिकअप टोकन और रियल-टाइम ट्रैकिंग प्रोग्रेस (Shiprocket Tracking)", caption_style))
    story.append(PageBreak())

    # ── MODULE 6 ──
    story.append(Paragraph("मॉड्यूल 6: लेन-देन सूचनाएं और ईमेल/एसएमएस के नमूने<br/>Module 6: Seller Transactional Notifications &amp; Alerts", h1_style))
    story.append(Paragraph(
        "<b>English:</b> StallCart keeps sellers fully informed at every milestone via real-time automated emails, SMS, and WhatsApp alerts.<br/>"
        "<b>हिंदी:</b> स्टॉलकार्ट हर महत्वपूर्ण गतिविधि पर विक्रेता को रजिस्टर्ड ईमेल, एसएमएस और व्हाट्सएप पर संदेश भेजता है।",
        body_style
    ))
    story.append(Paragraph("<b>विक्रेता को प्राप्त होने वाले प्रमुख संदेश / Notification Types:</b>", h2_style))
    story.append(Paragraph("• <b>1. नया ऑर्डर ईमेल (New Order Alert):</b> ग्राहक द्वारा ऑर्डर करते ही आता है। इसमें उत्पाद का नाम, साइज, मात्रा और पैकिंग की समय-सीमा लिखी होती है।", bullet_style))
    story.append(Paragraph("• <b>2. कूरियर पिकअप अलर्ट (Pickup Confirmed):</b> जब कूरियर राइडर आपके पते से पैकेट स्कैन करके उठाता है, तो इसकी पुष्टि प्राप्त होती है।", bullet_style))
    story.append(Paragraph("• <b>3. डिलीवरी अलर्ट (Delivery Confirmed):</b> जब ग्राहक ओटीपी देकर पैकेट प्राप्त कर लेता है, तो डिलीवरी की पुष्टि का संदेश आता है।", bullet_style))
    story.append(Paragraph("• <b>4. पेआउट जमा ईमेल (Settlement Disbursed):</b> जब स्टॉलकार्ट आपके बैंक खाते में पैसे ट्रांसफर करता है, तो बैंक UTR नंबर और कटौती के पूरे विवरण के साथ ईमेल आता है।", bullet_style))
    story.append(Spacer(1, 6))

    s6_path = os.path.join(SCREENSHOTS_DIR, 'screen_6_notification_emails.png')
    story.append(RLImage(s6_path, width=520, height=295))
    story.append(Paragraph("चित्र 6.1: स्टॉलकार्ट द्वारा विक्रेता को भेजे जाने वाले आधिकारिक ईमेल अलर्ट (Email Notification Samples)", caption_style))
    story.append(PageBreak())

    # ── MODULE 7 ──
    story.append(Paragraph("मॉड्यूल 7: कमीशन कटौती, बैंक भुगतान और UTR ऑडिट<br/>Module 7: Settlements, Commissions &amp; Bank Payouts", h1_style))
    story.append(Paragraph(
        "<b>English:</b> StallCart operates on a transparent, audit-ready financial settlement model. Sellers receive direct bank payouts with complete UTR references.<br/>"
        "<b>हिंदी:</b> स्टॉलकार्ट पर भुगतान पूरी तरह पारदर्शी है। हर बैंक ट्रांसफर के साथ बैंक यूटीआर नंबर (UTR No) दिया जाता है जिसे आप अपनी पासबुक में देख सकते हैं।",
        body_style
    ))
    story.append(Paragraph("<b>विक्रेता की शुद्ध कमाई का सूत्र / Earning Formula:</b>", h2_style))

    formula_data = [
        [Paragraph("<b>कमाई का सूत्र / Formula:</b>", ParagraphStyle('FH', fontName=dev_font, fontSize=9.5, textColor=brand_navy)),
         Paragraph("<code>शुद्ध बैंक भुगतान = उत्पाद का अंतिम बिक्री मूल्य  -  प्लेटफ़ॉर्म केटेगरी कमीशन</code><br/>"
                   "<code>Net Seller Payable = Item Selling Price  -  Platform Category Commission</code>", ParagraphStyle('FC', fontName=dev_font, fontSize=9, textColor=brand_emerald))],
        [Paragraph("<b>वास्तविक उदाहरण / Example:</b>", body_style),
         Paragraph("बिक्री मूल्य (Selling Price): ₹89.00<br/>केटेगरी कमीशन (15%): -₹13.35<br/><b>विक्रेता को शुद्ध बैंक ट्रांसफर: ₹75.65</b>", body_style)],
        [Paragraph("<b>भुगतान का समय / Schedule:</b>", body_style),
         Paragraph("ऑर्डर सफलतापूर्वक डिलीवर होने और 7-दिन की आसान रिटर्न अवधि पूरी होने के बाद सेटलमेंट किया जाता है।", body_style)],
        [Paragraph("<b>ट्रांसफर का माध्यम / Mode:</b>", body_style),
         Paragraph("सीधा बैंक खाता ट्रांसफर (NEFT / RTGS / IMPS / UPI) अथवा RazorpayX इंस्टेंट पेआउट।", body_style)],
        [Paragraph("<b>बैंक UTR नंबर / Proof:</b>", body_style),
         Paragraph("हर भुगतान के साथ 22-अंकीय बैंक यूटीआर नंबर (जैसे <code>T2611131350345249750598</code>) प्रदान किया जाता है।", body_style)]
    ]
    formula_table = Table(formula_data, colWidths=[140, 380])
    formula_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(formula_table)
    story.append(Spacer(1, 8))

    s7_path = os.path.join(SCREENSHOTS_DIR, 'screen_7_settlement_statement.png')
    story.append(RLImage(s7_path, width=520, height=295))
    story.append(Paragraph("चित्र 7.1: विक्रेता पेआउट लेज़र, सेटलमेंट विवरण एवं बैंक यूटीआर संदर्भ (Settlement Statement with UTR)", caption_style))
    story.append(PageBreak())

    # ── MODULE 8 ──
    story.append(Paragraph("मॉड्यूल 8: कस्टमर रिटर्न, RTO और हेल्पलाइन सपोर्ट<br/>Module 8: Returns, RTO Management &amp; Seller Support", h1_style))
    story.append(Paragraph(
        "<b>English:</b> Handling customer returns and unexpected transit issues smoothly is critical to maintaining a 5-star seller rating.<br/>"
        "<b>हिंदी:</b> किसी भी ई-कॉमर्स व्यवसाय में रिटर्न और RTO का सही प्रबंधन विक्रेता की रेटिंग और मुनाफे को सुरक्षित रखता है।",
        body_style
    ))
    story.append(Paragraph("<b>रिटर्न एवं RTO के नियम / Return &amp; RTO Policies:</b>", h2_style))
    story.append(Paragraph("• <b>7-दिन की रिटर्न अवधि (7-Day Return):</b> ग्राहक केवल डिफेक्टिव, गलत साइज या टूटा सामान होने पर ही 7 दिन में रिटर्न का अनुरोध कर सकता है।", bullet_style))
    story.append(Paragraph("• <b>विक्रेता द्वारा सामान की जांच (Inspection):</b> कूरियर द्वारा लौटाया गया सामान आपके पते पर वापस आता है। विक्रेता द्वारा सामान की स्थिति जांचने के बाद ही रिफंड की पुष्टि होती है।", bullet_style))
    story.append(Paragraph("• <b>RTO (डिलीवरी न होना):</b> यदि ग्राहक 3 प्रयासों के बाद भी उपलब्ध नहीं होता, तो पैकेट RTO होकर आपके गोदाम में सुरक्षित लौट आता है। RTO पैकेट पर कोई प्लेटफ़ॉर्म कमीशन नहीं काटा जाता।", bullet_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>स्टॉलकार्ट आधिकारिक सहायता केंद्र / Official Support Channels:</b>", h2_style))
    
    support_data = [
        [Paragraph("<b>माध्यम / Channel</b>", ParagraphStyle('SH', fontName=dev_font, fontSize=9, textColor=brand_navy)),
         Paragraph("<b>विवरण एवं समय / Contact Details</b>", ParagraphStyle('SH', fontName=dev_font, fontSize=9, textColor=brand_navy))],
        [Paragraph("<b>व्हाट्सएप सेलर डेस्क</b>", body_style),
         Paragraph("<b>+91 7307383046</b> (पिकअप समस्या या ऑर्डर सहायता के लिए · प्रातः 9 बजे से रात्रि 9 बजे तक)", body_style)],
        [Paragraph("<b>ईमेल सपोर्ट</b>", body_style),
         Paragraph("<b>stallcartsupport@gmail.com</b> (उत्पाद कैटलॉग, बैंक खाता बदलाव या सेटलमेंट पूछताछ)", body_style)],
        [Paragraph("<b>वेबसाइट चैटबॉट</b>", body_style),
         Paragraph("होमपेज (<code>stallcart.in</code>) पर 24/7 उपलब्ध। यहां से सीधे मैनुअल डाउनलोड कर सकते हैं।", body_style)],
        [Paragraph("<b>विक्रेता डैशबोर्ड</b>", body_style),
         Paragraph("<code>https://stallcart.in/items/dashboard/</code> (लाइव स्टॉक, ऑर्डर और पेआउट नियंत्रण)", body_style)]
    ]
    support_table = Table(support_data, colWidths=[140, 380])
    support_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ecfdf5')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#a7f3d0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(support_table)
    story.append(Spacer(1, 16))

    closing_data = [
        [
            Paragraph("<b>स्टॉलकार्ट परिवार में आपका स्वागत है! (Welcome to StallCart)</b><br/>"
                      "हम पूरे भारत में आपके व्यवसाय को बढ़ाने, तेज कूरियर डिलीवरी और समय पर पारदर्शी बैंक भुगतान देने के लिए समर्पित हैं। "
                      "स्टॉलकार्ट का पार्टनर बनने के लिए धन्यवाद।",
                      ParagraphStyle('Close', fontName=dev_font, fontSize=9.5, leading=14, textColor=brand_navy))
        ]
    ]
    closing_table = Table(closing_data, colWidths=[520])
    closing_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1.5, brand_emerald),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(closing_table)

    print(f"Building Bilingual PDF at: {PDF_OUTPUT_PATH} ...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print("PDF build complete!")

    shutil.copyfile(PDF_OUTPUT_PATH, MEDIA_PDF_PATH)
    print(f"Copied to media path: {MEDIA_PDF_PATH}")
    print(f"Final file size: {os.path.getsize(PDF_OUTPUT_PATH)} bytes")


def main():
    print("=== Generating StallCart Bilingual Seller Manual Screenshots ===")
    generate_screen_1_registration()
    generate_screen_2_product_listing()
    generate_screen_3_orders_dashboard()
    generate_screen_4_packing_sop()
    generate_screen_5_shiprocket_pickup()
    generate_screen_6_notification_emails()
    generate_screen_7_settlement_statement()
    print("All 7 screenshots generated successfully!")

    print("=== Building Official Bilingual PDF Manual ===")
    build_pdf()
    print("=== All Steps Finished Successfully! ===")


if __name__ == '__main__':
    main()
