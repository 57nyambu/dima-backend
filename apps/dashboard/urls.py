from django.urls import path
from . import views

app_name = 'apps.dashboard'

urlpatterns = [
    # Seller Dashboard
    path('seller/overview/', views.seller_overview, name='seller-overview'),
    path('seller/sales-stats/', views.seller_sales_stats, name='seller-sales-stats'),
    
    # Admin Dashboard
    path('admin/overview/', views.admin_overview, name='admin-overview'),
    path('admin/platform-stats/', views.admin_platform_stats, name='admin-platform-stats'),
    
    # Admin Management Actions
    path('admin/users/<int:user_id>/manage/', views.admin_manage_user, name='admin-manage-user'),
    path('admin/businesses/<int:business_id>/manage/', views.admin_manage_business, name='admin-manage-business'),
    
    # Buyer Dashboard
    path('buyer/overview/', views.buyer_overview, name='buyer-overview'),
    path('buyer/order-stats/', views.buyer_order_stats, name='buyer-order-stats'),
]
