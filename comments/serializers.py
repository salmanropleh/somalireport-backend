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
    
    # Explicitly hide internal fields
    content_type = serializers.HiddenField(default=None)
    object_id = serializers.HiddenField(default=None)
    ip_address = serializers.HiddenField(default=None)
    user_agent = serializers.HiddenField(default=None)
    moderated_by = serializers.HiddenField(default=None)
    moderated_at = serializers.HiddenField(default=None)
    
    class Meta:
        model = Comment
        fields = '__all__'
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
    
    def to_representation(self, instance):
        """Custom representation to exclude internal fields."""
        # Get the standard representation
        ret = super().to_representation(instance)
        # Remove internal fields we don't want to expose
        ret.pop('content_type', None)
        ret.pop('object_id', None)
        ret.pop('ip_address', None)
        ret.pop('user_agent', None)
        ret.pop('moderated_by', None)
        ret.pop('moderated_at', None)
        return ret


class CommentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating comments.
    """
    
    content_type = serializers.IntegerField(help_text="ContentType ID for the content being commented on")
    object_id = serializers.IntegerField(help_text="ID of the content object")
    
    class Meta:
        model = Comment
        fields = [
            'content_type', 'object_id', 'content', 'parent', 
            'author_name', 'author_email', 'author_website'
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
    
    def validate_content_type(self, value):
        """Validate that content_type exists."""
        try:
            ContentType.objects.get(pk=value)
            return value  # Return the ID
        except ContentType.DoesNotExist:
            raise serializers.ValidationError("Invalid content_type ID.")
    
    def validate(self, attrs):
        """Validate that the object exists."""
        content_type_id = attrs.get('content_type')
        object_id = attrs.get('object_id')
        
        if content_type_id and object_id:
            try:
                content_type = ContentType.objects.get(pk=content_type_id)
                content_object = content_type.get_object_for_this_type(pk=object_id)
                if not content_object:
                    raise serializers.ValidationError({
                        'object_id': 'Content object not found.'
                    })
            except Exception as e:
                raise serializers.ValidationError({
                    'object_id': 'Invalid content object.'
                })
        
        return attrs
    
    def create(self, validated_data):
        """Create comment with content_type."""
        content_type_id = validated_data.pop('content_type')
        object_id = validated_data.pop('object_id')
        
        validated_data['content_type_id'] = content_type_id
        validated_data['object_id'] = object_id
        
        instance = super().create(validated_data)
        
        # Use CommentSerializer for the response to avoid content_type serialization issues
        return instance
    
    def to_representation(self, instance):
        """Use CommentSerializer for output to avoid internal field issues."""
        from .serializers import CommentSerializer
        return CommentSerializer(instance, context=self.context).to_representation(instance)


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
