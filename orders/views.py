# orders/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction, models
from django.utils import timezone
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
import razorpay
import json
import logging
from decimal import Decimal
from io import BytesIO
from common.decorators import *
from .models import Order, OrderItem, ReturnRequest, OrderStatusLog, OrderReturnImage, SellerSettlement
from items.models import Product, SellerProfile
from delivery.models import DeliveryPartner
from django.conf import settings
import hmac, hashlib, json
from django.views.decorators.csrf import csrf_exempt
logger = logging.getLogger(__name__)
User = get_user_model()

from common.notification_service import (
    notify_order_placed,
    notify_order_shipped,
    notify_order_out_for_delivery,
    notify_order_delivered
)

# ==================== RAZORPAY CLIENT ====================
razorpay_client = razorpay.Client(auth=(
    settings.RAZORPAY_KEY_ID,
    settings.RAZORPAY_KEY_SECRET
))

def get_friendly_remark(status, remarks):
    """
    Returns a customer-friendly description for the timeline status log.
    If the remark is a developer/system debug string or empty, we return a professional status description.
    """
    remarks_lower = (remarks or "").lower()
    
    # Check if the remark is system-generated / debug
    is_system = (
        not remarks
        or "automatically updated" in remarks_lower
        or "automatic synchronization" in remarks_lower
        or "automatically synced" in remarks_lower
        or "overall status updated" in remarks_lower
        or "automatically pushed" in remarks_lower
        or "failed to auto-push" in remarks_lower
        or "sent manual awb" in remarks_lower
        or "awaiting tracking" in remarks_lower
    )
    
    if is_system:
        # Return friendly status defaults
        friendly_defaults = {
            'pending': 'Your order has been placed successfully.',
            'confirmed': 'Your order has been confirmed by the seller.',
            'processing': 'Your order is being packed and prepared for pickup.',
            'shipped': 'Your package is in transit with our courier partner.',
            'out_for_delivery': 'Your package is out for delivery and will reach you today.',
            'delivered': 'Your package has been delivered successfully.',
            'cancelled': 'Your order has been cancelled.',
            'returned_to_source': 'Your package is returning to the source (RTO).',
            'returned': 'The return was completed successfully.',
            'refund_initiated': 'Refund has been initiated for your order.',
            'refunded': 'Refund has been successfully credited.',
            'courier_failed_pickup': 'Courier partner failed to pick up your package. Refund has been initiated to your source account (should reflect within 3-5 business days).',
            'seller_unresponsive': 'Seller did not proceed with fulfilling your order. Refund has been initiated to your source account (should reflect within 3-5 business days).',
        }
        return friendly_defaults.get(status, '')
        
    return remarks


def build_cleaned_timeline(order):
    """
    Builds a list of status log entries for public/seller timelines.
    Excludes internal developer debug logs (where status didn't transition)
    and logs containing technical/system messages (like API payloads or alert emails).
    """
    status_logs = order.cleaned_status_logs
    status_labels = {
        'pending': 'Order Placed', 
        'confirmed': 'Order Confirmed',
        'processing': 'Processing', 
        'shipped': 'Shipped',
        'out_for_delivery': 'Out for Delivery', 
        'delivered': 'Delivered',
        'returned_to_source': 'Returned to Source (RTO)',
        'returned': 'Returned & Refunded',
        'cancelled': 'Cancelled',
        'courier_failed_pickup': 'Pickup Failed (Courier)',
        'seller_unresponsive': 'Seller Unresponsive',
    }
    
    cleaned_timeline = []
    for log in status_logs:
        # Skip explicit developer debug/error remarks
        remarks = log.remarks or ""
        if remarks.startswith("❌") or remarks.startswith("⚠️") or "API Request Payload" in remarks or "Failed to auto-push" in remarks:
            continue
            
        cleaned_timeline.append({
            'status': log.new_status,
            'label': status_labels.get(log.new_status, log.new_status),
            'get_new_status_display': log.get_new_status_display(),
            'timestamp': log.timestamp,
            'remarks': get_friendly_remark(log.new_status, remarks),
        })
    return cleaned_timeline

# ==================== CUSTOMER VIEWS ====================

# orders/views.py
@customer_only
def my_orders(request):
    """Customer: View all orders with tracking"""
    # ✅ Ensure we filter by logged-in user only
    orders = Order.objects.filter(
        user=request.user
    
    ).prefetch_related(
        'items__product', 
        'items__product__seller',
        'status_logs'
    ).order_by('-created_at')
    
    # ✅ Pass clear context to template
    context = {
        'orders': orders,
        'total_orders': orders.count(),
        'delivered_orders': orders.filter(status='delivered').count(),
        'in_progress_orders': orders.filter(
            status__in=['pending','confirmed','processing','shipped','out_for_delivery']
        ).count(),
    }
    return render(request, 'orders/my_orders.html', context)

def sync_shiprocket_tracking(order):
    """
    Sync order status dynamically from Shiprocket live tracking.
    Returns shiprocket_tracking dict or None.
    """
    shiprocket_tracking = None
    terminal_statuses = (
        'delivered', 'cancelled', 'returned', 'returned_to_source',
        'refund_initiated', 'refunded', 'courier_failed_pickup', 'seller_unresponsive'
    )
    if order.tracking_number and order.status not in terminal_statuses:
        from delivery.delivery_services import ShiprocketService
        from orders.models import OrderStatusLog
        from django.utils import timezone
        try:
            srv = ShiprocketService()
            shiprocket_tracking = srv.get_tracking(order.tracking_number)
            if shiprocket_tracking and shiprocket_tracking.get('current_status'):
                sr_status = shiprocket_tracking['current_status'].strip()
                # Status mapping to local db status
                status_map = {
                    'awb assigned': 'confirmed',
                    'manifested': 'processing',
                    'out for pickup': 'processing',
                    'pickup scheduled': 'processing',
                    'pickup queued': 'processing',
                    'pickup': 'shipped',
                    'picked up': 'shipped',
                    'picked-up': 'shipped',
                    'in transit': 'shipped',
                    'shipped': 'shipped',
                    'out for delivery': 'out_for_delivery',
                    'delivered': 'delivered',
                    'rto': 'returned_to_source',
                    'returned to source': 'returned_to_source',
                    'cancelled': 'cancelled',
                    'canceled': 'cancelled'
                }
                new_local_status = status_map.get(sr_status.lower())
                if new_local_status and new_local_status != order.status:
                    old_status = order.status
                    order.status = new_local_status
                    if new_local_status == 'delivered':
                        order.delivered_at = timezone.now()
                    order.save(update_fields=['status', 'delivered_at', 'updated_at'])
                    
                    # Create status change log
                    OrderStatusLog.objects.create(
                        order=order,
                        old_status=old_status,
                        new_status=new_local_status,
                        remarks=f"Automatic synchronization from Shiprocket (Status: {sr_status})"
                    )
        except Exception as e:
            logger.warning(f"Shiprocket live status synchronization failed for order {order.id}: {e}")
            
    # If fallback case, but tracking number exists, try to get live cached tracking anyway
    elif order.tracking_number and order.status not in terminal_statuses:
        from delivery.delivery_services import ShiprocketService
        try:
            srv = ShiprocketService()
            shiprocket_tracking = srv.get_tracking(order.tracking_number)
        except Exception:
            pass
            
    return shiprocket_tracking


@customer_only
def order_detail(request, order_id):
    """Customer: View single order with tracking timeline"""
    order = get_object_or_404(Order, unique_order_id=order_id, user=request.user)
    
    # Live Shiprocket sync
    shiprocket_tracking = sync_shiprocket_tracking(order)
    
    timeline = build_cleaned_timeline(order)
    
    context = {
        'order': order,
        'timeline': timeline,
        'delivery': getattr(order, 'delivery_task', None),
        'shiprocket_tracking': shiprocket_tracking,
    }
    return render(request, 'orders/order_detail.html', context)

@require_POST
@login_required
def cancel_order(request, order_id):
    """Customer: Cancel order (if eligible)"""
    order = get_object_or_404(Order, unique_order_id=order_id, user=request.user)
    
    if not order.is_cancellable:
        return JsonResponse({'error': 'Order cannot be cancelled at this stage'}, status=400)
    
    data = json.loads(request.body)
    reason = data.get('reason', 'other')
    remarks = data.get('remarks', '')
    
    with transaction.atomic():
        old_status = order.status
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.cancellation_reason = reason
        order.cancellation_remarks = remarks
        order.save()
        order.items.all().update(status='cancelled')
        
        OrderStatusLog.objects.create(
            order=order, old_status=old_status, new_status='cancelled',
            changed_by=request.user, remarks=f'Cancelled by customer: {remarks}'
        )
    
    messages.success(request, f"Order {order.unique_order_id} cancelled successfully")
    return JsonResponse({'status': 'success', 'redirect': '/orders/'})

@login_required
def request_return(request, order_item_id):
    """Customer: Request return for an item"""
    order_item = get_object_or_404(OrderItem, id=order_item_id, order__user=request.user)
    
    if not order_item.product.is_returnable:
        messages.error(request, "This item is non-returnable")
        return redirect('orders:order_detail', order_id=order_item.order.unique_order_id)
        
    if not order_item.order.is_returnable:
        messages.error(request, "Return window has closed for this order")
        return redirect('orders:order_detail', order_id=order_item.order.unique_order_id)
    
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            quantity = 1
            
        reason = request.POST.get('reason')
        remarks = request.POST.get('remarks', '')
        
        if quantity < 1 or quantity > order_item.remaining_quantity:
            messages.error(request, "Invalid return quantity")
            return redirect('orders:order_detail', order_id=order_item.order.unique_order_id)
            
        with transaction.atomic():
            return_req = ReturnRequest.objects.create(
                order_item=order_item,
                user=request.user,
                quantity=quantity,
                reason=reason,
                remarks=remarks,
                refund_amount=order_item.price * quantity,
            )
            
            # Save uploaded images
            files = request.FILES.getlist('images')
            for i, f in enumerate(files[:3]):  # Limit to 3 images
                OrderReturnImage.objects.create(
                    return_request=return_req,
                    image=f,
                    caption=f"Evidence {i+1}",
                    is_primary=(i == 0)
                )
                
        messages.success(request, "Return request submitted successfully.")
        return redirect('orders:return_detail', return_id=return_req.id)
        
    context = {
        'order_item': order_item,
        'reasons': Order.RETURN_REASONS,
        'remaining_quantity': order_item.remaining_quantity
    }
    return render(request, 'orders/return_form.html', context)

