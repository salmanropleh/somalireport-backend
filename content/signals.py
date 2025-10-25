"""
Signals for content app.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Article, ArticleLike, ArticleShare
import logging

logger = logging.getLogger(__name__)


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
