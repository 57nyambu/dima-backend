from django.contrib import admin
from .models import ProductImage

# admin.py
from django.utils.html import format_html

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'thumbnail_preview', 'is_primary')
    list_editable = ('is_primary',)
    
    def product_name(self, obj):
        return obj.product.name
    
    def thumbnail_preview(self, obj):
        return format_html(
            '<img src="{}" width="50" height="50" />',
            obj.thumbnail.url if obj.thumbnail else ''
        )
    
    thumbnail_preview.short_description = 'Thumbnail'
