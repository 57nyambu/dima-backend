from django.db import models
from django.conf import settings
from django.core.files.storage import default_storage

class DynamicStorageImageField(models.ImageField):
    """
    ImageField that dynamically chooses storage backend based on settings
    """
    
    def __init__(self, *args, **kwargs):
        # Remove storage from kwargs if present to handle it dynamically
        if 'storage' in kwargs:
            kwargs.pop('storage')
        
        super().__init__(*args, **kwargs)
    
    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)
        
        # Set storage dynamically based on settings
        if hasattr(settings, 'STORAGE_BACKEND') and settings.STORAGE_BACKEND == 'cloud':
            try:
                from apps.utils.storage import CloudImageStorage
                self.storage = CloudImageStorage()
            except ImportError:
                # Fallback to default storage if cloud storage is not available
                self.storage = default_storage
        else:
            self.storage = default_storage