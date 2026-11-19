#!/usr/bin/env python3
"""
StallCart Official Seller Operations Manual & Handbook Generator (Bilingual: Hindi & English)
Faithfully renders:
1. Actual StallCart Web App UI mockups with Announcement Bar, StallCart Navbar, Real App Theme (#2874f0),
   and 100% FICTIONAL / SAMPLE DEMO DATA (No real seller from database).
2. Comprehensive, bilingual (Hindi Devanagari & English) multi-page PDF document with ReportLab.
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

    # Variant Matrix Table
    d.text((45, 395), "Size & Color Variants (वेरिएंट स्टॉक मैट्रिक्स):", fill=(30, 41, 59), font=get_pillow_font(12, bold=True))
    
    v_rows = [
        ("Size: M", "Color: Navy Blue", "₹ 499.00", "Stock: 35 Units"),
        ("Size: L", "Color: Navy Blue", "₹ 499.00", "Stock: 40 Units"),
        ("Size: XL", "Color: Navy Blue", "₹ 499.00", "Stock: 25 Units"),
    ]
    vy = 420
    for s_size, s_col, s_pr, s_st in v_rows:
        d.rounded_rectangle([(45, vy), (545, vy + 32)], radius=4, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
        d.text((60, vy + 8), f"● {s_size}  |  {s_col}  |  {s_pr}  |  {s_st}", fill=(30, 41, 59), font=get_pillow_font(11, bold=False))
        vy += 40

    # Right Column: Photo Upload
    d.rounded_rectangle([(580, 160), (w - 30, h - 25)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(580, 160), (w - 30, 192)], fill=(241, 245, 249))
    d.text((595, 170), "Product Gallery Photos (उत्पाद फोटो अपलोड)", fill=(30, 41, 59), font=get_pillow_font(13, bold=True))

    d.rounded_rectangle([(600, 210), (740, 340)], radius=8, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    d.text((620, 260), "📷 Front View", fill=(37, 99, 235), font=get_pillow_font(12, bold=True))
    d.text((630, 280), "Primary Photo ✓", fill=(5, 150, 105), font=get_pillow_font(10, bold=False))

    d.rounded_rectangle([(760, 210), (900, 340)], radius=8, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((785, 260), "📷 Side Angle", fill=(71, 85, 105), font=get_pillow_font(12, bold=False))
    d.text((795, 280), "Angle Photo 2", fill=(148, 163, 184), font=get_pillow_font(10, bold=False))

    d.rounded_rectangle([(600, 360), (740, 460)], radius=8, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((625, 400), "📷 Fabric Texture", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))

    d.rounded_rectangle([(760, 360), (900, 460)], radius=8, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((788, 400), "📷 Size Chart", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))

    d.rounded_rectangle([(600, 490), (900, 535)], radius=8, fill=(40, 116, 240))
    d.text((660, 505), "🚀 Publish Product (प्रकाशित करें)", fill=(255, 255, 255), font=get_pillow_font(14, bold=True))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_2_product_listing.png')
    img.save(path)
    return path


def generate_screen_3_orders_dashboard():
    """Screenshot 3: StallCart Seller Orders Dashboard (Sample Data)"""
    w, h = 980, 580
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller Orders", "https://stallcart.in/orders/seller/orders/")
    draw_stallcart_header(d, w, active_nav='orders')
    
    # Subheader & Stats Row
    d.text((30, 128), "Orders Received · ऑर्डर प्रबंधन (Apex Trends Demo Seller)", fill=(15, 23, 42), font=get_pillow_font(16, bold=True))

    stat_cards = [
        ("Total Items", "8", (15, 23, 42)),
        ("Pending", "1", (217, 119, 6)),
        ("Delivered", "2", (5, 150, 105)),
        ("Total Profit", "₹1,240.00", (37, 99, 235)),
        ("Received Payout", "₹848.30", (5, 150, 105)),
        ("Due from Admin", "₹391.70", (217, 119, 6))
    ]
    sx = 30
    for st_title, st_val, st_col in stat_cards:
        d.rounded_rectangle([(sx, 155), (sx + 145, 205)], radius=8, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        d.text((sx + 12, 163), st_val, fill=st_col, font=get_pillow_font(15, bold=True))
        d.text((sx + 12, 185), st_title, fill=(100, 116, 139), font=get_pillow_font(9, bold=True))
        sx += 155

    # Order Card 1 (Sample Action Required)
    d.rounded_rectangle([(30, 220), (w - 30, 375)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 220), (w - 30, 260)], fill=(248, 250, 252))
    d.line([(30, 260), (w - 30, 260)], fill=(226, 232, 240), width=1)
    
    d.text((45, 232), "ORDER #ORD-SAMPLE-202611-01", fill=(15, 23, 42), font=get_pillow_font(13, bold=True))
    d.text((340, 234), "Placed: 20 Nov 2026, 10:15 AM", fill=(100, 116, 139), font=get_pillow_font(11, bold=False))
    
    d.rounded_rectangle([(w - 240, 228), (w - 45, 254)], radius=12, fill=(254, 243, 199))
    d.text((w - 225, 234), "⚡ ACTION REQUIRED (नया ऑर्डर)", fill=(180, 83, 9), font=get_pillow_font(10, bold=True))

    d.text((45, 275), "Customer: Priya Verma (Sample Customer)  |  Delivery: Gomti Nagar, Lucknow, UP - 226001", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))
    d.text((45, 298), "Item: Men's Classic Slim Fit Cotton Casual Shirt (Size: L, Navy Blue) x 1", fill=(15, 23, 42), font=get_pillow_font(13, bold=True))
    d.text((45, 322), "Selling Price: ₹499.00  |  Platform Comm: 15% (-₹74.85)  |  Net Seller Earnings: ₹424.15", fill=(5, 150, 105), font=get_pillow_font(12, bold=True))

    d.rounded_rectangle([(w - 230, 280), (w - 45, 314)], radius=6, fill=(5, 150, 105))
    d.text((w - 215, 290), "✓ Accept & Pack (स्वीकार करें)", fill=(255, 255, 255), font=get_pillow_font(11, bold=True))

    d.rounded_rectangle([(w - 230, 324), (w - 45, 358)], radius=6, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.text((w - 215, 334), "📄 Print Tax Invoice (इनवॉइस)", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))

    # Order Card 2 (Sample Ready for Pickup)
    d.rounded_rectangle([(30, 395), (w - 30, 545)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 395), (w - 30, 435)], fill=(248, 250, 252))
    d.line([(30, 435), (w - 30, 435)], fill=(226, 232, 240), width=1)
    
    d.text((45, 407), "ORDER #ORD-SAMPLE-202611-02", fill=(15, 23, 42), font=get_pillow_font(13, bold=True))
    d.rounded_rectangle([(w - 240, 403), (w - 45, 429)], radius=12, fill=(239, 246, 255))
    d.text((w - 225, 409), "🚚 READY FOR PICKUP (पिकअप हेतु तैयार)", fill=(29, 78, 216), font=get_pillow_font(10, bold=True))
    
    d.text((45, 450), "Logistics: Delhivery Express  |  AWB: 143200987654  |  Pickup Token: PKP-DEMO-9821", fill=(37, 99, 235), font=get_pillow_font(12, bold=True))
    d.text((45, 475), "Item: Women's Embroidered Cotton Kurti (Size: M, Teal) x 1  |  Net Seller Payout: ₹552.50", fill=(15, 23, 42), font=get_pillow_font(13, bold=True))
    d.text((45, 500), "Status: Hand over parcel to Delhivery courier rider upon physical barcode scan.", fill=(100, 116, 139), font=get_pillow_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_3_orders_dashboard.png')
    img.save(path)
    return path


def generate_screen_4_packing_sop():
    """Screenshot 4: StallCart Packaging SOP & Real Tax Invoice Layout (Sample Data)"""
    w, h = 980, 580
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart - Tax Invoice & Packaging SOP", "https://stallcart.in/orders/order/ORD-SAMPLE-202611-01/invoice/")
    draw_stallcart_header(d, w, active_nav='orders')
    
    # Left Column: Exact StallCart Tax Invoice layout
    d.rounded_rectangle([(30, 130), (460, h - 25)], radius=8, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    
    # Invoice Header
    d.text((45, 145), "TAX INVOICE / PACKING SLIP", fill=(15, 23, 42), font=get_pillow_font(13, bold=True))
    d.text((45, 163), "StallCart E-Commerce Platform", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))
    d.line([(45, 180), (445, 180)], fill=(226, 232, 240), width=1)
    
    d.text((45, 190), "Order ID: #ORD-SAMPLE-202611-01", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((45, 208), "Invoice No: SC-INV-SAMPLE-0089", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
    d.text((45, 226), "Seller: Apex Trends Fashion Hub (Sample Demo)", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
    d.text((45, 244), "Buyer: Priya Verma (Sample Customer), Lucknow UP", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
    
    # Invoice Items Table
    d.rectangle([(45, 268), (445, 292)], fill=(241, 245, 249))
    d.text((50, 274), "Item Description", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((290, 274), "Qty", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    d.text((360, 274), "Total", fill=(30, 41, 59), font=get_pillow_font(10, bold=True))
    
    d.text((50, 302), "Men's Cotton Shirt (Size L)", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((295, 302), "1", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((360, 302), "₹ 499.00", fill=(15, 23, 42), font=get_pillow_font(10, bold=True))

    # Barcode
    d.rectangle([(45, 350), (445, 430)], fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    for bx in range(65, 425, 6):
        d.line([(bx, 362), (bx, 405)], fill=(0, 0, 0), width=3 if bx % 4 == 0 else 1)
    d.text((160, 412), "* 143200987654 *", fill=(0, 0, 0), font=get_pillow_font(11, bold=True))

    d.text((45, 450), "📌 Note: Fold Invoice and place inside clear pouch.", fill=(180, 83, 9), font=get_pillow_font(10, bold=True))
    d.text((45, 470), "AWB barcode label must be on outermost box face.", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

    # Right Column: 5 Packaging Rules
    d.rounded_rectangle([(480, 130), (w - 30, h - 25)], radius=8, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.text((505, 150), "Packaging Guidelines · 5 सुनहरे नियम (SOP)", fill=(4, 120, 87), font=get_pillow_font(15, bold=True))
    
    steps = [
        ("Step 1: Quality Check (क्वालिटी और साइज जांचें)", "उत्पाद की सही जांच करें। सही साइज (L) और कलर वेरिएंट सुनिश्चित करें।"),
        ("Step 2: Bubble Wrap (सुरक्षित रैपिंग)", "कम से कम 2 लेयर बबल रैप लगाएं ताकि रास्ते में सामान टूटे या खराब न हो।"),
        ("Step 3: Sturdy Outer Box (मजबूत बॉक्स)", "स्टॉलकार्ट टेंपर-प्रूफ बैग या 3-प्लाई कोरुगेटेड बॉक्स में पैक करें।"),
        ("Step 4: Barcode Label (बारकोड लेबल)", "दिल्लीवरी/शिपरोकेट का शिपिंग लेबल बाहर चिपकाएं। बारकोड पर टेप न लगाएं।"),
        ("Step 5: Courier Handover (कूरियर हैंडओवर)", "राइडर का आईडी देखें, पैकेट स्कैन करवाएं और डिलीवरी टोकन नोट करें।")
    ]
    sy = 195
    for s_title, s_desc in steps:
        d.ellipse([(505, sy), (525, sy + 20)], fill=(5, 150, 105))
        d.text((511, sy + 2), "✓", fill=(255, 255, 255), font=get_pillow_font(12, bold=True))
        d.text((535, sy), s_title, fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
        d.text((535, sy + 20), s_desc, fill=(100, 116, 139), font=get_pillow_font(10, bold=False))
        sy += 68

    path = os.path.join(SCREENSHOTS_DIR, 'screen_4_packing_sop.png')
    img.save(path)
    return path


def generate_screen_5_shiprocket_pickup():
    """Screenshot 5: Shiprocket & Delhivery Express Courier Flow (Sample Data)"""
    w, h = 980, 580
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Logistics - Courier Dispatch & OTP Delivery", "https://stallcart.in/orders/track/ORD-SAMPLE-202611-01/")
    draw_stallcart_header(d, w, active_nav='orders')
    
    d.text((30, 130), "Automated Logistics & Courier Tracking (कूरियर पिकअप एवं सुरक्षित ओटीपी)", fill=(15, 23, 42), font=get_pillow_font(16, bold=True))

    # Courier Partner Card
    d.rounded_rectangle([(30, 165), (w - 30, 260)], radius=10, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    d.text((50, 180), "COURIER PARTNER: DELHIVERY EXPRESS (कूरियर पार्टनर)", fill=(29, 78, 216), font=get_pillow_font(14, bold=True))
    d.text((50, 205), "AWB / Tracking Number: 143200987654 (Sample AWB)", fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
    d.text((480, 205), "Pickup Token: PKP-DEMO-9821", fill=(15, 23, 42), font=get_pillow_font(12, bold=True))
    d.text((50, 230), "Scheduled Slot: Today, 02:00 PM - 05:00 PM  |  Rider Phone: +91 98000 00000 (Sample Rider)", fill=(71, 85, 105), font=get_pillow_font(11, bold=False))

    # Shipping Stepper Card
    d.rounded_rectangle([(30, 280), (w - 30, h - 25)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.text((50, 300), "Complete Order Shipping Journey (शिपिंग के 6 चरण)", fill=(30, 41, 59), font=get_pillow_font(14, bold=True))

    stages = [
        ("1. Order Placed", "ऑर्डर प्राप्त हुआ", True),
        ("2. Packed & Ready", "पैक हो गया", True),
        ("3. Courier Picked", "कूरियर ने उठाया", True),
        ("4. In Transit", "रास्ते में है", True),
        ("5. Out for Delivery", "डिलीवरी पर निकला", True),
        ("6. Delivered (OTP)", "ओटीपी डिलीवरी सफल", True)
    ]
    step_x = 50
    step_width = 145
    for idx, (st_name, st_sub, is_done) in enumerate(stages):
        d.ellipse([(step_x + 35, 345), (step_x + 75, 385)], fill=(5, 150, 105) if is_done else (203, 213, 225))
        d.text((step_x + 48, 357), "✓", fill=(255, 255, 255), font=get_pillow_font(15, bold=True))
        if idx < len(stages) - 1:
            d.line([(step_x + 75, 365), (step_x + 75 + step_width - 40, 365)], fill=(5, 150, 105), width=3)
        d.text((step_x, 398), st_name, fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
        d.text((step_x, 418), st_sub, fill=(100, 116, 139), font=get_pillow_font(10, bold=False))
        step_x += step_width

    # OTP Box
    d.rounded_rectangle([(50, 460), (w - 50, 535)], radius=8, fill=(254, 242, 242), outline=(254, 202, 202), width=1)
    d.text((70, 475), "🛡️ 4-Digit Secret Delivery OTP Guarantee (सुरक्षित ओटीपी डिलीवरी):", fill=(185, 28, 28), font=get_pillow_font(13, bold=True))
    d.text((70, 498), "ग्राहक द्वारा 4-अंकीय गुप्त ओटीपी दिए बिना राइडर पैकेट नहीं दे सकता।", fill=(153, 27, 27), font=get_pillow_font(11, bold=False))
    d.text((70, 515), "इससे गलत या झूठी डिलीवरी क्लेम से विक्रेता को 100% सुरक्षा मिलती है।", fill=(153, 27, 27), font=get_pillow_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_5_shiprocket_pickup.png')
    img.save(path)
    return path


def generate_screen_6_notification_emails():
    """Screenshot 6: StallCart Real Email Templates (Sample Demo Data)"""
    w, h = 980, 580
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "Seller Email Notifications - StallCart Automated Alerts", "https://mail.google.com/mail/u/0/#inbox")
    draw_stallcart_header(d, w, active_nav='seller')

    # Left Email: New Order Alert
    d.rounded_rectangle([(30, 130), (470, h - 25)], radius=10, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.rectangle([(30, 130), (470, 175)], fill=(15, 23, 42))
    d.text((50, 145), "StallCart: New Order! नया ऑर्डर प्राप्त 📦", fill=(255, 255, 255), font=get_pillow_font(13, bold=True))

    d.text((50, 190), "Dear Apex Trends Fashion Hub (Sample Seller),", fill=(15, 23, 42), font=get_pillow_font(11, bold=True))
    d.text((50, 210), "बधाई! आपकी दुकान पर नया ऑर्डर प्राप्त हुआ है।", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
    
    d.rounded_rectangle([(50, 235), (450, 345)], radius=6, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((65, 250), "Order ID: #ORD-SAMPLE-202611-01", fill=(30, 41, 59), font=get_pillow_font(11, bold=True))
    d.text((65, 272), "Product: Men's Classic Slim Fit Cotton Shirt (Size L)", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((65, 294), "Quantity: 1 Pc  |  Selling Price: ₹499.00", fill=(15, 23, 42), font=get_pillow_font(10, bold=False))
    d.text((65, 316), "Your Net Earnings: ₹424.15 (15% Comm Deducted)", fill=(5, 150, 105), font=get_pillow_font(10, bold=True))

    d.text((50, 365), "Action Required (तत्काल कदम):", fill=(180, 83, 9), font=get_pillow_font(11, bold=True))
    d.text((50, 385), "कृपया इस ऑर्डर को तुरंत पैक करें और सेलर पोर्टल में", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))
    d.text((50, 405), "'Ready for Pickup' मार्क करें ताकि कूरियर आज पिकअप कर सके।", fill=(71, 85, 105), font=get_pillow_font(10, bold=False))

    d.rounded_rectangle([(50, 435), (260, 468)], radius=6, fill=(40, 116, 240))
    d.text((70, 445), "Go to Seller Portal →", fill=(255, 255, 255), font=get_pillow_font(11, bold=True))
    d.text((50, 490), "Helpdesk Phone: +91 7307383046", fill=(100, 116, 139), font=get_pillow_font(10, bold=False))

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
# 4. REPORTLAB NUMBERED CANVAS (Running Header & Footer)
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
        self.drawString(36, 32, "© 2026 StallCart Platform · हेल्पलाइन: +91 7307383046 · stallcartsupport@gmail.com")
        self.drawRightString(559, 32, f"Page {self._pageNumber} of {page_count}")

        self.restoreState()


# ─────────────────────────────────────────────────────────────
# 5. BUILD BILINGUAL REPORTLAB PDF DOCUMENT (PURE SAMPLE DATA)
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

    brand_primary = colors.HexColor("#2874f0")
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
        [[Paragraph("<b>STALLCART PARTNER ECOSYSTEM · विक्रेता सहयोग पोर्टल (Official Guide)</b>", ParagraphStyle('Badge', fontName=dev_font, fontSize=9, textColor=colors.HexColor('#047857')))]],
        colWidths=[310]
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
        "शिपरोकेट कूरियर पिकअप और बैंक सेटलमेंट (UTR नंबर सहित) की संपूर्ण सचित्र मार्गदर्शिका। "
        "<br/><i>(सभी स्क्रीनशॉट और डेटा स्टॉलकार्ट वेब ऐप के मानक डेमो प्रारूप पर आधारित हैं।)</i>",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=brand_primary, spaceBefore=4, spaceAfter=18))

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
    story.append(Paragraph("• <b>पंजीकरण लिंक / Registration Portal:</b> <code>https://stallcart.in/accounts/seller/register/</code> पर जाएं या होमपेज पर 'Seller Panel' पर क्लिक करें।", bullet_style))
    story.append(Paragraph("• <b>दुकान एवं संपर्क / Business Identity:</b> अपनी दुकान का नाम (Shop Name जैसे <i>Apex Trends Fashion Hub</i>), रजिस्टर्ड मोबाइल और ईमेल दर्ज करें।", bullet_style))
    story.append(Paragraph("• <b>पिकअप पता और पिनकोड / Pickup Address:</b> वह सटीक गोदाम/दुकान का पता और 6-अंकीय पिनकोड (उदा. <i>452001</i>) दर्ज करें जहां से कूरियर राइडर पैकेट उठाएगा।", bullet_style))
    story.append(Paragraph("• <b>बैंक खाता विवरण / Bank Details for Payout:</b> बैंक का नाम (जैसे <i>HDFC Bank</i>), खाता संख्या, और IFSC कोड दर्ज करें। सभी भुगतान इसी खाते में जाएंगे।", bullet_style))
    story.append(Paragraph("• <b>केवाईसी सत्यापन / KYC Verification:</b> स्टॉलकार्ट एडमिन 24 घंटे के भीतर विवरण सत्यापित करता है और आपका खाता <b>KYC Approved ✓</b> हो जाता है।", bullet_style))
    story.append(Spacer(1, 6))

    s1_path = os.path.join(SCREENSHOTS_DIR, 'screen_1_registration.png')
    story.append(RLImage(s1_path, width=520, height=295))
    story.append(Paragraph("चित्र 1.1: स्टॉलकार्ट विक्रेता पंजीकरण एवं बैंक खाता सत्यापन स्क्रीन (Seller Registration Form - Sample Data)", caption_style))
    story.append(PageBreak())

    # ── MODULE 2 ──
    story.append(Paragraph("मॉड्यूल 2: उत्पाद लिस्टिंग, फोटो नियम और वेरिएंट सेटअप<br/>Module 2: Product Cataloging, Images &amp; Variant Setup", h1_style))
    story.append(Paragraph(
        "<b>English:</b> Listing attractive products with accurate pricing and high-definition photography is essential to maximize sales.<br/>"
        "<b>हिंदी:</b> उत्पाद की सही जानकारी, उचित मूल्य और साफ फोटो डालने से ग्राहक का भरोसा बढ़ता है और बिक्री तेज होती है।",
        body_style
    ))
    story.append(Paragraph("<b>मुख्य नियम एवं दिशानिर्देश / Listing Guidelines:</b>", h2_style))
    story.append(Paragraph("• <b>उत्पाद का शीर्षक (Title):</b> ब्रांड नाम, प्रमुख सामग्री या साइज स्पष्ट लिखें (उदा. <i>Men's Classic Slim Fit Cotton Casual Shirt - Navy Blue</i>)।", bullet_style))
    story.append(Paragraph("• <b>श्रेणी एवं कमीशन (Category &amp; Commission):</b> सही केटेगरी चुनें (उदा. <i>Men's Fashion &amp; Apparel</i>)। उस केटेगरी का स्टॉलकार्ट कमीशन प्रतिशत (जैसे 15%) स्क्रीन पर दिखेगा।", bullet_style))
    story.append(Paragraph("• <b>MRP बनाम सेलिंग प्राइस (Pricing):</b> अधिकतम खुदरा मूल्य (MRP जैसे ₹999) और अपना अंतिम बिक्री मूल्य (Selling Price जैसे ₹499) दर्ज करें। 50% की छूट ग्राहकों को आकर्षित करती है।", bullet_style))
    story.append(Paragraph("• <b>स्टॉक (Inventory):</b> अपने पास उपलब्ध स्टॉक दर्ज करें (जैसे 100 पीस)। स्टॉक 0 होने पर सिस्टम ऑटोमैटिक 'Out of Stock' दिखाएगा।", bullet_style))
    story.append(Paragraph("• <b>वेरिएंट्स मैट्रिक्स (Variants):</b> कपड़ों के लिए साइज (M, L, XL) और रंग चुनें। प्रत्येक साइज का स्टॉक अलग सेट करें।", bullet_style))
    story.append(Paragraph("• <b>फोटो नियम (Photography SOP):</b> साफ सफेद बैकग्राउंड में न्यूनतम 3 साफ तस्वीरें अपलोड करें (Front, Side, Fabric, Size Chart)।", bullet_style))
    story.append(Spacer(1, 6))

    s2_path = os.path.join(SCREENSHOTS_DIR, 'screen_2_product_listing.png')
    story.append(RLImage(s2_path, width=520, height=310))
    story.append(Paragraph("चित्र 2.1: स्टॉलकार्ट उत्पाद लिस्टिंग फॉर्म, लाइव वेरिएंट मैट्रिक्स और फोटो गैलरी (Add Product Form - Sample Data)", caption_style))
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
         Paragraph("ग्राहक ने भुगतान कर दिया है। विक्रेता को तुरंत <b>Accept &amp; Pack Order</b> पर क्लिक करना चाहिए।", body_style)],
        [Paragraph("<b>Ready for Pickup</b><br/>(पिकअप हेतु तैयार)", body_style),
         Paragraph("विक्रेता ने पैकेट तैयार कर लिया है। सिस्टम कूरियर राइडर असाइन करता है और पिकअप टोकन (जैसे <code>PKP-DEMO-9821</code>) जारी करता है।", body_style)],
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
    story.append(RLImage(s3_path, width=520, height=295))
    story.append(Paragraph("चित्र 3.1: स्टॉलकार्ट सेलर ऑर्डर्स डैशबोर्ड, स्टेटस कार्ड्स एवं ग्राहक विवरण (Orders Received - Sample Data)", caption_style))
    story.append(PageBreak())

    # ── MODULE 4 ──
    story.append(Paragraph("मॉड्यूल 4: सुरक्षित पैकेजिंग मानक प्रक्रिया (SOP) और टैक्स इनवॉइस<br/>Module 4: Packaging Standard Operating Procedure (SOP)", h1_style))
    story.append(Paragraph(
        "<b>English:</b> Proper packaging protects items during transit, minimizes returns, and creates a five-star unboxing experience.<br/>"
        "<b>हिंदी:</b> सही तरीके से पैकिंग करने से रास्ते में सामान सुरक्षित रहता है, ग्राहक संतुष्ट होता है और डैमेज रिटर्न की संभावना खत्म हो जाती है।",
        body_style
    ))
    story.append(Paragraph("<b>पैकिंग के 5 सुनहरे नियम / 5-Step Packing Protocol:</b>", h2_style))
    story.append(Paragraph("<b>1. क्वालिटी और साइज जांच (Quality Verification):</b> पैकेट पैक करने से पहले चेक करें कि सही साइज (उदा. Size L, न कि M) और सही कलर का डिफेक्ट-फ्री सामान है।", bullet_style))
    story.append(Paragraph("<b>2. बबल रैप सुरक्षा (Bubble Wrap Layer):</b> परिधान या नाजुक सामान को कम से कम 2 परत वाटरप्रूफ पॉलीथीन या बबल रैप में लपेटें।", bullet_style))
    story.append(Paragraph("<b>3. मजबूत बाहरी बॉक्स/बैग (Outer Box):</b> स्टॉलकार्ट टेंपर-एविडेंट प्लास्टिक बैग या 3-प्लाई वाले मजबूत कार्डबोर्ड बॉक्स में पैक करें।", bullet_style))
    story.append(Paragraph("<b>4. टैक्स इनवॉइस अंदर रखें (Insert Tax Invoice):</b> सेलर पोर्टल से टैक्स इनवॉइस (Tax Invoice) डाउनलोड करके प्रिंट करें और पैकेट के अंदर डालें।", bullet_style))
    story.append(Paragraph("<b>5. कूरियर बारकोड लेबल चिपकाएं (Affix AWB Label):</b> दिल्लीवरी/शिपरोकेट का AWB बारकोड लेबल बॉक्स के ऊपर सपाट चिपकाएं। बारकोड पर कभी टेप न लगाएं।", bullet_style))
    story.append(Spacer(1, 6))

    s4_path = os.path.join(SCREENSHOTS_DIR, 'screen_4_packing_sop.png')
    story.append(RLImage(s4_path, width=520, height=295))
    story.append(Paragraph("चित्र 4.1: स्टॉलकार्ट आधिकारिक टैक्स इनवॉइस एवं 5-चरणीय पैकेजिंग मानक प्रक्रिया (Packaging SOP - Sample Data)", caption_style))
    story.append(PageBreak())

    # ── MODULE 5 ──
    story.append(Paragraph("मॉड्यूल 5: शिपरोकेट कूरियर पिकअप, टोकन और सुरक्षित डिस्पैच<br/>Module 5: Courier Pickup Scheduling &amp; Dispatch", h1_style))
    story.append(Paragraph(
        "<b>English:</b> StallCart integrates directly with Shiprocket &amp; Delhivery Express. Sellers do not need separate courier contracts.<br/>"
        "<b>हिंदी:</b> स्टॉलकार्ट सीधे शिपरोकेट और दिल्लीवरी एक्सप्रेस से जुड़ा हुआ है। आपको कूरियर कंपनी से अलग से बात करने की जरूरत नहीं होती।",
        body_style
    ))
    story.append(Paragraph("<b>पिकअप हैंडओवर दिशानिर्देश / Handover Protocol:</b>", h2_style))
    story.append(Paragraph("• <b>स्वचालित पिकअप असाइनमेंट:</b> जब आप 'Ready for Pickup' पर क्लिक करते हैं, तो सिस्टम कूरियर राइडर असाइन करके एक <b>पिकअप टोकन</b> (उदा. <code>PKP-DEMO-9821</code>) जारी करता है।", bullet_style))
    story.append(Paragraph("• <b>राइडर की जानकारी:</b> आपको कूरियर राइडर का नाम, मोबाइल नंबर और आगमन का समय डैशबोर्ड और एसएमएस पर मिल जाता है।", bullet_style))
    story.append(Paragraph("• <b>बारकोड स्कैन करवाएं:</b> जब राइडर आपके पते पर आए, तो उसका पहचान पत्र देखें और पैकेट सौंपकर अपने सामने बारकोड स्कैन करवाएं।", bullet_style))
    story.append(Paragraph("• <b>पिकअप रसीद (Manifest):</b> राइडर से डिजिटल या कागजी मैनिफेस्ट पर साइन लें।", bullet_style))
    story.append(Paragraph("• <b>सुरक्षित डिलीवरी ओटीपी (Secret 4-Digit OTP):</b> डिलीवरी के समय ग्राहक द्वारा राइडर को 4-अंकीय गुप्त ओटीपी देना अनिवार्य है। इससे झूठी डिलीवरी क्लेम से विक्रेता को 100% सुरक्षा मिलती है।", bullet_style))
    story.append(Spacer(1, 6))

    s5_path = os.path.join(SCREENSHOTS_DIR, 'screen_5_shiprocket_pickup.png')
    story.append(RLImage(s5_path, width=520, height=295))
    story.append(Paragraph("चित्र 5.1: कूरियर डिस्पैच प्रबंधन, शिपरोकेट पिकअप टोकन और 6-चरणीय डिलीवरी ट्रैकिंग (Shiprocket Tracking - Sample Data)", caption_style))
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
    story.append(Paragraph("चित्र 6.1: स्टॉलकार्ट आधिकारिक ईमेल अलर्ट टेम्पलेट - नया ऑर्डर एवं बैंक पेआउट सूचना (Email Notifications - Sample Data)", caption_style))
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
         Paragraph("बिक्री मूल्य (Selling Price): ₹499.00<br/>केटेगरी कमीशन (15%): -₹74.85<br/><b>विक्रेता को शुद्ध बैंक ट्रांसफर: ₹424.15</b>", body_style)],
        [Paragraph("<b>भुगतान का समय / Schedule:</b>", body_style),
         Paragraph("ऑर्डर सफलतापूर्वक डिलीवर होने और 7-दिन की आसान रिटर्न अवधि पूरी होने के बाद सेटलमेंट किया जाता है।", body_style)],
        [Paragraph("<b>ट्रांसफर का माध्यम / Mode:</b>", body_style),
         Paragraph("सीधा बैंक खाता ट्रांसफर (NEFT / RTGS / IMPS / UPI) अथवा RazorpayX इंस्टेंट पेआउट।", body_style)],
        [Paragraph("<b>बैंक UTR नंबर / Proof:</b>", body_style),
         Paragraph("हर भुगतान के साथ बैंक यूटीआर नंबर (उदा. <code>CMS987654321012</code>) प्रदान किया जाता है।", body_style)]
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
    story.append(Paragraph("चित्र 7.1: स्टॉलकार्ट सेलर सेटलमेंट एवं पेआउट लेज़र स्क्रीन (Settlements & Payouts Dashboard - Sample Data)", caption_style))
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
        ('BOX', (0,0), (-1,-1), 1.5, brand_primary),
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
    print("=== Generating StallCart Web App Screenshot Mockups (100% Sample Data) ===")
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
