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

@login_required
def my_orders(request):
    """Customer: View all orders with tracking"""
    orders = Order.objects.filter(
        user=request.user
    ).select_related('delivery_assignment__delivery_partner').prefetch_related('items__product').order_by('-created_at')
    
    context = {'orders': orders}
    return render(request, 'orders/my_orders.html', context)

@login_required
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

@login_required
def download_invoice(request, order_id):
    """Generate & download PDF invoice"""
    order = get_object_or_404(Order, unique_order_id=order_id, user=request.user)
    html_string = render_to_string('orders/invoice.html', {'order': order})
    
    try:
        from weasyprint import HTML
        pdf = HTML(string=html_string).write_pdf()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice-{order.unique_order_id}.pdf"'
        return response
    except ImportError:
        messages.error(request, "PDF generation not available. Please contact support.")
        return redirect('orders:order_detail', order_id=order_id)

# ==================== SELLER VIEWS ====================

@login_required
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
    
    context = {'order_items': order_items, 'seller': seller, 'filters': request.GET.dict()}
    return render(request, 'orders/seller_orders.html', context)

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

@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_orders(request):
    """Admin: View all orders system-wide"""
    orders = Order.objects.select_related('user', 'delivery_assignment__delivery_partner').prefetch_related('items__product').order_by('-created_at')
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)
    context = {'orders': orders, 'filters': request.GET.dict()}
    return render(request, 'orders/admin_orders.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_order_detail(request, order_id):
    """Admin: Full order detail view"""
    order = get_object_or_404(Order, unique_order_id=order_id)
    context = {'order': order}
    return render(request, 'orders/admin_order_detail.html', context)

@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
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