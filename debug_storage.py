import os
import django
import sys

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Root.settings.development')
django.setup()

from apps.products.models import ProductImage
from apps.utils.storage_selector import get_image_url
from django.conf import settings

print("\n=== Debugging Image Storage ===\n")

img = ProductImage.objects.first()
if img and img.original:
    print(f"ProductImage ID: {img.id}")
    print(f"Stored path: {img.original.name}")
    print(f"Has storage attr: {hasattr(img.original, 'storage')}")
    print(f"Storage type: {type(img.original.storage)}")
    print(f"Has get_processed_url: {hasattr(img.original.storage, 'get_processed_url')}")
    print(f"STORAGE_BACKEND setting: {settings.STORAGE_BACKEND}")
    
    print("\n--- Testing get_image_url ---")
    url = get_image_url(img.original, size='thumbnail_medium', format='webp')
    print(f"Result: {url}")
    
    print("\n--- Testing direct storage method ---")
    if hasattr(img.original.storage, 'get_processed_url'):
        direct_url = img.original.storage.get_processed_url(
            img.original.name,
            width=300,
            height=300,
            quality=85,
            format='webp'
        )
        print(f"Direct result: {direct_url}")
else:
    print("No ProductImage found!")
