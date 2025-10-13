# marketplace/services.py
from django.db import transaction
from django.db.models import Q, Avg, Count, F
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.core.cache import cache
from django.utils import timezone
from typing import List, Dict, Any, Optional
import logging
from django.conf import settings



from Root.settings.base import MARKETPLACE_SETTINGS
from apps.products.models import Product, Category
from apps.business.models import Business
from apps.orders.models import Order
from apps.accounts.models import CustomUser
from .models import (
    Cart, CartItem, ProductSearchIndex, VendorSearchIndex,
    MarketplaceNotification, MarketplaceDispute, MarketplaceSettings
)

logger = logging.getLogger(__name__)


class OrderSplitterService:
    """Service to split multi-vendor carts into separate orders"""
    
    @staticmethod
    def split_cart_into_orders(cart: Cart, buyer: CustomUser, shipping_details: dict, 
                              payment_method: str) -> List[Order]:
        """
        Split cart items into separate orders per vendor
        """
        orders = []
        
        # Group cart items by vendor
        vendor_items = {}
        for item in cart.items.select_related('product__business'):
            vendor_id = item.product.business.id
            if vendor_id not in vendor_items:
                vendor_items[vendor_id] = {
                    'business': item.product.business,
                    'items': []
                }
            vendor_items[vendor_id]['items'].append(item)
        
        # Create separate order for each vendor
        with transaction.atomic():
            for vendor_id, vendor_data in vendor_items.items():
                business = vendor_data['business']
                items = vendor_data['items']
                
                # Calculate order total for this vendor
                order_total = sum(item.subtotal for item in items)
                
                # Create order (assuming you have Order model)
                order = Order.objects.create(
                    buyer=buyer,
                    business=business,
                    total_amount=order_total,
                    shipping_address=shipping_details.get('address'),
                    shipping_phone=shipping_details.get('phone'),
                    payment_method=payment_method,
                    status='pending'
                )
                
                # Create order items (assuming you have OrderItem model)
                for cart_item in items:
                    # This would create OrderItem - adjust based on your orders app structure
                    order_item_data = {
                        'order': order,
                        'product': cart_item.product,
                        'quantity': cart_item.quantity,
                        'price': cart_item.product.discounted_price or cart_item.product.price,
                        'subtotal': cart_item.subtotal
                    }
                    # order.items.create(**order_item_data)  # Uncomment when OrderItem model exists
                
                orders.append(order)
                
                # Update product stock
                for cart_item in items:
                    product = cart_item.product
                    product.stock_qty = F('stock_qty') - cart_item.quantity
                    product.sales_count = F('sales_count') + cart_item.quantity
                    product.save(update_fields=['stock_qty', 'sales_count'])
        
        return orders


class CommissionEngine:
    """Service to calculate platform commission and vendor payouts"""
    
    # Default commission rate (10%)
    PLATFORM_COMMISSION_RATE = 0.10
    
    # Get commission rate from MarketplaceSettings
    @staticmethod
    def get_commission_rate():
        try:
            settings = MarketplaceSettings.objects.first()
            return float(settings.commission_rate) / 100 if settings else 0.10
        except Exception:
            return 0.10  # Default 10% if settings not available

    @staticmethod
    def calculate_commission(order_total: float, business: Business = None) -> Dict[str, float]:
        """
        Calculate commission breakdown for an order
        """
        # Get commission rate (could be per-business or global)
        commission_rate = CommissionEngine.get_commission_rate()

        # If business has custom commission rate (future feature)
        # if business and hasattr(business, 'commission_rate'):
        #     commission_rate = business.commission_rate / 100
        
        platform_commission = order_total * commission_rate
        vendor_payout = order_total - platform_commission
        
        # Calculate payment processing fee (e.g., 2.5%)
        processing_fee = order_total * 0.025
        final_vendor_payout = vendor_payout - processing_fee
        
        return {
            'order_total': order_total,
            'commission_rate': commission_rate,
            'platform_commission': platform_commission,
            'processing_fee': processing_fee,
            'vendor_payout': final_vendor_payout,
            'platform_total': platform_commission + processing_fee
        }
    
    @staticmethod
    def process_payout_calculation(business: Business, period_start: timezone.datetime,
                                 period_end: timezone.datetime) -> Dict[str, Any]:
        """
        Calculate total payout for a business over a period
        """
        # Get completed orders for the period
        orders = Order.objects.filter(
            business=business,
            status='delivered',
            created_at__range=[period_start, period_end]
        )
        
        total_sales = sum(order.total_amount for order in orders)
        total_orders = orders.count()
        
        if total_sales == 0:
            return {
                'total_sales': 0,
                'total_orders': 0,
                'platform_commission': 0,
                'processing_fees': 0,
                'net_payout': 0
            }
        
        commission_breakdown = CommissionEngine.calculate_commission(total_sales, business)
        
        return {
            'total_sales': total_sales,
            'total_orders': total_orders,
            'platform_commission': commission_breakdown['platform_commission'],
            'processing_fees': commission_breakdown['processing_fee'],
            'net_payout': commission_breakdown['vendor_payout'],
            'orders': list(orders.values('id', 'order_number', 'total_amount', 'created_at'))
        }


