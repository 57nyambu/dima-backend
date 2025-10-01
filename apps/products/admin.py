from django.contrib import admin
from django.utils.html import format_html
from .models import ProductImage, Product, Category, CategoryImage, ProductReview

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(CategoryImage)
class CategoryImageAdmin(admin.ModelAdmin):
    list_display = ('category', 'image_preview', 'is_feature', 'created_at')
    list_filter = ('is_feature', 'created_at')
    
    def image_preview(self, obj):
        return format_html(
            '<img src="{}" width="50" height="50" />',
            obj.original.url if obj.original else ''
        )
    image_preview.short_description = 'Image'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'category', 'price', 'discounted_price', 
                   'stock_qty', 'is_active', 'is_feature')
    list_filter = ('is_active', 'is_feature', 'category', 'business')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active', 'is_feature', 'stock_qty')

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'thumbnail_preview', 'is_primary')
    list_editable = ('is_primary',)
    list_filter = ('is_primary', 'created_at')
    
    def product_name(self, obj):
        return obj.product.name
    
    def thumbnail_preview(self, obj):
        return format_html(
            '<img src="{}" width="50" height="50" />',
            obj.thumbnail.url if obj.thumbnail else ''
        )
    thumbnail_preview.short_description = 'Thumbnail'

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__name', 'user__username', 'comment')