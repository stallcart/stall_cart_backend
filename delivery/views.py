from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json
from .models import DeliveryPartner, DeliveryTask
from orders.models import Order, OrderStatusLog
from django.db import transaction
from django.utils import timezone
import logging
from common.notification_service import (
    notify_order_out_for_delivery,
    notify_order_delivered
)

logger = logging.getLogger(__name__)

def delivery_portal(request):
    """Main delivery partner page - matches delivery.html"""
    return render(request, 'delivery/portal.html')

@require_POST
def register_partner(request):
    """API: Register delivery partner (matches Firebase addDoc)"""
    try:
        data = json.loads(request.body)
        partner, created = DeliveryPartner.objects.update_or_create(
            phone=data['phone'],
            defaults={
                'full_name': data['name'],
                'current_address': data['address'],
                'aadhar_id': data['idCard'],
                'status': 'Pending' if created else 'Active'
            }
        )
        return JsonResponse({'status': 'success', 'phone': partner.phone})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def get_tasks(request):
    """API: Get delivery tasks (matches Firebase onSnapshot)"""
    phone = request.GET.get('phone')
    if not phone:
        return JsonResponse({'tasks': []})
    
    try:
        partner = DeliveryPartner.objects.get(phone=phone)
        tasks = DeliveryTask.objects.filter(
            partner=partner
        ).select_related('order').prefetch_related('order__items__product').order_by('-order__created_at')
        
        task_list = []
        for t in tasks:
            order = t.order
            first_item = order.items.first()
            task_list.append({
                'id': str(t.id)[:8].upper(),
                'product_title': first_item.product.name if first_item else 'Product',
                'status': t.status,
                'user_name': order.user.full_name if order.user else 'Guest',
                'user_phone': order.address.get('phone', ''),
                'address': order.address,
                'delivery_otp': t.delivery_otp,
                'order_id': str(order.id)[:8].upper()
            })
        return JsonResponse({'tasks': task_list})
    except DeliveryPartner.DoesNotExist:
        return JsonResponse({'tasks': [], 'message': 'Partner not registered'})

@require_POST
def update_task_status(request, task_id):
    """API: Update delivery task status (matches Firebase updateDoc)"""
    try:
        with transaction.atomic():
            task = DeliveryTask.objects.select_for_update().get(id=task_id)
            order = task.order
            data = json.loads(request.body)
            action = data.get('action')
            
            old_status = order.status
            new_status = None
            
            if action == 'out_for_delivery':
                task.status = 'Out for Delivery'
                new_status = 'out_for_delivery'
            elif action == 'deliver':
                if data.get('otp') != task.delivery_otp:
                    return JsonResponse({'error': 'Invalid OTP'}, status=400)
                task.status = 'Delivered'
                task.delivered_at = timezone.now()
                new_status = 'delivered'
                if task.partner:
                    task.partner.delivered_count += 1
                    task.partner.save()
            
            task.save()
            
            if new_status and new_status != old_status:
                order.status = new_status
                order.status_updated_at = timezone.now()
                if new_status == 'delivered':
                    order.delivered_at = timezone.now()
                order.save()
                
                changed_by = request.user if request.user.is_authenticated else (task.partner.user if task.partner else None)
                OrderStatusLog.objects.create(
                    order=order,
                    old_status=old_status,
                    new_status=new_status,
                    changed_by=changed_by,
                    remarks=f'Updated to {new_status} via delivery portal'
                )

        if new_status and new_status != old_status:
            try:
                if new_status == 'out_for_delivery':
                    notify_order_out_for_delivery(order)
                elif new_status == 'delivered':
                    notify_order_delivered(order)
            except Exception as e:
                logger.error(f"[FCM] Delivery portal update notification failed for order {order.id} (status: {new_status}): {e}")

        return JsonResponse({'status': task.status, 'message': 'Updated successfully'})
    except DeliveryTask.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)
    except Exception as e:
        logger.error(f"Error in update_task_status: {e}")
        return JsonResponse({'error': str(e)}, status=500)