from rest_framework import status, serializers as drf_serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q, F, Avg, Max, Min
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from drf_spectacular.utils import extend_schema, inline_serializer

from .permissions import IsSellerPermission, IsAdminPermission, IsBuyerPermission
from .serializers import (
    SellerDashboardSerializer,
    AdminDashboardSerializer,
    BuyerDashboardSerializer,
    RevenueChartSerializer,
    TopProductSerializer
)
from apps.orders.models import Order, OrderItem
from apps.orders.serializers import OrderListSerializer
from apps.products.models import Product
from apps.accounts.models import CustomUser
from apps.business.models import Business
from apps.payments.models import Payment, PaymentSettlement


# ==================== SELLER DASHBOARD ====================

@extend_schema(responses=SellerDashboardSerializer, description='Seller dashboard overview with all key metrics including payment analytics')
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSellerPermission])
def seller_overview(request):
    """
    Seller dashboard overview with all key metrics including payment analytics
    Query params: start_date, end_date (YYYY-MM-DD)
    """
    user = request.user
    
    # Get seller's business
    try:
        business = Business.objects.get(owner=user)
    except Business.DoesNotExist:
        return Response(
            {"error": "No business found for this seller"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Date range filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    orders_query = Order.objects.filter(business=business)
    
    if start_date and end_date:
        orders_query = orders_query.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    
    # Order statistics
    total_orders = orders_query.count()
    pending_orders = orders_query.filter(status='pending').count()
    completed_orders = orders_query.filter(status='delivered').count()
    total_revenue = orders_query.filter(
        payment_status='paid'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    # Product statistics
    products = Product.objects.filter(business=business)
    total_products = products.count()
    active_products = products.filter(is_active=True).count()
    out_of_stock = products.filter(stock_qty=0).count()
    
    # Recent orders (last 10)
    recent_orders = OrderListSerializer(
        orders_query.order_by('-created_at')[:10],
        many=True
    ).data
    
    # Top products by sales
    top_products_data = OrderItem.objects.filter(
        order__business=business,
        order__payment_status='paid'
    ).values(
        'product__id',
        'product__name'
    ).annotate(
        sales_count=Count('id'),
        revenue=Sum(F('quantity') * F('price'))
    ).order_by('-revenue')[:5]
    
    top_products = []
    for item in top_products_data:
        product = Product.objects.filter(id=item['product__id']).first()
        top_products.append({
            'id': item['product__id'],
            'name': item['product__name'],
            'sales_count': item['sales_count'],
            'revenue': float(item['revenue']),
            'image': product.get_primary_image_url() if product else None
        })
    
    # Revenue trend (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    revenue_by_date = orders_query.filter(
        created_at__gte=thirty_days_ago,
        payment_status='paid'
    ).extra(
        select={'day': 'date(created_at)'}
    ).values('day').annotate(
        revenue=Sum('total'),
        orders=Count('id')
    ).order_by('day')
    
    revenue_trend = [
        {
            'date': item['day'],
            'revenue': float(item['revenue']),
            'orders': item['orders']
        }
        for item in revenue_by_date
    ]
    
    # Payment breakdown by method
    payment_breakdown = {
        'by_method': {},
        'by_status': {},
        'total_paid': 0,
        'total_pending': 0,
        'total_failed': 0
    }
    
    paid_orders = orders_query.filter(payment_status='paid')
    for method in ['mpesa', 'cod', 'card', 'paypal', 'airtel']:
        count = paid_orders.filter(payment_method=method).count()
        amount = paid_orders.filter(payment_method=method).aggregate(
            total=Sum('total')
        )['total'] or 0
        if count > 0:
            payment_breakdown['by_method'][method] = {
                'count': count,
                'amount': float(amount)
            }
    
    payment_breakdown['by_status'] = {
        'paid': orders_query.filter(payment_status='paid').count(),
        'pending': orders_query.filter(payment_status='pending').count(),
        'failed': orders_query.filter(payment_status='failed').count(),
    }
    payment_breakdown['total_paid'] = float(
        orders_query.filter(payment_status='paid').aggregate(total=Sum('total'))['total'] or 0
    )
    payment_breakdown['total_pending'] = float(
        orders_query.filter(payment_status='pending').aggregate(total=Sum('total'))['total'] or 0
    )
    payment_breakdown['total_failed'] = float(
        orders_query.filter(payment_status='failed').aggregate(total=Sum('total'))['total'] or 0
    )
    
    # Financial summary (settlements, fees, net earnings)
    settlements = PaymentSettlement.objects.filter(business=business)
    if start_date and end_date:
        settlements = settlements.filter(settled_at__date__gte=start_date, settled_at__date__lte=end_date)
    
    financial_summary = {
        'gross_revenue': float(total_revenue),
        'total_settlements': settlements.count(),
        'total_fees': float(settlements.aggregate(total=Sum('fee'))['total'] or 0),
        'net_earnings': float(settlements.aggregate(total=Sum('net_amount'))['total'] or 0),
        'pending_settlements': orders_query.filter(
            payment_status='paid',
            payment__is_settled=False
        ).count(),
        'pending_settlement_amount': float(
            orders_query.filter(
                payment_status='paid',
                payment__is_settled=False
            ).aggregate(total=Sum('total'))['total'] or 0
        ),
        'average_order_value': float(paid_orders.aggregate(avg=Avg('total'))['avg'] or 0),
        'highest_order': float(paid_orders.aggregate(max=Max('total'))['max'] or 0),
    }
    
    data = {
        'total_orders': total_orders,
        'total_revenue': float(total_revenue),
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'total_products': total_products,
        'active_products': active_products,
        'out_of_stock': out_of_stock,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'revenue_trend': revenue_trend,
        'payment_breakdown': payment_breakdown,
        'financial_summary': financial_summary
    }
    
    serializer = SellerDashboardSerializer(data)
    return Response(serializer.data)


@extend_schema(
    responses=inline_serializer(
        name='SellerSalesStatsResponse',
        fields={
            'total_sales': drf_serializers.FloatField(),
            'total_orders': drf_serializers.IntegerField(),
            'average_order_value': drf_serializers.FloatField(),
            'by_status': drf_serializers.DictField(),
            'by_payment_status': drf_serializers.DictField(),
        },
    ),
    description='Detailed sales statistics for seller',
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSellerPermission])
def seller_sales_stats(request):
    """Detailed sales statistics for seller"""
    user = request.user
    
    try:
        business = Business.objects.get(owner=user)
    except Business.DoesNotExist:
        return Response(
            {"error": "No business found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    period = request.GET.get('period', '30')  # days
    days = int(period)
    start_date = timezone.now() - timedelta(days=days)
    
    orders = Order.objects.filter(business=business, created_at__gte=start_date)
    
    stats = {
        'total_sales': float(orders.filter(payment_status='paid').aggregate(total=Sum('total'))['total'] or 0),
        'total_orders': orders.count(),
        'average_order_value': float(orders.filter(payment_status='paid').aggregate(avg=Avg('total'))['avg'] or 0),
        'by_status': {
            'pending': orders.filter(status='pending').count(),
            'processing': orders.filter(status='processing').count(),
            'shipped': orders.filter(status='shipped').count(),
            'delivered': orders.filter(status='delivered').count(),
            'cancelled': orders.filter(status='cancelled').count(),
        },
        'by_payment_status': {
            'paid': orders.filter(payment_status='paid').count(),
            'pending': orders.filter(payment_status='pending').count(),
            'failed': orders.filter(payment_status='failed').count(),
        }
    }
    
    return Response(stats)


# ==================== ADMIN DASHBOARD ====================

@extend_schema(responses=AdminDashboardSerializer, description='Admin dashboard overview with platform-wide metrics, user management, and payment analytics')
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminPermission])
def admin_overview(request):
    """
    Admin dashboard overview with platform-wide metrics, user management, and payment analytics
    Query params: start_date, end_date (YYYY-MM-DD)
    """
    # Date range filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # User statistics
    total_users = CustomUser.objects.filter(is_active=True).count()
    total_sellers = CustomUser.objects.filter(is_seller=True, is_active=True).count()
    total_buyers = CustomUser.objects.filter(is_seller=False, is_admin=False, is_active=True).count()
    
    # Business statistics
    total_businesses = Business.objects.filter(is_verified=True).count()
    
    # Product statistics
    total_products = Product.objects.count()
    
    # Order statistics
    orders_query = Order.objects.all()
    
    if start_date and end_date:
        orders_query = orders_query.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    
    total_orders = orders_query.count()
    pending_orders = orders_query.filter(status='pending').count()
    total_revenue = orders_query.filter(
        payment_status='paid'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    # All users with detail (paginated latest 50)
    all_users_query = CustomUser.objects.all().order_by('-date_joined')[:50]
    recent_users = [
        {
            'id': user.id,
            'email': user.email,
            'name': f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
            'phone': user.phone_number,
            'is_active': user.is_active,
            'is_seller': user.is_seller,
            'is_admin': user.is_admin,
            'is_verified': user.is_verified,
            'auth_provider': user.auth_provider,
            'date_joined': user.date_joined,
            'last_login': user.last_login,
        }
        for user in all_users_query
    ]
    
    # Deactivated users count
    deactivated_users = CustomUser.objects.filter(is_active=False).count()
    
    # Recent orders (last 10)
    recent_orders = OrderListSerializer(
        orders_query.order_by('-created_at')[:10],
        many=True
    ).data
    
    # Revenue trend (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    revenue_by_date = orders_query.filter(
        created_at__gte=thirty_days_ago,
        payment_status='paid'
    ).extra(
        select={'day': 'date(created_at)'}
    ).values('day').annotate(
        revenue=Sum('total'),
        orders=Count('id')
    ).order_by('day')
    
    revenue_trend = [
        {
            'date': item['day'],
            'revenue': float(item['revenue']),
            'orders': item['orders']
        }
        for item in revenue_by_date
    ]
    
    # Top selling products across platform
    top_products_data = OrderItem.objects.filter(
        order__payment_status='paid'
    ).values(
        'product__id',
        'product__name',
        'product__business__name'
    ).annotate(
        sales_count=Count('id'),
        revenue=Sum(F('quantity') * F('price'))
    ).order_by('-revenue')[:10]
    
    top_selling_products = []
    for item in top_products_data:
        product = Product.objects.filter(id=item['product__id']).first()
        top_selling_products.append({
            'id': item['product__id'],
            'name': item['product__name'],
            'business': item['product__business__name'],
            'sales_count': item['sales_count'],
            'revenue': float(item['revenue']),
            'image': product.get_primary_image_url() if product else None
        })
    
    # User Analytics
    thirty_days_ago = timezone.now() - timedelta(days=30)
    seven_days_ago = timezone.now() - timedelta(days=7)
    
    user_analytics = {
        'total_active': total_users,
        'total_deactivated': deactivated_users,
        'new_users_30d': CustomUser.objects.filter(date_joined__gte=thirty_days_ago).count(),
        'new_users_7d': CustomUser.objects.filter(date_joined__gte=seven_days_ago).count(),
        'new_sellers_30d': CustomUser.objects.filter(
            is_seller=True,
            date_joined__gte=thirty_days_ago
        ).count(),
        'verified_users': CustomUser.objects.filter(is_verified=True).count(),
        'unverified_users': CustomUser.objects.filter(is_verified=False).count(),
        'active_buyers_30d': Order.objects.filter(
            created_at__gte=thirty_days_ago
        ).values('user').distinct().count(),
        'google_auth_users': CustomUser.objects.filter(auth_provider='google').count(),
        'email_auth_users': CustomUser.objects.filter(auth_provider='email').count(),
        'user_growth_rate': 0,
        'seller_conversion_rate': 0,
    }
    
    # Calculate growth rates
    sixty_days_ago = timezone.now() - timedelta(days=60)
    users_previous_30d = CustomUser.objects.filter(
        date_joined__gte=sixty_days_ago,
        date_joined__lt=thirty_days_ago
    ).count()
    if users_previous_30d > 0:
        user_analytics['user_growth_rate'] = round(
            ((user_analytics['new_users_30d'] - users_previous_30d) / users_previous_30d) * 100,
            2
        )
    
    if total_users > 0:
        user_analytics['seller_conversion_rate'] = round(
            (total_sellers / total_users) * 100,
            2
        )
    
    # Payment Analytics
    all_payments = Payment.objects.all()
    if start_date and end_date:
        all_payments = all_payments.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    
    payment_analytics = {
        'total_payments': all_payments.count(),
        'confirmed_payments': all_payments.filter(is_confirmed=True).count(),
        'pending_payments': all_payments.filter(is_confirmed=False).count(),
        'by_method': {},
        'total_processed': float(all_payments.filter(is_confirmed=True).aggregate(
            total=Sum('amount')
        )['total'] or 0),
        'total_settlements': PaymentSettlement.objects.count(),
        'total_fees_collected': float(PaymentSettlement.objects.aggregate(
            total=Sum('fee')
        )['total'] or 0),
        'pending_settlements': all_payments.filter(
            is_confirmed=True,
            is_settled=False
        ).count(),
        'pending_settlement_value': float(all_payments.filter(
            is_confirmed=True,
            is_settled=False
        ).aggregate(total=Sum('amount'))['total'] or 0),
        'average_transaction': float(all_payments.filter(is_confirmed=True).aggregate(
            avg=Avg('amount')
        )['avg'] or 0),
    }
    
    # Payment by method breakdown
    for method_code, method_name in Payment.PAYMENT_METHODS:
        count = all_payments.filter(method=method_code, is_confirmed=True).count()
        amount = all_payments.filter(method=method_code, is_confirmed=True).aggregate(
            total=Sum('amount')
        )['total'] or 0
        if count > 0:
            payment_analytics['by_method'][method_code] = {
                'name': method_name,
                'count': count,
                'amount': float(amount),
                'percentage': round((count / payment_analytics['confirmed_payments']) * 100, 2) if payment_analytics['confirmed_payments'] > 0 else 0
            }
    
    # Business Analytics
    all_businesses = Business.objects.annotate(
        total_revenue=Sum(
            'orders__total',
            filter=Q(orders__payment_status='paid')
        ),
        order_count=Count('orders'),
        product_count=Count('products')
    )
    
    business_analytics = {
        'total': Business.objects.count(),
        'total_verified': Business.objects.filter(is_verified=True).count(),
        'total_unverified': Business.objects.filter(is_verified=False).count(),
        'pending_verification': Business.objects.filter(verification_status='pending').count(),
        'rejected': Business.objects.filter(verification_status='rejected').count(),
        'new_businesses_30d': Business.objects.filter(created_at__gte=thirty_days_ago).count(),
        'new_businesses_7d': Business.objects.filter(created_at__gte=seven_days_ago).count(),
        'by_type': {},
        'businesses': [],
    }
    
    # Businesses by type
    for btype_code, btype_name in Business.CATEGORY_TYPE:
        count = Business.objects.filter(business_type=btype_code).count()
        if count > 0:
            business_analytics['by_type'][btype_code] = {
                'name': btype_name,
                'count': count
            }
    
    # Full business listing with owner info, stats, verification status
    for biz in all_businesses.order_by('-created_at')[:50]:
        business_analytics['businesses'].append({
            'id': biz.id,
            'name': biz.name,
            'slug': biz.slug,
            'business_type': biz.get_business_type_display(),
            'is_verified': biz.is_verified,
            'verification_status': biz.verification_status,
            'kra_pin': biz.kra_pin,
            'business_reg_no': biz.business_reg_no,
            'owner': {
                'id': biz.owner.id,
                'email': biz.owner.email,
                'name': f"{biz.owner.first_name or ''} {biz.owner.last_name or ''}".strip() or biz.owner.email,
                'phone': biz.owner.phone_number,
                'is_active': biz.owner.is_active,
            },
            'products': biz.product_count,
            'orders': biz.order_count,
            'revenue': float(biz.total_revenue or 0),
            'created_at': biz.created_at,
            'verified_at': biz.verified_at,
        })
    
    data = {
        'total_users': total_users,
        'total_sellers': total_sellers,
        'total_buyers': total_buyers,
        'total_businesses': total_businesses,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': float(total_revenue),
        'pending_orders': pending_orders,
        'recent_users': recent_users,
        'recent_orders': recent_orders,
        'revenue_trend': revenue_trend,
        'top_selling_products': top_selling_products,
        'user_analytics': user_analytics,
        'payment_analytics': payment_analytics,
        'business_analytics': business_analytics
    }
    
    serializer = AdminDashboardSerializer(data)
    return Response(serializer.data)


@extend_schema(
    responses=inline_serializer(
        name='AdminPlatformStatsResponse',
        fields={
            'users': drf_serializers.DictField(),
            'businesses': drf_serializers.DictField(),
            'products': drf_serializers.DictField(),
            'orders': drf_serializers.DictField(),
            'revenue': drf_serializers.DictField(),
        },
    ),
    description='Detailed platform statistics',
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminPermission])
def admin_platform_stats(request):
    """Detailed platform statistics"""
    period = request.GET.get('period', '30')  # days
    days = int(period)
    start_date = timezone.now() - timedelta(days=days)
    
    stats = {
        'users': {
            'total': CustomUser.objects.filter(is_active=True).count(),
            'new': CustomUser.objects.filter(date_joined__gte=start_date).count(),
            'sellers': CustomUser.objects.filter(is_seller=True).count(),
            'buyers': CustomUser.objects.filter(is_seller=False, is_admin=False).count(),
        },
        'businesses': {
            'total': Business.objects.count(),
            'verified': Business.objects.filter(is_verified=True).count(),
            'pending': Business.objects.filter(verification_status='pending').count(),
            'new': Business.objects.filter(created_at__gte=start_date).count(),
        },
        'products': {
            'total': Product.objects.count(),
            'active': Product.objects.filter(is_active=True).count(),
            'out_of_stock': Product.objects.filter(stock_qty=0).count(),
        },
        'orders': {
            'total': Order.objects.filter(created_at__gte=start_date).count(),
            'by_status': {
                'pending': Order.objects.filter(status='pending', created_at__gte=start_date).count(),
                'processing': Order.objects.filter(status='processing', created_at__gte=start_date).count(),
                'shipped': Order.objects.filter(status='shipped', created_at__gte=start_date).count(),
                'delivered': Order.objects.filter(status='delivered', created_at__gte=start_date).count(),
                'cancelled': Order.objects.filter(status='cancelled', created_at__gte=start_date).count(),
            }
        },
        'revenue': {
            'total': float(Order.objects.filter(
                payment_status='paid',
                created_at__gte=start_date
            ).aggregate(total=Sum('total'))['total'] or 0),
            'average_order': float(Order.objects.filter(
                payment_status='paid',
                created_at__gte=start_date
            ).aggregate(avg=Avg('total'))['avg'] or 0),
        }
    }
    
    return Response(stats)


