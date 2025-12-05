# marketplace/serializers.py
from rest_framework import serializers
from django.conf import settings
from django.db.models import Avg, Count, Q
from django.db import models
from apps.products.models import Product, ProductImage, Category
from apps.business.models import Business, BusinessReview
from apps.orders.models import Order
#from apps.shipping.models import ShippingOption
from .models import (
    Banner, FeaturedProduct, MarketplaceDispute,
    MarketplaceNotification, DisputeMessage
)


class VendorSummarySerializer(serializers.ModelSerializer):
    """Compact vendor info for product listings"""
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    completion_rate = serializers.SerializerMethodField()
    response_time = serializers.SerializerMethodField()
    
    class Meta:
        model = Business
        fields = [
            'id', 'name', 'slug', 'business_type', 'is_verified',
            'avg_rating', 'review_count', 'product_count', 
            'completion_rate', 'response_time'
        ]
    
    def get_avg_rating(self, obj):
        avg = obj.reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(avg, 2) if avg else 0.0
    
    def get_review_count(self, obj):
        return obj.reviews.count()
    
    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()
    
    def get_completion_rate(self, obj):
        # Calculate from orders - placeholder logic
        total_orders = obj.orders.count() if hasattr(obj, 'orders') else 0
        completed_orders = obj.orders.filter(status='delivered').count() if hasattr(obj, 'orders') else 0
        if total_orders > 0:
            return round((completed_orders / total_orders) * 100, 2)
        return 100.0
    
    def get_response_time(self, obj):
        # Placeholder - would calculate average response time
        return "2-4 hours"


class VendorHomepageSerializer(serializers.ModelSerializer):
    """Simplified vendor info for homepage - only name, orders completed, and rating"""
    avg_rating = serializers.SerializerMethodField()
    orders_completed = serializers.SerializerMethodField()
    
    class Meta:
        model = Business
        fields = ['id', 'name', 'slug', 'avg_rating', 'orders_completed']
    
    def get_avg_rating(self, obj):
        if hasattr(obj, 'avg_rating') and obj.avg_rating:
            return round(obj.avg_rating, 2)
        return 0.0
    
    def get_orders_completed(self, obj):
        if hasattr(obj, 'orders_completed'):
            return obj.orders_completed
        return Order.objects.filter(business=obj, status='delivered').count()


class ProductImageSerializer(serializers.ModelSerializer):
    """Product images with different sizes"""
    original = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    medium_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductImage
        fields = ['id', 'original', 'thumbnail_url', 'medium_url', 'is_primary']

    def get_original(self, obj):
        if not obj or not obj.original:
            return None
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
            try:
                from apps.utils.storage_selector import get_original_image_url
                return get_original_image_url(obj.original)
            except Exception as e:
                import logging
                logging.getLogger('storage').error(f"Error generating original URL: {e}")
                return None
        return self.context['request'].build_absolute_uri(obj.original.url) if 'request' in self.context else obj.original.url
    
    def get_thumbnail_url(self, obj):
        # 300x300 WebP for product listings - Perfect for cards/grids
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
            try:
                from apps.utils.storage_selector import get_image_url
                # Use thumbnail_medium (300x300) with WebP format
                return get_image_url(obj.original, size='thumbnail_medium', format='webp') if obj.original else None
            except Exception as e:
                import logging
                logging.getLogger('storage').error(f"Error generating thumbnail URL: {e}")
                return None
        # Local: use ImageKit if available
        thumb = getattr(obj, 'thumbnail', None)
        return self.context['request'].build_absolute_uri(thumb.url) if thumb else (self.context['request'].build_absolute_uri(obj.original.url) if obj.original else None)
    
    def get_medium_url(self, obj):
        # 800x800 WebP for product detail pages
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
            try:
                from apps.utils.storage_selector import get_image_url
                # Use medium (800x800) with WebP format for detail views
                return get_image_url(obj.original, size='medium', format='webp') if obj.original else None
            except Exception as e:
                import logging
                logging.getLogger('storage').error(f"Error generating medium URL: {e}")
                return None
        med = getattr(obj, 'medium', None)
        return self.context['request'].build_absolute_uri(med.url) if med else (self.context['request'].build_absolute_uri(obj.original.url) if obj.original else None)


