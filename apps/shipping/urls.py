from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShippingAddressViewSet, ShippingMethodViewSet, ShipmentViewSet, CustomerDeliveryAddressViewSet

router = DefaultRouter()
router.register(r'addresses', ShippingAddressViewSet)
router.register(r'delivery-addresses', CustomerDeliveryAddressViewSet, basename='delivery-address')
router.register(r'methods', ShippingMethodViewSet)
router.register(r'shipments', ShipmentViewSet)

urlpatterns = [
    path('', include(router.urls)),
]