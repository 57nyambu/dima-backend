from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Category, Product, ProductImage, CategoryImage
from .serializers import (
    CategorySerializer, ProductSerializer, ProductImageSerializer,
    CategoryImageSerializer, ProductDetailsSerializer
)
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from django.db import transaction

# Handles creation of a category along with its image in a single request.
class Category_ImageViewSet(ModelViewSet):
    queryset = CategoryImage.objects.all()
    serializer_class = CategoryImageSerializer
    parser_classes = (MultiPartParser, FormParser)

    @action(detail=False, methods=['post'])
    @transaction.atomic
    def create_category_with_image(self, request):
        category_data = request.data.copy()
        category_image = request.FILES.get('image')

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
                        image=image,
                        alt_text=request.data.get('alt_text', ''),
                        is_feature=request.data.get('is_feature', False)
                    )
                    for image in product_images
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