class CategoryBreadcrumbSerializer(serializers.ModelSerializer):
    """Category hierarchy for breadcrumbs"""
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']


class ProductMarketplaceSerializer(serializers.ModelSerializer):
    """Enhanced product serializer for marketplace listings"""
    vendor = VendorSummarySerializer(source='business', read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    primary_image = serializers.SerializerMethodField()
    category_breadcrumb = serializers.SerializerMethodField()
    
    # Rating and review stats
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    # Pricing
    effective_price = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()
    
    # Stock and availability
    in_stock = serializers.SerializerMethodField()
    low_stock = serializers.SerializerMethodField()
    
    # Shipping info
    shipping_options = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'discounted_price',
            'effective_price', 'discount_percentage', 'stock_qty', 'sales_count',
            'is_active', 'is_feature', 'created_at', 'updated_at',
            'vendor', 'images', 'primary_image', 'category_breadcrumb',
            'avg_rating', 'review_count', 'in_stock', 'low_stock',
            'shipping_options'
        ]
    
    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if primary:
            return ProductImageSerializer(primary, context=self.context).data
        # Fallback to first image (serialize properly) if exists
        fallback = obj.images.first()
        if fallback:
            return ProductImageSerializer(fallback, context=self.context).data
        return None
    
    def get_category_breadcrumb(self, obj):
        breadcrumb = []
        category = obj.category
        while category:
            breadcrumb.insert(0, CategoryBreadcrumbSerializer(category).data)
            category = category.parent
        return breadcrumb
    
    def get_avg_rating(self, obj):
        avg = obj.reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(avg, 2) if avg else 0.0
    
    def get_review_count(self, obj):
        return obj.reviews.count()
    
    def get_effective_price(self, obj):
        return obj.discounted_price if obj.discounted_price > 0 else obj.price
    
    def get_discount_percentage(self, obj):
        if obj.discounted_price > 0 and obj.price > obj.discounted_price:
            return round(((obj.price - obj.discounted_price) / obj.price) * 100, 0)
        return 0
    
    def get_in_stock(self, obj):
        return obj.stock_qty > 0
    
    def get_low_stock(self, obj):
        return 0 < obj.stock_qty <= 10  # Consider low stock threshold
    
    def get_shipping_options(self, obj):
        # Get shipping options for this vendor
        if hasattr(obj.business, 'shipping_options'):
            return obj.business.shipping_options.filter(is_active=True).values(
                'id', 'name', 'price', 'estimated_days'
            )
        return []


class VendorDetailSerializer(serializers.ModelSerializer):
    """Detailed vendor information"""
    avg_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    recent_reviews = serializers.SerializerMethodField()
    business_metrics = serializers.SerializerMethodField()
    
    class Meta:
        model = Business
        fields = [
            'id', 'name', 'slug', 'business_type', 'description',
            'is_verified', 'created_at', 'avg_rating', 'review_count',
            'product_count', 'categories', 'recent_reviews', 'business_metrics'
        ]
    
    def get_avg_rating(self, obj):
        avg = obj.reviews.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(avg, 2) if avg else 0.0
    
    def get_review_count(self, obj):
        return obj.reviews.count()
    
    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()
    
    def get_categories(self, obj):
        categories = Category.objects.filter(
            products__business=obj,
            products__is_active=True
        ).distinct().values('id', 'name', 'slug')
        return list(categories)
    
    def get_recent_reviews(self, obj):
        reviews = obj.reviews.select_related('user').order_by('-created_at')[:3]
        return [{
            'rating': review.rating,
            'comment': review.comment,
            'user': review.user.first_name or review.user.username or 'Anonymous',
            'created_at': review.created_at
        } for review in reviews]
    
    def get_business_metrics(self, obj):
        return {
            'total_orders': getattr(obj, 'total_orders', 0),
            'completion_rate': 95.5,  # Placeholder
            'response_time': '2-4 hours',  # Placeholder
            'member_since': obj.created_at
        }