@login_required
def return_detail(request, return_id):
    """View return request status (Customer, Seller of item, or Admin)"""
    return_req = get_object_or_404(ReturnRequest, id=return_id)
    
    # Check permissions:
    is_authorized = False
    if request.user == return_req.user or request.user.is_staff or request.user.is_superuser:
        is_authorized = True
    elif hasattr(request.user, 'seller_profile') and return_req.order_item.product.seller == request.user.seller_profile:
        is_authorized = True
        
    if not is_authorized:
        from django.http import Http404
        raise Http404("You are not authorized to view this return request.")
        
    context = {'return_request': return_req}
    return render(request, 'orders/return_detail.html', context)

# Add this view in orders/views.py under CUSTOMER VIEWS section

# Add this under CUSTOMER VIEWS section in orders/views.py

@require_POST
@customer_only
def reorder_order(request, order_id):
    """
    Customer: Reorder by redirecting to first available product's detail page.
    No session manipulation - pure DB lookup + redirect.
    """
    # Fetch order - ensure it belongs to logged-in user
    order = get_object_or_404(
        Order.objects.select_related('user'),
        unique_order_id=order_id,
        user=request.user
    )
    
    # Only allow reorder for delivered or cancelled orders
    if order.status not in ['delivered', 'cancelled']:
        messages.warning(request, "Only delivered or cancelled orders can be reordered.")
        return redirect('orders:order_detail', order_id=order_id)
    
    # Find first available, active product from this order
    first_available_item = order.items.filter(
        product__is_active=True,
        product__status='published'  # assuming you have this field
    ).select_related('product').first()
    
    if first_available_item and first_available_item.product:
        product = first_available_item.product
        
        # Build redirect URL with reorder context
        redirect_url = f"{product.get_absolute_url()}?reorder_from={order.unique_order_id}"
        
        return JsonResponse({
            'status': 'success',
            'redirect_url': redirect_url,
            'message': f'Redirecting to "{product.name}"',
            'product_name': product.name,
            'order_id': order.unique_order_id,
            'total_items': order.items.count()
        })
    
    # Fallback: no available items
    return JsonResponse({
        'status': 'error',
        'message': 'No available items to reorder. Products may be out of stock or unpublished.'
    }, status=400)
def get_invoice_context(request, order):
    """
    Build context for the invoice.html template.
    If the user is a seller, filter the items and calculate seller-specific totals
    so they only see their own products/totals and no commission/earnings leak.
    """
    from decimal import Decimal
    role = getattr(request.user, 'role', 'customer')
    is_seller = (role == 'seller')
    
    if is_seller and hasattr(request.user, 'seller_profile'):
        order_items = order.items.filter(seller__user=request.user).select_related('product', 'variant')
        items_subtotal = sum(item.total for item in order_items)
        items_commission = sum(item.commission_amount for item in order_items)
        items_earnings = sum(item.seller_earnings for item in order_items)
        invoice_seller = request.user.seller_profile
    else:
        order_items = order.items.all().select_related('product', 'variant', 'seller')
        items_subtotal = order.mrp_subtotal
        items_commission = Decimal('0.00')
        items_earnings = Decimal('0.00')
        
        # Determine the invoice seller for customers/admins (default to first item's seller for consolidated/admin views)
        invoice_seller = order_items[0].seller if order_items.exists() else None
        
    return {
        'order': order,
        'order_items': order_items,
        'is_seller': is_seller,
        'items_subtotal': items_subtotal,
        'items_commission': items_commission,
        'items_earnings': items_earnings,
        'invoice_seller': invoice_seller,
    }


@login_required
def download_invoice(request, order_id):
    """
    Generate & download PDF invoice using xhtml2pdf (macOS compatible).
    Falls back to HTML download if PDF generation fails.
    """
    # 1. Fetch order with related data based on user role (prevent N+1)
    role = getattr(request.user, 'role', 'customer')
    if role == 'seller':
        order = get_object_or_404(
            Order.objects.filter(items__seller__user=request.user).prefetch_related('items__product', 'items__seller').distinct(),
            unique_order_id=order_id
        )
    elif request.user.is_staff or request.user.is_superuser:
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product', 'items__seller'),
            unique_order_id=order_id
        )
    else:
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product', 'items__seller'),
            unique_order_id=order_id,
            user=request.user
        )
    
    context = get_invoice_context(request, order)
    
    # 2. Render template WITH request for context processors
    try:
        html_string = render_to_string(
            'orders/invoice.html',
            context,
            request=request  # 🔑 Critical for site_settings context processor
        )
    except Exception as e:
        logger.error(f"Template render error for invoice {order_id}: {e}")
        messages.error(request, "Could not generate invoice. Please try again.")
        return redirect('orders:order_detail', order_id=order_id)
    
    # 3. Generate PDF using xhtml2pdf
    try:
        from xhtml2pdf import pisa
        
        # Create response with PDF content type
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="invoice-{order.unique_order_id}.pdf"'
        
        # Generate PDF - dest=response writes directly to HttpResponse
        pdf_result = pisa.CreatePDF(
            src=html_string,
            dest=response,
            encoding='utf-8',
            # Optional: Handle relative image URLs
            link_callback=lambda uri, rel: _link_callback(uri, rel, request)
        )
        
        # Check for errors
        if pdf_result.err:
            logger.error(f"xhtml2pdf errors: {pdf_result.err}")
            messages.error(request, "Could not generate PDF. Downloading as HTML instead.")
            return _download_invoice_html(request, order)
        
        # Success - PDF is already in response
        return response
        
    except ImportError:
        logger.error("xhtml2pdf not installed. Run: pip install xhtml2pdf")
        messages.error(
            request, 
            "PDF generation requires xhtml2pdf. Please contact support or download as HTML."
        )
        return _download_invoice_html(request, order)
        
    except Exception as e:
        logger.error(f"PDF generation failed for order {order_id}: {e}", exc_info=True)
        messages.error(request, f"Could not generate PDF: {str(e)[:100]}")
        return _download_invoice_html(request, order)



def _link_callback(uri, rel, request):
    """
    Convert relative media URLs to absolute paths for xhtml2pdf.
    Handles static files and user uploads.
    """
    from django.contrib.staticfiles.storage import staticfiles_storage
    from django.conf import settings
    import os
    
    # Strip protocol and host if pointing to our own server to avoid loopback deadlock
    host = request.get_host()
    if uri.startswith(f"http://{host}"):
        uri = uri[len(f"http://{host}"):]
    elif uri.startswith(f"https://{host}"):
        uri = uri[len(f"https://{host}"):]
    
    # Handle static files
    if uri.startswith(settings.STATIC_URL):
        path = uri.replace(settings.STATIC_URL, '', 1)
        try:
            return staticfiles_storage.path(path)
        except:
            return None
    
    # Handle media files
    if uri.startswith(settings.MEDIA_URL):
        path = uri.replace(settings.MEDIA_URL, '', 1)
        media_path = os.path.join(settings.MEDIA_ROOT, path)
        if os.path.exists(media_path):
            return media_path
        return None
    
    # Handle absolute URLs - try to download
    if uri.startswith('http'):
        import urllib.request
        import tempfile
        try:
            with urllib.request.urlopen(uri) as response:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                    tmp.write(response.read())
                    return tmp.name
        except:
            pass
    
    return None


