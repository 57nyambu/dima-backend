from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BusinessViewSet, PaymentMethodsViewSet, ReviewViewSet

router = DefaultRouter()
router.register(r'businesses', BusinessViewSet, basename='business')
router.register(r'payment-methods', PaymentMethodsViewSet, basename='payment-method')
router.register(r'reviews', ReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
]