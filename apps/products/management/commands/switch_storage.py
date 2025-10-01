from django.core.management.base import BaseCommand
from django.conf import settings
from apps.products.models import ProductImage, CategoryImage
from apps.utils.storage_selector import get_image_storage
import os
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Switch between local and cloud storage backends'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'storage_type',
            type=str,
            choices=['local', 'cloud'],
            help='Storage type to switch to: local or cloud'
        )
        parser.add_argument(
            '--migrate-files',
            action='store_true',
            help='Migrate existing files to the new storage backend'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes'
        )
    
    def handle(self, *args, **options):
        storage_type = options['storage_type']
        migrate_files = options['migrate_files']
        dry_run = options['dry_run']
        
        current_backend = getattr(settings, 'STORAGE_BACKEND', 'local')
        
        self.stdout.write(f"Current storage backend: {current_backend}")
        self.stdout.write(f"Switching to: {storage_type}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))
        
        if current_backend == storage_type:
            self.stdout.write(self.style.WARNING(f"Already using {storage_type} storage"))
            return
        
        # Update storage backend setting
        if not dry_run:
            self.update_storage_setting(storage_type)
        
        if migrate_files:
            if storage_type == 'cloud':
                self.migrate_to_cloud(dry_run)
            else:
                self.migrate_to_local(dry_run)
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully switched to {storage_type} storage backend")
        )
        
        if not migrate_files:
            self.stdout.write(
                self.style.WARNING(
                    "Files were not migrated. Use --migrate-files flag to migrate existing files."
                )
            )
    
    def update_storage_setting(self, storage_type):
        """Update the storage setting in environment or settings file"""
        # This is a simplified approach - in production, you might want to update
        # the environment file or use environment variables
        self.stdout.write(f"Update your .env file or environment variable:")
        self.stdout.write(f"STORAGE_BACKEND={storage_type}")
        
        # For immediate effect in current session
        os.environ['STORAGE_BACKEND'] = storage_type
        
        # Update Django settings
        settings.STORAGE_BACKEND = storage_type
    
    def migrate_to_cloud(self, dry_run):
        """Migrate files from local to cloud storage"""
        self.stdout.write("Migrating files to cloud storage...")
        
        # Get cloud storage instance
        try:
            from apps.utils.storage import CloudImageStorage
            cloud_storage = CloudImageStorage()
        except ImportError:
            self.stderr.write(
                self.style.ERROR("Cloud storage not available. Check if apps.utils.storage is properly configured.")
            )
            return
        
        # Migrate product images
        product_images = ProductImage.objects.all()
        for image in product_images:
            if image.original and hasattr(image.original, 'path'):
                try:
                    if os.path.exists(image.original.path):
                        if dry_run:
                            self.stdout.write(f"Would migrate: {image.original.path}")
                        else:
                            # Read local file
                            with open(image.original.path, 'rb') as f:
                                content = f.read()
                            
                            # Upload to cloud
                            cloud_path = cloud_storage._save(image.original.name, content)
                            
                            self.stdout.write(f"Migrated: {image.original.path} -> {cloud_path}")
                except Exception as e:
                    self.stderr.write(f"Error migrating {image.original.path}: {e}")
        
        # Migrate category images
        category_images = CategoryImage.objects.all()
        for image in category_images:
            if image.original and hasattr(image.original, 'path'):
                try:
                    if os.path.exists(image.original.path):
                        if dry_run:
                            self.stdout.write(f"Would migrate: {image.original.path}")
                        else:
                            # Read local file
                            with open(image.original.path, 'rb') as f:
                                content = f.read()
                            
                            # Upload to cloud
                            cloud_path = cloud_storage._save(image.original.name, content)
                            
                            self.stdout.write(f"Migrated: {image.original.path} -> {cloud_path}")
                except Exception as e:
                    self.stderr.write(f"Error migrating {image.original.path}: {e}")
    
    def migrate_to_local(self, dry_run):
        """Migrate files from cloud to local storage"""
        self.stdout.write("Migrating files to local storage...")
        
        # This is more complex as it requires downloading from cloud
        # For now, we'll just show what would be migrated
        product_images = ProductImage.objects.all()
        category_images = CategoryImage.objects.all()
        
        total_files = product_images.count() + category_images.count()
        
        if dry_run:
            self.stdout.write(f"Would migrate {total_files} files to local storage")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Cloud to local migration not fully implemented. "
                    "This would require downloading files from your cloud storage."
                )
            )