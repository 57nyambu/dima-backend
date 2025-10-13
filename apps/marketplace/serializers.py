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
    Cart, CartItem, Wishlist, WishlistItem, Banner, 
    FeaturedProduct, Banner, MarketplaceDispute,
    ProductComparison, MarketplaceNotification, DisputeMessage
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
            except Exception:
                return obj.original.url
        return self.context['request'].build_absolute_uri(obj.original.url) if 'request' in self.context else obj.original.url
    
    def get_thumbnail_url(self, obj):
        # 300x300 in our config
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
            try:
                from apps.utils.storage_selector import get_image_url
                return get_image_url(obj.original, size='thumbnail_medium') if obj.original else None
            except Exception:
                return obj.original.url if obj.original else None
        # Local: use ImageKit if available
        thumb = getattr(obj, 'thumbnail', None)
        return self.context['request'].build_absolute_uri(thumb.url) if thumb else (self.context['request'].build_absolute_uri(obj.original.url) if obj.original else None)
    
    def get_medium_url(self, obj):
        # 600x600 in our config
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
            try:
                from apps.utils.storage_selector import get_image_url
                return get_image_url(obj.original, size='thumbnail_large') if obj.original else None
            except Exception:
                return obj.original.url if obj.original else None
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
    
    # User-specific fields (require authentication)
    is_in_wishlist = serializers.SerializerMethodField()
    is_in_cart = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'discounted_price',
            'effective_price', 'discount_percentage', 'stock_qty', 'sales_count',
            'is_active', 'is_feature', 'created_at', 'updated_at',
            'vendor', 'images', 'primary_image', 'category_breadcrumb',
            'avg_rating', 'review_count', 'in_stock', 'low_stock',
            'shipping_options', 'is_in_wishlist', 'is_in_cart'
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
    
    def get_is_in_wishlist(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.wishlist_items.filter(wishlist__user=request.user).exists()
        return False
    
    def get_is_in_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.cart_items.filter(cart__user=request.user).exists()
        return False


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


class CartItemSerializer(serializers.ModelSerializer):
    """Cart items with product details"""
    product = ProductMarketplaceSerializer(read_only=True)
    subtotal = serializers.ReadOnlyField()
    
    class Meta:
        model = CartItem
        fields = ['id', 'product', 'quantity', 'subtotal', 'created_at']


class CartSerializer(serializers.ModelSerializer):
    """Shopping cart with items grouped by vendor"""
    items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.ReadOnlyField()
    total_items = serializers.ReadOnlyField()
    vendors_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = ['id', 'items', 'total_amount', 'total_items', 'vendors_summary', 'updated_at']
    
    def get_vendors_summary(self, obj):
        """Group cart items by vendor"""
        vendors = {}
        for item in obj.items.all():
            vendor_id = item.product.business.id
            if vendor_id not in vendors:
                vendors[vendor_id] = {
                    'vendor': VendorSummarySerializer(item.product.business).data,
                    'items': [],
                    'vendor_total': 0
                }
            vendors[vendor_id]['items'].append(CartItemSerializer(item).data)
            vendors[vendor_id]['vendor_total'] += item.subtotal
        
        return list(vendors.values())


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
            'id', 'order_number', 'status', 'total_amount', 'created_at',
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

class HomepageDataSerializer(serializers.Serializer):
    """Aggregated homepage data"""
    banners = serializers.SerializerMethodField()
    featured_products = serializers.SerializerMethodField()
    top_vendors = serializers.SerializerMethodField()
    trending_products = serializers.SerializerMethodField()
    
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
    
    def get_featured_products(self, obj):
        from django.utils import timezone
        now = timezone.now()
        featured = FeaturedProduct.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).select_related('product__business').prefetch_related('product__images').order_by('position')[:12]
        
        results = []
        for fp in featured:
            thumb = None
            primary = fp.product.images.filter(is_primary=True).first()
            if primary and primary.original:
                if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
                    try:
                        from apps.utils.storage_selector import get_image_url
                        thumb = get_image_url(primary.original, size='thumbnail_medium') or primary.original.url
                    except Exception:
                        thumb = primary.original.url
                else:
                    thumb = getattr(getattr(primary, 'thumbnail', None), 'url', None) or primary.original.url
            results.append({
                **ProductMarketplaceSerializer(fp.product, context=self.context).data,
                'thumbnail_url': thumb
            })
        return results
    
    def get_top_vendors(self, obj):
        # Get top-rated verified vendors
        top_vendors = Business.objects.filter(
            is_verified=True
        ).annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews')
        ).filter(
            review_count__gte=5
        ).order_by('-avg_rating', '-review_count')[:8]
        
        return [VendorSummarySerializer(vendor).data for vendor in top_vendors]
    
    def get_trending_products(self, obj):
        # Get products with high recent sales
        trending = Product.objects.filter(
            is_active=True
        ).prefetch_related('images').order_by('-sales_count', '-created_at')[:12]
        
        results = []
        for product in trending:
            thumb = None
            primary = product.images.filter(is_primary=True).first()
            if primary and primary.original:
                if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
                    try:
                        from apps.utils.storage_selector import get_image_url
                        thumb = get_image_url(primary.original, size='thumbnail_medium') or primary.original.url
                    except Exception:
                        thumb = primary.original.url
                else:
                    thumb = getattr(getattr(primary, 'thumbnail', None), 'url', None) or primary.original.url
            results.append({
                **ProductMarketplaceSerializer(product, context=self.context).data,
                'thumbnail_url': thumb
            })
        return results

    def get_categories(self, obj):
        # Get main categories with optimized images
        categories = Category.objects.filter(
            parent=None,
            is_active=True
        ).prefetch_related('images').order_by('name')
        
        output = []
        for cat in categories:
            featured_image = cat.images.filter(is_feature=True).first()
            url = None
            alt = cat.name
            if featured_image and featured_image.original:
                alt = featured_image.alt_text or cat.name
                if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
                    try:
                        from apps.utils.storage_selector import get_image_url
                        url = get_image_url(featured_image.original, size='thumbnail_small') or featured_image.original.url
                    except Exception:
                        url = featured_image.original.url
                else:
                    url = getattr(getattr(featured_image, 'thumbnail_small', None), 'url', None) or featured_image.original.url
            output.append({
                'name': cat.name,
                'slug': cat.slug,
                'image': {
                    'url': url,
                    'alt_text': alt
                }
            })
        return output


