from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.NotificationViewSet, basename='notification')

urlpatterns = [
    path('test-sms/', views.test_sms, name='test-sms'),
    path('send-order-sms/', views.send_order_sms_notification, name='send-order-sms'),
    path('', include(router.urls)),
]
