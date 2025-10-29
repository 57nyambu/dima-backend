# marketplace/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from apps.products.models import Product, ProductReview
from apps.business.models import BusinessReview
from .models import ProductSearchIndex, VendorSearchIndex
from .services import NotificationService
from django.db import models


@receiver(post_save, sender=Product)
def update_product_search_index(sender, instance, **kwargs):
    """Update product search index when product is saved"""
    if instance.is_active:
        search_index, created = ProductSearchIndex.objects.get_or_create(
            product=instance
        )
        
        # Update denormalized fields
        search_index.business_name = instance.business.name
        search_index.business_verified = instance.business.is_verified
        search_index.category_name = instance.category.name
        search_index.sales_count = instance.sales_count
        search_index.wishlist_count = instance.wishlist_count if hasattr(instance, 'wishlist_count') else 0
        search_index.save()
        
        # Clear related cache
        cache.delete('homepage_data:anonymous')


@receiver(post_delete, sender=Product)
def delete_product_search_index(sender, instance, **kwargs):
    """Delete search index when product is deleted"""
    try:
        instance.search_index.delete()
    except ProductSearchIndex.DoesNotExist:
        pass


@receiver(post_save, sender=ProductReview)
def handle_product_review(sender, instance, created, **kwargs):
    """Handle new product reviews"""
    if created:
        # Send notification to vendor
        NotificationService.send_review_notification(
            instance.product, 
            instance.user, 
            instance.rating
        )
        
        # Update search index
        try:
            search_index = instance.product.search_index
            search_index.avg_rating = instance.product.reviews.aggregate(
                avg=models.Avg('rating')
            )['avg'] or 0.0
            search_index.review_count = instance.product.reviews.count()
            search_index.save()
        except ProductSearchIndex.DoesNotExist:
            pass


@receiver(post_save, sender=BusinessReview)
def handle_business_review(sender, instance, created, **kwargs):
    """Handle new business reviews"""
    if created:
        # Update vendor search index
        try:
            search_index = instance.product.search_index  # product is actually business
            search_index.avg_rating = instance.product.reviews.aggregate(
                avg=models.Avg('rating')
            )['avg'] or 0.0
            search_index.review_count = instance.product.reviews.count()
            search_index.save()
        except VendorSearchIndex.DoesNotExist:
            pass


