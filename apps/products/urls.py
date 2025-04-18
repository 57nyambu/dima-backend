from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, ProductImageViewSet, CategoryImageViewSet

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('products', ProductViewSet, basename='product')
router.register('product-images', ProductImageViewSet, basename='product-image')
router.register('category-images', CategoryImageViewSet, basename='category-image')

app_name = 'api'

urlpatterns = [
    path('', include(router.urls)),
]