# marketplace/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import (
    MarketplaceSettings, FeaturedProduct, Banner, 
    ProductSearchIndex, VendorSearchIndex,
    Cart, CartItem, Wishlist, WishlistItem,
    ProductComparison, MarketplaceDispute, DisputeMessage,
    MarketplaceNotification
)


@admin.register(MarketplaceSettings)
class MarketplaceSettingsAdmin(admin.ModelAdmin):
    list_display = ['site_name', 'commission_rate', 'currency', 'updated_at']
    fieldsets = [
        ('Basic Settings', {
            'fields': ['site_name', 'currency', 'commission_rate', 'tax_rate', 'min_order_amount']
        }),
        ('Limits', {
            'fields': ['max_products_per_order']
        }),
        ('Features', {
            'fields': ['enable_reviews', 'enable_wishlist', 'enable_comparison', 'enable_vendor_chat']
        })
    ]


@admin.register(FeaturedProduct)
class FeaturedProductAdmin(admin.ModelAdmin):
    list_display = ['product', 'title', 'position', 'is_active', 'start_date', 'end_date']
    list_filter = ['is_active', 'start_date', 'end_date']
    search_fields = ['product__name', 'title']
    ordering = ['position', '-created_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product__business')


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ['title', 'banner_type', 'position', 'is_active', 'start_date', 'end_date']
    list_filter = ['banner_type', 'is_active', 'start_date']
    search_fields = ['title', 'subtitle']
    ordering = ['position', '-created_at']
    
    def image_preview(self, obj):
        if obj.original:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 100px;" />',
                obj.original.url
            )
        return "No image"
    image_preview.short_description = "Preview"


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ['subtotal']
    

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_items', 'total_amount', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['total_amount', 'total_items']
    inlines = [CartItemInline]
    
    def total_items(self, obj):
        return obj.total_items
    total_items.short_description = "Total Items"
    
    def total_amount(self, obj):
        return f"KES {obj.total_amount:.2f}"
    total_amount.short_description = "Total Amount"


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'item_count', 'updated_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    inlines = [WishlistItemInline]
    
    def item_count(self, obj):
        return obj.items.count()
    item_count.short_description = "Items"


@admin.register(ProductComparison)
class ProductComparisonAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'product_count', 'created_at']
    search_fields = ['user__email', 'name']
    filter_horizontal = ['products']
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = "Products"


class DisputeMessageInline(admin.TabularInline):
    model = DisputeMessage
    extra = 0
    readonly_fields = ['created_at']


@admin.register(MarketplaceDispute)
class MarketplaceDisputeAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject', 'buyer', 'seller', 'status', 'created_at']
    list_filter = ['status', 'dispute_type', 'created_at']
    search_fields = ['subject', 'buyer__email', 'seller__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [DisputeMessageInline]
    
    fieldsets = [
        ('Dispute Info', {
            'fields': ['id', 'dispute_type', 'subject', 'description', 'status']
        }),
        ('Parties', {
            'fields': ['buyer', 'seller', 'order']
        }),
        ('Resolution', {
            'fields': ['admin_notes', 'resolution_amount', 'resolved_by', 'resolved_at']
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at']
        })
    ]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('buyer', 'seller', 'order')


@admin.register(MarketplaceNotification)
class MarketplaceNotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['title', 'user__email', 'message']
    readonly_fields = ['created_at']
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} notifications marked as read.")
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
        self.message_user(request, f"{queryset.count()} notifications marked as unread.")
    mark_as_unread.short_description = "Mark selected notifications as unread"


@admin.register(ProductSearchIndex)
class ProductSearchIndexAdmin(admin.ModelAdmin):
    list_display = ['product', 'business_name', 'category_name', 'avg_rating', 'sales_count', 'updated_at']
    list_filter = ['business_verified', 'category_name', 'updated_at']
    search_fields = ['product__name', 'business_name']
    readonly_fields = ['search_vector', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')


@admin.register(VendorSearchIndex)
class VendorSearchIndexAdmin(admin.ModelAdmin):
    list_display = ['business', 'avg_rating', 'review_count', 'product_count', 'completion_rate', 'updated_at']
    list_filter = ['updated_at']
    search_fields = ['business__name']
    readonly_fields = ['search_vector', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('business')
