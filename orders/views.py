# orders/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.db import transaction
from django.utils import timezone
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
import razorpay
import json
import logging
from decimal import Decimal
from common.decorators import *
from .models import Order, OrderItem, ReturnRequest, OrderStatusLog, OrderReturnImage
from items.models import Product, SellerProfile
from delivery.models import DeliveryPartner
from django.conf import settings
logger = logging.getLogger(__name__)
User = get_user_model()

# ==================== RAZORPAY CLIENT ====================
razorpay_client = razorpay.Client(auth=(
    settings.RAZORPAY_KEY_ID,
    settings.RAZORPAY_KEY_SECRET
))

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

@customer_only
def order_detail(request, order_id):
    """Customer: View single order with tracking timeline"""
    order = get_object_or_404(Order, unique_order_id=order_id, user=request.user)
    
    timeline = []
    status_logs = order.status_logs.select_related('changed_by').order_by('timestamp')
    status_labels = {
        'pending': 'Order Placed', 'confirmed': 'Order Confirmed',
        'processing': 'Processing', 'shipped': 'Shipped',
        'out_for_delivery': 'Out for Delivery', 'delivered': 'Delivered',
    }
    
    for log in status_logs:
        timeline.append({
            'status': log.new_status,
            'label': status_labels.get(log.new_status, log.new_status),
            'timestamp': log.timestamp,
            'remarks': log.remarks,
        })
    
    context = {
        'order': order,
        'timeline': timeline,
        'delivery': getattr(order, 'delivery_assignment', None),
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
        
        OrderStatusLog.objects.create(
            order=order, old_status=old_status, new_status='cancelled',
            changed_by=request.user, remarks=f'Cancelled by customer: {remarks}'
        )
        
        for item in order.items.all():
            item.product.stock += item.quantity
            item.product.save()
    
    if order.payment_status == 'paid' and order.payment_method == 'razorpay':
        try:
            razorpay_client.refund.create({
                'payment_id': order.razorpay_payment_id,
                'amount': int(order.total_amount * 100),
                'notes': {'order_id': order.unique_order_id}
            })
            order.payment_status = 'refunded'
            order.save()
        except Exception as e:
            logger.error(f"Refund failed for {order.unique_order_id}: {e}")
    
    messages.success(request, f"Order {order.unique_order_id} cancelled successfully")
    return JsonResponse({'status': 'success', 'redirect': '/orders/'})

@login_required
def request_return(request, order_item_id):
    """Customer: Request return for an item"""
    order_item = get_object_or_404(OrderItem, id=order_item_id, order__user=request.user)
    
    if not order_item.order.is_returnable:
        messages.error(request, "Return window has closed for this order")
        return redirect('orders:order_detail', order_id=order_item.order.unique_order_id)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        return_req = ReturnRequest.objects.create(
            order_item=order_item, user=request.user,
            quantity=data.get('quantity', 1), reason=data.get('reason'),
            remarks=data.get('remarks', ''),
            refund_amount=order_item.price * data.get('quantity', 1),
        )
        messages.success(request, "Return request submitted. We'll contact you within 24 hours.")
        return JsonResponse({'status': 'success', 'return_id': return_req.id})
    
    context = {'order_item': order_item, 'reasons': Order.RETURN_REASONS}
    return render(request, 'orders/return_form.html', context)

@login_required
def return_detail(request, return_id):
    """Customer: View return request status"""
    return_req = get_object_or_404(ReturnRequest, id=return_id, user=request.user)
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
@login_required
def download_invoice(request, order_id):
    """
    Generate & download PDF invoice using xhtml2pdf (macOS compatible).
    Falls back to HTML download if PDF generation fails.
    """
    # 1. Fetch order with related data (prevent N+1)
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product', 'items__seller'),
        unique_order_id=order_id,
        user=request.user
    )
    
    # 2. Render template WITH request for context processors
    try:
        html_string = render_to_string(
            'orders/invoice.html',
            {'order': order},
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
    html_string = render_to_string('orders/invoice.html', {'order': order}, request=request)
    
    response = HttpResponse(html_string, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="invoice-{order.unique_order_id}.html"'
    messages.info(
        request, 
        "Downloaded as HTML. Open the file in your browser and use 'Print → Save as PDF'."
    )
    return response


@login_required
def preview_invoice(request, order_id):
    """
    Preview invoice in browser (HTML) for client-side PDF export.
    Add ?print=1 to URL to auto-open print dialog.
    """
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        unique_order_id=order_id,
        user=request.user
    )
    
    html_string = render_to_string(
        'orders/invoice.html',
        {'order': order},
        request=request
    )
    
    return HttpResponse(html_string)


@login_required
def debug_invoice(request, order_id):
    """
    Debug endpoint to test invoice generation.
    Access: /orders/order/ORD-XXXXXX/invoice/debug/
    """
    order = get_object_or_404(Order, unique_order_id=order_id, user=request.user)
    
    # Test 1: Template render
    try:
        html = render_to_string('orders/invoice.html', {'order': order}, request=request)
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
    if not (request.user.role == 'seller' and hasattr(request.user, 'seller_profile')):
        messages.error(request, "Only sellers can view this page.")
        return redirect('shop:home')
    
    seller = request.user.seller_profile
    order_items = OrderItem.objects.filter(
        product__seller=seller
    ).select_related('order', 'product', 'order__user').prefetch_related(
        'order__items__product'
    ).order_by('-order__created_at')
    
    status_filter = request.GET.get('status')
    if status_filter:
        order_items = order_items.filter(order__status=status_filter)
    pending_count = order_items.filter(order__status='pending').count()
    delivered_count = order_items.filter(order__status='delivered').count()

    context = {'order_items': order_items, 'seller': seller, 'filters': request.GET.dict(),
            'pending_count': pending_count,
            'delivered_count':delivered_count,

            }
    return render(request, 'orders/seller_order.html', context)

@login_required
def seller_order_detail(request, order_id):
    """Seller: View details of a specific order containing their products"""
    if not (request.user.role == 'seller' and hasattr(request.user, 'seller_profile')):
        messages.error(request, "Only sellers can view this page.")
        return redirect('shop:home')
    
    seller = request.user.seller_profile
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        unique_order_id=order_id, items__product__seller=seller
    )
    
    seller_items = order.items.filter(product__seller=seller).select_related('product')
    
    timeline = []
    status_logs = order.status_logs.select_related('changed_by').order_by('timestamp')
    status_labels = {
        'pending': 'Order Placed', 'confirmed': 'Order Confirmed',
        'processing': 'Processing', 'shipped': 'Shipped',
        'out_for_delivery': 'Out for Delivery', 'delivered': 'Delivered',
    }
    for log in status_logs:
        timeline.append({
            'status': log.new_status,
            'label': status_labels.get(log.new_status, log.new_status),
            'timestamp': log.timestamp, 'remarks': log.remarks,
        })
    
    context = {
        'order': order, 'seller_items': seller_items, 'timeline': timeline,
        'delivery': getattr(order, 'delivery_assignment', None),
    }
    return render(request, 'orders/seller_order_detail.html', context)

