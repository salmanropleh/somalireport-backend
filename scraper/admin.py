from django.contrib import admin
from .models import NewsSource, ScrapedArticle, ScrapingJob, ScrapingLog


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    """Admin configuration for NewsSource model."""
    list_display = ['name', 'source_type', 'is_active', 'last_scraped', 'success_rate', 'total_scraped']
    list_filter = ['is_active', 'source_type', 'last_scraped']
    search_fields = ['name', 'url', 'description']
    readonly_fields = ['total_scraped', 'successful_scrapes', 'failed_scrapes', 'success_rate', 'last_scraped', 'created_at', 'updated_at']
    fieldsets = (
        ('Source Information', {
            'fields': ('name', 'url', 'source_type', 'description', 'is_active')
        }),
        ('Visual Identity', {
            'fields': ('icon', 'icon_url')
        }),
        ('Content Association', {
            'fields': ('category', 'tags')
        }),
        ('Configuration', {
            'fields': ('update_frequency', 'title_selector', 'content_selector', 'image_selector', 'date_selector')
        }),
        ('Authentication', {
            'fields': ('api_key', 'username', 'password')
        }),
        ('Statistics', {
            'fields': ('total_scraped', 'successful_scrapes', 'failed_scrapes', 'success_rate', 'last_scraped')
        }),
    )
    filter_horizontal = ['tags']


@admin.register(ScrapedArticle)
class ScrapedArticleAdmin(admin.ModelAdmin):
    """Admin configuration for ScrapedArticle model."""
    list_display = ['title', 'source', 'category', 'status', 'quality_score', 'scraped_at', 'processed_by']
    list_filter = ['status', 'source', 'category', 'quality_score', 'scraped_at', 'language']
    search_fields = ['title', 'content', 'excerpt', 'source_url']
    readonly_fields = ['content_hash', 'title_hash', 'scraped_at', 'created_at', 'updated_at']
    date_hierarchy = 'scraped_at'
    
    fieldsets = (
        ('Article Information', {
            'fields': ('title', 'content', 'excerpt', 'source_url', 'external_id')
        }),
        ('Source', {
            'fields': ('source', 'published_at', 'scraped_at')
        }),
        ('Content Association', {
            'fields': ('category', 'tags')
        }),
        ('Media', {
            'fields': ('image_url', 'author')
        }),
        ('Status', {
            'fields': ('status', 'processed_by', 'processed_at')
        }),
        ('Quality', {
            'fields': ('quality_score', 'language', 'content_hash', 'title_hash')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    filter_horizontal = ['tags']


@admin.register(ScrapingJob)
class ScrapingJobAdmin(admin.ModelAdmin):
    """Admin configuration for ScrapingJob model."""
    list_display = ['source', 'status', 'articles_found', 'articles_scraped', 'articles_processed', 'started_at', 'completed_at']
    list_filter = ['status', 'source', 'started_at']
    search_fields = ['source__name', 'error_message']
    readonly_fields = ['status', 'started_at', 'completed_at', 'error_message', 'articles_found', 'articles_scraped', 'articles_processed', 'created_at', 'updated_at']
    date_hierarchy = 'started_at'


@admin.register(ScrapingLog)
class ScrapingLogAdmin(admin.ModelAdmin):
    """Admin configuration for ScrapingLog model."""
    list_display = ['source', 'level', 'message', 'created_at']
    list_filter = ['level', 'source', 'created_at']
    search_fields = ['message', 'details']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
