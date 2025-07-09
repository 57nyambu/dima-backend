from rest_framework import serializers
from .models import Business, PaymentMethod, BusinessReview

class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['type', 'till_number', 'business_number', 
                  'paybill_account_number', 'bank_account_number', 
                  'bank_name', 'card_number']
        extra_kwargs = {
            'till_number': {'required': False},
            'business_number': {'required': False},
            'paybill_account_number': {'required': False},
            'bank_account_number': {'required': False},
            'bank_name': {'required': False},
            'card_number': {'required': False}
        }

    def validate(self, data):
        payment_type = data.get('type')
        
        if payment_type == 'mpesa_till' and not data.get('till_number'):
            raise serializers.ValidationError(
                {"till_number": "Till number is required for M-Pesa Till."}
            )
        
        elif payment_type == 'mpesa_paybill':
            if not data.get('business_number') or not data.get('paybill_account_number'):
                raise serializers.ValidationError(
                    "Paybill and account number are required for M-Pesa Paybill."
                )
        
        elif payment_type == 'bank_transfer':
            if not data.get('bank_name') or not data.get('bank_account_number'):
                raise serializers.ValidationError(
                    "Bank name and account number are required for bank transfers."
                )
        
        elif payment_type == 'card' and not data.get('card_number'):
            raise serializers.ValidationError(
                {"card_number": "Card number is required for card payment."}
            )
        
        return data

class BusinessSerializer(serializers.ModelSerializer):
    payment_methods = PaymentMethodSerializer(many=True, required=False)

    class Meta:
        model = Business
        fields = [
            'id', 'owner', 'name', 'slug', 'business_type', 
            'description', 'kra_pin', 'business_reg_no', 
            'is_verified', 'created_at', 'updated_at', 
            'payment_methods', 'verification_status', 'verified_at'
        ]
        read_only_fields = [
            'slug', 'is_verified', 'created_at', 'updated_at', 
            'owner', 'verification_status', 'verified_at'
        ]

    def create(self, validated_data):
        # Extract payment methods if provided
        payment_methods_data = validated_data.pop('payment_methods', [])
        
        # Set the owner to the currently logged-in user
        validated_data['owner'] = self.context['request'].user
        
        # Create the business
        business = Business.objects.create(**validated_data)
        
        # Create associated payment methods
        for method_data in payment_methods_data:
            PaymentMethod.objects.create(business=business, **method_data)
        
        return business

    def update(self, instance, validated_data):
        # Handle payment methods during update
        payment_methods_data = validated_data.pop('payment_methods', None)
        
        # Update business fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # If payment methods are provided, update them
        if payment_methods_data is not None:
            # Remove existing payment methods
            instance.payment_methods.all().delete()
            
            # Create new payment methods
            for method_data in payment_methods_data:
                PaymentMethod.objects.create(business=instance, **method_data)
        
        return instance

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessReview
        fields = ['id', 'product', 'user', 'rating', 'comment', 'mpesa_code', 'created_at', '']
        read_only_fields = ['user', 'created_at']

    def create(self, validated_data):
        # Automatically set the user to the currently logged-in user
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value