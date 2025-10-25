"""
Serializers for content app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Category, Tag, Article, MediaFile, ArticleView, ArticleLike, ArticleShare
from core.utils import StringHelper

User = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category model.
    """
    
    article_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'color', 'icon',
            'is_active', 'sort_order', 'article_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
    
    def get_article_count(self, obj):
        """Get count of published articles in this category."""
        return obj.article_set.filter(status='published').count()


class TagSerializer(serializers.ModelSerializer):
    """
    Serializer for Tag model.
    """
    
    article_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tag
        fields = [
            'id', 'name', 'slug', 'description', 'color',
            'is_active', 'article_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
    
    def get_article_count(self, obj):
        """Get count of published articles with this tag."""
        return obj.article_set.filter(status='published').count()


class MediaFileSerializer(serializers.ModelSerializer):
    """
    Serializer for MediaFile model.
    """
    
    file_size_mb = serializers.ReadOnlyField()
    is_image = serializers.ReadOnlyField()
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    
    class Meta:
        model = MediaFile
        fields = [
            'id', 'name', 'file', 'file_type', 'file_size', 'file_size_mb',
            'mime_type', 'alt_text', 'caption', 'uploaded_by', 'uploaded_by_name',
            'article', 'width', 'height', 'is_image', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'file_size', 'mime_type', 'uploaded_by', 'created_at', 'updated_at']


class ArticleListSerializer(serializers.ModelSerializer):
    """
    Serializer for Article list view.
    """
    
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    tag_names = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    reading_time = serializers.ReadOnlyField()
    is_published = serializers.ReadOnlyField()
    featured_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'excerpt', 'status', 'priority',
            'author', 'author_name', 'category', 'category_name',
            'tags', 'tag_names', 'featured_image', 'featured_image_url',
            'published_at', 'view_count', 'like_count', 'share_count',
            'is_featured', 'is_breaking', 'reading_time', 'is_published',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'view_count', 'like_count', 'share_count', 'created_at', 'updated_at']
    
    def get_featured_image_url(self, obj):
        """Get featured image URL."""
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None


class ArticleDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for Article detail view.
    """
    
    author_name = serializers.CharField(source='author.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    tag_names = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    reading_time = serializers.ReadOnlyField()
    is_published = serializers.ReadOnlyField()
    featured_image_url = serializers.SerializerMethodField()
    media_files = MediaFileSerializer(many=True, read_only=True)
    is_liked = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content', 'status', 'priority',
            'author', 'author_name', 'category', 'category_name',
            'tags', 'tag_names', 'featured_image', 'featured_image_url',
            'meta_title', 'meta_description', 'published_at', 'scheduled_at',
            'view_count', 'like_count', 'share_count', 'allow_comments',
            'is_featured', 'is_breaking', 'reading_time', 'is_published',
            'media_files', 'is_liked', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'view_count', 'like_count', 'share_count', 'created_at', 'updated_at']
    
    def get_featured_image_url(self, obj):
        """Get featured image URL."""
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None
    
    def get_is_liked(self, obj):
        """Check if current user has liked this article."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False


class ArticleCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for Article create/update operations.
    """
    
    class Meta:
        model = Article
        fields = [
            'title', 'excerpt', 'content', 'status', 'priority',
            'category', 'tags', 'featured_image', 'meta_title',
            'meta_description', 'published_at', 'scheduled_at',
            'allow_comments', 'is_featured', 'is_breaking'
        ]
    
    def validate_title(self, value):
        """Validate article title."""
        if len(value) < 10:
            raise serializers.ValidationError("Title must be at least 10 characters long.")
        return value
    
    def validate_content(self, value):
        """Validate article content."""
        if len(value) < 100:
            raise serializers.ValidationError("Content must be at least 100 characters long.")
        return value
    
    def validate_scheduled_at(self, value):
        """Validate scheduled publication time."""
        if value and value <= timezone.now():
            raise serializers.ValidationError("Scheduled time must be in the future.")
        return value


class ArticleViewSerializer(serializers.ModelSerializer):
    """
    Serializer for ArticleView model.
    """
    
    class Meta:
        model = ArticleView
        fields = [
            'id', 'article', 'user', 'ip_address', 'user_agent',
            'referrer', 'session_id', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ArticleLikeSerializer(serializers.ModelSerializer):
    """
    Serializer for ArticleLike model.
    """
    
    class Meta:
        model = ArticleLike
        fields = ['id', 'article', 'user', 'created_at']
        read_only_fields = ['id', 'user', 'created_at']


class ArticleShareSerializer(serializers.ModelSerializer):
    """
    Serializer for ArticleShare model.
    """
    
    class Meta:
        model = ArticleShare
        fields = [
            'id', 'article', 'user', 'platform', 'ip_address', 'created_at'
        ]
        read_only_fields = ['id', 'user', 'ip_address', 'created_at']
