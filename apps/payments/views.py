from rest_framework import generics, status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, inline_serializer
import logging

from .models import Payment, PaymentSettlement
from .serializers import PaymentSerializer
from .mpesa import MpesaGateway, initiate_stk_push
from apps.orders.models import Order

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing payments with full CRUD operations.
    
    Endpoints:
    - GET /payments/ - List all user's payments
    - POST /payments/ - Create new payment (initiate)
    - GET /payments/{id}/ - Get specific payment details
    - POST /payments/{id}/verify/ - Verify payment status
    - POST /payments/{id}/refund/ - Request payment refund
    - POST /payments/mpesa-stk-push/ - Initiate MPesa STK push
    - GET /payments/by-order/{order_id}/ - Get payment by order ID
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    queryset = Payment.objects.all()
    
    def get_queryset(self):
        """Filter payments based on user role"""
        user = self.request.user
        
        if user.is_staff or user.is_superuser:
            # Admin can see all payments
            return Payment.objects.all().select_related('order', 'order__business')
        
        # Regular users see only their payments
        return Payment.objects.filter(
            order__buyer=user
        ).select_related('order', 'order__business')
    
    def create(self, request, *args, **kwargs):
        """
        Initiate a payment for an order.
        
        Request body:
        {
            "order": <order_id>,
            "method": "mpesa|airtel|paypal|cod|card",
            "mpesa_phone": "254722123456" (required for mpesa),
            "amount": 1000.00 (optional, auto-calculated from order)
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order = serializer.validated_data['order']
        payment_method = serializer.validated_data['method']
        
        # Check if order already has a payment
        if hasattr(order, 'payment'):
            return Response({
                "error": "Payment already exists for this order",
                "payment_id": order.payment.id
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # For MPesa payments - initiate STK push
        if payment_method == Payment.MPESA:
            mpesa_phone = serializer.validated_data.get('mpesa_phone')
            
            if not mpesa_phone:
                return Response({
                    "error": "MPesa phone number is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            logger.info(f"Initiating MPesa payment for Order {order.id}")
            
            response = initiate_stk_push(
                phone_number=mpesa_phone,
                amount=order.total_amount,
                account_reference=f"ORDER-{order.id}",
                transaction_desc=f"Payment for Order {order.id}"
            )
            
            if response.get('success'):
                # Save payment as pending
                payment = serializer.save(is_confirmed=False)
                
                return Response({
                    "success": True,
                    "message": "MPesa payment request sent to your phone",
                    "payment_id": payment.id,
                    "checkout_request_id": response.get('CheckoutRequestID'),
                    "merchant_request_id": response.get('MerchantRequestID'),
                    "customer_message": response.get('CustomerMessage', 'Please check your phone and enter PIN')
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    "success": False,
                    "error": response.get('errorMessage', 'Failed to initiate MPesa payment'),
                    "error_code": response.get('errorCode')
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # For Airtel Money payments
        elif payment_method == Payment.AIRTEL:
            airtel_phone = request.data.get('airtel_phone')
            
            if not airtel_phone:
                return Response({
                    "error": "Airtel phone number is required"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # TODO: Implement Airtel Money API integration
            payment = serializer.save(is_confirmed=False)
            
            return Response({
                "success": True,
                "message": "Airtel Money payment initiated",
                "payment_id": payment.id,
                "note": "Please complete payment via Airtel Money"
            }, status=status.HTTP_201_CREATED)
        
        # For Cash on Delivery
        elif payment_method == Payment.COD:
            # Verify business accepts COD
            if not hasattr(order.business, 'allows_cod') or not order.business.allows_cod:
                return Response({
                    "error": "This business does not accept Cash on Delivery"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # COD payments are auto-confirmed
            payment = serializer.save(is_confirmed=True)
            
            return Response({
                "success": True,
                "message": "Cash on Delivery payment confirmed",
                "payment_id": payment.id,
                "note": "Please have cash ready upon delivery"
            }, status=status.HTTP_201_CREATED)
        
        # For other payment methods (PayPal, Card, etc.)
        else:
            payment = serializer.save(is_confirmed=False)
            
            return Response({
                "success": True,
                "message": f"{payment_method.upper()} payment initiated",
                "payment_id": payment.id
            }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], url_path='verify')
    def verify_payment(self, request, pk=None):
        """
        Verify payment status.
        
        POST /payments/{id}/verify/
        """
        payment = self.get_object()
        
        if payment.is_confirmed:
            return Response({
                "verified": True,
                "message": "Payment already confirmed",
                "payment": PaymentSerializer(payment).data
            })
        
        # For MPesa, you could query the transaction status
        if payment.method == Payment.MPESA:
            # TODO: Implement MPesa query API
            return Response({
                "verified": False,
                "message": "Payment verification in progress",
                "note": "Please complete the payment on your phone"
            })
        
        return Response({
            "verified": payment.is_confirmed,
            "payment": PaymentSerializer(payment).data
        })
    
    @action(detail=True, methods=['post'], url_path='confirm')
    def confirm_payment(self, request, pk=None):
        """
        Manually confirm a payment (admin only).
        
        POST /payments/{id}/confirm/
        Body: {
            "mpesa_code": "NLJ7RT56" (optional)
        }
        """
        if not request.user.is_staff:
            return Response({
                "error": "Only staff can manually confirm payments"
            }, status=status.HTTP_403_FORBIDDEN)
        
        payment = self.get_object()
        
        if payment.is_confirmed:
            return Response({
                "message": "Payment already confirmed"
            })
        
        # Update payment
        payment.is_confirmed = True
        
        if 'mpesa_code' in request.data:
            payment.mpesa_code = request.data['mpesa_code']
        
        payment.save()
        
        # Update order status
        order = payment.order
        if order.status == 'pending_payment':
            order.status = 'confirmed'
            order.save()
        
        return Response({
            "success": True,
            "message": "Payment confirmed successfully",
            "payment": PaymentSerializer(payment).data
        })
    
    @action(detail=True, methods=['post'], url_path='refund')
    def refund_payment(self, request, pk=None):
        """
        Request a payment refund.
        
        POST /payments/{id}/refund/
        Body: {
            "reason": "Product not received"
        }
        """
        payment = self.get_object()
        
        if not payment.is_confirmed:
            return Response({
                "error": "Cannot refund unconfirmed payment"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if payment.order.status == 'refunded':
            return Response({
                "error": "Payment already refunded"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        reason = request.data.get('reason', 'Customer requested refund')
        
        # TODO: Implement actual refund logic
        # For now, just mark the order
        order = payment.order
        order.status = 'refund_requested'
        order.save()
        
        logger.info(f"Refund requested for Payment {payment.id}: {reason}")
        
        return Response({
            "success": True,
            "message": "Refund request submitted",
            "note": "Your refund will be processed within 5-7 business days"
        })
    
    @action(detail=False, methods=['post'], url_path='mpesa-stk-push')
    def mpesa_stk_push(self, request):
        """
        Direct MPesa STK push endpoint.
        
        POST /payments/mpesa-stk-push/
        Body: {
            "phone_number": "254722123456",
            "amount": 1000,
            "order_id": 123,
            "description": "Payment for Order 123"
        }
        """
        phone_number = request.data.get('phone_number')
        amount = request.data.get('amount')
        order_id = request.data.get('order_id')
        description = request.data.get('description', 'Payment')
        
        if not all([phone_number, amount, order_id]):
            return Response({
                "error": "phone_number, amount, and order_id are required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify order exists
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({
                "error": f"Order {order_id} not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        response = initiate_stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=f"ORDER-{order_id}",
            transaction_desc=description
        )
        
        if response.get('success'):
            return Response({
                "success": True,
                "message": response.get('ResponseDescription', 'STK push sent'),
                "checkout_request_id": response.get('CheckoutRequestID'),
                "customer_message": response.get('CustomerMessage')
            })
        else:
            return Response({
                "success": False,
                "error": response.get('errorMessage'),
                "error_code": response.get('errorCode')
            }, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], url_path='by-order/(?P<order_id>[0-9]+)')
    def get_by_order(self, request, order_id=None):
        """
        Get payment by order ID.
        
        GET /payments/by-order/{order_id}/
        """
        try:
            order = Order.objects.get(id=order_id)
            payment = get_object_or_404(Payment, order=order)
            
            # Check permission
            if not (request.user.is_staff or payment.order.buyer == request.user):
                return Response({
                    "error": "Permission denied"
                }, status=status.HTTP_403_FORBIDDEN)
            
            return Response(PaymentSerializer(payment).data)
        except Order.DoesNotExist:
            return Response({
                "error": f"Order {order_id} not found"
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'], url_path='admin/status', permission_classes=[IsAdminUser])
    def payment_status(self, request):
        """
        Admin endpoint to view payment status overview.
        
        GET /payments/admin/status/
        Query params:
        - status: filter by status (pending/succeeded/failed)
        - method: filter by payment method
        - date_from: filter from date (YYYY-MM-DD)
        - date_to: filter to date (YYYY-MM-DD)
        """
        payments = Payment.objects.select_related('order', 'order__business', 'order__buyer').all()
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter == 'succeeded':
            payments = payments.filter(is_confirmed=True)
        elif status_filter == 'pending':
            payments = payments.filter(is_confirmed=False, order__status__in=['pending', 'pending_payment'])
        elif status_filter == 'failed':
            payments = payments.filter(is_confirmed=False, order__status='cancelled')
        
        method_filter = request.query_params.get('method')
        if method_filter:
            payments = payments.filter(method=method_filter)
        
        date_from = request.query_params.get('date_from')
        if date_from:
            payments = payments.filter(created_at__gte=date_from)
        
        date_to = request.query_params.get('date_to')
        if date_to:
            payments = payments.filter(created_at__lte=date_to)
        
        # Get statistics
        stats = {
            'total_payments': payments.count(),
            'succeeded': payments.filter(is_confirmed=True).count(),
            'pending': payments.filter(is_confirmed=False, order__status__in=['pending', 'pending_payment']).count(),
            'failed': payments.filter(is_confirmed=False, order__status='cancelled').count(),
            'by_method': {
                'mpesa': payments.filter(method=Payment.MPESA).count(),
                'airtel': payments.filter(method=Payment.AIRTEL).count(),
                'cod': payments.filter(method=Payment.COD).count(),
                'paypal': payments.filter(method=Payment.PAYPAL).count(),
                'card': payments.filter(method=Payment.CARD).count(),
            },
            'total_amount': sum(p.amount for p in payments),
            'confirmed_amount': sum(p.amount for p in payments if p.is_confirmed),
            'pending_amount': sum(p.amount for p in payments.filter(is_confirmed=False, order__status__in=['pending', 'pending_payment'])),
        }
        
        # Paginate results
        page = self.paginate_queryset(payments)
        if page is not None:
            serializer = PaymentSerializer(page, many=True)
            response_data = self.get_paginated_response(serializer.data)
            response_data.data['statistics'] = stats
            return response_data
        
        serializer = PaymentSerializer(payments, many=True)
        return Response({
            'statistics': stats,
            'payments': serializer.data
        })


class InitiatePaymentView(generics.CreateAPIView):
    """
    Legacy endpoint - Handles payment initiation (including MPesa STK push).
    Kept for backward compatibility.
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        order = serializer.validated_data['order']
        
        # For MPesa payments
        if serializer.validated_data['method'] == Payment.MPESA:
            mpesa = MpesaGateway()
            response = mpesa.stk_push(
                phone=serializer.validated_data['mpesa_phone'],
                amount=order.total_amount,
                order_id=order.id,
                description=f"Payment for Order #{order.id}"
            )
            
            if 'ResponseCode' in response and response['ResponseCode'] == "0":
                payment = serializer.save(is_confirmed=False)
                return Response({
                    "message": "MPesa payment request sent",
                    "checkout_request_id": response['CheckoutRequestID']
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {"error": "MPesa request failed"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # For other payment methods
        payment = serializer.save(is_confirmed=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(
    request=inline_serializer(
        name='MPesaCallbackRequest',
        fields={'Body': drf_serializers.DictField()},
    ),
    responses=inline_serializer(
        name='MPesaCallbackViewResponse',
        fields={
            'ResultCode': drf_serializers.IntegerField(),
            'ResultDesc': drf_serializers.CharField(),
        },
    ),
    description='Handles MPesa payment confirmation webhook from Safaricom',
)
class MPesaCallbackView(generics.GenericAPIView):
    """
    Handles MPesa payment confirmation webhook from Safaricom.
    This endpoint should be publicly accessible (no authentication).
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        """
        POST /payments/mpesa-callback/
        
        Receives callback from Safaricom when payment is completed.
        """
        data = request.data
        logger.info(f"MPesa callback received: {data}")
        
        # Verify the callback is from Safaricom
        if not self._verify_callback(data):
            logger.warning("MPesa callback verification failed")
            return Response(status=status.HTTP_403_FORBIDDEN)
        
        try:
            # Extract transaction details from callback
            result_code = data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
            result_desc = data.get('Body', {}).get('stkCallback', {}).get('ResultDesc')
            checkout_request_id = data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
            
            if result_code == 0:
                # Payment successful
                callback_metadata = data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
                
                # Extract payment details
                mpesa_receipt = None
                phone_number = None
                amount = None
                
                for item in callback_metadata:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        mpesa_receipt = item.get('Value')
                    elif item.get('Name') == 'PhoneNumber':
                        phone_number = item.get('Value')
                    elif item.get('Name') == 'Amount':
                        amount = item.get('Value')
                
                # Find and update payment
                # Note: You may need to store CheckoutRequestID when creating payment
                # For now, find by phone and amount
                payment = Payment.objects.filter(
                    method=Payment.MPESA,
                    is_confirmed=False,
                    mpesa_phone=phone_number,
                    amount=amount
                ).first()
                
                if payment:
                    payment.is_confirmed = True
                    payment.mpesa_code = mpesa_receipt
                    payment.save()
                    
                    # Update order status
                    order = payment.order
                    if order.status == 'pending_payment':
                        order.status = 'confirmed'
                        order.save()
                    
                    logger.info(f"Payment {payment.id} confirmed with MPesa code {mpesa_receipt}")
                else:
                    logger.warning(f"Payment not found for MPesa callback: phone={phone_number}, amount={amount}")
            
            else:
                # Payment failed
                logger.warning(f"MPesa payment failed: {result_desc}")
            
            return Response({"ResultCode": 0, "ResultDesc": "Success"}, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error processing MPesa callback: {str(e)}", exc_info=True)
            return Response({"ResultCode": 1, "ResultDesc": "Failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _verify_callback(self, data):
        """
        Verify callback authenticity.
        In production, implement proper security:
        - Verify IP address is from Safaricom
        - Verify signature/hash if provided
        - Check timestamp
        """
        # TODO: Implement proper verification
        return True  # For now, accept all callbacks