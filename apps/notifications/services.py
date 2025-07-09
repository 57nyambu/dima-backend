from .models import Notification
from .sms import SMSService
from .emails import EmailService
from django.conf import settings
from django.utils import timezone

class NotificationService:
    def __init__(self):
        self.sms_service = SMSService()
        self.email_service = EmailService()
    
    def send_notification(self, user, notification_type, subject, message, order=None):
        """
        Central method to send all types of notifications
        """
        # Create notification record
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            subject=subject,
            message=message,
            related_order=order
        )
        
        # Dispatch based on type
        if notification_type == 'sms':
            return self._send_sms_notification(user, message)
        elif notification_type == 'email':
            return self._send_email_notification(user, subject, message)
        
        notification.sent_at = timezone.now()
        notification.save()
        return True
    
    def _send_sms_notification(self, user, message):
        if not user.phone_number:
            return False
        
        result = self.sms_service.send_sms(user.phone_number, message)
        return result['success']
    
    def _send_email_notification(self, user, subject, message):
        if not user.email:
            return False
            
        return self.email_service.send_email(
            subject=subject,
            recipient=user.email,
            template_name="notifications/emails/generic_notification.html",
            context={'message': message}
        )
    
    def send_business_verification_notification(self, business, old_status, new_status):
        """
        Specialized method for business verification notifications
        """
        user = business.owner
        if new_status == 'verified':
            # Send congratulatory email with template
            return self.email_service.send_email(
                subject="Your Business Has Been Verified!",
                recipient=user.email,
                template_name="notifications/emails/business_verified.html",
                context={
                    'user': user,
                    'business': business,
                    'site_url': settings.SITE_URL
                }
            )
        elif new_status == 'rejected':
            # Send rejection email with instructions
            return self.email_service.send_email(
                subject="Business Verification Update",
                recipient=user.email,
                template_name="notifications/emails/business_rejected.html",
                context={
                    'user': user,
                    'business': business,
                    'site_url': settings.SITE_URL,
                    'support_email': settings.SUPPORT_EMAIL
                }
            )
        else:
            # Generic status change notification
            return self.send_notification(
                user=user,
                notification_type='email',
                subject=f"Business Status Changed to {new_status}",
                message=f"Your business {business.name} status changed from {old_status} to {new_status}."
            )