def _download_invoice_html(request, order):
    """Fallback: Download invoice as HTML file for browser PDF conversion"""
    context = get_invoice_context(request, order)
    html_string = render_to_string('orders/invoice.html', context, request=request)
    
    response = HttpResponse(html_string, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="invoice-{order.unique_order_id}.html"'
    messages.info(
        request, 
        "Downloaded as HTML. Open the file in your browser and use 'Print → Save as PDF'."
    )
    return response


@login_required
def export_invoice_csv(request, order_id):
    """
    Export single order invoice details as CSV for the seller, customer, or admin.
    """
    role = getattr(request.user, 'role', 'customer')
    if role == 'seller':
        order = get_object_or_404(
            Order.objects.filter(items__seller__user=request.user).prefetch_related('items__product', 'items__seller').distinct(),
            unique_order_id=order_id
        )
    elif request.user.is_staff or request.user.is_superuser:
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product', 'items__seller'),
            unique_order_id=order_id
        )
    else:
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product', 'items__seller'),
            unique_order_id=order_id,
            user=request.user
        )
        
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="invoice-{order.unique_order_id}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['INVOICE / BILL DETAILS'])
    writer.writerow([])
    writer.writerow(['Order ID', order.unique_order_id])
    writer.writerow(['Order Date', order.created_at.strftime('%Y-%m-%d %I:%M %p')])
    writer.writerow([])
    
    # Billing Info
    billing = order.billing_address
    writer.writerow(['BILL TO'])
    writer.writerow(['Name', billing.name if billing else (order.user.full_name if order.user else order.guest_email)])
    writer.writerow(['Address Line 1', billing.address_line1 if billing else ''])
    writer.writerow(['Address Line 2', billing.address_line2 if billing else ''])
    writer.writerow(['City', billing.city if billing else ''])
    writer.writerow(['State', billing.state if billing else ''])
    writer.writerow(['Postal Code', billing.postal_code if billing else ''])
    writer.writerow(['Country', billing.country if billing else 'India'])
    writer.writerow(['Phone', billing.phone if billing else (order.guest_phone or (order.user.phone if order.user else ''))])
    writer.writerow([])
    
    # Seller Info (use logged-in seller if seller is viewing, otherwise default to first item's seller)
    if role == 'seller' and hasattr(request.user, 'seller_profile'):
        seller = request.user.seller_profile
    else:
        seller = order.items.first().seller if order.items.exists() else None

    if seller:
        writer.writerow(['SELLER DETAILS'])
        writer.writerow(['Shop Name', seller.shop_name])
        writer.writerow(['GSTIN', seller.gst_number if seller.gst_number else 'N/A'])
        writer.writerow([])
        
    # Write Items
    writer.writerow(['ORDER ITEMS'])
    writer.writerow(['Product Name', 'SKU', 'Seller', 'Price (Rs.)', 'Quantity', 'Total (Rs.)'])
    
    items = order.items.all()
    if role == 'seller':
        items = items.filter(seller__user=request.user)
        
    for item in items:
        writer.writerow([
            item.product.name,
            item.product.sku or 'N/A',
            item.seller.shop_name if item.seller else 'StallCart',
            f"{item.price:.2f}",
            item.quantity,
            f"{item.total:.2f}"
        ])
    
    writer.writerow([])
    
    # Summary
    if role == 'seller':
        subtotal = sum(i.total for i in items)
        commission = sum(i.commission_amount for i in items)
        earnings = sum(i.seller_earnings for i in items)
        writer.writerow(['SUMMARY (YOUR ITEMS)'])
        writer.writerow(['Items Total', f"Rs. {subtotal:.2f}"])
        writer.writerow(['Platform Commission', f"-Rs. {commission:.2f}"])
        writer.writerow(['Your Earnings', f"Rs. {earnings:.2f}"])
    else:
        writer.writerow(['SUMMARY'])
        writer.writerow(['MRP Subtotal', f"Rs. {order.mrp_subtotal:.2f}"])
        if order.discount_amount:
            writer.writerow(['Discount', f"-Rs. {order.discount_amount:.2f}"])
        if order.delivery_charge:
            writer.writerow(['Delivery Charge', f"Rs. {order.delivery_charge:.2f}"])
        tax_amount = getattr(order, 'tax_amount', 0) or 0
        if tax_amount:
            writer.writerow(['Tax (GST)', f"Rs. {tax_amount:.2f}"])
        writer.writerow(['Grand Total', f"Rs. {order.total_amount:.2f}"])
        
    return response


@login_required
def preview_invoice(request, order_id):
    """
    Preview invoice in browser (HTML) for client-side PDF export.
    Add ?print=1 to URL to auto-open print dialog.
    """
    role = getattr(request.user, 'role', 'customer')
    if role == 'seller':
        order = get_object_or_404(
            Order.objects.filter(items__seller__user=request.user).prefetch_related('items__product').distinct(),
            unique_order_id=order_id
        )
    elif request.user.is_staff or request.user.is_superuser:
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product'),
            unique_order_id=order_id
        )
    else:
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product'),
            unique_order_id=order_id,
            user=request.user
        )
    
    context = get_invoice_context(request, order)
    html_string = render_to_string(
        'orders/invoice.html',
        context,
        request=request
    )
    
    return HttpResponse(html_string)


@login_required
def debug_invoice(request, order_id):
    """
    Debug endpoint to test invoice generation.
    Access: /orders/order/ORD-XXXXXX/invoice/debug/
    """
    role = getattr(request.user, 'role', 'customer')
    if role == 'seller':
        order = get_object_or_404(
            Order.objects.filter(items__seller__user=request.user).distinct(),
            unique_order_id=order_id
        )
    elif request.user.is_staff or request.user.is_superuser:
        order = get_object_or_404(Order, unique_order_id=order_id)
    else:
        order = get_object_or_404(Order, unique_order_id=order_id, user=request.user)
    
    # Test 1: Template render
    try:
        context = get_invoice_context(request, order)
        html = render_to_string('orders/invoice.html', context, request=request)
        test1 = "✅ Template rendered"
    except Exception as e:
        return JsonResponse({'error': f'Template render failed: {str(e)}'}, status=500)
    
    # Test 2: xhtml2pdf import
    try:
        from xhtml2pdf import pisa
        test2 = "✅ xhtml2pdf imported"
    except ImportError as e:
        return JsonResponse({'error': f'xhtml2pdf not installed: {str(e)}'}, status=500)
    
    # Test 3: PDF generation
    try:
        dest = BytesIO()
        result = pisa.CreatePDF(html, dest=dest, encoding='utf-8')
        if result.err:
            return JsonResponse({'error': f'PDF errors: {result.err}'}, status=500)
        test3 = f"✅ PDF generated ({len(dest.getvalue())} bytes)"
    except Exception as e:
        return JsonResponse({'error': f'PDF generation failed: {str(e)}'}, status=500)
    
    return JsonResponse({
        'order_id': order.unique_order_id,
        'status': 'success',
        'tests': [test1, test2, test3],
        'message': 'All checks passed! PDF should download correctly.',
        'download_url': request.build_absolute_uri(
            f"/orders/order/{order_id}/invoice/download/"
        )
    })
# ==================== SELLER VIEWS ====================

@seller_only
def seller_orders(request):
    """Seller: View all orders containing their products"""
    if not ((request.user.role == 'seller' or request.user.is_admin) and hasattr(request.user, 'seller_profile')):
        messages.error(request, "Only sellers and staff can view this page.")
        return redirect('shop:home')
    
    seller = request.user.seller_profile
    order_items = OrderItem.objects.filter(
        product__seller=seller
    ).select_related('order', 'product', 'order__user').prefetch_related(
        'order__items__product'
    ).order_by('-order__created_at')
    
    # ── Search & Filter ──────────────────────────────────────────
    from django.db.models import Q
    from datetime import datetime
    
    q = request.GET.get('q', '').strip()
    if q:
        query = Q(order__unique_order_id__icontains=q) | \
                Q(order__user__full_name__icontains=q) | \
                Q(order__user__phone__icontains=q) | \
                Q(order__guest_email__icontains=q) | \
                Q(order__guest_phone__icontains=q)
        
        # Support inline date search (e.g. YYYY-MM-DD)
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(q, fmt).date()
                query |= Q(order__created_at__date=dt)
                break
            except ValueError:
                continue
        order_items = order_items.filter(query)
        
    date_filter = request.GET.get('date', '').strip()
    if date_filter:
        try:
            dt = datetime.strptime(date_filter, "%Y-%m-%d").date()
            order_items = order_items.filter(order__created_at__date=dt)
        except ValueError:
            pass
            
    status_filter = request.GET.get('status')
    if status_filter:
        order_items = order_items.filter(status=status_filter)
        
    pending_count = order_items.filter(status='pending').count()
    delivered_count = order_items.filter(status='delivered').count()
    pending_returns = ReturnRequest.objects.filter(
        order_item__product__seller=seller,
        status__in=['requested', 'approved', 'pickup_scheduled', 'picked_up', 'received']
    ).select_related('order_item__product', 'order_item__order', 'order_item__variant').order_by('-created_at')

    context = {'order_items': order_items, 'seller': seller, 'filters': request.GET.dict(),
            'pending_count': pending_count,
            'delivered_count': delivered_count,
            'pending_returns': pending_returns,
            }
    return render(request, 'orders/seller_order.html', context)

@login_required
def seller_order_detail(request, order_id):
    """Seller: View details of a specific order containing their products"""
    if not ((request.user.role == 'seller' or request.user.is_admin) and hasattr(request.user, 'seller_profile')):
        messages.error(request, "Only sellers and staff can view this page.")
        return redirect('shop:home')
    
    seller = request.user.seller_profile
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        unique_order_id=order_id
    )
    
    seller_items = order.items.filter(product__seller=seller).select_related('product')
    if not seller_items.exists():
        messages.error(request, "You are not authorized to view this order.")
        return redirect('shop:home')
    
    # Calculate financial totals for the seller
    seller_items_total = Decimal('0.00')
    seller_commission_total = Decimal('0.00')
    seller_earnings_total = Decimal('0.00')
    
    for item in seller_items:
        seller_items_total += item.total
        seller_commission_total += item.commission_amount
        seller_earnings_total += item.seller_earnings

    # Live Shiprocket sync
    shiprocket_tracking = sync_shiprocket_tracking(order)

    timeline = build_cleaned_timeline(order)
    
    pending_returns = ReturnRequest.objects.filter(
        order_item__order=order,
        order_item__product__seller=seller,
        status__in=['requested', 'approved', 'pickup_scheduled', 'picked_up', 'received']
    ).select_related('order_item__product', 'order_item__order', 'order_item__variant')
    
    context = {
        'order': order, 'seller_items': seller_items, 'timeline': timeline,
        'delivery': getattr(order, 'delivery_task', None),
        'seller_items_total': seller_items_total,
        'seller_commission_total': seller_commission_total,
        'seller_earnings_total': seller_earnings_total,
        'pending_returns': pending_returns,
        'shiprocket_tracking': shiprocket_tracking,
    }
    return render(request, 'orders/seller_order_detail.html', context)


