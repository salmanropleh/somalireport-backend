"""
Signals for newsletter app.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=User)
def link_subscription_to_user(sender, instance, created, **kwargs):
    """
    When a new user registers, check if there's an existing newsletter subscription
    with their email and link it to the user account.
    """
    from .models import NewsletterSubscription

    if created:
        # User was just created, check for existing subscription
        try:
            subscription = NewsletterSubscription.objects.filter(
                email=instance.email,
                user__isnull=True,
                is_deleted=False
            ).first()

            if subscription:
                subscription.user = instance
                subscription.save(update_fields=['user'])
                logger.info(
                    f"Linked existing newsletter subscription to new user: {instance.email}"
                )
        except Exception as e:
            logger.error(
                f"Error linking subscription to user {instance.email}: {e}"
            )
    else:
        # User was updated, check if email changed
        try:
            # If email changed, try to link any matching subscription
            subscription = NewsletterSubscription.objects.filter(
                email=instance.email,
                user__isnull=True,
                is_deleted=False
            ).first()

            if subscription:
                subscription.user = instance
                subscription.save(update_fields=['user'])
                logger.info(
                    f"Linked newsletter subscription after email update: {instance.email}"
                )
        except Exception as e:
            logger.error(
                f"Error linking subscription after update for {instance.email}: {e}"
            )


@receiver(post_save, sender='newsletter.NewsletterRead')
def update_newsletter_open_count(sender, instance, created, **kwargs):
    """
    Update newsletter open count when a new read record is created.
    """
    if created:
        # Note: This is also handled in the view to avoid race conditions,
        # but we keep this here as a fallback
        logger.info(
            f"Newsletter '{instance.newsletter.title}' read by {instance.subscription.email}"
        )
