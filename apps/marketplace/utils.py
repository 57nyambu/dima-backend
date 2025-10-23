# marketplace/utils.py
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending marketplace emails"""
    
    @staticmethod
    def send_order_confirmation_email(order, to_email):
        """Send order confirmation email to buyer"""
        subject = f'Order Confirmation #{getattr(order, "order_number", order.id)}'
        
        html_message = render_to_string('marketplace/emails/order_confirmation.html', {
            'order': order,
            'buyer_name': order.buyer.first_name or order.buyer.email,
            'vendor_name': order.business.name,
            'total_amount': order.total_amount
        })
        
        plain_message = strip_tags(html_message)
        
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=html_message,
                fail_silently=False
            )
            logger.info(f"Order confirmation email sent to {to_email}")
        except Exception as e:
            logger.error(f"Failed to send order confirmation email: {e}")
    
    @staticmethod
    def send_vendor_notification_email(order, vendor_email):
        """Send new order notification to vendor"""
        subject = f'New Order Received #{getattr(order, "order_number", order.id)}'
        
        html_message = render_to_string('marketplace/emails/vendor_new_order.html', {
            'order': order,
            'vendor_name': order.business.name,
            'buyer_name': order.buyer.first_name or order.buyer.email,
            'total_amount': order.total_amount
        })
        
        plain_message = strip_tags(html_message)
        
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[vendor_email],
                html_message=html_message,
                fail_silently=False
            )
            logger.info(f"Vendor notification email sent to {vendor_email}")
        except Exception as e:
            logger.error(f"Failed to send vendor notification email: {e}")


@shared_task
def update_search_indexes():
    """Background task to update search indexes"""
    from .services import AggregationService
    
    try:
        AggregationService.update_search_indexes()
        logger.info("Search indexes updated successfully")
    except Exception as e:
        logger.error(f"Failed to update search indexes: {e}")


@shared_task
def send_order_emails(order_id):
    """Background task to send order-related emails"""
    from apps.orders.models import Order
    
    try:
        order = Order.objects.get(id=order_id)
        
        # Send confirmation to buyer
        EmailService.send_order_confirmation_email(order, order.buyer.email)
        
        # Send notification to vendor
        EmailService.send_vendor_notification_email(order, order.business.owner.email)
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for email sending")
    except Exception as e:
        logger.error(f"Failed to send order emails for order {order_id}: {e}")


@shared_task
def generate_vendor_analytics_report(business_id, period_start, period_end):
    """Generate analytics report for a vendor"""
    from .services import CommissionEngine
    from apps.business.models import Business
    
    try:
        business = Business.objects.get(id=business_id)
        report = CommissionEngine.process_payout_calculation(
            business, period_start, period_end
        )
        
        # You could save this report to a model or send it via email
        logger.info(f"Analytics report generated for {business.name}")
        
        return report
        
    except Business.DoesNotExist:
        logger.error(f"Business {business_id} not found for analytics report")
