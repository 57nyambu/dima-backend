from rest_framework import serializers
from .models import Notification, SMSLog, EmailLog


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


class SMSLogSerializer(serializers.ModelSerializer):
    """Serializer for SMS logs"""
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    order_number = serializers.CharField(source='related_order.order_number', read_only=True, allow_null=True)
    is_successful = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = SMSLog
        fields = [
            'id', 'recipient', 'message', 'message_type', 'status',
            'user_email', 'order_number', 'at_message_id', 'at_status_code',
            'at_cost', 'error_message', 'retry_count', 'created_at',
            'sent_at', 'delivered_at', 'sender_id', 'message_length',
            'sms_count', 'is_successful'
        ]
        read_only_fields = fields


class SMSLogDetailSerializer(serializers.ModelSerializer):
    """Detailed SMS log serializer with full API response"""
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    order_number = serializers.CharField(source='related_order.order_number', read_only=True, allow_null=True)
    is_successful = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = SMSLog
        fields = '__all__'
        read_only_fields = fields


class SMSStatsSerializer(serializers.Serializer):
    """Serializer for SMS statistics"""
    total = serializers.IntegerField()
    sent = serializers.IntegerField()
    delivered = serializers.IntegerField()
    failed = serializers.IntegerField()
    pending = serializers.IntegerField()
    success_rate = serializers.FloatField()
    

class SMSResendSerializer(serializers.Serializer):
    """Serializer for resending failed SMS"""
    sms_log_id = serializers.IntegerField(required=True)
    
    def validate_sms_log_id(self, value):
        try:
            sms_log = SMSLog.objects.get(id=value)
            if sms_log.status == 'sent':
                raise serializers.ValidationError("SMS was already sent successfully")
            return value
        except SMSLog.DoesNotExist:
            raise serializers.ValidationError("SMS log not found")


# Email serializers

class EmailLogSerializer(serializers.ModelSerializer):
    """Serializer for Email logs"""
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    order_number = serializers.CharField(source='related_order.order_number', read_only=True, allow_null=True)
    is_successful = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = EmailLog
        fields = [
            'id', 'recipient', 'subject', 'email_type', 'status',
            'user_email', 'order_number', 'resend_id', 'from_email',
            'from_name', 'error_message', 'retry_count', 'created_at',
            'sent_at', 'delivered_at', 'opened_at', 'clicked_at',
            'opens_count', 'clicks_count', 'is_successful'
        ]
        read_only_fields = fields


class EmailLogDetailSerializer(serializers.ModelSerializer):
    """Detailed Email log serializer with full content"""
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    order_number = serializers.CharField(source='related_order.order_number', read_only=True, allow_null=True)
    is_successful = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = EmailLog
        fields = '__all__'
        read_only_fields = fields


class EmailStatsSerializer(serializers.Serializer):
    """Serializer for Email statistics"""
    total = serializers.IntegerField()
    sent = serializers.IntegerField()
    delivered = serializers.IntegerField()
    failed = serializers.IntegerField()
    bounced = serializers.IntegerField()
    pending = serializers.IntegerField()
    success_rate = serializers.FloatField()
    delivery_rate = serializers.FloatField()
    bounce_rate = serializers.FloatField()
    avg_opens = serializers.FloatField()
    avg_clicks = serializers.FloatField()


class EmailResendSerializer(serializers.Serializer):
    """Serializer for resending failed Email"""
    email_log_id = serializers.IntegerField(required=True)
    
    def validate_email_log_id(self, value):
        try:
            email_log = EmailLog.objects.get(id=value)
            if email_log.status in ['sent', 'delivered']:
                raise serializers.ValidationError("Email was already sent successfully")
            return value
        except EmailLog.DoesNotExist:
            raise serializers.ValidationError("Email log not found")
