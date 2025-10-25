"""
Content models for Somali Report Backend.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import AuditModel
from core.utils import StringHelper

User = get_user_model()


class Category(AuditModel):
    """
    Category model for organizing articles.
    """
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default='#007bff')  # Hex color
    icon = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided."""
        if not self.slug:
            self.slug = StringHelper.slugify(self.name)
        super().save(*args, **kwargs)


class Tag(AuditModel):
    """
    Tag model for article tagging.
    """
    
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=7, default='#6c757d')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'tags'
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided."""
        if not self.slug:
            self.slug = StringHelper.slugify(self.name)
        super().save(*args, **kwargs)


class Article(AuditModel):
    """
    Article model for news content.
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Review'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    excerpt = models.TextField(max_length=500, blank=True, null=True)
    content = models.TextField()
    featured_image = models.ImageField(upload_to='articles/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Relationships
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True)
    
    # SEO fields
    meta_title = models.CharField(max_length=200, blank=True, null=True)
    meta_description = models.TextField(max_length=300, blank=True, null=True)
    
    # Publishing
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    
    # Content settings
    allow_comments = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_breaking = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'articles'
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        """Auto-generate slug and excerpt if not provided."""
        if not self.slug:
            self.slug = StringHelper.slugify(self.title)
        
        if not self.excerpt:
            self.excerpt = StringHelper.extract_excerpt(self.content)
        
        if not self.meta_title:
            self.meta_title = self.title
        
        if not self.meta_description:
            self.meta_description = self.excerpt
        
        super().save(*args, **kwargs)
    
    @property
    def is_published(self):
        """Check if article is published."""
        return self.status == 'published' and self.published_at is not None
    
    @property
    def reading_time(self):
        """Estimate reading time in minutes."""
        word_count = len(self.content.split())
        return max(1, word_count // 200)  # Assume 200 words per minute
    
    def increment_view_count(self):
        """Increment view count."""
        self.view_count += 1
        self.save(update_fields=['view_count'])


class MediaFile(AuditModel):
    """
    Media file model for storing images, videos, etc.
    """
    
    FILE_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('document', 'Document'),
    ]
    
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='media/')
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES)
    file_size = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=100)
    alt_text = models.CharField(max_length=200, blank=True, null=True)
    caption = models.TextField(blank=True, null=True)
    
    # Relationships
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='media_files')
    article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, blank=True, related_name='media_files')
    
    # Image specific fields
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'media_files'
        verbose_name = 'Media File'
        verbose_name_plural = 'Media Files'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def file_size_mb(self):
        """Return file size in MB."""
        return round(self.file_size / (1024 * 1024), 2)
    
    @property
    def is_image(self):
        """Check if file is an image."""
        return self.file_type == 'image'


class ArticleView(AuditModel):
    """
    Track article views for analytics.
    """
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    referrer = models.URLField(blank=True, null=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        db_table = 'article_views'
        verbose_name = 'Article View'
        verbose_name_plural = 'Article Views'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"View of {self.article.title}"


class ArticleLike(AuditModel):
    """
    Track article likes.
    """
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='article_likes')
    
    class Meta:
        db_table = 'article_likes'
        verbose_name = 'Article Like'
        verbose_name_plural = 'Article Likes'
        unique_together = ['article', 'user']
    
    def __str__(self):
        return f"{self.user.email} likes {self.article.title}"


class ArticleShare(AuditModel):
    """
    Track article shares.
    """
    
    SHARE_PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('twitter', 'Twitter'),
        ('linkedin', 'LinkedIn'),
        ('whatsapp', 'WhatsApp'),
        ('email', 'Email'),
        ('other', 'Other'),
    ]
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    platform = models.CharField(max_length=20, choices=SHARE_PLATFORM_CHOICES)
    ip_address = models.GenericIPAddressField()
    
    class Meta:
        db_table = 'article_shares'
        verbose_name = 'Article Share'
        verbose_name_plural = 'Article Shares'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Share of {self.article.title} on {self.platform}"