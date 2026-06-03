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
    if order.tracking_number and order.status not in ('delivered', 'cancelled', 'returned'):
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
                    'AWB Assigned': 'confirmed',
                    'Manifested': 'processing',
                    'In Transit': 'shipped',
                    'Shipped': 'shipped',
                    'Out for Delivery': 'out_for_delivery',
                    'Delivered': 'delivered',
                    'RTO': 'returned_to_source',
                    'Returned to Source': 'returned_to_source',
                    'Cancelled': 'cancelled'
                }
                new_local_status = status_map.get(sr_status)
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
            
    # If terminal status (or fallback case), but tracking number exists, try to get live cached tracking anyway
    elif order.tracking_number:
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
    
    timeline = []
    status_logs = order.status_logs.select_related('changed_by').order_by('timestamp')
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
    # 1. Fetch order with related data based on user role (prevent N+1)
    role = getattr(request.user, 'role', 'customer')
    if role == 'seller':
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product', 'items__seller'),
            unique_order_id=order_id,
            items__seller__user=request.user
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
    role = getattr(request.user, 'role', 'customer')
    if role == 'seller':
        order = get_object_or_404(
            Order.objects.prefetch_related('items__product'),
            unique_order_id=order_id,
            items__seller__user=request.user
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
    role = getattr(request.user, 'role', 'customer')
    if role == 'seller':
        order = get_object_or_404(Order, unique_order_id=order_id, items__seller__user=request.user)
    elif request.user.is_staff or request.user.is_superuser:
        order = get_object_or_404(Order, unique_order_id=order_id)
    else:
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
        order_items = order_items.filter(order__status=status_filter)
        
    pending_count = order_items.filter(order__status='pending').count()
    delivered_count = order_items.filter(order__status='delivered').count()
    pending_returns = ReturnRequest.objects.filter(
        order_item__product__seller=seller,
        status='requested'
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
    if not (request.user.role == 'seller' and hasattr(request.user, 'seller_profile')):
        messages.error(request, "Only sellers can view this page.")
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

    timeline = []
    status_logs = order.status_logs.select_related('changed_by').order_by('timestamp')
    status_labels = {
        'pending': 'Order Placed', 'confirmed': 'Order Confirmed',
        'processing': 'Processing', 'shipped': 'Shipped',
        'out_for_delivery': 'Out for Delivery', 'delivered': 'Delivered',
        'returned_to_source': 'Returned to Source', 'returned': 'Returned',
    }
    for log in status_logs:
        timeline.append({
            'status': log.new_status,
            'label': status_labels.get(log.new_status, log.new_status),
            'timestamp': log.timestamp, 'remarks': log.remarks,
        })
    
    pending_returns = ReturnRequest.objects.filter(
        order_item__order=order,
        order_item__product__seller=seller,
        status='requested'
    ).select_related('order_item__product', 'order_item__order', 'order_item__variant')
    
    context = {
        'order': order, 'seller_items': seller_items, 'timeline': timeline,
        'delivery': getattr(order, 'delivery_task', None),
        'seller_items_total': seller_items_total,
        'seller_commission_total': seller_commission_total,
        'seller_earnings_total': seller_earnings_total,
        'pending_returns': pending_returns,
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
        order.status = new_status
        order.status_updated_at = timezone.now()
        if new_status == 'shipped':
            order.shipped_at = timezone.now()
        elif new_status == 'delivered':
            order.delivered_at = timezone.now()
        order.save()
        
        OrderStatusLog.objects.create(
            order=order, old_status=old_status, new_status=new_status,
            changed_by=request.user, remarks='Updated by seller/admin'
        )
    
    if new_status == 'shipped':
        try:
            notify_order_shipped(order, order.tracking_number)
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
        if not order.items.filter(product__seller=seller).exists():
            return JsonResponse({'error': 'Unauthorized'}, status=403)
            
    data = json.loads(request.body)
    order.tracking_number = data.get('tracking_number')
    order.courier_name = data.get('courier_name', 'Shiprocket')
    order.save()
    
    return JsonResponse({'status': 'success', 'message': 'Tracking updated'})

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
        status='requested'
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
            
        # Find Order
        order = None
        if awb:
            order = Order.objects.filter(tracking_number=awb).first()
        if not order and order_id:
            order = Order.objects.filter(unique_order_id=order_id).first()
            
        if not order:
            logger.warning(f"Shiprocket webhook: Order not found for AWB={awb}, OrderID={order_id}")
            return HttpResponse("Order not found", status=404)
            
        sr_status = sr_status.strip()
        status_map = {
            'AWB Assigned': 'confirmed',
            'Manifested': 'processing',
            'In Transit': 'shipped',
            'Shipped': 'shipped',
            'Out for Delivery': 'out_for_delivery',
            'Delivered': 'delivered',
            'RTO': 'returned_to_source',
            'Returned to Source': 'returned_to_source',
            'Cancelled': 'cancelled'
        }
        
        new_local_status = status_map.get(sr_status)
        if new_local_status and new_local_status != order.status:
            old_status = order.status
            order.status = new_local_status
            if new_local_status == 'delivered':
                order.delivered_at = timezone.now()
            elif new_local_status == 'shipped' and not order.shipped_at:
                order.shipped_at = timezone.now()
                
            order.save(update_fields=['status', 'delivered_at', 'shipped_at', 'updated_at'])
            
            # Log status change in OrderStatusLog
            OrderStatusLog.objects.create(
                order=order,
                old_status=old_status,
                new_status=new_local_status,
                remarks=f"Automatic update via Shiprocket Webhook (Status: {sr_status})"
            )
            logger.info(f"Shiprocket Webhook: Updated order {order.unique_order_id} status from {old_status} to {new_local_status}")
            
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
    
    timeline = OrderStatusLog.objects.filter(order=order).order_by('timestamp')
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
    Approve or reject a return request.
    
    POST payload:
    {
        "action": "approve" | "reject",
        "rejection_reason": "string (required if action=reject)"
    }
    
    On approve:
    - Restocks the product/variant
    - Marks order item as returned
    - Initiates Razorpay refund for ONLINE payments
    - Marks COD for manual bank transfer
    
    Returns JSON response for frontend integration.
    """
    try:
        import json
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON payload'}, status=400)
    
    action = data.get('action', '').lower()
    if action not in ['approve', 'reject']:
        return JsonResponse({'status': 'error', 'message': 'Invalid action. Use "approve" or "reject"'}, status=400)
    
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
    
    # Permission check: seller can only approve returns for their own products
    if not request.user.is_staff and not request.user.is_superuser:
        if not hasattr(request.user, 'seller_profile') or return_req.order_item.product.seller != request.user.seller_profile:
            return JsonResponse(
                {'status': 'error', 'message': 'You can only manage returns for your own products'}, 
                status=403
            )
    
    # Only pending/requested returns can be actioned
    if return_req.status != 'requested':
        return JsonResponse(
            {'status': 'error', 'message': f'Return request is already {return_req.status}'}, 
            status=400
        )
    
    order_item = return_req.order_item
    order = order_item.order
    product = order_item.product
    variant = order_item.variant
    
    # === REJECT FLOW ===
    if action == 'reject':
        rejection_reason = data.get('rejection_reason', '').strip()
        if not rejection_reason:
            return JsonResponse(
                {'status': 'error', 'message': 'Rejection reason is required'}, 
                status=400
            )
        
        return_req.status = 'rejected'
        return_req.rejection_reason = rejection_reason
        return_req.actioned_by = request.user
        return_req.actioned_at = timezone.now()
        return_req.save(update_fields=['status', 'rejection_reason', 'actioned_by', 'actioned_at', 'updated_at'])
        
        # Optional: Notify customer of rejection (implement your notification system)
        # send_return_rejected_notification(return_req, rejection_reason)
        
        logger.info(f"Return #{return_id} rejected by {request.user}: {rejection_reason}")
        return JsonResponse({
            'status': 'success',
            'message': 'Return request rejected',
            'return_id': return_req.id,
            'new_status': 'rejected'
        })
    
    # === APPROVE FLOW ===
    with transaction.atomic():
        # 1. Restock the product/variant
        qty_to_restock = return_req.quantity
        
        if variant:
            # Restock specific variant
            variant.stock = (variant.stock or 0) + qty_to_restock
            variant.save(update_fields=['stock', 'updated_at'])
            logger.info(f"Restocked {qty_to_restock} units of variant #{variant.id}")
        else:
            # Restock base product
            product.stock = (product.stock or 0) + qty_to_restock
            product.save(update_fields=['stock', 'updated_at'])
            logger.info(f"Restocked {qty_to_restock} units of product #{product.id}")
        
        # 2. Mark order item as returned
        order_item.is_returned = True
        order_item.returned_quantity = (order_item.returned_quantity or 0) + qty_to_restock
        order_item.save(update_fields=['is_returned', 'returned_quantity', 'updated_at'])
        
        # 3. Update return request
        return_req.status = 'approved'
        return_req.actioned_by = request.user
        return_req.actioned_at = timezone.now()
        return_req.refund_initiated_at = timezone.now()
        return_req.save(update_fields=[
            'status', 'actioned_by', 'actioned_at', 
            'refund_initiated_at', 'updated_at'
        ])
        
        # 4. Process refund based on payment method
        refund_result = _process_refund(order, return_req, qty_to_restock)
        
        # 5. Update order status if all items are returned
        _update_order_status_if_fully_returned(order)
    
    logger.info(f"Return #{return_id} approved by {request.user}, refund: {refund_result}")
    
    return JsonResponse({
        'status': 'success',
        'message': 'Return approved & refund initiated',
        'return_id': return_req.id,
        'new_status': 'approved',
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
    if not request.user.is_staff and not request.user.is_superuser:
        if not hasattr(request.user, 'seller_profile'):
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
        has_product = order.items.filter(product__seller=request.user.seller_profile).exists()
        if not has_product:
            return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)
            
    if order.status != 'returned_to_source':
        return JsonResponse({'status': 'error', 'message': f'Order is in {order.status} state, not returned_to_source'}, status=400)
        
    with transaction.atomic():
        # 1. Restock products/variants
        for item in order.items.all():
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
                item.save(update_fields=['is_returned', 'returned_quantity', 'updated_at'])
                
        # 2. Refund to customer
        refund_note = ""
        payment_method = order.payment_method.lower()
        if payment_method == 'wallet':
            order.payment_status = 'refunded'
            order.refund_amount = order.total_amount
            order.refund_at = timezone.now()
            refund_note = "RTO Refund: pending manual bank transfer (wallet disabled)"
        elif payment_method == 'razorpay' and order.razorpay_payment_id:
            client = get_razorpay_client()
            if client:
                try:
                    razorpay_refund = client.refund.create({
                        'payment_id': order.razorpay_payment_id,
                        'amount': int(order.total_amount * 100),
                        'notes': {'order_id': order.unique_order_id, 'reason': 'RTO'}
                    })
                    order.razorpay_refund_id = razorpay_refund.get('id')
                    order.payment_status = 'refunded'
                    order.refund_amount = order.total_amount
                    order.refund_at = timezone.now()
                    refund_note = f"refunded to original source (Razorpay ID: {razorpay_refund.get('id')})"
                except Exception as e:
                    logger.error(f"RTO Razorpay refund failed for {order.unique_order_id}: {e}")
                    order.payment_status = 'failed'
                    refund_note = "Razorpay refund failed; manual refund required"
            else:
                logger.error(f"RTO Razorpay refund failed for {order.unique_order_id}: Razorpay client not configured")
                order.payment_status = 'failed'
                refund_note = "Razorpay client not configured; manual refund required"
        elif payment_method == 'cod':
            order.payment_status = 'refunded'
            order.refund_amount = order.total_amount
            refund_note = "COD refund: pending manual bank transfer"
        else:
            order.payment_status = 'failed'
            refund_note = "Unsupported payment method; manual refund required"
        
        # 3. Update Order Status
        old_status = order.status
        order.status = 'returned'
        order.save(update_fields=['status', 'payment_status', 'refund_amount', 'refund_at', 'razorpay_refund_id', 'updated_at'])
        
        # 4. Log status change
        OrderStatusLog.objects.create(
            order=order,
            old_status=old_status,
            new_status='returned',
            changed_by=request.user,
            remarks=f'RTO delivery receipt confirmed & {refund_note}'
        )
        
    return JsonResponse({
        'status': 'success',
        'message': f'RTO receipt confirmed. Refund details: {refund_note}.',
        'new_status': 'Returned'
    })


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def admin_trigger_payout_ajax(request, settlement_id):
    """Trigger RazorpayX payout for a settlement."""
    settlement = get_object_or_404(SellerSettlement, id=settlement_id)
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
    
    items = OrderItem.objects.filter(
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
        
    with transaction.atomic():
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