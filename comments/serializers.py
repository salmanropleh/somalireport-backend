"""
Serializers for comments app.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from .models import Comment, CommentLike, CommentReport, CommentSubscription

User = get_user_model()


class CommentSerializer(serializers.ModelSerializer):
    """
    Serializer for Comment model.
    """
    
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_avatar = serializers.ImageField(source='user.avatar', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_disliked = serializers.SerializerMethodField()
    depth = serializers.ReadOnlyField()
    is_reply = serializers.ReadOnlyField()
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'parent', 'user', 'user_name', 'user_avatar',
            'author_name', 'author_email', 'author_website', 'status',
            'is_approved', 'like_count', 'dislike_count', 'reply_count',
            'is_liked', 'is_disliked', 'depth', 'is_reply', 'replies',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'status', 'is_approved', 'like_count',
            'dislike_count', 'reply_count', 'created_at', 'updated_at'
        ]
    
    def get_is_liked(self, obj):
        """Check if current user has liked this comment."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user, like_type='like').exists()
        return False
    
    def get_is_disliked(self, obj):
        """Check if current user has disliked this comment."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user, like_type='dislike').exists()
        return False
    
    def get_replies(self, obj):
        """Get replies to this comment."""
        replies = obj.replies.filter(is_approved=True).order_by('created_at')
        return CommentSerializer(replies, many=True, context=self.context).data


class CommentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating comments.
    """
    
    class Meta:
        model = Comment
        fields = [
            'content', 'parent', 'author_name', 'author_email', 'author_website'
        ]
    
    def validate_content(self, value):
        """Validate comment content."""
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Comment must be at least 10 characters long.")
        if len(value) > 1000:
            raise serializers.ValidationError("Comment must be less than 1000 characters.")
        return value
    
    def validate_parent(self, value):
        """Validate parent comment."""
        if value and value.depth >= 3:
            raise serializers.ValidationError("Maximum comment depth is 3 levels.")
        return value


class CommentModerationSerializer(serializers.ModelSerializer):
    """
    Serializer for comment moderation.
    """
    
    class Meta:
        model = Comment
        fields = ['status', 'is_approved']
    
    def validate_status(self, value):
        """Validate status change."""
        if value == 'approved':
            self.instance.is_approved = True
        elif value in ['rejected', 'spam']:
            self.instance.is_approved = False
        return value


class CommentLikeSerializer(serializers.ModelSerializer):
    """
    Serializer for CommentLike model.
    """
    
    class Meta:
        model = CommentLike
        fields = ['comment', 'like_type']
    
    def validate_like_type(self, value):
        """Validate like type."""
        if value not in ['like', 'dislike']:
            raise serializers.ValidationError("Like type must be 'like' or 'dislike'.")
        return value


class CommentReportSerializer(serializers.ModelSerializer):
    """
    Serializer for CommentReport model.
    """
    
    class Meta:
        model = CommentReport
        fields = ['comment', 'reason', 'description']
    
    def validate_reason(self, value):
        """Validate report reason."""
        if value not in [choice[0] for choice in CommentReport.REPORT_REASONS]:
            raise serializers.ValidationError("Invalid report reason.")
        return value


class CommentSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for CommentSubscription model.
    """
    
    class Meta:
        model = CommentSubscription
        fields = ['content_type', 'object_id', 'is_active']
    
    def validate(self, attrs):
        """Validate subscription data."""
        content_type = attrs.get('content_type')
        object_id = attrs.get('object_id')
        
        if content_type and object_id:
            try:
                content_object = content_type.get_object_for_this_type(pk=object_id)
                if not content_object:
                    raise serializers.ValidationError("Content object not found.")
            except Exception:
                raise serializers.ValidationError("Invalid content object.")
        
        return attrs


class CommentStatsSerializer(serializers.Serializer):
    """
    Serializer for comment statistics.
    """
    
    total_comments = serializers.IntegerField()
    approved_comments = serializers.IntegerField()
    pending_comments = serializers.IntegerField()
    rejected_comments = serializers.IntegerField()
    spam_comments = serializers.IntegerField()
    total_likes = serializers.IntegerField()
    total_dislikes = serializers.IntegerField()
    total_reports = serializers.IntegerField()
    unresolved_reports = serializers.IntegerField()
