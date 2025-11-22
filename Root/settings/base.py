import os
from pathlib import Path
from datetime import timedelta
import environ
import psycopg2

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Storage Configuration
#STORAGE_BACKEND = env('STORAGE_BACKEND', default='local')  # 'local' or 'cloud'
#STORAGE_DEBUG = env.bool('STORAGE_DEBUG', default=False)

# Cloud Storage (same machine in prod = fast!)
#if STORAGE_BACKEND == 'cloud':
#    CLOUD_STORAGE_URL = env('CLOUD_STORAGE_URL', default='http://127.0.0.1:8080')
#else:
#    MEDIA_ROOT = BASE_DIR / 'media'
#    MEDIA_URL = '/media/'


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY=env('SECRET_KEY')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'requests',
    'mptt',
    'imagekit',
    'drf_spectacular',
    'apps.accounts',
    'apps.products',
    'apps.orders',
    'apps.payments',
    'apps.business',
    'apps.notifications',
    'apps.marketplace',
    'apps.shipping',
    'apps.core',
    'apps.utils',  # Added for storage utilities
]

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',  # Optional: for form data
    ],
}

APPEND_SLASH = True

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),  # Short-lived access tokens
    'REFRESH_TOKEN_LIFETIME': timedelta(days=10),     # Longer-lived refresh tokens
    'ROTATE_REFRESH_TOKENS': True,                  # Issue a new refresh token on every use
    'BLACKLIST_AFTER_ROTATION': True,               # Blacklist old refresh tokens if rotated
    'ALGORITHM': 'HS256',                           # Default is HS256, but you can switch to RS256 for RSA keys
    'SIGNING_KEY': SECRET_KEY,                      # Default is Django's SECRET_KEY
    'AUTH_HEADER_TYPES': ('Bearer',),               # Authorization: Bearer <token>
    'USER_ID_FIELD': 'id',                          # Field to identify the user
    'USER_ID_CLAIM': 'user_id',                     # Claim name in the token
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),  # Token classes
    'TOKEN_TYPE_CLAIM': 'token_type',               # Token type claim
}


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # Add this line
    ]

ROOT_URLCONF = 'Root.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Add your templates directory
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Root.wsgi.application'


# https://docs.djangoproject.com/en/5.1/ref/settings/#databases# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

SPECTACULAR_SETTINGS = {
    "TITLE": "Dima Api Documentation",
    "DESCRIPTION": "Dima is a platform that allows users to create and manage their own online stores, providing a seamless shopping experience for customers.",
    "VERSION": "1.0.0",
    "SERVER_INCLUDE_SCHEMA": False,
}

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Nairobi'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

# Storage Configuration
# Media configuration based on storage backend

STORAGE_BACKEND = env('STORAGE_BACKEND')  # 'local' or 'cloud'
STORAGE_DEBUG = env.bool('STORAGE_DEBUG', default=False)

# Cloud Storage (same machine in prod = fast!)
if STORAGE_BACKEND == 'cloud':
    CLOUD_STORAGE_URL = env('CLOUD_STORAGE_URL', default='http://127.0.0.1:8080')
else:
    MEDIA_ROOT = BASE_DIR / 'media'
    MEDIA_URL = '/media/'

