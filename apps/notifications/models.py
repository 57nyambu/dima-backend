from django.db import models
from django.conf import settings
from apps.accounts.models import CustomUser
from apps.orders.models import Order
from django.utils import timezone

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App Notification'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    related_order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type} notification for {self.user}"


class SMSLog(models.Model):
    """
    Comprehensive SMS logging for tracking all sent messages
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('queued', 'Queued'),
    )
    
    MESSAGE_TYPE_CHOICES = (
        ('order_confirmation', 'Order Confirmation'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('order_cancelled', 'Order Cancelled'),
        ('seller_new_order', 'Seller New Order'),
        ('signup_welcome', 'Signup Welcome'),
        ('password_reset', 'Password Reset'),
        ('account_verification', 'Account Verification'),
        ('business_verification', 'Business Verification'),
        ('payment_success', 'Payment Success'),
        ('payment_failed', 'Payment Failed'),
        ('generic', 'Generic'),
    )
    
    # Core fields
    recipient = models.CharField(max_length=20, db_index=True, help_text="Phone number in international format")
    message = models.TextField(help_text="SMS content sent")
    message_type = models.CharField(max_length=30, choices=MESSAGE_TYPE_CHOICES, default='generic', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    
    # Relationships
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_logs')
    related_order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='sms_logs')
    
    # Africa's Talking response data
    at_message_id = models.CharField(max_length=100, blank=True, null=True, help_text="Africa's Talking message ID")
    at_status_code = models.IntegerField(blank=True, null=True, help_text="Status code from AT (100=Processed, 101=Sent, 102=Queued)")
    at_cost = models.CharField(max_length=20, blank=True, null=True, help_text="SMS cost")
    at_response = models.JSONField(blank=True, null=True, help_text="Full API response from Africa's Talking")
    
    # Error handling
    error_message = models.TextField(blank=True, null=True, help_text="Error details if sending failed")
    retry_count = models.IntegerField(default=0, help_text="Number of retry attempts")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(blank=True, null=True, help_text="When SMS was successfully sent")
    delivered_at = models.DateTimeField(blank=True, null=True, help_text="When SMS was delivered (if DLR available)")
    
    # Metadata
    sender_id = models.CharField(max_length=20, blank=True, null=True, help_text="Sender ID used")
    message_length = models.IntegerField(default=0, help_text="Character count")
    sms_count = models.IntegerField(default=1, help_text="Number of SMS parts (160 chars = 1 SMS)")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'status']),
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['message_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"SMS to {self.recipient} ({self.message_type}) - {self.status}"
    
    def mark_sent(self, at_response=None):
        """Mark SMS as sent with Africa's Talking response data"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        
        if at_response:
            self.at_response = at_response
            recipients = at_response.get('SMSMessageData', {}).get('Recipients', [])
            if recipients:
                recipient_data = recipients[0]
                self.at_message_id = recipient_data.get('messageId')
                self.at_status_code = recipient_data.get('statusCode')
                self.at_cost = recipient_data.get('cost')
                
                # Update status based on AT status code
                if self.at_status_code in [100, 101]:
                    self.status = 'sent'
                elif self.at_status_code == 102:
                    self.status = 'queued'
        
        self.save()
    
    def mark_failed(self, error_message):
        """Mark SMS as failed with error details"""
        self.status = 'failed'
        self.error_message = error_message
        self.save()
    
    def mark_delivered(self):
        """Mark SMS as delivered"""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save()
    
    @property
    def is_successful(self):
        """Check if SMS was successfully sent or delivered"""
        return self.status in ['sent', 'delivered', 'queued']
    
    @classmethod
    def get_stats(cls, days=30):
        """Get SMS statistics for the last N days"""
        from django.db.models import Count, Q
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        stats = cls.objects.filter(created_at__gte=start_date).aggregate(
            total=Count('id'),
            sent=Count('id', filter=Q(status='sent')),
            delivered=Count('id', filter=Q(status='delivered')),
            failed=Count('id', filter=Q(status='failed')),
            pending=Count('id', filter=Q(status='pending')),
        )
        
        stats['success_rate'] = (
            (stats['sent'] + stats['delivered']) / stats['total'] * 100
            if stats['total'] > 0 else 0
        )
        
        return stats


