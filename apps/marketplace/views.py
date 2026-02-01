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
import logging

logger = logging.getLogger(__name__)

from apps.products.models import Product, Category
from apps.business.models import Business
from apps.orders.models import Order
from .models import (
    Banner, MarketplaceDispute, MarketplaceNotification
)
from .serializers import (
    ProductMarketplaceSerializer, VendorDetailSerializer, VendorSummarySerializer,
    OrderMarketplaceSerializer, HomepageDataSerializer,
    DisputeSerializer,
    NotificationSerializer, SearchResultSerializer,
    CategoryListSerializer, BannerSerializer, CheckoutSerializer, CheckoutResponseSerializer
)
from .services import (
    SearchService, AggregationService,
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
def homepage_data(request):
    """Aggregated homepage data with pagination support"""
    # Get pagination parameters
    products_page = int(request.query_params.get('products_page', 1))
    vendors_page = int(request.query_params.get('vendors_page', 1))
    products_per_page = int(request.query_params.get('products_per_page', 24))
    vendors_per_page = int(request.query_params.get('vendors_per_page', 20))
    
    # Validate pagination parameters
    products_page = max(1, products_page)
    vendors_page = max(1, vendors_page)
    products_per_page = min(max(1, products_per_page), 100)
    vendors_per_page = min(max(1, vendors_per_page), 50)
    
    data = AggregationService.get_homepage_data(
        request.user if request.user.is_authenticated else None,
        products_page=products_page,
        vendors_page=vendors_page,
        products_per_page=products_per_page,
        vendors_per_page=vendors_per_page
    )
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
        logger.error(f"Search suggestions error: {str(e)}", exc_info=True)
        
        # Return empty suggestions instead of an error
        return Response({'suggestions': []})


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


# Checkout Views
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_checkout(request):
    """
    Process checkout with cart data from frontend.
    Supports M-Pesa, Airtel Money, PayPal, and Cash on Delivery.
    """
    from .serializers import CheckoutSerializer, CheckoutResponseSerializer
    from apps.payments.mpesa import initiate_stk_push
    from apps.shipping.models import CustomerDeliveryAddress
    
    # Validate checkout data
    serializer = CheckoutSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    validated_data = serializer.validated_data
    
    try:
        # Update customer profile if provided
        customer_data = validated_data.get('customer', {})
        user = request.user
        
        # Update user profile with customer data
        if customer_data.get('firstName'):
            user.first_name = customer_data['firstName']
        if customer_data.get('lastName'):
            user.last_name = customer_data['lastName']
        if customer_data.get('phone'):
            user.phone_number = customer_data['phone']
        user.save()
        
        # Save delivery address if not already saved
        delivery_data = validated_data.get('delivery', {})
        county = delivery_data.get('county')
        town = delivery_data.get('town')
        specific_location = delivery_data.get('specificLocation')
        delivery_notes = delivery_data.get('deliveryNotes', '')
        
        # Check if this address already exists for the user
        existing_address = CustomerDeliveryAddress.objects.filter(
            user=user,
            county=county,
            town=town,
            specific_location=specific_location
        ).first()
        
        if not existing_address:
            # Create new delivery address
            is_first_address = not CustomerDeliveryAddress.objects.filter(user=user).exists()
            CustomerDeliveryAddress.objects.create(
                user=user,
                county=county,
                town=town,
                specific_location=specific_location,
                delivery_notes=delivery_notes,
                is_default=is_first_address  # Set as default if it's the first address
            )
        
        # Extract payment details
        payment_data = validated_data.get('payment', {})
        payment_method = payment_data.get('method')
        
        # Create orders from cart items
        orders = OrderSplitterService.create_orders_from_cart(
            buyer=request.user,
            cart_items=validated_data['items'],
            shipping_details={
                'shipping_address': specific_location,
                'shipping_city': town,
                'shipping_county': county,
                'shipping_phone': customer_data.get('phone'),
                'shipping_notes': delivery_notes
            },
            payment_method=payment_method
        )
        
        if not orders:
            return Response({
                'success': False,
                'message': 'No orders could be created. Please check your cart items.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate total amount
        total_amount = sum(order.total for order in orders)
        
        # Prepare response data
        order_responses = []
        for order in orders:
            order_responses.append({
                'order_id': order.id,
                'order_number': getattr(order, 'order_number', str(order.id)),
                'vendor_name': order.business.name,
                'total_amount': float(order.total),
                'status': order.status,
                'payment_status': getattr(order, 'payment_status', 'pending')
            })
        
        # Adjust message based on payment method
        if payment_method == 'mpesa':
            message = f'{len(orders)} order(s) created - awaiting M-Pesa payment confirmation'
        else:
            message = f'{len(orders)} order(s) created successfully'
        
        response_data = {
            'success': True,
            'message': message,
            'orders': order_responses,
            'total_orders': len(orders),
            'total_amount': float(total_amount)
        }
        
        # Handle M-Pesa payment
        if payment_method == 'mpesa':
            mpesa_phone = payment_data.get('mpesaNumber')
            try:
                # Initiate M-Pesa STK Push
                mpesa_response = initiate_stk_push(
                    phone_number=mpesa_phone,
                    amount=int(total_amount),
                    account_reference=f"ORDER-{'-'.join([str(o.id) for o in orders])}",
                    transaction_desc=f"Payment for {len(orders)} order(s)"
                )
                
                if mpesa_response.get('success'):
                    response_data['payment_info'] = {
                        'provider': 'M-Pesa',
                        'status': 'initiated',
                        'message': 'STK push sent to your phone. Please enter your M-Pesa PIN.',
                        'checkout_request_id': mpesa_response.get('CheckoutRequestID'),
                        'merchant_request_id': mpesa_response.get('MerchantRequestID')
                    }
                    
                    # Store checkout request ID for callback matching
                    for order in orders:
                        order.mpesa_code = mpesa_response.get('CheckoutRequestID')
                        order.payment_status = 'pending'
                        order.save(update_fields=['mpesa_code', 'payment_status'])
                else:
                    response_data['payment_info'] = {
                        'provider': 'M-Pesa',
                        'status': 'failed',
                        'message': mpesa_response.get('errorMessage', 'Failed to initiate M-Pesa payment'),
                        'error_code': mpesa_response.get('errorCode')
                    }
                    
            except Exception as e:
                logger.error(f"M-Pesa STK Push failed: {str(e)}")
                response_data['payment_info'] = {
                    'provider': 'M-Pesa',
                    'status': 'error',
                    'message': 'Payment initiation failed. Please try again or contact support.'
                }
        
        elif payment_method == 'airtel':
            airtel_phone = payment_data.get('airtelNumber')
            response_data['payment_info'] = {
                'provider': 'Airtel Money',
                'status': 'pending',
                'message': 'Airtel Money integration coming soon. Please use M-Pesa or Cash on Delivery.',
                'phone': airtel_phone
            }
        
        elif payment_method == 'paypal':
            response_data['payment_info'] = {
                'provider': 'PayPal',
                'status': 'pending',
                'message': 'PayPal integration coming soon. Please use M-Pesa or Cash on Delivery.'
            }
        
        elif payment_method == 'cod':
            # Set payment_status to pending for COD orders
            for order in orders:
                order.payment_status = 'pending'
                order.save(update_fields=['payment_status'])
            
            response_data['payment_info'] = {
                'provider': 'Cash on Delivery',
                'status': 'confirmed',
                'message': 'Order placed successfully. Pay when you receive your order.'
            }
        
        # Send notifications
        for order in orders:
            try:
                NotificationService.send_order_notification('order_placed', order)
            except Exception as e:
                logger.error(f"Failed to send notification for order {order.id}: {str(e)}")
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Checkout failed: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'message': 'Checkout failed. Please try again or contact support.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def mpesa_callback(request):
    """
    Handle M-Pesa payment callback from Safaricom.
    This endpoint should be registered in your M-Pesa configuration.
    """
    try:
        callback_data = request.data
        logger.info(f"M-Pesa Callback received: {callback_data}")
        
        # Extract callback data
        result_code = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultCode')
        checkout_request_id = callback_data.get('Body', {}).get('stkCallback', {}).get('CheckoutRequestID')
        
        if not checkout_request_id:
            logger.error("No CheckoutRequestID in callback")
            return Response({'ResultCode': 1, 'ResultDesc': 'Invalid callback data'})
        
        # Find orders with this checkout request ID
        orders = Order.objects.filter(mpesa_code=checkout_request_id)
        
        if not orders.exists():
            logger.warning(f"No orders found for CheckoutRequestID: {checkout_request_id}")
            return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})
        
        # Check if payment was successful
        if result_code == 0:
            # Payment successful
            callback_metadata = callback_data.get('Body', {}).get('stkCallback', {}).get('CallbackMetadata', {}).get('Item', [])
            
            # Extract payment details
            mpesa_receipt = None
            phone_number = None
            amount = None
            
            for item in callback_metadata:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')
                elif item.get('Name') == 'PhoneNumber':
                    phone_number = item.get('Value')
                elif item.get('Name') == 'Amount':
                    amount = item.get('Value')
            
            # Update M-Pesa receipt code on orders
            orders.update(mpesa_code=mpesa_receipt)
            
            # Confirm orders and reduce stock
            orders_list = list(orders)
            if OrderSplitterService.confirm_mpesa_orders(orders_list):
                logger.info(f"Payment confirmed for {len(orders_list)} orders. Receipt: {mpesa_receipt}")
                
                # Send confirmation notifications
                for order in orders_list:
                    try:
                        NotificationService.send_order_notification('order_confirmed', order)
                    except Exception as e:
                        logger.error(f"Failed to send notification for order {order.id}: {e}")
                
                return Response({
                    'ResultCode': 0,
                    'ResultDesc': 'Success'
                }, status=status.HTTP_200_OK)
            else:
                logger.error("Failed to confirm M-Pesa orders after successful payment")
                return Response({
                    'ResultCode': 1,
                    'ResultDesc': 'Order confirmation failed'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        else:
            # Payment failed or cancelled
            result_desc = callback_data.get('Body', {}).get('stkCallback', {}).get('ResultDesc', 'Payment failed')
            logger.warning(f"M-Pesa payment failed: {result_desc}")
            
            # Update orders to show payment failed - don't reduce stock
            orders.update(
                status='cancelled',
                payment_status='failed'
            )
            
            logger.info(f"Cancelled {orders.count()} orders due to failed payment")
            
            return Response({
                'ResultCode': 1,
                'ResultDesc': 'Payment failed'
            }, status=status.HTTP_200_OK)
        
        return Response({'ResultCode': 0, 'ResultDesc': 'Accepted'})
        
    except Exception as e:
        logger.error(f"M-Pesa callback processing failed: {str(e)}", exc_info=True)
        return Response({'ResultCode': 1, 'ResultDesc': 'Processing failed'})


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