class OrderMarketplaceSerializer(serializers.ModelSerializer):
    """Buyer-friendly order information"""
    vendor = VendorSummarySerializer(source='business', read_only=True)
    items_summary = serializers.SerializerMethodField()
    shipping_info = serializers.SerializerMethodField()
    payment_info = serializers.SerializerMethodField()
    tracking_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'total', 'created_at',
            'vendor', 'items_summary', 'shipping_info', 'payment_info', 
            'tracking_info'
        ]
    
    def get_items_summary(self, obj):
        # Assuming you have OrderItem model in orders app
        if hasattr(obj, 'items'):
            return obj.items.count(), obj.items.aggregate(total=models.Sum('quantity'))['total']
        return 0, 0
    
    def get_shipping_info(self, obj):
        return {
            'method': getattr(obj, 'shipping_method', 'Standard'),
            'cost': getattr(obj, 'shipping_cost', 0),
            'estimated_delivery': getattr(obj, 'estimated_delivery', None)
        }
    
    def get_payment_info(self, obj):
        return {
            'method': getattr(obj, 'payment_method', 'M-Pesa'),
            'status': getattr(obj, 'payment_status', 'Paid')
        }
    
    def get_tracking_info(self, obj):
        return {
            'tracking_number': getattr(obj, 'tracking_number', None),
            'courier': getattr(obj, 'courier', None),
            'current_status': obj.status
        }


class CategoryListSerializer(serializers.ModelSerializer):
    """Simple category serializer for homepage"""
    image = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['name', 'image', 'slug']
    
    def get_image(self, obj):
        featured_image = obj.images.filter(is_feature=True).first()
        if not featured_image or not featured_image.original:
            return None
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
            try:
                from apps.utils.storage_selector import get_image_url
                url = get_image_url(featured_image.original, size='thumbnail_small') or featured_image.original.url
            except Exception:
                url = featured_image.original.url
        else:
            # Local: use ImageKit thumb if available
            url = getattr(getattr(featured_image, 'thumbnail_small', None), 'url', None) or featured_image.original.url
        return {
            'url': url,
            'alt_text': featured_image.alt_text or obj.name
        }


class CategoryHomepageSerializer(serializers.ModelSerializer):
    """Simplified category serializer for homepage - NO IMAGES"""
    product_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'product_count']


class HomepageDataSerializer(serializers.Serializer):
    """Aggregated homepage data - New structure with products tagged and all vendors ranked"""
    banners = serializers.SerializerMethodField()
    categories = serializers.SerializerMethodField()
    vendors = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    pagination = serializers.SerializerMethodField()
    
    def get_banners(self, obj):
        from django.utils import timezone
        now = timezone.now()
        banners = Banner.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).order_by('position')
        data = []
        for banner in banners:
            img_url = None
            if banner.original:
                if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
                    try:
                        storage = banner.original.storage
                        if hasattr(storage, 'get_processed_url'):
                            img_url = storage.get_processed_url(banner.original.name, width=600, height=300, quality=90)
                        else:
                            img_url = banner.original.url
                    except Exception:
                        img_url = banner.original.url
                else:
                    img_url = banner.thumbnail_large.url if hasattr(banner, 'thumbnail_large') and banner.thumbnail_large else banner.original.url
            data.append({
                'id': banner.id,
                'title': banner.title,
                'subtitle': banner.subtitle,
                'image': img_url,
                'banner_type': banner.banner_type,
                'link_url': banner.link_url,
                'link_text': banner.link_text
            })
        return data
    
    def get_categories(self, obj):
        """Get main categories WITHOUT images"""
        categories_data = obj.get('categories', [])
        return CategoryHomepageSerializer(categories_data, many=True).data
    
    def get_vendors(self, obj):
        """Get all vendors ranked by rating"""
        vendors_data = obj.get('vendors', [])
        return VendorHomepageSerializer(vendors_data, many=True).data
    
    def get_products(self, obj):
        """Get products with tags (featured, trending, etc.)"""
        products_data = obj.get('products', [])
        
        # Add product serialization with tags
        results = []
        for product_item in products_data:
            product = product_item['product']
            product_data = ProductMarketplaceSerializer(product, context=self.context).data
            
            # Add tags - use correct keys from service layer
            product_data['tags'] = {
                'featured': product_item.get('is_featured', False),
                'trending': product_item.get('is_trending', False),
                'new': product_item.get('is_new', False),
            }
            
            results.append(product_data)
        
        return results
    
    def get_pagination(self, obj):
        """Return pagination info"""
        return {
            'products': obj.get('products_pagination', {}),
            'vendors': obj.get('vendors_pagination', {})
        }


