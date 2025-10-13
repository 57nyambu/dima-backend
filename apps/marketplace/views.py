# marketplace/views.py
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404
from django.db.models import Q, Avg, Count
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db import models

from apps.products.models import Product, Category
from apps.business.models import Business
from apps.orders.models import Order
from .models import (
    Cart, CartItem, Wishlist, WishlistItem, Banner,
    ProductComparison, MarketplaceDispute, MarketplaceNotification
)
from .serializers import (
    ProductMarketplaceSerializer, VendorDetailSerializer, VendorSummarySerializer,
    CartSerializer, OrderMarketplaceSerializer, HomepageDataSerializer,
    WishlistSerializer, ProductComparisonSerializer, DisputeSerializer,
    NotificationSerializer, SearchResultSerializer, CheckoutSessionSerializer,
    CategoryListSerializer, BannerSerializer
)
from .services import (
    SearchService, AggregationService, CartService, 
    OrderSplitterService, NotificationService
)


class ProductListView(generics.ListAPIView):
    """List products with marketplace enhancements"""
    serializer_class = ProductMarketplaceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True).select_related(
            'business', 'category'
        ).prefetch_related('images', 'reviews')
        
        # Apply filters
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__slug=category)
        
        vendor = self.request.query_params.get('vendor')
        if vendor:
            queryset = queryset.filter(business__slug=vendor)
        
        price_min = self.request.query_params.get('price_min')
        if price_min:
            queryset = queryset.filter(price__gte=price_min)
        
        price_max = self.request.query_params.get('price_max')
        if price_max:
            queryset = queryset.filter(price__lte=price_max)
        
        # Featured products only
        featured = self.request.query_params.get('featured')
        if featured == 'true':
            queryset = queryset.filter(is_feature=True)
        
        # Verified vendors only
        verified_only = self.request.query_params.get('verified_only')
        if verified_only == 'true':
            queryset = queryset.filter(business__is_verified=True)
        
        # Sorting
        sort_by = self.request.query_params.get('sort_by', 'created_at')
        if sort_by == 'price_low':
            queryset = queryset.order_by('price')
        elif sort_by == 'price_high':
            queryset = queryset.order_by('-price')
        elif sort_by == 'rating':
            queryset = queryset.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
        elif sort_by == 'popular':
            queryset = queryset.order_by('-sales_count')
        else:
            queryset = queryset.order_by('-created_at')
        
        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    """Product detail with enhanced marketplace data"""
    serializer_class = ProductMarketplaceSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    
    def get_queryset(self):
        return Product.objects.filter(is_active=True).select_related(
            'business', 'category'
        ).prefetch_related('images', 'reviews__user')


class VendorListView(generics.ListAPIView):
    """List verified vendors with ratings and metrics"""
    serializer_class = VendorSummarySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get_queryset(self):
        queryset = Business.objects.filter(is_verified=True).annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews'),
            product_count=Count('products', filter=Q(products__is_active=True))
        )
        
        # Filter by business type
        business_type = self.request.query_params.get('type')
        if business_type:
            queryset = queryset.filter(business_type=business_type)
        
        # Filter by minimum rating
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.filter(avg_rating__gte=min_rating)
        
        return queryset.order_by('-avg_rating', '-review_count')


