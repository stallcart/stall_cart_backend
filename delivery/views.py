from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json
from .models import DeliveryPartner, DeliveryTask
from orders.models import Order

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
        task = DeliveryTask.objects.get(id=task_id)
        data = json.loads(request.body)
        action = data.get('action')
        
        if action == 'out_for_delivery':
            task.status = 'Out for Delivery'
        elif action == 'deliver':
            if data.get('otp') != task.delivery_otp:
                return JsonResponse({'error': 'Invalid OTP'}, status=400)
            task.status = 'Delivered'
            from django.utils import timezone
            task.delivered_at = timezone.now()
            if task.partner:
                task.partner.delivered_count += 1
                task.partner.save()
        
        task.save()
        return JsonResponse({'status': task.status, 'message': 'Updated successfully'})
    except DeliveryTask.DoesNotExist:
        return JsonResponse({'error': 'Task not found'}, status=404)