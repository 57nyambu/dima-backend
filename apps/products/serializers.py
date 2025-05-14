from rest_framework import serializers
from apps.business.models import Business
from .models import (
    Category, 
    Product, 
    ProductImage, 
    CategoryImage,
    ProductReview
)
from django.utils.text import slugify

class CategoryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryImage
        fields = ['id', 'image', 'alt_text', 'is_feature']
        read_only_fields = ['is_feature']

class CategorySerializer(serializers.ModelSerializer):
    images = CategoryImageSerializer(many=True, read_only=True)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        write_only=True, required=False,
    )
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'parent', 'is_active', 'images']
        read_only_fields = ['slug']

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'alt_text', 'is_feature']

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductReview
        fields = '__all__'

class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        write_only=True,
        source='category',
        required=False
    )
    images = ProductImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'category', 'category_id', 'name', 'slug', 
            'description', 'price', 
            'stock_qty', 'is_active', 'images'
        ]
        read_only_fields = ['slug']

class ProductDetailsSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    business = serializers.StringRelatedField(read_only=True)
    is_in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'discounted_price',
            'stock_qty', 'category', 'images', 'reviews', 'business', 'is_in_stock'
        ]

    def get_is_in_stock(self, obj):
        return obj.stock_qty > 0

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'category', 'name', 'slug', 
            'description', 'price', 'discounted_price',
            'stock_qty', 'is_active'
        ]
        read_only_fields = ['slug']