@require_POST
@login_required
def seller_update_status(request, order_id):
    """Seller: Update order status (e.g., mark as shipped/delivered/returned)"""
    if not (is_seller_or_admin(request.user)):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    order = get_object_or_404(Order, unique_order_id=order_id)
    
    # If seller, verify they own items in the order
    if not request.user.is_superuser:
        seller = request.user.seller_profile
        if not order.items.filter(product__seller=seller).exists():
            return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if order.status not in ['pending', 'confirmed', 'processing', 'shipped', 'delivered']:
        return JsonResponse({'error': 'Order cannot be updated at this stage'}, status=400)
    
    data = json.loads(request.body)
    new_status = data.get('status')
    
    if new_status not in ['processing', 'shipped', 'delivered', 'returned']:
        return JsonResponse({'error': 'Invalid status transition'}, status=400)
    
    with transaction.atomic():
        old_status = order.status
        
        # Identify items to update
        if request.user.is_superuser:
            items_to_update = order.items.all()
        else:
            items_to_update = order.items.filter(seller=request.user.seller_profile)
            
        # Update items
        for item in items_to_update:
            item.status = new_status
            item.shiprocket_status = None
            if new_status == 'shipped':
                item.shipped_at = timezone.now()
            elif new_status == 'delivered':
                item.delivered_at = timezone.now()
            item.save(update_fields=['status', 'shipped_at', 'delivered_at', 'shiprocket_status', 'updated_at'])
            
        # Update overall order status
        order.update_overall_status()
        # Clear overall order shiprocket status since seller overrode items manually
        order.shiprocket_status = None
        order.save(update_fields=['shiprocket_status', 'updated_at'])
        
        OrderStatusLog.objects.create(
            order=order, old_status=old_status, new_status=new_status,
            changed_by=request.user, remarks=f'Updated to {new_status} for seller items.'
        )
        
        if new_status in ['confirmed', 'processing']:
            from delivery.delivery_services import auto_push_order_to_shiprocket
            transaction.on_commit(lambda: auto_push_order_to_shiprocket(order))
    
    if new_status == 'shipped':
        try:
            first_item = items_to_update.first()
            tracking_no = first_item.tracking_number if first_item else order.tracking_number
            notify_order_shipped(order, tracking_no)
        except Exception as e:
            logger.error(f"[FCM] Seller update shipped notification failed for order {order.id}: {e}")
    
    return JsonResponse({'status': 'success', 'new_status': order.get_status_display()})

@require_POST
@login_required
def seller_add_tracking(request, order_id):
    """Seller/Admin: Add or edit courier tracking number"""
    if not (is_seller_or_admin(request.user)):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    order = get_object_or_404(Order, unique_order_id=order_id)
    
    # If seller, verify they own items in the order
    if not request.user.is_superuser:
        seller = request.user.seller_profile
        items_to_update = order.items.filter(seller=seller)
        if not items_to_update.exists():
            return JsonResponse({'error': 'Unauthorized'}, status=403)
    else:
        items_to_update = order.items.all()
            
    data = json.loads(request.body)
    tracking_number = data.get('tracking_number')
    courier_name = data.get('courier_name', 'Shiprocket')
    
    # Update tracking details at the item level
    for item in items_to_update:
        item.tracking_number = tracking_number
        item.courier_name = courier_name
        item.save(update_fields=['tracking_number', 'courier_name', 'updated_at'])
    
    # For compatibility/fallback
    order.tracking_number = tracking_number
    order.courier_name = courier_name
    order.save(update_fields=['tracking_number', 'courier_name', 'updated_at'])
        
    return JsonResponse({'status': 'success', 'message': 'Tracking updated'})


@login_required
def print_shipping_label(request, order_id):
    """
    Seller/Admin: Print a clean shipping label for a specific order.
    Pulls official Shiprocket label if shipment is registered,
    otherwise falls back to custom label with full Shiprocket tracking details.
    """
    role = getattr(request.user, 'role', 'customer')
    if role == 'seller':
        if not hasattr(request.user, 'seller_profile'):
            messages.error(request, "Only verified sellers can access this page.")
            return redirect('shop:home')
        seller = request.user.seller_profile
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product', 'items__seller'),
            unique_order_id=order_id
        )
        # Verify the seller has items in this order
        seller_items = order.items.filter(product__seller=seller)
        if not seller_items.exists():
            messages.error(request, "You are not authorized to print the label for this order.")
            return redirect('shop:home')
    elif request.user.is_staff or request.user.is_superuser:
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product', 'items__seller'),
            unique_order_id=order_id
        )
        seller = order.items.first().seller if order.items.exists() else None
        seller_items = order.items.all()
    else:
        messages.error(request, "Access denied.")
        return redirect('shop:home')

    # Try to fetch official Shiprocket label PDF if Shiprocket is configured
    from django.conf import settings
    from delivery.delivery_services import ShiprocketService

    shiprocket_email = getattr(settings, 'SHIPROCKET_EMAIL', None)
    shiprocket_password = getattr(settings, 'SHIPROCKET_PASSWORD', None)

    if shiprocket_email and shiprocket_password:
        try:
            shipment_id = order.shipment_id
            srv = ShiprocketService()

            # If shipment_id is not stored, try to retrieve it dynamically from Shiprocket
            if not shipment_id:
                details = srv.fetch_shipment_details_by_channel_order_id(order.unique_order_id)
                if details:
                    order.shiprocket_order_id = details.get("shiprocket_order_id")
                    order.shipment_id = details.get("shipment_id")
                    order.save(update_fields=["shiprocket_order_id", "shipment_id", "updated_at"])
                    shipment_id = order.shipment_id

            if shipment_id:
                label_url = srv.get_label_url(shipment_id)
                if label_url:
                    # Redirect directly to official PDF label
                    return redirect(label_url)
        except Exception as e:
            # Log error and fall back gracefully to custom label template
            import logging
            logging.getLogger(__name__).error(f"Error fetching Shiprocket label PDF for order {order.unique_order_id}: {e}")

    # Calculate total quantity of seller's items in this order
    total_qty = sum(item.quantity for item in seller_items)

    # Format the seller address
    if seller and hasattr(seller, 'shop_address') and seller.shop_address:
        shop_addr = seller.shop_address
        address_parts = [shop_addr.address_line1]
        if shop_addr.address_line2:
            address_parts.append(shop_addr.address_line2)
        from_details = {
            'name': shop_addr.shop_name or seller.shop_name,
            'address': ", ".join(address_parts),
            'city': shop_addr.city,
            'state': shop_addr.state,
            'pincode': shop_addr.postal_code,
            'phone': '',
        }
    else:
        seller_addr = seller.address if seller else {}
        from_details = {
            'name': seller.shop_name if seller else 'StallCart Seller',
            'address': seller_addr.get('address', ''),
            'city': seller_addr.get('city', ''),
            'state': seller_addr.get('state', ''),
            'pincode': seller_addr.get('postalCode', '') or seller_addr.get('pincode', ''),
            'phone': '',
        }

    # Format the customer address
    to_details = {
        'name': order.shipping_address.get('name', ''),
        'address_line1': order.shipping_address.get('address_line1', ''),
        'address_line2': order.shipping_address.get('address_line2', ''),
        'city': order.shipping_address.get('city', ''),
        'state': order.shipping_address.get('state', ''),
        'pincode': order.shipping_address.get('postal_code', ''),
        'phone': order.shipping_address.get('phone', ''),
    }

    # Generate vector barcode bars pattern based on AWB/Tracking number or Order ID
    bars = []
    barcode_val = order.tracking_number or order.unique_order_id
    barcode_str = f"*{barcode_val}*"
    for char in barcode_str:
        val = ord(char)
        # Output 9 binary bars/spaces per character for Code 39-like look
        for i in range(9):
            bars.append(1 if (val & (1 << (i % 8))) else 0)
            bars.append(0)

    context = {
        'order': order,
        'from_details': from_details,
        'to_details': to_details,
        'total_qty': total_qty,
        'bars': bars,
        'barcode_val': barcode_val,
    }
    return render(request, 'orders/shipping_label.html', context)


# ==================== ADMIN VIEWS ====================

# @login_required
# @user_passes_test(lambda u: u.is_superuser)
@admin_only
def admin_orders(request):
    """Admin: View all orders system-wide"""
    orders = Order.objects.select_related('user', 'delivery_task__partner').prefetch_related('items__product').order_by('-created_at')
    
    # ── Search & Filter ──────────────────────────────────────────
    from django.db.models import Q
    from datetime import datetime
    
    q = request.GET.get('q', '').strip()
    if q:
        query = Q(unique_order_id__icontains=q) | \
                Q(user__full_name__icontains=q) | \
                Q(user__phone__icontains=q) | \
                Q(guest_email__icontains=q) | \
                Q(guest_phone__icontains=q)
        
        # Support inline date search (e.g. YYYY-MM-DD)
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(q, fmt).date()
                query |= Q(created_at__date=dt)
                break
            except ValueError:
                continue
        orders = orders.filter(query)
        
    date_filter = request.GET.get('date', '').strip()
    if date_filter:
        try:
            dt = datetime.strptime(date_filter, "%Y-%m-%d").date()
            orders = orders.filter(created_at__date=dt)
        except ValueError:
            pass
            
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)
        
    pending_count = Order.objects.filter(status='pending').count()
    delivered_count = Order.objects.filter(status='delivered').count()
    
    pending_returns = ReturnRequest.objects.filter(
        status__in=['requested', 'approved', 'pickup_scheduled', 'picked_up', 'received']
    ).select_related('order_item__product', 'order_item__order', 'order_item__variant').order_by('-created_at')
    
    context = {
        'orders': orders, 
        'filters': request.GET.dict(),
        'pending_returns': pending_returns,
        'pending_count': pending_count,
        'delivered_count': delivered_count,
    }
    return render(request, 'orders/admin_orders.html', context)

@admin_only
def admin_order_detail(request, order_id):
    """Admin: Full order detail view"""
    order = get_object_or_404(Order, unique_order_id=order_id)
    context = {'order': order}
    return render(request, 'orders/admin_order_detail.html', context)

