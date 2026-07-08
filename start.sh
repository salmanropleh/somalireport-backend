#!/bin/bash
cd /var/www/SomReport/somalireport-backend
export DJANGO_SETTINGS_MODULE=config.settings.prod
exec venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 2
