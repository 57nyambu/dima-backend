# marketplace/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from apps.products.models import Product
from apps.business.models import Business
from apps.orders.models import Order
import uuid
from imagekit.processors import ResizeToFill
from imagekit.models import ImageSpecField

User = get_user_model()


class MarketplaceSettings(models.Model):
    """Global marketplace configuration"""
    site_name = models.CharField(max_length=100, default="Marketplace")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    currency = models.CharField(max_length=3, default="KES")
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    max_products_per_order = models.IntegerField(default=50)
    
    # Feature flags
    enable_reviews = models.BooleanField(default=True)
    enable_vendor_chat = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Marketplace Settings"
        verbose_name_plural = "Marketplace Settings"
    
    def __str__(self):
        return f"{self.site_name} Settings"


class FeaturedProduct(models.Model):
    """Products featured on homepage or category pages"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='featured_listings')
    title = models.CharField(max_length=200, help_text="Custom title for featuring")
    description = models.TextField(blank=True, help_text="Custom description for featuring")
    position = models.PositiveIntegerField(default=0, help_text="Display order")
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['position', '-created_at']
        indexes = [
            models.Index(fields=['is_active', 'start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"Featured: {self.product.name}"


def banner_image_path(instance, filename):
    """Generate upload path for banner images"""
    from apps.utils.storage_selector import get_upload_path_function
    path_func = get_upload_path_function('banner')
    return path_func(instance, filename) if hasattr(path_func, '__call__') else f'banner/{instance.title}/{filename}'


class Banner(models.Model):
    """Homepage and category page banners"""
    BANNER_TYPES = [
        ('hero', 'Hero Banner'),
        ('category', 'Category Banner'),
        ('promotional', 'Promotional Banner'),
        ('vendor', 'Vendor Spotlight'),
    ]
    
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    
    # Get storage backend based on settings
    from django.conf import settings
    from apps.utils.storage_selector import get_image_storage
    _storage = get_image_storage() if settings.STORAGE_BACKEND == 'cloud' else None
    
    original = models.ImageField(upload_to=banner_image_path, null=True, blank=True, storage=_storage)
    thumbnail_small = ImageSpecField(
        source='original',
        processors=[ResizeToFill(150, 150)],
        format='JPEG',
        options={'quality': 80}
    )
    # Medium size for category cards (300x200)
    thumbnail_medium = ImageSpecField(
        source='original',
        processors=[ResizeToFill(300, 200)],
        format='JPEG',
        options={'quality': 85}
    )
    # Larger size for category headers (600x300)
    thumbnail_large = ImageSpecField(
        source='original',
        processors=[ResizeToFill(600, 300)],
        format='JPEG',
        options={'quality': 90}
    )
    banner_type = models.CharField(max_length=20, choices=BANNER_TYPES)
    link_url = models.URLField(blank=True, help_text="Where banner should link to")
    link_text = models.CharField(max_length=50, blank=True, help_text="Call-to-action text")
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['position', '-created_at']
    
    def __str__(self):
        return f"{self.get_banner_type_display()}: {self.title}"


class ProductSearchIndex(models.Model):
    """Denormalized search index for fast product searches"""
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='search_index')
    search_vector = SearchVectorField()
    
    # Denormalized fields for fast filtering
    business_name = models.CharField(max_length=225)
    business_verified = models.BooleanField(default=False)
    category_name = models.CharField(max_length=100)
    category_path = models.TextField()  # Full category hierarchy
    price_range = models.CharField(max_length=20)  # e.g., "100-500"
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    review_count = models.IntegerField(default=0)
    
    # Popularity metrics
    view_count = models.IntegerField(default=0)
    sales_count = models.IntegerField(default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector']),
            models.Index(fields=['price_range']),
            models.Index(fields=['avg_rating']),
            models.Index(fields=['business_verified']),
        ]
    
    def __str__(self):
        return f"Search index for {self.product.name}"


class VendorSearchIndex(models.Model):
    """Denormalized search index for vendor searches"""
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name='search_index')
    search_vector = SearchVectorField()
    
    # Denormalized fields
    avg_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    review_count = models.IntegerField(default=0)
    product_count = models.IntegerField(default=0)
    order_count = models.IntegerField(default=0)
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            GinIndex(fields=['search_vector']),
            models.Index(fields=['avg_rating']),
            models.Index(fields=['completion_rate']),
        ]
    
    def __str__(self):
        return f"Search index for {self.business.name}"


class MarketplaceDispute(models.Model):
    """Disputes between buyers and sellers"""
    DISPUTE_TYPES = [
        ('product_not_received', 'Product Not Received'),
        ('product_damaged', 'Product Damaged/Defective'),
        ('wrong_product', 'Wrong Product Sent'),
        ('refund_issue', 'Refund Issue'),
        ('service_quality', 'Service Quality Issue'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='disputes')
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buyer_disputes')
    seller = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='seller_disputes')
    dispute_type = models.CharField(max_length=30, choices=DISPUTE_TYPES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # Resolution details
    admin_notes = models.TextField(blank=True)
    resolution_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_disputes')
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Dispute #{str(self.id)[:8]} - {self.subject}"


class DisputeMessage(models.Model):
    """Messages within dispute conversations"""
    dispute = models.ForeignKey(MarketplaceDispute, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dispute_messages')
    message = models.TextField()
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message in dispute #{str(self.dispute.id)[:8]}"


class MarketplaceNotification(models.Model):
    """Notifications for marketplace events"""
    NOTIFICATION_TYPES = [
        ('order_placed', 'Order Placed'),
        ('order_confirmed', 'Order Confirmed'),
        ('order_shipped', 'Order Shipped'),
        ('order_delivered', 'Order Delivered'),
        ('payment_received', 'Payment Received'),
        ('dispute_opened', 'Dispute Opened'),
        ('dispute_resolved', 'Dispute Resolved'),
        ('product_review', 'Product Review'),
        ('vendor_review', 'Vendor Review'),
        ('stock_low', 'Low Stock Alert'),
        ('new_message', 'New Message'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marketplace_notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    # Optional references
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, null=True, blank=True)
    dispute = models.ForeignKey(MarketplaceDispute, on_delete=models.CASCADE, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.title} for {self.user.email}"