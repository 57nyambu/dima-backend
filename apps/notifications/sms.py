import africastalking
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import logging

logger = logging.getLogger(__name__)

class SMSService:
    def __init__(self):
        if not all([settings.AFRICASTALKING_USERNAME, settings.AFRICASTALKING_API_KEY]):
            raise ImproperlyConfigured("Africa's Talking credentials not configured")
            
        africastalking.initialize(
            username=settings.AFRICASTALKING_USERNAME,
            api_key=settings.AFRICASTALKING_API_KEY
        )
        self.sms = africastalking.SMS
    
    def send_sms(self, phone_number, message):
        """
        Send SMS via Africa's Talking
        :param phone_number: Recipient phone number (format: +2547XXXXXXXX)
        :param message: SMS content
        :return: Africa's Talking API response
        """
        try:
            response = self.sms.send(message, [phone_number])
            return {
                'success': True,
                'response': response,
                'recipient': phone_number
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'recipient': phone_number
            }
    
    def send_generic_sms(self, phone_number, context):
        """
        Send generic SMS notifications with smart templating
        :param phone_number: Recipient phone number
        :param context: Dictionary containing:
            - template (optional): Predefined template key
            - subject: Short summary
            - message: Main content
            - order_number (optional): For order-related SMS
            - action_url (optional): Shortened URL for actions
        :return: API response
        """
        try:
            # Handle different notification types
            if context.get('template') == 'order_confirmation':
                sms_msg = (f"Order #{context['order_number']} confirmed. "
                          f"Details: {context.get('action_url', 'Visit your account')}")
            
            elif context.get('template') == 'shipping_update':
                sms_msg = (f"Your order #{context['order_number']} has shipped. "
                          f"Track: {context.get('action_url', 'Check your email')}")
            
            else:  # Generic message
                sms_msg = f"{context.get('subject', 'Notification')}: {context['message']}"
                if 'action_url' in context:
                    sms_msg += f" - {context['action_url']}"
            
            # Trim to meet SMS length limits
            sms_msg = sms_msg[:160]  # Single SMS limit
            
            return self.send_sms(phone_number, sms_msg)
            
        except Exception as e:
            logger.error(f"SMS sending failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
        
        # Example usage:
        # sms_context = {
        #     'template': 'shipping_update',
        #     'order_number': '12345',
        #     'action_url': 'https://dima.ke/track/abc123'  # Should be shortened in practice
        # }
        # sms_service.send_generic_sms('+254712345678', sms_context)
        #
        # or
        #
        # sms_context = {
        #     'subject': 'Account Update',
        #     'message': 'Your password has been changed successfully',
        #     'action_url': 'https://dima.ke/account'  # Shortened URL
        # }
        # sms_service.send_generic_sms('+254712345678', sms_context)