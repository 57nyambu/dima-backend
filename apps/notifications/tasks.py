from celery import shared_task
from .services import NotificationService
from .models import Notification
from django.utils import timezone
from apps.business.models import Business
from django.conf import settings


@shared_task(bind=True, max_retries=3)
def send_notification_task(self, notification_id):
    """
    Async task to send a notification
    """
    try:
        notification = Notification.objects.get(id=notification_id)
        service = NotificationService()
        
        if notification.notification_type == 'sms':
            service._send_sms_notification(notification.user, notification.message)
        elif notification.notification_type == 'email':
            service._send_email_notification(
                notification.user,
                notification.subject,
                notification.message
            )
        
        notification.sent_at = timezone.now()
        notification.save()
        return True
    except Exception as e:
        self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_business_verification_notification(self, business_id, old_status, new_status):
    """
    Async task to send business verification status change notifications
    """
    try:
        business = Business.objects.get(id=business_id)
        user = business.owner
        notification_service = NotificationService()
        
        # Prepare notification content based on status change
        if new_status == 'verified':
            subject = "Business Verified Successfully"
            message = f"Congratulations! Your business {business.name} has been verified."
            sms_message = f"Your business {business.name} is now verified on {settings.SITE_NAME}!"
        elif new_status == 'rejected':
            subject = "Business Verification Rejected"
            message = f"Your business {business.name} verification was rejected. Please check for required updates."
            sms_message = f"Your business {business.name} verification was rejected. Please check your email."
        else:  # pending or other statuses
            subject = f"Business Verification Status Changed"
            message = f"Your business {business.name} status changed from {old_status} to {new_status}."
            sms_message = f"Your business {business.name} status is now {new_status}."
        
        # Create and send email notification
        notification = Notification.objects.create(
            user=user,
            notification_type='email',
            subject=subject,
            message=message,
        )
        notification_service._send_email_notification(user, subject, message)
        
        # Send SMS if user has phone number
        if user.phone_number:
            sms_notification = Notification.objects.create(
                user=user,
                notification_type='sms',
                subject=subject,
                message=sms_message,
            )
            notification_service._send_sms_notification(user, sms_message)
        
        return True
        
    except Exception as e:
        self.retry(exc=e, countdown=60)