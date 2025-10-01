from rest_framework import status, pagination, permissions, serializers
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Category, Product, ProductImage, CategoryImage, ProductReview
from .serializers import (
    CategorySerializer, ProductSerializer, ProductImageSerializer,
    CategoryImageSerializer, ProductDetailsSerializer, ProductReviewSerializer
)
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from django.db import models, transaction

class ProductReviewViewSet(ModelViewSet):
    queryset = ProductReview.objects.all()
    serializer_class = ProductReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Filter reviews based on product's business owner or the reviewer
        return ProductReview.objects.filter(
            models.Q(product__business__owner=self.request.user) | 
            models.Q(user=self.request.user)
        )

    def perform_create(self, serializer):
        # Validate that the user hasn't already reviewed this product
        product_id = self.request.data.get('product_id')
        existing_review = ProductReview.objects.filter(
            user=self.request.user, 
            product_id=product_id
        ).exists()
        
        if existing_review:
            raise serializers.ValidationError(
                "You have already reviewed this product."
            )
        
        serializer.save(user=self.request.user)

# Handles creation of a category along with its image in a single request.
class CustomPagination(pagination.PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100


class Category_ImageViewSet(ModelViewSet):
    queryset = CategoryImage.objects.all()
    serializer_class = CategoryImageSerializer
    parser_classes = (MultiPartParser, FormParser)

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def create_category_with_image(self, request):
        category_data = request.data.copy()
        category_image = request.FILES.get('original')

        category_serializer = CategorySerializer(data=category_data)
        if category_serializer.is_valid():
            category = category_serializer.save()

            if category_image:
                image_instance = CategoryImage.objects.create(
                    category=category,
                    image=category_image,
                    alt_text=request.data.get('alt_text', ''),
                    is_feature=request.data.get('is_feature', False)
                )
                image_serializer = CategoryImageSerializer(image_instance)
                return Response({
                    'category': category_serializer.data,
                    'image': image_serializer.data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'category': category_serializer.data
                }, status=status.HTTP_201_CREATED)

        return Response(category_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Handles all CRUD operations for products, including creation with images and detailed retrieval.
class Product_ImageViewSet(ModelViewSet):
    queryset = Product.objects.all()
    parser_classes = (MultiPartParser, FormParser)
    lookup_field = 'slug'
    pagination_class = CustomPagination

    def get_serializer_class(self):
        # Use detailed serializer for retrieving a single product
        if self.action == 'retrieve':
            return ProductDetailsSerializer
        return ProductSerializer

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def create_product_with_images(self, request):
        product_data = request.data.copy()
        product_images = request.FILES.getlist('images') or request.FILES.getlist('image')

        product_serializer = ProductSerializer(data=product_data)
        if product_serializer.is_valid():
            product = product_serializer.save()
            created_images = []

            if product_images:
                image_objs = [
                    ProductImage(
                        product=product,
                        original=image,
                        is_primary=(i == 0)  # Optionally set the first image as primary
                    )
                    for i, image in enumerate(product_images)
                ]
                ProductImage.objects.bulk_create(image_objs)
                created_images = ProductImageSerializer(
                    ProductImage.objects.filter(product=product), many=True
                ).data

            return Response({
                'product': product_serializer.data,
                'images': created_images
            }, status=status.HTTP_201_CREATED)

        return Response(product_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=False, methods=['GET'])
    def featured_products(self, request):
        """Get products marked as featured"""
        featured_products = self.queryset.filter(
            is_active=True,
            stock_qty__gt=0
        ).order_by('-created_at')
        
        page = self.paginate_queryset(featured_products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def on_sale(self, request):
        """Get products that have a discounted price"""
        on_sale = self.queryset.filter(
            is_active=True,
            discounted_price__lt=models.F('price')
        ).order_by('-created_at')
        
        page = self.paginate_queryset(on_sale)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def new_arrivals(self, request):
        """Get recently added products"""
        new_products = self.queryset.filter(
            is_active=True
        ).order_by('-created_at')
        
        page = self.paginate_queryset(new_products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def best_selling(self, request):
        """Get products with highest sales"""
        best_sellers = self.queryset.filter(
            is_active=True,
            stock_qty__gt=0
        ).order_by('-sales_count')
        
        page = self.paginate_queryset(best_sellers)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def category_products(self, request):
        """Get products by category"""
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response(
                {'error': 'category_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        products = self.queryset.filter(
            category_id=category_id,
            is_active=True
        ).order_by('-created_at')  # Added ordering
        
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def search_products(self, request):
        """Search products by name or description"""
        query = request.query_params.get('q', '')
        if not query:
            return Response(
                {'error': 'Search query is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        products = self.queryset.filter(
            models.Q(name__icontains=query) |
            models.Q(description__icontains=query),
            is_active=True
        ).order_by('-created_at')  # Added ordering
        
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

    @action(detail=False, methods=['GET'])
    def price_range(self, request):
        """Get products within a price range"""
        try:
            min_price = float(request.query_params.get('min', 0))
            max_price = float(request.query_params.get('max', 0))
        except (TypeError, ValueError):
            return Response(
                {'error': 'Invalid price values'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not max_price:
            return Response(
                {'error': 'Max price is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        products = self.queryset.filter(
            price__gte=min_price,
            price__lte=max_price,
            is_active=True
        ).order_by('-created_at')  # Added ordering
        
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)