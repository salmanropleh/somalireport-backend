"""
Scraper models for Somali Report Backend.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import BaseModel

User = get_user_model()


class NewsSource(BaseModel):
    """
    News source model for tracking external news sources.
    """
    
    SOURCE_TYPE_CHOICES = [
        ('rss', 'RSS Feed'),
        ('api', 'API'),
        ('scraper', 'Web Scraper'),
        ('manual', 'Manual Entry'),
    ]
    
    name = models.CharField(max_length=200)
    url = models.URLField()
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    
    # Configuration
    is_active = models.BooleanField(default=True)
    update_frequency = models.PositiveIntegerField(default=60)  # minutes
    last_scraped = models.DateTimeField(null=True, blank=True)
    
    # Authentication
    api_key = models.CharField(max_length=200, blank=True, null=True)
    username = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    
    # Parsing configuration
    title_selector = models.CharField(max_length=200, blank=True, null=True)
    content_selector = models.CharField(max_length=200, blank=True, null=True)
    image_selector = models.CharField(max_length=200, blank=True, null=True)
    date_selector = models.CharField(max_length=200, blank=True, null=True)
    
    # Content association
    icon_url = models.URLField(blank=True, null=True, help_text="Icon/logo URL for the source")
    icon = models.ImageField(upload_to='sources/icons/', blank=True, null=True, help_text="Source icon/logo")
    category = models.ForeignKey('content.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='news_sources', help_text="Default category for scraped content")
    tags = models.ManyToManyField('content.Tag', blank=True, related_name='news_sources', help_text="Default tags for scraped content")
    
    # Statistics
    total_scraped = models.PositiveIntegerField(default=0)
    successful_scrapes = models.PositiveIntegerField(default=0)
    failed_scrapes = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'news_sources'
        verbose_name = 'News Source'
        verbose_name_plural = 'News Sources'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def success_rate(self):
        """Calculate success rate."""
        if self.total_scraped == 0:
            return 0
        return (self.successful_scrapes / self.total_scraped) * 100
    
    def update_stats(self, success=True):
        """Update scraping statistics."""
        self.total_scraped += 1
        if success:
            self.successful_scrapes += 1
        else:
            self.failed_scrapes += 1
        self.last_scraped = timezone.now()
        self.save(update_fields=['total_scraped', 'successful_scrapes', 'failed_scrapes', 'last_scraped'])


class ScrapedArticle(BaseModel):
    """
    Scraped article model for storing articles from external sources.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('duplicate', 'Duplicate'),
        ('published', 'Published'),
    ]
    
    # Source information
    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE, related_name='scraped_articles')
    source_url = models.URLField()
    external_id = models.CharField(max_length=200, blank=True, null=True)
    
    # Article content
    title = models.CharField(max_length=500)
    content = models.TextField()
    excerpt = models.TextField(blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)
    author = models.CharField(max_length=200, blank=True, null=True)
    
    # Publishing information
    published_at = models.DateTimeField()
    scraped_at = models.DateTimeField(default=timezone.now)
    
    # Processing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Duplicate detection
    content_hash = models.CharField(max_length=64, blank=True, null=True)
    title_hash = models.CharField(max_length=64, blank=True, null=True)
    
    # Quality metrics
    quality_score = models.FloatField(default=0.0)
    language = models.CharField(max_length=10, default='en')
    
    # Content association (from source)
    category = models.ForeignKey('content.Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='scraped_articles', help_text="Category inherited from source")
    tags = models.ManyToManyField('content.Tag', blank=True, related_name='scraped_articles', help_text="Tags inherited from source")
    
    class Meta:
        db_table = 'scraped_articles'
        verbose_name = 'Scraped Article'
        verbose_name_plural = 'Scraped Articles'
        ordering = ['-scraped_at']
        unique_together = ['source', 'external_id']
    
    def __str__(self):
        return self.title
    
    def approve(self, user):
        """Approve scraped article."""
        self.status = 'approved'
        self.processed_by = user
        self.processed_at = timezone.now()
        self.save()
    
    def reject(self, user):
        """Reject scraped article."""
        self.status = 'rejected'
        self.processed_by = user
        self.processed_at = timezone.now()
        self.save()
    
    def mark_duplicate(self, user):
        """Mark scraped article as duplicate."""
        self.status = 'duplicate'
        self.processed_by = user
        self.processed_at = timezone.now()
        self.save()


class ScrapingJob(BaseModel):
    """
    Scraping job model for tracking scraping tasks.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE, related_name='scraping_jobs')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Job details
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    
    # Results
    articles_found = models.PositiveIntegerField(default=0)
    articles_scraped = models.PositiveIntegerField(default=0)
    articles_processed = models.PositiveIntegerField(default=0)
    
    # Configuration
    max_articles = models.PositiveIntegerField(default=100)
    force_update = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'scraping_jobs'
        verbose_name = 'Scraping Job'
        verbose_name_plural = 'Scraping Jobs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Scraping job for {self.source.name} - {self.status}"
    
    def start(self):
        """Start scraping job."""
        self.status = 'running'
        self.started_at = timezone.now()
        self.save()
    
    def complete(self, articles_found=0, articles_scraped=0, articles_processed=0):
        """Complete scraping job."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.articles_found = articles_found
        self.articles_scraped = articles_scraped
        self.articles_processed = articles_processed
        self.save()
    
    def fail(self, error_message):
        """Mark scraping job as failed."""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save()


class ScrapingLog(BaseModel):
    """
    Scraping log model for tracking scraping activities.
    """
    
    LOG_LEVEL_CHOICES = [
        ('debug', 'Debug'),
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ]
    
    source = models.ForeignKey(NewsSource, on_delete=models.CASCADE, related_name='scraping_logs')
    job = models.ForeignKey(ScrapingJob, on_delete=models.CASCADE, null=True, blank=True, related_name='logs')
    level = models.CharField(max_length=20, choices=LOG_LEVEL_CHOICES)
    message = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'scraping_logs'
        verbose_name = 'Scraping Log'
        verbose_name_plural = 'Scraping Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.level}: {self.message}"