#!/usr/bin/env python3
"""
Simple file management service for image server
Run this on your image server to handle uploads/deletes
"""

import os
import shutil
import hashlib
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from werkzeug.utils import secure_filename
from PIL import Image
import logging

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Configuration
CACHE_DIR = Path('/home/prod/cache')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
THUMBNAIL_SIZES = {
    'thumbnail': (300, 300),
    'medium': (600, 600),
    'large': (1200, 1200)
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_file_hash(file_content):
    """Generate hash for file deduplication"""
    return hashlib.md5(file_content).hexdigest()

def create_thumbnail(image_path, size, quality=85):
    """Create thumbnail with specified size"""
    try:
        with Image.open(image_path) as img:
            # Convert RGBA to RGB for JPEG
            if img.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            
            # Resize maintaining aspect ratio
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Create thumbnail path
            thumbnail_dir = image_path.parent / 'thumbnails'
            thumbnail_dir.mkdir(exist_ok=True)
            
            thumbnail_path = thumbnail_dir / f"{image_path.stem}_{size[0]}x{size[1]}.jpg"
            
            # Save thumbnail
            img.save(thumbnail_path, 'JPEG', quality=quality, optimize=True)
            
            return thumbnail_path
            
    except Exception as e:
        logger.error(f"Error creating thumbnail: {e}")
        return None

@app.route('/upload/', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'File type not allowed'}), 400
        
        # Get target path
        target_path = request.form.get('path', '')
        if not target_path:
            return jsonify({'error': 'No path provided'}), 400
        
        # Secure the filename and path
        filename = secure_filename(file.filename)
        full_path = CACHE_DIR / target_path
        
        # Create directory if it doesn't exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read file content for deduplication
        file_content = file.read()
        file_hash = generate_file_hash(file_content)
        
        # Check for duplicate
        hash_path = CACHE_DIR / 'hashes' / f"{file_hash}.txt"
        if hash_path.exists():
            with open(hash_path, 'r') as f:
                existing_path = f.read().strip()
                if Path(existing_path).exists():
                    logger.info(f"File already exists: {existing_path}")
                    return jsonify({'path': existing_path, 'status': 'exists'}), 200
        
        # Save file
        with open(full_path, 'wb') as f:
            f.write(file_content)
        
        # Store hash mapping
        hash_path.parent.mkdir(parents=True, exist_ok=True)
        with open(hash_path, 'w') as f:
            f.write(str(full_path.relative_to(CACHE_DIR)))
        
        # Create thumbnails if it's an image
        if any(full_path.suffix.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png']):
            for size_name, size in THUMBNAIL_SIZES.items():
                create_thumbnail(full_path, size)
        
        logger.info(f"File uploaded: {full_path}")
        return jsonify({'path': str(full_path.relative_to(CACHE_DIR)), 'status': 'uploaded'}), 200
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete/', methods=['DELETE'])
def delete_file():
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'No path provided'}), 400
        
        file_path = CACHE_DIR / data['path']
        
        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        # Delete main file
        file_path.unlink()
        
        # Delete thumbnails
        thumbnail_dir = file_path.parent / 'thumbnails'
        if thumbnail_dir.exists():
            for thumbnail in thumbnail_dir.glob(f"{file_path.stem}_*"):
                thumbnail.unlink()
        
        logger.info(f"File deleted: {file_path}")
        return jsonify({'status': 'deleted'}), 200
        
    except Exception as e:
        logger.error(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/process/<path:image_path>')
def process_image(image_path):
    """Process image on-demand (resize, optimize) - accessed through hidden path"""
    try:
        # Get query parameters
        width = request.args.get('w', type=int)
        height = request.args.get('h', type=int)
        quality = request.args.get('q', type=int, default=85)
        
        # Remove any qazsw prefix if present (from nginx rewrite)
        if image_path.startswith('qazsw/'):
            image_path = image_path[6:]  # Remove 'qazsw/' prefix
        
        full_path = CACHE_DIR / image_path
        
        if not full_path.exists():
            logger.warning(f"Image not found: {image_path}")
            return "Image not found", 404
        
        # Verify it's actually an image file
        if not any(full_path.suffix.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            logger.warning(f"Not an image file: {image_path}")
            return "Not an image file", 400
        
        # If no resize parameters, serve original
        if not width and not height:
            return send_file(full_path)
        
        # Create processed image
        cache_key = f"{image_path}_{width or 'auto'}x{height or 'auto'}_q{quality}"
        cache_path = CACHE_DIR / 'processed' / f"{hashlib.md5(cache_key.encode()).hexdigest()}.jpg"
        
        if not cache_path.exists():
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            with Image.open(full_path) as img:
                # Resize logic
                if width and height:
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                elif width:
                    ratio = width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((width, new_height), Image.Resampling.LANCZOS)
                elif height:
                    ratio = height / img.height
                    new_width = int(img.width * ratio)
                    img = img.resize((new_width, height), Image.Resampling.LANCZOS)
                
                # Convert and save
                if img.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                
                img.save(cache_path, 'JPEG', quality=quality, optimize=True)
        
        return send_file(cache_path)
        
    except Exception as e:
        logger.error(f"Process error for {image_path}: {e}")
        return "Processing error", 500

@app.route('/health')
def health_check():
    return "OK", 200

if __name__ == '__main__':
    # Create required directories
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / 'hashes').mkdir(exist_ok=True)
    (CACHE_DIR / 'processed').mkdir(exist_ok=True)
    
    app.run(host='127.0.0.1', port=8080, debug=False)