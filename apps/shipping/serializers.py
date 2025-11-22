from rest_framework import serializers
from .models import ShippingAddress, ShippingMethod, Shipment, CustomerDeliveryAddress

class CustomerDeliveryAddressSerializer(serializers.ModelSerializer):
    """Serializer for customer's saved delivery addresses"""
    class Meta:
        model = CustomerDeliveryAddress
        fields = ['id', 'county', 'town', 'specific_location', 'delivery_notes', 'is_default', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Ensure at least one address is default if this is the user's first address"""
        user = self.context.get('request').user if self.context.get('request') else None
        
        if user and not self.instance:  # Creating new address
            existing_addresses = CustomerDeliveryAddress.objects.filter(user=user).exists()
            if not existing_addresses:
                data['is_default'] = True
        
        return data


class ShippingAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingAddress
        fields = '__all__'

class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = '__all__'

class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = '__all__'