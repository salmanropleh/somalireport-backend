"""
Signals for scraper app.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import NewsSource, ScrapedArticle, ScrapingJob
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=NewsSource)
def update_source_stats(sender, instance, created, **kwargs):
    """
    Update source statistics when source is saved.
    """
    if created:
        logger.info(f"New news source created: {instance.name}")
    else:
        logger.info(f"News source updated: {instance.name}")


@receiver(post_save, sender=ScrapedArticle)
def handle_scraped_article(sender, instance, created, **kwargs):
    """
    Handle scraped article creation.
    """
    if created:
        logger.info(f"New scraped article: {instance.title}")
        
        # Auto-approve high-quality articles
        if instance.quality_score >= 0.8:
            instance.status = 'approved'
            instance.save()
            logger.info(f"Auto-approved high-quality article: {instance.title}")


@receiver(post_save, sender=ScrapingJob)
def handle_scraping_job(sender, instance, created, **kwargs):
    """
    Handle scraping job status changes.
    """
    if created:
        logger.info(f"New scraping job created for {instance.source.name}")
    else:
        logger.info(f"Scraping job {instance.id} status changed to {instance.status}")
        
        # Send notifications for failed jobs
        if instance.status == 'failed':
            logger.error(f"Scraping job {instance.id} failed: {instance.error_message}")
        
        # Send notifications for completed jobs
        elif instance.status == 'completed':
            logger.info(f"Scraping job {instance.id} completed successfully")
