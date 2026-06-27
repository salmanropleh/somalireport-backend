"""
Serializers for newsletter app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Newsletter, NewsletterSubscription, NewsletterRead
from content.models import Article

User = get_user_model()


class NewsletterSubscribeSerializer(serializers.Serializer):
    """
    Serializer for subscribing to the newsletter.
    """

    email = serializers.EmailField()

    def validate_email(self, value):
        value = value.lower().strip()

        existing = NewsletterSubscription.objects.filter(
            email=value,
            is_active=True,
            is_deleted=False
        ).first()

        if existing:
            raise serializers.ValidationError("This email is already subscribed.")

        return value


class NewsletterUnsubscribeSerializer(serializers.Serializer):
    """
    Serializer for unsubscribing from the newsletter.
    """

    token = serializers.CharField(max_length=64)

    def validate_token(self, value):
        subscription = NewsletterSubscription.objects.filter(
            unsubscribe_token=value,
            is_active=True,
            is_deleted=False
        ).first()

        if not subscription:
            raise serializers.ValidationError("Invalid or expired unsubscribe token.")

        return value


class NewsletterSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for subscription details.
    """

    class Meta:
        model = NewsletterSubscription
        fields = [
            'id', 'email', 'is_active', 'created_at', 'unsubscribed_at'
        ]
        read_only_fields = ['id', 'email', 'created_at', 'unsubscribed_at']


class NewsletterSubscriptionAdminSerializer(serializers.ModelSerializer):
    """
    Admin serializer for subscription details with user info.
    """

    user_email = serializers.CharField(source='user.email', read_only=True, allow_null=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True, allow_null=True)

    class Meta:
        model = NewsletterSubscription
        fields = [
            'id', 'email', 'user', 'user_email', 'user_name',
            'is_active', 'unsubscribe_token', 'created_at',
            'updated_at', 'unsubscribed_at'
        ]
        read_only_fields = ['id', 'unsubscribe_token', 'created_at', 'updated_at']


class ArticlePickerSerializer(serializers.Serializer):
    """
    Lightweight serializer for article picker in campaign composer.
    """

    id = serializers.IntegerField()
    title = serializers.CharField()
    slug = serializers.CharField()
    excerpt = serializers.CharField()
    featured_image_url = serializers.SerializerMethodField()
    published_at = serializers.DateTimeField()

    def get_featured_image_url(self, obj):
        request = self.context.get('request')
        if obj.featured_image_url:
            return obj.featured_image_url
        if obj.featured_image:
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None


class ArticleSummarySerializer(serializers.Serializer):
    """
    Nested article summary for newsletter detail views.
    """

    id = serializers.IntegerField()
    title = serializers.CharField()
    slug = serializers.CharField()
    excerpt = serializers.CharField()
    featured_image_url = serializers.SerializerMethodField()
    published_at = serializers.DateTimeField()

    def get_featured_image_url(self, obj):
        request = self.context.get('request')
        if obj.featured_image_url:
            return obj.featured_image_url
        if obj.featured_image:
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None


class NewsletterListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for newsletter list view.
    """

    is_read = serializers.SerializerMethodField()
    featured_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Newsletter
        fields = [
            'id', 'title', 'slug', 'subject', 'excerpt',
            'featured_image', 'featured_image_url', 'status',
            'email_type', 'template_style', 'recipients_type',
            'header_image_url', 'text_blocks',
            'sent_at', 'recipient_count', 'open_count',
            'is_read', 'created_at'
        ]
        read_only_fields = [
            'id', 'slug', 'sent_at', 'recipient_count',
            'open_count', 'created_at'
        ]

    def get_is_read(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        try:
            subscription = NewsletterSubscription.objects.get(
                user=request.user,
                is_active=True,
                is_deleted=False
            )
            return NewsletterRead.objects.filter(
                newsletter=obj,
                subscription=subscription
            ).exists()
        except NewsletterSubscription.DoesNotExist:
            return None

    def get_featured_image_url(self, obj):
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None


class NewsletterDetailSerializer(serializers.ModelSerializer):
    """
    Full detail serializer for newsletter.
    """

    is_read = serializers.SerializerMethodField()
    featured_image_url = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, allow_null=True)
    articles_data = serializers.SerializerMethodField()

    class Meta:
        model = Newsletter
        fields = [
            'id', 'title', 'slug', 'subject', 'excerpt',
            'content_html', 'content_text', 'featured_image',
            'featured_image_url', 'status', 'sent_at',
            'recipient_count', 'open_count', 'is_read',
            'email_type', 'template_style', 'accent_color',
            'greeting_text', 'recipients_type', 'custom_recipients',
            'header_image_url', 'text_blocks',
            'articles', 'article_order', 'articles_data',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'sent_at', 'recipient_count',
            'open_count', 'created_by', 'created_at', 'updated_at',
            'articles_data'
        ]

    def get_is_read(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        try:
            subscription = NewsletterSubscription.objects.get(
                user=request.user,
                is_active=True,
                is_deleted=False
            )
            return NewsletterRead.objects.filter(
                newsletter=obj,
                subscription=subscription
            ).exists()
        except NewsletterSubscription.DoesNotExist:
            return None

    def get_featured_image_url(self, obj):
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None

    def get_articles_data(self, obj):
        """Return articles in the order specified by article_order."""
        articles = list(obj.articles.all())
        if obj.article_order:
            order_map = {aid: idx for idx, aid in enumerate(obj.article_order)}
            articles.sort(key=lambda a: order_map.get(a.id, 9999))
        serializer = ArticleSummarySerializer(articles, many=True, context=self.context)
        return serializer.data


class NewsletterCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating newsletters / email campaigns.
    """

    articles = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=False,
        required=False,
        queryset=Article.objects.filter(status='published', is_deleted=False)
    )
    header_image_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    text_blocks = serializers.JSONField(required=False, default=list)

    class Meta:
        model = Newsletter
        fields = [
            'id', 'title', 'subject', 'excerpt', 'content_html',
            'content_text', 'featured_image', 'status',
            'email_type', 'template_style', 'accent_color',
            'greeting_text', 'recipients_type', 'custom_recipients',
            'header_image_url', 'text_blocks',
            'articles', 'article_order',
        ]
        read_only_fields = ['id']

    def validate_title(self, value):
        if len(value) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters long.")
        return value

    def validate_subject(self, value):
        if len(value) < 5:
            raise serializers.ValidationError("Subject must be at least 5 characters long.")
        return value

    def validate(self, data):
        if data.get('status') == 'sent':
            raise serializers.ValidationError({
                'status': "Cannot set status to 'sent' directly. Use the send endpoint."
            })

        email_type = data.get('email_type', 'newsletter')

        # Direct emails require body content
        if email_type == 'direct':
            content_html = data.get('content_html', '')
            if not content_html or len(content_html) < 20:
                raise serializers.ValidationError({
                    'content_html': "Direct emails require HTML content (at least 20 characters)."
                })

        # Custom recipients require addresses
        if data.get('recipients_type') == 'custom':
            if not data.get('custom_recipients', '').strip():
                raise serializers.ValidationError({
                    'custom_recipients': "Please provide at least one email address for custom recipients."
                })

        return data

    def create(self, validated_data):
        articles = validated_data.pop('articles', [])
        if validated_data.get('header_image_url') is None:
            validated_data['header_image_url'] = ''
        if validated_data.get('text_blocks') is None:
            validated_data['text_blocks'] = []
        instance = super().create(validated_data)
        if articles:
            instance.articles.set(articles)
        return instance

    def update(self, instance, validated_data):
        articles = validated_data.pop('articles', None)
        if validated_data.get('header_image_url') is None:
            validated_data['header_image_url'] = ''
        if validated_data.get('text_blocks') is None:
            validated_data['text_blocks'] = []
        instance = super().update(instance, validated_data)
        if articles is not None:
            instance.articles.set(articles)
        return instance


class NewsletterSendSerializer(serializers.Serializer):
    """
    Serializer for sending newsletter.
    """

    test_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)

    def validate_test_email(self, value):
        if value:
            return value.lower().strip()
        return value


class NewsletterPublicListSerializer(serializers.ModelSerializer):
    featured_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Newsletter
        fields = ['id', 'title', 'slug', 'subject', 'excerpt', 'featured_image_url', 'sent_at']

    def get_featured_image_url(self, obj):
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None


class NewsletterPublicDetailSerializer(serializers.ModelSerializer):
    featured_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Newsletter
        fields = ['id', 'title', 'slug', 'subject', 'excerpt', 'content_html', 'featured_image_url', 'sent_at']

    def get_featured_image_url(self, obj):
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None
