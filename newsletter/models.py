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
    Newsletter model for storing newsletter content and direct email campaigns.
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
    ]

    EMAIL_TYPE_CHOICES = [
        ('newsletter', 'Newsletter'),
        ('direct', 'Direct Email'),
    ]

    TEMPLATE_CHOICES = [
        ('classic', 'Classic'),
        ('modern', 'Modern'),
        ('minimal', 'Minimal'),
    ]

    RECIPIENTS_CHOICES = [
        ('subscribers', 'Subscribers'),
        ('all_users', 'All Users'),
        ('custom', 'Custom'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    subject = models.CharField(max_length=200, help_text="Email subject line")
    excerpt = models.TextField(max_length=500, blank=True)
    content_html = models.TextField(blank=True, help_text="HTML email content (used for direct emails)")
    content_text = models.TextField(blank=True, help_text="Plain text fallback")
    featured_image = models.ImageField(upload_to='newsletters/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    sent_at = models.DateTimeField(null=True, blank=True)
    recipient_count = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)

    # Campaign type & targeting
    email_type = models.CharField(max_length=20, choices=EMAIL_TYPE_CHOICES, default='newsletter')
    recipients_type = models.CharField(max_length=20, choices=RECIPIENTS_CHOICES, default='subscribers')
    custom_recipients = models.TextField(blank=True, help_text="Comma-separated email addresses")

    # Newsletter-specific
    articles = models.ManyToManyField(
        'content.Article',
        blank=True,
        related_name='newsletters',
        help_text="Articles to feature in newsletter campaigns"
    )
    article_order = models.JSONField(default=list, blank=True, help_text="Ordered list of article IDs")
    greeting_text = models.CharField(max_length=255, blank=True, help_text="Optional greeting e.g. 'Dear Reader,'")

    # Appearance
    template_style = models.CharField(max_length=20, choices=TEMPLATE_CHOICES, default='classic')
    accent_color = models.CharField(max_length=7, default='#1a3a6e', help_text="Hex color for branding")
    header_image_url = models.URLField(blank=True, help_text="Full-width header image URL")
    text_blocks = models.JSONField(default=list, blank=True, help_text="Custom text blocks: [{id, content, position}]")

    class Meta:
        db_table = 'newsletters'
        verbose_name = 'Newsletter'
        verbose_name_plural = 'Newsletters'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = StringHelper.slugify(self.title)
            slug = base_slug
            counter = 1
            while Newsletter.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
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
