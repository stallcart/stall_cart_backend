#!/usr/bin/env python3
"""
StallCart Official Seller Operations Manual & Handbook Generator
Supports 3 Editions:
1. Hindi Edition (🇮🇳 पूर्ण हिंदी संस्करण): StallCart_Seller_Manual_Hindi.pdf
2. English Edition (🇬🇧 Complete English Edition): StallCart_Seller_Manual_English.pdf
3. Bilingual / Both Edition (🌐 हिंदी + English): StallCart_Seller_Manual.pdf & StallCart_Seller_Manual_Bilingual.pdf

Faithfully renders:
1. Actual StallCart Web App UI mockups with Announcement Bar, StallCart Navbar, Real App Theme (#2874f0),
   and 100% FICTIONAL / SAMPLE DEMO DATA (No real seller from database).
2. High-precision PDF document via WeasyPrint with Pango & HarfBuzz for 100% accurate,
   undisturbed Devanagari glyph shaping, matras, conjuncts, and modern CSS layout.
   (Falls back to ReportLab on local dev if WeasyPrint is not installed).
"""

import os
import sys
import base64
import shutil
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont

# Define Output Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, 'static', 'docs', 'screenshots')
STATIC_DOCS_DIR = os.path.join(PROJECT_ROOT, 'static', 'docs')
MEDIA_MANUALS_DIR = os.path.join(PROJECT_ROOT, 'media', 'manuals')

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(STATIC_DOCS_DIR, exist_ok=True)
os.makedirs(MEDIA_MANUALS_DIR, exist_ok=True)

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
# 2. ACTUAL STALLCART WEB APP CHROME & NAVBAR MOCKUP HELPERS
# ─────────────────────────────────────────────────────────────