if STORAGE_BACKEND == 'cloud':
    # Cloud Media Storage Configuration
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

    # Cloud Storage Settings
    _CLOUD_BASE = CLOUD_STORAGE_URL.rstrip('/')
    CLOUD_MEDIA_SERVER = {
        'BASE_URL': _CLOUD_BASE,
        'UPLOAD_ENDPOINT': f"{_CLOUD_BASE}/qazsw-upload/",
        'DELETE_ENDPOINT': f"{_CLOUD_BASE}/qazsw-delete/",
        'PROCESS_ENDPOINT': f"{_CLOUD_BASE}/process/",
        'ORIGINAL_PATH': '/qazsw/',
        'SUPPORTED_FORMATS': ['jpeg', 'jpg', 'png', 'webp', 'gif', 'bmp', 'tiff'],
        'MAX_FILE_SIZE': 52428800,  # 50MB
        'MAX_DIMENSION': 4000,
        'TIMEOUT': 30,
        'RETRY_ATTEMPTS': 3,
        'RETRY_DELAY': 1,
    }

    # Image Size Presets (with WebP defaults for better performance)
    CLOUD_IMAGE_SIZES = {
        # Small thumbnails for mobile/list views (150x150 WebP)
        'thumbnail_small': {'width': 150, 'height': 150, 'quality': 80, 'format': 'webp'},
        # Medium thumbnails for product cards (300x300 WebP) - Perfect for product listings
        'thumbnail_medium': {'width': 300, 'height': 300, 'quality': 85, 'format': 'webp'},
        # Large thumbnails for product detail pages (600x600 WebP)
        'thumbnail_large': {'width': 600, 'height': 600, 'quality': 90, 'format': 'webp'},
        # Medium size for detail views (800x800 WebP)
        'medium': {'width': 800, 'height': 800, 'quality': 90, 'format': 'webp'},
        # Large size for hero images (1200x1200 WebP) - Perfect for product detail pages
        'large': {'width': 1200, 'height': 1200, 'quality': 95, 'format': 'webp'},
    }

    # Use cloud storage as default
    DEFAULT_FILE_STORAGE = 'apps.utils.storage.CloudImageStorage'
else:
    # Local Media Storage
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644

# Image Processing Settings (used for local storage only)
IMAGE_PROCESSING = {
    'ENABLE_OPTIMIZATION': True,
    'DEFAULT_QUALITY': 85,
    'MAX_WIDTH': 1200,
    'MAX_HEIGHT': 1200,
    'THUMBNAIL_SIZES': {
        'small': (150, 150),
        'medium': (300, 300),
        'large': (600, 600),
    },
    'ENABLE_WEBP': True,
    'ENABLE_PROGRESSIVE_JPEG': True,
}

# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.CustomUser'

# Email conf
RESEND_KEY = env('DIMA_RESEND_KEY')
DB_URL = str(env('DB_URL'))
# Security settings
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

# Static files configuration
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

#M-PESA settings
MPESA_CONSUMER_KEY = env('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = env('MPESA_CONSUMER_SECRET')
MPESA_SHORTCODE = env('MPESA_SHORTCODE')
MPESA_PASSKEY = env('MPESA_PASSKEY')


# Cache configuration (recommended for marketplace performance)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'TIMEOUT': 300,  # 5 minutes default timeout
        'KEY_PREFIX': 'dima'  # Prefix for all cache keys
    }
}

# Celery configuration for background tasks
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Nairobi'

# Marketplace-specific settings
MARKETPLACE_SETTINGS = {
    'DEFAULT_COMMISSION_RATE': 10.0,  # 10%
    'MAX_CART_ITEMS': 50,
    'SEARCH_RESULTS_PER_PAGE': 24,
    'ENABLE_PRODUCT_REVIEWS': True,
    'ENABLE_VENDOR_REVIEWS': True,
    'AUTO_APPROVE_REVIEWS': False,
    'LOW_STOCK_THRESHOLD': 10,
    'ABANDONED_CART_DAYS': 10,
}

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
DEFAULT_FROM_EMAIL = 'noreply@yourmarketplace.com'

# Google Confs
GOOGLE_CLIENT_ID = env('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = env('GOOGLE_CLIENT_SECRET')

# PostgreSQL full-text search (optional but recommended)
#if 'postgresql' in DATABASES['default']['ENGINE']:
#    INSTALLED_APPS.append('django.contrib.postgres')

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'marketplace.log',
            'formatter': 'verbose',
        },
        'storage_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'storage_debug.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'marketplace': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'storage': {
            'handlers': ['storage_file', 'console'] if env('STORAGE_DEBUG', default=False) else ['storage_file'],
            'level': 'DEBUG' if env('STORAGE_DEBUG', default=False) else 'INFO',
            'propagate': False,
        },
    },
}