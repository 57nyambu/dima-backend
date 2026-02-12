from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from .models import Notification, SMSLog, EmailLog


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'notification_type', 'subject', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__email', 'subject', 'message']
    readonly_fields = ['created_at', 'sent_at']
    date_hierarchy = 'created_at'


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'recipient', 'message_type_badge', 'status_badge', 
        'user_link', 'order_link', 'cost_display', 'created_at'
    ]
    list_filter = [
        'status', 'message_type', 'created_at', 
        ('user', admin.EmptyFieldListFilter)
    ]
    search_fields = ['recipient', 'message', 'at_message_id', 'user__email']
    readonly_fields = [
        'recipient', 'message', 'message_type', 'status', 'user', 'related_order',
        'at_message_id', 'at_status_code', 'at_cost', 'at_response',
        'error_message', 'retry_count', 'created_at', 'sent_at', 'delivered_at',
        'sender_id', 'message_length', 'sms_count', 'formatted_response'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('recipient', 'message', 'message_type', 'status')
        }),
        ('Relationships', {
            'fields': ('user', 'related_order')
        }),
        ("Africa's Talking Response", {
            'fields': ('at_message_id', 'at_status_code', 'at_cost', 'formatted_response'),
            'classes': ('collapse',)
        }),
        ('Error Details', {
            'fields': ('error_message', 'retry_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'sent_at', 'delivered_at')
        }),
        ('Metadata', {
            'fields': ('sender_id', 'message_length', 'sms_count'),
            'classes': ('collapse',)
        }),
    )
    
    def message_type_badge(self, obj):
        """Display message type as a colored badge"""
        colors = {
            'order_confirmation': '#28a745',
            'order_shipped': '#17a2b8',
            'order_delivered': '#28a745',
            'seller_new_order': '#ffc107',
            'signup_welcome': '#007bff',
            'password_reset': '#dc3545',
            'generic': '#6c757d',
        }
        color = colors.get(obj.message_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_message_type_display()
        )
    message_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            'pending': '#ffc107',
            'sent': '#28a745',
            'delivered': '#28a745',
            'failed': '#dc3545',
            'queued': '#17a2b8',
        }
        icons = {
            'pending': '⏳',
            'sent': '✓',
            'delivered': '✓✓',
            'failed': '✗',
            'queued': '⏸',
        }
        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '•')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def user_link(self, obj):
        """Link to related user"""
        if obj.user:
            url = reverse('admin:accounts_customuser_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return '-'
    user_link.short_description = 'User'
    
    def order_link(self, obj):
        """Link to related order"""
        if obj.related_order:
            url = reverse('admin:orders_order_change', args=[obj.related_order.id])
            return format_html('<a href="{}">{}</a>', url, obj.related_order.order_number)
        return '-'
    order_link.short_description = 'Order'
    
    def cost_display(self, obj):
        """Display cost with formatting"""
        if obj.at_cost:
            return obj.at_cost
        return '-'
    cost_display.short_description = 'Cost'
    
    def formatted_response(self, obj):
        """Display formatted JSON response"""
        if obj.at_response:
            import json
            formatted = json.dumps(obj.at_response, indent=2)
            return format_html('<pre style="background: #f8f9fa; padding: 10px;">{}</pre>', formatted)
        return '-'
    formatted_response.short_description = "Full API Response"
    
    def get_queryset(self, request):
        """Optimize queries"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'related_order')
    
    def has_add_permission(self, request):
        """Disable manual creation of SMS logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup"""
        return request.user.is_superuser
    
    # Add custom admin actions
    actions = ['mark_as_delivered', 'retry_failed']
    
    def mark_as_delivered(self, request, queryset):
        """Mark selected SMS as delivered"""
        updated = queryset.filter(status='sent').update(status='delivered')
        self.message_user(request, f'{updated} SMS marked as delivered')
    mark_as_delivered.short_description = 'Mark selected as delivered'
    
    def retry_failed(self, request, queryset):
        """Retry failed SMS"""
        from .sms import SMSService
        sms_service = SMSService()
        
        success_count = 0
        fail_count = 0
        
        for sms_log in queryset.filter(status='failed'):
            result = sms_service.send_sms(
                sms_log.recipient,
                sms_log.message,
                sms_log.message_type,
                sms_log.user,
                sms_log.related_order
            )
            
            if result['success']:
                success_count += 1
                sms_log.retry_count += 1
                sms_log.save()
            else:
                fail_count += 1
        
        self.message_user(
            request, 
            f'Retry complete: {success_count} successful, {fail_count} failed'
        )
    retry_failed.short_description = 'Retry selected failed SMS'


# Add summary statistics to admin index
class SMSStatsAdmin(admin.ModelAdmin):
    """Custom admin view for SMS statistics"""
    
    def changelist_view(self, request, extra_context=None):
        # Get statistics
        stats = SMSLog.get_stats(days=30)
        
        extra_context = extra_context or {}
        extra_context['sms_stats'] = stats
        
        return super().changelist_view(request, extra_context)


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'recipient', 'subject_short', 'email_type_badge', 'status_badge',
        'user_link', 'order_link', 'opens_count', 'clicks_count', 'created_at'
    ]
    list_filter = [
        'status', 'email_type', 'created_at',
        ('user', admin.EmptyFieldListFilter)
    ]
    search_fields = ['recipient', 'subject', 'resend_id', 'user__email']
    readonly_fields = [
        'recipient', 'subject', 'html_content', 'text_content', 'email_type',
        'status', 'user', 'related_order', 'resend_id', 'resend_response',
        'from_email', 'from_name', 'reply_to', 'cc', 'bcc', 'attachments',
        'error_message', 'retry_count', 'created_at', 'sent_at', 'delivered_at',
        'opened_at', 'clicked_at', 'opens_count', 'clicks_count',
        'formatted_response', 'html_preview'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('recipient', 'subject', 'email_type', 'status')
        }),
        ('Content', {
            'fields': ('html_preview', 'html_content', 'text_content'),
            'classes': ('collapse',)
        }),
        ('Relationships', {
            'fields': ('user', 'related_order')
        }),
        ('Resend Response', {
            'fields': ('resend_id', 'formatted_response'),
            'classes': ('collapse',)
        }),
        ('Sender Information', {
            'fields': ('from_email', 'from_name', 'reply_to', 'cc', 'bcc'),
            'classes': ('collapse',)
        }),
        ('Error Details', {
            'fields': ('error_message', 'retry_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'sent_at', 'delivered_at', 'opened_at', 'clicked_at')
        }),
        ('Engagement Metrics', {
            'fields': ('opens_count', 'clicks_count')
        }),
        ('Attachments', {
            'fields': ('attachments',),
            'classes': ('collapse',)
        }),
    )
    
    def subject_short(self, obj):
        """Display shortened subject"""
        if len(obj.subject) > 50:
            return obj.subject[:50] + '...'
        return obj.subject
    subject_short.short_description = 'Subject'
    
    def email_type_badge(self, obj):
        """Display email type as a colored badge"""
        colors = {
            'order_confirmation': '#28a745',
            'order_shipped': '#17a2b8',
            'order_delivered': '#28a745',
            'seller_new_order': '#ffc107',
            'signup_welcome': '#007bff',
            'password_reset': '#dc3545',
            'low_stock_alert': '#fd7e14',
            'generic': '#6c757d',
        }
        color = colors.get(obj.email_type, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_email_type_display()
        )
    email_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            'pending': '#ffc107',
            'sent': '#28a745',
            'delivered': '#28a745',
            'failed': '#dc3545',
            'bounced': '#dc3545',
            'complained': '#6c757d',
        }
        icons = {
            'pending': '⏳',
            'sent': '✓',
            'delivered': '✓✓',
            'failed': '✗',
            'bounced': '↩',
            'complained': '⚠',
        }
        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '•')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def user_link(self, obj):
        """Link to related user"""
        if obj.user:
            url = reverse('admin:accounts_customuser_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return '-'
    user_link.short_description = 'User'
    
    def order_link(self, obj):
        """Link to related order"""
        if obj.related_order:
            url = reverse('admin:orders_order_change', args=[obj.related_order.id])
            return format_html('<a href="{}">{}</a>', url, obj.related_order.order_number)
        return '-'
    order_link.short_description = 'Order'
    
    def formatted_response(self, obj):
        """Display formatted JSON response"""
        if obj.resend_response:
            import json
            formatted = json.dumps(obj.resend_response, indent=2)
            return format_html('<pre style="background: #f8f9fa; padding: 10px;">{}</pre>', formatted)
        return '-'
    formatted_response.short_description = "Full API Response"
    
    def html_preview(self, obj):
        """Display HTML content preview"""
        if obj.html_content:
            # Show first 500 characters with HTML rendering
            preview = obj.html_content[:500]
            return format_html(
                '<div style="border: 1px solid #ddd; padding: 10px; max-height: 300px; '
                'overflow-y: scroll;">{}</div>',
                preview
            )
        return '-'
    html_preview.short_description = "HTML Preview"
    
    def get_queryset(self, request):
        """Optimize queries"""
        qs = super().get_queryset(request)
        return qs.select_related('user', 'related_order')
    
    def has_add_permission(self, request):
        """Disable manual creation of email logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup"""
        return request.user.is_superuser
    
    # Add custom admin actions
    actions = ['mark_as_delivered', 'retry_failed']
    
    def mark_as_delivered(self, request, queryset):
        """Mark selected emails as delivered"""
        updated = queryset.filter(status='sent').update(status='delivered')
        self.message_user(request, f'{updated} emails marked as delivered')
    mark_as_delivered.short_description = 'Mark selected as delivered'
    
    def retry_failed(self, request, queryset):
        """Retry failed emails"""
        from .emails import EmailService
        email_service = EmailService()
        
        success_count = 0
        fail_count = 0
        
        for email_log in queryset.filter(status='failed'):
            result = email_service.send_email(
                email_log.recipient,
                email_log.subject,
                email_log.html_content,
                email_log.text_content,
                email_log.email_type,
                email_log.user,
                email_log.related_order
            )
            
            if result['success']:
                success_count += 1
                email_log.retry_count += 1
                email_log.save()
            else:
                fail_count += 1
        
        self.message_user(
            request,
            f'Retry complete: {success_count} successful, {fail_count} failed'
        )
    retry_failed.short_description = 'Retry selected failed emails'
