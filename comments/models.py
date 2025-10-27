"""
Comment models for Somali Report Backend.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from core.models import BaseModel

User = get_user_model()


class Comment(BaseModel):
    """
    Comment model for articles and other content.
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('spam', 'Spam'),
    ]
    
    # Generic foreign key to link to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Comment content
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # User information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    author_name = models.CharField(max_length=100, blank=True, null=True)
    author_email = models.EmailField(blank=True, null=True)
    author_website = models.URLField(blank=True, null=True)
    
    # Moderation
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_approved = models.BooleanField(default=False)
    moderated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_comments')
    moderated_at = models.DateTimeField(null=True, blank=True)
    
    # User agent and IP for spam detection
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    
    # Analytics
    like_count = models.PositiveIntegerField(default=0)
    dislike_count = models.PositiveIntegerField(default=0)
    reply_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'comments'
        verbose_name = 'Comment'
        verbose_name_plural = 'Comments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment by {self.user.email if self.user else self.author_name} on {self.content_object}"
    
    @property
    def is_reply(self):
        """Check if this is a reply to another comment."""
        return self.parent is not None
    
    @property
    def depth(self):
        """Get comment depth (0 for top-level, 1 for replies, etc.)."""
        depth = 0
        parent = self.parent
        while parent:
            depth += 1
            parent = parent.parent
        return depth
    
    def approve(self, moderator):
        """Approve comment."""
        self.status = 'approved'
        self.is_approved = True
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save()
    
    def reject(self, moderator):
        """Reject comment."""
        self.status = 'rejected'
        self.is_approved = False
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save()
    
    def mark_as_spam(self, moderator):
        """Mark comment as spam."""
        self.status = 'spam'
        self.is_approved = False
        self.moderated_by = moderator
        self.moderated_at = timezone.now()
        self.save()


class CommentLike(BaseModel):
    """
    Comment like/dislike model.
    """
    
    LIKE_CHOICES = [
        ('like', 'Like'),
        ('dislike', 'Dislike'),
    ]
    
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_likes')
    like_type = models.CharField(max_length=10, choices=LIKE_CHOICES)
    
    class Meta:
        db_table = 'comment_likes'
        verbose_name = 'Comment Like'
        verbose_name_plural = 'Comment Likes'
        unique_together = ['comment', 'user']
    
    def __str__(self):
        return f"{self.user.email} {self.like_type}s comment {self.comment.id}"


class CommentReport(BaseModel):
    """
    Comment report model for reporting inappropriate comments.
    """
    
    REPORT_REASONS = [
        ('spam', 'Spam'),
        ('inappropriate', 'Inappropriate Content'),
        ('harassment', 'Harassment'),
        ('hate_speech', 'Hate Speech'),
        ('fake_news', 'Fake News'),
        ('other', 'Other'),
    ]
    
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_reports')
    reason = models.CharField(max_length=20, choices=REPORT_REASONS)
    description = models.TextField(blank=True, null=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_reports')
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'comment_reports'
        verbose_name = 'Comment Report'
        verbose_name_plural = 'Comment Reports'
        unique_together = ['comment', 'reporter']
    
    def __str__(self):
        return f"Report on comment {self.comment.id} by {self.reporter.email}"


class CommentSubscription(BaseModel):
    """
    Comment subscription model for email notifications.
    """
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_subscriptions')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'comment_subscriptions'
        verbose_name = 'Comment Subscription'
        verbose_name_plural = 'Comment Subscriptions'
        unique_together = ['user', 'content_type', 'object_id']
    
    def __str__(self):
        return f"{self.user.email} subscribed to comments on {self.content_object}"