@require_POST
@login_required
def seller_update_status(request, order_id):
    """Seller: Update order status (e.g., mark as shipped)"""
    if not (request.user.role == 'seller' and hasattr(request.user, 'seller_profile')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    seller = request.user.seller_profile
    order = get_object_or_404(Order, unique_order_id=order_id, items__product__seller=seller)
    
    if order.status not in ['pending', 'confirmed', 'processing']:
        return JsonResponse({'error': 'Order cannot be updated at this stage'}, status=400)
    
    data = json.loads(request.body)
    new_status = data.get('status')
    
    if new_status not in ['processing', 'shipped']:
        return JsonResponse({'error': 'Invalid status transition'}, status=400)
    
    with transaction.atomic():
        old_status = order.status
        order.status = new_status
        order.status_updated_at = timezone.now()
        if new_status == 'shipped':
            order.shipped_at = timezone.now()
        order.save()
        
        OrderStatusLog.objects.create(
            order=order, old_status=old_status, new_status=new_status,
            changed_by=request.user, remarks='Updated by seller'
        )
    
    return JsonResponse({'status': 'success', 'new_status': order.get_status_display()})

@require_POST
@login_required
def seller_add_tracking(request, order_id):
    """Seller: Add courier tracking number"""
    if not (request.user.role == 'seller' and hasattr(request.user, 'seller_profile')):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    order = get_object_or_404(Order, unique_order_id=order_id, items__product__seller=request.user.seller_profile)
    data = json.loads(request.body)
    
    order.tracking_number = data.get('tracking_number')
    order.courier_name = data.get('courier_name', 'Shiprocket')
    order.save()
    
    return JsonResponse({'status': 'success', 'message': 'Tracking added'})

# ==================== ADMIN VIEWS ====================

# @login_required
# @user_passes_test(lambda u: u.is_superuser)
@admin_only
def admin_orders(request):
    """Admin: View all orders system-wide"""
    orders = Order.objects.select_related('user', 'delivery_assignment__delivery_partner').prefetch_related('items__product').order_by('-created_at')
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)
    context = {'orders': orders, 'filters': request.GET.dict()}
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
    
    if new_status not in dict(Order.STATUS_CHOICES):
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    with transaction.atomic():
        old_status = order.status
        order.status = new_status
        order.status_updated_at = timezone.now()
        if new_status == 'delivered':
            order.delivered_at = timezone.now()
        order.save()
        
        OrderStatusLog.objects.create(
            order=order, old_status=old_status, new_status=new_status,
            changed_by=request.user, remarks='Updated by admin'
        )
    
    return JsonResponse({'status': 'success'})

