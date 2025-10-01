from django.conf import settings
from django.core.files.storage import FileSystemStorage

def get_image_storage():
    """
    Get the appropriate storage backend based on configuration
    """
    if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
        try:
            from apps.utils.storage import CloudImageStorage
            return CloudImageStorage()
        except ImportError:
            # Fallback to local storage if cloud storage is not available
            return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
    else:
        return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)

def get_upload_path_function(model_type='product'):
    """
    Get the appropriate upload path function based on storage backend
    """
    if getattr(settings, 'STORAGE_BACKEND', 'local') == 'cloud':
        if model_type == 'product':
            return cloud_product_image_path
        elif model_type == 'category':
            return cloud_category_image_path
    else:
        if model_type == 'product':
            return local_product_image_path
        elif model_type == 'category':
            return local_category_image_path
    
    # Fallback
    return local_product_image_path

# Cloud storage path functions
def cloud_product_image_path(instance, filename):
    """Generate optimized upload path for product images (cloud)"""
    try:
        from apps.utils.storage import generate_cloud_path
        return generate_cloud_path(instance, filename, 'originals')
    except ImportError:
        # Fallback to local path if cloud utils are not available
        return local_product_image_path(instance, filename)

def cloud_category_image_path(instance, filename):
    """Generate optimized upload path for category images (cloud)"""
    try:
        from apps.utils.storage import generate_cloud_path
        return generate_cloud_path(instance, filename, 'originals')
    except ImportError:
        # Fallback to local path if cloud utils are not available
        return local_category_image_path(instance, filename)

# Local storage path functions (your original setup)
def local_product_image_path(instance, filename):
    """Generate upload path for product images (local)"""
    return f'product_images/{instance.product.created_at.year}/{instance.product.created_at.month}/{filename}'

def local_category_image_path(instance, filename):
    """Generate upload path for category images (local)"""
    return f'categories/{instance.category.slug}/{filename}'