from django.db import models
from django.conf import settings
from apps.accounts.models import CustomUser
from apps.orders.models import Order

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
