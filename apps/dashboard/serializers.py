from rest_framework import serializers
from apps.orders.models import Order
from apps.products.models import Product
from apps.accounts.models import CustomUser
from apps.business.models import Business


class DashboardStatsSerializer(serializers.Serializer):
    """Base serializer for dashboard statistics"""
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    pending_orders = serializers.IntegerField()
    completed_orders = serializers.IntegerField()


class SellerDashboardSerializer(DashboardStatsSerializer):
    """Seller dashboard overview data"""
    total_products = serializers.IntegerField()
    active_products = serializers.IntegerField()
    out_of_stock = serializers.IntegerField()
    recent_orders = serializers.ListField()
    top_products = serializers.ListField()
    revenue_trend = serializers.ListField()
    payment_breakdown = serializers.DictField()
    financial_summary = serializers.DictField()


class AdminDashboardSerializer(serializers.Serializer):
    """Admin dashboard overview data"""
    total_users = serializers.IntegerField()
    total_sellers = serializers.IntegerField()
    total_buyers = serializers.IntegerField()
    total_businesses = serializers.IntegerField()
    total_products = serializers.IntegerField()
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending_orders = serializers.IntegerField()
    recent_users = serializers.ListField()
    recent_orders = serializers.ListField()
    revenue_trend = serializers.ListField()
    top_selling_products = serializers.ListField()
    user_analytics = serializers.DictField()
    payment_analytics = serializers.DictField()
    business_analytics = serializers.DictField()


class BuyerDashboardSerializer(serializers.Serializer):
    """Buyer dashboard overview data"""
    total_orders = serializers.IntegerField()
    pending_orders = serializers.IntegerField()
    completed_orders = serializers.IntegerField()
    cancelled_orders = serializers.IntegerField()
    total_spent = serializers.DecimalField(max_digits=10, decimal_places=2)
    recent_orders = serializers.ListField()
    favorite_categories = serializers.ListField()


class RevenueChartSerializer(serializers.Serializer):
    """Revenue chart data"""
    date = serializers.DateField()
    revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    orders = serializers.IntegerField()


class TopProductSerializer(serializers.Serializer):
    """Top selling product data"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    sales_count = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    image = serializers.CharField(allow_null=True)
