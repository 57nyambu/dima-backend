from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

class EmailService:
    @staticmethod
    def send_email(subject, recipient, template_name, context):
        """
        Send HTML email with plain text fallback
        """
        html_content = render_to_string(f"notifications/emails/{template_name}", context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient]
        )
        email.attach_alternative(html_content, "text/html")
        
        try:
            email.send()
            return True
        except Exception as e:
            # Log email sending error
            return False

    # Specific email templates
    def send_order_confirmation(self, order, user):
        context = {
            'user': user,
            'order': order,
            'site_url': settings.SITE_URL
        }
        return self.send_email(
            subject=f"Order Confirmation #{order.order_number}",
            recipient=user.email,
            template_name="order_confirmation.html",
            context=context
        )
    
    def send_password_reset(self, user, reset_link):
        context = {
            'user': user,
            'reset_link': reset_link,
            'site_url': settings.SITE_URL
        }
        return self.send_email(
            subject="Password Reset Request",
            recipient=user.email,
            template_name="password_reset.html",
            context=context
        )