class NotificationService:
    """Service to handle marketplace notifications"""
    
    NOTIFICATION_TEMPLATES = {
        'order_placed': {
            'buyer_title': 'Order Placed Successfully',
            'buyer_message': 'Your order #{order_number} has been placed successfully.',
            'seller_title': 'New Order Received',
            'seller_message': 'You have received a new order #{order_number} worth KES {amount}.'
        },
        'order_confirmed': {
            'buyer_title': 'Order Confirmed',
            'buyer_message': 'Your order #{order_number} has been confirmed by the seller.'
        },
        'order_shipped': {
            'buyer_title': 'Order Shipped',
            'buyer_message': 'Your order #{order_number} has been shipped. Tracking: {tracking_number}'
        },
        'order_delivered': {
            'buyer_title': 'Order Delivered',
            'buyer_message': 'Your order #{order_number} has been delivered successfully.'
        },
        'dispute_opened': {
            'buyer_title': 'Dispute Opened',
            'buyer_message': 'Your dispute for order #{order_number} has been opened.',
            'seller_title': 'Dispute Alert',
            'seller_message': 'A dispute has been opened for order #{order_number}.'
        }
    }
    
    @staticmethod
    def send_order_notification(notification_type: str, order: Order, **kwargs):
        """Send notifications for order events"""
        template = NotificationService.NOTIFICATION_TEMPLATES.get(notification_type)
        if not template:
            logger.warning(f"Unknown notification type: {notification_type}")
            return
        
        # Send to buyer
        if 'buyer_title' in template:
            MarketplaceNotification.objects.create(
                user=order.buyer,
                notification_type=notification_type,
                title=template['buyer_title'],
                message=template['buyer_message'].format(
                    order_number=order.order_number,
                    amount=order.total_amount,
                    **kwargs
                ),
                order=order
            )
        
        # Send to seller
        if 'seller_title' in template:
            MarketplaceNotification.objects.create(
                user=order.business.owner,
                notification_type=notification_type,
                title=template['seller_title'],
                message=template['seller_message'].format(
                    order_number=order.order_number,
                    amount=order.total_amount,
                    **kwargs
                ),
                order=order,
                business=order.business
            )
    
    @staticmethod
    def send_dispute_notification(dispute: MarketplaceDispute):
        """Send notifications for dispute events"""
        NotificationService.send_order_notification('dispute_opened', dispute.order)
    
    @staticmethod
    def send_review_notification(product, reviewer, rating):
        """Send notification when product gets reviewed"""
        MarketplaceNotification.objects.create(
            user=product.business.owner,
            notification_type='product_review',
            title='New Product Review',
            message=f'Your product "{product.name}" received a {rating}-star review.',
            product=product,
            business=product.business
        )
    
    @staticmethod
    def send_stock_alert(product: Product):
        """Send low stock alert to vendor"""
        MarketplaceNotification.objects.create(
            user=product.business.owner,
            notification_type='stock_low',
            title='Low Stock Alert',
            message=f'Your product "{product.name}" is running low on stock ({product.stock_qty} remaining).',
            product=product,
            business=product.business
        )


