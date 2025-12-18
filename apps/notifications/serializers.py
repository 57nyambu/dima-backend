from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification model
    """
    user_email = serializers.EmailField(source='user.email', read_only=True)
    order_number = serializers.CharField(source='related_order.order_number', read_only=True, allow_null=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user_email', 'notification_type', 'subject', 'message',
            'is_read', 'order_number', 'related_order', 'sent_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'user_email', 'notification_type', 'subject', 'message',
            'order_number', 'related_order', 'sent_at', 'created_at'
        ]
