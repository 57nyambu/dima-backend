from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from .sms import SMSService
from .models import Notification
from .serializers import NotificationSerializer
import logging

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing user notifications
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer
    
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
