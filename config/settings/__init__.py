"""
Settings init file for Somali Report Backend project.
"""

import os
from django.core.exceptions import ImproperlyConfigured

# Get the environment variable
ENVIRONMENT = os.environ.get('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

# Import the appropriate settings module
if ENVIRONMENT == 'config.settings.dev':
    from .dev import *
elif ENVIRONMENT == 'config.settings.prod':
    from .prod import *
else:
    raise ImproperlyConfigured(
        f"Invalid DJANGO_SETTINGS_MODULE: {ENVIRONMENT}. "
        "Must be either 'config.settings.dev' or 'config.settings.prod'"
    )
