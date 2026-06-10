"""
Serializers for newsletter app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Newsletter, NewsletterSubscription, NewsletterRead

User = get_user_model()


class NewsletterSubscribeSerializer(serializers.Serializer):
    """
    Serializer for subscribing to the newsletter.
    """

    email = serializers.EmailField()

    def validate_email(self, value):
        """Validate email and check for existing active subscription."""
        value = value.lower().strip()

        # Check if already subscribed and active
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
        """Validate unsubscribe token."""
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
            'sent_at', 'recipient_count', 'open_count',
            'is_read', 'created_at'
        ]
        read_only_fields = [
            'id', 'slug', 'sent_at', 'recipient_count',
            'open_count', 'created_at'
        ]

    def get_is_read(self, obj):
        """Check if the current user has read this newsletter."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        # Get user's subscription
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
        """Get featured image URL."""
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

    class Meta:
        model = Newsletter
        fields = [
            'id', 'title', 'slug', 'subject', 'excerpt',
            'content_html', 'content_text', 'featured_image',
            'featured_image_url', 'status', 'sent_at',
            'recipient_count', 'open_count', 'is_read',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'sent_at', 'recipient_count',
            'open_count', 'created_by', 'created_at', 'updated_at'
        ]

    def get_is_read(self, obj):
        """Check if the current user has read this newsletter."""
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
        """Get featured image URL."""
        if obj.featured_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            return obj.featured_image.url
        return None


class NewsletterCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating newsletters.
    """

    class Meta:
        model = Newsletter
        fields = [
            'title', 'subject', 'excerpt', 'content_html',
            'content_text', 'featured_image', 'status'
        ]

    def validate_title(self, value):
        """Validate newsletter title."""
        if len(value) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters long.")
        return value

    def validate_subject(self, value):
        """Validate email subject."""
        if len(value) < 5:
            raise serializers.ValidationError("Subject must be at least 5 characters long.")
        return value

    def validate_content_html(self, value):
        """Validate HTML content."""
        if len(value) < 50:
            raise serializers.ValidationError("HTML content must be at least 50 characters long.")
        return value

    def validate_content_text(self, value):
        """Validate text content."""
        if len(value) < 20:
            raise serializers.ValidationError("Text content must be at least 20 characters long.")
        return value

    def validate(self, data):
        """Validate the newsletter data."""
        # Cannot change status to 'sent' directly via this serializer
        if data.get('status') == 'sent':
            raise serializers.ValidationError({
                'status': "Cannot set status to 'sent' directly. Use the send endpoint."
            })
        return data


class NewsletterSendSerializer(serializers.Serializer):
    """
    Serializer for sending newsletter.
    """

    test_email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)

    def validate_test_email(self, value):
        """Validate optional test email."""
        if value:
            return value.lower().strip()
        return value
