"""
Production settings for Somali Report Backend project.
"""

from .base import *

# Override base settings for production
DEBUG = True

# ALLOWED_HOSTS - add your PythonAnywhere domain and any custom domains
# Ensure PythonAnywhere domain is always included
default_hosts = ['*']
env_allowed_hosts = env.list('ALLOWED_HOSTS', default=[])
# Merge environment hosts with defaults, ensuring no duplicates
ALLOWED_HOSTS = list(set(env_allowed_hosts + default_hosts))

# ALLOWED_HOSTS - add your PythonAnywhere domain and any custom domains
# Ensure PythonAnywhere domain is always included
default_hosts = ['johnhenry411.pythonanywhere.com', 'localhost', '127.0.0.1']
env_allowed_hosts = env.list('ALLOWED_HOSTS', default=[])
# Merge environment hosts with defaults, ensuring no duplicates
ALLOWED_HOSTS = list(set(env_allowed_hosts + default_hosts))

# Production security settings
# Note: SSL settings may be managed by the hosting provider (e.g., PythonAnywhere)
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)  # Let hosting provider handle SSL
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=True)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=True)
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=True)

# Production database
# Note: Base settings already handle SQLite absolute path conversion
# Only override if you need PostgreSQL or other database
# DATABASES is already configured in base.py with absolute path handling
# If using PostgreSQL, uncomment and configure:
# DATABASES = {
#     'default': env.db()
# }
# For SQLite, the base.py configuration is sufficient

# Production email backend
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Production logging
# Use project logs directory (accessible on PythonAnywhere)
log_dir = BASE_DIR / 'logs'
log_dir.mkdir(exist_ok=True)  # Create logs directory if it doesn't exist
LOGGING['handlers']['file']['filename'] = str(log_dir / 'django.log')
LOGGING['handlers']['file']['level'] = 'WARNING'
LOGGING['loggers']['django']['level'] = 'WARNING'
# Suppress drf-spectacular schema generation warnings (non-critical)
LOGGING['loggers']['drf_spectacular'] = {
    'handlers': ['console', 'file'],
    'level': 'ERROR',  # Only show errors, suppress warnings
    'propagate': False,
}

# Production CORS settings
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])

# Production cache (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Production static files
# Use environment variables for flexibility, fallback to project directories
STATIC_ROOT = env('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles'))
STATIC_URL = env('STATIC_URL', default='/static/')
MEDIA_ROOT = env('MEDIA_ROOT', default=str(BASE_DIR / 'media'))
MEDIA_URL = env('MEDIA_URL', default='/media/')

# Production file upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Production rate limiting
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'

# Production monitoring
SENTRY_DSN = env('SENTRY_DSN', default='')

if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=True,
    )
