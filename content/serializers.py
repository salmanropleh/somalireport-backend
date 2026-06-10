"""
Serializers for content app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Category, Tag, Article, MediaFile, Video, ArticleView, ArticleLike, ArticleShare, Contact
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
        from .models import Article
        
        # Count articles where this category is either primary or secondary
        primary_count = Article.objects.filter(
            primary_category=obj,
            status='published'
        ).count()
        
        secondary_count = Article.objects.filter(
            secondary_categories=obj,
            status='published'
        ).count()
        
        return primary_count + secondary_count


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
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = MediaFile
        fields = [
            'id', 'name', 'file', 'file_type', 'file_size', 'file_size_mb',
            'mime_type', 'alt_text', 'caption', 'uploaded_by', 'uploaded_by_name',
            'article', 'width', 'height', 'is_image', 'file_url', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'file_size', 'mime_type', 'uploaded_by', 'created_at', 'updated_at']
    
    def _get_file_type(self, mime_type):
        """Determine file type from MIME type."""
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        else:
            return 'document'
    
    def create(self, validated_data):
        """Create MediaFile instance with file_size, mime_type, and file_type."""
        file = validated_data.get('file')
        if file:
            # Calculate file_size from the uploaded file
            validated_data['file_size'] = file.size
            # Get mime_type from the file
            validated_data['mime_type'] = file.content_type or 'application/octet-stream'
            # Determine file_type from mime_type
            validated_data['file_type'] = self._get_file_type(validated_data['mime_type'])
        
        return super().create(validated_data)
    
    def get_file_url(self, obj):
        """Get file URL."""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class ArticleListSerializer(serializers.ModelSerializer):
    """
    Serializer for Article list view.
    """
    
    author_name = serializers.SerializerMethodField()
    author_username = serializers.SerializerMethodField()
    display_author_name = serializers.SerializerMethodField()
    display_author_affiliation = serializers.SerializerMethodField()
    primary_category_name = serializers.CharField(source='primary_category.name', read_only=True)
    secondary_category_names = serializers.StringRelatedField(source='secondary_categories', many=True, read_only=True)
    tag_names = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    reading_time = serializers.ReadOnlyField()
    is_published = serializers.ReadOnlyField()
    featured_image_url = serializers.SerializerMethodField()
    featured_image_display_url = serializers.ReadOnlyField()
    is_primary_category_active = serializers.ReadOnlyField()
    is_secondary_categories_active = serializers.ReadOnlyField()
    is_primary_archived = serializers.ReadOnlyField()
    is_secondary_archived = serializers.ReadOnlyField()
    manual_author_image_display_url = serializers.ReadOnlyField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'excerpt', 'status', 'priority',
            'author', 'author_name', 'author_username', 'display_author_name', 'display_author_affiliation',
            'primary_category', 'primary_category_name',
            'secondary_categories', 'secondary_category_names',
            'tags', 'tag_names', 'featured_image', 'featured_image_url', 'featured_image_display_url',
            'published_at', 'view_count', 'like_count', 'share_count',
            'is_featured', 'is_breaking', 'reading_time', 'is_published',
            'primary_category_expires_at', 'primary_category_archived_at',
            'secondary_categories_expire_at', 'secondary_categories_archived_at',
            'is_primary_category_active', 'is_secondary_categories_active',
            'is_primary_archived', 'is_secondary_archived',
            'manual_author_name', 'manual_author_affiliation', 'manual_author_image', 'manual_author_image_url', 'manual_author_image_display_url', 'author_opinion_note',
            'show_manual_author', 'show_opinion_note',
            'created_at', 'updated_at',
            'is_saved'
        ]
        read_only_fields = ['id', 'slug', 'view_count', 'like_count', 'share_count', 'created_at', 'updated_at', 'is_saved']
    
    def get_is_saved(self, obj):
        """Check if current user has saved this article."""
        request = self.context.get('request')
        if request and request.user.is_authenticated and hasattr(obj, 'saves'):
             from .models import ArticleSave
             return ArticleSave.objects.filter(article=obj, user=request.user, is_deleted=False).exists()
        return False

    def get_author_name(self, obj):
        """Get the automatic author name (original author)."""
        return obj.author.full_name if obj.author else None

    def get_author_username(self, obj):
        return obj.author.username if obj.author else None

    def get_display_author_name(self, obj):
        """Get the author name to display based on toggle."""
        if obj.show_manual_author and obj.manual_author_name:
            return obj.manual_author_name
        return obj.author.full_name if obj.author else None
    
    def get_display_author_affiliation(self, obj):
        """Get the author affiliation to display."""
        if obj.show_manual_author and obj.manual_author_affiliation:
            return obj.manual_author_affiliation
        return None
    
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
    
    author_name = serializers.SerializerMethodField()
    author_username = serializers.SerializerMethodField()
    author_photo_url = serializers.SerializerMethodField()
    author_bio = serializers.SerializerMethodField()
    display_author_name = serializers.SerializerMethodField()
    display_author_affiliation = serializers.SerializerMethodField()
    primary_category_name = serializers.CharField(source='primary_category.name', read_only=True)
    secondary_category_names = serializers.StringRelatedField(source='secondary_categories', many=True, read_only=True)
    tag_names = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    reading_time = serializers.ReadOnlyField()
    is_published = serializers.ReadOnlyField()
    featured_image_url = serializers.SerializerMethodField()
    featured_image_display_url = serializers.ReadOnlyField()
    media_files = MediaFileSerializer(many=True, read_only=True)
    inline_media_files = serializers.SerializerMethodField()
    inline_media_urls = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_primary_category_active = serializers.ReadOnlyField()
    is_secondary_categories_active = serializers.ReadOnlyField()
    is_primary_archived = serializers.ReadOnlyField()
    is_secondary_archived = serializers.ReadOnlyField()
    manual_author_image_display_url = serializers.ReadOnlyField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content', 'status', 'priority',
            'author', 'author_name', 'author_username', 'author_photo_url', 'author_bio', 'display_author_name', 'display_author_affiliation',
            'primary_category', 'primary_category_name',
            'secondary_categories', 'secondary_category_names',
            'tags', 'tag_names', 'featured_image', 'featured_image_url', 'featured_image_display_url',
            'meta_title', 'meta_description', 'published_at', 'scheduled_at',
            'view_count', 'like_count', 'share_count', 'allow_comments',
            'is_featured', 'is_breaking', 'reading_time', 'is_published',
            'primary_category_expires_at', 'primary_category_archived_at',
            'secondary_categories_expire_at', 'secondary_categories_archived_at',
            'is_primary_category_active', 'is_secondary_categories_active',
            'is_primary_archived', 'is_secondary_archived',
            'manual_author_name', 'manual_author_affiliation', 'manual_author_image', 'manual_author_image_url', 'manual_author_image_display_url', 'author_opinion_note',
            'show_manual_author', 'show_opinion_note',
            'media_files', 'inline_media_files', 'inline_media_urls', 'is_liked', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'view_count', 'like_count', 'share_count', 'created_at', 'updated_at']
    
    def get_author_name(self, obj):
        """Get the automatic author name (original author)."""
        return obj.author.full_name if obj.author else None

    def get_author_username(self, obj):
        return obj.author.username if obj.author else None

    def get_author_photo_url(self, obj):
        """Get author's profile photo URL."""
        if obj.author and obj.author.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.author.avatar.url)
            return obj.author.avatar.url
        return None

    def get_author_bio(self, obj):
        """Get the author's bio."""
        return obj.author.bio if obj.author else None

    def get_display_author_name(self, obj):
        """Get the author name to display based on toggle."""
        if obj.show_manual_author and obj.manual_author_name:
            return obj.manual_author_name
        return obj.author.full_name if obj.author else None
    
    def get_display_author_affiliation(self, obj):
        """Get the author affiliation to display."""
        if obj.show_manual_author and obj.manual_author_affiliation:
            return obj.manual_author_affiliation
        return None
    
    def get_featured_image_url(self, obj):
        """Get featured image URL."""
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None
    
    def get_inline_media_files(self, obj):
        """Get MediaFile objects referenced in the article content."""
        media_files = obj.get_inline_media_files()
        serializer = MediaFileSerializer(media_files, many=True, context=self.context)
        return serializer.data
    
    def get_inline_media_urls(self, obj):
        """Get URLs of media files referenced in the article content."""
        return obj.extract_media_urls_from_content()
    
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
            'primary_category', 'secondary_categories', 'tags', 'featured_image', 'featured_image_url',
            'meta_title', 'meta_description', 'published_at', 'scheduled_at',
            'primary_category_expires_at', 'secondary_categories_expire_at',
            'allow_comments', 'is_featured', 'is_breaking',
            'manual_author_name', 'manual_author_affiliation', 'manual_author_image', 'manual_author_image_url', 'author_opinion_note',
            'show_manual_author', 'show_opinion_note'
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
    
    def validate(self, data):
        """Validate featured image fields and manual author fields."""
        featured_image = data.get('featured_image')
        featured_image_url = data.get('featured_image_url')
        
        # If both are provided, prefer the file upload
        if featured_image and featured_image_url:
            data['featured_image_url'] = None  # Clear URL if file is provided
        
        # Validate manual author fields
        show_manual_author = data.get('show_manual_author', False)
        manual_author_name = data.get('manual_author_name')
        
        if show_manual_author and not manual_author_name:
            raise serializers.ValidationError({
                'manual_author_name': 'Manual author name is required when "show_manual_author" is enabled.'
            })
            
        # Prioritize file upload over URL for manual author image
        manual_author_image = data.get('manual_author_image')
        manual_author_image_url = data.get('manual_author_image_url')
        
        if manual_author_image and manual_author_image_url:
            data['manual_author_image_url'] = None
        
        return data


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


class VideoListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for Video list view - optimized for efficient retrieval.
    """
    
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    tag_names = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    file_size_mb = serializers.ReadOnlyField()
    is_published = serializers.ReadOnlyField()
    
    class Meta:
        model = Video
        fields = [
            'id', 'title', 'slug', 'description', 'status', 'uploaded_by', 'uploaded_by_name',
            'category', 'category_name', 'tags', 'tag_names', 'thumbnail', 'thumbnail_url',
            'duration', 'view_count', 'like_count', 'share_count', 'is_featured',
            'published_at', 'video_url', 'external_video_url', 'file_size_mb', 'is_published', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'view_count', 'like_count', 'share_count', 'created_at', 'updated_at']
    
    def get_thumbnail_url(self, obj):
        """Get thumbnail URL."""
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None
    
    def get_video_url(self, obj):
        """Get video URL (internal or external)."""
        if obj.video_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.video_file.url)
            return obj.video_file.url
        elif obj.external_video_url:
            return obj.external_video_url
        return None


class VideoDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for Video detail view.
    """
    
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    tag_names = serializers.StringRelatedField(source='tags', many=True, read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    file_size_mb = serializers.ReadOnlyField()
    is_published = serializers.ReadOnlyField()
    
    class Meta:
        model = Video
        fields = [
            'id', 'title', 'slug', 'description', 'status', 'uploaded_by', 'uploaded_by_name',
            'category', 'category_name', 'tags', 'tag_names', 'thumbnail', 'thumbnail_url',
            'duration', 'view_count', 'like_count', 'share_count', 'is_featured',
            'allow_comments', 'published_at', 'video_url', 'external_video_url', 'file_size_mb', 'mime_type',
            'is_published', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'view_count', 'like_count', 'share_count', 'created_at', 'updated_at']
    
    def get_thumbnail_url(self, obj):
        """Get thumbnail URL."""
        if obj.thumbnail:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None
    
    def get_video_url(self, obj):
        """Get video URL (internal or external)."""
        if obj.video_file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.video_file.url)
            return obj.video_file.url
        elif obj.external_video_url:
            return obj.external_video_url
        return None


class VideoCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for Video create/update operations.
    """
    
    class Meta:
        model = Video
        fields = [
            'title', 'description', 'video_file', 'external_video_url', 'thumbnail', 'status',
            'category', 'tags', 'duration', 'allow_comments', 'is_featured',
            'published_at'
        ]
    
    def validate_title(self, value):
        """Validate video title."""
        if len(value) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters long.")
        return value
    
    def validate_video_file(self, value):
        """Validate video file."""
        if value:
            # Check file extension
            allowed_extensions = ['.mp4', '.webm', '.ogg', '.mov', '.avi']
            if not any(value.name.lower().endswith(ext) for ext in allowed_extensions):
                raise serializers.ValidationError(
                    "Video file must be one of: mp4, webm, ogg, mov, avi"
                )
            # Check file size (max 500MB)
            max_size = 500 * 1024 * 1024  # 500MB
            if value.size > max_size:
                raise serializers.ValidationError(
                    f"Video file too large. Maximum size is {max_size // (1024*1024)}MB"
                )
        return value

    def validate(self, data):
        """Validate that either video_file or external_video_url is provided."""
        video_file = data.get('video_file')
        external_video_url = data.get('external_video_url')
        
        if not video_file and not external_video_url:
            raise serializers.ValidationError(
                "Either a video file or an external video URL must be provided."
            )
            
        if video_file and external_video_url:
            raise serializers.ValidationError(
                "Please provide either a video file or an external video URL, not both."
            )
            
        return data


class ContactSerializer(serializers.ModelSerializer):
    """
    Serializer for Contact model.
    """
    
    class Meta:
        model = Contact
        fields = ['id', 'name', 'email', 'subject', 'message', 'is_read', 'created_at']
        read_only_fields = ['id', 'is_read', 'created_at']

