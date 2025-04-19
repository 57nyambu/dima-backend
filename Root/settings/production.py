import dj_database_url
from Root.settings.base import *

# Set DEBUG to True for local testing
DEBUG = True

# Allowed hosts: Allow all hosts for local testing
ALLOWED_HOSTS = ['*']

DATABASES =  {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
        'OPTIONS': {
            'sslmode': 'require',
        },
    }
}

# CORS settings: Allow frontend (Vite) to access Django API
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite default dev server
    "https://elaborate-axolotl-e6c495.netlify.app"
]

# Allow all methods and headers
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Remove CORS_ALLOW_ALL_ORIGINS, as it's conflicting with CORS_ALLOWED_ORIGINS
# CORS_ALLOW_ALL_ORIGINS = True  # REMOVE THIS

# Secure cookies: Disable secure cookies for local testing
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False

# Enforce HTTPS and prevent HTTP traffic: Disable for local testing
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Logging: Set the level to DEBUG for detailed logs
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "debug.log",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

# Security headers (Optional, but useful)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
