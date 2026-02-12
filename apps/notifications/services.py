from .models import Notification
from .sms import SMSService
from .emails import EmailService
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Enhanced notification service with comprehensive SMS and email support
    """
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
            success = self._send_sms_notification(user, message, order=order)
        elif notification_type == 'email':
            success = self._send_email_notification(user, subject, message)
        else:
            success = True
        
        if success:
            notification.sent_at = timezone.now()
            notification.save()
        
        return success
    
    def _send_sms_notification(self, user, message, order=None):
        """Send SMS notification"""
        if not user.phone_number:
            logger.warning(f"Cannot send SMS to user {user.id}: No phone number")
            return False
        
        result = self.sms_service.send_sms(
            user.phone_number, 
            message, 
            message_type='generic',
            user=user,
            order=order
        )
        return result['success']
    
    def _send_email_notification(self, user, subject, message):
        """Send email notification"""
        if not user.email:
            return False
            
        return self.email_service.send_generic_email(
            recipient=user.email,
            subject=subject,
            message=message,
            user=user
        ).get('success', False)
        """Send email notification"""
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
        Sends both email and SMS
        """
        user = business.owner
        
        if new_status == 'verified':
            # Send email using convenience method
            email_result = self.email_service.send_business_verification_status(business, approved=True)
            
            # Send SMS
            sms_result = self.sms_service.send_business_verification_status(business, approved=True)
            
            return email_result.get('success', False) or sms_result.get('success', False)
            
        elif new_status == 'rejected':
            # Send email using convenience method
            email_result = self.email_service.send_business_verification_status(business, approved=False)
            
            # Send SMS
            sms_result = self.sms_service.send_business_verification_status(business, approved=False)
            
            return email_result.get('success', False) or sms_result.get('success', False)
        else:
            # Generic status change notification
            return self.send_notification(
                user=user,
                notification_type='email',
                subject=f"Business Status Changed to {new_status}",
                message=f"Your business {business.name} status changed from {old_status} to {new_status}."
            )
    
    def send_order_notifications(self, order):
        """
        Send comprehensive order notifications to buyer and seller via SMS and Email
        """
        # Send to buyer
        if order.customer_email:
            try:
                self.email_service.send_order_confirmation_buyer(order)
                logger.info(f"✓ Order confirmation email sent to buyer for order {order.order_number}")
            except Exception as e:
                logger.error(f"✗ Failed to send order email to buyer: {e}")
        
        if order.customer_phone:
            self.sms_service.send_order_confirmation_buyer(order)
        
        # Send to seller
        if order.business.owner.email:
            try:
                self.email_service.send_order_confirmation_seller(order)
                logger.info(f"✓ New order email sent to seller for order {order.order_number}")
            except Exception as e:
                logger.error(f"✗ Failed to send order email to seller: {e}")
        
        if order.business.owner.phone_number:
            self.sms_service.send_order_confirmation_seller(order)
    
    def send_shipping_notification(self, order):
        """Send shipping notification to buyer via SMS and Email"""
        if order.customer_email:
            try:
                self.email_service.send_order_shipped(order)
                logger.info(f"✓ Shipping email sent for order {order.order_number}")
            except Exception as e:
                logger.error(f"✗ Failed to send shipping email: {e}")
        
        if order.customer_phone:
            self.sms_service.send_order_shipped(order)
    
    def send_delivery_notification(self, order):
        """Send delivery confirmation to buyer via SMS and Email"""
        if order.customer_email:
            try:
                self.email_service.send_order_delivered(order)
                logger.info(f"✓ Delivery email sent for order {order.order_number}")
            except Exception as e:
                logger.error(f"✗ Failed to send delivery email: {e}")
        
        if order.customer_phone:
            self.sms_service.send_order_delivered(order)
    
    def send_payment_notification(self, order, amount, success=True):
        """Send payment notification via SMS and Email"""
        if success:
            if order.customer_email:
                try:
                    self.email_service.send_payment_confirmation(order, amount)
                    logger.info(f"✓ Payment confirmation email sent for order {order.order_number}")
                except Exception as e:
                    logger.error(f"✗ Failed to send payment email: {e}")
            
            if order.customer_phone:
                self.sms_service.send_payment_success(order, amount)
    
    @staticmethod
    def send_stock_alert(product):
        """Send low stock alert to vendor via notification, SMS, and Email"""
        from apps.marketplace.models import MarketplaceNotification
        from apps.products.models import Product
        
        # Create in-app notification
        MarketplaceNotification.objects.create(
            user=product.business.owner,
            notification_type='low_stock',
            title=f'Low Stock Alert: {product.name}',
            message=f'Your product "{product.name}" is running low with only {product.quantity} units left.',
            link=f'/business/products/{product.id}/edit'
        )
        
        # Send email alert to seller
        seller_email = product.business.owner.email
        if seller_email:
            try:
                from apps.notifications.emails import EmailService
                email_service = EmailService()
                email_service.send_low_stock_alert(product, seller_email)
                logger.info(f"✓ Low stock email sent to seller for product {product.name}")
            except Exception as e:
                logger.error(f"✗ Failed to send low stock email: {e}")
        
        # Send SMS alert to seller
        seller_phone = product.business.owner.phone_number
        if seller_phone:
            try:
                from apps.notifications.sms import SMSService
                sms_service = SMSService()
                sms_service.send_low_stock_alert(product, seller_phone)
                logger.info(f"✓ Low stock SMS sent to seller for product {product.name}")
            except Exception as e:
                logger.error(f"✗ Failed to send low stock SMS: {e}")