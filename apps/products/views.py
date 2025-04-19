from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Category, Product, ProductImage, CategoryImage
from .serializers import CategorySerializer, ProductSerializer, ProductImageSerializer, CategoryImageSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response

class Category_ImageViewSet(ModelViewSet):
    queryset = CategoryImage.objects.all()
    serializer_class = CategoryImageSerializer
    parser_classes = (MultiPartParser, FormParser)

    @action(detail=False, methods=['post'])
    def create_category_with_image(self, request):
        # Get category data
        category_data = request.data.copy()
        category_image = category_data.pop('image', None)
        
        # Create category first
        category_serializer = CategorySerializer(data=category_data)
        if category_serializer.is_valid():
            category = category_serializer.save()

            # Now handle the image creation
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


class CategoryImageViewSet(ModelViewSet):
    queryset = CategoryImage.objects.all()
    serializer_class = CategoryImageSerializer
    parser_classes = (MultiPartParser, FormParser)


class ProductImageViewSet(ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    parser_classes = (MultiPartParser, FormParser)

class Product_ImageViewSet(ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    parser_classes = (MultiPartParser, FormParser)
    lookup_field = 'slug'

    @action(detail=False, methods=['post'])
    def create_product_with_images(self, request):
        # Get product data
        product_data = request.data.copy()
        product_images = product_data.pop('images', None)

        # Create product first
        product_serializer = ProductSerializer(data=product_data)
        if product_serializer.is_valid():
            product = product_serializer.save()

            # Now handle the image creation
            created_images = []
            if product_images:
                for image in product_images:
                    image_instance = ProductImage.objects.create(
                        product=product,
                        image=image,
                        alt_text=request.data.get('alt_text', ''),
                        is_feature=request.data.get('is_feature', False)
                    )
                    created_images.append(ProductImageSerializer(image_instance).data)

            return Response({
                'product': product_serializer.data,
                'images': created_images
            }, status=status.HTTP_201_CREATED)

        return Response(product_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()