"""
Signals for content app.
"""

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from .models import Article, ArticleLike, ArticleShare
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Article)
def capture_pre_save_status(sender, instance, **kwargs):
    """Store the DB status before the save so post_save can detect transitions."""
    if instance.pk:
        try:
            instance._pre_save_status = Article.objects.get(pk=instance.pk).status
        except Article.DoesNotExist:
            instance._pre_save_status = None
    else:
        instance._pre_save_status = None


@receiver(post_save, sender=Article)
def notify_google_on_publish(sender, instance, created, **kwargs):
    """Ping Google Indexing API exactly once when status first becomes 'published'."""
    old_status = getattr(instance, '_pre_save_status', None)
    if instance.status == 'published' and old_status != 'published':
        from django.conf import settings
        from core.utils import StringHelper
        site_url = getattr(settings, 'SITE_URL', 'https://somalireport.com')
        slug = instance.slug or StringHelper.slugify(instance.title)
        url = f'{site_url}/article/{instance.id}/{slug}'
        from .indexing import notify_google
        notify_google(url)


@receiver(post_save, sender=Article)
def update_article_counts(sender, instance, created, **kwargs):
    """
    Update article counts when article is saved.
    """
    if created:
        logger.info(f"New article created: {instance.title}")
    else:
        logger.info(f"Article updated: {instance.title}")


@receiver(post_save, sender=ArticleLike)
def update_like_count(sender, instance, created, **kwargs):
    """
    Update article like count when like is created.
    """
    if created:
        instance.article.like_count += 1
        instance.article.save(update_fields=['like_count'])
        logger.info(f"Article {instance.article.title} liked by {instance.user.email}")


@receiver(post_delete, sender=ArticleLike)
def update_like_count_delete(sender, instance, **kwargs):
    """
    Update article like count when like is deleted.
    """
    instance.article.like_count -= 1
    instance.article.save(update_fields=['like_count'])
    logger.info(f"Article {instance.article.title} unliked by {instance.user.email}")


@receiver(post_save, sender=ArticleShare)
def update_share_count(sender, instance, created, **kwargs):
    """
    Update article share count when share is created.
    """
    if created:
        instance.article.share_count += 1
        instance.article.save(update_fields=['share_count'])
        logger.info(f"Article {instance.article.title} shared on {instance.platform}")
