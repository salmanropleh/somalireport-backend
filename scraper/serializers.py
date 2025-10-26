"""
Serializers for scraper app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import NewsSource, ScrapedArticle, ScrapingJob, ScrapingLog

User = get_user_model()


class NewsSourceSerializer(serializers.ModelSerializer):
    """
    Serializer for NewsSource model.
    """
    
    success_rate = serializers.ReadOnlyField()
    
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    tags_data = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    
    class Meta:
        model = NewsSource
        fields = [
            'id', 'name', 'url', 'source_type', 'description', 'is_active',
            'update_frequency', 'last_scraped', 'api_key', 'username', 'password',
            'title_selector', 'content_selector', 'image_selector', 'date_selector',
            'icon', 'icon_url', 'category', 'category_name', 'category_slug',
            'tags', 'tags_data',
            'total_scraped', 'successful_scrapes', 'failed_scrapes', 'success_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'total_scraped', 'successful_scrapes', 'failed_scrapes', 'success_rate', 'last_scraped', 'created_at', 'updated_at']
    
    def to_representation(self, instance):
        """Hide sensitive information."""
        data = super().to_representation(instance)
        # Mask sensitive fields
        if data.get('api_key'):
            data['api_key'] = data['api_key'][:4] + '******'
        if data.get('password'):
            data['password'] = '******'
        return data


class ScrapedArticleListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for ScrapedArticle list view.
    """
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    source_icon_url = serializers.SerializerMethodField()
    source_icon_image = serializers.SerializerMethodField()
    quality_score_display = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    tags_data = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    
    class Meta:
        model = ScrapedArticle
        fields = [
            'id', 'title', 'excerpt', 'status', 'source', 'source_name',
            'source_icon_url', 'source_icon_image', 'source_url', 'published_at',
            'scraped_at', 'processed_by', 'processed_at', 'quality_score',
            'quality_score_display', 'language', 'category', 'category_name',
            'tags', 'tags_data', 'created_at'
        ]
        read_only_fields = ['id', 'scraped_at', 'processed_by', 'processed_at', 'created_at']
    
    def get_quality_score_display(self, obj):
        """Get human-readable quality score."""
        if obj.quality_score >= 0.8:
            return "High"
        elif obj.quality_score >= 0.5:
            return "Medium"
        else:
            return "Low"
    
    def get_source_icon_url(self, obj):
        """Get source icon URL."""
        return obj.source.icon_url if obj.source.icon_url else None
    
    def get_source_icon_image(self, obj):
        """Get source icon image URL."""
        if obj.source.icon:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.source.icon.url)
            return obj.source.icon.url
        return None


class ScrapedArticleDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for ScrapedArticle.
    """
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    source_url_display = serializers.URLField(source='source.url', read_only=True)
    source_icon_url = serializers.SerializerMethodField()
    source_icon_image = serializers.SerializerMethodField()
    processed_by_name = serializers.CharField(source='processed_by.full_name', read_only=True, allow_null=True)
    quality_score_display = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    tags_data = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    
    class Meta:
        model = ScrapedArticle
        fields = [
            'id', 'source', 'source_name', 'source_url_display', 'source_icon_url',
            'source_icon_image', 'source_url', 'external_id', 'title', 'content', 'excerpt',
            'image_url', 'author', 'published_at', 'scraped_at',
            'status', 'processed_by', 'processed_by_name', 'processed_at',
            'quality_score', 'quality_score_display', 'language',
            'category', 'category_name', 'category_slug', 'tags', 'tags_data',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'scraped_at', 'processed_by', 'processed_at', 'created_at', 'updated_at']
    
    def get_quality_score_display(self, obj):
        """Get human-readable quality score."""
        if obj.quality_score >= 0.8:
            return "High"
        elif obj.quality_score >= 0.5:
            return "Medium"
        else:
            return "Low"
    
    def get_source_icon_url(self, obj):
        """Get source icon URL."""
        return obj.source.icon_url if obj.source.icon_url else None
    
    def get_source_icon_image(self, obj):
        """Get source icon image URL."""
        if obj.source.icon:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.source.icon.url)
            return obj.source.icon.url
        return None


class ScrapingJobSerializer(serializers.ModelSerializer):
    """
    Serializer for ScrapingJob model.
    """
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    
    class Meta:
        model = ScrapingJob
        fields = [
            'id', 'source', 'source_name', 'status', 'started_at',
            'completed_at', 'error_message', 'articles_found', 'articles_scraped',
            'articles_processed', 'max_articles', 'force_update', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'source', 'status', 'started_at', 'completed_at', 'error_message',
                           'articles_found', 'articles_scraped', 'articles_processed', 'created_at', 'updated_at']


class ScrapingLogSerializer(serializers.ModelSerializer):
    """
    Serializer for ScrapingLog model.
    """
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    
    class Meta:
        model = ScrapingLog
        fields = [
            'id', 'source', 'source_name', 'job', 'level', 'message',
            'details', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ScrapeRequestSerializer(serializers.Serializer):
    """
    Serializer for scrape request.
    """
    
    source_id = serializers.IntegerField(required=False)
    max_articles = serializers.IntegerField(default=100, min_value=1, max_value=1000)
    force_update = serializers.BooleanField(default=False)

