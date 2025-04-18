from rest_framework import serializers
from .models import Category, Product, ProductImage, CategoryImage
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

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        write_only=True,
        source='category'
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