from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import Product_ImageViewSet, ProductImageViewSet, Category_ImageViewSet

router = DefaultRouter()
router.register('products', Product_ImageViewSet, basename='product')
router.register('product-images', ProductImageViewSet, basename='product-image')
router.register('category-images', Category_ImageViewSet, basename='category-image')

app_name = 'api'

urlpatterns = [
    path('', include(router.urls)),
]