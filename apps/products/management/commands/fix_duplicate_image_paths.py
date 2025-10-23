"""
Management command to fix duplicate image paths in the database

This fixes paths like:
  FROM: 'filename.jpg/filename.jpg'
  TO:   'filename.jpg'

Usage:
  python manage.py fix_duplicate_image_paths --dry-run  # Preview changes
  python manage.py fix_duplicate_image_paths            # Apply changes
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.products.models import ProductImage, CategoryImage
from apps.marketplace.models import Banner
import os


class Command(BaseCommand):
    help = 'Fix duplicate image paths in database (e.g., file.jpg/file.jpg -> file.jpg)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be saved'))
        
        # Track statistics
        stats = {
            'product_images': 0,
            'category_images': 0,
            'banners': 0,
        }
        
        # Fix ProductImage paths
        self.stdout.write('\nChecking ProductImage records...')
        product_images = ProductImage.objects.all()
        for img in product_images:
            if img.original and img.original.name:
                old_path = img.original.name
                new_path = self.fix_duplicate_path(old_path)
                
                if old_path != new_path:
                    self.stdout.write(f'  ProductImage #{img.id}:')
                    self.stdout.write(f'    OLD: {old_path}')
                    self.stdout.write(f'    NEW: {new_path}')
                    
                    if not dry_run:
                        img.original.name = new_path
                        img.save(update_fields=['original'])
                    
                    stats['product_images'] += 1
        
        # Fix CategoryImage paths
        self.stdout.write('\nChecking CategoryImage records...')
        category_images = CategoryImage.objects.all()
        for img in category_images:
            if img.original and img.original.name:
                old_path = img.original.name
                new_path = self.fix_duplicate_path(old_path)
                
                if old_path != new_path:
                    self.stdout.write(f'  CategoryImage #{img.id}:')
                    self.stdout.write(f'    OLD: {old_path}')
                    self.stdout.write(f'    NEW: {new_path}')
                    
                    if not dry_run:
                        img.original.name = new_path
                        img.save(update_fields=['original'])
                    
                    stats['category_images'] += 1
        
        # Fix Banner paths
        self.stdout.write('\nChecking Banner records...')
        banners = Banner.objects.all()
        for banner in banners:
            if banner.original and banner.original.name:
                old_path = banner.original.name
                new_path = self.fix_duplicate_path(old_path)
                
                if old_path != new_path:
                    self.stdout.write(f'  Banner #{banner.id}:')
                    self.stdout.write(f'    OLD: {old_path}')
                    self.stdout.write(f'    NEW: {new_path}')
                    
                    if not dry_run:
                        banner.original.name = new_path
                        banner.save(update_fields=['original'])
                    
                    stats['banners'] += 1
        
        # Print summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('Summary:'))
        self.stdout.write(f"  ProductImages fixed: {stats['product_images']}")
        self.stdout.write(f"  CategoryImages fixed: {stats['category_images']}")
        self.stdout.write(f"  Banners fixed: {stats['banners']}")
        self.stdout.write(f"  Total fixed: {sum(stats.values())}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were saved'))
            self.stdout.write('Run without --dry-run to apply these changes')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ All changes saved successfully!'))
    
    def fix_duplicate_path(self, path):
        """
        Fix duplicate paths and normalize path separators.
        
        Handles:
        - 'filename.jpg/filename.jpg' -> 'filename.jpg'
        - 'dir/filename.jpg/filename.jpg' -> 'dir/filename.jpg'  
        - Windows paths: 'file.jpg\\file.jpg' -> 'file.jpg'
        - Complex cases: 'dir\\file-uuid.jpg\\file.jpg' -> 'dir/file-uuid.jpg'
        """
        if not path:
            return path
        
        # Normalize path separators (convert backslashes to forward slashes)
        normalized_path = path.replace('\\', '/')
        
        # Split the path by '/'
        parts = normalized_path.split('/')
        
        # Filter out empty parts
        parts = [p for p in parts if p]
        
        if len(parts) < 2:
            return normalized_path
        
        # Check if the last two parts are identical filenames (exact duplicate)
        if parts[-1] == parts[-2]:
            # Remove the duplicate last part
            fixed_path = '/'.join(parts[:-1])
            return fixed_path
        
        # Check if both last two parts are files (have extensions)
        last = parts[-1]
        second_last = parts[-2]
        
        if '.' in last and '.' in second_last:
            # Check if they're both filenames (not directory names)
            # If second_last looks like a generated filename (has uuid) and last is simpler
            # Keep the one with UUID as it's the actual stored file
            if '-' in second_last and len(second_last) > len(last):
                # Looks like 'file-uuid.jpg' vs 'file.jpg' - keep the UUID one
                fixed_path = '/'.join(parts[:-1])
                return fixed_path
            elif last == second_last:
                # Exact duplicates
                fixed_path = '/'.join(parts[:-1])
                return fixed_path
        
        # Return normalized path (with forward slashes)
        return normalized_path
