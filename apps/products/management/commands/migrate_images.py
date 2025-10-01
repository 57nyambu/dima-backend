from django.core.management.base import BaseCommand
from django.conf import settings
from apps.products.models import ProductImage, CategoryImage
from apps.utils.storage import CloudImageStorage
from apps.utils.image_processing import ImageProcessingService
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Migrate existing images to cloud storage'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            type=str,
            choices=['product', 'category', 'all'],
            default='all',
            help='Which model images to migrate'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of images to process in each batch'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually doing it'
        )
    
    def handle(self, *args, **options):
        cloud_storage = CloudImageStorage()
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        
        if options['model'] in ['product', 'all']:
            self.migrate_product_images(cloud_storage, batch_size, dry_run)
        
        if options['model'] in ['category', 'all']:
            self.migrate_category_images(cloud_storage, batch_size, dry_run)
    
    def migrate_product_images(self, cloud_storage, batch_size, dry_run):
        self.stdout.write("Migrating product images...")
        
        images = ProductImage.objects.filter(original__isnull=False)
        total = images.count()
        
        self.stdout.write(f"Found {total} product images to migrate")
        
        if dry_run:
            for image in images[:10]:  # Show first 10 for preview
                self.stdout.write(f"Would migrate: {image.original.path}")
            return
        
        migrated = 0
        for i in range(0, total, batch_size):
            batch = images[i:i+batch_size]
            
            for image in batch:
                try:
                    if os.path.exists(image.original.path):
                        # Upload to cloud with hidden path structure
                        with open(image.original.path, 'rb') as f:
                            cloud_path = cloud_storage._save(
                                f"products/{image.product.slug}/original_{image.id}.jpg",
                                f
                            )
                        
                        # Update image URL to point to cloud (will automatically use qazsw path)
                        image.original.name = cloud_path
                        image.save()
                        
                        migrated += 1
                        self.stdout.write(f"Migrated product image {image.id} to hidden path")
                        
                except Exception as e:
                    logger.error(f"Failed to migrate product image {image.id}: {e}")
                    self.stderr.write(f"Error migrating product image {image.id}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully migrated {migrated} product images")
        )
    
    def migrate_category_images(self, cloud_storage, batch_size, dry_run):
        self.stdout.write("Migrating category images...")
        
        images = CategoryImage.objects.filter(original__isnull=False)
        total = images.count()
        
        self.stdout.write(f"Found {total} category images to migrate")
        
        if dry_run:
            for image in images[:10]:  # Show first 10 for preview
                self.stdout.write(f"Would migrate: {image.original.path}")
            return
        
        migrated = 0
        for i in range(0, total, batch_size):
            batch = images[i:i+batch_size]
            
            for image in batch:
                try:
                    if os.path.exists(image.original.path):
                        # Upload to cloud with hidden path structure
                        with open(image.original.path, 'rb') as f:
                            cloud_path = cloud_storage._save(
                                f"categories/{image.category.slug}/original_{image.id}.jpg",
                                f
                            )
                        
                        # Update image URL to point to cloud (will automatically use qazsw path)
                        image.original.name = cloud_path
                        image.save()
                        
                        migrated += 1
                        self.stdout.write(f"Migrated category image {image.id} to hidden path")
                        
                except Exception as e:
                    logger.error(f"Failed to migrate category image {image.id}: {e}")
                    self.stderr.write(f"Error migrating category image {image.id}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully migrated {migrated} category images")
        )