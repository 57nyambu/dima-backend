import africastalking
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class SMSService:
    """
    Enhanced AfricasTalking SMS Service with templates and comprehensive logging
    Docs: https://developers.africastalking.com/docs/sms/overview
    """
    
    # SMS Templates for different notification types
    SMS_TEMPLATES = {
        'order_confirmation_buyer': (
            "✓ Order confirmed! Your order #{order_number} from {business_name} "
            "for KES {total:.2f} has been received and is being processed."
        ),
        'order_confirmation_seller': (
            "💰 New order #{order_number}! You received an order worth KES {total:.2f}. "
            "Login to your dashboard to process it."
        ),
        'order_shipped': (
            "📦 Your order #{order_number} has been shipped! "
            "{tracking_info}Track your package online."
        ),
        'order_delivered': (
            "✓ Your order #{order_number} has been delivered. "
            "Thank you for shopping with us! Rate your experience."
        ),
        'order_cancelled': (
            "Order #{order_number} has been cancelled. "
            "Refund will be processed within 3-5 business days."
        ),
        'signup_welcome': (
            "Welcome to Dima Marketplace! Your account has been created successfully. "
            "Start shopping or selling today!"
        ),
        'password_reset': (
            "Your password reset code is: {reset_code}. "
            "Valid for 10 minutes. Do not share this code with anyone."
        ),
        'password_reset_success': (
            "✓ Your password has been successfully reset. "
            "If you did not make this change, please contact support immediately."
        ),
        'account_verification': (
            "Your verification code is: {verification_code}. "
            "Use this code to verify your Dima account."
        ),
        'business_verification_approved': (
            "🎉 Congratulations! Your business '{business_name}' has been verified. "
            "You can now start selling on Dima."
        ),
        'business_verification_rejected': (
            "Your business verification was not approved. "
            "Please review requirements and resubmit."
        ),
        'payment_success': (
            "Payment successful! KES {amount:.2f} received for order #{order_number}. "
            "Your order is being processed."
        ),
        'payment_failed': (
            "Payment failed for order #{order_number}. "
            "Please try again or contact support."
        ),
        'low_stock_alert': (
            "⚠️ Low stock alert: {product_name} has only {stock_count} units left. "
            "Restock soon to avoid missed sales."
        ),
    }
    
    def __init__(self):
        if not all([settings.AFRICASTALKING_USERNAME, settings.AFRICASTALKING_API_KEY]):
            raise ImproperlyConfigured("Africa's Talking credentials not configured")
        
        self.username = settings.AFRICASTALKING_USERNAME
        self.api_key = settings.AFRICASTALKING_API_KEY
        self.sender_id = getattr(settings, 'AFRICASTALKING_SENDER_ID', None)
        
        # Initialize AfricasTalking SDK
        africastalking.initialize(
            username=self.username,
            api_key=self.api_key
        )
        
        self.sms = africastalking.SMS
        logger.info(f"SMS Service initialized for username: {self.username}")
    
    def _calculate_sms_count(self, message):
        """Calculate how many SMS parts will be used"""
        length = len(message)
        if length <= 160:
            return 1
        elif length <= 306:
            return 2
        else:
            return (length // 153) + (1 if length % 153 > 0 else 0)
    
    def _log_sms(self, phone_number, message, message_type='generic', user=None, order=None):
        """Create SMS log entry"""
        from .models import SMSLog
        
        sms_log = SMSLog.objects.create(
            recipient=phone_number,
            message=message,
            message_type=message_type,
            user=user,
            related_order=order,
            sender_id=self.sender_id,
            message_length=len(message),
            sms_count=self._calculate_sms_count(message),
            status='pending'
        )
        return sms_log
    
    def send_sms(self, phone_number, message, message_type='generic', user=None, order=None):
        """
        Send SMS via AfricasTalking SDK with comprehensive logging
        
        Args:
            phone_number: Recipient phone number (format: +2547XXXXXXXX)
            message: SMS content
            message_type: Type of message for categorization
            user: CustomUser instance (optional)
            order: Order instance (optional)
            
        Returns:
            Dictionary with success status, sms_log instance, and response data
        """
        # Create log entry
        sms_log = self._log_sms(phone_number, message, message_type, user, order)
        
        try:
            # Ensure phone number is a list
            phone_numbers = [phone_number] if isinstance(phone_number, str) else phone_number
            
            # Validate phone numbers
            for number in phone_numbers:
                if not number.startswith('+'):
                    logger.warning(f"Phone number {number} should start with + (e.g., +254712345678)")
            
            logger.info(f"Sending SMS to {phone_numbers}: {message[:50]}...")
            
            # Build kwargs for SDK
            kwargs = {}
            if self.sender_id and self.username != 'sandbox':
                kwargs['sender_id'] = self.sender_id
            
            # Send SMS using SDK
            response = self.sms.send(message, phone_numbers, **kwargs)
            
            logger.info(f"API Response: {response}")
            
            # Parse SDK response
            sms_data = response.get('SMSMessageData', {})
            recipients = sms_data.get('Recipients', [])
            
            # Check if any messages were sent successfully
            if recipients:
                success = any(r.get('statusCode') in [100, 101, 102] for r in recipients)
            else:
                logger.error(f"No recipients in response. Full data: {sms_data}")
                success = False
            
            if success:
                logger.info(f"✓ SMS sent successfully: {sms_data.get('Message', '')}")
                sms_log.mark_sent(response)
                
                for r in recipients:
                    logger.info(f"  → {r.get('number')}: {r.get('status')} (Code: {r.get('statusCode')})")
            else:
                logger.error(f"✗ SMS failed. Recipients: {recipients}")
                error_msg = recipients[0].get('status', 'Unknown error') if recipients else 'No recipients'
                sms_log.mark_failed(error_msg)
                
                if recipients:
                    for r in recipients:
                        logger.error(f"  → {r.get('number')}: {r.get('status')} (Code: {r.get('statusCode')})")
            
            return {
                'success': success,
                'sms_log': sms_log,
                'response': response,
                'recipient': phone_numbers[0] if len(phone_numbers) == 1 else phone_numbers,
                'message_data': sms_data,
                'recipients': recipients,
            }
            
        except Exception as e:
            logger.error(f"✗ SMS sending failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            sms_log.mark_failed(str(e))
            
            return {
                'success': False,
                'sms_log': sms_log,
                'error': str(e),
                'recipient': phone_number
            }
    
    def send_templated_sms(self, phone_number, template_key, context, user=None, order=None):
        """
        Send SMS using predefined template
        
        Args:
            phone_number: Recipient phone number
            template_key: Key from SMS_TEMPLATES
            context: Dictionary with template variables
            user: CustomUser instance (optional)
            order: Order instance (optional)
            
        Returns:
            API response dictionary
        """
        if template_key not in self.SMS_TEMPLATES:
            logger.error(f"Template '{template_key}' not found")
            return {
                'success': False,
                'error': f"Template '{template_key}' not found"
            }
        
        try:
            message = self.SMS_TEMPLATES[template_key].format(**context)
            return self.send_sms(phone_number, message, template_key, user, order)
        except KeyError as e:
            logger.error(f"Missing template variable: {e}")
            return {
                'success': False,
                'error': f"Missing template variable: {e}"
            }
    
    # Convenience methods for specific notification types
    
    def send_order_confirmation_buyer(self, order, phone_number=None):
        """Send order confirmation to buyer"""
        phone = phone_number or order.customer_phone
        if not phone:
            return {'success': False, 'error': 'No phone number available'}
        
        context = {
            'order_number': order.order_number,
            'business_name': order.business.name,
            'total': order.total
        }
        return self.send_templated_sms(
            phone, 'order_confirmation_buyer', context,
            user=order.user, order=order
        )
    
    def send_order_confirmation_seller(self, order, phone_number=None):
        """Send new order notification to seller"""
        phone = phone_number or order.business.owner.phone_number
        if not phone:
            return {'success': False, 'error': 'No phone number available'}
        
        context = {
            'order_number': order.order_number,
            'total': order.total
        }
        return self.send_templated_sms(
            phone, 'order_confirmation_seller', context,
            user=order.business.owner, order=order
        )
    
    def send_order_shipped(self, order, phone_number=None):
        """Send shipping notification"""
        phone = phone_number or order.customer_phone
        if not phone:
            return {'success': False, 'error': 'No phone number available'}
        
        tracking_info = f"Tracking: {order.tracking_number}. " if order.tracking_number else ""
        context = {
            'order_number': order.order_number,
            'tracking_info': tracking_info
        }
        return self.send_templated_sms(
            phone, 'order_shipped', context,
            user=order.user, order=order
        )
    
    def send_order_delivered(self, order, phone_number=None):
        """Send delivery confirmation"""
        phone = phone_number or order.customer_phone
        if not phone:
            return {'success': False, 'error': 'No phone number available'}
        
        context = {'order_number': order.order_number}
        return self.send_templated_sms(
            phone, 'order_delivered', context,
            user=order.user, order=order
        )
    
    def send_signup_welcome(self, user):
        """Send welcome SMS to new user"""
        if not user.phone_number:
            return {'success': False, 'error': 'No phone number available'}
        
        return self.send_templated_sms(
            user.phone_number, 'signup_welcome', {},
            user=user
        )
    
    def send_password_reset_code(self, user, reset_code):
        """Send password reset code"""
        if not user.phone_number:
            return {'success': False, 'error': 'No phone number available'}
        
        context = {'reset_code': reset_code}
        return self.send_templated_sms(
            user.phone_number, 'password_reset', context,
            user=user
        )
    
    def send_password_reset_success(self, user):
        """Send password reset success confirmation"""
        if not user.phone_number:
            return {'success': False, 'error': 'No phone number available'}
        
        return self.send_templated_sms(
            user.phone_number, 'password_reset_success', {},
            user=user
        )
    
    def send_business_verification_status(self, business, approved=True):
        """Send business verification status"""
        phone = business.owner.phone_number
        if not phone:
            return {'success': False, 'error': 'No phone number available'}
        
        template_key = 'business_verification_approved' if approved else 'business_verification_rejected'
        context = {'business_name': business.name}
        
        return self.send_templated_sms(
            phone, template_key, context,
            user=business.owner
        )
    
    def send_payment_success(self, order, amount, phone_number=None):
        """Send payment success notification"""
        phone = phone_number or order.customer_phone
        if not phone:
            return {'success': False, 'error': 'No phone number available'}
        
        context = {
            'amount': amount,
            'order_number': order.order_number
        }
        return self.send_templated_sms(
            phone, 'payment_success', context,
            user=order.user, order=order
        )
    
    def send_low_stock_alert(self, product, seller_phone):
        """Send low stock alert to seller"""
        if not seller_phone:
            return {'success': False, 'error': 'No phone number available'}
        
        context = {
            'product_name': product.name,
            'stock_count': product.stock_quantity
        }
        return self.send_templated_sms(
            seller_phone, 'low_stock_alert', context,
            user=product.business.owner
        )