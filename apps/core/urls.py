from django.urls import path
from .views import DocumentationView, LandingView, ProductDetailView, NewLandingView, NewProductDetailView

app_name = 'apps.core'

urlpatterns = [
    path('', NewLandingView.as_view(), name='landing'),
    path('docs/', DocumentationView.as_view(), name='documentation'),
    path('products/<slug:slug>/', NewProductDetailView.as_view(), name='product_detail'),
]