class DisputeMessageSerializer(serializers.ModelSerializer):
    """Dispute conversation messages"""
    sender_name = serializers.SerializerMethodField()
    
    class Meta:
        model = DisputeMessage
        fields = ['id', 'message', 'sender_name', 'is_admin', 'created_at']
    
    def get_sender_name(self, obj):
        if obj.is_admin:
            return "Marketplace Support"
        return obj.sender.first_name or obj.sender.username or "User"


class DisputeSerializer(serializers.ModelSerializer):
    """Marketplace disputes"""
    buyer_name = serializers.SerializerMethodField()
    seller_name = serializers.CharField(source='seller.name')
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    messages = DisputeMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = MarketplaceDispute
        fields = [
            'id', 'dispute_type', 'subject', 'description', 'status',
            'buyer_name', 'seller_name', 'order_number', 'messages',
            'resolution_amount', 'resolved_at', 'created_at'
        ]
    
    def get_buyer_name(self, obj):
        return obj.buyer.first_name or obj.buyer.username or "User"


class NotificationSerializer(serializers.ModelSerializer):
    """Marketplace notifications"""
    class Meta:
        model = MarketplaceNotification
        fields = [
            'id', 'notification_type', 'title', 'message', 'is_read', 'created_at'
        ]


class SearchResultSerializer(serializers.Serializer):
    """Search results with filters and pagination"""
    products = ProductMarketplaceSerializer(many=True)
    vendors = VendorSummarySerializer(many=True)
    total_products = serializers.IntegerField()
    total_vendors = serializers.IntegerField()
    filters = serializers.SerializerMethodField()
    
    def get_filters(self, obj):
        """Available filters based on search results"""
        products = obj.get('products', [])
        if not products:
            return {
                'categories': [],
                'price_ranges': [
                    {'min': 0, 'max': 1000, 'label': 'Under KES 1,000'},
                    {'min': 1000, 'max': 5000, 'label': 'KES 1,000 - 5,000'},
                    {'min': 5000, 'max': 10000, 'label': 'KES 5,000 - 10,000'},
                    {'min': 10000, 'max': 50000, 'label': 'KES 10,000 - 50,000'},
                    {'min': 50000, 'max': None, 'label': 'Over KES 50,000'},
                ],
                'vendors': [],
                'rating_options': [
                    {'min': 4, 'label': '4+ stars'},
                    {'min': 3, 'label': '3+ stars'},
                    {'min': 2, 'label': '2+ stars'},
                    {'min': 1, 'label': '1+ stars'},
                ]
            }
        
        # Extract filter options from products
        categories = set()
        price_ranges = []
        vendors = set()
        
        try:
            for product in products:
                # Safely access category
                if hasattr(product, 'category') and product.category:
                    categories.add((product.category.id, product.category.name))
                
                # Safely access price
                if hasattr(product, 'price'):
                    price_ranges.append(float(product.price))
                
                # Safely access business/vendor
                if hasattr(product, 'business') and product.business:
                    vendors.add((product.business.id, product.business.name))
        except Exception as e:
            # Log the error but don't break the API
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating filters: {e}")
        
        # Generate price ranges
        price_brackets = [
            {'min': 0, 'max': 1000, 'label': 'Under KES 1,000'},
            {'min': 1000, 'max': 5000, 'label': 'KES 1,000 - 5,000'},
            {'min': 5000, 'max': 10000, 'label': 'KES 5,000 - 10,000'},
            {'min': 10000, 'max': 50000, 'label': 'KES 10,000 - 50,000'},
            {'min': 50000, 'max': None, 'label': 'Over KES 50,000'},
        ]
        
        return {
            'categories': [{'id': cat[0], 'name': cat[1]} for cat in categories],
            'price_ranges': price_brackets,
            'vendors': [{'id': v[0], 'name': v[1]} for v in vendors],
            'rating_options': [
                {'min': 4, 'label': '4+ stars'},
                {'min': 3, 'label': '3+ stars'},
                {'min': 2, 'label': '2+ stars'},
                {'min': 1, 'label': '1+ stars'},
            ]
        }


