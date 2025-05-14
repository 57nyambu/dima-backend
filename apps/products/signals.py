# signals.py
from .models import ProductImage
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
import os

@receiver(pre_delete, sender=ProductImage)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes original file and all generated files when
    corresponding ProductImage object is deleted.
    """
    if instance.original:
        if os.path.isfile(instance.original.path):
            os.remove(instance.original.path)
    
    # Delete all generated files (thumbnails, etc.)
    for field in ['thumbnail', 'medium']:
        file = getattr(instance, field)
        if file and os.path.isfile(file.path):
            os.remove(file.path)

@receiver(post_save, sender=ProductImage)
def set_primary_image(sender, instance, created, **kwargs):
    """
    Ensures only one primary image exists per product
    """
    if instance.is_primary:
        ProductImage.objects.filter(
            product=instance.product
        ).exclude(
            pk=instance.pk
        ).update(is_primary=False)