from django.views.generic import DetailView
from django.shortcuts import get_object_or_404
from django.db import models
from apps.products.models import Product
from django.db.models import Prefetch
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny
from apps.products.serializers import ProductDetailsSerializer

class ProductDetailView(DetailView):
    model = Product
    template_name = 'marketplace/product_detail.html'
    context_object_name = 'product'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return Product.objects.filter(
            is_active=True
        ).select_related(
            'business',  # For vendor info
            'category'   # For breadcrumb
        ).prefetch_related(
            'images',
            'category__children'  # For category breadcrumb
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Update product view count
        if hasattr(self.object, 'search_index'):
            self.object.increase_view_count()
            
        return context

class ProductDetailAPIView(RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductDetailsSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Product.objects.filter(
            is_active=True
        ).select_related(
            'business',
            'category',
            'search_index'  # For rating and view count
        ).prefetch_related(
            'images',
            'category__children',
            'reviews',  # For detailed reviews
            'business__payment_methods'  # For business payment methods
        ).annotate(
            avg_rating=models.Avg('reviews__rating'),
            review_count=models.Count('reviews'),
            low_stock=models.Case(
                models.When(stock_qty__lt=10, stock_qty__gt=0, then=True),
                default=False,
                output_field=models.BooleanField()
            )
        )
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if hasattr(instance, 'search_index'):
            instance.increase_view_count()
        return super().retrieve(request, *args, **kwargs)