class BannerSerializer(serializers.ModelSerializer):
    """Serializer for marketplace banners"""
    thumbnail_small_url = serializers.SerializerMethodField()
    thumbnail_medium_url = serializers.SerializerMethodField()
    thumbnail_large_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Banner
        fields = [
            'id', 'title', 'subtitle', 'original', 'thumbnail_small_url',
            'thumbnail_medium_url', 'thumbnail_large_url', 'banner_type',
            'link_url', 'link_text', 'position', 'is_active',
            'start_date', 'end_date'
        ]
    
    def get_thumbnail_small_url(self, obj):
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud' and obj.original:
            try:
                storage = obj.original.storage
                if hasattr(storage, 'get_processed_url'):
                    # 150x150 WebP for small banner thumbnails
                    return storage.get_processed_url(obj.original.name, width=150, height=150, quality=80, format='webp')
            except Exception as e:
                import logging
                logging.getLogger('storage').error(f"Error generating banner small URL: {e}")
                return None
        return obj.thumbnail_small.url if hasattr(obj, 'thumbnail_small') and obj.thumbnail_small else (obj.original.url if obj.original else None)
    
    def get_thumbnail_medium_url(self, obj):
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud' and obj.original:
            try:
                storage = obj.original.storage
                if hasattr(storage, 'get_processed_url'):
                    # 800x400 WebP for medium banner displays
                    return storage.get_processed_url(obj.original.name, width=800, height=400, quality=85, format='webp')
            except Exception as e:
                import logging
                logging.getLogger('storage').error(f"Error generating banner medium URL: {e}")
                return None
        return obj.thumbnail_medium.url if hasattr(obj, 'thumbnail_medium') and obj.thumbnail_medium else (obj.original.url if obj.original else None)
    
    def get_thumbnail_large_url(self, obj):
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud' and obj.original:
            try:
                storage = obj.original.storage
                if hasattr(storage, 'get_processed_url'):
                    # 1920x600 WebP for large banner displays (hero banners)
                    return storage.get_processed_url(obj.original.name, width=1920, height=600, quality=90, format='webp')
            except Exception as e:
                import logging
                logging.getLogger('storage').error(f"Error generating banner large URL: {e}")
                return None
        return obj.thumbnail_large.url if hasattr(obj, 'thumbnail_large') and obj.thumbnail_large else (obj.original.url if obj.original else None)


class CheckoutItemSerializer(serializers.Serializer):
    """Serializer for individual cart items from frontend"""
    id = serializers.IntegerField(source='product_id')
    name = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    def validate_id(self, value):
        """Validate that product exists and is active"""
        try:
            product = Product.objects.get(id=value, is_active=True)
            return value
        except Product.DoesNotExist:
            raise serializers.ValidationError(f"Product with ID {value} not found or inactive")
    
    def validate(self, data):
        """Validate stock availability and set price"""
        try:
            product = Product.objects.get(id=data['product_id'])
            if product.stock_qty < data['quantity']:
                raise serializers.ValidationError({
                    'quantity': f"Insufficient stock. Only {product.stock_qty} available for {product.name}"
                })
            data['price'] = product.discounted_price if product.discounted_price > 0 else product.price
            data['name'] = product.name
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found")
        
        return data


class CheckoutCustomerSerializer(serializers.Serializer):
    """Customer details for checkout"""
    firstName = serializers.CharField(max_length=225, required=True)
    lastName = serializers.CharField(max_length=225, required=True)
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(max_length=15, required=True)
    
    def validate_phone(self, value):
        """Validate phone number format"""
        if value:
            phone = value.replace(' ', '').replace('-', '').replace('+', '')
            if phone.startswith('254'):
                if len(phone) != 12:
                    raise serializers.ValidationError("Invalid phone number format. Use 254XXXXXXXXX")
            elif phone.startswith('0'):
                if len(phone) != 10:
                    raise serializers.ValidationError("Invalid phone number format. Use 07XXXXXXXX or 01XXXXXXXX")
            else:
                raise serializers.ValidationError("Invalid phone number format. Use 254XXXXXXXXX or 07XXXXXXXX")
        return value


