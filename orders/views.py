# orders/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
import razorpay
import json
from decimal import Decimal
from .models import *
from items.models import Product
from delivery.models import DeliveryPartner, DeliveryAssignment
from django.conf import settings

# Razorpay Client (initialize once)
razorpay_client = razorpay.Client(auth=(
    settings.RAZORPAY_KEY_ID,
    settings.RAZORPAY_KEY_SECRET
))

@login_required
def my_orders(request):
    """Customer: View all orders with tracking"""
    orders = Order.objects.filter(
        user=request.user
    ).select_related('delivery_assignment__delivery_partner').prefetch_related('items__product').order_by('-created_at')
    
    context = {'orders': orders}
    return render(request, 'orders/my_orders.html', context)

@login_required
def order_detail(request, unique_order_id):
    """Customer: View single order with tracking timeline"""
    order = get_object_or_404(Order, unique_order_id=unique_order_id, user=request.user)
    
    # Build tracking timeline
    timeline = []
    status_logs = order.status_logs.select_related('changed_by').order_by('timestamp')
    
    status_labels = {
        'pending': 'Order Placed',
        'confirmed': 'Order Confirmed',
        'processing': 'Processing',
        'shipped': 'Shipped',
        'out_for_delivery': 'Out for Delivery',
        'delivered': 'Delivered',
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
def cancel_order(request, unique_order_id):
    """Customer: Cancel order (if eligible)"""
    order = get_object_or_404(Order, unique_order_id=unique_order_id, user=request.user)
    
    if not order.is_cancellable:
        return JsonResponse({'error': 'Order cannot be cancelled at this stage'}, status=400)
    
    data = json.loads(request.body)
    reason = data.get('reason', 'other')
    remarks = data.get('remarks', '')
    
    with transaction.atomic():
        # Update order status
        old_status = order.status
        order.status = 'cancelled'
        order.cancelled_at = timezone.now()
        order.cancellation_reason = reason
        order.cancellation_remarks = remarks
        order.save()
        
        # Log status change
        from orders.models import OrderStatusLog
        OrderStatusLog.objects.create(
            order=order,
            old_status=old_status,
            new_status='cancelled',
            changed_by=request.user,
            remarks=f'Cancelled by customer: {remarks}'
        )
        
        # Restore product stock
        for item in order.items.all():
            item.product.stock += item.quantity
            item.product.save()
    
    # Refund if already paid
    if order.payment_status == 'paid' and order.payment_method == 'razorpay':
        # Initiate Razorpay refund (async in production)
        try:
            refund = razorpay_client.refund.create({
                'payment_id': order.razorpay_payment_id,
                'amount': int(order.total_amount * 100),  # in paise
                'notes': {'unique_order_id': order.unique_order_id}
            })
            order.payment_status = 'refunded'
            order.save()
        except Exception as e:
            # Log error, notify admin
            print(f"Refund failed: {e}")
    
    messages.success(request, f"Order {order.unique_order_id} cancelled successfully")
    return JsonResponse({'status': 'success', 'redirect': '/orders/'})

@login_required
def request_return(request, order_item_id):
    """Customer: Request return for an item"""
    order_item = get_object_or_404(OrderItem, id=order_item_id, order__user=request.user)
    
    if not order_item.order.is_returnable:
        messages.error(request, "Return window has closed for this order")
        return redirect('orders:order_detail', unique_order_id=order_item.order.unique_order_id)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        
        return_request = ReturnRequest.objects.create(
            order_item=order_item,
            user=request.user,
            quantity=data.get('quantity', 1),
            reason=data.get('reason'),
            remarks=data.get('remarks', ''),
            refund_amount=order_item.price * data.get('quantity', 1),
        )
        
        messages.success(request, "Return request submitted. We'll contact you within 24 hours.")
        return JsonResponse({'status': 'success', 'return_id': return_request.id})
    
    # GET: Show return form
    context = {
        'order_item': order_item,
        'reasons': Order.RETURN_REASONS,
    }
    return render(request, 'orders/return_form.html', context)

# orders/views.py
@login_required
@require_POST
def submit_return(request, order_item_id):
    order_item = get_object_or_404(OrderItem, id=order_item_id, order__user=request.user)
    
    if not order_item.order.is_returnable:
        return JsonResponse({'error': 'Return window closed'}, status=400)
    
    reason = request.POST.get('reason')
    remarks = request.POST.get('remarks', '')
    images = request.FILES.getlist('images')
    
    # Create return request
    return_req = ReturnRequest.objects.create(
        order_item=order_item,
        user=request.user,
        quantity=1,
        reason=reason,
        remarks=remarks,
        refund_amount=order_item.price,
        status='requested'
    )
    
    # Save uploaded images
    for i, img in enumerate(images[:3]):  # Limit to 3 images
        OrderReturnImage.objects.create(
            return_request=return_req,
            image=img,
            is_primary=(i == 0)
        )
    
    return JsonResponse({
        'status': 'success',
        'redirect': f"/orders/{order_item.order.order_id}/"
    })

# ==================== RAZORPAY WEBHOOK ====================
@require_POST
def razorpay_webhook(request):
    """Handle Razorpay payment events"""
    signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
    body = request.body
    
    try:
        # Verify webhook signature
        razorpay_client.utility.verify_webhook_signature(
            body.decode('utf-8'),
            signature,
            settings.RAZORPAY_WEBHOOK_SECRET
        )
        
        event = json.loads(body)
        
        if event.get('event') == 'payment.captured':
            payment = event['payload']['payment']['entity']
            order = Order.objects.filter(razorpay_payment_id=payment['id']).first()
            
            if order:
                with transaction.atomic():
                    order.payment_status = 'paid'
                    order.status = 'confirmed'  # Move to next stage
                    order.save()
                    
                    # Log status change
                    from orders.models import OrderStatusLog
                    OrderStatusLog.objects.create(
                        order=order,
                        old_status='pending',
                        new_status='confirmed',
                        remarks='Payment captured via Razorpay'
                    )
                    
                    # Reduce product stock
                    for item in order.items.all():
                        item.product.stock -= item.quantity
                        item.product.save()
                
                # Send confirmation email/SMS (async task)
                # send_order_confirmation.delay(order.id)
        
        return HttpResponse(status=200)
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return HttpResponse(status=400)