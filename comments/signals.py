"""
Signals for comments app.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Comment, CommentLike, CommentReport
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Comment)
def update_comment_counts(sender, instance, created, **kwargs):
    """
    Update comment counts when comment is saved.
    """
    if created:
        logger.info(f"New comment created by {instance.user.email if instance.user else instance.author_name}")
        
        # Update parent comment reply count
        if instance.parent:
            instance.parent.reply_count += 1
            instance.parent.save(update_fields=['reply_count'])
    else:
        logger.info(f"Comment updated: {instance.id}")


@receiver(post_save, sender=CommentLike)
def update_comment_like_count(sender, instance, created, **kwargs):
    """
    Update comment like count when like is created.
    """
    if created:
        if instance.like_type == 'like':
            instance.comment.like_count += 1
        else:
            instance.comment.dislike_count += 1
        instance.comment.save(update_fields=['like_count', 'dislike_count'])
        logger.info(f"Comment {instance.comment.id} {instance.like_type}d by {instance.user.email}")


@receiver(post_delete, sender=CommentLike)
def update_comment_like_count_delete(sender, instance, **kwargs):
    """
    Update comment like count when like is deleted.
    """
    if instance.like_type == 'like':
        instance.comment.like_count -= 1
    else:
        instance.comment.dislike_count -= 1
    instance.comment.save(update_fields=['like_count', 'dislike_count'])
    logger.info(f"Comment {instance.comment.id} {instance.like_type} removed by {instance.user.email}")


@receiver(post_save, sender=CommentReport)
def handle_comment_report(sender, instance, created, **kwargs):
    """
    Handle comment report creation.
    """
    if created:
        logger.info(f"Comment {instance.comment.id} reported by {instance.reporter.email} for {instance.reason}")
        
        # Auto-moderate if multiple reports
        report_count = CommentReport.objects.filter(
            comment=instance.comment,
            is_resolved=False
        ).count()
        
        if report_count >= 3:  # Auto-moderate after 3 reports
            instance.comment.status = 'spam'
            instance.comment.is_approved = False
            instance.comment.save()
            logger.info(f"Comment {instance.comment.id} auto-moderated due to multiple reports")
