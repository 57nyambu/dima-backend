import os
import requests
import hashlib
from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils.deconstruct import deconstructible
from urllib.parse import urljoin
import logging
import time

logger = logging.getLogger('storage')

@deconstructible
class CloudImageStorage(Storage):
    """
    Django storage backend for cloud image server
    
    Simple integration:
    - Uploads images to /qazsw-upload/
    - Stores paths in database (e.g., "products/nike-air-max/main.jpg")
    - Generates URLs dynamically for originals and processed versions
    """
    
    def __init__(self):
        self.config = settings.CLOUD_MEDIA_SERVER
        self.base_url = self.config['BASE_URL']
        self.upload_endpoint = self.config['UPLOAD_ENDPOINT']
        self.delete_endpoint = self.config['DELETE_ENDPOINT']
        self.timeout = self.config.get('TIMEOUT', 30)
        self.retry_attempts = self.config.get('RETRY_ATTEMPTS', 3)
        self.retry_delay = self.config.get('RETRY_DELAY', 1)
        self.debug = settings.STORAGE_DEBUG
        
    def _log(self, message, level='info'):
        """Centralized logging with debug toggle"""
        if self.debug or level == 'error':
            log_func = getattr(logger, level, logger.info)
            log_func(f"[CloudStorage] {message}")
    
    def _retry_request(self, func, *args, **kwargs):
        """
        Retry logic with exponential backoff as per guide recommendations
        """
        for attempt in range(self.retry_attempts):
            try:
                return func(*args, **kwargs)
            except requests.RequestException as e:
                if attempt == self.retry_attempts - 1:
                    raise
                delay = self.retry_delay * (2 ** attempt)
                self._log(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay}s...", 'warning')
                time.sleep(delay)
        
    def _save(self, name, content):
        """
        Save file to cloud server
        
        Returns: path to store in database (e.g., "products/nike-air-max/main.jpg")
        """
        self._log(f"Uploading file: {name}")
        
        try:
            # Reset file pointer
            if hasattr(content, 'seek'):
                content.seek(0)
            
            # Prepare upload - pass full path
            files = {'file': content}
            data = {'path': name}
            
            # Upload with retry logic
            def upload():
                response = requests.post(
                    self.upload_endpoint,
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response
            
            response = self._retry_request(upload)
            result = response.json()
            
            stored_path = result.get('path')
            self._log(f"Upload successful: {stored_path}")
            
            # Return path to store in database
            return stored_path
                
        except Exception as e:
            self._log(f"Upload failed for {name}: {str(e)}", 'error')
            raise
    
    def _open(self, name, mode='rb'):
        """
        Open file from cloud server via original path
        """
        url = self.url(name)
        self._log(f"Opening file from: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self._log(f"File opened successfully: {name}")
                return ContentFile(response.content)
            else:
                raise FileNotFoundError(f"File {name} not found on cloud server (status: {response.status_code})")
        except Exception as e:
            self._log(f"Error opening {name}: {str(e)}", 'error')
            raise
    
    def exists(self, name):
        """
        Check if file exists on cloud server
        """
        url = self.url(name)
        try:
            response = requests.head(url, timeout=5)
            exists = response.status_code == 200
            self._log(f"File exists check for {name}: {exists}")
            return exists
        except:
            return False
    
    def delete(self, name):
        """
        Delete file from cloud server
        
        Per guide: Send DELETE request with path in JSON body
        Server removes main file and all cached/processed versions
        """
        self._log(f"Deleting file: {name}")
        
        try:
            response = requests.delete(
                self.delete_endpoint,
                json={'path': name},
                timeout=10
            )
            
            if response.status_code == 200:
                self._log(f"File deleted successfully: {name}")
                return True
            elif response.status_code == 404:
                self._log(f"File not found for deletion: {name}", 'warning')
                return True  # Already gone
            else:
                self._log(f"Delete failed with status {response.status_code}: {response.text}", 'error')
                return False
                
        except Exception as e:
            self._log(f"Error deleting {name}: {str(e)}", 'error')
            return False
    
    def url(self, name):
        """
        Return URL for accessing the ORIGINAL file
        
        Format: https://files.dima.co.ke/qazsw/products/nike-air-max/main.jpg
        """
        if not name:
            return ''
        
        clean_name = name.lstrip('/')
        return f"{self.base_url}/qazsw/{clean_name}"
    
    def size(self, name):
        """
        Get file size from cloud server
        """
        url = self.url(name)
        try:
            response = requests.head(url, timeout=5)
            size = int(response.headers.get('Content-Length', 0))
            self._log(f"File size for {name}: {size} bytes")
            return size
        except:
            return 0
    
    def get_processed_url(self, name, width=None, height=None, quality=None, format=None):
        """
        Generate URL for processed/resized image
        
        Args:
            name: Image path (e.g., 'products/nike-air-max/main.jpg')
            width: Target width in pixels
            height: Target height in pixels
            quality: Quality 10-100
            format: Output format ('jpeg', 'webp', 'avif')
        
        Returns: 
            https://files.dima.co.ke/process/products/nike-air-max/main.jpg?w=300&f=webp
        """
        if not name:
            return ''
        
        clean_name = name.lstrip('/')
        
        # Build query parameters
        params = []
        if width:
            params.append(f"w={width}")
        if height:
            params.append(f"h={height}")
        if quality:
            params.append(f"q={quality}")
        if format:
            params.append(f"f={format}")
        
        url = f"{self.base_url}/process/{clean_name}"
        return f"{url}?{'&'.join(params)}" if params else url


def generate_cloud_path(instance, filename):
    """
    Generate path for cloud upload
    
    Returns simple path like: 'products/nike-air-max/main.jpg'
    Server will handle the rest.
    """
    import uuid
    from django.utils.text import slugify
    
    # Get file extension
    name, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    # Validate extension
    supported = settings.CLOUD_MEDIA_SERVER.get('SUPPORTED_FORMATS', [])
    if ext.lstrip('.') not in supported:
        logger.warning(f"Unsupported format: {ext}. Supported: {supported}")
    
    # Generate clean filename
    clean_name = f"{slugify(name)[:50]}-{uuid.uuid4().hex[:8]}{ext}"
    
    # Determine prefix based on instance type
    if hasattr(instance, 'product'):
        # ProductImage
        prefix = f"products/{instance.product.slug}"
    elif hasattr(instance, 'category'):
        # CategoryImage
        prefix = f"categories/{instance.category.slug}"
    else:
        # Generic fallback
        prefix = "uploads"
    
    path = f"{prefix}/{clean_name}"
    logger.debug(f"Generated cloud path: {path}")
    return path