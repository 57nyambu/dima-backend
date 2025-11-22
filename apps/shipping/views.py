from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import ShippingAddress, ShippingMethod, Shipment, CustomerDeliveryAddress
from .serializers import ShippingAddressSerializer, ShippingMethodSerializer, ShipmentSerializer, CustomerDeliveryAddressSerializer


class CustomerDeliveryAddressViewSet(viewsets.ModelViewSet):
    """ViewSet for managing customer delivery addresses"""
    serializer_class = CustomerDeliveryAddressSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return only addresses for the authenticated user"""
        return CustomerDeliveryAddress.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Automatically set the user when creating an address"""
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this address as the default"""
        address = self.get_object()
        
        # Unset all other defaults
        CustomerDeliveryAddress.objects.filter(user=request.user, is_default=True).update(is_default=False)
        
        # Set this one as default
        address.is_default = True
        address.save()
        
        serializer = self.get_serializer(address)
        return Response({
            'success': True,
            'message': 'Default address updated',
            'data': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def get_default(self, request):
        """Get the default delivery address"""
        try:
            default_address = CustomerDeliveryAddress.objects.get(user=request.user, is_default=True)
            serializer = self.get_serializer(default_address)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        except CustomerDeliveryAddress.DoesNotExist:
            return Response({
                'success': False,
                'message': 'No default address found'
            }, status=status.HTTP_404_NOT_FOUND)


class ShippingAddressViewSet(viewsets.ModelViewSet):
    queryset = ShippingAddress.objects.all()
    serializer_class = ShippingAddressSerializer

class ShippingMethodViewSet(viewsets.ModelViewSet):
    queryset = ShippingMethod.objects.all()
    serializer_class = ShippingMethodSerializer

class ShipmentViewSet(viewsets.ModelViewSet):
    queryset = Shipment.objects.all()
    serializer_class = ShipmentSerializer