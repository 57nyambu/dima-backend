from apps.business.models import Business
from apps.accounts.models import CustomUser
from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
from mptt.models import MPTTModel, TreeForeignKey
from imagekit.processors import ResizeToFill
from imagekit.models import ImageSpecField
from django.core.exceptions import ValidationError


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


class CategoryImage(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='categories/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_feature = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

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
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.category}) - {self.price}"
    
def upload_to(instance, filename):
    return f'products/{instance.product.slug}/{filename}'

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    original = models.ImageField(upload_to='product_images/%Y/%m/', max_length=255)
    thumbnail = ImageSpecField(source='original', processors=[ResizeToFill(300, 300)], format='JPEG', options={'quality': 85})
    medium = ImageSpecField(source='original', processors=[ResizeToFill(600, 600)], format='JPEG', options={'quality': 90})
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
        if self.is_primary:
            # Unset is_primary for other images of this product
            ProductImage.objects.filter(product=self.product, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)

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