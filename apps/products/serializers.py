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

class ProductReviewSerializer(serializers.ModelSerializer):
    user = serializers.EmailField(source='user.email', read_only=True)
    product = serializers.SerializerMethodField()
    product_id = serializers.PrimaryKeyRelatedField(
        source='product',
        queryset=Product.objects.all(),
        write_only=True
    )

    class Meta:
        model = ProductReview
        fields = ['id', 'product', 'product_id', 'user', 'rating', 
                 'comment', 'mpesa_code', 'created_at']
        read_only_fields = ['user', 'created_at']

    def get_product(self, obj):
        return {
            'name': obj.product.name,
            'business': obj.product.business.name,
            'category': obj.product.category.name,
            'price': str(obj.product.price)
        }

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

class CategoryImageSerializer(serializers.ModelSerializer):
    # Dynamic URL fields that work with both local and cloud storage
    thumbnail_small = serializers.SerializerMethodField()
    thumbnail_medium = serializers.SerializerMethodField()
    thumbnail_large = serializers.SerializerMethodField()
    original_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CategoryImage
        fields = ['id', 'original', 'original_url', 'thumbnail_small', 'thumbnail_medium', 
                  'thumbnail_large', 'alt_text', 'is_feature', 'created_at']
        read_only_fields = ['is_feature']
    
    def get_original_url(self, obj):
        """Get URL for original image"""
        return obj.original.url if obj.original else ''
    
    def get_thumbnail_small(self, obj):
        """Get URL for small thumbnail"""
        return obj.get_thumbnail_small_url()
    
    def get_thumbnail_medium(self, obj):
        """Get URL for medium thumbnail"""
        return obj.get_thumbnail_medium_url()
    
    def get_thumbnail_large(self, obj):
        """Get URL for large thumbnail"""
        return obj.get_thumbnail_large_url()

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
    # Dynamic URL fields that work with both local and cloud storage
    thumbnail = serializers.SerializerMethodField()
    medium = serializers.SerializerMethodField()
    original_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductImage
        fields = ['id', 'original', 'original_url', 'thumbnail', 'medium', 'is_primary', 'created_at']
    
    def get_original_url(self, obj):
        """Get URL for original image"""
        return obj.original.url if obj.original else ''
    
    def get_thumbnail(self, obj):
        """Get URL for thumbnail"""
        return obj.get_thumbnail_url()
    
    def get_medium(self, obj):
        """Get URL for medium size"""
        return obj.get_medium_url()


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
    business = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    avg_rating = serializers.FloatField(read_only=True)
    review_count = serializers.IntegerField(read_only=True)
    discount_percentage = serializers.SerializerMethodField()
    is_low_stock = serializers.BooleanField(read_only=True)
    view_count = serializers.SerializerMethodField()
    payment_methods = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'discounted_price',
            'stock_qty', 'category', 'images', 'reviews', 'business', 
            'is_in_stock', 'avg_rating', 'review_count', 'discount_percentage',
            'is_low_stock', 'view_count', 'payment_methods', 'created_at'
        ]

    def get_is_in_stock(self, obj) -> bool:
        return obj.stock_qty > 0

    def get_discount_percentage(self, obj):
        return obj.discount_percentage

    def get_view_count(self, obj):
        return obj.search_index.view_count if hasattr(obj, 'search_index') else 0

    def get_business(self, obj):
        return {
            'id': obj.business.id,
            'name': str(obj.business.name),
            'type': obj.business.get_business_type_display(),
            'is_verified': obj.business.is_verified,
            'verification_status': obj.business.verification_status
        }

    def get_payment_methods(self, obj):
        return [
            {
                'type': method.get_type_display(),
                'details': method.till_number or method.business_number or method.bank_name
            }
            for method in obj.business.payment_methods.all()
        ]

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'category', 'name', 'slug', 
            'description', 'price', 'discounted_price',
            'stock_qty', 'is_active'
        ]
        read_only_fields = ['slug']