@require_POST
@admin_only
def admin_update_status(request, order_id):
    """Admin: Update any order status"""
    order = get_object_or_404(Order, unique_order_id=order_id)
    data = json.loads(request.body)
    new_status = data.get('status')
    
    if new_status not in dict(Order.STATUS_CHOICES) or new_status == 'cancelled':
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    with transaction.atomic():
        old_status = order.status
        order.status = new_status
        order.shiprocket_status = None
        order.status_updated_at = timezone.now()
        if new_status == 'delivered':
            order.delivered_at = timezone.now()
        order.save()
        
        # Propagate status to all items
        for item in order.items.all():
            item.status = new_status
            item.shiprocket_status = None
            if new_status == 'shipped':
                item.shipped_at = timezone.now()
            elif new_status == 'delivered':
                item.delivered_at = timezone.now()
            item.save(update_fields=['status', 'shipped_at', 'delivered_at', 'shiprocket_status', 'updated_at'])
        
        OrderStatusLog.objects.create(
            order=order, old_status=old_status, new_status=new_status,
            changed_by=request.user, remarks='Updated by admin'
        )
        
        if new_status in ['confirmed', 'processing']:
            from delivery.delivery_services import auto_push_order_to_shiprocket
            transaction.on_commit(lambda: auto_push_order_to_shiprocket(order))
    
    if new_status != old_status:
        try:
            if new_status in ['pending', 'confirmed']:
                notify_order_placed(order)
            elif new_status == 'shipped':
                notify_order_shipped(order, order.tracking_number)
            elif new_status == 'out_for_delivery':
                notify_order_out_for_delivery(order)
            elif new_status == 'delivered':
                notify_order_delivered(order)
        except Exception as e:
            logger.error(f"[FCM] Admin update notification failed for order {order.id} (status: {new_status}): {e}")
    
    return JsonResponse({'status': 'success'})

# ==================== WEBHOOKS ====================

# @require_POST
# def razorpay_webhook(request):
#     """Handle Razorpay payment events"""
#     signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
#     body = request.body
    
#     try:
#         razorpay_client.utility.verify_webhook_signature(
#             body.decode('utf-8'), signature, settings.RAZORPAY_WEBHOOK_SECRET
#         )
        
#         event = json.loads(body)
#         if event.get('event') == 'payment.captured':
#             payment = event['payload']['payment']['entity']
#             order = Order.objects.filter(razorpay_payment_id=payment['id']).first()
            
#             if order:
#                 with transaction.atomic():
#                     order.payment_status = 'paid'
#                     if order.status == 'pending':
#                         order.status = 'confirmed'
#                         order.status_updated_at = timezone.now()
#                         OrderStatusLog.objects.create(
#                             order=order, old_status='pending', new_status='confirmed',
#                             remarks='Payment captured via Razorpay'
#                         )
#                     order.save()
                    
#                     for item in order.items.all():
#                         item.product.stock -= item.quantity
#                         item.product.save()
        
#         return HttpResponse(status=200)
#     except Exception as e:
#         logger.error(f"Razorpay webhook error: {e}")
#         return HttpResponse(status=400)


@csrf_exempt  # Razorpay webhooks don't send CSRF
def razorpay_webhook(request):
    """
    Handle Razorpay webhook events:
    - payment.captured (for order confirmation fallback)
    - refund.processed (mark refund as completed)
    - refund.failed (alert admin)
    """
    
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Verify webhook signature
    signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
    if not signature or not hasattr(settings, 'RAZORPAY_WEBHOOK_SECRET'):
        return JsonResponse({'error': 'Missing signature or secret'}, status=400)
    
    expected_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        request.body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        logger.warning("Razorpay webhook signature mismatch")
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    try:
        event = json.loads(request.body)
        entity = event.get('payload', {}).get('refund', {}).get('entity', {})
        event_type = event.get('event', '')
        
        if event_type == 'refund.processed' and entity.get('status') == 'processed':
            razorpay_refund_id = entity.get('id')
            return_req = ReturnRequest.objects.filter(
                razorpay_refund_id=razorpay_refund_id
            ).first()
            
            if return_req:
                return_req.refund_status = 'completed'
                return_req.save(update_fields=['refund_status', 'updated_at'])
                logger.info(f"Refund {razorpay_refund_id} marked as completed")
                # Optional: Notify customer refund completed
                # send_refund_completed_notification(return_req)
        
        elif event_type == 'refund.failed':
            razorpay_refund_id = entity.get('id')
            return_req = ReturnRequest.objects.filter(
                razorpay_refund_id=razorpay_refund_id
            ).first()
            if return_req:
                return_req.refund_status = 'failed'
                return_req.refund_failure_reason = entity.get('error', {}).get('description', 'Unknown error')
                return_req.save(update_fields=['refund_status', 'refund_failure_reason', 'updated_at'])
                logger.error(f"Refund {razorpay_refund_id} failed: {return_req.refund_failure_reason}")
                # Optional: Alert admin
                # send_admin_alert(f"Refund failed for Return #{return_req.id}")
        
        return JsonResponse({'status': 'ok'}, status=200)
        
    except Exception as e:
        logger.exception(f"Error processing Razorpay webhook: {e}")
        return JsonResponse({'error': 'Internal error'}, status=500)
@csrf_exempt
@require_POST
def shiprocket_webhook(request):
    """Handle Shiprocket delivery tracking updates"""
    try:
        data = json.loads(request.body)
        
        # Extract AWB and Order ID
        awb = data.get('awb')
        order_id = data.get('order_id')
        sr_status = data.get('current_status')
        
        if not awb and not order_id:
            logger.warning("Shiprocket webhook received with no AWB or Order ID.")
            return HttpResponse("Missing AWB or Order ID", status=400)
            
        if not sr_status:
            logger.warning("Shiprocket webhook received with no current_status.")
            return HttpResponse("Missing current_status", status=400)
            
        # Find Order or OrderItem
        order_item = None
        order = None
        if awb:
            order_item = OrderItem.objects.filter(tracking_number=awb).first()
            if order_item:
                order = order_item.order
            else:
                order = Order.objects.filter(tracking_number=awb).first()
        if not order and order_id:
            order = Order.objects.filter(unique_order_id=order_id).first()
            
        if not order:
            logger.warning(f"Shiprocket webhook: Order not found for AWB={awb}, OrderID={order_id}")
            return HttpResponse("Order not found", status=404)
            
        sr_status = sr_status.strip()
        status_map = {
            'awb assigned': 'confirmed',
            'manifested': 'processing',
            'out for pickup': 'processing',
            'pickup scheduled': 'processing',
            'pickup queued': 'processing',
            'pickup': 'shipped',
            'picked up': 'shipped',
            'picked-up': 'shipped',
            'in transit': 'shipped',
            'shipped': 'shipped',
            'out for delivery': 'out_for_delivery',
            'delivered': 'delivered',
            'rto': 'returned_to_source',
            'returned to source': 'returned_to_source',
            'cancelled': 'cancelled',
            'canceled': 'cancelled',
            'pickup failed': 'courier_failed_pickup',
            'pickup exception': 'courier_failed_pickup',
            'pickup_failed': 'courier_failed_pickup',
            'pickup_exception': 'courier_failed_pickup',
        }
        
        new_local_status = status_map.get(sr_status.lower())
        
        with transaction.atomic():
            order.shiprocket_status = sr_status
            order.save(update_fields=['shiprocket_status', 'updated_at'])
            
            if new_local_status:
                if order_item:
                    # Update status of specific order item
                    order_item.shiprocket_status = sr_status
                    if order_item.status != new_local_status:
                        old_status = order.status
                        order_item.status = new_local_status
                        if new_local_status == 'delivered':
                            order_item.delivered_at = timezone.now()
                        elif new_local_status == 'shipped' and not order_item.shipped_at:
                            order_item.shipped_at = timezone.now()
                        order_item.save(update_fields=['status', 'shipped_at', 'delivered_at', 'shiprocket_status', 'updated_at'])
                        
                        # Recalculate overall status
                        order.update_overall_status()
                        
                        logger.info(f"Shiprocket Webhook: Updated order item {order_item.id}. Status: {new_local_status}. Order status recalculated to {order.status}")
                    else:
                        order_item.save(update_fields=['shiprocket_status', 'updated_at'])
                else:
                    # Fallback to updating the overall order status and items
                    tracking_updated = False
                    if awb and not order.tracking_number:
                        order.tracking_number = awb
                        tracking_updated = True

                    if (new_local_status and new_local_status != order.status) or tracking_updated:
                        old_status = order.status
                        update_fields = ['updated_at', 'shiprocket_status']
                        
                        if new_local_status and new_local_status != order.status:
                            order.status = new_local_status
                            update_fields.append('status')
                            if new_local_status == 'delivered':
                                order.delivered_at = timezone.now()
                                update_fields.append('delivered_at')
                            elif new_local_status == 'shipped' and not order.shipped_at:
                                order.shipped_at = timezone.now()
                                update_fields.append('shipped_at')
                                
                        if tracking_updated:
                            update_fields.append('tracking_number')
                            
                        order.save(update_fields=update_fields)
                        
                        # Sync down to all order items that don't have separate tracking numbers
                        items_to_sync = order.items.filter(tracking_number__isnull=True) | order.items.filter(tracking_number='')
                        for item in items_to_sync:
                            item.status = new_local_status
                            item.shiprocket_status = sr_status
                            if new_local_status == 'shipped':
                                item.shipped_at = timezone.now()
                            elif new_local_status == 'delivered':
                                item.delivered_at = timezone.now()
                            item.save(update_fields=['status', 'shipped_at', 'delivered_at', 'shiprocket_status', 'updated_at'])

                        # Create status change log
                        OrderStatusLog.objects.create(
                            order=order,
                            old_status=old_status,
                            new_status=new_local_status,
                            remarks=f"Automatic update via Shiprocket Webhook (AWB: {awb}, status: {sr_status})"
                        )
                        logger.info(f"Shiprocket Webhook: Updated order {order.unique_order_id}. Status: {old_status} -> {order.status}.")
            
        return HttpResponse("OK", status=200)
        
    except json.JSONDecodeError:
        logger.error("Shiprocket webhook: Invalid JSON payload received.")
        return HttpResponse("Invalid JSON", status=400)
    except Exception as e:
        logger.exception(f"Shiprocket webhook error: {e}")
        return HttpResponse(f"Internal Error: {e}", status=500)

