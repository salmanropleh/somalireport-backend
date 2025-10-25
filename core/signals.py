"""
Core signals for Somali Report Backend.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Signal handler for User model post_save.
    """
    if created:
        logger.info(f"New user created: {instance.email}")
        # You can add additional logic here, such as:
        # - Send welcome email
        # - Create user profile
        # - Set default permissions
    else:
        logger.info(f"User updated: {instance.email}")


@receiver(pre_save, sender=User)
def user_pre_save(sender, instance, **kwargs):
    """
    Signal handler for User model pre_save.
    """
    # Ensure email is lowercase
    if instance.email:
        instance.email = instance.email.lower()
    
    # Set last_login if not set
    if not instance.last_login:
        instance.last_login = timezone.now()
