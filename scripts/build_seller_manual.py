#!/usr/bin/env python3
"""
StallCart Official Seller Operations Manual & Handbook Generator
Generates:
1. High-resolution pixel-perfect UI mockup screenshots for each step in the seller workflow.
2. Comprehensive, executive-quality multi-page PDF document with ReportLab.
"""

import os
import sys
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
# 1. HELPER: FONT LOADER
# ─────────────────────────────────────────────────────────────
def get_font(size=14, bold=False):
    font_candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in font_candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ─────────────────────────────────────────────────────────────
# 2. SCREENSHOT GENERATORS (Pillow UI Mockups)
# ─────────────────────────────────────────────────────────────

def draw_browser_frame(d, width, height, title, url):
    # Window Header
    d.rectangle([(0, 0), (width, 42)], fill=(241, 245, 249))
    d.line([(0, 42), (width, 42)], fill=(203, 213, 225), width=1)
    
    # Window controls (macOS traffic lights)
    d.ellipse([(14, 15), (26, 27)], fill=(239, 68, 68))
    d.ellipse([(34, 15), (46, 27)], fill=(245, 158, 11))
    d.ellipse([(54, 15), (66, 27)], fill=(34, 197, 94))
    
    # URL Pill
    url_box_left = 85
    url_box_right = width - 20
    d.rounded_rectangle([(url_box_left, 8), (url_box_right, 34)], radius=6, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    font_url = get_font(12, bold=False)
    font_title = get_font(12, bold=True)
    d.text((url_box_left + 12, 12), f"🔒 {url}", fill=(100, 116, 139), font=font_url)


def generate_screen_1_registration():
    """Screenshot 1: Seller Onboarding & KYC Form"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart - Seller Registration", "https://stallcart.in/accounts/seller/register/")
    
    # Nav bar
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "StallCart", fill=(15, 23, 42), font=get_font(22, bold=True))
    d.text((135, 60), "Seller Partner Onboarding Portal", fill=(5, 150, 105), font=get_font(15, bold=True))
    d.rounded_rectangle([(w - 180, 55), (w - 30, 85)], radius=6, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((w - 165, 62), "● KYC Approved ✓", fill=(4, 120, 87), font=get_font(12, bold=True))

    # Main Card
    d.rounded_rectangle([(30, 115), (w - 30, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    
    # Card Header
    d.text((55, 135), "1. Business & Pickup Store Details", fill=(30, 41, 59), font=get_font(16, bold=True))
    
    # Form Row 1: Shop Name & Mobile
    d.text((55, 175), "Shop / Legal Business Name *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(55, 195), (450, 230)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((70, 203), "AyurSattva Herbal Care", fill=(15, 23, 42), font=get_font(13, bold=False))
    
    d.text((480, 175), "Registered Phone / WhatsApp *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(480, 195), (875, 230)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((495, 203), "+91 6355588582 (OTP Verified ✓)", fill=(5, 150, 105), font=get_font(13, bold=True))

    # Form Row 2: Pickup Address & Pincode
    d.text((55, 245), "Courier Pickup Warehouse Address *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(55, 265), (580, 300)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((70, 273), "Plot 42, Herbal Industrial Estate, Khasur, Surat", fill=(15, 23, 42), font=get_font(13, bold=False))
    
    d.text((610, 245), "Pickup Pincode *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(610, 265), (875, 300)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((625, 273), "395004 (Delhivery Serviceable ✓)", fill=(5, 150, 105), font=get_font(13, bold=True))

    # Card Header 2: Bank Details for Payouts
    d.text((55, 325), "2. Bank Account Details for Payout Disbursements", fill=(30, 41, 59), font=get_font(16, bold=True))
    
    # Form Row 3: Bank Name, A/C No, IFSC
    d.text((55, 355), "Bank Name *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(55, 375), (320, 410)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((70, 383), "Bank of Baroda", fill=(15, 23, 42), font=get_font(13, bold=False))
    
    d.text((345, 355), "Account Number *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(345, 375), (610, 410)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((360, 383), "446487269828611 (Valid)", fill=(15, 23, 42), font=get_font(13, bold=False))

    d.text((635, 355), "IFSC Code *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(635, 375), (875, 410)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((650, 383), "BARB0KHASUR (Verified)", fill=(5, 150, 105), font=get_font(13, bold=True))

    # Submit Button
    d.rounded_rectangle([(55, 440), (280, 485)], radius=8, fill=(5, 150, 105))
    d.text((80, 452), "Save & Submit Profile", fill=(255, 255, 255), font=get_font(14, bold=True))
    d.text((305, 455), "🔒 StallCart ensures bank details are 256-bit encrypted for automated payouts.", fill=(100, 116, 139), font=get_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_1_registration.png')
    img.save(path)
    return path


def generate_screen_2_product_listing():
    """Screenshot 2: Add Product & Variant Cataloging Form"""
    w, h = 950, 600
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller - Add New Product", "https://stallcart.in/items/seller/products/add/")
    
    # Nav header
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "Seller Panel", fill=(15, 23, 42), font=get_font(20, bold=True))
    d.text((170, 60), "›  Add New Product Listing", fill=(100, 116, 139), font=get_font(14, bold=False))
    
    # Left Column: Product Details
    d.rounded_rectangle([(30, 115), (550, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.text((50, 135), "Product Information", fill=(30, 41, 59), font=get_font(16, bold=True))
    
    d.text((50, 175), "Product Title *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(50, 195), (530, 230)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((65, 203), "AyurSattva Charcoal Detox Herbal Soap (100g)", fill=(15, 23, 42), font=get_font(13, bold=False))
    
    d.text((50, 245), "Category *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(50, 265), (280, 300)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((65, 273), "Personal Care & Wellness", fill=(15, 23, 42), font=get_font(13, bold=False))
    d.text((295, 273), "Commission: 15%", fill=(37, 99, 235), font=get_font(12, bold=True))
    
    d.text((50, 315), "MRP (₹) *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(50, 335), (200, 370)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((65, 343), "₹ 120.00", fill=(15, 23, 42), font=get_font(13, bold=False))
    
    d.text((220, 315), "Selling Price (₹) *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(220, 335), (370, 370)], radius=6, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((235, 343), "₹ 89.00 (25% OFF)", fill=(4, 120, 87), font=get_font(13, bold=True))

    d.text((390, 315), "Stock Qty *", fill=(71, 85, 105), font=get_font(12, bold=True))
    d.rounded_rectangle([(390, 335), (530, 370)], radius=6, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((405, 343), "50 Units", fill=(15, 23, 42), font=get_font(13, bold=False))

    # Variant matrix preview
    d.text((50, 395), "Variants (Size / Weight Matrix)", fill=(30, 41, 59), font=get_font(14, bold=True))
    d.rectangle([(50, 425), (530, 465)], fill=(241, 245, 249))
    d.text((60, 435), "1 Bar (100g)  —  ₹89.00  —  Stock: 50", fill=(30, 41, 59), font=get_font(12, bold=True))
    d.rectangle([(50, 470), (530, 510)], fill=(248, 250, 252))
    d.text((60, 480), "Pack of 3 (300g) —  ₹239.00 —  Stock: 25", fill=(30, 41, 59), font=get_font(12, bold=True))

    # Right Column: High Quality Photos
    d.rounded_rectangle([(580, 115), (w - 30, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.text((605, 135), "Product Images (High-Res)", fill=(30, 41, 59), font=get_font(16, bold=True))
    d.text((605, 160), "Upload clean white-background photos (min 800x800 px)", fill=(100, 116, 139), font=get_font(11, bold=False))

    # Photo Slots
    d.rounded_rectangle([(605, 190), (745, 330)], radius=8, fill=(241, 245, 249), outline=(167, 243, 208), width=2)
    d.text((630, 250), "📷 Primary Photo", fill=(5, 150, 105), font=get_font(12, bold=True))
    d.text((645, 270), "(Cover Image)", fill=(100, 116, 139), font=get_font(10, bold=False))

    d.rounded_rectangle([(765, 190), (905, 330)], radius=8, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((795, 250), "📷 Angle Photo 2", fill=(71, 85, 105), font=get_font(12, bold=False))

    d.rounded_rectangle([(605, 350), (745, 450)], radius=8, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((635, 395), "📷 Ingredients / Box", fill=(71, 85, 105), font=get_font(11, bold=False))

    d.rounded_rectangle([(765, 350), (905, 450)], radius=8, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d.text((800, 395), "📷 + Add More", fill=(37, 99, 235), font=get_font(12, bold=True))

    # Save Button
    d.rounded_rectangle([(605, 480), (905, 530)], radius=8, fill=(5, 150, 105))
    d.text((660, 495), "🚀 Publish to StallCart", fill=(255, 255, 255), font=get_font(15, bold=True))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_2_product_listing.png')
    img.save(path)
    return path


def generate_screen_3_orders_dashboard():
    """Screenshot 3: Seller Orders Dashboard with Status Lifecycle"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller Orders", "https://stallcart.in/orders/seller/orders/")
    
    # Header
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "Manage Orders", fill=(15, 23, 42), font=get_font(20, bold=True))
    d.text((200, 60), "Real-time Order Processing & Fulfillment", fill=(100, 116, 139), font=get_font(13, bold=False))
    
    # Filter Tabs
    tabs = [("All Orders (8)", False), ("Pending (1)", True), ("Ready for Pickup (2)", False), ("In Transit (3)", False), ("Delivered (2)", False)]
    cur_x = 30
    for label, active in tabs:
        box_w = 150
        if active:
            d.rounded_rectangle([(cur_x, 115), (cur_x + box_w, 150)], radius=6, fill=(236, 253, 245), outline=(5, 150, 105), width=2)
            d.text((cur_x + 16, 126), label, fill=(4, 120, 87), font=get_font(12, bold=True))
        else:
            d.rounded_rectangle([(cur_x, 115), (cur_x + box_w, 150)], radius=6, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
            d.text((cur_x + 16, 126), label, fill=(100, 116, 139), font=get_font(12, bold=False))
        cur_x += box_w + 12

    # Order Card 1
    d.rounded_rectangle([(30, 175), (w - 30, 340)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    
    # Card Header
    d.rectangle([(30, 175), (w - 30, 220)], fill=(248, 250, 252))
    d.line([(30, 220), (w - 30, 220)], fill=(226, 232, 240), width=1)
    d.text((50, 188), "ORDER #ORD-20261120-000001", fill=(15, 23, 42), font=get_font(14, bold=True))
    d.text((360, 190), "Placed: 20 Nov 2026, 09:30 AM", fill=(100, 116, 139), font=get_font(12, bold=False))
    
    # Status Badge
    d.rounded_rectangle([(w - 220, 185), (w - 50, 212)], radius=12, fill=(254, 243, 199))
    d.text((w - 200, 190), "⚡ ACTION REQUIRED", fill=(180, 83, 9), font=get_font(11, bold=True))

    # Order Body
    d.text((50, 235), "Customer: Amit Sharma  |  Shipping: Varanasi, UP - 221001", fill=(71, 85, 105), font=get_font(12, bold=False))
    d.text((50, 260), "Item: AyurSattva Charcoal Detox Herbal Soap (100g) x 1", fill=(15, 23, 42), font=get_font(15, bold=True))
    d.text((50, 285), "Item Total: ₹89.00  |  Platform Comm: 15% (₹13.35)  |  Your Net Earnings: ₹75.65", fill=(5, 150, 105), font=get_font(13, bold=True))

    # Action Buttons on right
    d.rounded_rectangle([(w - 240, 240), (w - 50, 275)], radius=6, fill=(5, 150, 105))
    d.text((w - 225, 248), "✓ Accept & Pack Order", fill=(255, 255, 255), font=get_font(12, bold=True))

    d.rounded_rectangle([(w - 240, 285), (w - 50, 320)], radius=6, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.text((w - 225, 294), "📄 Print Tax Invoice", fill=(30, 41, 59), font=get_font(12, bold=True))

    # Order Card 2: Ready for Pickup
    d.rounded_rectangle([(30, 360), (w - 30, 520)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.rectangle([(30, 360), (w - 30, 405)], fill=(248, 250, 252))
    d.line([(30, 405), (w - 30, 405)], fill=(226, 232, 240), width=1)
    d.text((50, 373), "ORDER #ORD-20261020-000001", fill=(15, 23, 42), font=get_font(14, bold=True))
    d.rounded_rectangle([(w - 220, 370), (w - 50, 397)], radius=12, fill=(239, 246, 255))
    d.text((w - 200, 375), "🚚 READY FOR PICKUP", fill=(29, 78, 216), font=get_font(11, bold=True))
    
    d.text((50, 420), "Courier: Delhivery  |  AWB: 143289028129  |  Token: PKP-98210", fill=(37, 99, 235), font=get_font(13, bold=True))
    d.text((50, 445), "Item: AyurSattva Herbal Shampoo (200ml) x 1  |  Disbursement: ₹145.00", fill=(15, 23, 42), font=get_font(14, bold=True))
    d.text((50, 470), "Status: Hand package to courier rider upon OTP verification.", fill=(100, 116, 139), font=get_font(12, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_3_orders_dashboard.png')
    img.save(path)
    return path


def generate_screen_4_packing_sop():
    """Screenshot 4: Packaging SOP & Invoice Printing"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart - Packaging & Dispatch SOP", "https://stallcart.in/orders/order/ORD-20261120-000001/invoice/")
    
    # Left Box: Official StallCart Tax Invoice Mockup
    d.rounded_rectangle([(30, 60), (450, h - 30)], radius=8, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.text((50, 75), "TAX INVOICE / PACKING SLIP", fill=(15, 23, 42), font=get_font(14, bold=True))
    d.text((50, 95), "StallCart Retail Platform", fill=(100, 116, 139), font=get_font(11, bold=False))
    d.line([(50, 115), (430, 115)], fill=(226, 232, 240), width=1)
    
    d.text((50, 125), "Order ID: #ORD-20261120-000001", fill=(30, 41, 59), font=get_font(12, bold=True))
    d.text((50, 145), "Invoice No: SC-INV-2026-9021", fill=(71, 85, 105), font=get_font(11, bold=False))
    d.text((50, 165), "Seller: AyurSattva Herbal Care", fill=(71, 85, 105), font=get_font(11, bold=False))
    d.text((50, 185), "Buyer: Amit Sharma, Varanasi UP", fill=(71, 85, 105), font=get_font(11, bold=False))
    
    # Table header
    d.rectangle([(50, 210), (430, 235)], fill=(241, 245, 249))
    d.text((55, 217), "Item Description", fill=(30, 41, 59), font=get_font(10, bold=True))
    d.text((280, 217), "Qty", fill=(30, 41, 59), font=get_font(10, bold=True))
    d.text((340, 217), "Total", fill=(30, 41, 59), font=get_font(10, bold=True))
    
    d.text((55, 245), "AyurSattva Charcoal Soap (100g)", fill=(15, 23, 42), font=get_font(10, bold=False))
    d.text((285, 245), "1", fill=(15, 23, 42), font=get_font(10, bold=False))
    d.text((340, 245), "₹89.00", fill=(15, 23, 42), font=get_font(10, bold=True))

    # Mock Barcode
    d.rectangle([(50, 310), (430, 380)], fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    for bx in range(70, 410, 6):
        d.line([(bx, 320), (bx, 360)], fill=(0, 0, 0), width=3 if bx % 4 == 0 else 1)
    d.text((150, 365), "* 143289028129 *", fill=(0, 0, 0), font=get_font(11, bold=True))

    d.text((50, 400), "Fold and insert Invoice INSIDE package pouch.", fill=(180, 83, 9), font=get_font(11, bold=True))

    # Right Box: Packaging Guidelines & Visual Steps
    d.rounded_rectangle([(480, 60), (w - 30, h - 30)], radius=8, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.text((505, 80), "StallCart Standard Packaging SOP", fill=(4, 120, 87), font=get_font(18, bold=True))
    
    steps = [
        ("Step 1: Product Quality Inspection", "Check item thoroughly. Ensure zero defects, correct size/color variant, and intact original product seal."),
        ("Step 2: Moisture & Bubble Wrap", "Wrap individual item in at least 2 layers of bubble wrap for cosmetic/liquid/fragile items. Prevent leaks."),
        ("Step 3: Sturdy Outer Packaging", "Place in StallCart tamper-evident flyer bag or corrugated 3-ply box. Seal securely with adhesive tape."),
        ("Step 4: Affix Shipping AWB Label", "Affix Delhivery/Shiprocket barcode label on FLAT surface. Do NOT tape over barcode; ensure 100% scannable."),
        ("Step 5: Handover to Courier Rider", "Verify courier identity. Take signature on manifest or record token upon courier pickup scan.")
    ]
    sy = 125
    for s_title, s_desc in steps:
        d.ellipse([(505, sy), (525, sy + 20)], fill=(5, 150, 105))
        d.text((511, sy + 2), "✓", fill=(255, 255, 255), font=get_font(12, bold=True))
        d.text((535, sy), s_title, fill=(15, 23, 42), font=get_font(13, bold=True))
        d.text((535, sy + 20), s_desc[:70] + "...", fill=(100, 116, 139), font=get_font(11, bold=False))
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
    
    # Header
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "Automated Logistics & Tracking", fill=(15, 23, 42), font=get_font(20, bold=True))
    d.text((350, 60), "Integrated with Shiprocket & Delhivery Express", fill=(5, 150, 105), font=get_font(13, bold=True))

    # Courier Details Banner
    d.rounded_rectangle([(30, 115), (w - 30, 210)], radius=12, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    d.text((50, 130), "COURIER PARTNER: DELHIVERY EXPRESS", fill=(29, 78, 216), font=get_font(15, bold=True))
    d.text((50, 155), "AWB / Tracking Number: 143289028129", fill=(15, 23, 42), font=get_font(13, bold=True))
    d.text((450, 155), "Pickup Token: PKP-98210-SC", fill=(15, 23, 42), font=get_font(13, bold=True))
    d.text((50, 180), "Scheduled Pickup Slot: Today, 02:00 PM - 05:00 PM  |  Rider Phone: +91 98765 43210", fill=(71, 85, 105), font=get_font(12, bold=False))

    # Stepper / Progress Bar
    d.rounded_rectangle([(30, 230), (w - 30, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    d.text((50, 250), "Complete Order Shipping Journey", fill=(30, 41, 59), font=get_font(16, bold=True))

    stages = [
        ("1. Order Placed", "Customer placed order", True),
        ("2. Packed & Ready", "Seller packed box", True),
        ("3. Courier Picked Up", "Rider scanned AWB", True),
        ("4. In Transit", "Moving via hub", True),
        ("5. Out for Delivery", "Rider has package", True),
        ("6. Delivered (OTP)", "Verified Delivery", True)
    ]
    step_x = 50
    step_width = 140
    for idx, (st_name, st_sub, is_done) in enumerate(stages):
        # Circle
        d.ellipse([(step_x + 35, 300), (step_x + 75, 340)], fill=(5, 150, 105) if is_done else (203, 213, 225))
        d.text((step_x + 48, 312), "✓", fill=(255, 255, 255), font=get_font(15, bold=True))
        if idx < len(stages) - 1:
            d.line([(step_x + 75, 320), (step_x + 75 + step_width - 40, 320)], fill=(5, 150, 105), width=3)
        d.text((step_x, 355), st_name, fill=(15, 23, 42), font=get_font(11, bold=True))
        d.text((step_x, 375), st_sub, fill=(100, 116, 139), font=get_font(10, bold=False))
        step_x += step_width

    # Safety Notice
    d.rounded_rectangle([(50, 430), (w - 50, 500)], radius=8, fill=(254, 242, 242), outline=(254, 202, 202), width=1)
    d.text((70, 445), "🛡️ OTP Secure Delivery Guarantee:", fill=(185, 28, 28), font=get_font(13, bold=True))
    d.text((70, 468), "StallCart requires customers to provide a 4-digit secret OTP to the courier before delivery.", fill=(153, 27, 27), font=get_font(12, bold=False))
    d.text((70, 485), "This eliminates fake delivery claims and guarantees 100% genuine delivery proof for sellers.", fill=(153, 27, 27), font=get_font(11, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_5_shiprocket_pickup.png')
    img.save(path)
    return path


def generate_screen_6_notification_emails():
    """Screenshot 6: Transactional Emails Sample (New Order, Pickup, Settlement)"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "Seller Email Notifications - StallCart Automated Alerts", "https://mail.google.com/seller-inbox")

    # Email Container 1: New Order Received Email
    d.rounded_rectangle([(30, 60), (460, h - 30)], radius=10, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.rectangle([(30, 60), (460, 110)], fill=(5, 150, 105))
    d.text((50, 75), "StallCart Seller Alert: New Order! 📦", fill=(255, 255, 255), font=get_font(15, bold=True))

    d.text((50, 125), "Dear AyurSattva Herbal Care,", fill=(15, 23, 42), font=get_font(12, bold=True))
    d.text((50, 145), "Great news! You have received a new customer order.", fill=(71, 85, 105), font=get_font(11, bold=False))
    
    d.rounded_rectangle([(50, 175), (440, 290)], radius=6, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((65, 190), "Order ID: #ORD-20261120-000001", fill=(30, 41, 59), font=get_font(12, bold=True))
    d.text((65, 212), "Product: AyurSattva Charcoal Soap (100g)", fill=(15, 23, 42), font=get_font(11, bold=False))
    d.text((65, 234), "Quantity: 1 Pc  |  Price: ₹89.00", fill=(15, 23, 42), font=get_font(11, bold=False))
    d.text((65, 256), "Your Earnings: ₹75.65 (Comm 15% deducted)", fill=(5, 150, 105), font=get_font(11, bold=True))

    d.text((50, 310), "Action Required:", fill=(180, 83, 9), font=get_font(12, bold=True))
    d.text((50, 330), "Please pack this order and click 'Ready for Pickup'", fill=(71, 85, 105), font=get_font(11, bold=False))
    d.text((50, 350), "before 02:00 PM today to ensure fast courier dispatch.", fill=(71, 85, 105), font=get_font(11, bold=False))

    d.rounded_rectangle([(50, 385), (250, 420)], radius=6, fill=(5, 150, 105))
    d.text((80, 395), "Go to Seller Portal →", fill=(255, 255, 255), font=get_font(12, bold=True))

    d.text((50, 440), "Support Hotline: +91 7307383046", fill=(100, 116, 139), font=get_font(10, bold=False))

    # Email Container 2: Settlement Processed Email
    d.rounded_rectangle([(490, 60), (920, h - 30)], radius=10, fill=(255, 255, 255), outline=(203, 213, 225), width=1)
    d.rectangle([(490, 60), (920, 110)], fill=(37, 99, 235))
    d.text((510, 75), "StallCart: Payout Disbursed! 💸", fill=(255, 255, 255), font=get_font(15, bold=True))

    d.text((510, 125), "Dear AyurSattva Herbal Care,", fill=(15, 23, 42), font=get_font(12, bold=True))
    d.text((510, 145), "Your seller settlement payout has been transferred.", fill=(71, 85, 105), font=get_font(11, bold=False))

    d.rounded_rectangle([(510, 175), (900, 310)], radius=6, fill=(239, 246, 255), outline=(191, 219, 254), width=1)
    d.text((525, 188), "Settlement Batch: SET-20261119-0001", fill=(30, 41, 59), font=get_font(12, bold=True))
    d.text((525, 210), "Amount Disbursed: ₹75.65", fill=(4, 120, 87), font=get_font(15, bold=True))
    d.text((525, 235), "Bank: Bank of Baroda (••••8611)", fill=(15, 23, 42), font=get_font(11, bold=False))
    d.text((525, 255), "IFSC Code: BARB0KHASUR", fill=(15, 23, 42), font=get_font(11, bold=False))
    d.text((525, 278), "Bank UTR: T2611131350345249750598", fill=(37, 99, 235), font=get_font(12, bold=True))

    d.text((510, 330), "Order Settled:", fill=(30, 41, 59), font=get_font(12, bold=True))
    d.text((510, 350), "• #ORD-20261020-000001 : AyurSattva Soap x1", fill=(71, 85, 105), font=get_font(11, bold=False))
    d.text((510, 370), "Status: Credit reflected in your bank account.", fill=(5, 150, 105), font=get_font(11, bold=True))

    d.rounded_rectangle([(510, 400), (710, 435)], radius=6, fill=(37, 99, 235))
    d.text((535, 410), "Download Tax Invoice", fill=(255, 255, 255), font=get_font(12, bold=True))

    d.text((510, 455), "Need help? WhatsApp: 7307383046", fill=(100, 116, 139), font=get_font(10, bold=False))

    path = os.path.join(SCREENSHOTS_DIR, 'screen_6_notification_emails.png')
    img.save(path)
    return path


def generate_screen_7_settlement_statement():
    """Screenshot 7: Payout Audit & Settlement History with UTR"""
    w, h = 950, 560
    img = Image.new('RGB', (w, h), (248, 250, 252))
    d = ImageDraw.Draw(img)
    draw_browser_frame(d, w, h, "StallCart Seller Finance - Settlements & Payouts", "https://stallcart.in/orders/seller/payouts/")
    
    # Header
    d.rectangle([(0, 43), (w, 95)], fill=(255, 255, 255))
    d.line([(0, 95), (w, 95)], fill=(226, 232, 240), width=1)
    d.text((30, 56), "Seller Financial Ledger & Disbursements", fill=(15, 23, 42), font=get_font(20, bold=True))
    d.text((450, 60), "100% Transparent Platform Audit", fill=(5, 150, 105), font=get_font(13, bold=True))

    # Metrics Summary Cards
    cards = [
        ("Total Net Settled", "₹ 75.65", "Direct credited to bank", (5, 150, 105)),
        ("Platform Commission", "₹ 13.35", "Avg 15% category fee", (37, 99, 235)),
        ("Pending Next Cycle", "₹ 0.00", "All batches cleared", (180, 83, 9)),
    ]
    cx = 30
    for title, val, sub, col in cards:
        d.rounded_rectangle([(cx, 115), (cx + 280, 195)], radius=10, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        d.text((cx + 18, 128), title, fill=(100, 116, 139), font=get_font(12, bold=False))
        d.text((cx + 18, 146), val, fill=col, font=get_font(20, bold=True))
        d.text((cx + 18, 172), sub, fill=(148, 163, 184), font=get_font(10, bold=False))
        cx += 300

    # Settlements Table
    d.rounded_rectangle([(30, 220), (w - 30, h - 30)], radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
    
    # Table Header
    d.rectangle([(30, 220), (w - 30, 260)], fill=(241, 245, 249))
    d.text((50, 234), "Batch ID", fill=(30, 41, 59), font=get_font(11, bold=True))
    d.text((200, 234), "Orders & Items", fill=(30, 41, 59), font=get_font(11, bold=True))
    d.text((420, 234), "Gross Sale", fill=(30, 41, 59), font=get_font(11, bold=True))
    d.text((520, 234), "Commission", fill=(30, 41, 59), font=get_font(11, bold=True))
    d.text((640, 234), "Net Paid", fill=(30, 41, 59), font=get_font(11, bold=True))
    d.text((740, 234), "Bank Ref / UTR", fill=(30, 41, 59), font=get_font(11, bold=True))

    # Row 1
    d.text((50, 280), "SET-20261119-0001", fill=(37, 99, 235), font=get_font(12, bold=True))
    d.text((50, 300), "19 Nov 2026, 11:53 PM", fill=(148, 163, 184), font=get_font(10, bold=False))

    d.text((200, 280), "#ORD-20261020-000001", fill=(15, 23, 42), font=get_font(12, bold=True))
    d.text((200, 300), "AyurSattva Charcoal Soap x1", fill=(100, 116, 139), font=get_font(10, bold=False))

    d.text((420, 280), "₹ 89.00", fill=(15, 23, 42), font=get_font(12, bold=False))
    d.text((520, 280), "-₹ 13.35 (15%)", fill=(220, 38, 38), font=get_font(12, bold=False))
    d.text((640, 280), "₹ 75.65", fill=(5, 150, 105), font=get_font(14, bold=True))

    d.rounded_rectangle([(740, 275), (900, 315)], radius=6, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
    d.text((748, 282), "UTR: T261113...598", fill=(4, 120, 87), font=get_font(11, bold=True))
    d.text((748, 298), "● Disbursed to BoB", fill=(4, 120, 87), font=get_font(9, bold=False))

    d.line([(40, 330), (w - 40, 330)], fill=(241, 245, 249), width=1)

    # Formula Explanatory Box
    d.rounded_rectangle([(50, 360), (w - 50, 500)], radius=8, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
    d.text((70, 375), "💡 Transparent Calculation Standard:", fill=(30, 41, 59), font=get_font(13, bold=True))
    d.text((70, 400), "Net Payout = Product Final Selling Price  -  (Product Price × Category Commission Rate)", fill=(15, 23, 42), font=get_font(12, bold=True))
    d.text((70, 425), "• Example above: ₹89.00 - 15% (₹13.35) = ₹75.65 Net Bank Credit.", fill=(71, 85, 105), font=get_font(11, bold=False))
    d.text((70, 445), "• No hidden payment gateway deductions, no listing fees, zero setup charges.", fill=(71, 85, 105), font=get_font(11, bold=False))
    d.text((70, 465), "• Direct bank credit via NEFT/RTGS with genuine UTR provided for your chartered accountant / GST filing.", fill=(71, 85, 105), font=get_font(11, bold=False))

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
            # Skip header & footer on cover page
            return

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#0f172a"))

        # Header
        self.drawString(36, 810, "STALLCART · OFFICIAL SELLER OPERATIONS MANUAL")
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawRightString(559, 810, "Partner Operations & Logistics Standard v2.0")
        
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.75)
        self.line(36, 802, 559, 802)

        # Footer
        self.line(36, 45, 559, 45)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(36, 32, "© 2026 StallCart Platform · Seller Helpdesk: +91 7307383046 · stallcartsupport@gmail.com")
        self.drawRightString(559, 32, f"Page {self._pageNumber} of {page_count}")

        self.restoreState()


# ─────────────────────────────────────────────────────────────
# 4. BUILD THE COMPLETE REPORTLAB PDF DOCUMENT
# ─────────────────────────────────────────────────────────────
def build_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    # Document setup
    doc = SimpleDocTemplate(
        PDF_OUTPUT_PATH,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom styles
    brand_emerald = colors.HexColor("#059669")
    brand_navy = colors.HexColor("#0f172a")
    text_dark = colors.HexColor("#1e293b")
    text_muted = colors.HexColor("#64748b")
    brand_blue = colors.HexColor("#2563eb")

    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=26,
        leading=32,
        textColor=brand_navy,
        alignment=0,
        spaceAfter=10
    )

    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=17,
        textColor=text_muted,
        alignment=0,
        spaceAfter=20
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=22,
        textColor=brand_navy,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=brand_emerald,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=text_dark,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=15,
        bulletIndent=5,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=brand_navy
    )

    caption_style = ParagraphStyle(
        'ImageCaption',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=11,
        textColor=text_muted,
        alignment=1,
        spaceBefore=4,
        spaceAfter=12
    )

    story = []

    # ── COVER PAGE ──
    story.append(Spacer(1, 40))
    
    # Brand Badge
    badge_table = Table(
        [[Paragraph("<b>STALLCART PARTNER ECOSYSTEM</b>", ParagraphStyle('Badge', fontName='Helvetica-Bold', fontSize=9, textColor=colors.HexColor('#047857')))]],
        colWidths=[210]
    )
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ecfdf5')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#a7f3d0')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 15))

    story.append(Paragraph("Seller Operations Manual<br/>&amp; Complete Partner Handbook", title_style))
    story.append(Paragraph(
        "A practical, visual operating standard for registered sellers on <b>StallCart</b> (stallcart.in). "
        "Includes step-by-step procedures for seller registration, product cataloging, order packaging, "
        "Shiprocket courier dispatch, and automated bank settlements with UTR audit trail.",
        subtitle_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=brand_emerald, spaceBefore=5, spaceAfter=20))

    # Metadata Grid
    meta_data = [
        [
            Paragraph("<b>Document Version:</b> 2.0 (Official Standard)", body_style),
            Paragraph("<b>Platform URL:</b> https://stallcart.in", body_style)
        ],
        [
            Paragraph("<b>Target Audience:</b> Verified StallCart Sellers &amp; Brands", body_style),
            Paragraph("<b>Courier Network:</b> Shiprocket &amp; Delhivery Express", body_style)
        ],
        [
            Paragraph("<b>Seller Support Hotline:</b> +91 7307383046", body_style),
            Paragraph("<b>Official Email:</b> stallcartsupport@gmail.com", body_style)
        ],
        [
            Paragraph("<b>Settlement Frequency:</b> Automated Post-Delivery / Weekly", body_style),
            Paragraph("<b>Disbursement Mode:</b> Direct Bank Transfer / UPI / UTR", body_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 30))

    # Quick Index Summary Box
    index_data = [
        [
            Paragraph("<b>Table of Contents / Core Modules</b>", ParagraphStyle('IdxH', fontName='Helvetica-Bold', fontSize=10, textColor=brand_navy))
        ],
        [
            Paragraph("<b>Module 1:</b> Seller Onboarding, Shop Setup &amp; Bank KYC Verification<br/>"
                      "<b>Module 2:</b> Product Cataloging, High-Resolution Images &amp; Variant Matrix<br/>"
                      "<b>Module 3:</b> Order Receiving Lifecycle &amp; Seller Dashboard Navigation<br/>"
                      "<b>Module 4:</b> Packaging Standard Operating Procedure (SOP) &amp; Tax Invoices<br/>"
                      "<b>Module 5:</b> Courier Pickup Scheduling, AWB Barcodes &amp; Handover Protocol<br/>"
                      "<b>Module 6:</b> Transactional Notifications (Email Alerts, SMS &amp; WhatsApp)<br/>"
                      "<b>Module 7:</b> Commission Accounting, Bank Disbursements &amp; UTR Audit Trail<br/>"
                      "<b>Module 8:</b> Customer Returns, RTO Management &amp; Support Escalations",
                      body_style)
        ]
    ]
    index_table = Table(index_data, colWidths=[520])
    index_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffffff')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(index_table)
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────
    # MODULE 1: SELLER REGISTRATION & BANK KYC
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Module 1: Seller Onboarding &amp; Bank KYC Verification", h1_style))
    story.append(Paragraph(
        "To begin selling on StallCart, every merchant must complete the verified seller registration. "
        "This ensures platform authenticity and establishes an encrypted link for automated seller payouts.",
        body_style
    ))
    story.append(Paragraph("<b>Step-by-Step Registration Workflow:</b>", h2_style))
    story.append(Paragraph("• <b>Step 1: Access Registration Portal:</b> Visit <code>https://stallcart.in/accounts/seller/register/</code> or click 'Become a Seller' on the homepage header.", bullet_style))
    story.append(Paragraph("• <b>Step 2: Business &amp; Shop Identity:</b> Enter your official Shop Name, primary contact number, and legal business name.", bullet_style))
    story.append(Paragraph("• <b>Step 3: Pickup Warehouse Location:</b> Provide the exact street address and 6-digit postal pincode where courier riders will collect packaged orders.", bullet_style))
    story.append(Paragraph("• <b>Step 4: Bank Account Details for Payouts:</b> Provide your official Bank Name, Account Number, and IFSC Code. Double check this carefully—all product earnings are disbursed to this account.", bullet_style))
    story.append(Paragraph("• <b>Step 5: KYC Verification:</b> StallCart staff verifies the phone number and bank IFSC within 1 business day. Once verified, your status switches to <b>KYC Approved ✓</b>.", bullet_style))
    story.append(Spacer(1, 8))

    # Embed Screenshot 1
    s1_path = os.path.join(SCREENSHOTS_DIR, 'screen_1_registration.png')
    story.append(RLImage(s1_path, width=520, height=305))
    story.append(Paragraph("Figure 1.1: StallCart Seller Registration and Bank Account Verification Screen", caption_style))
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────
    # MODULE 2: PRODUCT CATALOGING & VARIANTS
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Module 2: Product Cataloging, Images &amp; Variant Setup", h1_style))
    story.append(Paragraph(
        "Listing attractive products with accurate pricing and high-definition photography is essential to maximize your sales conversion on StallCart.",
        body_style
    ))
    story.append(Paragraph("<b>Key Fields in the Product Listing Form:</b>", h2_style))
    story.append(Paragraph("• <b>Product Title:</b> Include brand name, key ingredients or fabric, and package size (e.g., <i>AyurSattva Charcoal Detox Herbal Soap - 100g</i>).", bullet_style))
    story.append(Paragraph("• <b>Category &amp; Commission Tier:</b> Select the most accurate category. The transparent platform commission rate (typically 5% to 15%) is displayed automatically beside the category.", bullet_style))
    story.append(Paragraph("• <b>MRP vs Selling Price:</b> Specify the Maximum Retail Price (MRP) and your actual StallCart selling price. Offering a genuine discount of 15%-30% increases customer click-through.", bullet_style))
    story.append(Paragraph("• <b>Inventory Stock:</b> Enter the ready units available in your warehouse. StallCart automatically prevents orders when stock hits 0.", bullet_style))
    story.append(Paragraph("• <b>Variants Matrix:</b> For apparel, configure Size (S, M, L, XL) and Color. For grocery or cosmetics, configure Pack Sizes (Single, Pack of 3, 500g, 1Kg) with individual prices.", bullet_style))
    story.append(Paragraph("• <b>Photography Guidelines:</b> Upload minimum 3 photos per product. Use clean white/light neutral backgrounds with square aspect ratio (1:1) and no watermarks.", bullet_style))
    story.append(Spacer(1, 8))

    # Embed Screenshot 2
    s2_path = os.path.join(SCREENSHOTS_DIR, 'screen_2_product_listing.png')
    story.append(RLImage(s2_path, width=520, height=325))
    story.append(Paragraph("Figure 2.1: Add Product Form with Live Variant Matrix &amp; High-Resolution Photo Uploads", caption_style))
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────
    # MODULE 3: RECEIVING ORDERS & DASHBOARD
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Module 3: Order Receiving Lifecycle &amp; Seller Dashboard", h1_style))
    story.append(Paragraph(
        "When a shopper purchases your product on StallCart, the order is immediately dispatched to your dedicated seller dashboard at <code>/orders/seller/orders/</code>.",
        body_style
    ))
    story.append(Paragraph("<b>Order Status Lifecycle:</b>", h2_style))
    
    status_data = [
        [Paragraph("<b>Status</b>", ParagraphStyle('SH', fontName='Helvetica-Bold', fontSize=9, textColor=brand_navy)),
         Paragraph("<b>Meaning &amp; Required Seller Action</b>", ParagraphStyle('SH', fontName='Helvetica-Bold', fontSize=9, textColor=brand_navy))],
        [Paragraph("<b>Pending / Confirmed</b>", body_style),
         Paragraph("Customer has completed payment. Seller must click <b>Accept &amp; Pack Order</b> within 2 hours.", body_style)],
        [Paragraph("<b>Ready for Pickup</b>", body_style),
         Paragraph("Seller has packed the item and attached invoice. System assigns courier rider and generates Pickup Token.", body_style)],
        [Paragraph("<b>In Transit</b>", body_style),
         Paragraph("Courier rider has scanned the package and handed it over to the logistics hub. Moving towards buyer city.", body_style)],
        [Paragraph("<b>Out for Delivery</b>", body_style),
         Paragraph("Package has arrived at destination hub. Courier delivery agent is out to deliver to buyer door.", body_style)],
        [Paragraph("<b>Delivered (OTP Verified)</b>", body_style),
         Paragraph("Buyer provided 4-digit secret OTP to rider. Delivery complete! Order enters settlement eligibility queue.", body_style)]
    ]
    status_table = Table(status_data, colWidths=[130, 390])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f1f5f9')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(status_table)
    story.append(Spacer(1, 10))

    # Embed Screenshot 3
    s3_path = os.path.join(SCREENSHOTS_DIR, 'screen_3_orders_dashboard.png')
    story.append(RLImage(s3_path, width=520, height=305))
    story.append(Paragraph("Figure 3.1: Seller Orders Dashboard with Status Tabs, Customer Details &amp; Action Buttons", caption_style))
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────
    # MODULE 4: PACKAGING SOP & INVOICE
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Module 4: Packaging Standard Operating Procedure (SOP)", h1_style))
    story.append(Paragraph(
        "Proper packaging protects the item from damage during transit, minimizes returns, and ensures a delightful unboxing experience for StallCart customers.",
        body_style
    ))
    story.append(Paragraph("<b>5-Step Packing Protocol:</b>", h2_style))
    story.append(Paragraph("<b>1. Quality &amp; Variant Verification:</b> Verify the item SKU against the order sheet. Ensure correct size (e.g. Size M, not L) and that the product is factory-fresh.", bullet_style))
    story.append(Paragraph("<b>2. Primary Protective Wrapping:</b> Wrap the product in moisture-proof bubble wrap or air pouches. Secure with clear tape. Liquids must be double sealed.", bullet_style))
    story.append(Paragraph("<b>3. Secondary Outer Packaging:</b> Place in a branded StallCart tamper-evident polybag or sturdy corrugated box (3-ply or 5-ply).", bullet_style))
    story.append(Paragraph("<b>4. Tax Invoice Insertion:</b> Download the Tax Invoice from the Seller Portal (<code>/orders/order/&lt;id&gt;/invoice/</code>). Fold neatly and place inside the package or in the packing pouch.", bullet_style))
    story.append(Paragraph("<b>5. Affix Shipping AWB Label:</b> Print the Shiprocket / Delhivery courier label. Affix securely on the flat top surface. Never fold across the barcode or QR code.", bullet_style))
    story.append(Spacer(1, 8))

    # Embed Screenshot 4
    s4_path = os.path.join(SCREENSHOTS_DIR, 'screen_4_packing_sop.png')
    story.append(RLImage(s4_path, width=520, height=305))
    story.append(Paragraph("Figure 4.1: StallCart Packaging SOP and Tax Invoice / Barcode Placement Standard", caption_style))
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────
    # MODULE 5: SHIPROCKET COURIER PICKUP & DISPATCH
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Module 5: Courier Pickup Scheduling &amp; Dispatch", h1_style))
    story.append(Paragraph(
        "StallCart integrates directly with <b>Shiprocket</b>, <b>Delhivery</b>, and leading courier networks. "
        "Sellers do not need to negotiate courier contracts—StallCart automatically dispatches the fastest rider to your warehouse.",
        body_style
    ))
    story.append(Paragraph("<b>Pickup Handover Workflow:</b>", h2_style))
    story.append(Paragraph("• <b>Automatic Pickup Generation:</b> When you click 'Mark Ready for Pickup', the system generates a unique <b>Pickup Token</b> (e.g. <code>PKP-98210-SC</code>) and assigns a courier rider.", bullet_style))
    story.append(Paragraph("• <b>Rider Arrival Notification:</b> You will receive the rider's name, phone number, and scheduled arrival window on your dashboard and via SMS.", bullet_style))
    story.append(Paragraph("• <b>Barcode Scan Verification:</b> When the delivery rider arrives, verify their official courier ID. Hand over the package and ensure the rider scans the AWB barcode with their handheld scanner.", bullet_style))
    story.append(Paragraph("• <b>Pickup Receipt:</b> Take the signed physical or digital manifest confirmation from the rider.", bullet_style))
    story.append(Paragraph("• <b>OTP Delivery Guarantee:</b> To protect sellers against fraudulent delivery disputes, all high-value deliveries require the customer to verify a 4-digit secret OTP before the rider releases the box.", bullet_style))
    story.append(Spacer(1, 8))

    # Embed Screenshot 5
    s5_path = os.path.join(SCREENSHOTS_DIR, 'screen_5_shiprocket_pickup.png')
    story.append(RLImage(s5_path, width=520, height=305))
    story.append(Paragraph("Figure 5.1: Courier Dispatch Management &amp; Real-time Shipment Tracking Stepper", caption_style))
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────
    # MODULE 6: TRANSACTIONAL EMAILS & NOTIFICATIONS
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Module 6: Seller Transactional Notifications &amp; Alerts", h1_style))
    story.append(Paragraph(
        "StallCart keeps sellers fully informed at every milestone through automated email, SMS, and WhatsApp alerts.",
        body_style
    ))
    story.append(Paragraph("<b>Key Notification Types Received by Sellers:</b>", h2_style))
    story.append(Paragraph("• <b>1. New Order Notification Email:</b> Sent instantly when customer checkout succeeds. Details product name, size variant, quantity, delivery pincode, and target packing deadline.", bullet_style))
    story.append(Paragraph("• <b>2. Courier Pickup Confirmation:</b> Sent when the courier rider scans and collects the package from your doorstep.", bullet_style))
    story.append(Paragraph("• <b>3. Delivery Confirmation Alert:</b> Sent when the order is successfully delivered to the customer door via OTP.", bullet_style))
    story.append(Paragraph("• <b>4. Settlement Processed Email:</b> Sent when platform admin executes your bank payout. Includes exact bank account number, net amount, and bank UTR reference number.", bullet_style))
    story.append(Spacer(1, 8))

    # Embed Screenshot 6
    s6_path = os.path.join(SCREENSHOTS_DIR, 'screen_6_notification_emails.png')
    story.append(RLImage(s6_path, width=520, height=305))
    story.append(Paragraph("Figure 6.1: Sample Transactional Emails Received by StallCart Sellers", caption_style))
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────
    # MODULE 7: SETTLEMENTS & BANK DISBURSEMENT
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Module 7: Settlements, Commissions &amp; Bank Payouts", h1_style))
    story.append(Paragraph(
        "StallCart operates on a transparent, audit-ready financial settlement model. Sellers receive direct bank transfers with complete transaction references.",
        body_style
    ))
    story.append(Paragraph("<b>How Seller Earnings Are Calculated:</b>", h2_style))
    
    formula_data = [
        [Paragraph("<b>Earnings Formula:</b>", ParagraphStyle('FH', fontName='Helvetica-Bold', fontSize=10, textColor=brand_navy)),
         Paragraph("<code>Net Seller Payable = Item Selling Price  -  Platform Category Commission</code>", ParagraphStyle('FC', fontName='Helvetica-Bold', fontSize=10, textColor=brand_emerald))],
        [Paragraph("<b>Sample Calculation:</b>", body_style),
         Paragraph("Selling Price: ₹89.00<br/>Category Commission (15%): -₹13.35<br/><b>Net Bank Payout to Seller: ₹75.65</b>", body_style)],
        [Paragraph("<b>Payout Schedule:</b>", body_style),
         Paragraph("Orders are eligible for payout once marked Delivered and the 7-day return period clears.", body_style)],
        [Paragraph("<b>Disbursement Methods:</b>", body_style),
         Paragraph("Direct Bank Transfer (NEFT / RTGS / IMPS / UPI) or Instant RazorpayX Payout API.", body_style)],
        [Paragraph("<b>Proof of Payment:</b>", body_style),
         Paragraph("Every disbursal records an official <b>Bank UTR Number</b> (e.g. <code>T2611131350345249750598</code>) visible in your dashboard and email.", body_style)]
    ]
    formula_table = Table(formula_data, colWidths=[140, 380])
    formula_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(formula_table)
    story.append(Spacer(1, 10))

    # Embed Screenshot 7
    s7_path = os.path.join(SCREENSHOTS_DIR, 'screen_7_settlement_statement.png')
    story.append(RLImage(s7_path, width=520, height=305))
    story.append(Paragraph("Figure 7.1: Seller Settlement Statement &amp; Financial Ledger with Bank UTR", caption_style))
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────
    # MODULE 8: RETURNS, RTO & SELLER SUPPORT
    # ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Module 8: Returns, RTO Management &amp; Seller Support", h1_style))
    story.append(Paragraph(
        "Handling customer returns and unexpected transit issues smoothly is critical to maintaining a 5-star seller rating on StallCart.",
        body_style
    ))
    story.append(Paragraph("<b>Customer Returns &amp; RTO Policies:</b>", h2_style))
    story.append(Paragraph("• <b>7-Day Return Window:</b> Customers can initiate a return within 7 calendar days of delivery for defective, incorrect size, or damaged products.", bullet_style))
    story.append(Paragraph("• <b>Seller Quality Inspection:</b> Returned items are shipped back to your warehouse via reverse pickup. Sellers inspect the returned item before refund clearance.", bullet_style))
    story.append(Paragraph("• <b>Return to Origin (RTO):</b> If a customer is unreachable after 3 delivery attempts, the package is marked RTO and safely returned to your pickup warehouse. Zero platform commission is charged on RTO orders.", bullet_style))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Official StallCart Seller Support Channels:</b>", h2_style))
    
    support_data = [
        [Paragraph("<b>Channel</b>", ParagraphStyle('SH', fontName='Helvetica-Bold', fontSize=9, textColor=brand_navy)),
         Paragraph("<b>Details &amp; Availability</b>", ParagraphStyle('SH', fontName='Helvetica-Bold', fontSize=9, textColor=brand_navy))],
        [Paragraph("<b>WhatsApp Seller Desk</b>", body_style),
         Paragraph("<b>+91 7307383046</b> (Quick response for urgent pickup &amp; order issues · 9 AM - 9 PM)", body_style)],
        [Paragraph("<b>Seller Email Support</b>", body_style),
         Paragraph("<b>stallcartsupport@gmail.com</b> (Catalog approvals, bank changes &amp; dispute escalations)", body_style)],
        [Paragraph("<b>Web Chatbot Assistant</b>", body_style),
         Paragraph("Available 24/7 on homepage (<code>stallcart.in</code>) with instant seller manual &amp; query registration.", body_style)],
        [Paragraph("<b>Seller Dashboard</b>", body_style),
         Paragraph("<code>https://stallcart.in/items/dashboard/</code> (Live analytics, payouts &amp; inventory controls)", body_style)]
    ]
    support_table = Table(support_data, colWidths=[140, 380])
    support_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ecfdf5')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#a7f3d0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 7),
    ]))
    story.append(support_table)
    story.append(Spacer(1, 20))

    # Closing Notice Box
    closing_data = [
        [
            Paragraph("<b>Welcome to the StallCart Family!</b><br/>"
                      "We are committed to helping your business grow across India with fast logistics, "
                      "fair commissions, and dependable payouts. Thank you for partnering with StallCart.",
                      ParagraphStyle('Close', fontName='Helvetica', fontSize=10, leading=14, textColor=brand_navy))
        ]
    ]
    closing_table = Table(closing_data, colWidths=[520])
    closing_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1.5, brand_emerald),
        ('PADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(closing_table)

    # Build Document
    print(f"Building PDF at: {PDF_OUTPUT_PATH} ...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print("PDF build complete!")

    # Copy to media/manuals as well
    import shutil
    shutil.copyfile(PDF_OUTPUT_PATH, MEDIA_PDF_PATH)
    print(f"Copied to media path: {MEDIA_PDF_PATH}")
    print(f"Final file size: {os.path.getsize(PDF_OUTPUT_PATH)} bytes")


def main():
    print("=== Generating StallCart Seller Manual Screenshots ===")
    generate_screen_1_registration()
    generate_screen_2_product_listing()
    generate_screen_3_orders_dashboard()
    generate_screen_4_packing_sop()
    generate_screen_5_shiprocket_pickup()
    generate_screen_6_notification_emails()
    generate_screen_7_settlement_statement()
    print("All 7 screenshots generated successfully!")

    print("=== Building Official PDF Manual ===")
    build_pdf()
    print("=== All Steps Finished Successfully! ===")


if __name__ == '__main__':
    main()