# ==================== PUBLIC/UTILITY ====================

@require_GET
def track_order_public(request, order_id):
    """Public order tracking (like Flipkart) - no login required"""
    order = get_object_or_404(Order, unique_order_id=order_id)
    
    if order.status not in ['shipped', 'out_for_delivery', 'delivered']:
        if order.guest_email and order.guest_email != request.GET.get('email'):
            return render(request, 'orders/tracking_not_found.html', {'order_id': order_id})
    
    # Live Shiprocket sync
    shiprocket_tracking = sync_shiprocket_tracking(order)
    
    timeline = build_cleaned_timeline(order)
    context = {
        'order': order, 
        'timeline': timeline,
        'shiprocket_tracking': shiprocket_tracking
    }
    return render(request, 'orders/track_public.html', context)

def order_success(request, order_id):
    """Order success page after payment"""
    order = get_object_or_404(Order, unique_order_id=order_id)
    
    # Optional: Log payment_id from query param for audit
    payment_id = request.GET.get('payment_id')
    if payment_id and order.razorpay_payment_id != payment_id:
        logger.warning(f"Payment ID mismatch for order {order_id}: DB={order.razorpay_payment_id}, URL={payment_id}")
    
    context = {'order': order}
    return render(request, 'orders/order_success.html', context)

def order_failed(request):
    """Order failed/cancelled page"""
    return render(request, 'orders/order_failed.html')



# Initialize Razorpay client (lazy load to avoid startup errors)
def get_razorpay_client():
    if not hasattr(settings, 'RAZORPAY_KEY_ID') or not settings.RAZORPAY_KEY_ID:
        return None
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        timeout=30
    )


def is_seller_or_admin(user):
    """Check if user is admin or seller"""
    return user.is_authenticated and (user.is_staff or user.is_superuser or getattr(user, 'role', None) == 'seller')


@login_required
@user_passes_test(is_seller_or_admin)
@require_POST
def approve_return(request, return_id):
    """
    Approve, reject, mark received, or approve refund for a return request.
    
    POST payload:
    {
        "action": "approve" | "reject" | "mark_received" | "approve_refund",
        "rejection_reason": "string (required if action=reject)"
    }
    """
    try:
        import json
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON payload'}, status=400)
    
    action = data.get('action', '').lower()
    if action not in ['approve', 'reject', 'mark_received', 'approve_refund']:
        return JsonResponse({'status': 'error', 'message': 'Invalid action. Use "approve", "reject", "mark_received", or "approve_refund"'}, status=400)
    
    # Get return request with related objects
    return_req = get_object_or_404(
        ReturnRequest.objects.select_related(
            'order_item', 
            'order_item__order',
            'order_item__product',
            'order_item__variant'
        ),
        id=return_id
    )
    
    # Permission check: seller can only manage returns for their own products
    if not request.user.is_staff and not request.user.is_superuser:
        if not hasattr(request.user, 'seller_profile') or return_req.order_item.product.seller != request.user.seller_profile:
            return JsonResponse(
                {'status': 'error', 'message': 'You can only manage returns for your own products'}, 
                status=403
            )
            
    order_item = return_req.order_item
    order = order_item.order
    product = order_item.product
    variant = order_item.variant
    
    # === REJECT FLOW ===
    if action == 'reject':
        if return_req.status not in ['requested', 'received']:
            return JsonResponse({'status': 'error', 'message': f'Return request cannot be rejected from status {return_req.status}'}, status=400)
        rejection_reason = data.get('rejection_reason', '').strip()
        if not rejection_reason:
            return JsonResponse({'status': 'error', 'message': 'Rejection reason is required'}, status=400)
        
        return_req.status = 'rejected'
        return_req.rejection_reason = rejection_reason
        return_req.actioned_by = request.user
        return_req.actioned_at = timezone.now()
        return_req.save(update_fields=['status', 'rejection_reason', 'actioned_by', 'actioned_at', 'updated_at'])
        
        logger.info(f"Return #{return_id} rejected by {request.user}: {rejection_reason}")
        return JsonResponse({
            'status': 'success',
            'message': 'Return request rejected',
            'return_id': return_req.id,
            'new_status': 'rejected'
        })
        
    # === APPROVE RETURN REQUEST FLOW ===
    elif action == 'approve':
        if return_req.status != 'requested':
            return JsonResponse({'status': 'error', 'message': f'Return request is already {return_req.status}'}, status=400)
            
        return_req.status = 'approved'
        return_req.actioned_by = request.user
        return_req.actioned_at = timezone.now()
        return_req.save(update_fields=['status', 'actioned_by', 'actioned_at', 'updated_at'])
        
        logger.info(f"Return #{return_id} approved (pickup authorized) by {request.user}")
        return JsonResponse({
            'status': 'success',
            'message': 'Return request approved. Courier pickup authorized.',
            'return_id': return_req.id,
            'new_status': 'approved'
        })

    # === MARK RECEIVED FLOW ===
    elif action == 'mark_received':
        if return_req.status not in ['approved', 'pickup_scheduled', 'picked_up']:
            return JsonResponse({'status': 'error', 'message': f'Return request cannot be marked as received from status {return_req.status}'}, status=400)
            
        return_req.status = 'received'
        return_req.save(update_fields=['status', 'updated_at'])
        
        logger.info(f"Return #{return_id} marked as received at warehouse by {request.user}")
        return JsonResponse({
            'status': 'success',
            'message': 'Return marked as received at warehouse.',
            'return_id': return_req.id,
            'new_status': 'received'
        })

    # === APPROVE REFUND FLOW ===
    elif action == 'approve_refund':
        if return_req.status != 'received':
            return JsonResponse({'status': 'error', 'message': f'Refund can only be approved for received returns. Current status: {return_req.status}'}, status=400)
            
        with transaction.atomic():
            # 1. Restock the product/variant
            qty_to_restock = return_req.quantity
            if variant:
                variant.stock = (variant.stock or 0) + qty_to_restock
                variant.save(update_fields=['stock', 'updated_at'])
                logger.info(f"Restocked {qty_to_restock} units of variant #{variant.id}")
            else:
                product.stock = (product.stock or 0) + qty_to_restock
                product.save(update_fields=['stock', 'updated_at'])
                logger.info(f"Restocked {qty_to_restock} units of product #{product.id}")
            
            # 2. Mark order item as returned
            order_item.is_returned = True
            order_item.returned_quantity = (order_item.returned_quantity or 0) + qty_to_restock
            order_item.save(update_fields=['is_returned', 'returned_quantity', 'updated_at'])
            
            # 3. Update return request status
            return_req.status = 'completed'
            return_req.refund_initiated_at = timezone.now()
            return_req.save(update_fields=['status', 'refund_initiated_at', 'updated_at'])
            
            # 4. Process refund based on payment method
            refund_result = _process_refund(order, return_req, qty_to_restock)
            
            # 5. Update order status if all items are returned
            _update_order_status_if_fully_returned(order)
            
        logger.info(f"Refund for return #{return_id} approved & processed by {request.user}, result: {refund_result}")
        return JsonResponse({
            'status': 'success',
            'message': 'Refund approved & processed successfully.',
            'return_id': return_req.id,
            'new_status': 'completed',
            'refund': refund_result,
            'restocked': {
                'product': product.name,
                'variant': variant.name if variant else None,
                'quantity': qty_to_restock
            }
        })



def _process_refund(order, return_req, qty_to_restock):
    """
    Internal helper: Process refund via Razorpay, Wallet, or credit to Wallet for COD.
    """
    payment_method = order.payment_method.lower()
    razorpay_payment_id = order.razorpay_payment_id
    refund_amount = return_req.refund_amount
    
    result = {
        'amount': float(refund_amount),
        'currency': 'INR',
        'method': payment_method,
        'status': 'pending',
        'razorpay_refund_id': None
    }
    
    # 1. Wallet Payment: Wallet concept is commented out/disabled; redirect to manual bank transfer
    if payment_method == 'wallet':
        return_req.refund_status = 'manual_pending'
        return_req.refund_method = 'bank'
        return_req.save(update_fields=['refund_status', 'refund_method', 'updated_at'])
        result['status'] = 'manual_pending'
        result['method'] = 'bank'
        result['note'] = 'Wallet payments are disabled; refund marked for manual bank transfer'
        return result
        
    # 2. Razorpay Payment: Try Razorpay API refund to source. Do NOT fallback to Wallet.
    elif payment_method == 'razorpay' and razorpay_payment_id:
        client = get_razorpay_client()
        if client:
            try:
                refund_data = {
                    'payment_id': razorpay_payment_id,
                    'amount': int(refund_amount * 100),
                    'notes': {
                        'return_id': return_req.id,
                        'order_id': order.id,
                        'reason': return_req.reason,
                        'initiated_by': return_req.actioned_by.phone if return_req.actioned_by else 'system'
                    }
                }
                razorpay_refund = client.refund.create(refund_data)
                return_req.razorpay_refund_id = razorpay_refund.get('id')
                return_req.refund_status = 'processing'
                return_req.refund_method = 'original'
                return_req.save(update_fields=['razorpay_refund_id', 'refund_status', 'refund_method', 'updated_at'])
                result['status'] = 'processing'
                result['razorpay_refund_id'] = razorpay_refund.get('id')
                return result
            except Exception as e:
                logger.error(f"Razorpay refund failed for returned item RTN-{return_req.id}: {e}")
                
        # Set status to failed instead of falling back to wallet
        return_req.refund_status = 'failed'
        return_req.refund_method = 'original'
        return_req.save(update_fields=['refund_status', 'refund_method', 'updated_at'])
        result['status'] = 'failed'
        result['note'] = 'Razorpay refund failed/skipped; marked as failed'
        return result
        
    # 3. COD Payment: COD has no online source, mark for manual bank transfer instead of wallet deposit
    elif payment_method == 'cod':
        return_req.refund_status = 'manual_pending'
        return_req.refund_method = 'bank'
        return_req.save(update_fields=['refund_status', 'refund_method', 'updated_at'])
        result['status'] = 'manual_pending'
        result['method'] = 'bank'
        result['note'] = 'COD order: refund marked for manual bank transfer'
        return result
        
    else:
        # Unknown/unsupported payment method: set to failed
        return_req.refund_status = 'failed'
        return_req.save(update_fields=['refund_status', 'updated_at'])
        result['status'] = 'failed'
        result['note'] = 'Unsupported payment method; marked as failed'
        return result


