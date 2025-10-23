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
    ProductSearchIndex, VendorSearchIndex,
    MarketplaceNotification, MarketplaceDispute, MarketplaceSettings
)

logger = logging.getLogger(__name__)


class OrderSplitterService:
    """Service to split multi-vendor orders and create order records"""
    
    @staticmethod
    def create_orders_from_cart(buyer: CustomUser, cart_items: list, shipping_details: dict, 
                                payment_method: str) -> List[Order]:
        """
        Split cart items into separate orders per vendor and create Order records
        
        Args:
            buyer: CustomUser instance
            cart_items: List of dicts with {product_id, quantity, price}
            shipping_details: Dict with shipping information
            payment_method: Payment method chosen
        
        Returns:
            List of created Order objects
        """
        from apps.products.models import Product
        
        orders = []
        
        # Group cart items by vendor
        vendor_items = {}
        for item_data in cart_items:
            try:
                product = Product.objects.select_related('business').get(
                    id=item_data['product_id'],
                    is_active=True
                )
                
                # Check stock availability again (race condition protection)
                if product.stock_qty < item_data['quantity']:
                    raise ValueError(f"Insufficient stock for {product.name}")
                
                vendor_id = product.business.id
                if vendor_id not in vendor_items:
                    vendor_items[vendor_id] = {
                        'business': product.business,
                        'items': []
                    }
                
                vendor_items[vendor_id]['items'].append({
                    'product': product,
                    'quantity': item_data['quantity'],
                    'price': item_data.get('price', product.price)
                })
                
            except Product.DoesNotExist:
                logger.error(f"Product {item_data['product_id']} not found during checkout")
                continue
        
        # Create separate order for each vendor
        with transaction.atomic():
            for vendor_id, vendor_data in vendor_items.items():
                business = vendor_data['business']
                items = vendor_data['items']
                
                # Calculate order total for this vendor
                order_total = sum(item['price'] * item['quantity'] for item in items)
                
                # Create order
                order = Order.objects.create(
                    user=buyer,  # The field is 'user' not 'buyer'
                    business=business,
                    total=order_total,  # The field is 'total' not 'total_amount'
                    # Store shipping details in a way compatible with current model
                    # You may need to add these fields to Order model or store differently
                    payment_method=payment_method,
                    status='pending'
                )
                
                # Create order items (if OrderItem model exists)
                for item in items:
                    # Update this based on your actual OrderItem model
                    if hasattr(order, 'items'):
                        try:
                            order.items.create(
                                product=item['product'],
                                quantity=item['quantity'],
                                price=item['price'],
                                subtotal=item['price'] * item['quantity']
                            )
                        except Exception as e:
                            logger.error(f"Could not create order item: {e}")
                
                # Update product stock
                for item in items:
                    product = item['product']
                    product.stock_qty = F('stock_qty') - item['quantity']
                    product.sales_count = F('sales_count') + item['quantity']
                    product.save(update_fields=['stock_qty', 'sales_count'])
                
                orders.append(order)
                logger.info(f"Created order {order.id} for business {business.name}")
        
        return orders
    
    @staticmethod
    def calculate_total_amount(cart_items: list) -> float:
        """Calculate total amount from cart items"""
        return sum(item.get('price', 0) * item.get('quantity', 0) for item in cart_items)


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
    def get_homepage_data(user: CustomUser = None, products_page: int = 1, vendors_page: int = 1, 
                         products_per_page: int = 24, vendors_per_page: int = 20) -> Dict[str, Any]:
        """Get aggregated data for homepage with pagination"""
        cache_key = f"homepage_data:{user.id if user else 'anonymous'}:p{products_page}:v{vendors_page}"
        data = cache.get(cache_key)
        
        if data is None:
            from .models import Banner, FeaturedProduct
            from django.utils import timezone
            
            now = timezone.now()
            
            # Get active banners (no pagination needed)
            banners = Banner.objects.filter(
                is_active=True,
                start_date__lte=now,
                end_date__gte=now
            ).order_by('position')[:10]
            
            # Get main categories WITHOUT images
            categories = Category.objects.filter(
                parent=None,
                is_active=True
            ).annotate(
                product_count=Count('products', filter=Q(products__is_active=True))
            ).order_by('name')
            
            # Get ALL vendors ranked by rating
            all_vendors = Business.objects.filter(
                is_verified=True
            ).annotate(
                avg_rating=Avg('reviews__rating'),
                orders_completed=Count('orders', filter=Q(orders__status='delivered'))
            ).order_by('-avg_rating', '-orders_completed')
            
            # Paginate vendors
            vendors_offset = (vendors_page - 1) * vendors_per_page
            vendors_total = all_vendors.count()
            vendors = all_vendors[vendors_offset:vendors_offset + vendors_per_page]
            
            # Get featured product IDs and trending product IDs
            featured_product_ids = set(
                FeaturedProduct.objects.filter(
                    is_active=True,
                    start_date__lte=now,
                    end_date__gte=now
                ).values_list('product_id', flat=True)
            )
            
            # Get all active products with tags
            from datetime import timedelta
            recent_date = now - timedelta(days=30)
            
            all_products = Product.objects.filter(
                is_active=True
            ).select_related('business', 'category').prefetch_related('images')
            
            # Build product list with tags
            products_with_tags = []
            for product in all_products:
                # Check if featured: either in FeaturedProduct table OR has is_feature=True
                is_featured = product.id in featured_product_ids or product.is_feature
                is_trending = product.sales_count > 10  # Products with >10 sales are trending
                is_new = product.created_at >= recent_date
                
                products_with_tags.append({
                    'product': product,
                    'is_featured': is_featured,
                    'is_trending': is_trending,
                    'is_new': is_new,
                })
            
            # Sort products: featured first, then trending, then by date
            products_with_tags.sort(
                key=lambda x: (
                    -int(x['is_featured']),
                    -int(x['is_trending']),
                    -x['product'].sales_count,
                    -x['product'].created_at.timestamp()
                )
            )
            
            # Paginate products
            products_offset = (products_page - 1) * products_per_page
            products_total = len(products_with_tags)
            products_page_data = products_with_tags[products_offset:products_offset + products_per_page]
            
            data = {
                'banners': banners,
                'categories': list(categories),
                'vendors': list(vendors),
                'products': products_page_data,
                'products_pagination': {
                    'page': products_page,
                    'per_page': products_per_page,
                    'total': products_total,
                    'total_pages': (products_total + products_per_page - 1) // products_per_page,
                    'has_next': products_offset + products_per_page < products_total,
                    'has_prev': products_page > 1
                },
                'vendors_pagination': {
                    'page': vendors_page,
                    'per_page': vendors_per_page,
                    'total': vendors_total,
                    'total_pages': (vendors_total + vendors_per_page - 1) // vendors_per_page,
                    'has_next': vendors_offset + vendors_per_page < vendors_total,
                    'has_prev': vendors_page > 1
                }
            }
            
            # Cache for 15 minutes (shorter due to pagination)
            cache.set(cache_key, data, 900)
        
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
