"""
Content models for Somali Report Backend.
"""

from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from core.models import AuditModel
from core.utils import StringHelper
import re

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
    featured_image_url = models.URLField(blank=True, null=True, help_text="URL for featured image (alternative to file upload)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Relationships
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='articles')
    primary_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='primary_articles')
    secondary_categories = models.ManyToManyField(Category, blank=True, related_name='secondary_articles')
    tags = models.ManyToManyField(Tag, blank=True)
    
    # SEO fields
    meta_title = models.CharField(max_length=200, blank=True, null=True)
    meta_description = models.TextField(max_length=300, blank=True, null=True)
    
    # Publishing
    published_at = models.DateTimeField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    
    # Category Auto-Archiving
    primary_category_expires_at = models.DateTimeField(null=True, blank=True, help_text="When to auto-archive from primary category")
    primary_category_archived_at = models.DateTimeField(null=True, blank=True, help_text="When article was archived from primary category")
    secondary_categories_expire_at = models.DateTimeField(null=True, blank=True, help_text="When to auto-archive from secondary categories")
    secondary_categories_archived_at = models.DateTimeField(null=True, blank=True, help_text="When article was archived from secondary categories")
    archived_secondary_categories = models.ManyToManyField(Category, blank=True, related_name='archived_secondary_articles', help_text="Secondary categories this article has been archived from")
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    
    # Content settings
    allow_comments = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_breaking = models.BooleanField(default=False)
    
    # Manual Author Information
    manual_author_name = models.CharField(max_length=200, blank=True, null=True, help_text="Manually entered author name")
    manual_author_image = models.ImageField(upload_to='authors/', blank=True, null=True, help_text="Manual author profile picture")
    manual_author_image_url = models.URLField(blank=True, null=True, help_text="URL for manual author profile picture (alternative to file upload)")
    manual_author_affiliation = models.CharField(max_length=200, blank=True, null=True, help_text="Author's affiliation/organization")
    author_opinion_note = models.TextField(blank=True, null=True, help_text="Opinion disclaimer note (e.g., 'This article is the sole opinion of the above author and in no way Somali Report's point of view')")
    show_manual_author = models.BooleanField(default=False, help_text="If True, display manual author info instead of the automatic author")
    show_opinion_note = models.BooleanField(default=False, help_text="If True, display the opinion note with the article")
    
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
            base_slug = StringHelper.slugify(self.title)
            slug = base_slug
            counter = 2
            qs = Article.objects.exclude(pk=self.pk)
            while qs.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

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
    def featured_image_display_url(self):
        """Get featured image URL from either file field or URL field."""
        if self.featured_image:
            return self.featured_image.url
        elif self.featured_image_url:
            return self.featured_image_url
        return None
    
    @property
    def manual_author_image_display_url(self):
        """Get manual author image URL from either file field or URL field."""
        if self.manual_author_image:
            return self.manual_author_image.url
        elif self.manual_author_image_url:
            return self.manual_author_image_url
        return None
    
    @property
    def reading_time(self):
        """Estimate reading time in minutes."""
        word_count = len(self.content.split())
        return max(1, word_count // 200)  # Assume 200 words per minute
    
    def increment_view_count(self):
        """Increment view count."""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    @property
    def is_primary_category_active(self):
        """Check if article is still active in primary category."""
        if not self.primary_category:
            return False
        
        # If manually archived, it's not active
        if self.primary_category_archived_at:
            return False
        
        # If auto-archiving is set and expired
        if self.primary_category_expires_at and timezone.now() > self.primary_category_expires_at:
            return False
        
        return True
    
    @property
    def is_secondary_categories_active(self):
        """Check if article is still active in secondary categories."""
        if not self.secondary_categories.exists():
            return False
        
        # If manually archived (old method), it's not active
        if self.secondary_categories_archived_at:
            return False
        
        # If auto-archiving is set and expired
        if self.secondary_categories_expire_at and timezone.now() > self.secondary_categories_expire_at:
            return False
        
        return True
    
    @property
    def is_primary_archived(self):
        """Check if article is archived from primary category."""
        if not self.primary_category:
            return False
        # Check if manually archived
        if self.primary_category_archived_at:
            return True
        # Check if auto-archiving is set and expired
        if self.primary_category_expires_at and timezone.now() > self.primary_category_expires_at:
            return True
        return False
    
    @property
    def is_secondary_archived(self):
        """Check if article is archived from secondary categories."""
        # Check if manually archived (old method)
        if self.secondary_categories_archived_at:
            return True
        # Check if auto-archiving is set and expired
        if self.secondary_categories_expire_at and timezone.now() > self.secondary_categories_expire_at:
            return True
        # Check if any categories are in archived_secondary_categories
        if self.archived_secondary_categories.exists():
            return True
        return False
    
    def archive_from_primary_category(self, manual=True):
        """Archive article from primary category."""
        if self.primary_category:
            self.primary_category_archived_at = timezone.now()
            self.save(update_fields=['primary_category_archived_at'])
            return True
        return False
    
    def archive_from_secondary_categories(self, manual=True):
        """Archive article from secondary categories."""
        if self.secondary_categories.exists():
            self.secondary_categories_archived_at = timezone.now()
            self.save(update_fields=['secondary_categories_archived_at'])
            return True
        return False
    
    def restore_from_primary_category(self):
        """Restore article from primary category archive."""
        if self.primary_category_archived_at:
            self.primary_category_archived_at = None
            self.save(update_fields=['primary_category_archived_at'])
            return True
        return False
    
    def restore_from_secondary_categories(self):
        """Restore article from secondary categories archive."""
        if self.secondary_categories_archived_at:
            self.secondary_categories_archived_at = None
            self.save(update_fields=['secondary_categories_archived_at'])
            return True
        return False
    
    def archive_from_specific_secondary_category(self, category, manual=True):
        """Archive article from a specific secondary category."""
        if not self.secondary_categories.filter(id=category.id).exists():
            return False, "Article is not in this secondary category"
        
        # Add to archived secondary categories
        self.archived_secondary_categories.add(category)
        
        # Remove from active secondary categories
        self.secondary_categories.remove(category)
        
        return True, f"Article archived from {category.name}"
    
    def restore_from_specific_secondary_category(self, category):
        """Restore article to a specific secondary category."""
        if not self.archived_secondary_categories.filter(id=category.id).exists():
            return False, "Article was not archived from this secondary category"
        
        # Remove from archived secondary categories
        self.archived_secondary_categories.remove(category)
        
        # Add back to active secondary categories
        self.secondary_categories.add(category)
        
        return True, f"Article restored to {category.name}"
    
    def get_active_secondary_categories(self):
        """Get secondary categories that are currently active (not archived)."""
        return self.secondary_categories.all()
    
    def get_archived_secondary_categories(self):
        """Get secondary categories that have been archived."""
        return self.archived_secondary_categories.all()
    
    def is_active_in_secondary_category(self, category):
        """Check if article is active in a specific secondary category."""
        return self.secondary_categories.filter(id=category.id).exists()
    
    def is_archived_from_secondary_category(self, category):
        """Check if article is archived from a specific secondary category."""
        return self.archived_secondary_categories.filter(id=category.id).exists()
    
    def set_primary_category_duration(self, hours=None, days=None):
        """Set auto-archiving duration for primary category."""
        if hours:
            self.primary_category_expires_at = timezone.now() + timezone.timedelta(hours=hours)
        elif days:
            self.primary_category_expires_at = timezone.now() + timezone.timedelta(days=days)
        else:
            self.primary_category_expires_at = None
        self.save(update_fields=['primary_category_expires_at'])
    
    def set_secondary_categories_duration(self, hours=None, days=None):
        """Set auto-archiving duration for secondary categories."""
        if hours:
            self.secondary_categories_expire_at = timezone.now() + timezone.timedelta(hours=hours)
        elif days:
            self.secondary_categories_expire_at = timezone.now() + timezone.timedelta(days=days)
        else:
            self.secondary_categories_expire_at = None
        self.save(update_fields=['secondary_categories_expire_at'])
    
    def archive(self):
        """Archive the article by setting status to 'archived'."""
        if self.status != 'archived':
            previous_status = self.status
            self.status = 'archived'
            self.save(update_fields=['status'])
            return True, previous_status
        return False, None
    
    def unarchive(self, restore_to_status='draft'):
        """Unarchive/restore the article by changing status from 'archived' to specified status."""
        if self.status == 'archived':
            # Validate the restore status
            valid_statuses = [choice[0] for choice in self.STATUS_CHOICES if choice[0] != 'archived']
            if restore_to_status not in valid_statuses:
                restore_to_status = 'draft'  # Default to draft if invalid
            
            self.status = restore_to_status
            self.save(update_fields=['status'])
            return True, restore_to_status
        return False, None
    
    def extract_media_urls_from_content(self):
        """Extract media URLs from article content."""
        media_urls = []
        
        # Pattern to match img tags with src attributes
        img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
        img_matches = re.findall(img_pattern, self.content)
        
        # Pattern to match video tags with src attributes
        video_pattern = r'<video[^>]+src=["\']([^"\']+)["\'][^>]*>'
        video_matches = re.findall(video_pattern, self.content)
        
        # Pattern to match source tags within video elements
        source_pattern = r'<source[^>]+src=["\']([^"\']+)["\'][^>]*>'
        source_matches = re.findall(source_pattern, self.content)
        
        # Combine all matches
        all_urls = img_matches + video_matches + source_matches
        
        # Filter out external URLs (only include URLs from our media files)
        for url in all_urls:
            if '/media/' in url:
                media_urls.append(url)
        
        return media_urls
    
    def get_inline_media_files(self):
        """Get MediaFile objects referenced in the article content."""
        media_urls = self.extract_media_urls_from_content()
        media_files = []
        
        for url in media_urls:
            # Extract filename from URL
            filename = url.split('/')[-1]
            try:
                # Try to find the media file by filename
                media_file = MediaFile.objects.filter(file__icontains=filename).first()
                if media_file:
                    media_files.append(media_file)
            except MediaFile.DoesNotExist:
                continue
        
        return media_files


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
    file = models.FileField(upload_to='uploads/')  # Changed from 'media/' to avoid double /media/media/ in URLs
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


class Video(AuditModel):
    """
    Video model for storing and managing video content.
    """
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Review'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]
    
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(max_length=1000, blank=True, null=True)
    video_file = models.FileField(upload_to='videos/', blank=True, null=True)
    external_video_url = models.URLField(blank=True, null=True, help_text="External video URL (e.g. YouTube)")
    thumbnail = models.ImageField(upload_to='videos/thumbnails/', blank=True, null=True)
    duration = models.PositiveIntegerField(default=0, help_text="Duration in seconds")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Relationships
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='videos')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='videos')
    tags = models.ManyToManyField(Tag, blank=True, related_name='videos')
    
    # Metadata
    file_size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    
    # Publishing
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Analytics
    view_count = models.PositiveIntegerField(default=0)
    like_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    
    # Content settings
    allow_comments = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'videos'
        verbose_name = 'Video'
        verbose_name_plural = 'Videos'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided."""
        if not self.slug:
            base_slug = StringHelper.slugify(self.title)
            slug = base_slug
            counter = 2
            qs = Video.objects.exclude(pk=self.pk)
            while qs.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
    
    @property
    def is_published(self):
        """Check if video is published."""
        return self.status == 'published' and self.published_at is not None
    
    @property
    def file_size_mb(self):
        """Return file size in MB."""
        return round(self.file_size / (1024 * 1024), 2)
    
    def increment_view_count(self):
        """Increment view count."""
        self.view_count += 1
        self.save(update_fields=['view_count'])


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


class ArticleSave(AuditModel):
    """
    Track saved articles.
    """
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='saves')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_articles')
    
    class Meta:
        db_table = 'article_saves'
        verbose_name = 'Saved Article'
        verbose_name_plural = 'Saved Articles'
        unique_together = ['article', 'user']
    
    def __str__(self):
        return f"{self.user.email} saved {self.article.title}"


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


class Contact(AuditModel):
    """
    Contact model for storing contact form submissions.
    """
    
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'contacts'
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Message from {self.name}: {self.subject}"