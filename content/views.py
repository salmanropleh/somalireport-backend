"""
Views for content app.
"""

from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os
import mimetypes
from PIL import Image
from drf_spectacular.utils import extend_schema

from .models import Category, Tag, Article, MediaFile, Video, ArticleView, ArticleLike, ArticleShare
from .serializers import (
    CategorySerializer, TagSerializer, ArticleListSerializer,
    ArticleDetailSerializer, ArticleCreateUpdateSerializer,
    MediaFileSerializer, ArticleViewSerializer, ArticleLikeSerializer,
    ArticleShareSerializer, VideoListSerializer, VideoDetailSerializer, VideoCreateUpdateSerializer
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
        from django.db.models import Count, Q
        
        return Category.objects.filter(
            is_active=True,
            is_deleted=False
        ).annotate(
            article_count=Count('primary_articles', filter=Q(primary_articles__status='published')) + 
                         Count('secondary_articles', filter=Q(secondary_articles__status='published'))
        )
    
    def destroy(self, request, *args, **kwargs):
        """Delete a category and handle related articles."""
        try:
            category = self.get_object()
            category_name = category.name
            
            # Get articles that will be affected
            primary_articles = Article.objects.filter(primary_category=category)
            secondary_articles = Article.objects.filter(secondary_categories=category)
            
            # Count affected articles
            primary_count = primary_articles.count()
            secondary_count = secondary_articles.count()
            total_affected = primary_count + secondary_count
            
            # Handle related articles before deleting the category
            if primary_count > 0:
                # Set primary_category to NULL for articles using this category as primary
                primary_articles.update(primary_category=None)
            
            if secondary_count > 0:
                # Remove this category from secondary_categories for all articles
                for article in secondary_articles:
                    article.secondary_categories.remove(category)
            
            # Hard delete the category (permanently remove from database)
            category.hard_delete()
            
            # Prepare response message
            message_parts = [f"Category '{category_name}' deleted successfully"]
            if total_affected > 0:
                affected_msg = []
                if primary_count > 0:
                    affected_msg.append(f"{primary_count} article(s) had their primary category removed")
                if secondary_count > 0:
                    affected_msg.append(f"{secondary_count} article(s) had this category removed from their secondary categories")
                message_parts.append(f"Affected articles: {', '.join(affected_msg)}")
            
            return APIResponse.success(
                message=". ".join(message_parts),
                data={
                    'deleted_category': {
                        'id': category.id,
                        'name': category_name
                    },
                    'affected_articles': {
                        'primary_count': primary_count,
                        'secondary_count': secondary_count,
                        'total_count': total_affected
                    }
                }
            )
            
        except Exception as e:
            return APIResponse.error(
                message=f"Failed to delete category: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def inactive(self, request):
        """Get inactive categories (for admin purposes)."""
        inactive_categories = Category.objects.filter(
            Q(is_active=False) | Q(is_deleted=True)
        )
        serializer = self.get_serializer(inactive_categories, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Inactive categories retrieved")
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore an inactive category."""
        try:
            # Get the category (including inactive ones)
            category = get_object_or_404(Category, pk=pk)
            
            if category.is_active:
                return APIResponse.error(
                    message="Category is already active",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Restore the category
            category.is_active = True
            category.save(update_fields=['is_active'])
            
            serializer = self.get_serializer(category, context={'request': request})
            
            return APIResponse.success(
                data=serializer.data,
                message=f"Category '{category.name}' restored successfully"
            )
            
        except Exception as e:
            return APIResponse.error(
                message=f"Failed to restore category: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def deleted(self, request):
        """Get soft-deleted categories (for admin purposes)."""
        deleted_categories = Category.objects.filter(is_deleted=True)
        serializer = self.get_serializer(deleted_categories, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Deleted categories retrieved")
    
    @action(detail=True, methods=['post'])
    def restore_deleted(self, request, pk=None):
        """Restore a soft-deleted category."""
        try:
            # Get the category (including soft-deleted ones)
            category = get_object_or_404(Category, pk=pk)
            
            if not category.is_deleted:
                return APIResponse.error(
                    message="Category is not deleted",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Restore the category
            category.is_deleted = False
            category.deleted_at = None
            category.is_active = True  # Also make it active
            category.save(update_fields=['is_deleted', 'deleted_at', 'is_active'])
            
            serializer = self.get_serializer(category, context={'request': request})
            
            return APIResponse.success(
                data=serializer.data,
                message=f"Category '{category.name}' restored successfully"
            )
            
        except Exception as e:
            return APIResponse.error(
                message=f"Failed to restore category: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def articles(self, request, pk=None):
        """Get articles in this category with filtering options."""
        from django.db.models import Q
        from django_filters.rest_framework import DjangoFilterBackend
        from rest_framework import filters
        
        category = self.get_object()
        
        # Base queryset - articles in this category (primary or secondary)
        articles = Article.objects.filter(
            Q(primary_category=category) | Q(secondary_categories=category),
            status='published'
        ).select_related('author', 'primary_category').prefetch_related('tags', 'secondary_categories')
        
        # Apply filters
        filterset_fields = ['tags', 'author', 'is_featured', 'is_breaking']
        search_fields = ['title', 'excerpt', 'content']
        ordering_fields = ['published_at', 'view_count', 'like_count', 'created_at']
        
        # Filter by tags if provided and not empty
        if 'tags' in request.GET:
            tag_ids = [tid for tid in request.GET.getlist('tags') if tid.strip()]
            if tag_ids:
                articles = articles.filter(tags__id__in=tag_ids)
        
        # Filter by author if provided and not empty
        if 'author' in request.GET and request.GET['author'].strip():
            try:
                author_id = int(request.GET['author'])
                articles = articles.filter(author__id=author_id)
            except (ValueError, TypeError):
                pass  # Skip invalid author ID
        
        # Filter by featured/breaking if provided and not empty
        if 'is_featured' in request.GET and request.GET['is_featured'].strip():
            is_featured = request.GET['is_featured'].lower() == 'true'
            articles = articles.filter(is_featured=is_featured)
        
        if 'is_breaking' in request.GET and request.GET['is_breaking'].strip():
            is_breaking = request.GET['is_breaking'].lower() == 'true'
            articles = articles.filter(is_breaking=is_breaking)
        
        # Search functionality
        if 'search' in request.GET and request.GET['search'].strip():
            search_term = request.GET['search'].strip()
            articles = articles.filter(
                Q(title__icontains=search_term) |
                Q(excerpt__icontains=search_term) |
                Q(content__icontains=search_term)
            )
        
        # Ordering
        ordering = request.GET.get('ordering', '-published_at')
        if ordering in ordering_fields:
            articles = articles.order_by(ordering)
        else:
            articles = articles.order_by('-published_at')
        
        # Pagination
        page_size = int(request.GET.get('page_size', 20))
        page = int(request.GET.get('page', 1))
        
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = articles.count()
        paginated_articles = articles[start:end]
        
        serializer = ArticleListSerializer(paginated_articles, many=True, context={'request': request})
        
        return APIResponse.success(
            data={
                'articles': serializer.data,
                'category': {
                    'id': category.id,
                    'name': category.name,
                    'slug': category.slug,
                    'description': category.description,
                    'color': category.color,
                    'icon': category.icon
                },
                'pagination': {
                    'total_count': total_count,
                    'page': page,
                    'page_size': page_size,
                    'total_pages': (total_count + page_size - 1) // page_size,
                    'has_next': end < total_count,
                    'has_previous': page > 1
                },
                'filters_applied': {
                    'tags': [tid for tid in request.GET.getlist('tags') if tid.strip()],
                    'author': request.GET.get('author') if request.GET.get('author', '').strip() else None,
                    'is_featured': request.GET.get('is_featured') if request.GET.get('is_featured', '').strip() else None,
                    'is_breaking': request.GET.get('is_breaking') if request.GET.get('is_breaking', '').strip() else None,
                    'search': request.GET.get('search') if request.GET.get('search', '').strip() else None,
                    'ordering': ordering
                }
            },
            message=f"Retrieved {len(serializer.data)} articles from {category.name} category"
        )


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
        return Tag.objects.filter(
            is_active=True,
            is_deleted=False
        ).annotate(
            article_count=Count('article', filter=Q(article__status='published'))
        )
    
    def destroy(self, request, *args, **kwargs):
        """Delete a tag and handle related articles."""
        try:
            tag = self.get_object()
            tag_name = tag.name
            
            # Get articles that will be affected
            articles_with_tag = Article.objects.filter(tags=tag)
            affected_count = articles_with_tag.count()
            
            # Remove this tag from all articles before deleting the tag
            if affected_count > 0:
                for article in articles_with_tag:
                    article.tags.remove(tag)
            
            # Hard delete the tag (permanently remove from database)
            tag.hard_delete()
            
            # Prepare response message
            message_parts = [f"Tag '{tag_name}' deleted successfully"]
            if affected_count > 0:
                message_parts.append(f"Removed from {affected_count} article(s)")
            
            return APIResponse.success(
                message=". ".join(message_parts),
                data={
                    'deleted_tag': {
                        'id': tag.id,
                        'name': tag_name
                    },
                    'affected_articles': {
                        'count': affected_count
                    }
                }
            )
            
        except Exception as e:
            return APIResponse.error(
                message=f"Failed to delete tag: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def inactive(self, request):
        """Get inactive tags (for admin purposes)."""
        inactive_tags = Tag.objects.filter(
            Q(is_active=False) | Q(is_deleted=True)
        )
        serializer = self.get_serializer(inactive_tags, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Inactive tags retrieved")
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore an inactive tag."""
        try:
            # Get the tag (including inactive ones)
            tag = get_object_or_404(Tag, pk=pk)
            
            if tag.is_active:
                return APIResponse.error(
                    message="Tag is already active",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            # Restore the tag
            tag.is_active = True
            tag.save(update_fields=['is_active'])
            
            serializer = self.get_serializer(tag, context={'request': request})
            
            return APIResponse.success(
                data=serializer.data,
                message=f"Tag '{tag.name}' restored successfully"
            )
            
        except Exception as e:
            return APIResponse.error(
                message=f"Failed to restore tag: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
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
    filterset_fields = ['status', 'primary_category', 'secondary_categories', 'tags', 'author', 'is_featured', 'is_breaking']
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
        queryset = Article.objects.select_related('author', 'primary_category').prefetch_related('tags', 'secondary_categories')
        
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
    
    @action(detail=True, methods=['post'])
    def archive_from_primary(self, request, pk=None):
        """Manually archive article from primary category."""
        article = self.get_object()
        
        if article.archive_from_primary_category(manual=True):
            return APIResponse.success(message="Article archived from primary category")
        else:
            return APIResponse.error(message="Article has no primary category to archive")
    
    @action(detail=True, methods=['post'])
    def archive_from_secondary(self, request, pk=None):
        """Manually archive article from secondary categories."""
        article = self.get_object()
        
        if article.archive_from_secondary_categories(manual=True):
            return APIResponse.success(message="Article archived from secondary categories")
        else:
            return APIResponse.error(message="Article has no secondary categories to archive")
    
    @action(detail=True, methods=['post'])
    @extend_schema(
        summary="Archive from Specific Secondary Category",
        description="Archive article from a specific secondary category while keeping others active",
        request={
            "type": "object",
            "properties": {
                "category_id": {"type": "integer", "description": "ID of the category to archive from"}
            },
            "required": ["category_id"]
        },
        responses={
            200: {"description": "Article archived from category successfully"},
            400: {"description": "Invalid request data"},
            404: {"description": "Category not found"}
        },
        tags=["Article Archiving"]
    )
    def archive_from_specific_secondary(self, request, pk=None):
        """Archive article from a specific secondary category."""
        article = self.get_object()
        category_id = request.data.get('category_id')
        
        if not category_id:
            return APIResponse.error(
                message="category_id is required",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import Category
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return APIResponse.error(
                message="Category not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        success, message = article.archive_from_specific_secondary_category(category)
        
        if success:
            return APIResponse.success(
                message=message,
                data={
                    'article_id': article.id,
                    'category_id': category.id,
                    'category_name': category.name,
                    'active_secondary_categories': [
                        {'id': cat.id, 'name': cat.name} 
                        for cat in article.get_active_secondary_categories()
                    ],
                    'archived_secondary_categories': [
                        {'id': cat.id, 'name': cat.name} 
                        for cat in article.get_archived_secondary_categories()
                    ]
                }
            )
        else:
            return APIResponse.error(message=message)
    
    @action(detail=True, methods=['post'])
    @extend_schema(
        summary="Restore to Specific Secondary Category",
        description="Restore article to a specific secondary category from archived status",
        request={
            "type": "object",
            "properties": {
                "category_id": {"type": "integer", "description": "ID of the category to restore to"}
            },
            "required": ["category_id"]
        },
        responses={
            200: {"description": "Article restored to category successfully"},
            400: {"description": "Invalid request data"},
            404: {"description": "Category not found"}
        },
        tags=["Article Archiving"]
    )
    def restore_to_specific_secondary(self, request, pk=None):
        """Restore article to a specific secondary category."""
        article = self.get_object()
        category_id = request.data.get('category_id')
        
        if not category_id:
            return APIResponse.error(
                message="category_id is required",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import Category
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return APIResponse.error(
                message="Category not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        success, message = article.restore_from_specific_secondary_category(category)
        
        if success:
            return APIResponse.success(
                message=message,
                data={
                    'article_id': article.id,
                    'category_id': category.id,
                    'category_name': category.name,
                    'active_secondary_categories': [
                        {'id': cat.id, 'name': cat.name} 
                        for cat in article.get_active_secondary_categories()
                    ],
                    'archived_secondary_categories': [
                        {'id': cat.id, 'name': cat.name} 
                        for cat in article.get_archived_secondary_categories()
                    ]
                }
            )
        else:
            return APIResponse.error(message=message)
    
    @action(detail=True, methods=['get'])
    @extend_schema(
        summary="Get Secondary Category Status",
        description="Get the status of active and archived secondary categories for an article",
        responses={
            200: {"description": "Secondary category status retrieved successfully"}
        },
        tags=["Article Archiving"]
    )
    def secondary_category_status(self, request, pk=None):
        """Get the status of secondary categories for an article."""
        article = self.get_object()
        
        return APIResponse.success(
            data={
                'article_id': article.id,
                'article_title': article.title,
                'active_secondary_categories': [
                    {
                        'id': cat.id, 
                        'name': cat.name,
                        'slug': cat.slug,
                        'color': cat.color,
                        'is_active': True
                    } 
                    for cat in article.get_active_secondary_categories()
                ],
                'archived_secondary_categories': [
                    {
                        'id': cat.id, 
                        'name': cat.name,
                        'slug': cat.slug,
                        'color': cat.color,
                        'is_active': False
                    } 
                    for cat in article.get_archived_secondary_categories()
                ],
                'total_active': article.get_active_secondary_categories().count(),
                'total_archived': article.get_archived_secondary_categories().count()
            },
            message="Secondary category status retrieved"
        )
    
    @action(detail=True, methods=['post'])
    def set_primary_duration(self, request, pk=None):
        """Set auto-archiving duration for primary category."""
        article = self.get_object()
        
        hours = request.data.get('hours')
        days = request.data.get('days')
        
        if not hours and not days:
            return APIResponse.error(message="Either hours or days must be provided")
        
        article.set_primary_category_duration(hours=hours, days=days)
        
        return APIResponse.success(
            message=f"Primary category auto-archiving set for {hours or days} {'hours' if hours else 'days'}"
        )
    
    @action(detail=True, methods=['post'])
    def set_secondary_duration(self, request, pk=None):
        """Set auto-archiving duration for secondary categories."""
        article = self.get_object()
        
        hours = request.data.get('hours')
        days = request.data.get('days')
        
        if not hours and not days:
            return APIResponse.error(message="Either hours or days must be provided")
        
        article.set_secondary_categories_duration(hours=hours, days=days)
        
        return APIResponse.success(
            message=f"Secondary categories auto-archiving set for {hours or days} {'hours' if hours else 'days'}"
        )
    
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
    parser_classes = [MultiPartParser, FormParser]
    
    def perform_create(self, serializer):
        """Set uploaded_by when creating media file."""
        serializer.save(uploaded_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def upload(self, request):
        """
        Upload media file (image or video) and return URL.
        This endpoint is specifically designed for rich text editor integration.
        """
        if 'file' not in request.FILES:
            return APIResponse.error(
                message="No file provided",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        # Validate file size (max 50MB for videos, 10MB for images)
        max_size = 50 * 1024 * 1024  # 50MB
        if file.size > max_size:
            return APIResponse.error(
                message=f"File too large. Maximum size is {max_size // (1024*1024)}MB",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine file type
        mime_type = file.content_type
        file_type = self._get_file_type(mime_type)
        
        if file_type not in ['image', 'video']:
            return APIResponse.error(
                message="Only images and videos are allowed",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate unique filename
        file_extension = os.path.splitext(file.name)[1]
        filename = f"{timezone.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
        
        # Create media file record
        media_file = MediaFile.objects.create(
            name=file.name,
            file=file,
            file_type=file_type,
            file_size=file.size,
            mime_type=mime_type,
            alt_text=request.data.get('alt_text', ''),
            caption=request.data.get('caption', ''),
            uploaded_by=request.user,
            article_id=request.data.get('article_id') if request.data.get('article_id') else None
        )
        
        # Get image dimensions if it's an image
        if file_type == 'image':
            try:
                with Image.open(file) as img:
                    media_file.width, media_file.height = img.size
                    media_file.save(update_fields=['width', 'height'])
            except Exception as e:
                # If we can't get dimensions, continue without them
                pass
        
        # Build the URL
        request_obj = request
        file_url = request_obj.build_absolute_uri(media_file.file.url)
        
        return APIResponse.success(
            data={
                'id': media_file.id,
                'url': file_url,
                'name': media_file.name,
                'file_type': media_file.file_type,
                'file_size': media_file.file_size,
                'width': media_file.width,
                'height': media_file.height,
                'alt_text': media_file.alt_text,
                'caption': media_file.caption
            },
            message="File uploaded successfully"
        )
    
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


class VideoViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Video management with efficient retrieval.
    """
    
    queryset = Video.objects.all()
    permission_classes = [IsReporterOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category', 'tags', 'uploaded_by', 'is_featured']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'published_at', 'view_count', 'like_count']
    ordering = ['-created_at']
    parser_classes = [MultiPartParser, FormParser]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return VideoListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return VideoCreateUpdateSerializer
        return VideoDetailSerializer
    
    def get_queryset(self):
        """Return videos based on user permissions."""
        queryset = Video.objects.select_related('uploaded_by', 'category').prefetch_related('tags')
        
        # If user is not authenticated or is a reader, only show published videos
        if not self.request.user.is_authenticated or self.request.user.role == 'reader':
            queryset = queryset.filter(status='published')
        # If user is a reporter, show their own videos and published videos
        elif self.request.user.role == 'reporter':
            queryset = queryset.filter(
                Q(status='published') | Q(uploaded_by=self.request.user)
            )
        # Editors and admins can see all videos
        elif self.request.user.role in ['editor', 'admin'] or self.request.user.is_staff:
            pass  # Show all videos
        
        return queryset
    
    def perform_create(self, serializer):
        """Set uploaded_by and compute file metadata when creating video."""
        video_file = self.request.FILES.get('video_file')
        
        if video_file:
            # Compute file size and mime type
            file_size = video_file.size
            mime_type = video_file.content_type
            
            # Save with metadata
            video = serializer.save(
                uploaded_by=self.request.user,
                file_size=file_size,
                mime_type=mime_type
            )
        else:
            video = serializer.save(uploaded_by=self.request.user)
        
        return video
    
    def perform_update(self, serializer):
        """Update metadata if video file is being updated."""
        video_file = self.request.FILES.get('video_file')
        
        if video_file:
            # Compute file size and mime type
            file_size = video_file.size
            mime_type = video_file.content_type
            
            # Update with metadata
            serializer.save(file_size=file_size, mime_type=mime_type)
        else:
            serializer.save()
    
    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Record video view."""
        video = self.get_object()
        
        # Increment view count
        video.increment_view_count()
        
        return APIResponse.success(message="View recorded")
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured videos."""
        videos = self.get_queryset().filter(is_featured=True, status='published')
        serializer = self.get_serializer(videos, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Featured videos retrieved")
    
    @action(detail=False, methods=['get'])
    def category_videos(self, request):
        """Get videos by category."""
        category_id = request.GET.get('category_id')
        
        if not category_id:
            return APIResponse.error(
                message="category_id parameter is required",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            videos = self.get_queryset().filter(category_id=category_id, status='published')
            serializer = self.get_serializer(videos, many=True, context={'request': request})
            return APIResponse.success(data=serializer.data, message=f"Videos from category retrieved")
        except Exception as e:
            return APIResponse.error(message=f"Error retrieving videos: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def by_tag(self, request):
        """Get videos by tag."""
        tag_id = request.GET.get('tag_id')
        
        if not tag_id:
            return APIResponse.error(
                message="tag_id parameter is required",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            videos = self.get_queryset().filter(tags__id=tag_id, status='published')
            serializer = self.get_serializer(videos, many=True, context={'request': request})
            return APIResponse.success(data=serializer.data, message="Videos by tag retrieved")
        except Exception as e:
            return APIResponse.error(message=f"Error retrieving videos: {str(e)}")
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending videos based on views and likes."""
        videos = self.get_queryset().filter(status='published').order_by(
            '-view_count', '-like_count', '-created_at'
        )[:10]
        serializer = self.get_serializer(videos, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Trending videos retrieved")