def draw_browser_frame(d, width, height, title, url):
    """Draws top browser frame with tabs and URL bar"""
    d.rectangle([(0, 0), (width, 38)], fill=(241, 245, 249))
    d.line([(0, 38), (width, 38)], fill=(203, 213, 225), width=1)
    d.ellipse([(14, 13), (24, 23)], fill=(239, 68, 68))
    d.ellipse([(32, 13), (42, 23)], fill=(245, 158, 11))
    d.ellipse([(50, 13), (60, 23)], fill=(34, 197, 94))
    
    url_box_left = 75
    url_box_right = width - 20
    d.rounded_rectangle([(url_box_left, 6), (url_box_right, 32)], radius=5, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    font_url = get_pillow_font(11, bold=False)
    d.text((url_box_left + 10, 10), f"🔒 {url}", fill=(100, 116, 139), font=font_url)


def draw_stallcart_header(d, width, active_nav='seller'):
    """
    Renders StallCart's exact web application header:
    - Top Announcement Bar: dark navy #0f172a
    - Main Header: StallCart Logo, Search Bar, Navigation Links, User Badge
    """
    # 1. Top Announcement Bar (height: 24px)
    d.rectangle([(0, 39), (width, 63)], fill=(15, 23, 42))
    ann_font = get_pillow_font(10, bold=False)
    ann_text = "⚡ Free delivery on orders above ₹499   ·   ↩ 7-day easy returns   ·   🛡 100% genuine products"
    d.text((width // 2 - 210, 44), ann_text, fill=(241, 245, 249), font=ann_font)

    # 2. Main StallCart Navbar (height: 52px)
    d.rectangle([(0, 64), (width, 116)], fill=(255, 255, 255))
    d.line([(0, 116), (width, 116)], fill=(226, 232, 240), width=1)

    # Logo: Stall (Navy) + Cart (Primary Blue #2874f0)
    logo_font = get_pillow_font(21, bold=True)
    d.text((25, 76), "Stall", fill=(15, 23, 42), font=logo_font)
    d.text((72, 76), "Cart", fill=(40, 116, 240), font=logo_font)

    # Search Bar (center)
    s_box_left = 145
    s_box_right = 530
    d.rounded_rectangle([(s_box_left, 74), (s_box_right, 106)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((s_box_left + 12, 82), "🔍 Search products, sellers, brands…", fill=(148, 163, 184), font=get_pillow_font(11, bold=False))
    d.rounded_rectangle([(s_box_right - 65, 74), (s_box_right, 106)], radius=6, fill=(40, 116, 240))
    d.text((s_box_right - 52, 82), "Search", fill=(255, 255, 255), font=get_pillow_font(11, bold=True))

    # Right Navigation Links
    nav_font = get_pillow_font(11, bold=True)
    
    # Seller Panel
    if active_nav == 'seller':
        d.rounded_rectangle([(550, 77), (645, 103)], radius=5, fill=(239, 246, 255))
        d.text((560, 82), "🏪 Seller Panel", fill=(37, 99, 235), font=nav_font)
    else:
        d.text((560, 82), "🏪 Seller Panel", fill=(71, 85, 105), font=nav_font)

    # Manage Orders
    if active_nav == 'orders':
        d.rounded_rectangle([(655, 77), (765, 103)], radius=5, fill=(239, 246, 255))
        d.text((665, 82), "📋 Manage Orders", fill=(37, 99, 235), font=nav_font)
    else:
        d.text((665, 82), "📋 Manage Orders", fill=(71, 85, 105), font=nav_font)

    # Payouts
    if active_nav == 'payouts':
        d.rounded_rectangle([(775, 77), (850, 103)], radius=5, fill=(236, 253, 245))
        d.text((785, 82), "💸 Payouts", fill=(5, 150, 105), font=nav_font)
    else:
        d.text((785, 82), "💸 Payouts", fill=(71, 85, 105), font=nav_font)

    # User Profile Avatar (Sample Demo Seller / Admin)
    d.ellipse([(width - 110, 75), (width - 78, 107)], fill=(40, 116, 240))
    d.text((width - 99, 81), "R", fill=(255, 255, 255), font=get_pillow_font(14, bold=True))
    d.text((width - 72, 83), "Demo Seller", fill=(15, 23, 42), font=get_pillow_font(10, bold=True))


# ─────────────────────────────────────────────────────────────
# 3. SCREENSHOT GENERATORS (100% FICTIONAL SAMPLE DATA)
# ─────────────────────────────────────────────────────────────

def generate_screen_1_registration():
    """Screenshot 1: StallCart Seller Profile & KYC Onboarding (Sample Data)"""
    w, h = 980, 580
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller Registration", "https://stallcart.in/accounts/seller/register/")
    draw_stallcart_header(d, w, active_nav='seller')
    
    # Subheader / Breadcrumb
    d.text((30, 130), "Seller Partner Onboarding · विक्रेता पंजीकरण (Sample Demo Profile)", fill=(15, 23, 42), font=get_pillow_font(16, bold=True))
    d.rounded_rectangle([(w - 180, 126), (w - 30, 152)], radius=12, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((w - 165, 132), "● KYC Approved ✓", fill=(4, 120, 87), font=get_pillow_font(11, bold=True))

    # Card 1: Shop & Pickup Details
    d.rounded_rectangle([(30, 165), (w - 30, 345)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 165), (w - 30, 198)], fill=(241, 245, 249))
    d.text((45, 175), "1. Business & Pickup Warehouse Details (दुकान एवं पिकअप पता)", fill=(30, 41, 59), font=get_pillow_font(13, bold=True))
    
    d.text((45, 210), "Shop Name (दुकान का नाम) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(45, 226), (460, 258)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((58, 234), "Apex Trends Fashion Hub (Sample Demo Store)", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))
    
    d.text((490, 210), "Seller Phone / WhatsApp (मोबाइल नंबर) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(490, 226), (935, 258)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((503, 234), "+91 98000 12345 (OTP Verified ✓)", fill=(5, 150, 105), font=get_pillow_font(12, bold=True))

    d.text((45, 272), "Pickup Warehouse Address (कूरियर पिकअप गोदाम) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(45, 288), (620, 320)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((58, 296), "Plot No. 104, Industrial Area, Sector 5, Indore, Madhya Pradesh", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))
    
    d.text((645, 272), "Pickup Pincode (पिनकोड) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(645, 288), (935, 320)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((658, 296), "452001 (Delhivery Express Serviceable ✓)", fill=(5, 150, 105), font=get_pillow_font(12, bold=True))

    # Card 2: Bank Account Details for Payouts
    d.rounded_rectangle([(30, 360), (w - 30, 520)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 360), (w - 30, 393)], fill=(241, 245, 249))
    d.text((45, 370), "2. Bank Account for Automated Payouts (पेआउट बैंक खाता विवरण - Sample)", fill=(30, 41, 59), font=get_pillow_font(13, bold=True))
    
    d.text((45, 405), "Bank Name (बैंक का नाम) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(45, 421), (320, 453)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((58, 429), "HDFC Bank (Sample Demo)", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))
    
    d.text((345, 405), "Account Number (खाता संख्या) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(345, 421), (640, 453)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((358, 429), "50100492815678 (••••5678 Encrypted)", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))

    d.text((665, 405), "IFSC Code (आईएफएससी कोड) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(665, 421), (935, 453)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((678, 429), "HDFC0001234 (Verified ✓)", fill=(5, 150, 105), font=get_pillow_font(12, bold=True))

    # Bottom Submit Action
    d.rounded_rectangle([(45, 470), (280, 504)], radius=6, fill=(40, 116, 240))
    d.text((65, 480), "✓ Save & Submit Profile (जमा करें)", fill=(255, 255, 255), font=get_pillow_font(12, bold=True))
    d.text((305, 482), "🔒 All bank details are 256-bit encrypted for automated NEFT/RazorpayX disbursements.", fill=(100, 116, 139), font=get_pillow_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_1_registration.png')
    img.save(path)
    return path


def generate_screen_2_product_listing():
    """Screenshot 2: StallCart Add Product Form & Variants (Sample Data)"""
    w, h = 980, 600
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller - Add New Product", "https://stallcart.in/items/seller/products/add/")
    draw_stallcart_header(d, w, active_nav='seller')
    
    # Page Header
    d.text((30, 130), "Add New Product (नया उत्पाद कैटलॉग में जोड़ें)", fill=(15, 23, 42), font=get_pillow_font(16, bold=True))
    d.text((450, 133), "Apex Trends Catalog · Category Commission: 15%", fill=(37, 99, 235), font=get_pillow_font(12, bold=True))

    # Left Column: Basic Info & Pricing
    d.rounded_rectangle([(30, 160), (560, h - 25)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 160), (560, 192)], fill=(241, 245, 249))
    d.text((45, 170), "Product Information & Pricing (उत्पाद विवरण एवं मूल्य)", fill=(30, 41, 59), font=get_pillow_font(13, bold=True))
    
    d.text((45, 205), "Product Name (उत्पाद का नाम) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(45, 221), (545, 253)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((58, 229), "Men's Classic Slim Fit Cotton Casual Shirt (Navy Blue)", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))
    
    d.text((45, 265), "Category (श्रेणी) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(45, 281), (285, 313)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((58, 289), "Men's Fashion & Apparel", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))
    
    d.text((305, 265), "Brand (ब्रांड)", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(305, 281), (545, 313)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((318, 289), "Apex Trends (Sample Brand)", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))

    # Pricing Row
    d.text((45, 325), "MRP (अधिकतम मूल्य) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(45, 341), (195, 373)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((58, 349), "₹ 999.00", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))
    
    d.text((215, 325), "Selling Price (बिक्री मूल्य) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(215, 341), (375, 373)], radius=5, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((228, 349), "₹ 499.00 (50% OFF)", fill=(4, 120, 87), font=get_pillow_font(12, bold=True))

    d.text((395, 325), "Stock Qty (स्टॉक) *", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(395, 341), (545, 373)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((408, 349), "100 Units", fill=(15, 23, 42), font=get_pillow_font(12, bold=False))

    # Description Box
    d.text((45, 385), "Product Highlights & Description (उत्पाद विवरण)", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(45, 401), (545, 500)], radius=5, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((58, 410), "• 100% Breathable Combed Cotton fabric.", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((58, 430), "• Spread collar with curved hemline, machine wash.", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((58, 450), "• Standard Indian sizing (M: 38, L: 40, XL: 42).", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((58, 470), "• Fast Dispatch within 24 Hours guaranteed.", fill=(5, 150, 105), font=get_pillow_font(11, bold=True))

    # Right Column: Variant & Media Gallery
    d.rounded_rectangle([(585, 160), (w - 30, h - 25)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(585, 160), (w - 30, 192)], fill=(241, 245, 249))
    d.text((600, 170), "Sizes, Color Variants & Images (वेरिएंट और फोटो)", fill=(30, 41, 59), font=get_pillow_font(13, bold=True))

    # Variants Table
    d.text((600, 205), "Active Variants Matrix (साइज व रंग)", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    d.rounded_rectangle([(600, 221), (w - 45, 335)], radius=6, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    
    # Table header
    d.text((615, 230), "Size", fill=(100, 116, 139), font=get_pillow_font(10, bold=True))
    d.text((680, 230), "Color", fill=(100, 116, 139), font=get_pillow_font(10, bold=True))
    d.text((760, 230), "Stock", fill=(100, 116, 139), font=get_pillow_font(10, bold=True))
    d.text((840, 230), "SKU Code", fill=(100, 116, 139), font=get_pillow_font(10, bold=True))
    d.line([(600, 248), (w - 45, 248)], fill=(226, 232, 240), width=1)

    variants_sample = [
        ("M", "Navy Blue", "35 Units", "APX-SHIRT-M"),
        ("L", "Navy Blue", "40 Units", "APX-SHIRT-L"),
        ("XL", "Navy Blue", "25 Units", "APX-SHIRT-XL"),
    ]
    vy = 255
    for sz, col, stk, sku in variants_sample:
        d.text((615, vy), sz, fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
        d.text((680, vy), col, fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
        d.text((760, vy), stk, fill=(5, 150, 105), font=get_pillow_font(11, bold=True))
        d.text((840, vy), sku, fill=(100, 116, 139), font=get_pillow_font(10, bold=False))
        vy += 26

    # Product Images Area
    d.text((600, 350), "Product Photography (न्यूनतम 3 साफ तस्वीरें अपलोड करें)", fill=(71, 85, 105), font=get_pillow_font(11, bold=True))
    for i, label in enumerate(["1. Front View", "2. Side Angle", "3. Fabric Detail"]):
        ix = 600 + i * 115
        d.rounded_rectangle([(ix, 370), (ix + 105, 475)], radius=6, fill=(241, 245, 249), outline=(203, 213, 225), width=1)
        d.rectangle([(ix + 20, 390), (ix + 85, 435)], fill=(203, 213, 225))
        d.text((ix + 35, 405), "👕", font=get_pillow_font(20, bold=False))
        d.text((ix + 12, 450), label, fill=(100, 116, 139), font=get_pillow_font(9, bold=False))

    # Bottom Actions
    d.rounded_rectangle([(45, 515), (260, 550)], radius=6, fill=(40, 116, 240))
    d.text((65, 526), "✓ Publish to StallCart Catalog", fill=(255, 255, 255), font=get_pillow_font(12, bold=True))
    
    path = os.path.join(SCREENSHOTS_DIR, 'screen_2_product_listing.png')
    img.save(path)
    return path


def generate_screen_3_orders_dashboard():
    """Screenshot 3: StallCart Real Seller Order Receiving Dashboard (Sample Data)"""
    w, h = 980, 580
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller - Manage Orders", "https://stallcart.in/orders/seller/orders/")
    draw_stallcart_header(d, w, active_nav='orders')
    
    # Subheader
    d.text((30, 130), "Seller Orders Management (प्राप्त ऑर्डर्स और डिस्पैच स्थिति)", fill=(15, 23, 42), font=get_pillow_font(16, bold=True))

    # Metric Cards Row
    cards = [
        ("New / Pending", "1", "Needs Packing", (220, 38, 38)),
        ("Ready for Pickup", "1", "Courier Scheduled", (217, 119, 6)),
        ("In Transit", "2", "On the way to customer", (37, 99, 235)),
        ("Delivered (OTP)", "1", "Eligible for Settlement", (5, 150, 105))
    ]
    cx = 30
    for title, val, sub, col in cards:
        d.rounded_rectangle([(cx, 160), (cx + 220, 225)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        d.text((cx + 14, 170), title, fill=(100, 116, 139), font=get_pillow_font(10, bold=False))
        d.text((cx + 14, 186), val, fill=col, font=get_pillow_font(20, bold=True))
        d.text((cx + 14, 210), sub, fill=(148, 163, 184), font=get_pillow_font(9, bold=False))
        cx += 235

    # Main Orders Table
    d.rounded_rectangle([(30, 245), (w - 30, h - 25)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    
    # Table Header Bar
    d.rectangle([(30, 245), (w - 30, 280)], fill=(241, 245, 249))
    d.text((45, 256), "Order ID", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((180, 256), "Date & Time", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((290, 256), "Product & Size", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((540, 256), "Customer & City", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((700, 256), "Amount", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((790, 256), "Status & Action", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))

    # Row 1: New Pending Order (Sample)
    d.text((45, 295), "#ORD-SAMPLE-202611-01", fill=(37, 99, 235), font=get_pillow_font(11, bold=True))
    d.text((45, 312), "Prepaid (Razorpay)", fill=(5, 150, 105), font=get_pillow_font(9, bold=True))

    d.text((180, 295), "20 Nov 2026", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((180, 312), "10:15 AM", fill=(148, 163, 184), font=get_pillow_font(9, bold=False))

    d.text((290, 295), "Men's Classic Cotton Casual Shirt", fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
    d.text((290, 312), "Size: L | Color: Navy Blue | Qty: 1", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    d.text((540, 295), "Rahul Sharma (Sample Buyer)", fill=(15, 23, 42), font=get_pillow_font(11, bold=False))
    d.text((540, 312), "Bhopal, MP (PIN: 462001)", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    d.text((700, 295), "₹ 499.00", fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
    d.text((700, 312), "Comm: ₹74.85", fill=(100, 116, 139), font=get_pillow_font(9, bold=False))

    # Action Button for New Order: Accept & Pack
    d.rounded_rectangle([(790, 292), (935, 324)], radius=5, fill=(40, 116, 240))
    d.text((802, 301), "Accept & Pack Order →", fill=(255, 255, 255), font=get_pillow_font(9, bold=True))

    d.line([(40, 340), (w - 40, 340)], fill=(241, 245, 249), width=1)

    # Row 2: Delivered Order (Awaiting Settlement Batch)
    d.text((45, 355), "#ORD-SAMPLE-202611-02", fill=(37, 99, 235), font=get_pillow_font(11, bold=True))
    d.text((45, 372), "COD (Cash On Delivery)", fill=(100, 116, 139), font=get_pillow_font(9, bold=False))

    d.text((180, 355), "18 Nov 2026", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((180, 372), "03:40 PM", fill=(148, 163, 184), font=get_pillow_font(9, bold=False))

    d.text((290, 355), "Men's Classic Cotton Casual Shirt", fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
    d.text((290, 372), "Size: M | Color: Navy Blue | Qty: 1", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    d.text((540, 355), "Pooja Verma (Sample Buyer)", fill=(15, 23, 42), font=get_pillow_font(11, bold=False))
    d.text((540, 372), "Jaipur, RJ (PIN: 302001)", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    d.text((700, 355), "₹ 499.00", fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
    d.text((700, 372), "Net: ₹424.15", fill=(5, 150, 105), font=get_pillow_font(9, bold=True))

    d.rounded_rectangle([(790, 352), (935, 384)], radius=5, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((805, 361), "Delivered (OTP Verified ✓)", fill=(4, 120, 87), font=get_pillow_font(9, bold=True))

    # Helper Banner
    d.rounded_rectangle([(45, 430), (w - 45, 530)], radius=8, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    d.text((65, 445), "💡 विक्रेता के लिए आवश्यक दिशानिर्देश (Quick Seller Operational Rule):", fill=(30, 58, 138), font=get_pillow_font(12, bold=True))
    d.text((65, 468), "1. नया ऑर्डर आने के 24 घंटे के भीतर 'Accept & Pack Order' पर क्लिक करके पैकेट पैक करें।", fill=(30, 41, 59), font=get_pillow_font(11, bold=False))
    d.text((65, 488), "2. 'Ready for Pickup' मार्क करते ही कूरियर राइडर 1 कार्यदिवस में आपके गोदाम पर आ जाएगा।", fill=(30, 41, 59), font=get_pillow_font(11, bold=False))
    d.text((65, 508), "3. डिलीवरी के समय ग्राहक राइडर को 4-अंकीय ओटीपी देगा, जिससे फर्जी दावों की कोई गुंजाइश नहीं रहती।", fill=(30, 41, 59), font=get_pillow_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_3_orders_dashboard.png')
    img.save(path)
    return path


def generate_screen_4_packing_sop():
    """Screenshot 4: StallCart Packaging SOP & Official Invoice Sample (Sample Data)"""
    w, h = 980, 580
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart SOP - Packaging & Tax Invoice", "https://stallcart.in/orders/seller/sop/packaging/")
    draw_stallcart_header(d, w, active_nav='orders')
    
    # Subheader
    d.text((30, 130), "Packaging SOP & Tax Invoice Protocol (मानक पैकिंग प्रक्रिया एवं इनवॉइस)", fill=(15, 23, 42), font=get_pillow_font(16, bold=True))

    # Left Container: Printable Official Invoice
    d.rounded_rectangle([(30, 160), (460, h - 25)], radius=10, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.rectangle([(30, 160), (460, 195)], fill=(15, 23, 42))
    d.text((45, 172), "StallCart Official Tax Invoice (नमूना इनवॉइस)", fill=(255, 255, 255), font=get_pillow_font(11, bold=True))
    
    # Invoice Inner Content
    d.text((45, 210), "TAX INVOICE / BILL OF SUPPLY", fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
    d.text((45, 228), "Invoice No: STALL-INV-202611-0089", fill=(100, 116, 139), font=get_pillow_font(9, bold=False))
    d.text((45, 242), "Date: 20-Nov-2026 | Order: #ORD-SAMPLE-202611-01", fill=(100, 116, 139), font=get_pillow_font(9, bold=False))
    
    d.line([(45, 260), (445, 260)], fill=(226, 232, 240), width=1)

    d.text((45, 268), "Sold By (Seller Details):", fill=(71, 85, 105), font=get_pillow_font(9, bold=True))
    d.text((45, 282), "Apex Trends Fashion Hub (Sample Store)", fill=(15, 23, 42), font=get_pillow_font(10, bold=True))
    d.text((45, 296), "GSTIN: 23AAAAA0000A1Z5 · Indore, MP", fill=(100, 116, 139), font=get_pillow_font(9, bold=False))

    d.text((250, 268), "Shipping To (Customer):", fill=(71, 85, 105), font=get_pillow_font(9, bold=True))
    d.text((250, 282), "Rahul Sharma (Sample Buyer)", fill=(15, 23, 42), font=get_pillow_font(10, bold=True))
    d.text((250, 296), "Bhopal, MP - 462001", fill=(100, 116, 139), font=get_pillow_font(9, bold=False))

    d.line([(45, 318), (445, 318)], fill=(226, 232, 240), width=1)

    # Item breakdown table
    d.text((45, 328), "Item Description", fill=(100, 116, 139), font=get_pillow_font(9, bold=True))
    d.text((270, 328), "Qty", fill=(100, 116, 139), font=get_pillow_font(9, bold=True))
    d.text((320, 328), "Price", fill=(100, 116, 139), font=get_pillow_font(9, bold=True))
    d.text((390, 328), "Total", fill=(100, 116, 139), font=get_pillow_font(9, bold=True))
    d.line([(45, 342), (445, 342)], fill=(241, 245, 249), width=1)

    d.text((45, 350), "Men's Classic Cotton Casual Shirt (L)", fill=(15, 23, 42), font=get_pillow_font(9, bold=False))
    d.text((275, 350), "1", fill=(15, 23, 42), font=get_pillow_font(9, bold=False))
    d.text((320, 350), "₹475.24", fill=(15, 23, 42), font=get_pillow_font(9, bold=False))
    d.text((390, 350), "₹475.24", fill=(15, 23, 42), font=get_pillow_font(9, bold=False))

    d.text((45, 370), "CGST (2.5%) + SGST (2.5%)", fill=(100, 116, 139), font=get_pillow_font(9, bold=False))
    d.text((390, 370), "₹23.76", fill=(100, 116, 139), font=get_pillow_font(9, bold=False))

    d.line([(45, 390), (445, 390)], fill=(203, 213, 225), width=1)
    d.text((45, 400), "Grand Total (Prepaid Paid in Full):", fill=(15, 23, 42), font=get_pillow_font(10, bold=True))
    d.text((385, 400), "₹ 499.00", fill=(5, 150, 105), font=get_pillow_font(12, bold=True))

    # AWB Barcode Simulation on parcel
    d.rounded_rectangle([(45, 430), (445, 530)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((60, 440), "Delhivery Surface AWB: 284910284729102", fill=(15, 23, 42), font=get_pillow_font(10, bold=True))
    # Draw simulated barcode lines
    bx = 60
    for w_line in [2, 1, 3, 1, 4, 2, 1, 3, 2, 4, 1, 2, 3, 1, 2, 4, 1, 3, 2, 1, 4, 2, 3, 1, 2]:
        d.rectangle([(bx, 460), (bx + w_line, 500)], fill=(15, 23, 42))
        bx += w_line + 3
    d.text((60, 508), "Destination Hub: BHO/BPL · Sort Code: D-12", fill=(71, 85, 105), font=get_pillow_font(9, bold=False))

    # Right Container: 5 Golden Packing Steps SOP
    d.rounded_rectangle([(485, 160), (w - 30, h - 25)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(485, 160), (w - 30, 195)], fill=(37, 99, 235))
    d.text((500, 172), "5-Step Packaging Protocol (सुरक्षित 5-चरणीय पैकिंग मानक)", fill=(255, 255, 255), font=get_pillow_font(12, bold=True))

    steps = [
        ("1. Quality & Size Verification (क्वालिटी जांच)", "सामान पैक करने से पहले सुनिश्चित करें कि सही साइज (Size L), रंग और डिफेक्ट-फ्री उत्पाद ही पैक हो रहा है।"),
        ("2. Waterproof Polybag Wrap (बबल रैप / पॉलीथीन)", "कपड़े या नाजुक सामान को पहले स्वच्छ पॉलीथीन या 2-लेयर बबल रैप में सील करें ताकि नमी या बारिश से सुरक्षा रहे।"),
        ("3. Strong Outer Box / Bag (मजबूत बाहरी बॉक्स)", "स्टॉलकार्ट टेंपर-एविडेंट सिक्योरिटी बैग या 3-प्लाई वाले मजबूत कार्डबोर्ड बॉक्स में सुरक्षित रूप से रखें।"),
        ("4. Insert Tax Invoice Inside (टैक्स इनवॉइस रखें)", "सेलर पैनल से डाउनलोड किया हुआ टैक्स इनवॉइस बॉक्स के अंदर सामान के साथ अवश्य रखें।"),
        ("5. Affix Courier Label on Flat Face (कूरियर लेबल)", "शिपरोकेट/दिल्लीवरी का AWB शिपिंग बारकोड बॉक्स के ऊपर सपाट चिपकाएं। बारकोड पर कभी सेलोटेप न लगाएं।")
    ]
    sy = 210
    for title, desc in steps:
        d.text((505, sy), title, fill=(30, 58, 138), font=get_pillow_font(11, bold=True))
        d.text((505, sy + 20), desc[:62], fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
        if len(desc) > 62:
            d.text((505, sy + 36), desc[62:], fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
            sy += 64
        else:
            sy += 52

    path = os.path.join(SCREENSHOTS_DIR, 'screen_4_packing_sop.png')
    img.save(path)
    return path


def generate_screen_5_shiprocket_pickup():
    """Screenshot 5: Shiprocket Courier Pickup & Handover (Sample Data)"""
    w, h = 980, 580
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Logistics - Courier Pickup & Dispatch", "https://stallcart.in/orders/seller/shiprocket/pickup/")
    draw_stallcart_header(d, w, active_nav='orders')
    
    # Subheader
    d.text((30, 130), "Shiprocket Courier Pickup & Dispatch (कूरियर राइडर पिकअप एवं हैंडओवर)", fill=(15, 23, 42), font=get_pillow_font(16, bold=True))

    # Top Banner: Automated Pickup Token
    d.rounded_rectangle([(30, 160), (w - 30, 235)], radius=10, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((45, 172), "Pickup Token: PKP-DEMO-9821 · Scheduled for Today (आज पिकअप निर्धारित)", fill=(6, 95, 70), font=get_pillow_font(13, bold=True))
    d.text((45, 196), "Courier Partner: Delhivery Express via Shiprocket API · Service Type: Surface Fast Forward", fill=(15, 23, 42), font=get_pillow_font(11, bold=False))
    d.text((45, 214), "Assigned Rider: Ramesh Kumar (+91 97000 54321) · Expected Arrival: 02:00 PM - 04:00 PM", fill=(4, 120, 87), font=get_pillow_font(11, bold=True))

    # Tracking Milestones Box
    d.rounded_rectangle([(30, 255), (w - 30, 395)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 255), (w - 30, 288)], fill=(241, 245, 249))
    d.text((45, 267), "6-Stage Courier Transit Lifecycle (ऑर्डर की 6-चरणीय यात्रा)", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))

    # 6 Milestones
    milestones = [
        ("1. Order Packed", "विक्रेता ने पैक किया", True),
        ("2. Pickup Handover", "राइडर ने स्कैन किया", True),
        ("3. Hub In-Transit", "मुख्य हब पहुंचा", True),
        ("4. Dest. Sorting", "ग्राहक शहर पहुंचा", False),
        ("5. Out for Delivery", "डिलीवरी पर निकला", False),
        ("6. Delivered (OTP)", "ओटीपी से पुष्टि", False)
    ]
    mx = 45
    for title, desc, done in milestones:
        col_bg = (236, 253, 245) if done else (241, 245, 249)
        col_border = (167, 243, 208) if done else (203, 213, 225)
        col_title = (4, 120, 87) if done else (100, 116, 139)
        
        d.rounded_rectangle([(mx, 305), (mx + 135, 375)], radius=6, fill=col_bg, outline=col_border, width=1)
        d.text((mx + 10, 316), "✓ " + title if done else "○ " + title, fill=col_title, font=get_pillow_font(10, bold=True))
        d.text((mx + 10, 340), desc, fill=(71, 85, 105), font=get_pillow_font(9, bold=False))
        mx += 150

    # Handover Guidelines Card
    d.rounded_rectangle([(30, 415), (w - 30, h - 25)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 415), (w - 30, 448)], fill=(241, 245, 249))
    d.text((45, 426), "Rider Handover & OTP Verification Rules (राइडर को पैकेट सौंपने के नियम):", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))

    d.text((45, 460), "• कूरियर राइडर के आने पर उसका शिपरोकेट पहचान पत्र जांचें और अपने सामने AWB बारकोड स्कैन करवाएं।", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((45, 482), "• पिकअप रसीद (Manifest / Handover Acknowledgement) पर राइडर के हस्ताक्षर व मोबाइल नंबर अवश्य दर्ज करवाएं।", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((45, 504), "• गुप्त 4-अंकीय ओटीपी (Secret 4-Digit OTP): ग्राहक डिलीवरी के समय राइडर को ओटीपी देगा। इसके बिना डिलीवरी मान्य नहीं होती।", fill=(5, 150, 105), font=get_pillow_font(11, bold=True))
    d.text((45, 526), "• ओटीपी सत्यापन के तुरंत बाद ऑर्डर स्टॉलकार्ट पेआउट सेटलमेंट चक्र में शामिल हो जाता है।", fill=(37, 99, 235), font=get_pillow_font(11, bold=True))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_5_shiprocket_pickup.png')
    img.save(path)
    return path


def generate_screen_6_notification_emails():
    """Screenshot 6: Sample Seller Notification Emails (Order Alert & Payout Disbursal)"""
    w, h = 980, 540
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Automated Notifications Preview", "https://mail.google.com/")
    
    # Left Email: New Order Received
    d.rounded_rectangle([(40, 130), (480, h - 25)], radius=10, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.rectangle([(40, 130), (480, 175)], fill=(40, 116, 240))
    d.text((55, 145), "StallCart: New Order Received! नया ऑर्डर 🛒", fill=(255, 255, 255), font=get_pillow_font(13, bold=True))

    d.text((55, 190), "Dear Apex Trends Fashion Hub (Sample Seller),", fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
    d.text((55, 210), "आपको स्टॉलकार्ट पर एक नया ऑर्डर प्राप्त हुआ है!", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))

    d.rounded_rectangle([(55, 235), (465, 360)], radius=6, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((70, 248), "Order Number: #ORD-SAMPLE-202611-01", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((70, 270), "Item: Men's Classic Slim Fit Cotton Shirt", fill=(15, 23, 42), font=get_pillow_font(11, bold=False))
    d.text((70, 290), "Size: L  |  Color: Navy Blue  |  Qty: 1", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))
    d.text((70, 310), "Customer City: Bhopal, Madhya Pradesh", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
    d.text((70, 332), "Order Value: ₹499.00 (Prepaid Paid ✓)", fill=(5, 150, 105), font=get_pillow_font(11, bold=True))

    d.text((55, 380), "Action Required:", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((55, 400), "कृपया 24 घंटे के भीतर ऑर्डर पैक करके 'Ready for Pickup' करें।", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
    d.text((55, 420), "टैक्स इनवॉइस एवं शिपिंग लेबल अपने सेलर डैशबोर्ड से डाउनलोड करें।", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))

    d.rounded_rectangle([(55, 445), (230, 478)], radius=6, fill=(40, 116, 240))
    d.text((75, 455), "Open Seller Panel →", fill=(255, 255, 255), font=get_pillow_font(11, bold=True))
    d.text((55, 490), "Helpdesk Phone: +91 7307383046", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    # Right Email: Payout Disbursed
    d.rounded_rectangle([(500, 130), (940, h - 25)], radius=10, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.rectangle([(500, 130), (940, 175)], fill=(5, 150, 105))
    d.text((520, 145), "StallCart: Payout Disbursed! पेआउट सफल 💸", fill=(255, 255, 255), font=get_pillow_font(13, bold=True))

    d.text((520, 190), "Dear Apex Trends Fashion Hub (Sample Seller),", fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
    d.text((520, 210), "आपके बैंक खाते में पेआउट ट्रांसफर कर दिया गया है।", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))

    d.rounded_rectangle([(520, 235), (920, 360)], radius=6, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((535, 248), "Settlement Batch: SET-SAMPLE-202611-01", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((535, 270), "Amount Disbursed: ₹424.15", fill=(4, 120, 87), font=get_pillow_font(14, bold=True))
    d.text((535, 295), "Bank: HDFC Bank (••••5678 Encrypted)", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((535, 315), "IFSC Code: HDFC0001234", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((535, 335), "Bank UTR: CMS987654321012 (Verified ✓)", fill=(37, 99, 235), font=get_pillow_font(11, bold=True))

    d.text((520, 380), "Order Settled:", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((520, 400), "• #ORD-SAMPLE-202611-01 : Men's Cotton Shirt x1", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
    d.text((520, 420), "Status: राशि आपके खाते में क्रेडिट हो चुकी है।", fill=(5, 150, 105), font=get_pillow_font(10, bold=True))

    d.rounded_rectangle([(520, 445), (710, 478)], radius=6, fill=(5, 150, 105))
    d.text((540, 455), "View Payout Ledger →", fill=(255, 255, 255), font=get_pillow_font(11, bold=True))
    d.text((520, 490), "Email: stallcartsupport@gmail.com", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_6_notification_emails.png')
    img.save(path)
    return path


def generate_screen_7_settlement_statement():
    """Screenshot 7: StallCart Real Settlements & Payouts Dashboard with UTR (Sample Data)"""
    w, h = 980, 580
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller Settlements & Payouts", "https://stallcart.in/orders/admin/settlements/")
    draw_stallcart_header(d, w, active_nav='payouts')
    
    # Header
    d.text((30, 128), "Seller Settlements & Payouts (विक्रेता भुगतान एवं बैंक UTR ऑडिट)", fill=(15, 23, 42), font=get_pillow_font(16, bold=True))

    # Top Financial Cards
    cards = [
        ("Total Settled (सफल भुगतान)", "₹ 424.15", "Direct credited to bank", (5, 150, 105)),
        ("Commission Earned (कमीशन)", "₹ 74.85", "15% platform margin", (37, 99, 235)),
        ("Total Payout Due (बकाया राशि)", "₹ 424.15", "Delivered batches", (217, 119, 6)),
        ("Pending Batches (लंबित)", "₹ 0.00", "Awaiting disbursement", (100, 116, 139))
    ]
    cx = 30
    for title, val, sub, col in cards:
        d.rounded_rectangle([(cx, 155), (cx + 220, 225)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        d.text((cx + 14, 166), title, fill=(100, 116, 139), font=get_pillow_font(10, bold=False))
        d.text((cx + 14, 184), val, fill=col, font=get_pillow_font(18, bold=True))
        d.text((cx + 14, 206), sub, fill=(148, 163, 184), font=get_pillow_font(9, bold=False))
        cx += 235

    # Table Container
    d.rounded_rectangle([(30, 245), (w - 30, h - 25)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 245), (w - 30, 280)], fill=(241, 245, 249))
    
    d.text((45, 256), "Settlement ID", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((190, 256), "Date", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((310, 256), "Seller & Bank", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((540, 256), "Gross / Comm", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((680, 256), "Net Paid", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((790, 256), "Reference / UTR", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))

    # Row 1 (Sample Paid Batch)
    d.text((45, 298), "SET-SAMPLE-202611-01", fill=(37, 99, 235), font=get_pillow_font(11, bold=True))
    d.text((45, 316), "1 item [#ORD-SAMPLE-202611-01]", fill=(100, 116, 139), font=get_pillow_font(9, bold=False))

    d.text((190, 298), "20 Nov 2026", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((190, 314), "11:30 AM", fill=(148, 163, 184), font=get_pillow_font(9, bold=False))

    d.text((310, 298), "Apex Trends Fashion Hub", fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
    d.text((310, 316), "HDFC Bank (••••5678)", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    d.text((540, 298), "₹ 499.00", fill=(15, 23, 42), font=get_pillow_font(11, bold=False))
    d.text((540, 316), "Comm: ₹74.85 (15%)", fill=(220, 38, 38), font=get_pillow_font(9, bold=False))

    d.text((680, 298), "₹ 424.15", fill=(5, 150, 105), font=get_pillow_font(13, bold=True))
    d.rounded_rectangle([(680, 316), (730, 332)], radius=10, fill=(236, 253, 245))
    d.text((690, 319), "Paid ✓", fill=(4, 120, 87), font=get_pillow_font(9, bold=True))

    d.rounded_rectangle([(785, 292), (935, 328)], radius=5, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    d.text((795, 298), "CMS987654321012", fill=(29, 78, 216), font=get_pillow_font(10, bold=True))
    d.text((795, 313), "● Disbursed via Bank", fill=(5, 150, 105), font=get_pillow_font(8, bold=False))

    d.line([(40, 350), (w - 40, 350)], fill=(241, 245, 249), width=1)

    # Formula Explanatory Box
    d.rounded_rectangle([(45, 375), (w - 45, 525)], radius=8, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((65, 392), "💡 पारदर्शी कमाई और बैंक ट्रांसफर सूत्र (Sample Earning Formula):", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))
    d.text((65, 418), "Net Payout = Product Final Selling Price  -  (Product Price × Category Commission Rate)", fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
    d.text((65, 442), "• उदाहरण (Sample): ₹499.00 - 15% (₹74.85) = ₹424.15 शुद्ध भुगतान (Net Bank Credit).", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((65, 464), "• कोई छिपा हुआ शुल्क नहीं। पेमेंट गेटवे या लिस्टिंग चार्ज बिल्कुल शून्य (Zero Hidden Fees).", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((65, 486), "• हर भुगतान का बैंक यूटीआर नंबर (UTR No) उपलब्ध कराया जाता है जिसे आप अपनी पासबुक में देख सकते हैं।", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_7_settlement_statement.png')
    img.save(path)
    return path


# ─────────────────────────────────────────────────────────────
# 4. WEASYPRINT HTML & CSS BUILDER (MULTILINGUAL EDITIONS)
# ─────────────────────────────────────────────────────────────

def get_base64_image(filename):
    """Returns base64 encoded data URI for image file"""
    path = os.path.join(SCREENSHOTS_DIR, filename)
    if os.path.exists(path):
        with open(path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
            return f"data:image/png;base64,{encoded}"
    return ""


def generate_html_manual(lang='both'):
    """
    Builds the full 8-module manual as clean HTML with modern CSS.
    Supports 3 language modes:
    - 'hindi': Pure Hindi Devanagari edition
    - 'english': Complete English edition
    - 'both': Bilingual (Hindi + English side-by-side)
    """
    img1 = get_base64_image('screen_1_registration.png')
    img2 = get_base64_image('screen_2_product_listing.png')
    img3 = get_base64_image('screen_3_orders_dashboard.png')
    img4 = get_base64_image('screen_4_packing_sop.png')
    img5 = get_base64_image('screen_5_shiprocket_pickup.png')
    img6 = get_base64_image('screen_6_notification_emails.png')
    img7 = get_base64_image('screen_7_settlement_statement.png')

    is_hi = (lang == 'hindi')
    is_en = (lang == 'english')
    is_both = (lang == 'both')

    # Header / Title Strings
    if is_hi:
        doc_title = "स्टॉलकार्ट विक्रेता संचालन नियमावली और संपूर्ण गाइड (हिंदी संस्करण)"
        top_left_text = "STALLCART · विक्रेता संचालन नियमावली (हिंदी संस्करण)"
        top_right_text = "आधिकारिक पार्टनर हैंडबुक v2.0"
        badge_text = "STALLCART PARTNER ECOSYSTEM · विक्रेता सहयोग पोर्टल (Official Guide)"
        cover_heading = "विक्रेता संचालन नियमावली और संपूर्ण गाइड<br/><span class=\"brand\">StallCart</span> Seller Operations Manual"
        cover_sub = "<strong>पूर्ण हिंदी संस्करण (Hindi Edition):</strong> स्टॉलकार्ट (stallcart.in) पर विक्रेता पंजीकरण, उत्पाद लिस्टिंग, ऑर्डर पैकिंग मानक प्रक्रिया (SOP), शिपरोकेट कूरियर पिकअप और बैंक सेटलमेंट (UTR नंबर सहित) की संपूर्ण सचित्र मार्गदर्शिका।<br/><em>(सभी स्क्रीनशॉट और डेटा स्टॉलकार्ट वेब ऐप के मानक डेमो प्रारूप पर आधारित हैं — 100% Sample Demo Data)</em>"
    elif is_en:
        doc_title = "StallCart Official Seller Operations Manual (English Edition)"
        top_left_text = "STALLCART · SELLER OPERATIONS MANUAL (ENGLISH EDITION)"
        top_right_text = "Official Partner Handbook v2.0"
        badge_text = "STALLCART PARTNER ECOSYSTEM · SELLER HUB (OFFICIAL GUIDE)"
        cover_heading = "Seller Operations Manual & Partner Handbook<br/><span class=\"brand\">StallCart</span> Seller Operations Manual"
        cover_sub = "<strong>Complete English Edition:</strong> A complete step-by-step practical guide to merchant registration, catalog listing, packaging SOP, Shiprocket courier dispatch, and direct bank settlements (including UTR verification) on stallcart.in.<br/><em>(All screenshots and sample data reflect standard demo formats — 100% Sample Demo Data)</em>"
    else:
        doc_title = "StallCart Official Seller Operations Manual (Bilingual: Hindi & English)"
        top_left_text = "STALLCART · SELLER OPERATIONS MANUAL (हिंदी एवं अंग्रेजी)"
        top_right_text = "Bilingual Partner Handbook v2.0"
        badge_text = "STALLCART PARTNER ECOSYSTEM · विक्रेता सहयोग पोर्टल (Official Guide)"
        cover_heading = "विक्रेता संचालन नियमावली और संपूर्ण गाइड<br/><span class=\"brand\">StallCart</span> Seller Operations Manual"
        cover_sub = "<strong>द्विभाषी संस्करण (Bilingual Hindi &amp; English Edition):</strong> स्टॉलकार्ट (stallcart.in) पर विक्रेता पंजीकरण, उत्पाद लिस्टिंग, ऑर्डर पैकिंग मानक प्रक्रिया (SOP), शिपरोकेट कूरियर पिकअप और बैंक सेटलमेंट (UTR नंबर सहित) की संपूर्ण सचित्र मार्गदर्शिका।<br/><em>(सभी स्क्रीनशॉट और डेटा स्टॉलकार्ट वेब ऐप के मानक डेमो प्रारूप पर आधारित हैं — 100% Sample Demo Data)</em>"

    html = f"""<!DOCTYPE html>
<html lang="{'hi' if is_hi else 'en'}">
<head>
<meta charset="utf-8">
<title>{doc_title}</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    @page {{
        size: A4;
        margin: 20mm 15mm 20mm 15mm;
        @top-left {{
            content: "{top_left_text}";
            font-family: 'Plus Jakarta Sans', 'Noto Sans Devanagari', sans-serif;
            font-size: 8pt;
            font-weight: 700;
            color: #0f172a;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 4px;
        }}
        @top-right {{
            content: "{top_right_text}";
            font-family: 'Plus Jakarta Sans', 'Noto Sans Devanagari', sans-serif;
            font-size: 8pt;
            color: #64748b;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 4px;
        }}
        @bottom-left {{
            content: "© 2026 StallCart Platform · हेल्पलाइन: +91 7307383046 · stallcartsupport@gmail.com";
            font-family: 'Plus Jakarta Sans', 'Noto Sans Devanagari', sans-serif;
            font-size: 8pt;
            color: #64748b;
            border-top: 1px solid #e2e8f0;
            padding-top: 4px;
        }}
        @bottom-right {{
            content: "Page " counter(page) " of " counter(pages);
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 8pt;
            color: #64748b;
            border-top: 1px solid #e2e8f0;
            padding-top: 4px;
        }}
    }}

    @page :first {{
        @top-left {{ content: normal; border: none; }}
        @top-right {{ content: normal; border: none; }}
        @bottom-left {{ content: normal; border: none; }}
        @bottom-right {{ content: normal; border: none; }}
    }}

    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}

    body {{
        font-family: 'Noto Sans Devanagari', 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
        font-size: 9.5pt;
        line-height: 1.48;
        color: #1e293b;
        background: #ffffff;
    }}

    .page-break {{
        page-break-after: always;
    }}

    .badge-wrap {{
        display: inline-block;
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        color: #047857;
        font-size: 8.5pt;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 4px;
        margin-bottom: 14px;
        letter-spacing: 0.5px;
    }}

    h1.cover-title {{
        font-size: 22pt;
        line-height: 1.25;
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 8px;
    }}

    .cover-title span.brand {{
        color: #2874f0;
    }}

    p.cover-sub {{
        font-size: 10pt;
        line-height: 1.5;
        color: #475569;
        margin-bottom: 16px;
    }}

    .divider {{
        height: 3px;
        background: linear-gradient(90deg, #2874f0 0%, #059669 100%);
        border: none;
        margin: 14px 0 20px 0;
        border-radius: 2px;
    }}

    .meta-grid {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 22px;
    }}

    .meta-grid td {{
        width: 50%;
        padding: 8px 12px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        font-size: 9pt;
        vertical-align: top;
    }}

    .meta-grid td strong {{
        color: #0f172a;
    }}

    .toc-box {{
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        padding: 14px 18px;
        margin-top: 10px;
    }}

    .toc-title {{
        font-size: 11pt;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 10px;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 6px;
    }}

    .toc-item {{
        font-size: 8.8pt;
        line-height: 1.6;
        color: #334155;
    }}

    .toc-item strong {{
        color: #2874f0;
    }}

    /* Module Page Styles */
    .module-header {{
        border-bottom: 2px solid #2874f0;
        padding-bottom: 6px;
        margin-bottom: 10px;
    }}

    .module-title-hi {{
        font-size: 14pt;
        font-weight: 800;
        color: #0f172a;
    }}

    .module-title-en {{
        font-size: 10.5pt;
        font-weight: 600;
        color: #059669;
    }}

    .bilingual-lead {{
        font-size: 9pt;
        line-height: 1.45;
        color: #334155;
        margin-bottom: 10px;
        background: #f8fafc;
        border-left: 3px solid #2874f0;
        padding: 6px 10px;
        border-radius: 0 4px 4px 0;
    }}

    .section-title {{
        font-size: 10pt;
        font-weight: 700;
        color: #0f172a;
        margin: 8px 0 4px 0;
    }}

    ul.steps-list {{
        margin-left: 18px;
        margin-bottom: 10px;
    }}

    ul.steps-list li {{
        font-size: 8.8pt;
        line-height: 1.42;
        color: #1e293b;
        margin-bottom: 4px;
    }}

    ul.steps-list li strong {{
        color: #0f172a;
    }}

    code {{
        font-family: monospace;
        background: #f1f5f9;
        color: #0f172a;
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 8.5pt;
    }}

    .figure-wrap {{
        text-align: center;
        margin: 8px 0 4px 0;
    }}

    .figure-wrap img {{
        max-width: 100%;
        max-height: 290px;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.06);
    }}

    .caption {{
        font-size: 8pt;
        color: #64748b;
        text-align: center;
        margin-top: 4px;
        font-style: italic;
    }}

    table.info-table {{
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0 10px 0;
        font-size: 8.5pt;
    }}

    table.info-table th {{
        background: #f1f5f9;
        color: #0f172a;
        font-weight: 700;
        text-align: left;
        padding: 6px 10px;
        border: 1px solid #cbd5e1;
    }}

    table.info-table td {{
        padding: 5px 10px;
        border: 1px solid #e2e8f0;
        vertical-align: top;
        color: #334155;
    }}

    table.info-table tr:nth-child(even) td {{
        background: #f8fafc;
    }}

    .callout-box {{
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 6px;
        padding: 8px 12px;
        margin: 8px 0;
        font-size: 8.5pt;
        color: #1e3a8a;
    }}

    .callout-box strong {{
        color: #1e40af;
    }}
</style>
</head>
<body>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- COVER PAGE                                              -->
<!-- ═══════════════════════════════════════════════════════ -->
<div>
    <div style="height: 15px;"></div>
    <div class="badge-wrap">{badge_text}</div>
    
    <h1 class="cover-title">{cover_heading}</h1>
    <p class="cover-sub">{cover_sub}</p>

    <hr class="divider">

    <table class="meta-grid">
        <tr>
            <td><strong>संस्करण / Edition:</strong> Version 2.0 (Official Standard)</td>
            <td><strong>वेबसाइट / Portal:</strong> https://stallcart.in</td>
        </tr>
        <tr>
            <td><strong>लक्षित पाठक / Audience:</strong> {'सभी रजिस्टर्ड एवं नए विक्रेता' if not is_en else 'All Registered & Prospective Merchants'}</td>
            <td><strong>लॉजिस्टिक्स पार्टनर:</strong> Shiprocket &amp; Delhivery Express</td>
        </tr>
        <tr>
            <td><strong>व्हाट्सएप हेल्पलाइन:</strong> +91 7307383046</td>
            <td><strong>सपोर्ट ईमेल:</strong> stallcartsupport@gmail.com</td>
        </tr>
        <tr>
            <td><strong>भुगतान का माध्यम:</strong> {'सीधा बैंक ट्रांसफर (NEFT / UPI / UTR)' if not is_en else 'Direct Bank Transfer (NEFT / UPI / UTR)'}</td>
            <td><strong>सेटलमेंट चक्र:</strong> {'डिलीवरी व 7-दिन रिटर्न अवधि पश्चात' if not is_en else 'Post Delivery & 7-Day Return Window'}</td>
        </tr>
    </table>

    <div class="toc-box">
        <div class="toc-title">{'विषय सूची / Table of Contents' if is_both else ('विषय सूची' if is_hi else 'Table of Contents')}</div>
        <div class="toc-item"><strong>{'मॉड्यूल 1' if not is_en else 'Module 1'}:</strong> {'विक्रेता खाता पंजीकरण, दुकान विवरण एवं बैंक KYC सत्यापन' if not is_en else 'Seller Onboarding & KYC Verification'}</div>
        <div class="toc-item"><strong>{'मॉड्यूल 2' if not is_en else 'Module 2'}:</strong> {'उत्पाद लिस्टिंग, फोटोग्राफी नियम, मूल्य निर्धारण एवं वेरिएंट सेटअप' if not is_en else 'Product Cataloging, Pricing, Images & Variant Setup'}</div>
        <div class="toc-item"><strong>{'मॉड्यूल 3' if not is_en else 'Module 3'}:</strong> {'ऑर्डर प्राप्ति चक्र एवं विक्रेता डैशबोर्ड का उपयोग' if not is_en else 'Order Receiving Lifecycle & Seller Dashboard'}</div>
        <div class="toc-item"><strong>{'मॉड्यूल 4' if not is_en else 'Module 4'}:</strong> {'सुरक्षित पैकेजिंग मानक प्रक्रिया (SOP) एवं टैक्स इनवॉइस मुद्रण' if not is_en else 'Packaging Standard Operating Procedure (SOP) & Tax Invoice'}</div>
        <div class="toc-item"><strong>{'मॉड्यूल 5' if not is_en else 'Module 5'}:</strong> {'शिपरोकेट कूरियर पिकअप, टोकन, बारकोड एवं सुरक्षित डिलीवरी ओटीपी' if not is_en else 'Courier Pickup Scheduling, Token & Secret OTP Delivery'}</div>
        <div class="toc-item"><strong>{'मॉड्यूल 6' if not is_en else 'Module 6'}:</strong> {'स्वचालित ईमेल सूचनाएं, एसएमएस एवं व्हाट्सएप अलर्ट के नमूने' if not is_en else 'Seller Transactional Notifications & Email Alerts'}</div>
        <div class="toc-item"><strong>{'मॉड्यूल 7' if not is_en else 'Module 7'}:</strong> {'पारदर्शी कमीशन कटौती, बैंक भुगतान एवं UTR ऑडिट ट्रेल' if not is_en else 'Settlements, Category Commissions & Bank UTR Audit'}</div>
        <div class="toc-item"><strong>{'मॉड्यूल 8' if not is_en else 'Module 8'}:</strong> {'ग्राहक रिटर्न, RTO प्रबंधन एवं विक्रेता सहायता केंद्र' if not is_en else 'Returns, RTO Management & Seller Support Helpdesk'}</div>
    </div>
</div>

<div class="page-break"></div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- MODULE 1: SELLER REGISTRATION & KYC                     -->
<!-- ═══════════════════════════════════════════════════════ -->
<div>
    <div class="module-header">
        <div class="module-title-hi">{'मॉड्यूल 1: विक्रेता खाता पंजीकरण और बैंक KYC सत्यापन' if not is_en else 'Module 1: Seller Onboarding & Bank KYC Verification'}</div>
        {f'<div class="module-title-en">Module 1: Seller Onboarding &amp; Bank KYC Verification</div>' if is_both else ''}
    </div>

    <div class="bilingual-lead">
        {f'<strong>English:</strong> To begin selling on StallCart, every merchant must complete the verified seller registration. This establishes an encrypted link for automated seller payouts directly into your bank account.<br/>' if not is_hi else ''}
        {f'<strong>हिंदी:</strong> स्टॉलकार्ट पर सामान बेचने के लिए सबसे पहले विक्रेता पंजीकरण पूरा करना अनिवार्य है। यह आपके बैंक खाते को सुरक्षित रूप से जोड़ता है ताकि आपकी बिक्री का पैसा सीधे आपके खाते में पहुंच सके।' if not is_en else ''}
    </div>

    <div class="section-title">{'चरणबद्ध प्रक्रिया / Step-by-Step Workflow:' if is_both else ('चरणबद्ध प्रक्रिया:' if is_hi else 'Step-by-Step Workflow:')}</div>
    <ul class="steps-list">
        <li><strong>{'पंजीकरण लिंक / Registration Portal' if not is_en else 'Registration Portal'}:</strong> <code>https://stallcart.in/accounts/seller/register/</code> {'पर जाएं या होमपेज पर Seller Panel पर क्लिक करें।' if not is_en else 'Visit portal or click Seller Panel on homepage.'}</li>
        <li><strong>{'दुकान एवं संपर्क / Business Identity' if not is_en else 'Business Identity'}:</strong> {'अपनी दुकान का नाम (Shop Name जैसे Apex Trends Fashion Hub), रजिस्टर्ड मोबाइल और ईमेल दर्ज करें।' if not is_en else 'Enter Shop Name (e.g., Apex Trends Fashion Hub), verified phone and email.'}</li>
        <li><strong>{'पिकअप पता और पिनकोड / Pickup Address' if not is_en else 'Pickup Address & PIN'}:</strong> {'वह सटीक गोदाम/दुकान का पता और 6-अंकीय पिनकोड (उदा. 452001) दर्ज करें जहां से कूरियर राइडर पैकेट उठाएगा।' if not is_en else 'Provide complete warehouse address & 6-digit postal pincode (e.g., 452001) for courier pickup.'}</li>
        <li><strong>{'बैंक खाता विवरण / Bank Details for Payout' if not is_en else 'Bank Account for Payout'}:</strong> {'बैंक का नाम (जैसे HDFC Bank), खाता संख्या, और IFSC कोड दर्ज करें। सभी भुगतान इसी खाते में जाएंगे।' if not is_en else 'Enter Bank Name (e.g., HDFC Bank), Account Number, and IFSC code for direct payouts.'}</li>
        <li><strong>{'केवाईसी सत्यापन / KYC Verification' if not is_en else 'KYC Verification'}:</strong> {'स्टॉलकार्ट एडमिन 24 घंटे के भीतर विवरण सत्यापित करता है और आपका खाता KYC Approved ✓ हो जाता है।' if not is_en else 'StallCart operations team verifies bank & details within 24 hours to grant KYC Approved ✓ status.'}</li>
    </ul>

    <div class="figure-wrap">
        <img src="{img1}" alt="Seller Registration Screen">
        <div class="caption">{'चित्र 1.1: स्टॉलकार्ट विक्रेता पंजीकरण एवं बैंक खाता सत्यापन स्क्रीन (Seller Registration Form - Sample Demo Data)' if not is_en else 'Figure 1.1: StallCart Seller Registration & Bank KYC Verification Screen (Sample Demo Data)'}</div>
    </div>
</div>

<div class="page-break"></div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- MODULE 2: PRODUCT LISTING & VARIANTS                    -->
<!-- ═══════════════════════════════════════════════════════ -->
<div>
    <div class="module-header">
        <div class="module-title-hi">{'मॉड्यूल 2: उत्पाद लिस्टिंग, फोटो नियम और वेरिएंट सेटअप' if not is_en else 'Module 2: Product Cataloging, Pricing, Images & Variant Setup'}</div>
        {f'<div class="module-title-en">Module 2: Product Cataloging, Pricing, Images &amp; Variant Setup</div>' if is_both else ''}
    </div>

    <div class="bilingual-lead">
        {f'<strong>English:</strong> Listing attractive products with accurate pricing and high-definition photography is essential to maximize sales and reduce return rates.<br/>' if not is_hi else ''}
        {f'<strong>हिंदी:</strong> उत्पाद की सही जानकारी, उचित मूल्य और साफ फोटो डालने से ग्राहक का भरोसा बढ़ता है और बिक्री तेज होती है।' if not is_en else ''}
    </div>

    <div class="section-title">{'मुख्य नियम एवं दिशानिर्देश / Listing Guidelines:' if is_both else ('मुख्य नियम एवं दिशानिर्देश:' if is_hi else 'Listing Guidelines:')}</div>
    <ul class="steps-list">
        <li><strong>{'उत्पाद का शीर्षक (Title)' if not is_en else 'Product Title'}:</strong> {'ब्रांड नाम, प्रमुख सामग्री या साइज स्पष्ट लिखें (उदा. Men\'s Classic Slim Fit Cotton Casual Shirt - Navy Blue)।' if not is_en else 'Specify brand, key fabric, and color (e.g., Men\'s Classic Slim Fit Cotton Casual Shirt - Navy Blue).'}</li>
        <li><strong>{'श्रेणी एवं कमीशन (Category & Commission)' if not is_en else 'Category & Commission'}:</strong> {'सही केटेगरी चुनें (उदा. Men\'s Fashion & Apparel)। उस केटेगरी का स्टॉलकार्ट कमीशन प्रतिशत (जैसे 15%) स्क्रीन पर दिखेगा।' if not is_en else 'Select correct category. Upfront category commission (e.g. 15%) is displayed transparently.'}</li>
        <li><strong>{'MRP बनाम सेलिंग प्राइस (Pricing)' if not is_en else 'MRP vs. Selling Price'}:</strong> {'अधिकतम खुदरा मूल्य (MRP जैसे ₹999) और अपना अंतिम बिक्री मूल्य (Selling Price जैसे ₹499) दर्ज करें। 50% की छूट ग्राहकों को आकर्षित करती है।' if not is_en else 'Input MRP (e.g., ₹999) and final Selling Price (e.g., ₹499). Upfront discount badge drives shoppers.'}</li>
        <li><strong>{'स्टॉक (Inventory)' if not is_en else 'Inventory Count'}:</strong> {'अपने पास उपलब्ध स्टॉक दर्ज करें (जैसे 100 पीस)। स्टॉक 0 होने पर सिस्टम ऑटोमैटिक Out of Stock दिखाएगा।' if not is_en else 'Enter available quantity (e.g., 100 units). Auto marks Out of Stock when quantity reaches 0.'}</li>
        <li><strong>{'वेरिएंट्स मैट्रिक्स (Variants)' if not is_en else 'Variants Matrix'}:</strong> {'कपड़ों के लिए साइज (M, L, XL) और रंग चुनें। प्रत्येक साइज का स्टॉक अलग सेट करें।' if not is_en else 'Configure apparel size (M, L, XL) and color variations with isolated stock counters.'}</li>
        <li><strong>{'फोटो नियम (Photography SOP)' if not is_en else 'Photography SOP'}:</strong> {'साफ सफेद बैकग्राउंड में न्यूनतम 3 साफ तस्वीरें अपलोड करें (Front, Side, Fabric, Size Chart)।' if not is_en else 'Upload minimum 3 high-resolution photos on a clean white background (Front, Side, Detail).'}</li>
    </ul>

    <div class="figure-wrap">
        <img src="{img2}" alt="Product Listing Screen">
        <div class="caption">{'चित्र 2.1: स्टॉलकार्ट उत्पाद लिस्टिंग फॉर्म, लाइव वेरिएंट मैट्रिक्स और फोटो गैलरी (Add Product Form - Sample Demo Data)' if not is_en else 'Figure 2.1: StallCart Add Product Catalog Form, Variant Matrix & Gallery (Sample Demo Data)'}</div>
    </div>
</div>

<div class="page-break"></div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- MODULE 3: ORDER RECEIVING & DASHBOARD                   -->
<!-- ═══════════════════════════════════════════════════════ -->
<div>
    <div class="module-header">
        <div class="module-title-hi">{'मॉड्यूल 3: ऑर्डर प्राप्ति चक्र और विक्रेता डैशबोर्ड' if not is_en else 'Module 3: Order Receiving Lifecycle & Seller Dashboard'}</div>
        {f'<div class="module-title-en">Module 3: Order Receiving Lifecycle &amp; Seller Dashboard</div>' if is_both else ''}
    </div>

    <div class="bilingual-lead">
        {f'<strong>English:</strong> When a shopper purchases your product, the order is immediately dispatched to your dedicated seller dashboard at <code>/orders/seller/orders/</code>.<br/>' if not is_hi else ''}
        {f'<strong>हिंदी:</strong> जब भी कोई ग्राहक आपका सामान खरीदेगा, ऑर्डर तुरंत आपके सेलर डैशबोर्ड पर आ जाएगा और आपको तुरंत ईमेल/एसएमएस प्राप्त होगा।' if not is_en else ''}
    </div>

    <div class="section-title">{'ऑर्डर के विभिन्न चरण / Order Status Stages:' if is_both else ('ऑर्डर के विभिन्न चरण:' if is_hi else 'Order Status Stages:')}</div>
    <table class="info-table">
        <tr>
            <th style="width: 25%;">{'Status / स्थिति' if is_both else ('स्थिति' if is_hi else 'Status')}</th>
            <th>{'अर्थ एवं विक्रेता द्वारा की जाने वाली कार्रवाई (Action Required)' if not is_en else 'Meaning & Required Seller Action'}</th>
        </tr>
        <tr>
            <td><strong>Pending / New</strong><br/>{'(नया ऑर्डर)' if not is_en else '(Customer Ordered)'}</td>
            <td>{'ग्राहक ने भुगतान कर दिया है। विक्रेता को तुरंत Accept & Pack Order पर क्लिक करना चाहिए।' if not is_en else 'Shopper completed payment. Seller must click Accept & Pack Order within 24 hours.'}</td>
        </tr>
        <tr>
            <td><strong>Ready for Pickup</strong><br/>{'(पिकअप हेतु तैयार)' if not is_en else '(Manifest Ready)'}</td>
            <td>{'विक्रेता ने पैकेट तैयार कर लिया है। सिस्टम कूरियर राइडर असाइन करता है और पिकअप टोकन जारी करता है।' if not is_en else 'Parcel packed. System generates pickup token and assigns Delhivery/Shiprocket rider.'}</td>
        </tr>
        <tr>
            <td><strong>In Transit</strong><br/>{'(रास्ते में)' if not is_en else '(Dispatched)'}</td>
            <td>{'कूरियर राइडर ने पैकेट स्कैन करके उठा लिया है। पैकेट मुख्य हब से होते हुए ग्राहक के शहर जा रहा है।' if not is_en else 'Courier scanned and picked up package from merchant warehouse, routed to destination hub.'}</td>
        </tr>
        <tr>
            <td><strong>Out for Delivery</strong><br/>{'(डिलीवरी पर)' if not is_en else '(Last Mile)'}</td>
            <td>{'पैकेट ग्राहक के नजदीकी हब पहुंच चुका है और डिलीवरी बॉय आज ग्राहक के पते पर डिलीवर करेगा।' if not is_en else 'Parcel reached destination city hub; delivery agent out for final delivery to customer address.'}</td>
        </tr>
        <tr>
            <td><strong>Delivered (OTP)</strong><br/>{'(डिलीवरी सफल)' if not is_en else '(OTP Verified)'}</td>
            <td>{'ग्राहक ने 4-अंकीय गुप्त ओटीपी दिया और डिलीवरी पूरी हुई। ऑर्डर अब बैंक सेटलमेंट सूची में शामिल हो गया है।' if not is_en else 'Customer provided secret 4-digit OTP to rider. Verified & queued for automated bank settlement.'}</td>
        </tr>
    </table>

    <div class="figure-wrap">
        <img src="{img3}" alt="Seller Orders Dashboard">
        <div class="caption">{'चित्र 3.1: स्टॉलकार्ट सेलर ऑर्डर्स डैशबोर्ड, स्टेटस कार्ड्स एवं ग्राहक विवरण (Orders Received - Sample Demo Data)' if not is_en else 'Figure 3.1: StallCart Seller Orders Dashboard, Metric Cards & Order Records (Sample Demo Data)'}</div>
    </div>
</div>

<div class="page-break"></div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- MODULE 4: PACKAGING SOP & TAX INVOICE                   -->
<!-- ═══════════════════════════════════════════════════════ -->
<div>
    <div class="module-header">
        <div class="module-title-hi">{'मॉड्यूल 4: सुरक्षित पैकेजिंग मानक प्रक्रिया (SOP) और टैक्स इनवॉइस' if not is_en else 'Module 4: Packaging Standard Operating Procedure (SOP) & Tax Invoice'}</div>
        {f'<div class="module-title-en">Module 4: Packaging Standard Operating Procedure (SOP) &amp; Tax Invoice</div>' if is_both else ''}
    </div>

    <div class="bilingual-lead">
        {f'<strong>English:</strong> Proper packaging protects items during transit, minimizes returns, and creates a five-star unboxing experience.<br/>' if not is_hi else ''}
        {f'<strong>हिंदी:</strong> सही तरीके से पैकिंग करने से रास्ते में सामान सुरक्षित रहता है, ग्राहक संतुष्ट होता है और डैमेज रिटर्न की संभावना खत्म हो जाती है।' if not is_en else ''}
    </div>

    <div class="section-title">{'पैकिंग के 5 सुनहरे नियम / 5-Step Packing Protocol:' if is_both else ('पैकिंग के 5 सुनहरे नियम:' if is_hi else '5-Step Packaging Protocol:')}</div>
    <ul class="steps-list">
        <li><strong>{'1. क्वालिटी और साइज जांच (Quality Verification)' if not is_en else '1. Quality & Size Verification'}:</strong> {'पैकेट पैक करने से पहले चेक करें कि सही साइज (उदा. Size L) और सही कलर का डिफेक्ट-फ्री सामान है।' if not is_en else 'Cross-check accurate size (e.g. Size L), color code, and ensure 100% defect-free garment.'}</li>
        <li><strong>{'2. बबल रैप सुरक्षा (Bubble Wrap Layer)' if not is_en else '2. Waterproof & Bubble Wrap'}:</strong> {'परिधान या नाजुक सामान को कम से कम 2 परत वाटरप्रूफ पॉलीथीन या बबल रैप में लपेटें।' if not is_en else 'Wrap item in at least 2 protective layers of waterproof bubble wrap to seal against moisture.'}</li>
        <li><strong>{'3. मजबूत बाहरी बॉक्स/बैग (Outer Box)' if not is_en else '3. Corrugated Outer Box/Bag'}:</strong> {'स्टॉलकार्ट टेंपर-एविडेंट प्लास्टिक बैग या 3-प्लाई वाले मजबूत कार्डबोर्ड बॉक्स में पैक करें।' if not is_en else 'Pack inside tamper-evident StallCart security polybag or 3-ply heavy corrugated box.'}</li>
        <li><strong>{'4. टैक्स इनवॉइस अंदर रखें (Insert Tax Invoice)' if not is_en else '4. Insert Official Tax Invoice'}:</strong> {'सेलर पोर्टल से टैक्स इनवॉइस (Tax Invoice) डाउनलोड करके प्रिंट करें और पैकेट के अंदर डालें।' if not is_en else 'Print official Tax Invoice from seller dashboard and place securely inside the package.'}</li>
        <li><strong>{'5. कूरियर बारकोड लेबल चिपकाएं (Affix AWB Label)' if not is_en else '5. Affix Courier Barcode Flat'}:</strong> {'दिल्लीवरी/शिपरोकेट का AWB बारकोड लेबल बॉक्स के ऊपर सपाट चिपकाएं। बारकोड पर कभी सेलोटेप न लगाएं।' if not is_en else 'Affix Delhivery/Shiprocket AWB barcode flat on top face. Never place tape across barcode lines.'}</li>
    </ul>

    <div class="figure-wrap">
        <img src="{img4}" alt="Packaging SOP & Invoice">
        <div class="caption">{'चित्र 4.1: स्टॉलकार्ट आधिकारिक टैक्स इनवॉइस एवं 5-चरणीय पैकेजिंग मानक प्रक्रिया (Packaging SOP - Sample Demo Data)' if not is_en else 'Figure 4.1: Official Tax Invoice Sample & 5-Step Packaging SOP (Sample Demo Data)'}</div>
    </div>
</div>

<div class="page-break"></div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- MODULE 5: SHIPROCKET COURIER PICKUP & DISPATCH          -->
<!-- ═══════════════════════════════════════════════════════ -->
<div>
    <div class="module-header">
        <div class="module-title-hi">{'मॉड्यूल 5: शिपरोकेट कूरियर पिकअप, टोकन और सुरक्षित डिस्पैच' if not is_en else 'Module 5: Courier Pickup Scheduling, Token & Secret OTP Delivery'}</div>
        {f'<div class="module-title-en">Module 5: Courier Pickup Scheduling, Token &amp; Dispatch</div>' if is_both else ''}
    </div>

    <div class="bilingual-lead">
        {f'<strong>English:</strong> StallCart integrates directly with Shiprocket &amp; Delhivery Express. Sellers do not need separate courier contracts.<br/>' if not is_hi else ''}
        {f'<strong>हिंदी:</strong> स्टॉलकार्ट सीधे शिपरोकेट और दिल्लीवरी एक्सप्रेस से जुड़ा हुआ है। आपको कूरियर कंपनी से अलग से बात करने की जरूरत नहीं होती।' if not is_en else ''}
    </div>

    <div class="section-title">{'पिकअप हैंडओवर दिशानिर्देश / Handover Protocol:' if is_both else ('पिकअप हैंडओवर दिशानिर्देश:' if is_hi else 'Handover Protocol:')}</div>
    <ul class="steps-list">
        <li><strong>{'स्वचालित पिकअप असाइनमेंट' if not is_en else 'Automated Pickup Assignment'}:</strong> {'जब आप Ready for Pickup पर क्लिक करते हैं, तो सिस्टम कूरियर राइडर असाइन करके एक पिकअप टोकन (उदा. PKP-DEMO-9821) जारी करता है।' if not is_en else 'Marking Ready for Pickup instantly schedules courier pickup and issues a unique Pickup Token (e.g. PKP-DEMO-9821).'}</li>
        <li><strong>{'राइडर की जानकारी' if not is_en else 'Rider Identity & ETA'}:</strong> {'आपको कूरियर राइडर का नाम, मोबाइल नंबर और आगमन का समय डैशबोर्ड और एसएमएस पर मिल जाता है।' if not is_en else 'Assigned rider name, contact phone, and ETA window are communicated via SMS and dashboard.'}</li>
        <li><strong>{'बारकोड स्कैन करवाएं' if not is_en else 'On-spot Barcode Scan'}:</strong> {'जब राइडर आपके पते पर आए, तो उसका पहचान पत्र देखें और पैकेट सौंपकर अपने सामने बारकोड स्कैन करवाएं।' if not is_en else 'Verify rider ID badge and ensure courier executive scans the AWB barcode before leaving.'}</li>
        <li><strong>{'पिकअप रसीद (Manifest)' if not is_en else 'Handover Manifest Receipt'}:</strong> {'राइडर से डिजिटल या कागजी मैनिफेस्ट पर साइन व फोन नंबर लें।' if not is_en else 'Obtain rider signature and contact acknowledgment on digital or printed dispatch manifest.'}</li>
        <li><strong>{'सुरक्षित डिलीवरी ओटीपी (Secret 4-Digit OTP)' if not is_en else 'Secret 4-Digit Delivery OTP'}:</strong> {'डिलीवरी के समय ग्राहक द्वारा राइडर को 4-अंकीय गुप्त ओटीपी देना अनिवार्य है। इससे झूठी डिलीवरी क्लेम से विक्रेता को 100% सुरक्षा मिलती है।' if not is_en else 'Mandatory 4-digit secret OTP provided by buyer protects merchants against false non-delivery disputes.'}</li>
    </ul>

    <div class="figure-wrap">
        <img src="{img5}" alt="Shiprocket Tracking">
        <div class="caption">{'चित्र 5.1: कूरियर डिस्पैच प्रबंधन, शिपरोकेट पिकअप टोकन और 6-चरणीय डिलीवरी ट्रैकिंग (Shiprocket Tracking - Sample Demo Data)' if not is_en else 'Figure 5.1: Courier Dispatch Management, Pickup Token & 6-Stage Tracking Lifecycle (Sample Demo Data)'}</div>
    </div>
</div>

<div class="page-break"></div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- MODULE 6: NOTIFICATIONS & ALERTS                        -->
<!-- ═══════════════════════════════════════════════════════ -->
<div>
    <div class="module-header">
        <div class="module-title-hi">{'मॉड्यूल 6: लेन-देन सूचनाएं और ईमेल/एसएमएस के नमूने' if not is_en else 'Module 6: Seller Transactional Notifications & Email Alerts'}</div>
        {f'<div class="module-title-en">Module 6: Seller Transactional Notifications &amp; Alerts</div>' if is_both else ''}
    </div>

    <div class="bilingual-lead">
        {f'<strong>English:</strong> StallCart keeps sellers fully informed at every milestone via real-time automated emails, SMS, and WhatsApp alerts.<br/>' if not is_hi else ''}
        {f'<strong>हिंदी:</strong> स्टॉलकार्ट हर महत्वपूर्ण गतिविधि पर विक्रेता को रजिस्टर्ड ईमेल, एसएमएस और व्हाट्सएप पर संदेश भेजता है।' if not is_en else ''}
    </div>

    <div class="section-title">{'विक्रेता को प्राप्त होने वाले प्रमुख संदेश / Notification Types:' if is_both else ('विक्रेता को प्राप्त होने वाले प्रमुख संदेश:' if is_hi else 'Key Seller Notification Types:')}</div>
    <ul class="steps-list">
        <li><strong>{'1. नया ऑर्डर ईमेल (New Order Alert)' if not is_en else '1. New Order Received Alert'}:</strong> {'ग्राहक द्वारा ऑर्डर करते ही आता है। इसमें उत्पाद का नाम, साइज, मात्रा और पैकिंग की समय-सीमा लिखी होती है।' if not is_en else 'Dispatched immediately upon order placement; contains customer city, SKU variant, and 24-hr packing SLA.'}</li>
        <li><strong>{'2. कूरियर पिकअप अलर्ट (Pickup Confirmed)' if not is_en else '2. Courier Pickup Confirmation'}:</strong> {'जब कूरियर राइडर आपके पते से पैकेट स्कैन करके उठाता है, तो इसकी पुष्टि प्राप्त होती है।' if not is_en else 'Sent as soon as courier rider scans manifest and receives package from seller premises.'}</li>
        <li><strong>{'3. डिलीवरी अलर्ट (Delivery Confirmed)' if not is_en else '3. OTP Verified Delivery Notice'}:</strong> {'जब ग्राहक ओटीपी देकर पैकेट प्राप्त कर लेता है, तो डिलीवरी की पुष्टि का संदेश आता है।' if not is_en else 'Sent immediately when buyer provides delivery OTP to courier rider, queueing item for payout.'}</li>
        <li><strong>{'4. पेआउट जमा ईमेल (Settlement Disbursed)' if not is_en else '4. Payout Disbursed with Bank UTR'}:</strong> {'जब स्टॉलकार्ट आपके बैंक खाते में पैसे ट्रांसफर करता है, तो बैंक UTR नंबर और कटौती के पूरे विवरण के साथ ईमेल आता है।' if not is_en else 'Sent when funds are transferred to seller bank account, including bank UTR transaction reference.'}</li>
    </ul>

    <div class="figure-wrap">
        <img src="{img6}" alt="Email Notifications">
        <div class="caption">{'चित्र 6.1: स्टॉलकार्ट आधिकारिक ईमेल अलर्ट टेम्पलेट - नया ऑर्डर एवं बैंक पेआउट सूचना (Email Notifications - Sample Demo Data)' if not is_en else 'Figure 6.1: Official Transactional Email Templates - New Order & Bank Payout Notification (Sample Demo Data)'}</div>
    </div>
</div>

<div class="page-break"></div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- MODULE 7: SETTLEMENTS & BANK UTR                        -->
<!-- ═══════════════════════════════════════════════════════ -->
<div>
    <div class="module-header">
        <div class="module-title-hi">{'मॉड्यूल 7: कमीशन कटौती, बैंक भुगतान और UTR ऑडिट' if not is_en else 'Module 7: Settlements, Category Commissions & Bank Payouts'}</div>
        {f'<div class="module-title-en">Module 7: Settlements, Commissions &amp; Bank Payouts</div>' if is_both else ''}
    </div>

    <div class="bilingual-lead">
        {f'<strong>English:</strong> StallCart operates on a transparent, audit-ready financial settlement model. Sellers receive direct bank payouts with complete UTR references.<br/>' if not is_hi else ''}
        {f'<strong>हिंदी:</strong> स्टॉलकार्ट पर भुगतान पूरी तरह पारदर्शी है। हर बैंक ट्रांसफर के साथ बैंक यूटीआर नंबर (UTR No) दिया जाता है जिसे आप अपनी पासबुक में देख सकते हैं।' if not is_en else ''}
    </div>

    <div class="section-title">{'विक्रेता की शुद्ध कमाई का सूत्र / Earning Formula:' if is_both else ('विक्रेता की शुद्ध कमाई का सूत्र:' if is_hi else 'Net Seller Earning Formula:')}</div>
    <table class="info-table">
        <tr>
            <th style="width: 30%;">{'कमाई का सूत्र / Formula' if is_both else ('कमाई का सूत्र' if is_hi else 'Earning Formula')}</th>
            <td>
                <code>{'शुद्ध बैंक भुगतान = उत्पाद का अंतिम बिक्री मूल्य  -  प्लेटफ़ॉर्म केटेगरी कमीशन' if not is_en else 'Net Seller Payable = Item Selling Price  -  Platform Category Commission'}</code>
            </td>
        </tr>
        <tr>
            <th>{'वास्तविक उदाहरण / Example' if is_both else ('वास्तविक उदाहरण' if is_hi else 'Real Calculation Example')}</th>
            <td>{'बिक्री मूल्य (Selling Price): <strong>₹499.00</strong><br/>केटेगरी कमीशन (15%): -₹74.85<br/><strong>विक्रेता को शुद्ध बैंक ट्रांसफर: ₹424.15</strong>' if not is_en else 'Selling Price: <strong>₹499.00</strong><br/>Category Commission (15%): -₹74.85<br/><strong>Net Bank Credit to Seller: ₹424.15</strong>'}</td>
        </tr>
        <tr>
            <th>{'भुगतान का समय / Schedule' if not is_en else 'Payout Schedule'}</th>
            <td>{'ऑर्डर सफलतापूर्वक डिलीवर होने और 7-दिन की आसान रिटर्न अवधि पूरी होने के बाद सेटलमेंट किया जाता है।' if not is_en else 'Settled promptly after successful delivery and completion of the 7-day customer return window.'}</td>
        </tr>
        <tr>
            <th>{'ट्रांसफर का माध्यम / Mode' if not is_en else 'Payment Channel'}</th>
            <td>{'सीधा बैंक खाता ट्रांसफर (NEFT / RTGS / IMPS / UPI) अथवा RazorpayX इंस्टेंट पेआउट।' if not is_en else 'Direct Bank Transfer (NEFT / RTGS / IMPS / UPI) or automated RazorpayX instant disbursal.'}</td>
        </tr>
        <tr>
            <th>{'बैंक UTR नंबर / Proof' if not is_en else 'Bank UTR Audit Trail'}</th>
            <td>{'हर भुगतान के साथ बैंक यूटीआर नंबर (उदा. CMS987654321012) प्रदान किया जाता है।' if not is_en else 'Every payout includes verifiable bank UTR reference (e.g. CMS987654321012) for passbook audit.'}</td>
        </tr>
    </table>

    <div class="figure-wrap">
        <img src="{img7}" alt="Settlement Statement">
        <div class="caption">{'चित्र 7.1: स्टॉलकार्ट सेलर सेटलमेंट एवं पेआउट लेज़र स्क्रीन (Settlements & Payouts Dashboard - Sample Demo Data)' if not is_en else 'Figure 7.1: StallCart Seller Settlements Dashboard, UTR Ledger & Calculation Audit (Sample Demo Data)'}</div>
    </div>
</div>

<div class="page-break"></div>

<!-- ═══════════════════════════════════════════════════════ -->
<!-- MODULE 8: RETURNS, RTO & SELLER SUPPORT                 -->
<!-- ═══════════════════════════════════════════════════════ -->
<div>
    <div class="module-header">
        <div class="module-title-hi">{'मॉड्यूल 8: कस्टमर रिटर्न, RTO और हेल्पलाइन सपोर्ट' if not is_en else 'Module 8: Returns, RTO Management & Seller Support Helpdesk'}</div>
        {f'<div class="module-title-en">Module 8: Returns, RTO Management &amp; Seller Support</div>' if is_both else ''}
    </div>

    <div class="bilingual-lead">
        {f'<strong>English:</strong> Handling customer returns and unexpected transit issues smoothly is critical to maintaining a 5-star seller rating.<br/>' if not is_hi else ''}
        {f'<strong>हिंदी:</strong> किसी भी ई-कॉमर्स व्यवसाय में रिटर्न और RTO का सही प्रबंधन विक्रेता की रेटिंग और मुनाफे को सुरक्षित रखता है।' if not is_en else ''}
    </div>

    <div class="section-title">{'रिटर्न एवं RTO के नियम / Return & RTO Policies:' if is_both else ('रिटर्न एवं RTO के नियम:' if is_hi else 'Return & RTO Policies:')}</div>
    <ul class="steps-list">
        <li><strong>{'7-दिन की रिटर्न अवधि (7-Day Return)' if not is_en else '7-Day Return Window'}:</strong> {'ग्राहक केवल डिफेक्टिव, गलत साइज या टूटा सामान होने पर ही 7 दिन में रिटर्न का अनुरोध कर सकता है।' if not is_en else 'Shoppers can only initiate returns for defective, wrong-sized, or physically damaged items within 7 days.'}</li>
        <li><strong>{'विक्रेता द्वारा सामान की जांच (Inspection)' if not is_en else 'Seller Quality Inspection'}:</strong> {'कूरियर द्वारा लौटाया गया सामान आपके पते पर वापस आता है। विक्रेता द्वारा सामान की स्थिति जांचने के बाद ही रिफंड की पुष्टि होती है।' if not is_en else 'Returned goods are routed back to seller warehouse; refunds are verified post merchant inspection.'}</li>
        <li><strong>{'RTO (डिलीवरी न होना)' if not is_en else 'RTO (Non-Delivery to Buyer)'}:</strong> {'यदि ग्राहक 3 प्रयासों के बाद भी उपलब्ध नहीं होता, तो पैकेट RTO होकर आपके गोदाम में सुरक्षित लौट आता है। RTO पैकेट पर कोई प्लेटफ़ॉर्म कमीशन नहीं काटा जाता।' if not is_en else 'If customer is unavailable after 3 courier attempts, parcel is returned safely. ZERO platform commission is deducted on RTO.'}</li>
    </ul>

    <div class="section-title">{'स्टॉलकार्ट आधिकारिक सहायता केंद्र / Official Support Channels:' if is_both else ('स्टॉलकार्ट आधिकारिक सहायता केंद्र:' if is_hi else 'Official Support Channels:')}</div>
    <table class="info-table">
        <tr>
            <th style="width: 30%;">{'माध्यम / Channel' if is_both else ('माध्यम' if is_hi else 'Channel')}</th>
            <th>{'विवरण एवं समय / Contact Details' if is_both else ('विवरण एवं समय' if is_hi else 'Contact Details & Operating Hours')}</th>
        </tr>
        <tr>
            <td><strong>{'व्हाट्सएप सेलर डेस्क' if not is_en else 'WhatsApp Partner Desk'}</strong></td>
            <td><strong>+91 7307383046</strong> {'(पिकअप समस्या या ऑर्डर सहायता के लिए · प्रातः 9 बजे से रात्रि 9 बजे तक)' if not is_en else '(Pickup escalations & merchant support · 9 AM to 9 PM IST)'}</td>
        </tr>
        <tr>
            <td><strong>{'ईमेल सपोर्ट' if not is_en else 'Email Helpdesk'}</strong></td>
            <td><strong>stallcartsupport@gmail.com</strong> {'(उत्पाद कैटलॉग, बैंक खाता बदलाव या सेटलमेंट पूछताछ)' if not is_en else '(Catalog approvals, bank profile changes & payout inquiries)'}</td>
        </tr>
        <tr>
            <td><strong>{'वेबसाइट चैटबॉट' if not is_en else '24/7 AI Assistant'}</strong></td>
            <td>{'होमपेज (stallcart.in) पर 24/7 उपलब्ध। यहां से सीधे मैनुअल डाउनलोड कर सकते हैं।' if not is_en else 'Available 24/7 on stallcart.in. Direct one-click manual downloads in Hindi & English.'}</td>
        </tr>
        <tr>
            <td><strong>{'विक्रेता डैशबोर्ड' if not is_en else 'Seller Web Portal'}</strong></td>
            <td><code>https://stallcart.in/items/dashboard/</code> {'(लाइव स्टॉक, ऑर्डर और पेआउट नियंत्रण)' if not is_en else '(Live inventory, order fulfillment & settlement ledger)'}</td>
        </tr>
    </table>

    <div class="callout-box" style="margin-top: 15px; background: #f8fafc; border: 1.5px solid #2874f0; color: #0f172a;">
        <strong style="color: #2874f0; font-size: 10.5pt;">{'स्टॉलकार्ट परिवार में आपका स्वागत है! (Welcome to StallCart)' if not is_en else 'Welcome to the StallCart Merchant Family!'}</strong><br/>
        {'हम पूरे भारत में आपके व्यवसाय को बढ़ाने, तेज कूरियर डिलीवरी और समय पर पारदर्शी बैंक भुगतान देने के लिए समर्पित हैं। स्टॉलकार्ट का पार्टनर बनने के लिए धन्यवाद।' if not is_en else 'We are committed to scaling your business across India with fast doorstep pickups and guaranteed transparent bank settlements. Thank you for partnering with StallCart.'}
    </div>
</div>

</body>
</html>"""
    return html


# ─────────────────────────────────────────────────────────────
# 5. REPORTLAB FALLBACK BUILDER (For Environments without Pango)
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
        self.drawString(36, 810, "STALLCART · SELLER OPERATIONS MANUAL")
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawRightString(559, 810, "Partner Handbook v2.0")
        
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.75)
        self.line(36, 802, 559, 802)

        self.line(36, 45, 559, 45)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(36, 32, "© 2026 StallCart Platform · Helpline: +91 7307383046 · stallcartsupport@gmail.com")
        self.drawRightString(559, 32, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def build_pdf_reportlab(target_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    dev_font = register_reportlab_fonts()
    doc = SimpleDocTemplate(target_path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()

    brand_primary = colors.HexColor("#2874f0")
    brand_emerald = colors.HexColor("#059669")
    brand_navy = colors.HexColor("#0f172a")
    text_dark = colors.HexColor("#1e293b")
    text_muted = colors.HexColor("#64748b")

    title_style = ParagraphStyle('CoverTitle', parent=styles['Normal'], fontName=dev_font, fontSize=23, leading=28, textColor=brand_navy, spaceAfter=10)
    subtitle_style = ParagraphStyle('CoverSubtitle', parent=styles['Normal'], fontName=dev_font, fontSize=11, leading=16, textColor=text_muted, spaceAfter=18)
    h1_style = ParagraphStyle('Heading1_Custom', parent=styles['Heading1'], fontName=dev_font, fontSize=15, leading=20, textColor=brand_navy, spaceBefore=14, spaceAfter=6, keepWithNext=True)
    body_style = ParagraphStyle('Body_Custom', parent=styles['Normal'], fontName=dev_font, fontSize=9, leading=13.5, textColor=text_dark, spaceAfter=5)
    caption_style = ParagraphStyle('ImageCaption', parent=styles['Normal'], fontName=dev_font, fontSize=8, leading=11, textColor=text_muted, alignment=1, spaceBefore=4, spaceAfter=10)

    story = []
    story.append(Spacer(1, 30))
    story.append(Paragraph("विक्रेता संचालन नियमावली और संपूर्ण गाइड<br/>Seller Operations Manual &amp; Partner Handbook", title_style))
    story.append(Paragraph("StallCart Official Seller Operations Manual (Sample Demo Format).", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=brand_primary, spaceBefore=4, spaceAfter=18))

    s1_path = os.path.join(SCREENSHOTS_DIR, 'screen_1_registration.png')
    story.append(RLImage(s1_path, width=520, height=295))
    story.append(Paragraph("Figure 1.1: StallCart Seller Registration (Sample Demo Data)", caption_style))

    doc.build(story, canvasmaker=NumberedCanvas)


# ─────────────────────────────────────────────────────────────
# 6. MASTER BUILD DISPATCHER (BUILDS ALL 3 EDITIONS)
# ─────────────────────────────────────────────────────────────
def build_all_editions():
    """
    Compiles all 3 editions:
    1. 'hindi'   -> StallCart_Seller_Manual_Hindi.pdf
    2. 'english' -> StallCart_Seller_Manual_English.pdf
    3. 'both'    -> StallCart_Seller_Manual.pdf (and StallCart_Seller_Manual_Bilingual.pdf)
    """
    editions = [
        ('both', 'StallCart_Seller_Manual.pdf', 'Bilingual Edition (हिंदी + English)'),
        ('hindi', 'StallCart_Seller_Manual_Hindi.pdf', 'Hindi Edition (🇮🇳 पूर्ण हिंदी संस्करण)'),
        ('english', 'StallCart_Seller_Manual_English.pdf', 'English Edition (🇬🇧 Complete English)')
    ]

    for mode, filename, desc in editions:
        static_dest = os.path.join(STATIC_DOCS_DIR, filename)
        media_dest = os.path.join(MEDIA_MANUALS_DIR, filename)

        print(f"\n--- Compiling {desc} -> {filename} ---")
        compiled_ok = False
        try:
            import weasyprint
            print("Rendering with WeasyPrint (HarfBuzz OpenType Devanagari shaping engine)...")
            html = generate_html_manual(lang=mode)
            weasyprint.HTML(string=html, base_url=SCREENSHOTS_DIR).write_pdf(static_dest)
            print(f"✓ {filename} built successfully with WeasyPrint!")
            compiled_ok = True
        except Exception as e:
            print(f"[NOTE] WeasyPrint generation encountered: {e}")
            print("Falling back to ReportLab...")
            build_pdf_reportlab(static_dest)

        if os.path.exists(static_dest):
            shutil.copyfile(static_dest, media_dest)
            if mode == 'both':
                # Also save bilingual alias
                bilingual_alias = os.path.join(STATIC_DOCS_DIR, 'StallCart_Seller_Manual_Bilingual.pdf')
                shutil.copyfile(static_dest, bilingual_alias)
            print(f"✓ Copied to media path: {media_dest} ({os.path.getsize(static_dest)} bytes)")
        else:
            print(f"❌ Error: {filename} was not created!")


def main():
    print("=== Generating StallCart Web App Screenshot Mockups (100% Sample Data) ===")
    generate_screen_1_registration()
    generate_screen_2_product_listing()
    generate_screen_3_orders_dashboard()
    generate_screen_4_packing_sop()
    generate_screen_5_shiprocket_pickup()
    generate_screen_6_notification_emails()
    generate_screen_7_settlement_statement()
    print("All 7 screenshots generated successfully!")

    print("\n=== Building 3 Official Seller Manual Editions (Hindi, English, Bilingual) ===")
    build_all_editions()
    print("\n=== All Manual Editions Finished Successfully! ===")


if __name__ == '__main__':
    main()