# ==================== BUYER DASHBOARD ====================

@extend_schema(responses=BuyerDashboardSerializer, description='Buyer dashboard overview with order history and stats')
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsBuyerPermission])
def buyer_overview(request):
    """
    Buyer dashboard overview with order history and stats
    Query params: start_date, end_date (YYYY-MM-DD)
    """
    user = request.user
    
    # Date range filtering
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    orders_query = Order.objects.filter(user=user)
    
    if start_date and end_date:
        orders_query = orders_query.filter(created_at__date__gte=start_date, created_at__date__lte=end_date)
    
    # Order statistics
    total_orders = orders_query.count()
    pending_orders = orders_query.filter(status__in=['pending', 'processing']).count()
    completed_orders = orders_query.filter(status='delivered').count()
    cancelled_orders = orders_query.filter(status='cancelled').count()
    
    # Spending statistics
    total_spent = orders_query.filter(
        payment_status='paid'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')
    
    # Recent orders (last 10)
    recent_orders = OrderListSerializer(
        orders_query.order_by('-created_at')[:10],
        many=True
    ).data
    
    # Favorite categories (based on order items)
    favorite_categories_data = OrderItem.objects.filter(
        order__user=user,
        order__payment_status='paid'
    ).values(
        'product__category__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    favorite_categories = [
        {
            'name': item['product__category__name'],
            'order_count': item['count']
        }
        for item in favorite_categories_data
        if item['product__category__name']
    ]
    
    data = {
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
        'total_spent': float(total_spent),
        'recent_orders': recent_orders,
        'favorite_categories': favorite_categories
    }
    
    serializer = BuyerDashboardSerializer(data)
    return Response(serializer.data)


@extend_schema(
    responses=inline_serializer(
        name='BuyerOrderStatsResponse',
        fields={
            'total_orders': drf_serializers.IntegerField(),
            'total_spent': drf_serializers.FloatField(),
            'average_order_value': drf_serializers.FloatField(),
            'by_status': drf_serializers.DictField(),
            'by_payment_method': drf_serializers.DictField(),
        },
    ),
    description='Detailed order statistics for buyer',
)
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsBuyerPermission])
def buyer_order_stats(request):
    """Detailed order statistics for buyer"""
    user = request.user
    
    period = request.GET.get('period', '90')  # days
    days = int(period)
    start_date = timezone.now() - timedelta(days=days)
    
    orders = Order.objects.filter(user=user, created_at__gte=start_date)
    
    stats = {
        'total_orders': orders.count(),
        'total_spent': float(orders.filter(payment_status='paid').aggregate(total=Sum('total'))['total'] or 0),
        'average_order_value': float(orders.filter(payment_status='paid').aggregate(avg=Avg('total'))['avg'] or 0),
        'by_status': {
            'pending': orders.filter(status='pending').count(),
            'processing': orders.filter(status='processing').count(),
            'shipped': orders.filter(status='shipped').count(),
            'delivered': orders.filter(status='delivered').count(),
            'cancelled': orders.filter(status='cancelled').count(),
        },
        'by_payment_method': {
            'mpesa': orders.filter(payment_method='mpesa').count(),
            'cod': orders.filter(payment_method='cod').count(),
        }
    }
    
    return Response(stats)


