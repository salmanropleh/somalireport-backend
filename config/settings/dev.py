"""
Development settings for Somali Report Backend project.
Backend runs on: http://127.0.0.1:8000  (python manage.py runserver 8000)
"""

from .base import *

# Override base settings for development
DEBUG = True

# Development-specific apps
INSTALLED_APPS += [
    'django_extensions',
  # Disabled for now
]

# Development-specific middleware
MIDDLEWARE += [
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',  # Disabled for now
]

# Debug toolbar configuration
INTERNAL_IPS = [
    '127.0.0.1',
    'localhost',
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

# Development logging - Reduced verbosity
LOGGING['handlers']['console']['level'] = 'INFO'
LOGGING['loggers']['django']['level'] = 'INFO'
LOGGING['loggers']['django.db.backends'] = {
    'handlers': ['console'],
    'level': 'WARNING',  # Reduce SQL query logging
    'propagate': False,
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
