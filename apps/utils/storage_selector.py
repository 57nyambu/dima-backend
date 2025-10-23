from django.conf import settings
from django.core.files.storage import FileSystemStorage
import logging

logger = logging.getLogger('storage')

def get_image_storage():
    """
    Get the appropriate storage backend based on configuration
    
    Returns CloudImageStorage for cloud mode, FileSystemStorage for local mode
    """
    storage_backend = getattr(settings, 'STORAGE_BACKEND', 'local')
    
    if storage_backend == 'cloud':
        try:
            from apps.utils.storage import CloudImageStorage
            logger.info("Using CloudImageStorage backend")
            return CloudImageStorage()
        except ImportError as e:
            # Fallback to local storage if cloud storage is not available
            logger.warning(f"CloudImageStorage import failed: {e}. Falling back to local storage.")
            return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)
    else:
        logger.info("Using FileSystemStorage backend")
        return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)

def get_upload_path_function(model_type='product'):
    """
    Get the appropriate upload path function based on storage backend
    
    IMPORTANT: For cloud storage, returns simple path generator
    Cloud server handles date-based organization automatically (YYYY/MM/DD)
    """
    storage_backend = getattr(settings, 'STORAGE_BACKEND', 'local')
    
    if storage_backend == 'cloud':
        # Use simple cloud path - server organizes by date
        return cloud_image_path
    else:
        # Use traditional local paths with manual organization
        if model_type == 'product':
            return local_product_image_path
        elif model_type == 'category':
            return local_category_image_path
        else:
            return local_product_image_path

# Cloud storage path function (SIMPLIFIED per integration guide)
def cloud_image_path(instance, filename):
    """
    Generate simple filename for cloud upload
    
    The cloud server automatically organizes files into date-based folders (YYYY/MM/DD)
    and generates unique hashed filenames.
    
    We just need to provide a clean filename.
    """
    try:
        from apps.utils.storage import generate_cloud_path
        return generate_cloud_path(instance, filename)
    except ImportError:
        # Fallback to local path if cloud utils are not available
        logger.warning("Cloud path generator not available, using local path")
        if hasattr(instance, 'product'):
            return local_product_image_path(instance, filename)
        else:
            return local_category_image_path(instance, filename)

# Local storage path functions (your original setup)
def local_product_image_path(instance, filename):
    """Generate upload path for product images (local)"""
    import os
    from django.utils.text import slugify
    import uuid
    
    # Get extension - handle both full paths and just filenames
    basename = os.path.basename(filename)
    name, ext = os.path.splitext(basename)
    # Generate unique filename
    unique_name = f"{slugify(name)[:30]}-{uuid.uuid4().hex[:8]}{ext}"
    
    # Organize by product and date
    year = instance.product.created_at.year
    month = instance.product.created_at.month
    return f'product_images/{year}/{month}/{unique_name}'

def local_category_image_path(instance, filename):
    """Generate upload path for category images (local)"""
    import os
    from django.utils.text import slugify
    import uuid
    
    # Get extension - handle both full paths and just filenames
    basename = os.path.basename(filename)
    name, ext = os.path.splitext(basename)
    # Generate unique filename
    unique_name = f"{slugify(name)[:30]}-{uuid.uuid4().hex[:8]}{ext}"
    
    return f'categories/{instance.category.slug}/{unique_name}'


def get_image_url(file_field, size=None, format=None):
    """
    Generate appropriate URL for image based on storage backend
    
    For cloud storage: generates processed URLs for different sizes
    For local storage: returns the standard URL
    
    Args:
        file_field: Django ImageField or FileField instance
        size: String key from CLOUD_IMAGE_SIZES ('thumbnail_small', 'medium', etc.)
        format: Image format ('webp', 'jpeg', etc.) - defaults to 'webp'
    
    Returns:
        String URL
    
    Example:
        get_image_url(product.image, size='thumbnail_medium')
        get_image_url(product.image, size='medium', format='webp')
    """
    if not file_field:
        return ''
    
    storage_backend = getattr(settings, 'STORAGE_BACKEND', 'local')
    
    if storage_backend == 'cloud':
        try:
            storage = getattr(file_field, 'storage', None)
            
            # Default to webp for better performance
            if not format:
                format = 'webp'
            
            if size:
                # Get size configuration
                sizes = settings.CLOUD_IMAGE_SIZES
                size_config = sizes.get(size, {})
                
                if size_config and storage and hasattr(storage, 'get_processed_url'):
                    return storage.get_processed_url(
                        file_field.name,
                        width=size_config.get('width'),
                        height=size_config.get('height'),
                        quality=size_config.get('quality', 85),
                        format=format
                    )
            
            # No size or no storage method - return original
            base = settings.CLOUD_MEDIA_SERVER['BASE_URL'].rstrip('/')
            clean = file_field.name.lstrip('/')
            return f"{base}/qazsw/{clean}"
            
        except Exception as e:
            logger.error(f"Error generating cloud URL: {e}")
            return ''
    
    # Fallback to standard URL for local storage
    return file_field.url if file_field else ''


def get_original_image_url(file_field):
    """
    Return original image URL respecting cloud setup
    """
    if not file_field:
        return ''
    
    storage_backend = getattr(settings, 'STORAGE_BACKEND', 'local')
    
    if storage_backend == 'cloud':
        try:
            base = settings.CLOUD_MEDIA_SERVER['BASE_URL'].rstrip('/')
            clean = file_field.name.lstrip('/')
            return f"{base}/qazsw/{clean}"
        except Exception as e:
            logger.error(f"Error generating original cloud URL: {e}")
            return file_field.url
    
    return file_field.url