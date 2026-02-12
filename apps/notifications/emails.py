import os
import resend
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """
    Enhanced Resend email service with templates and comprehensive logging
    Docs: https://resend.com/docs/send-with-python
    """
    
    # Email templates for different notification types
    EMAIL_TEMPLATES = {
        'order_confirmation_buyer': {
            'subject': 'Order Confirmation #{order_number}',
            'template': 'notifications/emails/order_confirmation_buyer.html',
        },
        'order_confirmation_seller': {
            'subject': 'New Order Received #{order_number}',
            'template': 'notifications/emails/order_confirmation_seller.html',
        },
        'order_shipped': {
            'subject': 'Your Order Has Been Shipped #{order_number}',
            'template': 'notifications/emails/order_shipped.html',
        },
        'order_delivered': {
            'subject': 'Order Delivered Successfully #{order_number}',
            'template': 'notifications/emails/order_delivered.html',
        },
        'order_cancelled': {
            'subject': 'Order Cancelled #{order_number}',
            'template': 'notifications/emails/order_cancelled.html',
        },
        'signup_welcome': {
            'subject': 'Welcome to Dima!',
            'template': 'notifications/emails/signup_welcome.html',
        },
        'password_reset': {
            'subject': 'Password Reset Request',
            'template': 'notifications/emails/password_reset.html',
        },
        'password_reset_success': {
            'subject': 'Password Successfully Reset',
            'template': 'notifications/emails/password_reset_success.html',
        },
        'business_verification_approved': {
            'subject': 'Your Business Has Been Verified!',
            'template': 'notifications/emails/business_verified.html',
        },
        'business_verification_rejected': {
            'subject': 'Business Verification Update',
            'template': 'notifications/emails/business_rejected.html',
        },
        'low_stock_alert': {
            'subject': 'Low Stock Alert: {product_name}',
            'template': 'notifications/emails/low_stock_alert.html',
        },
        'payment_success': {
            'subject': 'Payment Confirmation - Order #{order_number}',
            'template': 'notifications/emails/payment_success.html',
        },
        'payment_failed': {
            'subject': 'Payment Failed - Order #{order_number}',
            'template': 'notifications/emails/payment_failed.html',
        },
        'review_received': {
            'subject': 'New Review on Your Product',
            'template': 'notifications/emails/review_received.html',
        },
        'dispute_opened': {
            'subject': 'Dispute Opened for Order #{order_number}',
            'template': 'notifications/emails/dispute_opened.html',
        },
        'generic': {
            'subject': '{subject}',
            'template': 'notifications/emails/generic_notification.html',
        },
    }
    
    def __init__(self):
        """Initialize Resend with API key"""
        resend_key = getattr(settings, 'DIMA_RESEND_KEY', os.environ.get('DIMA_RESEND_KEY'))
        
        if not resend_key:
            raise ImproperlyConfigured("DIMA_RESEND_KEY not found in settings or environment")
        
        resend.api_key = resend_key
        
        # Use DEFAULT_FROM_EMAIL from settings or default to Resend's onboarding domain
        self.default_from_email = getattr(
            settings, 
            'DEFAULT_FROM_EMAIL', 
            'Dima Marketplace <onboarding@resend.dev>'
        )
        
        logger.info(f"Email Service initialized with Resend | From: {self.default_from_email}")
    
    def _log_email(self, recipient, subject, html_content, text_content, email_type='generic', 
                   user=None, order=None, **metadata):
        """Create email log entry"""
        from .models import EmailLog
        
        log = EmailLog.objects.create(
            recipient=recipient,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=email_type,
            user=user,
            related_order=order,
            from_email=metadata.get('from_email', self.default_from_email),
            from_name=metadata.get('from_name', 'Dima Marketplace'),
            reply_to=metadata.get('reply_to'),
            cc=metadata.get('cc'),
            bcc=metadata.get('bcc'),
        )
        
        logger.info(f"Email log created: {log.id} to {recipient}")
        return log
    
    def send_email(self, recipient, subject, html_content=None, text_content=None, 
                   email_type='generic', user=None, order=None, **kwargs):
        """
        Send email using Resend with automatic logging
        
        Args:
            recipient: Email address
            subject: Email subject
            html_content: HTML content (if not using template)
            text_content: Plain text content (optional, generated from HTML if not provided)
            email_type: Type of email for logging
            user: Associated user
            order: Associated order
            **kwargs: Additional Resend parameters (reply_to, cc, bcc, attachments, etc.)
        
        Returns:
            dict: {'success': bool, 'email_log': EmailLog, 'response': dict}
        """
        # Create log entry first
        email_log = self._log_email(
            recipient=recipient,
            subject=subject,
            html_content=html_content or '',
            text_content=text_content or strip_tags(html_content) if html_content else '',
            email_type=email_type,
            user=user,
            order=order,
            **kwargs
        )
        
        try:
            # Prepare Resend parameters
            params = {
                "from": kwargs.get('from_email', self.default_from_email),
                "to": [recipient],
                "subject": subject,
                "html": html_content,
            }
            
            # Add optional text version
            if text_content:
                params["text"] = text_content
            
            # Add optional parameters
            if kwargs.get('reply_to'):
                params["reply_to"] = kwargs['reply_to']
            if kwargs.get('cc'):
                params["cc"] = kwargs['cc']
            if kwargs.get('bcc'):
                params["bcc"] = kwargs['bcc']
            if kwargs.get('attachments'):
                params["attachments"] = kwargs['attachments']
            
            # Send via Resend
            response = resend.Emails.send(params)
            
            # Mark as sent
            email_log.mark_sent(response)
            
            logger.info(f"✓ Email sent successfully to {recipient} | Type: {email_type} | ID: {response.get('id')}")
            
            return {
                'success': True,
                'email_log': email_log,
                'response': response
            }
            
        except Exception as e:
            error_msg = str(e)
            email_log.mark_failed(error_msg)
            logger.error(f"✗ Failed to send email to {recipient}: {error_msg}")
            
            return {
                'success': False,
                'email_log': email_log,
                'error': error_msg
            }
    
    def send_templated_email(self, recipient, template_key, context, user=None, order=None, **kwargs):
        """
        Send email using predefined template
        
        Args:
            recipient: Email address
            template_key: Key from EMAIL_TEMPLATES
            context: Template context dict
            user: Associated user
            order: Associated order
            **kwargs: Additional Resend parameters
        
        Returns:
            dict: Result from send_email()
        """
        if template_key not in self.EMAIL_TEMPLATES:
            logger.error(f"Unknown email template: {template_key}")
            return {'success': False, 'error': 'Unknown template'}
        
        template_config = self.EMAIL_TEMPLATES[template_key]
        
        # Add default context
        context.setdefault('site_url', getattr(settings, 'SITE_URL', 'https://dima.co.ke'))
        context.setdefault('site_name', 'Dima Marketplace')
        context.setdefault('support_email', getattr(settings, 'SUPPORT_EMAIL', 'support@dima.co.ke'))
        
        # Render subject with context
        subject = template_config['subject'].format(**context)
        
        # Render HTML template
        try:
            html_content = render_to_string(template_config['template'], context)
            text_content = strip_tags(html_content)
        except Exception as e:
            logger.error(f"Failed to render template {template_key}: {str(e)}")
            return {'success': False, 'error': f'Template rendering failed: {str(e)}'}
        
        return self.send_email(
            recipient=recipient,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
            email_type=template_key,
            user=user,
            order=order,
            **kwargs
        )
    
    # Convenience methods for specific notification types
    
    def send_order_confirmation_buyer(self, order, recipient=None):
        """Send order confirmation email to buyer"""
        recipient = recipient or order.customer_email
        
        context = {
            'order_number': order.order_number,
            'order': order,
            'user': order.customer,
            'total': order.total_amount,
            'items': order.items.all() if hasattr(order, 'items') else [],
        }
        
        return self.send_templated_email(
            recipient=recipient,
            template_key='order_confirmation_buyer',
            context=context,
            user=order.customer,
            order=order
        )
    
    def send_order_confirmation_seller(self, order, recipient=None):
        """Send new order notification to seller"""
        recipient = recipient or order.business.owner.email
        
        context = {
            'order_number': order.order_number,
            'order': order,
            'business': order.business,
            'seller': order.business.owner,
            'total': order.total_amount,
            'customer_name': order.customer_name,
        }
        
        return self.send_templated_email(
            recipient=recipient,
            template_key='order_confirmation_seller',
            context=context,
            user=order.business.owner,
            order=order
        )
    
    def send_order_shipped(self, order, tracking_number=None, recipient=None):
        """Send shipping notification to buyer"""
        recipient = recipient or order.customer_email
        
        context = {
            'order_number': order.order_number,
            'order': order,
            'tracking_number': tracking_number or order.tracking_number,
            'user': order.customer,
        }
        
        return self.send_templated_email(
            recipient=recipient,
            template_key='order_shipped',
            context=context,
            user=order.customer,
            order=order
        )
    
    def send_order_delivered(self, order, recipient=None):
        """Send delivery confirmation to buyer"""
        recipient = recipient or order.customer_email
        
        context = {
            'order_number': order.order_number,
            'order': order,
            'user': order.customer,
        }
        
        return self.send_templated_email(
            recipient=recipient,
            template_key='order_delivered',
            context=context,
            user=order.customer,
            order=order
        )
    
    def send_signup_welcome(self, user):
        """Send welcome email to new user"""
        context = {
            'user': user,
            'first_name': user.first_name or 'there',
        }
        
        return self.send_templated_email(
            recipient=user.email,
            template_key='signup_welcome',
            context=context,
            user=user
        )
    
    def send_password_reset(self, user, reset_code):
        """Send password reset code email"""
        context = {
            'user': user,
            'reset_code': reset_code,
            'first_name': user.first_name or 'there',
        }
        
        return self.send_templated_email(
            recipient=user.email,
            template_key='password_reset',
            context=context,
            user=user
        )
    
    def send_password_reset_success(self, user):
        """Send password reset success confirmation email"""
        context = {
            'user': user,
            'first_name': user.first_name or 'there',
        }
        
        return self.send_templated_email(
            recipient=user.email,
            template_key='password_reset_success',
            context=context,
            user=user
        )
    
    def send_business_verification_status(self, business, approved=True):
        """Send business verification status email"""
        template_key = 'business_verification_approved' if approved else 'business_verification_rejected'
        
        context = {
            'user': business.owner,
            'business': business,
            'business_name': business.name,
        }
        
        return self.send_templated_email(
            recipient=business.owner.email,
            template_key=template_key,
            context=context,
            user=business.owner
        )
    
    def send_low_stock_alert(self, product, seller_email):
        """Send low stock alert to seller"""
        context = {
            'product': product,
            'product_name': product.name,
            'stock_count': product.quantity,
            'business': product.business,
        }
        
        return self.send_templated_email(
            recipient=seller_email,
            template_key='low_stock_alert',
            context=context,
            user=product.business.owner
        )
    
    def send_payment_confirmation(self, order, amount, recipient=None):
        """Send payment success confirmation"""
        recipient = recipient or order.customer_email
        
        context = {
            'order_number': order.order_number,
            'order': order,
            'amount': amount,
            'user': order.customer,
        }
        
        return self.send_templated_email(
            recipient=recipient,
            template_key='payment_success',
            context=context,
            user=order.customer,
            order=order
        )
    
    def send_review_notification(self, product, review, seller_email):
        """Notify seller of new review"""
        context = {
            'product': product,
            'review': review,
            'reviewer_name': review.user.get_full_name() if hasattr(review, 'user') else 'A customer',
            'rating': review.rating if hasattr(review, 'rating') else 5,
        }
        
        return self.send_templated_email(
            recipient=seller_email,
            template_key='review_received',
            context=context,
            user=product.business.owner
        )
    
    def send_dispute_notification(self, order, dispute, recipient):
        """Send dispute notification"""
        context = {
            'order_number': order.order_number,
            'order': order,
            'dispute': dispute,
        }
        
        return self.send_templated_email(
            recipient=recipient,
            template_key='dispute_opened',
            context=context,
            order=order
        )
    
    def send_generic_email(self, recipient, subject, message, user=None):
        """Send generic notification email"""
        context = {
            'subject': subject,
            'message': message,
            'user': user,
        }
        
        return self.send_templated_email(
            recipient=recipient,
            template_key='generic',
            context=context,
            user=user
        )