from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BusinessViewSet, PaymentMethodsViewSet, BusinessReviewViewSet

router = DefaultRouter()
router.register(r'businesses', BusinessViewSet, basename='business')
router.register(r'payment-methods', PaymentMethodsViewSet, basename='payment-method')
router.register(r'business-reviews', BusinessReviewViewSet, basename='business-review')

urlpatterns = [
    path('', include(router.urls)),
]