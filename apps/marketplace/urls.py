# marketplace/urls.py
from django.urls import path, include
from . import views, product_views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()


app_name = 'apps.marketplace'

urlpatterns = [
    # Homepage and Discovery
    path('home/', views.homepage_data, name='homepage'),
    path('categories/', views.get_categories, name='category_list'),
    path('search/', views.search_products, name='product_search'),
    path('search/vendors/', views.search_vendors, name='vendor_search'),
    path('search/suggestions/', views.search_suggestions, name='search_suggestions'),
    
    # Products
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('products/<slug:slug>/', product_views.ProductDetailView.as_view(), name='product_detail'),
    path('api/products/<slug:slug>/', product_views.ProductDetailAPIView.as_view(), name='product_detail_api'),
    
    # Vendors
    path('vendors/', views.VendorListView.as_view(), name='vendor_list'),
    path('vendors/<slug:slug>/', views.VendorDetailView.as_view(), name='vendor_detail'),
    
    # Cart Management (Moved to Frontend)
    # path('cart/', views.CartView.as_view(), name='cart'),
    # path('cart/add/', views.add_to_cart, name='add_to_cart'),
    # path('cart/items/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    # path('cart/items/<int:item_id>/remove/', views.remove_from_cart, name='remove_from_cart'),
    # path('cart/clear/', views.clear_cart, name='clear_cart'),
    
    # Checkout (Keep these active as they require server-side processing)
    path('checkout/', views.checkout_session, name='checkout_session'),
    path('checkout/process/', views.process_checkout, name='process_checkout'),
    
    # Wishlist (Moved to Frontend)
    # path('wishlist/', views.WishlistView.as_view(), name='wishlist'),
    # path('wishlist/add/', views.add_to_wishlist, name='add_to_wishlist'),
    # path('wishlist/remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Orders
    path('orders/', views.OrderListView.as_view(), name='order_list'),
    path('orders/<int:pk>/', views.OrderDetailView.as_view(), name='order_detail'),
    
    # Product Comparison (Moved to Frontend)
    # path('comparisons/', views.ProductComparisonListView.as_view(), name='comparison_list'),
    # path('comparisons/add/', views.add_to_comparison, name='add_to_comparison'),
    
    # Disputes
    path('disputes/', views.DisputeListCreateView.as_view(), name='dispute_list'),
    path('disputes/<uuid:pk>/', views.DisputeDetailView.as_view(), name='dispute_detail'),
    
    # Notifications
    path('notifications/', views.NotificationListView.as_view(), name='notification_list'),
    path('notifications/mark-read/', views.mark_notifications_read, name='mark_notifications_read'),
    
    # Analytics (for vendors)
    path('analytics/vendor/', views.vendor_analytics, name='vendor_analytics'),
    
    # Banners
    path('banners/create/', views.BannerCreateView.as_view(), name='banner_create'),
]