from rest_framework import generics, status
from rest_framework.response import Response
from .models import Payment
from .serializers import PaymentSerializer
from .mpesa import MpesaGateway

class InitiatePaymentView(generics.CreateAPIView):
    """Handles payment initiation (including MPesa STK push)"""
    serializer_class = PaymentSerializer

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

class MPesaCallbackView(generics.GenericAPIView):
    """Handles MPesa payment confirmation webhook"""
    def post(self, request, *args, **kwargs):
        data = request.data
        
        # Verify the callback is from Safaricom
        if not self._verify_callback(data):
            return Response(status=status.HTTP_403_FORBIDDEN)
        
        # Update payment status
        try:
            payment = Payment.objects.get(
                mpesa_code=data['TransID'],
                is_confirmed=False
            )
            payment.is_confirmed = True
            payment.save()
            
            # TODO: Send confirmation email/SMS
            return Response(status=status.HTTP_200_OK)
            
        except Payment.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

    def _verify_callback(self, data):
        """Verify callback authenticity (implement proper security checks)"""
        return True  # In production, verify IP and signatures