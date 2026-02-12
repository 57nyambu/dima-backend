from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'sms-logs', views.SMSLogViewSet, basename='sms-log')
router.register(r'email-logs', views.EmailLogViewSet, basename='email-log')

urlpatterns = [
    # Testing endpoints
    path('test-sms/', views.test_sms, name='test-sms'),
    path('test-email/', views.test_email, name='test-email'),
    path('send-order-sms/', views.send_order_sms_notification, name='send-order-sms'),
    
    # Router endpoints (includes SMS & Email logs admin endpoints)
    path('', include(router.urls)),
]
