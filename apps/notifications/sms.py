import africastalking
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import logging

logger = logging.getLogger(__name__)

class SMSService:
    """
    AfricasTalking SMS Service using official SDK
    Docs: https://developers.africastalking.com/docs/sms/overview
    
    The official SDK handles:
    - Proper authentication
    - Sandbox vs production mode
    - Request formatting
    - Error handling
    """
    
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
    
    def send_sms(self, phone_number, message):
        """
        Send SMS via AfricasTalking SDK
        :param phone_number: Recipient phone number (format: +2547XXXXXXXX)
        :param message: SMS content (max 160 chars for single SMS)
        :return: Dictionary with success status and response data
        """
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
            # Status codes: 100=Processed, 101=Sent, 102=Queued
            if recipients:
                success = any(r.get('statusCode') in [100, 101, 102] for r in recipients)
            else:
                logger.error(f"No recipients in response. Full data: {sms_data}")
                success = False
            
            if success:
                logger.info(f"✓ SMS sent successfully: {sms_data.get('Message', '')}")
                for r in recipients:
                    logger.info(f"  → {r.get('number')}: {r.get('status')} (Code: {r.get('statusCode')})")
            else:
                logger.error(f"✗ SMS failed. Recipients: {recipients}")
                if recipients:
                    for r in recipients:
                        logger.error(f"  → {r.get('number')}: {r.get('status')} (Code: {r.get('statusCode')})")
            
            return {
                'success': success,
                'response': response,
                'recipient': phone_numbers[0] if len(phone_numbers) == 1 else phone_numbers,
                'message_data': sms_data,
                'recipients': recipients,
                'full_response': response
            }
            
        except Exception as e:
            logger.error(f"✗ SMS sending failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
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