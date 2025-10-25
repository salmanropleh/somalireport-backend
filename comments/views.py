"""
Views for comments app.
"""

from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Count
from django.utils import timezone

from .models import Comment, CommentLike, CommentReport, CommentSubscription
from .serializers import (
    CommentSerializer, CommentCreateSerializer, CommentModerationSerializer,
    CommentLikeSerializer, CommentReportSerializer, CommentSubscriptionSerializer,
    CommentStatsSerializer
)
from core.utils import APIResponse
from core.permissions import IsEditorOrReadOnly, IsOwnerOrReadOnly


class CommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Comment management.
    """
    
    queryset = Comment.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'is_approved', 'user', 'parent']
    search_fields = ['content', 'author_name', 'author_email']
    ordering_fields = ['created_at', 'like_count', 'dislike_count']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return CommentCreateSerializer
        elif self.action in ['moderate', 'approve', 'reject', 'mark_spam']:
            return CommentModerationSerializer
        return CommentSerializer
    
    def get_queryset(self):
        """Return comments based on user permissions."""
        queryset = Comment.objects.select_related('user', 'parent').prefetch_related('likes')
        
        # If user is not authenticated, only show approved comments
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(is_approved=True)
        # If user is a reader, show approved comments and their own comments
        elif self.request.user.role == 'reader':
            queryset = queryset.filter(
                Q(is_approved=True) | Q(user=self.request.user)
            )
        # Editors and admins can see all comments
        elif self.request.user.role in ['editor', 'admin'] or self.request.user.is_staff:
            pass  # Show all comments
        
        return queryset
    
    def perform_create(self, serializer):
        """Set user and IP when creating comment."""
        serializer.save(
            user=self.request.user,
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
    
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Like/dislike comment."""
        comment = self.get_object()
        like_type = request.data.get('like_type', 'like')
        
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        like, created = CommentLike.objects.get_or_create(
            comment=comment,
            user=request.user,
            defaults={'like_type': like_type}
        )
        
        if created:
            if like_type == 'like':
                comment.like_count += 1
            else:
                comment.dislike_count += 1
            comment.save(update_fields=['like_count', 'dislike_count'])
            return APIResponse.success(message=f"Comment {like_type}d")
        else:
            # Update existing like
            old_type = like.like_type
            like.like_type = like_type
            like.save()
            
            # Update counts
            if old_type == 'like' and like_type == 'dislike':
                comment.like_count -= 1
                comment.dislike_count += 1
            elif old_type == 'dislike' and like_type == 'like':
                comment.dislike_count -= 1
                comment.like_count += 1
            
            comment.save(update_fields=['like_count', 'dislike_count'])
            return APIResponse.success(message=f"Comment {like_type}d")
    
    @action(detail=True, methods=['post'])
    def unlike(self, request, pk=None):
        """Remove like/dislike from comment."""
        comment = self.get_object()
        
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            like = CommentLike.objects.get(comment=comment, user=request.user)
            like_type = like.like_type
            like.delete()
            
            # Update counts
            if like_type == 'like':
                comment.like_count -= 1
            else:
                comment.dislike_count -= 1
            comment.save(update_fields=['like_count', 'dislike_count'])
            
            return APIResponse.success(message="Like removed")
        except CommentLike.DoesNotExist:
            return APIResponse.error(message="Like not found")
    
    @action(detail=True, methods=['post'])
    def report(self, request, pk=None):
        """Report comment."""
        comment = self.get_object()
        
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        serializer = CommentReportSerializer(data=request.data)
        if serializer.is_valid():
            report, created = CommentReport.objects.get_or_create(
                comment=comment,
                reporter=request.user,
                defaults=serializer.validated_data
            )
            
            if created:
                return APIResponse.success(message="Comment reported")
            else:
                return APIResponse.error(message="Comment already reported by you")
        
        return APIResponse.error(message="Report failed", errors=serializer.errors)
    
    @action(detail=True, methods=['post'], permission_classes=[IsEditorOrReadOnly])
    def approve(self, request, pk=None):
        """Approve comment."""
        comment = self.get_object()
        comment.approve(request.user)
        return APIResponse.success(message="Comment approved")
    
    @action(detail=True, methods=['post'], permission_classes=[IsEditorOrReadOnly])
    def reject(self, request, pk=None):
        """Reject comment."""
        comment = self.get_object()
        comment.reject(request.user)
        return APIResponse.success(message="Comment rejected")
    
    @action(detail=True, methods=['post'], permission_classes=[IsEditorOrReadOnly])
    def mark_spam(self, request, pk=None):
        """Mark comment as spam."""
        comment = self.get_object()
        comment.mark_as_spam(request.user)
        return APIResponse.success(message="Comment marked as spam")
    
    @action(detail=False, methods=['get'], permission_classes=[IsEditorOrReadOnly])
    def pending(self, request):
        """Get pending comments for moderation."""
        comments = self.get_queryset().filter(status='pending')
        serializer = self.get_serializer(comments, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Pending comments retrieved")
    
    @action(detail=False, methods=['get'], permission_classes=[IsEditorOrReadOnly])
    def stats(self, request):
        """Get comment statistics."""
        stats = {
            'total_comments': Comment.objects.count(),
            'approved_comments': Comment.objects.filter(status='approved').count(),
            'pending_comments': Comment.objects.filter(status='pending').count(),
            'rejected_comments': Comment.objects.filter(status='rejected').count(),
            'spam_comments': Comment.objects.filter(status='spam').count(),
            'total_likes': CommentLike.objects.filter(like_type='like').count(),
            'total_dislikes': CommentLike.objects.filter(like_type='dislike').count(),
            'total_reports': CommentReport.objects.count(),
            'unresolved_reports': CommentReport.objects.filter(is_resolved=False).count(),
        }
        
        serializer = CommentStatsSerializer(stats)
        return APIResponse.success(data=serializer.data, message="Comment statistics retrieved")


class CommentReportViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for CommentReport management.
    """
    
    queryset = CommentReport.objects.all()
    serializer_class = CommentReportSerializer
    permission_classes = [IsEditorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['reason', 'is_resolved', 'reporter']
    search_fields = ['description']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['post'], permission_classes=[IsEditorOrReadOnly])
    def resolve(self, request, pk=None):
        """Resolve comment report."""
        report = self.get_object()
        report.is_resolved = True
        report.resolved_by = request.user
        report.resolved_at = timezone.now()
        report.save()
        
        return APIResponse.success(message="Report resolved")


class CommentSubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CommentSubscription management.
    """
    
    queryset = CommentSubscription.objects.all()
    serializer_class = CommentSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return subscriptions for current user."""
        return CommentSubscription.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Set user when creating subscription."""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def my_subscriptions(self, request):
        """Get current user's subscriptions."""
        subscriptions = self.get_queryset()
        serializer = self.get_serializer(subscriptions, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Subscriptions retrieved")