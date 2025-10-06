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
    Custom storage backend for Dima Image Server
    
    Following the integration guide from BACKEND_INTEGRATION.md:
    - Upload images to /qazsw-upload/
    - Store only paths in database (e.g., "2025/10/03/abc123def456.jpg")
    - Generate URLs dynamically for originals and processed versions
    - Handle automatic deduplication via file hash
    """
    
    def __init__(self):
        self.config = settings.CLOUD_MEDIA_SERVER
        self.base_url = self.config['BASE_URL']
        self.upload_endpoint = self.config['UPLOAD_ENDPOINT']
        self.delete_endpoint = self.config['DELETE_ENDPOINT']
        self.process_endpoint = self.config['PROCESS_ENDPOINT']
        self.original_path = self.config['ORIGINAL_PATH']
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
        
        CRITICAL: Returns ONLY the path (e.g., "2025/10/03/abc123.jpg")
        NOT the full URL. Store this path in your database.
        """
        self._log(f"Starting upload for: {name}")
        
        try:
            # Read content
            if hasattr(content, 'read'):
                content.seek(0)  # Reset file pointer
                file_content = content.read()
            else:
                file_content = content
            
            # Validate file size
            file_size = len(file_content)
            max_size = self.config.get('MAX_FILE_SIZE', 52428800)
            if file_size > max_size:
                raise ValueError(f"File size {file_size} exceeds maximum {max_size} bytes")
            
            self._log(f"File size: {file_size} bytes")
            
            # Prepare upload - use simple filename, server will organize by date
            # Extract just the filename without any path
            simple_name = os.path.basename(name)
            
            files = {'file': (simple_name, file_content)}
            data = {'path': simple_name}  # Server will add date-based path
            
            self._log(f"Uploading to: {self.upload_endpoint}")
            
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
            
            if response.status_code == 200:
                result = response.json()
                stored_path = result.get('path')
                file_status = result.get('status', 'uploaded')
                file_hash = result.get('hash', '')
                
                self._log(f"Upload successful - Status: {file_status}, Path: {stored_path}, Hash: {file_hash}")
                
                # IMPORTANT: Return ONLY the path, not full URL
                return stored_path
            else:
                error_msg = f"Upload failed with status {response.status_code}: {response.text}"
                self._log(error_msg, 'error')
                raise Exception(error_msg)
                
        except requests.RequestException as e:
            self._log(f"Network error uploading {name}: {str(e)}", 'error')
            raise
        except Exception as e:
            self._log(f"Error uploading {name}: {str(e)}", 'error')
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
        
        Format: https://files.dima.co.ke/qazsw/2025/10/03/abc123.jpg
        """
        if not name:
            return ''
        
        # Ensure name doesn't start with /
        clean_name = name.lstrip('/')
        
        # Construct URL using original path
        full_url = urljoin(self.base_url + self.original_path, clean_name)
        self._log(f"Generated URL for {name}: {full_url}")
        return full_url
    
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
        
        This is the KEY method for thumbnails and different sizes
        
        Usage:
            storage.get_processed_url(path, width=300, height=300)  # Thumbnail
            storage.get_processed_url(path, width=800)  # Medium (preserves aspect)
            storage.get_processed_url(path, width=800, format='webp')  # WebP format
        
        Returns: https://files.dima.co.ke/process/2025/10/03/abc123.jpg?w=300&h=300
        """
        if not name:
            return ''
        
        clean_name = name.lstrip('/')
        base_url = urljoin(self.process_endpoint, clean_name)
        
        # Build query parameters using short names as per guide
        params = []
        if width:
            params.append(f"w={width}")
        if height:
            params.append(f"h={height}")
        if quality:
            params.append(f"q={quality}")
        if format:
            params.append(f"f={format}")
        
        if params:
            full_url = f"{base_url}?{'&'.join(params)}"
        else:
            full_url = base_url
        
        self._log(f"Generated processed URL: {full_url}")
        return full_url


def generate_cloud_path(instance, filename):
    """
    Generate simple filename for cloud upload
    
    IMPORTANT: Don't create complex paths here!
    The cloud server organizes files by date automatically (YYYY/MM/DD)
    
    Just generate a unique filename with proper extension
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
    
    # Generate unique filename with hash
    # Format: slugified-name-hash.ext
    unique_filename = f"{slugify(name)[:50]}-{uuid.uuid4().hex[:12]}{ext}"
    
    logger.debug(f"Generated filename: {unique_filename}")
    return unique_filename