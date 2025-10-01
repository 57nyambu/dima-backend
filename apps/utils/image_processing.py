import os
import requests
from PIL import Image
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)

class ImageProcessingService:
    """
    Service for processing and optimizing images before cloud upload
    """
    
    SUPPORTED_FORMATS = ['JPEG', 'PNG', 'WEBP']
    
    @staticmethod
    def optimize_image(image_file, max_width=1200, max_height=1200, quality=85, format='JPEG'):
        """
        Optimize image for web delivery
        """
        try:
            # Open image
            if hasattr(image_file, 'read'):
                image = Image.open(image_file)
            else:
                image = Image.open(BytesIO(image_file))
            
            # Convert to RGB if necessary (for JPEG)
            if format == 'JPEG' and image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            
            # Resize if needed
            if image.width > max_width or image.height > max_height:
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Save optimized image
            output = BytesIO()
            save_kwargs = {'format': format, 'optimize': True}
            
            if format == 'JPEG':
                save_kwargs['quality'] = quality
                save_kwargs['progressive'] = True
            elif format == 'PNG':
                save_kwargs['compress_level'] = 6
            elif format == 'WEBP':
                save_kwargs['quality'] = quality
                save_kwargs['method'] = 6
            
            image.save(output, **save_kwargs)
            output.seek(0)
            
            return ContentFile(output.getvalue())
            
        except Exception as e:
            logger.error(f"Error optimizing image: {str(e)}")
            raise
    
    @staticmethod
    def create_thumbnails(image_file, sizes=None):
        """
        Create multiple thumbnail sizes
        """
        if sizes is None:
            sizes = {
                'thumbnail': (300, 300),
                'medium': (600, 600),
                'large': (1200, 1200)
            }
        
        thumbnails = {}
        
        try:
            for size_name, (width, height) in sizes.items():
                thumbnail = ImageProcessingService.optimize_image(
                    image_file, 
                    max_width=width, 
                    max_height=height,
                    quality=85
                )
                thumbnails[size_name] = thumbnail
                
        except Exception as e:
            logger.error(f"Error creating thumbnails: {str(e)}")
            raise
            
        return thumbnails
    
    @staticmethod
    def upload_with_variants(image_file, base_path, cloud_storage):
        """
        Upload original and optimized variants to cloud storage
        """
        results = {}
        
        try:
            # Upload original (optimized)
            optimized_original = ImageProcessingService.optimize_image(
                image_file, 
                max_width=1200, 
                max_height=1200, 
                quality=90
            )
            
            original_path = f"{base_path}/original.jpg"
            results['original'] = cloud_storage._save(original_path, optimized_original)
            
            # Create and upload thumbnails
            thumbnails = ImageProcessingService.create_thumbnails(image_file)
            
            for size_name, thumbnail in thumbnails.items():
                thumbnail_path = f"{base_path}/{size_name}.jpg"
                results[size_name] = cloud_storage._save(thumbnail_path, thumbnail)
                
        except Exception as e:
            logger.error(f"Error uploading image variants: {str(e)}")
            raise
            
        return results