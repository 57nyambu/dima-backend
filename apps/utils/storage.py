import os
import requests
import tempfile
from django.core.files.storage import Storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils.deconstruct import deconstructible
from urllib.parse import urljoin
import logging

logger = logging.getLogger(__name__)

@deconstructible
class CloudImageStorage(Storage):
    """
    Custom storage backend for uploading images to cloud server with hidden path
    """
    
    def __init__(self, base_url=None, upload_endpoint=None):
        self.base_url = base_url or settings.CLOUD_MEDIA_SERVER['BASE_URL']
        # Upload endpoint uses the hidden path
        self.upload_endpoint = upload_endpoint or f"https://deploy.finarchitect.online/qazsw-upload/"
        
    def _save(self, name, content):
        """
        Save file to cloud server
        """
        try:
            # Read content
            if hasattr(content, 'read'):
                file_content = content.read()
            else:
                file_content = content
                
            # Prepare upload
            files = {'file': (name, file_content)}
            data = {'path': name}
            
            # Upload to cloud server
            response = requests.post(
                self.upload_endpoint,
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('path', name)
            else:
                logger.error(f"Failed to upload {name}: {response.text}")
                raise Exception(f"Upload failed: {response.text}")
                
        except Exception as e:
            logger.error(f"Error uploading {name}: {str(e)}")
            raise
    
    def _open(self, name, mode='rb'):
        """
        Open file from cloud server
        """
        url = urljoin(self.base_url, name)
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return ContentFile(response.content)
            else:
                raise FileNotFoundError(f"File {name} not found on cloud server")
        except Exception as e:
            logger.error(f"Error opening {name}: {str(e)}")
            raise
    
    def exists(self, name):
        """
        Check if file exists on cloud server
        """
        url = urljoin(self.base_url, name)
        try:
            response = requests.head(url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def delete(self, name):
        """
        Delete file from cloud server
        """
        try:
            delete_url = f"https://deploy.finarchitect.online/qazsw-delete/"
            response = requests.delete(delete_url, json={'path': name}, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error deleting {name}: {str(e)}")
            return False
    
    def url(self, name):
        """
        Return URL for accessing the file
        """
        return urljoin(self.base_url, name)
    
    def size(self, name):
        """
        Get file size from cloud server
        """
        url = urljoin(self.base_url, name)
        try:
            response = requests.head(url, timeout=5)
            return int(response.headers.get('Content-Length', 0))
        except:
            return 0


# Convenience function for generating optimized paths
def generate_cloud_path(instance, filename, subfolder=''):
    """
    Generate optimized cloud storage paths
    """
    import uuid
    from django.utils.text import slugify
    
    # Get file extension
    name, ext = os.path.splitext(filename)
    
    # Generate unique filename
    unique_filename = f"{slugify(name)}-{uuid.uuid4().hex[:8]}{ext}"
    
    # Create path based on model type
    if hasattr(instance, 'product'):
        return f"products/{instance.product.slug}/{subfolder}/{unique_filename}"
    elif hasattr(instance, 'category'):
        return f"categories/{instance.category.slug}/{subfolder}/{unique_filename}"
    else:
        return f"uploads/{subfolder}/{unique_filename}"