from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Order
from .serializers import OrderSerializer, OrderListSerializer, OrderDetailSerializer


class IsReadOnlyOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit orders.
    Regular users can only view their own orders.
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        # Write permissions are only allowed to admin users
        return request.user and request.user.is_staff


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing orders.
    - Regular users can only view their own orders (read-only)
    - Staff/Admin users can view and modify all orders
    """
    permission_classes = [IsReadOnlyOrAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['order_number', 'customer_email', 'customer_phone', 'mpesa_code']
    ordering_fields = ['created_at', 'updated_at', 'total']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Filter orders based on user role:
        - Regular users: only their own orders
        - Staff/Admin: all orders
        """
        queryset = Order.objects.select_related('user', 'business').prefetch_related('items__product')
        
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)
    
    def get_serializer_class(self):
        """
        Use different serializers for list and detail views
        """
        if self.action == 'retrieve':
            return OrderDetailSerializer
        elif self.action == 'list':
            return OrderListSerializer
        return OrderSerializer
    
    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """
        Get all orders for the authenticated user
        """
        orders = self.get_queryset().filter(user=request.user)
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """
        Get all pending orders for the authenticated user
        """
        orders = self.get_queryset().filter(user=request.user, status='pending')
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def completed(self, request):
        """
        Get all completed orders for the authenticated user
        """
        orders = self.get_queryset().filter(
            user=request.user,
            status__in=['delivered', 'completed']
        )
        serializer = OrderListSerializer(orders, many=True)
        return Response(serializer.data)