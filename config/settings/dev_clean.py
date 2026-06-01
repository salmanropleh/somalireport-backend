"""
Clean development settings for Somali Report Backend project.
Minimal debug output for cleaner console experience.
"""

from .base import *

# Override base settings for development
DEBUG = True

# Development-specific apps
INSTALLED_APPS += [
    'django_extensions',
]

# Development database (SQLite)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Development email backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Clean logging configuration - minimal output
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'WARNING',  # Only show warnings and errors
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'ERROR',  # Only show database errors
            'propagate': False,
        },
    },
}

# Development CORS settings
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Development cache (dummy cache)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

# Development static files
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Development media files
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

# Development security settings (relaxed)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
