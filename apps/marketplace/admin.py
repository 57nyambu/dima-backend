# marketplace/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import (
    MarketplaceSettings, FeaturedProduct, Banner, 
    ProductSearchIndex, VendorSearchIndex,
    MarketplaceDispute, DisputeMessage,
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
            'fields': ['enable_reviews', 'enable_vendor_chat']
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
