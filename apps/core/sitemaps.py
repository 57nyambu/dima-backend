"""
SEO Sitemap Views
Generates XML sitemaps for Google and other search engines
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from apps.products.models import Product
from apps.business.models import Business
from datetime import datetime


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages"""
    priority = 0.8
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        # Return list of static page names
        return ['landing', 'about', 'contact', 'products']

    def location(self, item):
        # Map to frontend URLs with full domain
        url_map = {
            'landing': 'https://dima.co.ke/',
            'about': 'https://dima.co.ke/about',
            'contact': 'https://dima.co.ke/contact',
            'products': 'https://dima.co.ke/products',
        }
        return url_map.get(item, 'https://dima.co.ke/')


class ProductSitemap(Sitemap):
    """Sitemap for all active products"""
    changefreq = 'daily'
    priority = 1.0
    protocol = 'https'

    def items(self):
        # Only include active products with valid data
        return Product.objects.filter(
            is_active=True
        ).select_related('business').order_by('-created_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        # Frontend product detail URL format with full domain
        slug = obj.name.lower().replace(' ', '-').replace('/', '-')
        return f'https://dima.co.ke/product/{obj.id}/{slug}'


class BusinessSitemap(Sitemap):
    """Sitemap for verified businesses/vendors"""
    changefreq = 'weekly'
    priority = 0.7
    protocol = 'https'

    def items(self):
        # Only verified businesses
        return Business.objects.filter(
            verification_status='verified'
        ).order_by('-created_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        # Frontend business/vendor URL with full domain
        slug = obj.name.lower().replace(' ', '-').replace('/', '-')
        return f'https://dima.co.ke/business/{obj.id}/{slug}'


class CategorySitemap(Sitemap):
    """Sitemap for product categories"""
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        # Get unique categories from products
        from apps.products.models import Category
        return Category.objects.filter(
            is_active=True
        ).order_by('name')

    def location(self, obj):
        # Frontend category URL with full domain
        slug = obj.name.lower().replace(' ', '-')
        return f'https://dima.co.ke/category/{slug}'


# Sitemap index combining all sitemaps
sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'businesses': BusinessSitemap,
    'categories': CategorySitemap,
}
