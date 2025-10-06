"""
Storage utility functions for common operations
"""
from django.conf import settings
from apps.utils.storage_selector import get_image_storage
import logging

logger = logging.getLogger('storage')


def bulk_delete_images(paths):
    """
    Delete multiple images at once
    
    Args:
        paths: List of image paths to delete
    
    Returns:
        dict: {'success': int, 'failed': int, 'errors': []}
    """
    storage = get_image_storage()
    result = {
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    for path in paths:
        try:
            storage.delete(path)
            result['success'] += 1
            logger.info(f"Deleted: {path}")
        except Exception as e:
            result['failed'] += 1
            result['errors'].append({'path': path, 'error': str(e)})
            logger.error(f"Failed to delete {path}: {str(e)}")
    
    return result


def validate_image_file(file, max_size=None):
    """
    Validate image file before upload
    
    Args:
        file: Django UploadedFile object
        max_size: Maximum file size in bytes (defaults to settings)
    
    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    if not file:
        return False, "No file provided"
    
    # Check file size
    if max_size is None:
        max_size = settings.CLOUD_MEDIA_SERVER.get('MAX_FILE_SIZE', 52428800)
    
    if file.size > max_size:
        return False, f"File size {file.size} exceeds maximum {max_size} bytes"
    
    # Check file extension
    import os
    ext = os.path.splitext(file.name)[1].lower().lstrip('.')
    supported = settings.CLOUD_MEDIA_SERVER.get('SUPPORTED_FORMATS', [])
    
    if ext not in supported:
        return False, f"File format '{ext}' not supported. Supported formats: {', '.join(supported)}"
    
    return True, ""


def get_storage_info():
    """
    Get current storage configuration info
    
    Returns:
        dict: Storage configuration details
    """
    backend = settings.STORAGE_BACKEND
    
    info = {
        'backend': backend,
        'debug': settings.STORAGE_DEBUG,
    }
    
    if backend == 'cloud':
        config = settings.CLOUD_MEDIA_SERVER
        info.update({
            'base_url': config['BASE_URL'],
            'upload_endpoint': config['UPLOAD_ENDPOINT'],
            'max_file_size': config['MAX_FILE_SIZE'],
            'max_file_size_mb': config['MAX_FILE_SIZE'] / 1024 / 1024,
            'supported_formats': config['SUPPORTED_FORMATS'],
            'retry_attempts': config.get('RETRY_ATTEMPTS', 3),
        })
    else:
        info.update({
            'media_root': settings.MEDIA_ROOT,
            'media_url': settings.MEDIA_URL,
        })
    
    return info


def migrate_image_to_cloud(local_path):
    """
    Migrate a single image from local storage to cloud
    
    Args:
        local_path: Path to local file
    
    Returns:
        str: Cloud path or None if failed
    """
    if settings.STORAGE_BACKEND != 'cloud':
        logger.warning("Storage backend is not set to cloud")
        return None
    
    try:
        from django.core.files import File
        import os
        
        # Read local file
        full_path = os.path.join(settings.MEDIA_ROOT, local_path)
        if not os.path.exists(full_path):
            logger.error(f"Local file not found: {full_path}")
            return None
        
        with open(full_path, 'rb') as f:
            django_file = File(f)
            
            # Upload to cloud
            storage = get_image_storage()
            filename = os.path.basename(local_path)
            cloud_path = storage.save(filename, django_file)
            
            logger.info(f"Migrated {local_path} to {cloud_path}")
            return cloud_path
    
    except Exception as e:
        logger.error(f"Migration failed for {local_path}: {str(e)}")
        return None


def check_cloud_server_health():
    """
    Check if cloud storage server is healthy and accessible
    
    Returns:
        tuple: (bool, dict) - (is_healthy, status_info)
    """
    if settings.STORAGE_BACKEND != 'cloud':
        return False, {'error': 'Cloud storage not configured'}
    
    try:
        import requests
        config = settings.CLOUD_MEDIA_SERVER
        health_url = f"{config['BASE_URL']}/health"
        
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, {'status_code': response.status_code, 'error': 'Server returned non-200 status'}
    
    except requests.RequestException as e:
        return False, {'error': str(e)}
    except Exception as e:
        return False, {'error': f'Unexpected error: {str(e)}'}


def generate_responsive_image_urls(image_field):
    """
    Generate URLs for different responsive sizes
    
    Args:
        image_field: Django ImageField instance
    
    Returns:
        dict: URLs for different sizes
    """
    if not image_field:
        return {}
    
    storage = get_image_storage()
    urls = {
        'original': image_field.url,
    }
    
    if settings.STORAGE_BACKEND == 'cloud' and hasattr(storage, 'get_processed_url'):
        # Generate different sizes
        urls.update({
            'thumbnail': storage.get_processed_url(image_field.name, width=300, height=300),
            'small': storage.get_processed_url(image_field.name, width=640),
            'medium': storage.get_processed_url(image_field.name, width=1024),
            'large': storage.get_processed_url(image_field.name, width=1920),
            # WebP versions for modern browsers
            'thumbnail_webp': storage.get_processed_url(image_field.name, width=300, height=300, format='webp'),
            'medium_webp': storage.get_processed_url(image_field.name, width=1024, format='webp'),
        })
    
    return urls