class SearchService:
    """Service for marketplace search and discovery"""
    
    @staticmethod
    def search_products(query: str, filters: Dict[str, Any] = None, 
                       page: int = 1, per_page: int = 24) -> Dict[str, Any]:
        """
        Advanced product search with filters
        """
        filters = filters or {}
        
        # Base queryset
        products = Product.objects.filter(is_active=True).select_related(
            'business', 'category'
        ).prefetch_related('images', 'reviews')
        
        # Text search
        if query and query.strip():
            query = query.strip()
            # Use PostgreSQL full-text search if available
            try:
                search_vector = SearchVector('name', weight='A') + \
                              SearchVector('description', weight='B') + \
                              SearchVector('business__name', weight='C')
                search_query = SearchQuery(query)
                products = products.annotate(
                    search=search_vector,
                    rank=SearchRank(search_vector, search_query)
                ).filter(search=search_query).order_by('-rank', '-created_at')
            except:
                # Fallback to simple text search
                products = products.filter(
                    Q(name__icontains=query) |
                    Q(description__icontains=query) |
                    Q(business__name__icontains=query) |
                    Q(category__name__icontains=query)
                )
        
        # Apply filters
        if filters.get('category'):
            # Support both category ID and slug
            category_value = filters['category']
            try:
                # Try as ID first
                products = products.filter(category_id=int(category_value))
            except (ValueError, TypeError):
                # Try as slug
                products = products.filter(Q(category__slug=category_value) | Q(category__name__iexact=category_value))
        
        if filters.get('business'):
            products = products.filter(business_id=filters['business'])
        
        if filters.get('price_min'):
            products = products.filter(price__gte=filters['price_min'])
        
        if filters.get('price_max'):
            products = products.filter(price__lte=filters['price_max'])
        
        if filters.get('min_rating'):
            products = products.annotate(
                avg_rating=Avg('reviews__rating')
            ).filter(avg_rating__gte=filters['min_rating'])
        
        if filters.get('verified_only'):
            products = products.filter(business__is_verified=True)
        
        if filters.get('in_stock_only'):
            products = products.filter(stock_qty__gt=0)
        
        # Sorting
        sort_by = filters.get('sort_by', 'relevance')
        if sort_by == 'price_low':
            products = products.order_by('price')
        elif sort_by == 'price_high':
            products = products.order_by('-price')
        elif sort_by == 'rating':
            products = products.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
        elif sort_by == 'newest':
            products = products.order_by('-created_at')
        elif sort_by == 'popular':
            products = products.order_by('-sales_count')
        
        # Pagination
        offset = (page - 1) * per_page
        total_count = products.count()
        products_page = products[offset:offset + per_page]
        
        return {
            'products': products_page,  # Return queryset, not list
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page,
            'has_next': offset + per_page < total_count,
            'has_prev': page > 1
        }
    
    @staticmethod
    def search_vendors(query: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Search for vendors/businesses"""
        filters = filters or {}
        
        businesses = Business.objects.filter(is_verified=True).annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews'),
            product_count=Count('products', filter=Q(products__is_active=True))
        )
        
        if query:
            businesses = businesses.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query) |
                Q(business_type__icontains=query)
            )
        
        # Apply filters
        if filters.get('business_type'):
            businesses = businesses.filter(business_type=filters['business_type'])
        
        if filters.get('min_rating'):
            businesses = businesses.filter(avg_rating__gte=filters['min_rating'])
        
        # Sort by rating and review count
        businesses = businesses.order_by('-avg_rating', '-review_count')
        
        return {
            'vendors': list(businesses),
            'total_count': businesses.count()
        }
    
    @staticmethod
    def get_search_suggestions(query: str, limit: int = 10) -> List[str]:
        """Get search suggestions based on partial query"""
        cache_key = f"search_suggestions:{query.lower()}"
        suggestions = cache.get(cache_key)
        
        if suggestions is None:
            # Get product name suggestions
            product_suggestions = Product.objects.filter(
                name__icontains=query,
                is_active=True
            ).values_list('name', flat=True)[:limit//2]
            
            # Get category suggestions
            category_suggestions = Category.objects.filter(
                name__icontains=query,
                is_active=True
            ).values_list('name', flat=True)[:limit//2]
            
            suggestions = list(product_suggestions) + list(category_suggestions)
            cache.set(cache_key, suggestions, 300)  # Cache for 5 minutes
        
        return suggestions[:limit]


class AggregationService:
    """Service for aggregating marketplace data"""
    
    @staticmethod
    def get_homepage_data(user: CustomUser = None) -> Dict[str, Any]:
        """Get aggregated data for homepage"""
        cache_key = f"homepage_data:{user.id if user else 'anonymous'}"
        data = cache.get(cache_key)
        
        if data is None:
            from .models import Banner, FeaturedProduct
            
            now = timezone.now()
            
            # Get active banners
            banners = Banner.objects.filter(
                is_active=True,
                start_date__lte=now,
                end_date__gte=now
            ).order_by('position')[:5]
            
            # Get featured products
            featured_products = Product.objects.filter(
                featured_listings__is_active=True,
                featured_listings__start_date__lte=now,
                featured_listings__end_date__gte=now,
                is_active=True
            ).select_related('business').prefetch_related('images')[:12]
            
            # Get trending products (high sales, recent)
            trending_products = Product.objects.filter(
                is_active=True
            ).order_by('-sales_count', '-created_at')[:12]
            
            # Get top vendors
            top_vendors = Business.objects.filter(
                is_verified=True
            ).annotate(
                avg_rating=Avg('reviews__rating'),
                review_count=Count('reviews')
            ).filter(review_count__gte=5).order_by('-avg_rating')[:8]
            
            # Get main categories
            categories = Category.objects.filter(
                parent=None,
                is_active=True
            ).annotate(
                product_count=Count('products', filter=Q(products__is_active=True))
            ).order_by('name')[:12]
            
            data = {
                'banners': banners,
                'categories': categories,
                'featured_products': featured_products,
                'trending_products': trending_products,
                'top_vendors': top_vendors,
            }
            
            # Cache for 30 minutes
            cache.set(cache_key, data, 1800)
        
        return data
    
    @staticmethod
    def update_search_indexes():
        """Update search indexes for products and vendors"""
        # Update product search index
        products = Product.objects.filter(is_active=True).select_related(
            'business', 'category'
        )
        
        for product in products:
            search_index, created = ProductSearchIndex.objects.get_or_create(
                product=product
            )
            
            # Update denormalized fields
            search_index.business_name = product.business.name
            search_index.business_verified = product.business.is_verified
            search_index.category_name = product.category.name
            search_index.avg_rating = product.reviews.aggregate(
                avg=Avg('rating')
            )['avg'] or 0.0
            search_index.review_count = product.reviews.count()
            search_index.sales_count = product.sales_count
            
            # Update search vector
            search_index.search_vector = (
                SearchVector('product__name', weight='A') +
                SearchVector('product__description', weight='B') +
                SearchVector('business_name', weight='C') +
                SearchVector('category_name', weight='D')
            )
            
            search_index.save()
        
        logger.info(f"Updated search indexes for {products.count()} products")


class CartService:
    """Service for cart management"""
    
    @staticmethod
    def add_to_cart(user: CustomUser, product: Product, quantity: int = 1) -> CartItem:
        """Add product to user's cart"""
        cart, created = Cart.objects.get_or_create(user=user)
        
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        
        # Send low stock alert if needed
        if product.stock_qty <= 10:
            NotificationService.send_stock_alert(product)
        
        return cart_item
    
    @staticmethod
    def update_cart_item(user: CustomUser, product: Product, quantity: int) -> CartItem:
        """Update cart item quantity"""
        cart = Cart.objects.get(user=user)
        cart_item = CartItem.objects.get(cart=cart, product=product)
        
        if quantity <= 0:
            cart_item.delete()
            return None
        
        cart_item.quantity = quantity
        cart_item.save()
        return cart_item
    
    @staticmethod
    def clear_cart(user: CustomUser):
        """Clear user's cart"""
        try:
            cart = Cart.objects.get(user=user)
            cart.items.all().delete()
        except Cart.DoesNotExist:
            pass