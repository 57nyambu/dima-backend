from rest_framework import viewsets, permissions, status, filters, serializers as drf_serializers
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.db.models import Q, Count
from drf_spectacular.utils import extend_schema, inline_serializer
from .sms import SMSService
from .emails import EmailService
from .models import Notification, SMSLog, EmailLog
from .serializers import (
    NotificationSerializer, SMSLogSerializer, SMSLogDetailSerializer,
    SMSStatsSerializer, SMSResendSerializer,
    EmailLogSerializer, EmailLogDetailSerializer,
    EmailStatsSerializer, EmailResendSerializer
)
import logging

logger = logging.getLogger(__name__)


class SMSLogPagination(PageNumberPagination):
    """Pagination for SMS logs"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing user notifications
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    
    def get_queryset(self):
        """
        Return notifications for the authenticated user
        """
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        Mark all notifications as read
        """
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'All notifications marked as read'})
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Mark a specific notification as read
        """
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'Notification marked as read'})


class SMSLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin ViewSet for viewing all SMS logs
    """
    permission_classes = [permissions.IsAdminUser]
    pagination_class = SMSLogPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['recipient', 'message', 'message_type']
    ordering_fields = ['created_at', 'status', 'message_type']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SMSLogDetailSerializer
        return SMSLogSerializer
    
    def get_queryset(self):
        queryset = SMSLog.objects.select_related('user', 'related_order').all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by message type
        message_type = self.request.query_params.get('message_type')
        if message_type:
            queryset = queryset.filter(message_type=message_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Filter by recipient
        recipient = self.request.query_params.get('recipient')
        if recipient:
            queryset = queryset.filter(recipient__icontains=recipient)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get SMS statistics
        Query params: ?days=30 (default)
        """
        days = int(request.query_params.get('days', 30))
        stats = SMSLog.get_stats(days=days)
        
        serializer = SMSStatsSerializer(stats)
        return Response({
            'success': True,
            'days': days,
            'stats': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """
        Get SMS count breakdown by message type
        """
        stats = SMSLog.objects.values('message_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'success': True,
            'breakdown': list(stats)
        })
    
    @action(detail=False, methods=['get'])
    def failed(self, request):
        """
        Get all failed SMS logs
        """
        failed_sms = SMSLog.objects.filter(status='failed').order_by('-created_at')[:100]
        serializer = self.get_serializer(failed_sms, many=True)
        
        return Response({
            'success': True,
            'count': failed_sms.count(),
            'logs': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """
        Resend a failed SMS
        """
        sms_log = self.get_object()
        
        if sms_log.status in ['sent', 'delivered']:
            return Response({
                'success': False,
                'error': 'SMS was already sent successfully'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            sms_service = SMSService()
            result = sms_service.send_sms(
                sms_log.recipient,
                sms_log.message,
                sms_log.message_type,
                sms_log.user,
                sms_log.related_order
            )
            
            if result['success']:
                # The new log is created automatically, mark old one as superseded
                sms_log.retry_count += 1
                sms_log.error_message = 'Superseded by retry'
                sms_log.save()
                
                return Response({
                    'success': True,
                    'message': 'SMS resent successfully',
                    'new_log_id': result['sms_log'].id
                })
            else:
                sms_log.retry_count += 1
                sms_log.save()
                
                return Response({
                    'success': False,
                    'error': result.get('error', 'Failed to resend SMS')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Failed to resend SMS: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    request=inline_serializer(
        name='TestSMSRequest',
        fields={
            'phone_number': drf_serializers.CharField(),
            'message': drf_serializers.CharField(required=False),
        },
    ),
    responses=inline_serializer(
        name='TestSMSResponse',
        fields={
            'success': drf_serializers.BooleanField(),
            'message': drf_serializers.CharField(),
        },
    ),
    description='Test endpoint for sending SMS (Admin only)',
)
@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def test_sms(request):
    """
    Test endpoint for sending SMS (Admin only)
    
    POST /api/notifications/test-sms/
    Body: {
        "phone_number": "+254712345678",
        "message": "Test message"
    }
    """
    try:
        phone_number = request.data.get('phone_number')
        message = request.data.get('message', 'This is a test SMS from Dima.')
        
        if not phone_number:
            return Response(
                {'error': 'phone_number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate phone number format
        if not phone_number.startswith('+254') and not phone_number.startswith('+'):
            return Response(
                {'error': 'Phone number must start with + (e.g., +254712345678)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Send SMS
        sms_service = SMSService()
        result = sms_service.send_sms(phone_number, message)
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'SMS sent successfully',
                'details': result.get('message_data', {}),
                'recipients': result.get('recipients', [])
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': result.get('error', 'Unknown error'),
                'details': result
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Test SMS failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    request=inline_serializer(
        name='SendOrderSMSRequest',
        fields={
            'order_id': drf_serializers.IntegerField(),
            'phone_number': drf_serializers.CharField(required=False),
            'message_type': drf_serializers.CharField(required=False),
        },
    ),
    responses=inline_serializer(
        name='SendOrderSMSResponse',
        fields={
            'success': drf_serializers.BooleanField(),
            'message': drf_serializers.CharField(),
        },
    ),
    description='Send SMS notification for an order',
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_order_sms_notification(request):
    """
    Send SMS notification for an order (for testing or manual triggers)
    
    POST /api/notifications/send-order-sms/
    Body: {
        "order_id": 123,
        "phone_number": "+254712345678",
        "message_type": "confirmation"  // or "shipped", "delivered"
    }
    """
    try:
        from apps.orders.models import Order
        
        order_id = request.data.get('order_id')
        phone_number = request.data.get('phone_number')
        message_type = request.data.get('message_type', 'confirmation')
        
        if not order_id:
            return Response(
                {'error': 'order_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Use order's phone number if not provided
        phone_number = phone_number or order.customer_phone
        
        if not phone_number:
            return Response(
                {'error': 'No phone number available'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate message based on type
        if message_type == 'confirmation':
            message = (
                f"Order confirmed! Your order #{order.order_number} "
                f"from {order.business.name} for KES {order.total:.2f} "
                f"has been received."
            )
        elif message_type == 'shipped':
            message = f"Your order #{order.order_number} has been shipped!"
            if order.tracking_number:
                message += f" Tracking: {order.tracking_number}"
        elif message_type == 'delivered':
            message = f"Your order #{order.order_number} has been delivered. Enjoy!"
        else:
            message = request.data.get('custom_message', f"Order #{order.order_number} update")
        
        # Send SMS
        sms_service = SMSService()
        result = sms_service.send_sms(phone_number, message)
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'SMS sent successfully',
                'order_number': order.order_number,
                'details': result.get('message_data', {})
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Order SMS notification failed: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class EmailLogPagination(PageNumberPagination):
    """Pagination for Email logs"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin ViewSet for viewing all Email logs
    """
    permission_classes = [permissions.IsAdminUser]
    pagination_class = EmailLogPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['recipient', 'subject', 'email_type']
    ordering_fields = ['created_at', 'status', 'email_type']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EmailLogDetailSerializer
        return EmailLogSerializer
    
    def get_queryset(self):
        queryset = EmailLog.objects.select_related('user', 'related_order').all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by email type
        email_type = self.request.query_params.get('email_type')
        if email_type:
            queryset = queryset.filter(email_type=email_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Filter by recipient
        recipient = self.request.query_params.get('recipient')
        if recipient:
            queryset = queryset.filter(recipient__icontains=recipient)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get Email statistics
        Query params: ?days=30 (default)
        """
        days = int(request.query_params.get('days', 30))
        stats = EmailLog.get_stats(days=days)
        
        serializer = EmailStatsSerializer(stats)
        return Response({
            'success': True,
            'period_days': days,
            'stats': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """
        Get email count breakdown by type
        """
        type_counts = EmailLog.objects.values('email_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'success': True,
            'data': {item['email_type']: item['count'] for item in type_counts}
        })
    
    @action(detail=False, methods=['get'])
    def failed(self, request):
        """
        Get all failed emails with pagination
        """
        failed_logs = self.get_queryset().filter(status='failed')
        page = self.paginate_queryset(failed_logs)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(failed_logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """
        Resend a failed email
        """
        email_log = self.get_object()
        
        if email_log.status in ['sent', 'delivered']:
            return Response({
                'success': False,
                'error': 'Email was already sent successfully'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            email_service = EmailService()
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
                # The new log is created automatically, mark old one as superseded
                email_log.retry_count += 1
                email_log.error_message = 'Superseded by retry'
                email_log.save()
                
                return Response({
                    'success': True,
                    'message': 'Email resent successfully',
                    'new_log_id': result['email_log'].id
                })
            else:
                email_log.retry_count += 1
                email_log.error_message = result.get('error', 'Resend failed')
                email_log.save()
                
                return Response({
                    'success': False,
                    'error': result.get('error', 'Failed to resend Email')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            logger.error(f"Failed to resend Email: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    request=inline_serializer(
        name='TestEmailRequest',
        fields={
            'recipient': drf_serializers.EmailField(),
            'subject': drf_serializers.CharField(required=False),
            'message': drf_serializers.CharField(required=False),
        },
    ),
    responses=inline_serializer(
        name='TestEmailResponse',
        fields={
            'success': drf_serializers.BooleanField(),
            'message': drf_serializers.CharField(),
        },
    ),
    description='Test endpoint for sending emails (Admin only)',
)
@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def test_email(request):
    """
    Test endpoint for sending emails (Admin only)
    
    POST /api/notifications/test-email/
    Body: {
        "recipient": "test@example.com",
        "subject": "Test Email",
        "message": "Test message"
    }
    """
    try:
        recipient = request.data.get('recipient')
        subject = request.data.get('subject', 'Test Email from Dima')
        message = request.data.get('message', 'This is a test email.')
        
        if not recipient:
            return Response({
                'success': False,
                'error': 'Recipient email address is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Send test email
        email_service = EmailService()
        result = email_service.send_generic_email(
            recipient=recipient,
            subject=subject,
            message=message,
            user=request.user
        )
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'Test email sent successfully',
                'email_log_id': result['email_log'].id,
                'resend_id': result.get('response', {}).get('id')
            })
        else:
            return Response({
                'success': False,
                'error': result.get('error', 'Failed to send email')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
    except Exception as e:
        logger.error(f"Test email failed: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
