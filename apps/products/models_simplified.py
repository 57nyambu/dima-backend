"""Simplified Product Models with Cloud Storage"""
from apps.business.models import Business
from apps.accounts.models import CustomUser
from django.db import models
from django.conf import settings
import logging

logger = logging.getLogger('storage')

# Simple cloud storage helper
if settings.STORAGE_BACKEND == 'cloud':
    from apps.utils.cloud_storage import CloudStorage
    storage = CloudStorage()


class ProductImage(models.Model):
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='images')
    path = models.CharField(max_length=255)  # Stores relative path from image server
    alt_text = models.CharField(max_length=255, blank=True)
    is_feature = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Handle file upload for cloud storage
        if hasattr(self, '_file_to_upload') and settings.STORAGE_BACKEND == 'cloud':
            result = storage.upload(self._file_to_upload, f"products/{self._file_to_upload.name}")
            if result['success']:
                self.path = result['path']
                if settings.STORAGE_DEBUG:
                    logger.debug(f"Uploaded product image: {self.path}")
            else:
                raise Exception(f"Upload failed: {result.get('error')}")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Delete from cloud storage
        if self.path and settings.STORAGE_BACKEND == 'cloud':
            storage.delete(self.path)
        super().delete(*args, **kwargs)
    
    # Simple URL methods
    def get_url(self):
        """Get original image URL"""
        if settings.STORAGE_BACKEND == 'cloud':
            return storage.url(self.path)
        return f"/media/{self.path}"
    
    def get_thumbnail_small_url(self):
        """200x200 thumbnail"""
        if settings.STORAGE_BACKEND == 'cloud':
            return storage.thumb(self.path, w=200, h=200, q=80)
        return self.get_url()
    
    def get_thumbnail_medium_url(self):
        """400x400 thumbnail"""
        if settings.STORAGE_BACKEND == 'cloud':
            return storage.thumb(self.path, w=400, h=400, q=85)
        return self.get_url()
    
    def get_thumbnail_large_url(self):
        """800x800 thumbnail"""
        if settings.STORAGE_BACKEND == 'cloud':
            return storage.thumb(self.path, w=800, h=800, q=90)
        return self.get_url()
    
    def __str__(self):
        return f"{self.product.name} - Image"


class CategoryImage(models.Model):
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='images')
    path = models.CharField(max_length=255)
    alt_text = models.CharField(max_length=255, blank=True)
    is_feature = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if hasattr(self, '_file_to_upload') and settings.STORAGE_BACKEND == 'cloud':
            result = storage.upload(self._file_to_upload, f"categories/{self._file_to_upload.name}")
            if result['success']:
                self.path = result['path']
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        if self.path and settings.STORAGE_BACKEND == 'cloud':
            storage.delete(self.path)
        super().delete(*args, **kwargs)
    
    def get_url(self):
        if settings.STORAGE_BACKEND == 'cloud':
            return storage.url(self.path)
        return f"/media/{self.path}"
    
    def get_thumbnail_small_url(self):
        if settings.STORAGE_BACKEND == 'cloud':
            return storage.thumb(self.path, w=200, h=200, q=80)
        return self.get_url()
    
    def __str__(self):
        return f"{self.category.name} - Image"