# ==================== ADMIN MANAGEMENT ACTIONS ====================

@extend_schema(
    request=inline_serializer(
        name='AdminManageUserRequest',
        fields={'action': drf_serializers.CharField()},
    ),
    responses=inline_serializer(
        name='AdminManageUserResponse',
        fields={
            'message': drf_serializers.CharField(),
            'user': drf_serializers.DictField(),
        },
    ),
    description='Admin action to manage a user account',
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminPermission])
def admin_manage_user(request, user_id):
    """
    Admin action to manage a user account.
    Actions: activate, deactivate, make_seller, remove_seller, make_admin, remove_admin, verify, unverify
    Body: { "action": "deactivate" }
    """
    try:
        target_user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return Response(
            {"error": "User not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Prevent admin from modifying their own account
    if target_user.id == request.user.id:
        return Response(
            {"error": "Cannot modify your own account from dashboard"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    action = request.data.get('action')
    
    valid_actions = [
        'activate', 'deactivate',
        'make_seller', 'remove_seller',
        'make_admin', 'remove_admin',
        'verify', 'unverify'
    ]
    
    if action not in valid_actions:
        return Response(
            {"error": f"Invalid action. Must be one of: {', '.join(valid_actions)}"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if action == 'deactivate':
        target_user.is_active = False
    elif action == 'activate':
        target_user.is_active = True
    elif action == 'make_seller':
        target_user.is_seller = True
    elif action == 'remove_seller':
        target_user.is_seller = False
    elif action == 'make_admin':
        target_user.is_admin = True
    elif action == 'remove_admin':
        target_user.is_admin = False
    elif action == 'verify':
        target_user.is_verified = True
    elif action == 'unverify':
        target_user.is_verified = False
    
    target_user.save()
    
    return Response({
        'message': f"User {target_user.email} has been updated: {action}",
        'user': {
            'id': target_user.id,
            'email': target_user.email,
            'name': f"{target_user.first_name or ''} {target_user.last_name or ''}".strip() or target_user.email,
            'is_active': target_user.is_active,
            'is_seller': target_user.is_seller,
            'is_admin': target_user.is_admin,
            'is_verified': target_user.is_verified,
        }
    })


@extend_schema(
    request=inline_serializer(
        name='AdminManageBusinessRequest',
        fields={'action': drf_serializers.CharField()},
    ),
    responses=inline_serializer(
        name='AdminManageBusinessResponse',
        fields={
            'message': drf_serializers.CharField(),
            'business': drf_serializers.DictField(),
        },
    ),
    description='Admin action to manage a business',
)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminPermission])
def admin_manage_business(request, business_id):
    """
    Admin action to manage a business.
    Actions: verify, reject, unverify
    Body: { "action": "verify" }
    """
    try:
        business = Business.objects.get(id=business_id)
    except Business.DoesNotExist:
        return Response(
            {"error": "Business not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    action = request.data.get('action')
    
    valid_actions = ['verify', 'reject', 'unverify']
    
    if action not in valid_actions:
        return Response(
            {"error": f"Invalid action. Must be one of: {', '.join(valid_actions)}"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if action == 'verify':
        business.is_verified = True
        business.verification_status = 'verified'
        business.verified_at = timezone.now()
    elif action == 'reject':
        business.is_verified = False
        business.verification_status = 'rejected'
        business.verified_at = None
    elif action == 'unverify':
        business.is_verified = False
        business.verification_status = 'pending'
        business.verified_at = None
    
    business.save()
    
    return Response({
        'message': f"Business '{business.name}' has been updated: {action}",
        'business': {
            'id': business.id,
            'name': business.name,
            'is_verified': business.is_verified,
            'verification_status': business.verification_status,
            'verified_at': business.verified_at,
            'owner': {
                'id': business.owner.id,
                'email': business.owner.email,
                'name': f"{business.owner.first_name or ''} {business.owner.last_name or ''}".strip() or business.owner.email,
            }
        }
    })