class EmailLog(models.Model):
    """
    Comprehensive email logging for tracking all sent emails
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
        ('complained', 'Complained'),
    )
    
    EMAIL_TYPE_CHOICES = (
        ('order_confirmation', 'Order Confirmation'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('order_cancelled', 'Order Cancelled'),
        ('seller_new_order', 'Seller New Order'),
        ('signup_welcome', 'Signup Welcome'),
        ('password_reset', 'Password Reset'),
        ('account_verification', 'Account Verification'),
        ('business_verification', 'Business Verification'),
        ('payment_confirmation', 'Payment Confirmation'),
        ('payment_failed', 'Payment Failed'),
        ('low_stock_alert', 'Low Stock Alert'),
        ('review_received', 'Review Received'),
        ('dispute_opened', 'Dispute Opened'),
        ('generic', 'Generic'),
    )
    
    # Core fields
    recipient = models.EmailField(db_index=True, help_text="Email address")
    subject = models.CharField(max_length=255, help_text="Email subject line")
    html_content = models.TextField(help_text="HTML email content")
    text_content = models.TextField(blank=True, null=True, help_text="Plain text fallback")
    email_type = models.CharField(max_length=30, choices=EMAIL_TYPE_CHOICES, default='generic', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    
    # Relationships
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')
    related_order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')
    
    # Resend response data
    resend_id = models.CharField(max_length=100, blank=True, null=True, help_text="Resend email ID")
    resend_response = models.JSONField(blank=True, null=True, help_text="Full API response from Resend")
    
    # Email metadata
    from_email = models.EmailField(default="noreply@dima.co.ke", help_text="Sender email address")
    from_name = models.CharField(max_length=100, default="Dima Marketplace", help_text="Sender name")
    reply_to = models.EmailField(blank=True, null=True, help_text="Reply-to address")
    cc = models.JSONField(blank=True, null=True, help_text="CC recipients list")
    bcc = models.JSONField(blank=True, null=True, help_text="BCC recipients list")
    attachments = models.JSONField(blank=True, null=True, help_text="Attachment metadata")
    
    # Error handling
    error_message = models.TextField(blank=True, null=True, help_text="Error details if sending failed")
    retry_count = models.IntegerField(default=0, help_text="Number of retry attempts")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(blank=True, null=True, help_text="When email was successfully sent")
    delivered_at = models.DateTimeField(blank=True, null=True, help_text="When email was delivered")
    opened_at = models.DateTimeField(blank=True, null=True, help_text="When email was first opened")
    clicked_at = models.DateTimeField(blank=True, null=True, help_text="When links were clicked")
    
    # Tracking
    opens_count = models.IntegerField(default=0, help_text="Number of times opened")
    clicks_count = models.IntegerField(default=0, help_text="Number of link clicks")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'status']),
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['email_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"Email to {self.recipient} ({self.email_type}) - {self.status}"
    
    def mark_sent(self, resend_response=None):
        """Mark email as sent with Resend response data"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        
        if resend_response:
            self.resend_id = resend_response.get('id')
            self.resend_response = resend_response
        
        self.save()
    
    def mark_failed(self, error_message):
        """Mark email as failed with error details"""
        self.status = 'failed'
        self.error_message = error_message
        self.save()
    
    def mark_delivered(self):
        """Mark email as delivered"""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save()
    
    def mark_bounced(self):
        """Mark email as bounced"""
        self.status = 'bounced'
        self.save()
    
    def mark_opened(self):
        """Track email open"""
        if not self.opened_at:
            self.opened_at = timezone.now()
        self.opens_count += 1
        self.save()
    
    def mark_clicked(self):
        """Track link click"""
        if not self.clicked_at:
            self.clicked_at = timezone.now()
        self.clicks_count += 1
        self.save()
    
    @property
    def is_successful(self):
        """Check if email was successfully sent or delivered"""
        return self.status in ['sent', 'delivered']
    
    @classmethod
    def get_stats(cls, days=30):
        """Get email statistics for the last N days"""
        from django.db.models import Count, Q, Avg
        from datetime import timedelta
        
        start_date = timezone.now() - timedelta(days=days)
        
        stats = cls.objects.filter(created_at__gte=start_date).aggregate(
            total=Count('id'),
            sent=Count('id', filter=Q(status='sent')),
            delivered=Count('id', filter=Q(status='delivered')),
            failed=Count('id', filter=Q(status='failed')),
            bounced=Count('id', filter=Q(status='bounced')),
            pending=Count('id', filter=Q(status='pending')),
            avg_opens=Avg('opens_count'),
            avg_clicks=Avg('clicks_count'),
        )
        
        stats['success_rate'] = (
            (stats['sent'] + stats['delivered']) / stats['total'] * 100
            if stats['total'] > 0 else 0
        )
        
        stats['delivery_rate'] = (
            stats['delivered'] / (stats['sent'] + stats['delivered'])  * 100
            if (stats['sent'] + stats['delivered']) > 0 else 0
        )
        
        stats['bounce_rate'] = (
            stats['bounced'] / stats['total'] * 100
            if stats['total'] > 0 else 0
        )
        
        return stats
