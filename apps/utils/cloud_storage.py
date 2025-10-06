"""Ultra-Simple Cloud Storage for Dima Image Server"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger('storage')

class CloudStorage:
    def __init__(self):
        self.base = settings.CLOUD_STORAGE_URL
        self.debug = settings.STORAGE_DEBUG
    
    def upload(self, file_obj, path):
        """Upload file, returns {success, path, url} or {success, error}"""
        try:
            file_obj.seek(0)
            files = {'file': (file_obj.name, file_obj, file_obj.content_type)}
            data = {'path': path}
            
            if self.debug:
                logger.debug(f"Upload: {file_obj.name} -> {path}")
            
            r = requests.post(f"{self.base}/qazsw-upload/", files=files, data=data, timeout=30)
            
            if r.status_code == 200:
                result = r.json()
                return {
                    'success': True,
                    'path': result['path'],
                    'url': f"{self.base}/qazsw/{result['path']}"
                }
            return {'success': False, 'error': f"Upload failed: {r.status_code}"}
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete(self, path):
        """Delete file"""
        try:
            r = requests.delete(f"{self.base}/qazsw-delete/", json={'path': path}, timeout=10)
            return r.status_code == 200
        except:
            return False
    
    def url(self, path):
        """Get original image URL"""
        return f"{self.base}/qazsw/{path}" if path else ''
    
    def thumb(self, path, w=None, h=None, q=None, f=None):
        """Get processed image URL"""
        if not path:
            return ''
        params = []
        if w: params.append(f"w={w}")
        if h: params.append(f"h={h}")
        if q: params.append(f"q={q}")
        if f: params.append(f"f={f}")
        url = f"{self.base}/process/{path}"
        return f"{url}?{'&'.join(params)}" if params else url