def _update_order_status_if_fully_returned(order):
    """
    Internal helper: If all items in an order are returned, 
    update order status to 'returned'.
    """
    total_items = order.items.count()
    returned_items = order.items.filter(is_returned=True).count()
    
    if total_items > 0 and total_items == returned_items:
        old_status = order.status
        order.status = 'returned'
        order.save(update_fields=['status', 'updated_at'])
        logger.info(f"Order #{order.id} status updated: {old_status} → returned (all items returned)")


@login_required
@user_passes_test(is_seller_or_admin)
@require_POST
def confirm_rto_refund(request, order_id):
    """
    Seller/Admin: Confirm returned items receipt at source and process refund to customer wallet.
    """
    order = get_object_or_404(Order, unique_order_id=order_id)
    
    # Permission check: seller can only manage their own products in that order
    is_seller = not request.user.is_staff and not request.user.is_superuser
    if is_seller:
        if not hasattr(request.user, 'seller_profile'):
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        seller = request.user.seller_profile
        items_to_rto = order.items.filter(seller=seller)
        if not items_to_rto.exists():
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
    else:
        items_to_rto = order.items.all()
        
    if order.status != 'returned_to_source':
        has_rto_item = items_to_rto.filter(status='returned_to_source').exists()
        if not has_rto_item:
            return JsonResponse({'status': 'error', 'message': f'Order is in {order.status} state, and no items are in returned_to_source state'}, status=400)
        
    with transaction.atomic():
        # 1. Restock products/variants and update status to returned
        refund_amount = Decimal('0.00')
        for item in items_to_rto:
            if not item.is_returned:
                qty = item.quantity
                if item.variant:
                    item.variant.stock = (item.variant.stock or 0) + qty
                    item.variant.save(update_fields=['stock', 'updated_at'])
                else:
                    item.product.stock = (item.product.stock or 0) + qty
                    item.product.save(update_fields=['stock', 'updated_at'])
                    
                item.is_returned = True
                item.returned_quantity = qty
                item.status = 'returned'
                item.save(update_fields=['is_returned', 'returned_quantity', 'status', 'updated_at'])
                refund_amount += item.total
                
        if refund_amount <= 0:
            return JsonResponse({'status': 'error', 'message': 'No items to refund'}, status=400)
            
        # 2. Refund to customer
        refund_note = ""
        payment_method = order.payment_method.lower()
        if payment_method == 'wallet':
            order.payment_status = 'refunded'
            order.refund_amount = (order.refund_amount or Decimal('0.00')) + refund_amount
            order.refund_at = timezone.now()
            refund_note = f"RTO Refund: pending manual bank transfer of Rs. {refund_amount} (wallet disabled)"
        elif payment_method == 'razorpay' and order.razorpay_payment_id:
            client = get_razorpay_client()
            if client:
                try:
                    razorpay_refund = client.refund.create({
                        'payment_id': order.razorpay_payment_id,
                        'amount': int(refund_amount * 100),
                        'notes': {'order_id': order.unique_order_id, 'reason': 'RTO'}
                    })
                    order.razorpay_refund_id = razorpay_refund.get('id')
                    order.payment_status = 'refunded'
                    order.refund_amount = (order.refund_amount or Decimal('0.00')) + refund_amount
                    order.refund_at = timezone.now()
                    refund_note = f"refunded Rs. {refund_amount} to original source (Razorpay ID: {razorpay_refund.get('id')})"
                except Exception as e:
                    logger.error(f"RTO Razorpay refund failed for {order.unique_order_id}: {e}")
                    order.payment_status = 'failed'
                    refund_note = f"Razorpay refund of Rs. {refund_amount} failed; manual refund required"
            else:
                logger.error(f"RTO Razorpay refund failed for {order.unique_order_id}: Razorpay client not configured")
                order.payment_status = 'failed'
                refund_note = f"Razorpay client not configured; manual refund of Rs. {refund_amount} required"
        elif payment_method == 'cod':
            order.payment_status = 'refunded'
            order.refund_amount = (order.refund_amount or Decimal('0.00')) + refund_amount
            refund_note = f"COD refund: pending manual bank transfer of Rs. {refund_amount}"
        else:
            order.payment_status = 'failed'
            refund_note = f"Unsupported payment method; manual refund of Rs. {refund_amount} required"
        
        # 3. Update Order Status
        old_status = order.status
        order.update_overall_status()
        
        order.save(update_fields=['payment_status', 'refund_amount', 'refund_at', 'razorpay_refund_id', 'updated_at'])
        
        # 4. Log status change
        OrderStatusLog.objects.create(
            order=order,
            old_status=old_status,
            new_status=order.status,
            changed_by=request.user,
            remarks=f"RTO refund processed: {refund_note}"
        )
        
    return JsonResponse({
        'status': 'success',
        'message': f'RTO receipt confirmed. Refund details: {refund_note}.',
        'new_status': order.get_status_display()
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def admin_trigger_payout_ajax(request, settlement_id):
    """Trigger RazorpayX payout for a settlement."""
    from django.db import transaction
    with transaction.atomic():
        settlement = SellerSettlement.objects.select_for_update().filter(id=settlement_id).first()
        if not settlement:
            return JsonResponse({'status': 'error', 'message': 'Settlement not found'}, status=404)
        
        if settlement.razorpay_payout_id:
            return JsonResponse({'status': 'error', 'message': 'Payout has already been initiated for this settlement.'}, status=400)
            
        from .razorpayx_service import initiate_payout
        success, msg = initiate_payout(settlement)
        
    if success:
        return JsonResponse({'status': 'success', 'message': msg})
    return JsonResponse({'status': 'error', 'message': msg}, status=400)


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def admin_create_settlement_ajax(request, seller_id):
    """Create a new SellerSettlement and link the specified order items."""
    from items.models import SellerProfile
    seller = get_object_or_404(SellerProfile, id=seller_id)
    
    try:
        data = json.loads(request.body)
        order_item_ids = data.get('order_item_ids', [])
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON payload'}, status=400)
        
    if not order_item_ids:
        return JsonResponse({'status': 'error', 'message': 'No order items selected'}, status=400)
        
    from orders.models import OrderItem, SellerSettlement
    from django.utils import timezone
    from datetime import timedelta
    
    safety_date = timezone.now() - timedelta(days=10)
    
    with transaction.atomic():
        items = OrderItem.objects.select_for_update().filter(
            id__in=order_item_ids,
            seller=seller,
            order__status='delivered',
            order__delivered_at__lte=safety_date,
            is_returned=False
        ).exclude(
            settlements__isnull=False
        ).exclude(
            return_requests__status__in=['requested', 'approved', 'completed']
        )
        
        if not items.exists():
            return JsonResponse({'status': 'error', 'message': 'None of the selected order items are eligible for settlement.'}, status=400)
            
        settlement = SellerSettlement.objects.create(
            seller=seller,
            status='pending'
        )
        settlement.order_items.add(*items)
        
    return JsonResponse({
        'status': 'success',
        'message': f'Settlement {settlement.settlement_id} created successfully with {items.count()} items!',
        'settlement_id': settlement.id
    })


@csrf_exempt
def razorpayx_webhook(request):
    """Handle RazorpayX Payout webhook events."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        event = json.loads(request.body)
        event_type = event.get('event')
        payload = event.get('payload', {})
        payout = payload.get('payout', {}).get('entity', {})
        
        payout_id = payout.get('id')
        reference_id = payout.get('reference_id')
        
        if event_type and payout_id:
            from orders.models import SellerSettlement
            settlement = SellerSettlement.objects.filter(razorpay_payout_id=payout_id).first()
            if not settlement and reference_id:
                settlement = SellerSettlement.objects.filter(settlement_id=reference_id).first()
                
            if settlement:
                if event_type == 'payout.processed':
                    settlement.status = 'processed'
                    settlement.payment_reference = payout_id
                    settlement.save(update_fields=['status', 'payment_reference', 'updated_at'])
                    settlement.send_notification_email()
                    logger.info(f"Payout {payout_id} processed for settlement {settlement.settlement_id}")
                elif event_type in ('payout.failed', 'payout.reversed'):
                    settlement.status = 'failed'
                    settlement.payment_reference = payout_id
                    settlement.save(update_fields=['status', 'payment_reference', 'updated_at'])
                    logger.error(f"Payout {payout_id} failed/reversed: {payout.get('failure_reason', 'Unknown reason')}")
                    
        return JsonResponse({'status': 'ok'}, status=200)
    except Exception as e:
        logger.exception(f"Error processing RazorpayX webhook: {e}")
        return JsonResponse({'error': 'Internal error'}, status=500)


@admin_only
def admin_toggle_jobs_ajax(request):
    """Admin: Toggle background jobs switch"""
    if not request.user.is_superuser and request.user.role != 'admin':
        return JsonResponse({'error': '🔐 Permission denied. Only superadmins can toggle background jobs.'}, status=403)
    from common.models import SiteSettings
    settings = SiteSettings.get_singleton()
    settings.enable_background_jobs = not settings.enable_background_jobs
    settings.save(update_fields=['enable_background_jobs'])
    return JsonResponse({
        'status': 'success',
        'enable_background_jobs': settings.enable_background_jobs
    })


@require_POST
@login_required
def authorized_cancel_order(request, order_id):
    """
    Unified cancellation endpoint for Admin, Staff, and Sellers.
    - Admin/Staff: Can cancel any active items/orders at any status.
    - Sellers: Can cancel only their own items, only when status is pending, confirmed, or processing.
    - Triggers restocking, live refund (Razorpay/Wallet), and Shiprocket shipment cancellation.
    """
    from accounts.models import Wallet
    from delivery.delivery_services import ShiprocketService
    from orders.models import SystemActivityLog
    
    order = get_object_or_404(Order, unique_order_id=order_id)
    
    # 1. Permission check: must be admin/staff or seller
    user = request.user
    is_admin_or_staff = user.is_superuser or user.is_staff or (hasattr(user, 'role') and user.role == 'admin')
    is_seller = hasattr(user, 'role') and user.role == 'seller' and hasattr(user, 'seller_profile')
    
    if not (is_admin_or_staff or is_seller):
        return JsonResponse({'status': 'error', 'message': 'Permission denied. Only admins, staff, or sellers can perform this action.'}, status=403)
        
    try:
        data = json.loads(request.body)
    except Exception:
        data = {}
        
    item_ids = data.get('item_ids', [])
    reason = data.get('reason', 'other')
    remarks = data.get('remarks', '')
    
    active_states = ['pending', 'confirmed', 'processing', 'shipped', 'out_for_delivery']
    
    with transaction.atomic():
        # lock the order for update
        order = Order.objects.select_for_update().get(pk=order.pk)
        
        # 2. Identify and validate items to cancel
        if not item_ids:
            if is_admin_or_staff:
                items_to_cancel = order.items.filter(status__in=active_states)
            else:
                seller = user.seller_profile
                items_to_cancel = order.items.filter(seller=seller, status__in=['pending', 'confirmed', 'processing'])
        else:
            items_to_cancel = order.items.filter(id__in=item_ids)
            if items_to_cancel.count() != len(item_ids):
                return JsonResponse({'status': 'error', 'message': 'Some requested items do not belong to this order.'}, status=400)
                
        if not items_to_cancel.exists():
            return JsonResponse({'status': 'error', 'message': 'No active/cancellable items found to cancel.'}, status=400)
            
        # 3. Role-based constraints validation
        for item in items_to_cancel:
            if is_seller:
                if item.seller != user.seller_profile:
                    return JsonResponse({'status': 'error', 'message': f"You are not authorized to cancel item '{item.product.name}'."}, status=403)
                if item.status not in ['pending', 'confirmed', 'processing']:
                    return JsonResponse({'status': 'error', 'message': f"Cannot cancel item '{item.product.name}' as it is already '{item.get_status_display()}'."}, status=400)
            else:
                if item.status not in active_states:
                    return JsonResponse({'status': 'error', 'message': f"Item '{item.product.name}' is already '{item.get_status_display()}' and cannot be cancelled."}, status=400)
                    
        # 4. Restock, update item status, and calculate refund amount
        refund_amount = Decimal('0.00')
        shiprocket_order_ids = []
        
        for item in items_to_cancel:
            # Restock if not already returned/restocked
            if not item.is_returned:
                qty = item.quantity
                product = item.product
                variant = item.variant
                if variant:
                    variant.stock = (variant.stock or 0) + qty
                    variant.save(update_fields=['stock', 'updated_at'])
                    product.stock = product.variants.filter(is_active=True).aggregate(
                        total=models.Sum('stock')
                    )['total'] or 0
                    product.save(update_fields=['stock', 'updated_at'])
                else:
                    product.stock = (product.stock or 0) + qty
                    product.save(update_fields=['stock', 'updated_at'])
                
                item.is_returned = True
                item.returned_quantity = qty
                
            item.status = 'cancelled'
            item.save(update_fields=['status', 'is_returned', 'returned_quantity', 'updated_at'])
            
            refund_amount += item.total
            
            if item.shiprocket_order_id:
                shiprocket_order_ids.append(item.shiprocket_order_id)
                
        # 5. Process refund to source for prepaid orders
        refund_note = "No refund required (COD/unpaid)."
        payment_method = order.payment_method.lower()
        
        if order.payment_status == 'paid' and refund_amount > 0:
            if payment_method == 'razorpay' and order.razorpay_payment_id:
                client = get_razorpay_client()
                if client:
                    try:
                        razorpay_refund = client.refund.create({
                            'payment_id': order.razorpay_payment_id,
                            'amount': int(refund_amount * 100),
                            'notes': {
                                'order_id': order.unique_order_id,
                                'reason': f'Cancelled by {"Admin" if is_admin_or_staff else "Seller"}: {reason}',
                                'initiated_by': user.phone or user.email or 'system'
                            }
                        })
                        order.razorpay_refund_id = razorpay_refund.get('id')
                        order.refund_amount = (order.refund_amount or Decimal('0.00')) + refund_amount
                        order.refund_at = timezone.now()
                        refund_note = f"Refunded Rs. {refund_amount} to original source (Razorpay ID: {razorpay_refund.get('id')})"
                    except Exception as e:
                        logger.error(f"Razorpay refund failed during cancellation for order {order.unique_order_id}: {e}", exc_info=True)
                        order.payment_status = 'failed'
                        refund_note = f"Razorpay refund of Rs. {refund_amount} failed; manual refund required"
                else:
                    logger.error(f"Razorpay client not configured during cancellation for order {order.unique_order_id}")
                    order.payment_status = 'failed'
                    refund_note = f"Razorpay client not configured; manual refund of Rs. {refund_amount} required"
            elif payment_method == 'wallet':
                try:
                    wallet, created = Wallet.objects.get_or_create(user=order.user)
                    wallet.balance += refund_amount
                    wallet.save()
                    order.refund_amount = (order.refund_amount or Decimal('0.00')) + refund_amount
                    order.refund_at = timezone.now()
                    refund_note = f"Refunded Rs. {refund_amount} to StallCart Wallet."
                except Exception as e:
                    logger.error(f"Wallet refund failed during cancellation for order {order.unique_order_id}: {e}", exc_info=True)
                    refund_note = f"Wallet refund of Rs. {refund_amount} failed; manual refund required"
            elif payment_method == 'cod':
                refund_note = f"COD refund: pending manual refund of Rs. {refund_amount}"
            else:
                refund_note = f"Unsupported payment method; manual refund of Rs. {refund_amount} required"
                
        # Check if all items in the order are now cancelled / returned / refunded
        total_items = order.items.count()
        cancelled_or_refunded_items = order.items.filter(
            status__in=['cancelled', 'returned', 'returned_to_source', 'refund_initiated', 'refunded', 'courier_failed_pickup', 'seller_unresponsive']
        ).count()
        
        if total_items > 0 and total_items == cancelled_or_refunded_items:
            if order.payment_status == 'paid' and refund_amount > 0 and 'failed' not in refund_note:
                order.payment_status = 'refunded'
                
        order.save(update_fields=['payment_status', 'refund_amount', 'refund_at', 'razorpay_refund_id', 'updated_at'])
        
        # 6. Update overall order status
        old_status = order.status
        order.update_overall_status()
        
        if order.status == 'cancelled':
            order.cancelled_at = timezone.now()
            order.cancellation_reason = reason
            order.cancellation_remarks = remarks
            order.save(update_fields=['cancelled_at', 'cancellation_reason', 'cancellation_remarks', 'updated_at'])
            
        # 7. Cancel Shiprocket orders
        shiprocket_note = "No Shiprocket shipments required to cancel."
        if shiprocket_order_ids:
            try:
                srv = ShiprocketService()
                res = srv.cancel_shipment(shiprocket_order_ids)
                if res.get('success'):
                    shiprocket_note = f"Cancelled Shiprocket orders {', '.join(shiprocket_order_ids)} successfully."
                else:
                    err_msg = res.get('error', 'Unknown error')
                    shiprocket_note = f"⚠️ Failed to cancel Shiprocket orders {', '.join(shiprocket_order_ids)}: {err_msg}"
            except Exception as e:
                logger.error(f"Error calling Shiprocket cancel_shipment: {e}", exc_info=True)
                shiprocket_note = f"Error during auto-cancelling Shiprocket orders: {e}"
                
        # 8. Log the status change
        cancelled_item_names = [f"{item.product.name} (x{item.quantity})" for item in items_to_cancel]
        log_remarks = f"Cancelled item(s): {', '.join(cancelled_item_names)}. Reason: {reason}. Remarks: {remarks}."
        if refund_amount > 0:
            log_remarks += f" Refund: {refund_note}."
        log_remarks += f" Shiprocket: {shiprocket_note}."
        
        OrderStatusLog.objects.create(
            order=order,
            old_status=old_status,
            new_status=order.status,
            changed_by=user,
            remarks=log_remarks
        )
        
        SystemActivityLog.log(
            event_type='order_status',
            description=f"Items cancelled for order {order.unique_order_id} by {request.user.role if hasattr(request.user, 'role') else 'admin'}.",
            order=order,
            user=user,
            status='success',
            metadata={
                'cancelled_items': [item.id for item in items_to_cancel],
                'refund_amount': float(refund_amount),
                'shiprocket_order_ids': shiprocket_order_ids,
                'refund_note': refund_note,
                'shiprocket_note': shiprocket_note
            }
        )
        
    return JsonResponse({
        'status': 'success',
        'message': f"Successfully cancelled {items_to_cancel.count()} item(s).",
        'refund_note': refund_note,
        'shiprocket_note': shiprocket_note
    })