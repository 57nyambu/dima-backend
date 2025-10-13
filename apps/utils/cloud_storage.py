"""Simple Cloud Storage for Dima Image Server"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger('storage')

class CloudStorage:
    """Simple wrapper for image server operations"""
    
    def __init__(self):
        self.base = settings.CLOUD_STORAGE_URL
        self.debug = settings.STORAGE_DEBUG
    
    def upload(self, file_obj, path):
        """
        Upload file to image server
        Returns: {'success': True, 'path': '...', 'url': '...'} or {'success': False, 'error': '...'}
        """
        try:
            file_obj.seek(0)
            
            files = {'file': file_obj}
            data = {'path': path}
            
            if self.debug:
                logger.debug(f"Uploading to image server: {path}")
            
            response = requests.post(
                f"{self.base}/qazsw-upload/",
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'path': result['path'],
                    'url': f"{self.base}/qazsw/{result['path']}"
                }
            
            return {'success': False, 'error': f"Upload failed: {response.status_code}"}
            
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete(self, path):
        """Delete file from image server"""
        try:
            response = requests.delete(
                f"{self.base}/qazsw-delete/",
                json={'path': path},
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Delete error: {e}")
            return False
    
    def url(self, path):
        """Get original image URL"""
        if not path:
            return ''
        return f"{self.base}/qazsw/{path}"
    
    def processed_url(self, path, width=None, height=None, quality=None, format=None):
        """
        Get processed image URL with optional transformations
        
        Args:
            path: Image path (e.g., 'products/nike-air-max/main.jpg')
            width: Target width in pixels
            height: Target height in pixels
            quality: Quality 10-100 (default: 85)
            format: Output format ('jpeg', 'webp', 'avif')
        
        Returns:
            URL string for processed image
        """
        if not path:
            return ''
        
        params = []
        if width:
            params.append(f"w={width}")
        if height:
            params.append(f"h={height}")
        if quality:
            params.append(f"q={quality}")
        if format:
            params.append(f"f={format}")
        
        url = f"{self.base}/process/{path}"
        return f"{url}?{'&'.join(params)}" if params else url
