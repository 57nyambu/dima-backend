from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from apps.business.models import BusinessReview
from apps.notifications.sms import SMSService
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Order)
def update_business_review_order_counts(sender, instance, created, **kwargs):
    if not created and hasattr(instance, '_previous_status'):
        prev = instance._previous_status
        curr = instance.status
        if prev != curr:
            review, _ = BusinessReview.objects.get_or_create(
                user=instance.user,
                product=instance.business,
                defaults={'rating': 1}
            )
            if curr == 'delivered':
                review.orders_complete += 1
            elif curr == 'pending':
                review.orders_pending += 1
            elif curr == 'cancelled':
                review.canceled_orders += 1
            review.save()

@receiver(post_save, sender=Order)
def send_order_status_sms(sender, instance, created, **kwargs):
    """
    Send SMS notification when order status changes
    """
    try:
        # Get customer phone number
        phone_number = instance.customer_phone
        
        if not phone_number:
            logger.info(f"No phone number for order {instance.order_number}, skipping SMS")
            return
        
        # Send SMS for new orders or status changes
        if created:
            order_ref = instance.order_number or f"#{instance.id}"
            message = (
                f"Order confirmed! Your order {order_ref} "
                f"from {instance.business.name} for KES {instance.total:.2f} "
                f"has been received. Thank you for shopping with us!"
            )
        elif hasattr(instance, '_previous_status') and instance._previous_status != instance.status:
            status = instance.status
            order_ref = instance.order_number or f"#{instance.id}"
            
            if status == 'processing':
                message = f"Your order {order_ref} is now being processed."
            elif status == 'shipped':
                tracking = f" Tracking: {instance.tracking_number}" if instance.tracking_number else ""
                message = f"Good news! Your order {order_ref} has been shipped.{tracking}"
            elif status == 'delivered':
                message = f"Your order {order_ref} has been delivered. Enjoy your purchase!"
            elif status == 'cancelled':
                message = f"Your order {order_ref} has been cancelled. Contact us if you have questions."
            else:
                message = f"Order {order_ref} status updated to: {status}"
        else:
            return
        
        # Send SMS
        sms_service = SMSService()
        result = sms_service.send_sms(phone_number, message)
        
        if result['success']:
            logger.info(f"SMS sent successfully for order {instance.order_number}")
        else:
            logger.error(f"SMS failed for order {instance.order_number}: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error sending order SMS: {str(e)}")