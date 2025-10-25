"""
Scraper app configuration for Somali Report Backend.
"""

from django.apps import AppConfig


class ScraperConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scraper'
    verbose_name = 'Scraper'
    
    def ready(self):
        import scraper.signals