from apps.business.models import Business
from apps.accounts.models import CustomUser
from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from mptt.models import MPTTModel, TreeForeignKey
from imagekit.processors import ResizeToFill
from imagekit.models import ImageSpecField
from django.core.exceptions import ValidationError
from django.conf import settings


class Category(MPTTModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class MPTTMeta:
        order_insertion_by = ['name']

    class Meta:
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


    def __str__(self):
        return self.name


def category_image_path(instance, filename):
    """Generate upload path for category images based on storage backend"""
    from apps.utils.storage_selector import get_upload_path_function
    path_func = get_upload_path_function('category')
    return path_func(instance, filename)

class CategoryImage(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='images')
    
    # Get storage backend based on settings
    from apps.utils.storage_selector import get_image_storage
    _storage = get_image_storage() if settings.STORAGE_BACKEND == 'cloud' else None
    
    original = models.ImageField(
        upload_to=category_image_path, 
        max_length=255, 
        null=True, 
        blank=True,
        storage=_storage
    )
    
    # ImageKit fields for LOCAL storage only
    # For cloud storage, we use the cloud server's /process/ endpoint instead
    if settings.STORAGE_BACKEND != 'cloud':
        # Small thumbnail for mobile category lists (150x150)
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
    
    alt_text = models.CharField(max_length=255, blank=True)
    is_feature = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_feature', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['category'],
                condition=models.Q(is_feature=True),
                name='unique_feature_image_per_category'
            )
        ]

    def save(self, *args, **kwargs):
        # Set storage backend dynamically
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
            from apps.utils.storage_selector import get_image_storage
            self.original.storage = get_image_storage()
        
        if self.is_feature:
            # Unset is_feature for other images of this category
            CategoryImage.objects.filter(
                category=self.category, 
                is_feature=True
            ).exclude(pk=self.pk).update(is_feature=False)
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Override delete to remove file from storage"""
        if self.original:
            # This will trigger cloud deletion if using cloud storage
            self.original.delete(save=False)
        super().delete(*args, **kwargs)
    
    def get_thumbnail_small_url(self):
        """Get URL for small thumbnail (150x150)"""
        if settings.STORAGE_BACKEND == 'cloud':
            from apps.utils.storage_selector import get_image_url
            return get_image_url(self.original, size='thumbnail_small')
        else:
            return self.thumbnail_small.url if self.original else ''
    
    def get_thumbnail_medium_url(self):
        """Get URL for medium thumbnail (300x200)"""
        if settings.STORAGE_BACKEND == 'cloud':
            from apps.utils.storage_selector import get_image_url
            return get_image_url(self.original, size='thumbnail_medium')
        else:
            return self.thumbnail_medium.url if self.original else ''
    
    def get_thumbnail_large_url(self):
        """Get URL for large thumbnail (600x300)"""
        if settings.STORAGE_BACKEND == 'cloud':
            from apps.utils.storage_selector import get_image_url
            return get_image_url(self.original, size='thumbnail_large')
        else:
            return self.thumbnail_large.url if self.original else ''

    def __str__(self):
        return f"Image for {self.category.name}"


class Product(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    #sku = models.CharField(max_length=100, unique=True)
    stock_qty = models.IntegerField(default=0)
    sales_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_feature = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        
        # Check if this is a new product
        is_new = self._state.adding
        
        super().save(*args, **kwargs)
        
        # Create or update search index after save
        if hasattr(self, 'search_index'):
            self.search_index.save()
        else:
            from apps.marketplace.models import ProductSearchIndex
            ProductSearchIndex.objects.create(product=self)

    def __str__(self):
        return f"{self.name} ({self.category}) - {self.price}"
    
    @property
    def effective_price(self):
        """Get the current effective price"""
        return self.discounted_price if self.discounted_price > 0 else self.price
    
    @property
    def discount_percentage(self):
        """Calculate discount percentage if applicable"""
        if self.discounted_price and self.discounted_price < self.price:
            return round((1 - self.discounted_price / self.price) * 100)
        return 0
    
    @property
    def is_in_stock(self):
        """Check if product is in stock"""
        return self.stock_qty > 0
    
    @property
    def is_low_stock(self):
        """Check if product is running low on stock (less than 10 units)"""
        return 0 < self.stock_qty < 10
    
    def increase_view_count(self):
        """Increment product view count"""
        if hasattr(self, 'search_index'):
            self.search_index.view_count += 1
            self.search_index.save(update_fields=['view_count'])
    
    def update_sales_count(self, quantity=1):
        """Update sales count after successful order"""
        self.sales_count += quantity
        self.save(update_fields=['sales_count'])
        
        if hasattr(self, 'search_index'):
            self.search_index.sales_count += quantity
            self.search_index.save(update_fields=['sales_count'])
    
def product_image_path(instance, filename):
    """Generate upload path for product images based on storage backend"""
    from apps.utils.storage_selector import get_upload_path_function
    path_func = get_upload_path_function('product')
    return path_func(instance, filename)

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    
    # Get storage backend based on settings
    from apps.utils.storage_selector import get_image_storage
    _storage = get_image_storage() if settings.STORAGE_BACKEND == 'cloud' else None
    
    original = models.ImageField(
        upload_to=product_image_path, 
        max_length=255,
        storage=_storage
    )
    
    # ImageKit fields for LOCAL storage only
    # For cloud storage, we use the cloud server's /process/ endpoint instead
    if settings.STORAGE_BACKEND != 'cloud':
        thumbnail = ImageSpecField(
            source='original', 
            processors=[ResizeToFill(300, 300)], 
            format='JPEG', 
            options={'quality': 85}
        )
        medium = ImageSpecField(
            source='original', 
            processors=[ResizeToFill(600, 600)], 
            format='JPEG', 
            options={'quality': 90}
        )
    
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product'],
                condition=models.Q(is_primary=True),
                name='unique_primary_image_per_product'
            )
        ]

    def save(self, *args, **kwargs):
        # Set storage backend dynamically
        if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
            from apps.utils.storage_selector import get_image_storage
            self.original.storage = get_image_storage()
        
        if self.is_primary:
            # Unset is_primary for other images of this product
            ProductImage.objects.filter(
                product=self.product, 
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Override delete to remove file from storage"""
        if self.original:
            # This will trigger cloud deletion if using cloud storage
            self.original.delete(save=False)
        super().delete(*args, **kwargs)
    
    def get_thumbnail_url(self):
        """Get URL for thumbnail (300x300)"""
        if settings.STORAGE_BACKEND == 'cloud':
            from apps.utils.storage_selector import get_image_url
            return get_image_url(self.original, size='thumbnail_medium')
        else:
            return self.thumbnail.url if self.original else ''
    
    def get_medium_url(self):
        """Get URL for medium size (600x600)"""
        if settings.STORAGE_BACKEND == 'cloud':
            from apps.utils.storage_selector import get_image_url
            return get_image_url(self.original, size='thumbnail_large')
        else:
            return self.medium.url if self.original else ''

    def __str__(self):
        return f"Image for {self.product.name}"
    

class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='product_reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    mpesa_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta():
        unique_together = ['product', 'user']

    def clean(self):
        if self.product.business.owner == self.user:
            raise ValidationError("You cannot review your own product.")

    def __str__(self):
        return f"{self.user.username}"