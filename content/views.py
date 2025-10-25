"""
Views for content app.
"""

from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404

from .models import Category, Tag, Article, MediaFile, ArticleView, ArticleLike, ArticleShare
from .serializers import (
    CategorySerializer, TagSerializer, ArticleListSerializer,
    ArticleDetailSerializer, ArticleCreateUpdateSerializer,
    MediaFileSerializer, ArticleViewSerializer, ArticleLikeSerializer,
    ArticleShareSerializer
)
from core.utils import APIResponse
from core.permissions import IsEditorOrReadOnly, IsReporterOrReadOnly, IsOwnerOrReadOnly

class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Category management.
    """
    
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [IsEditorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'sort_order', 'created_at']
    ordering = ['sort_order', 'name']
    
    def get_queryset(self):
        """Return categories with article counts."""
        return Category.objects.filter(is_active=True).annotate(
            article_count=Count('article', filter=Q(article__status='published'))
        )
    
    @action(detail=True, methods=['get'])
    def articles(self, request, pk=None):
        """Get articles in this category."""
        category = self.get_object()
        articles = Article.objects.filter(
            category=category,
            status='published'
        ).order_by('-published_at')
        
        serializer = ArticleListSerializer(articles, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Category articles retrieved")


class TagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Tag management.
    """
    
    queryset = Tag.objects.filter(is_active=True)
    serializer_class = TagSerializer
    permission_classes = [IsEditorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Return tags with article counts."""
        return Tag.objects.filter(is_active=True).annotate(
            article_count=Count('article', filter=Q(article__status='published'))
        )
    
    @action(detail=True, methods=['get'])
    def articles(self, request, pk=None):
        """Get articles with this tag."""
        tag = self.get_object()
        articles = Article.objects.filter(
            tags=tag,
            status='published'
        ).order_by('-published_at')
        
        serializer = ArticleListSerializer(articles, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Tag articles retrieved")


class ArticleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Article management.
    """
    
    queryset = Article.objects.all()
    permission_classes = [IsReporterOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category', 'tags', 'author', 'is_featured', 'is_breaking']
    search_fields = ['title', 'excerpt', 'content']
    ordering_fields = ['created_at', 'published_at', 'view_count', 'like_count']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ArticleListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ArticleCreateUpdateSerializer
        return ArticleDetailSerializer
    
    def get_queryset(self):
        """Return articles based on user permissions."""
        queryset = Article.objects.select_related('author', 'category').prefetch_related('tags')
        
        # If user is not authenticated or is a reader, only show published articles
        if not self.request.user.is_authenticated or self.request.user.role == 'reader':
            queryset = queryset.filter(status='published')
        # If user is a reporter, show their own articles and published articles
        elif self.request.user.role == 'reporter':
            queryset = queryset.filter(
                Q(status='published') | Q(author=self.request.user)
            )
        # Editors and admins can see all articles
        elif self.request.user.role in ['editor', 'admin'] or self.request.user.is_staff:
            pass  # Show all articles
        
        return queryset
    
    def perform_create(self, serializer):
        """Set author when creating article."""
        serializer.save(author=self.request.user)
    
    def perform_update(self, serializer):
        """Set updated_by when updating article."""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Record article view."""
        article = self.get_object()
        
        # Create view record
        ArticleView.objects.create(
            article=article,
            user=request.user if request.user.is_authenticated else None,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referrer=request.META.get('HTTP_REFERER'),
            session_id=request.session.session_key
        )
        
        # Increment view count
        article.increment_view_count()
        
        return APIResponse.success(message="View recorded")
    
    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Like/unlike article."""
        article = self.get_object()
        
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        like, created = ArticleLike.objects.get_or_create(
            article=article,
            user=request.user
        )
        
        if created:
            article.like_count += 1
            article.save(update_fields=['like_count'])
            return APIResponse.success(message="Article liked")
        else:
            like.delete()
            article.like_count -= 1
            article.save(update_fields=['like_count'])
            return APIResponse.success(message="Article unliked")
    
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Record article share."""
        article = self.get_object()
        platform = request.data.get('platform', 'other')
        
        ArticleShare.objects.create(
            article=article,
            user=request.user if request.user.is_authenticated else None,
            platform=platform,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        article.share_count += 1
        article.save(update_fields=['share_count'])
        
        return APIResponse.success(message="Share recorded")
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured articles."""
        articles = self.get_queryset().filter(is_featured=True, status='published')
        serializer = self.get_serializer(articles, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Featured articles retrieved")
    
    @action(detail=False, methods=['get'])
    def breaking(self, request):
        """Get breaking news articles."""
        articles = self.get_queryset().filter(is_breaking=True, status='published')
        serializer = self.get_serializer(articles, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Breaking news retrieved")
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending articles based on views and likes."""
        articles = self.get_queryset().filter(status='published').order_by(
            '-view_count', '-like_count', '-created_at'
        )[:10]
        serializer = self.get_serializer(articles, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Trending articles retrieved")


class MediaFileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for MediaFile management.
    """
    
    queryset = MediaFile.objects.all()
    serializer_class = MediaFileSerializer
    permission_classes = [IsReporterOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['file_type', 'uploaded_by', 'article']
    search_fields = ['name', 'alt_text', 'caption']
    ordering_fields = ['created_at', 'file_size']
    ordering = ['-created_at']
    
    def perform_create(self, serializer):
        """Set uploaded_by when creating media file."""
        serializer.save(uploaded_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def images(self, request):
        """Get only image files."""
        images = self.get_queryset().filter(file_type='image')
        serializer = self.get_serializer(images, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Images retrieved")
    
    @action(detail=False, methods=['get'])
    def videos(self, request):
        """Get only video files."""
        videos = self.get_queryset().filter(file_type='video')
        serializer = self.get_serializer(videos, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Videos retrieved")