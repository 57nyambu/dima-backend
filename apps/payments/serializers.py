from rest_framework import serializers
from .models import Payment
from orders.models import Order
from serializers import PhoneNumberField


class PaymentSerializer(serializers.ModelSerializer):
    """Handles payment creation and validation"""
    mpesa_phone = PhoneNumberField(region='KE', required=False)
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'order',
            'amount',
            'method',
            'mpesa_phone',  # Only required for MPesa payments
            'mpesa_code',   # Auto-filled from callback
            'is_confirmed',
            'is_settled',
            'created_at'
        ]
        read_only_fields = [
            'id',
            'mpesa_code',
            'is_confirmed',
            'is_settled',
            'created_at'
        ]
        extra_kwargs = {
            'amount': {'required': False}  # Auto-calculated from order
        }

    def validate(self, data):
        """Custom validation for payment methods"""
        order = data.get('order')
        method = data.get('method')
        
        # Auto-set amount from order if not provided
        if not data.get('amount') and order:
            data['amount'] = order.total_amount
        
        # MPesa-specific validation
        if method == Payment.MPESA:
            if not data.get('mpesa_phone'):
                raise serializers.ValidationError(
                    "MPesa phone number is required for MPesa payments"
                )
            
            # Format phone to Safaricom standard (254...)
            phone = str(data['mpesa_phone'])
            if not phone.startswith('254'):
                if phone.startswith('0'):
                    phone = '254' + phone[1:]
                elif phone.startswith('+254'):
                    phone = phone[1:]
                data['mpesa_phone'] = phone
        
        # Cash on Delivery validation
        elif method == Payment.CASH:
            if not order.business.allows_cod:
                raise serializers.ValidationError(
                    "This business does not accept Cash on Delivery"
                )
        
        return data

    def to_representation(self, instance):
        """Custom representation for API responses"""
        ret = super().to_representation(instance)
        
        # Add order details for better frontend handling
        ret['order'] = {
            'id': instance.order.id,
            'status': instance.order.status,
            'business': {
                'id': instance.order.business.id,
                'name': instance.order.business.name
            }
        }
        
        # Hide sensitive fields if payment isn't confirmed
        if not instance.is_confirmed:
            ret.pop('mpesa_code', None)
        
        return ret