class VendorDetailView(generics.RetrieveAPIView):
    """Detailed vendor profile"""
    serializer_class = VendorDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    queryset = Business.objects.filter(is_verified=True)


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def get_categories(request):
    """Get all active categories with optimized images"""
    categories = Category.objects.filter(
        parent=None,
        is_active=True
    ).prefetch_related('images').order_by('name')
    
    serializer = CategoryListSerializer(categories, many=True, context={'request': request})
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
@cache_page(60 * 30)  # Cache for 30 minutes
def homepage_data(request):
    """Aggregated homepage data"""
    data = AggregationService.get_homepage_data(request.user if request.user.is_authenticated else None)
    serializer = HomepageDataSerializer(data, context={'request': request})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def search_products(request):
    """Advanced product search"""
    try:
        query = request.query_params.get('q', '')
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 24))
        
        # Log search request for debugging
        logger.info(f"Search request - Query: '{query}', Page: {page}, Params: {dict(request.query_params)}")
        
        # Validate pagination parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 24
        
        filters = {
            'category': request.query_params.get('category'),
            'business': request.query_params.get('business') or request.query_params.get('vendor'),  # Support both
            'price_min': request.query_params.get('price_min'),
            'price_max': request.query_params.get('price_max'),
            'min_rating': request.query_params.get('min_rating'),
            'verified_only': request.query_params.get('verified_only') == 'true',
            'in_stock_only': request.query_params.get('in_stock_only') == 'true',
            'sort_by': request.query_params.get('sort_by', 'relevance')
        }
        
        # Remove None values and validate numeric filters
        clean_filters = {}
        for k, v in filters.items():
            if v is not None:
                if k in ['price_min', 'price_max', 'min_rating']:
                    try:
                        clean_filters[k] = float(v) if v else None
                    except (ValueError, TypeError):
                        continue  # Skip invalid numeric values
                else:
                    clean_filters[k] = v
        
        results = SearchService.search_products(query, clean_filters, page, per_page)
        
        # Log results count
        logger.info(f"Search results - Total: {results['total_count']}, Page products: {len(results['products'])}")

        # IMPORTANT: Pass queryset objects directly so nested ProductMarketplaceSerializer
        # receives model instances (previous code passed already serialized dicts,
        # causing AttributeError: 'dict' object has no attribute 'discounted_price').
        response_data = {
            'products': results['products'],              # queryset slice
            'vendors': [],                                 # placeholder for vendor search
            'total_products': results['total_count'],
            'total_vendors': 0,
            # expose raw pagination data for client if needed
            'page': results['page'],
            'per_page': results['per_page'],
            'total_pages': results['total_pages'],
            'has_next': results['has_next'],
            'has_prev': results['has_prev']
        }

        serializer = SearchResultSerializer(response_data, context={'request': request})
        return Response(serializer.data)
    
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Search error: {str(e)}", exc_info=True)
        
        # Return a user-friendly error response
        return Response({
            'error': 'Search service is temporarily unavailable',
            'products': [],
            'vendors': [],
            'total_products': 0,
            'total_vendors': 0,
            'filters': {
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
        }, status=status.HTTP_200_OK)  # Return 200 instead of 500 for better UX


@api_view(['GET'])
@permission_classes([IsAuthenticatedOrReadOnly])
def search_vendors(request):
    """Search vendors/businesses"""
    query = request.query_params.get('q', '')
    filters = {
        'business_type': request.query_params.get('type'),
        'min_rating': request.query_params.get('min_rating')
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    
    results = SearchService.search_vendors(query, filters)
    serializer = VendorSummarySerializer(results['vendors'], many=True)
    
    return Response({
        'vendors': serializer.data,
        'total_count': results['total_count']
    })


@api_view(['GET'])
def search_suggestions(request):
    """Get search suggestions"""
    try:
        query = request.query_params.get('q', '')
        if len(query) < 2:
            return Response({'suggestions': []})
        
        suggestions = SearchService.get_search_suggestions(query, limit=10)
        return Response({'suggestions': suggestions})
    
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Search suggestions error: {str(e)}", exc_info=True)
        
        # Return empty suggestions instead of an error
        return Response({'suggestions': []})


# Cart Management Views
class CartView(generics.RetrieveAPIView):
    """User's shopping cart"""
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        return cart


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart(request):
    """Add product to cart"""
    product_id = request.data.get('product_id')
    quantity = int(request.data.get('quantity', 1))
    
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        
        # Check stock availability
        if product.stock_qty < quantity:
            return Response({
                'error': 'Insufficient stock',
                'available_stock': product.stock_qty
            }, status=status.HTTP_400_BAD_REQUEST)
        
        cart_item = CartService.add_to_cart(request.user, product, quantity)
        
        return Response({
            'message': 'Product added to cart',
            'cart_item_id': cart_item.id,
            'quantity': cart_item.quantity
        }, status=status.HTTP_201_CREATED)
        
    except Product.DoesNotExist:
        return Response({
            'error': 'Product not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_cart_item(request, item_id):
    """Update cart item quantity"""
    quantity = int(request.data.get('quantity', 1))
    
    try:
        cart_item = CartItem.objects.get(
            id=item_id,
            cart__user=request.user
        )
        
        if quantity <= 0:
            cart_item.delete()
            return Response({'message': 'Item removed from cart'})
        
        # Check stock
        if cart_item.product.stock_qty < quantity:
            return Response({
                'error': 'Insufficient stock',
                'available_stock': cart_item.product.stock_qty
            }, status=status.HTTP_400_BAD_REQUEST)
        
        cart_item.quantity = quantity
        cart_item.save()
        
        return Response({
            'message': 'Cart updated',
            'quantity': cart_item.quantity,
            'subtotal': cart_item.subtotal
        })
        
    except CartItem.DoesNotExist:
        return Response({
            'error': 'Cart item not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    try:
        cart_item = CartItem.objects.get(
            id=item_id,
            cart__user=request.user
        )
        cart_item.delete()
        
        return Response({'message': 'Item removed from cart'})
        
    except CartItem.DoesNotExist:
        return Response({
            'error': 'Cart item not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_cart(request):
    """Clear user's cart"""
    CartService.clear_cart(request.user)
    return Response({'message': 'Cart cleared'})


# Checkout Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def checkout_session(request):
    """Get checkout session data"""
    try:
        cart = Cart.objects.get(user=request.user)
        if not cart.items.exists():
            return Response({
                'error': 'Cart is empty'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        session_data = {'cart': cart}
        serializer = CheckoutSessionSerializer(session_data, context={'request': request})
        
        return Response(serializer.data)
        
    except Cart.DoesNotExist:
        return Response({
            'error': 'Cart not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_checkout(request):
    """Process multi-vendor checkout"""
    shipping_details = request.data.get('shipping_details', {})
    payment_method = request.data.get('payment_method', 'mpesa')
    
    try:
        cart = Cart.objects.get(user=request.user)
        if not cart.items.exists():
            return Response({
                'error': 'Cart is empty'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Split cart into separate orders per vendor
        orders = OrderSplitterService.split_cart_into_orders(
            cart, request.user, shipping_details, payment_method
        )
        
        # Send notifications
        for order in orders:
            NotificationService.send_order_notification('order_placed', order)
        
        # Clear cart after successful checkout
        CartService.clear_cart(request.user)
        
        return Response({
            'message': 'Orders created successfully',
            'order_count': len(orders),
            'orders': [
                {
                    'id': order.id,
                    'order_number': getattr(order, 'order_number', str(order.id)),
                    'vendor': order.business.name,
                    'total': order.total_amount
                } for order in orders
            ]
        }, status=status.HTTP_201_CREATED)
        
    except Cart.DoesNotExist:
        return Response({
            'error': 'Cart not found'
        }, status=status.HTTP_404_NOT_FOUND)


# Wishlist Views
class WishlistView(generics.RetrieveAPIView):
    """User's wishlist"""
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        wishlist, created = Wishlist.objects.get_or_create(user=self.request.user)
        return wishlist


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_wishlist(request):
    """Add product to wishlist"""
    product_id = request.data.get('product_id')
    
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        wishlist, created = Wishlist.objects.get_or_create(user=request.user)
        
        wishlist_item, created = WishlistItem.objects.get_or_create(
            wishlist=wishlist,
            product=product
        )
        
        if created:
            return Response({
                'message': 'Product added to wishlist'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'message': 'Product already in wishlist'
            })
            
    except Product.DoesNotExist:
        return Response({
            'error': 'Product not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_wishlist(request, product_id):
    """Remove product from wishlist"""
    try:
        wishlist = Wishlist.objects.get(user=request.user)
        wishlist_item = WishlistItem.objects.get(
            wishlist=wishlist,
            product_id=product_id
        )
        wishlist_item.delete()
        
        return Response({'message': 'Product removed from wishlist'})
        
    except (Wishlist.DoesNotExist, WishlistItem.DoesNotExist):
        return Response({
            'error': 'Product not found in wishlist'
        }, status=status.HTTP_404_NOT_FOUND)


# Order Views
class OrderListView(generics.ListAPIView):
    """User's order history"""
    serializer_class = OrderMarketplaceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(
            buyer=self.request.user
        ).select_related('business').order_by('-created_at')


class OrderDetailView(generics.RetrieveAPIView):
    """Order detail"""
    serializer_class = OrderMarketplaceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Order.objects.filter(buyer=self.request.user).select_related('business')


# Product Comparison Views
class ProductComparisonListView(generics.ListCreateAPIView):
    """User's product comparisons"""
    serializer_class = ProductComparisonSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ProductComparison.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_comparison(request):
    """Add product to comparison"""
    product_id = request.data.get('product_id')
    comparison_name = request.data.get('comparison_name', 'My Comparison')
    
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        comparison, created = ProductComparison.objects.get_or_create(
            user=request.user,
            name=comparison_name
        )
        
        if comparison.products.count() >= 4:
            return Response({
                'error': 'Maximum 4 products allowed in comparison'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        comparison.products.add(product)
        
        return Response({
            'message': 'Product added to comparison',
            'comparison_id': comparison.id
        })
        
    except Product.DoesNotExist:
        return Response({
            'error': 'Product not found'
        }, status=status.HTTP_404_NOT_FOUND)


# Dispute Views
class DisputeListCreateView(generics.ListCreateAPIView):
    """List and create disputes"""
    serializer_class = DisputeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return MarketplaceDispute.objects.filter(
            buyer=self.request.user
        ).order_by('-created_at')
    
    def perform_create(self, serializer):
        dispute = serializer.save(buyer=self.request.user)
        NotificationService.send_dispute_notification(dispute)


class DisputeDetailView(generics.RetrieveAPIView):
    """Dispute detail with messages"""
    serializer_class = DisputeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return MarketplaceDispute.objects.filter(
            buyer=self.request.user
        ).prefetch_related('messages__sender')


# Notification Views
class BannerCreateView(generics.CreateAPIView):
    """Create new marketplace banners"""
    serializer_class = BannerSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save()


class NotificationListView(generics.ListAPIView):
    """User notifications"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return MarketplaceNotification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    """Mark notifications as read"""
    notification_ids = request.data.get('notification_ids', [])
    
    if notification_ids:
        MarketplaceNotification.objects.filter(
            id__in=notification_ids,
            user=request.user
        ).update(is_read=True)
    else:
        # Mark all as read
        MarketplaceNotification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
    
    return Response({'message': 'Notifications marked as read'})


# Analytics endpoint for vendors (bonus)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def vendor_analytics(request):
    """Basic analytics for vendor dashboard"""
    if not request.user.is_business_owner:
        return Response({
            'error': 'Access denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get user's business
    business = request.user.businesses.first()
    if not business:
        return Response({
            'error': 'No business found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Calculate metrics
    total_products = business.products.filter(is_active=True).count()
    total_orders = Order.objects.filter(business=business).count()
    pending_orders = Order.objects.filter(business=business, status='pending').count()
    total_revenue = Order.objects.filter(
        business=business, 
        status='delivered'
    ).aggregate(total=models.Sum('total_amount'))['total'] or 0
    
    avg_rating = business.reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    
    return Response({
        'business_name': business.name,
        'total_products': total_products,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'total_revenue': total_revenue,
        'avg_rating': round(avg_rating, 2),
        'verification_status': business.verification_status,
        'is_verified': business.is_verified
    })