class WishlistSerializer(serializers.ModelSerializer):
    """User wishlist with products"""
    items = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    
    class Meta:
        model = Wishlist
        fields = ['id', 'items', 'total_items', 'updated_at']
    
    def get_items(self, obj):
        items = obj.items.select_related('product__business').order_by('-created_at')
        return [{
            'id': item.id,
            'product': ProductMarketplaceSerializer(item.product, context=self.context).data,
            'added_at': item.created_at
        } for item in items]
    
    def get_total_items(self, obj):
        return obj.items.count()


class ProductComparisonSerializer(serializers.ModelSerializer):
    """Product comparison with detailed specs"""
    products = ProductMarketplaceSerializer(many=True, read_only=True)
    comparison_matrix = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductComparison
        fields = ['id', 'name', 'products', 'comparison_matrix', 'created_at']
    
    def get_comparison_matrix(self, obj):
        """Create comparison matrix for key attributes"""
        products = obj.products.all()
        if not products:
            return {}
        
        matrix = {
            'price': [p.price for p in products],
            'discounted_price': [p.discounted_price for p in products],
            'rating': [p.reviews.aggregate(avg=Avg('rating'))['avg'] or 0 for p in products],
            'reviews': [p.reviews.count() for p in products],
            'stock': [p.stock_qty for p in products],
            'vendor_rating': [p.business.reviews.aggregate(avg=Avg('rating'))['avg'] or 0 for p in products],
            'vendor_verified': [p.business.is_verified for p in products]
        }
        return matrix


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
                    return storage.get_processed_url(obj.original.name, width=150, height=150, quality=80)
            except Exception:
                return obj.original.url
        return obj.thumbnail_small.url if hasattr(obj, 'thumbnail_small') and obj.thumbnail_small else (obj.original.url if obj.original else None)
    
    def get_thumbnail_medium_url(self, obj):
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud' and obj.original:
            try:
                storage = obj.original.storage
                if hasattr(storage, 'get_processed_url'):
                    return storage.get_processed_url(obj.original.name, width=300, height=200, quality=85)
            except Exception:
                return obj.original.url
        return obj.thumbnail_medium.url if hasattr(obj, 'thumbnail_medium') and obj.thumbnail_medium else (obj.original.url if obj.original else None)
    
    def get_thumbnail_large_url(self, obj):
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud' and obj.original:
            try:
                storage = obj.original.storage
                if hasattr(storage, 'get_processed_url'):
                    return storage.get_processed_url(obj.original.name, width=600, height=300, quality=90)
            except Exception:
                return obj.original.url
        return obj.thumbnail_large.url if hasattr(obj, 'thumbnail_large') and obj.thumbnail_large else (obj.original.url if obj.original else None)


class CheckoutSessionSerializer(serializers.Serializer):
    """Checkout session data"""
    cart_summary = CartSerializer()
    shipping_options = serializers.SerializerMethodField()
    payment_methods = serializers.SerializerMethodField()
    order_summary = serializers.SerializerMethodField()
    
    def get_shipping_options(self, obj):
        """Available shipping options for all vendors in cart"""
        cart = obj['cart']
        vendors = cart.vendors
        
        shipping_options = {}
        for vendor in vendors:
            if hasattr(vendor, 'shipping_options'):
                options = vendor.shipping_options.filter(is_active=True)
                shipping_options[vendor.id] = [{
                    'id': opt.id,
                    'name': opt.name,
                    'price': opt.price,
                    'estimated_days': opt.estimated_days,
                    'description': opt.description
                } for opt in options]
        
        return shipping_options
    
    def get_payment_methods(self, obj):
        """Available payment methods"""
        return [
            {'id': 'mpesa', 'name': 'M-Pesa', 'icon': 'mpesa.png'},
            {'id': 'airtel', 'name': 'Airtel Money', 'icon': 'airtel.png'},
            {'id': 'card', 'name': 'Credit/Debit Card', 'icon': 'card.png'},
        ]
    
    def get_order_summary(self, obj):
        """Calculate order totals"""
        cart = obj['cart']
        subtotal = cart.total_amount
        
        # Calculate shipping (placeholder logic)
        shipping_total = 200 * len(cart.vendors)  # KES 200 per vendor
        
        # Calculate tax
        tax_rate = 0.16  # 16% VAT
        tax_amount = subtotal * tax_rate
        
        # Platform fee
        platform_fee = subtotal * 0.025  # 2.5% platform fee
        
        total = subtotal + shipping_total + tax_amount + platform_fee
        
        return {
            'subtotal': subtotal,
            'shipping_total': shipping_total,
            'tax_amount': tax_amount,
            'platform_fee': platform_fee,
            'total': total,
            'currency': 'KES'
        }