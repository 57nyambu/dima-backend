from rest_framework import serializers
from .models import Order, OrderItem
from apps.products.serializers import ProductSerializer


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    subtotal = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price', 'subtotal']
        read_only_fields = ['id', 'product', 'price']
    
    def get_subtotal(self, obj):
        return obj.quantity * obj.price


class OrderListSerializer(serializers.ModelSerializer):
    """Serializer for listing orders with basic information"""
    customer_name = serializers.SerializerMethodField()
    delivery_address = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()
    business_name = serializers.CharField(source='business.name', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'business_name', 'status', 'payment_status',
            'total', 'shipping_cost', 'payment_method', 'customer_name',
            'delivery_address', 'item_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order_number', 'created_at', 'updated_at']
    
    def get_customer_name(self, obj):
        return obj.get_customer_name()
    
    def get_delivery_address(self, obj):
        return obj.get_delivery_address()
    
    def get_item_count(self, obj):
        return obj.items.count()


class OrderDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for viewing single order with all information"""
    items = OrderItemSerializer(many=True, read_only=True)
    customer_name = serializers.SerializerMethodField()
    delivery_address = serializers.SerializerMethodField()
    business_name = serializers.CharField(source='business.name', read_only=True)
    business_id = serializers.IntegerField(source='business.id', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'user_email', 'business_id', 'business_name',
            # Customer information
            'customer_first_name', 'customer_last_name', 'customer_name',
            'customer_email', 'customer_phone',
            # Delivery information
            'delivery_county', 'delivery_town', 'delivery_location',
            'delivery_notes', 'delivery_address',
            # Order status
            'status', 'payment_status', 'payment_method',
            # Financial
            'total', 'shipping_cost', 'mpesa_code',
            # Shipping
            'shipping_method', 'tracking_number', 'courier', 'estimated_delivery',
            # Items
            'items',
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order_number', 'user_email', 'business_id', 'business_name',
            'customer_first_name', 'customer_last_name', 'customer_email',
            'customer_phone', 'delivery_county', 'delivery_town',
            'delivery_location', 'delivery_notes', 'total', 'shipping_cost',
            'payment_method', 'mpesa_code', 'items', 'created_at', 'updated_at'
        ]
    
    def get_customer_name(self, obj):
        return obj.get_customer_name()
    
    def get_delivery_address(self, obj):
        return obj.get_delivery_address()


class OrderSerializer(serializers.ModelSerializer):
    """Legacy serializer for backward compatibility"""
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'business', 'status', 'total', 
                  'mpesa_code', 'created_at', 'updated_at', 'items']
        read_only_fields = ['id', 'created_at', 'updated_at']