class CheckoutDeliverySerializer(serializers.Serializer):
    """Delivery details for checkout"""
    county = serializers.CharField(max_length=100, required=True)
    town = serializers.CharField(max_length=100, required=True)
    specificLocation = serializers.CharField(max_length=255, required=True)
    deliveryNotes = serializers.CharField(required=False, allow_blank=True)


class CheckoutPaymentSerializer(serializers.Serializer):
    """Payment details for checkout"""
    method = serializers.ChoiceField(
        choices=['mpesa', 'airtel', 'paypal', 'cod'],
        required=True
    )
    mpesaNumber = serializers.CharField(max_length=15, required=False, allow_blank=True)
    airtelNumber = serializers.CharField(max_length=15, required=False, allow_blank=True)
    
    def validate_mpesaNumber(self, value):
        """Validate M-Pesa phone number format"""
        if value:
            phone = value.replace(' ', '').replace('-', '').replace('+', '')
            if phone.startswith('254'):
                if len(phone) != 12:
                    raise serializers.ValidationError("Invalid M-Pesa phone number format. Use 254XXXXXXXXX")
            elif phone.startswith('0'):
                if len(phone) != 10:
                    raise serializers.ValidationError("Invalid M-Pesa phone number format. Use 07XXXXXXXX or 01XXXXXXXX")
                phone = '254' + phone[1:]
            else:
                raise serializers.ValidationError("Invalid phone number format. Use 254XXXXXXXXX or 07XXXXXXXX")
            return phone
        return value
    
    def validate_airtelNumber(self, value):
        """Validate Airtel phone number format"""
        if value:
            phone = value.replace(' ', '').replace('-', '').replace('+', '')
            if phone.startswith('254'):
                if len(phone) != 12:
                    raise serializers.ValidationError("Invalid Airtel phone number format. Use 254XXXXXXXXX")
            elif phone.startswith('0'):
                if len(phone) != 10:
                    raise serializers.ValidationError("Invalid Airtel phone number format. Use 07XXXXXXXX or 01XXXXXXXX")
                phone = '254' + phone[1:]
            else:
                raise serializers.ValidationError("Invalid phone number format. Use 254XXXXXXXXX or 07XXXXXXXX")
            return phone
        return value
    
    def validate(self, data):
        """Validate payment method requirements"""
        method = data.get('method')
        
        if method == 'mpesa' and not data.get('mpesaNumber'):
            raise serializers.ValidationError({
                'mpesaNumber': 'M-Pesa phone number is required for M-Pesa payments'
            })
        
        if method == 'airtel' and not data.get('airtelNumber'):
            raise serializers.ValidationError({
                'airtelNumber': 'Airtel phone number is required for Airtel Money payments'
            })
        
        return data


class CheckoutSerializer(serializers.Serializer):
    """Complete checkout serializer with new structure"""
    customer = CheckoutCustomerSerializer(required=True)
    delivery = CheckoutDeliverySerializer(required=True)
    payment = CheckoutPaymentSerializer(required=True)
    items = CheckoutItemSerializer(many=True, required=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    shipping = serializers.DecimalField(max_digits=10, decimal_places=2, default=200)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    
    def validate_items(self, value):
        """Ensure cart is not empty"""
        if not value:
            raise serializers.ValidationError("Cart cannot be empty")
        if len(value) > 50:
            raise serializers.ValidationError("Maximum 50 items allowed per order")
        return value
    
    def validate(self, data):
        """Validate items - backend recalculates all totals"""
        items = data.get('items', [])
        
        # Just ensure we have items - prices are validated in CheckoutItemSerializer
        if not items:
            raise serializers.ValidationError({'items': 'Cart cannot be empty'})
        
        # Remove frontend-submitted subtotal/total - backend will calculate
        # This prevents price manipulation
        data.pop('subtotal', None)
        data.pop('total', None)
        
        return data


class OrderResponseSerializer(serializers.Serializer):
    """Response serializer after successful checkout"""
    order_id = serializers.IntegerField()
    order_number = serializers.CharField()
    vendor_name = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    payment_status = serializers.CharField()


class CheckoutResponseSerializer(serializers.Serializer):
    """Complete checkout response"""
    success = serializers.BooleanField()
    message = serializers.CharField()
    orders = OrderResponseSerializer(many=True)
    payment_info = serializers.DictField(required=False)
    total_orders = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