# ==================== WEBHOOKS ====================

@require_POST
def razorpay_webhook(request):
    """Handle Razorpay payment events"""
    signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
    body = request.body
    
    try:
        razorpay_client.utility.verify_webhook_signature(
            body.decode('utf-8'), signature, settings.RAZORPAY_WEBHOOK_SECRET
        )
        
        event = json.loads(body)
        if event.get('event') == 'payment.captured':
            payment = event['payload']['payment']['entity']
            order = Order.objects.filter(razorpay_payment_id=payment['id']).first()
            
            if order:
                with transaction.atomic():
                    order.payment_status = 'paid'
                    if order.status == 'pending':
                        order.status = 'confirmed'
                        order.status_updated_at = timezone.now()
                        OrderStatusLog.objects.create(
                            order=order, old_status='pending', new_status='confirmed',
                            remarks='Payment captured via Razorpay'
                        )
                    order.save()
                    
                    for item in order.items.all():
                        item.product.stock -= item.quantity
                        item.product.save()
        
        return HttpResponse(status=200)
    except Exception as e:
        logger.error(f"Razorpay webhook error: {e}")
        return HttpResponse(status=400)

@require_POST
def shiprocket_webhook(request):
    """Handle Shiprocket delivery tracking updates"""
    try:
        data = json.loads(request.body)
        # Example: Update delivery assignment status/location
        # awb = data.get('awb')
        # delivery = DeliveryAssignment.objects.filter(tracking_number=awb).first()
        # if delivery:
        #     delivery.current_location = data.get('current_location')
        #     delivery.save()
        return HttpResponse(status=200)
    except Exception as e:
        logger.error(f"Shiprocket webhook error: {e}")
        return HttpResponse(status=400)

# ==================== PUBLIC/UTILITY ====================

@require_GET
def track_order_public(request, order_id):
    """Public order tracking (like Flipkart) - no login required"""
    order = get_object_or_404(Order, unique_order_id=order_id)
    
    if order.status not in ['shipped', 'out_for_delivery', 'delivered']:
        if order.guest_email and order.guest_email != request.GET.get('email'):
            return render(request, 'orders/tracking_not_found.html', {'order_id': order_id})
    
    timeline = OrderStatusLog.objects.filter(order=order).order_by('timestamp')
    context = {'order': order, 'timeline': timeline}
    return render(request, 'orders/track_public.html', context)

def order_success(request, order_id):
    """Order success page after payment"""
    order = get_object_or_404(Order, unique_order_id=order_id)
    context = {'order': order}
    return render(request, 'orders/order_success.html', context)

def order_failed(request):
    """Order failed/cancelled page"""
    return render(request, 'orders/order_failed.html')