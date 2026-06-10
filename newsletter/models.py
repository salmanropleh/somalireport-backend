"""
Newsletter models for Somali Report Backend.
"""

import secrets
from django.db import models
from django.contrib.auth import get_user_model
from core.models import AuditModel, BaseModel
from core.utils import StringHelper

User = get_user_model()


class Newsletter(AuditModel):
    """
    Newsletter model for storing newsletter content.
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    subject = models.CharField(max_length=200, help_text="Email subject line")
    excerpt = models.TextField(max_length=500, blank=True)
    content_html = models.TextField(help_text="HTML email content")
    content_text = models.TextField(help_text="Plain text fallback")
    featured_image = models.ImageField(upload_to='newsletters/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient_count = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'newsletters'
        verbose_name = 'Newsletter'
        verbose_name_plural = 'Newsletters'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided."""
        if not self.slug:
            self.slug = StringHelper.slugify(self.title)
        if not self.excerpt and self.content_text:
            self.excerpt = StringHelper.extract_excerpt(self.content_text, length=500)
        super().save(*args, **kwargs)


class NewsletterSubscription(BaseModel):
    """
    Newsletter subscription model for tracking subscribers.
    """

    email = models.EmailField(unique=True)
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='newsletter_subscription'
    )
    is_active = models.BooleanField(default=True)
    unsubscribe_token = models.CharField(max_length=64, unique=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'newsletter_subscriptions'
        verbose_name = 'Newsletter Subscription'
        verbose_name_plural = 'Newsletter Subscriptions'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """Auto-generate unsubscribe token if not provided."""
        if not self.unsubscribe_token:
            self.unsubscribe_token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    @classmethod
    def generate_unsubscribe_token(cls):
        """Generate a unique unsubscribe token."""
        return secrets.token_urlsafe(48)


class NewsletterRead(models.Model):
    """
    Track which users have read which newsletters.
    """

    newsletter = models.ForeignKey(
        Newsletter,
        on_delete=models.CASCADE,
        related_name='reads'
    )
    subscription = models.ForeignKey(
        NewsletterSubscription,
        on_delete=models.CASCADE,
        related_name='reads'
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'newsletter_reads'
        verbose_name = 'Newsletter Read'
        verbose_name_plural = 'Newsletter Reads'
        unique_together = ['newsletter', 'subscription']
        ordering = ['-read_at']

    def __str__(self):
        return f"{self.subscription.email} read {self.newsletter.title}"
