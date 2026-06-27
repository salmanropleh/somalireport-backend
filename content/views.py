"""
Views for content app.
"""

from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.utils.html import escape
from django.db.models import Q, Count, F
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os
import mimetypes
from PIL import Image
from drf_spectacular.utils import extend_schema

from .models import Category, Tag, Article, MediaFile, Video, ArticleView, ArticleLike, ArticleShare, Contact, Banner
from .serializers import (
    CategorySerializer, TagSerializer, ArticleListSerializer,
    ArticleDetailSerializer, ArticleCreateUpdateSerializer,
    MediaFileSerializer, ArticleViewSerializer, ArticleLikeSerializer,
    ArticleShareSerializer, VideoListSerializer, VideoDetailSerializer, VideoCreateUpdateSerializer,
    ContactSerializer, BannerSerializer
)
from core.utils import APIResponse
from core.permissions import IsEditorOrReadOnly, IsReporterOrReadOnly, IsOwnerOrReadOnly, IsAdminOrReadOnly

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
        
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)

        # Base queryset - articles in this category (primary or secondary)
        articles = Article.objects.filter(
            Q(primary_category=category) | Q(secondary_categories=category),
            status='published'
        ).distinct().select_related('author', 'primary_category').prefetch_related('tags', 'secondary_categories')
        
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
        if ordering.lstrip('-') in ordering_fields:
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
    
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsEditorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        """Return tags with article counts."""
        queryset = Tag.objects.all()
        
        # Filter for active tags unless user is editor/admin
        if not (self.request.user.is_authenticated and (self.request.user.role in ['editor', 'admin'] or self.request.user.is_staff)):
            queryset = queryset.filter(is_active=True)
            
        return queryset.annotate(
            article_count=Count('article', filter=Q(article__status='published'))
        ).order_by('name')

    def create(self, request, *args, **kwargs):
        """Create a tag, handling duplicates gracefully."""
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError
        
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            # Check if tag exists
            name = request.data.get('name')
            if name:
                existing = Tag.objects.filter(name__iexact=name).first()
                if existing:
                    return APIResponse.error(
                        message=f"Tag '{name}' already exists.",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )
            raise
        except ValidationError as e:
            return APIResponse.error(
                message=str(e.detail) if hasattr(e, 'detail') else str(e),
                status_code=status.HTTP_400_BAD_REQUEST
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
    filterset_fields = ['status', 'primary_category', 'secondary_categories', 'tags', 'author', 'is_featured', 'is_breaking', 'priority']
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
        queryset = Article.objects.filter(is_deleted=False).select_related('author', 'primary_category').prefetch_related('tags', 'secondary_categories')
        
        # For retrieve, archive/unarchive actions, allow access to all articles regardless of status
        unrestricted_actions = ['retrieve', 'archive', 'unarchive', 'archive_from_primary', 'unarchive_from_primary', 
                          'archive_from_secondary', 'unarchive_from_secondary', 'archive_from_specific_secondary',
                          'restore_to_specific_secondary']
        
        if self.action in unrestricted_actions:
            # For retrieve and archive/unarchive actions, return all articles regardless of status
            return queryset
        
        # Editors and admins can see all articles
        if self.request.user.is_authenticated and (self.request.user.role in ['editor', 'admin'] or self.request.user.is_staff):
            return queryset

        # For authenticated users (readers, reporters), show published OR own articles
        if self.request.user.is_authenticated:
            return queryset.filter(
                Q(status='published') | Q(author=self.request.user)
            )
        
        # For anonymous users, only show published articles
        return queryset.filter(status='published')
    
    def perform_create(self, serializer):
        """Set author when creating article. Auto-set published_at if created as published."""
        extra = {'author': self.request.user}
        if serializer.validated_data.get('status') == 'published':
            extra.setdefault('published_at', serializer.validated_data.get('published_at') or timezone.now())
        serializer.save(**extra)
    
    def perform_update(self, serializer):
        """Set updated_by when updating article. Auto-set published_at on first publish."""
        instance = serializer.instance
        incoming_status = serializer.validated_data.get('status', instance.status)
        extra = {'updated_by': self.request.user}
        if incoming_status == 'published' and not instance.published_at:
            extra['published_at'] = timezone.now()
        serializer.save(**extra)
    
    def destroy(self, request, *args, **kwargs):
        """
        Hard delete the article.
        Per user requirement, this is a permanent delete, not soft delete.
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        instance.hard_delete()
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
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
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
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
            # Completely new like
            article.like_count += 1
            article.save(update_fields=['like_count'])
            message = "Article liked"
            is_liked = True
        else:
            # Existing record found - check if it's soft deleted
            if getattr(like, 'is_deleted', False):
                # Was unliked (soft deleted), now re-liking
                like.is_deleted = False
                like.deleted_at = None
                like.save()
                article.like_count += 1
                article.save(update_fields=['like_count'])
                message = "Article liked"
                is_liked = True
            else:
                # Was liked, now unliking
                like.delete()
                if article.like_count > 0:
                    article.like_count -= 1
                article.save(update_fields=['like_count'])
                message = "Article unliked"
                is_liked = False
            
        return APIResponse.success(
            data={
                'like_count': article.like_count,
                'is_liked': is_liked
            },
            message=message
        )
            
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_save(self, request, pk=None):
        """Save/unsave article."""
        article = self.get_object()
        
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        
        # Use localized import to avoid circular dependency
        from .models import ArticleSave
        
        save_obj, created = ArticleSave.objects.get_or_create(
            article=article,
            user=request.user
        )
        
        if created:
            # Completely new save
            message = "Article saved"
            is_saved = True
        else:
            # Existing record found - check if it's soft deleted
            if getattr(save_obj, 'is_deleted', False):
                # Was unsaved (soft deleted), now re-saving
                save_obj.is_deleted = False
                save_obj.deleted_at = None
                save_obj.save()
                message = "Article saved"
                is_saved = True
            else:
                # Was saved, now unsaving
                save_obj.delete()
                message = "Article removed from saved"
                is_saved = False
        
        return APIResponse.success(
            data={
                'is_saved': is_saved
            },
            message=message
        )

    @action(detail=False, methods=['get'])
    def saved(self, request):
        """Get processed saved articles for the current user."""
        if not request.user.is_authenticated:
             return APIResponse.error(
                 message="Authentication required",
                 status_code=status.HTTP_401_UNAUTHORIZED
             )
        
        saved_articles = Article.objects.filter(
            saves__user=request.user, 
            saves__is_deleted=False,
            saves__isnull=False
        ).distinct().order_by('-saves__created_at')
        
        page = self.paginate_queryset(saved_articles)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(saved_articles, many=True)
        return APIResponse.success(data=serializer.data, message="Saved articles retrieved")
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
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
            # Refresh from database to get updated fields
            article.refresh_from_db()
            serializer = self.get_serializer(article, context={'request': request})
            return APIResponse.success(
                data=serializer.data,
                message="Article archived from primary category"
            )
        else:
            return APIResponse.error(message="Article has no primary category to archive")
    
    @action(detail=True, methods=['post'])
    @extend_schema(
        summary="Unarchive from Primary Category",
        description="Restore article from primary category archive",
        responses={
            200: {"description": "Article unarchived from primary category successfully"},
            400: {"description": "Article is not archived from primary category"},
            404: {"description": "Article not found"}
        },
        tags=["Article Archiving"]
    )
    def unarchive_from_primary(self, request, pk=None):
        """Unarchive/restore article from primary category."""
        article = self.get_object()
        
        # Check if article is archived from primary category
        if not article.is_primary_archived:
            return APIResponse.error(
                message="Article is not archived from primary category. Only archived articles can be unarchived.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Restore from primary category
        if article.restore_from_primary_category():
            # Refresh from database to get updated fields
            article.refresh_from_db()
            serializer = self.get_serializer(article, context={'request': request})
            return APIResponse.success(
                data=serializer.data,
                message="Article unarchived from primary category"
            )
        else:
            return APIResponse.error(
                message="Failed to unarchive article from primary category",
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def archive_from_secondary(self, request, pk=None):
        """Manually archive article from secondary categories."""
        article = self.get_object()
        
        if article.archive_from_secondary_categories(manual=True):
            # Refresh from database to get updated fields
            article.refresh_from_db()
            serializer = self.get_serializer(article, context={'request': request})
            return APIResponse.success(
                data=serializer.data,
                message="Article archived from secondary categories"
            )
        else:
            return APIResponse.error(message="Article has no secondary categories to archive")
    
    @action(detail=True, methods=['post'])
    @extend_schema(
        summary="Unarchive from Secondary Categories",
        description="Restore article from secondary categories archive",
        responses={
            200: {"description": "Article unarchived from secondary categories successfully"},
            400: {"description": "Article is not archived from secondary categories"},
            404: {"description": "Article not found"}
        },
        tags=["Article Archiving"]
    )
    def unarchive_from_secondary(self, request, pk=None):
        """Unarchive/restore article from secondary categories."""
        article = self.get_object()
        
        # Check if article is archived from secondary categories
        if not article.is_secondary_archived:
            return APIResponse.error(
                message="Article is not archived from secondary categories. Only archived articles can be unarchived.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Restore from secondary categories
        if article.restore_from_secondary_categories():
            # Refresh from database to get updated fields
            article.refresh_from_db()
            serializer = self.get_serializer(article, context={'request': request})
            return APIResponse.success(
                data=serializer.data,
                message="Article unarchived from secondary categories"
            )
        else:
            return APIResponse.error(
                message="Failed to unarchive article from secondary categories",
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
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
    
    @action(detail=False, methods=['get'], url_path='by_user/(?P<user_id>[^/.]+)')
    @extend_schema(
        summary="Get Articles by User",
        description="Retrieve articles posted by a specific user ID",
        parameters=[
            {
                'name': 'user_id',
                'in': 'path',
                'description': 'ID of the user whose articles to retrieve',
                'required': True,
                'schema': {'type': 'integer'}
            },
            {
                'name': 'status',
                'in': 'query',
                'description': 'Filter by article status (optional)',
                'required': False,
                'schema': {'type': 'string', 'enum': ['draft', 'pending', 'published', 'archived']}
            },
            {
                'name': 'page',
                'in': 'query',
                'description': 'Page number for pagination',
                'required': False,
                'schema': {'type': 'integer', 'default': 1}
            },
            {
                'name': 'page_size',
                'in': 'query',
                'description': 'Number of items per page',
                'required': False,
                'schema': {'type': 'integer', 'default': 20}
            },
            {
                'name': 'ordering',
                'in': 'query',
                'description': 'Field to order by (e.g., -created_at, -published_at)',
                'required': False,
                'schema': {'type': 'string', 'default': '-created_at'}
            }
        ],
        responses={
            200: {"description": "Articles retrieved successfully"},
            400: {"description": "Invalid user_id parameter"},
            404: {"description": "User not found"}
        },
        tags=["Articles"]
    )
    def by_user(self, request, user_id=None):
        """Get articles posted by a specific user."""
        if not user_id:
            return APIResponse.error(
                message="user_id is required in the URL path",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            return APIResponse.error(
                message="user_id must be a valid integer",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user exists
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return APIResponse.error(
                message=f"User with ID {user_id} not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
        
        # Get all articles by this user (regardless of status)
        # Use direct queryset to bypass permission-based filtering
        articles = Article.objects.filter(
            is_deleted=False,
            author_id=user_id
        ).select_related('author', 'primary_category').prefetch_related('tags', 'secondary_categories')
        
        # Optional status filter
        status_filter = request.GET.get('status')
        if status_filter:
            articles = articles.filter(status=status_filter)
        
        # Apply ordering
        ordering = request.GET.get('ordering', '-created_at')
        if ordering.lstrip('-') in ['created_at', 'updated_at', 'published_at', 'view_count', 'like_count']:
            articles = articles.order_by(ordering)
        else:
            articles = articles.order_by('-created_at')
        
        # Pagination
        page = self.paginate_queryset(articles)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(articles, many=True, context={'request': request})
        return APIResponse.success(
            data={
                'articles': serializer.data,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': getattr(user, 'email', None)
                },
                'total_count': articles.count()
            },
            message=f"Retrieved {len(serializer.data)} article(s) by user {user.username}"
        )
    
    @action(detail=True, methods=['get'])
    @extend_schema(
        summary="Get Related Articles",
        description="Get articles related to the current article based on shared categories and tags",
        parameters=[
            {
                'name': 'limit',
                'in': 'query',
                'description': 'Maximum number of related articles to return (default: 10)',
                'required': False,
                'schema': {'type': 'integer', 'default': 10}
            }
        ],
        responses={
            200: {"description": "Related articles retrieved successfully"},
            404: {"description": "Article not found"}
        },
        tags=["Articles"]
    )
    def related(self, request, pk=None):
        """Get related articles based on shared categories and tags."""
        article = self.get_object()
        
        # Get limit from query params (default to 10)
        limit = int(request.GET.get('limit', 10))
        
        # Build query for related articles
        # Articles are related if they share:
        # 1. Same primary category
        # 2. Same secondary categories
        # 3. Same tags
        
        related_articles_query = Q()
        
        if article.primary_category:
            related_articles_query |= Q(primary_category=article.primary_category)



        
        # Add secondary category matches
        if article.secondary_categories.exists():
            related_articles_query |= Q(secondary_categories__in=article.secondary_categories.all())
        
        # Add tag matches
        if article.tags.exists():
            related_articles_query |= Q(tags__in=article.tags.all())
        
        # If no categories or tags, return empty result
        if not related_articles_query:
            return APIResponse.success(
                data={'articles': [], 'count': 0},
                message="No related articles found (article has no categories or tags)"
            )
        
        # Get related articles
        # Exclude the current article, only published articles
        related_articles = Article.objects.filter(
            related_articles_query,
            status='published'
        ).exclude(
            id=article.id
        ).select_related(
            'author', 'primary_category'
        ).prefetch_related(
            'tags', 'secondary_categories'
        ).distinct()
        
        # Calculate relevance score for each article
        # Score based on:
        # - Primary category match: 3 points
        # - Secondary category match: 2 points per category
        # - Tag match: 1 point per tag
        # Then order by score (descending) and recency
        
        article_scores = []
        for related_article in related_articles:
            score = 0
            
            # Primary category match
            if article.primary_category and related_article.primary_category == article.primary_category:
                score += 3
            
            # Secondary category matches
            shared_secondary = article.secondary_categories.filter(
                id__in=related_article.secondary_categories.values_list('id', flat=True)
            ).count()
            score += shared_secondary * 2
            
            # Tag matches
            shared_tags = article.tags.filter(
                id__in=related_article.tags.values_list('id', flat=True)
            ).count()
            score += shared_tags
            
            article_scores.append((related_article, score))
        
        # Sort by score (descending), then by published_at (descending)
        # Higher scores first, then most recent articles first
        # Use a large number for dates to ensure descending order
        def get_sort_key(item):
            article, score = item
            # Use a large timestamp value minus the actual timestamp for descending order
            date_value = article.published_at if article.published_at else article.created_at
            if date_value:
                # Convert to sortable value (larger timestamp = more recent)
                # We'll use negative of a large number minus timestamp for descending
                date_sort = -int(date_value.timestamp())
            else:
                date_sort = 0  # Articles without dates go last
            return (-score, date_sort)  # Negative score for descending
        
        article_scores.sort(key=get_sort_key)
        
        # Extract articles and limit
        related_articles = [art for art, score in article_scores[:limit]]
        
        # Serialize the results
        serializer = ArticleListSerializer(related_articles, many=True, context={'request': request})
        
        return APIResponse.success(
            data={
                'articles': serializer.data,
                'count': len(serializer.data),
                'current_article': {
                    'id': article.id,
                    'title': article.title,
                    'slug': article.slug
                }
            },
            message=f"Retrieved {len(serializer.data)} related article(s)"
        )
    
    @action(detail=False, methods=['get'])
    @extend_schema(
        summary="Get Archived Articles",
        description="Get archived articles. Admins/staff see all archived articles, other users see only their own authored archived articles.",
        parameters=[
            {
                'name': 'page',
                'in': 'query',
                'description': 'Page number for pagination',
                'required': False,
                'schema': {'type': 'integer', 'default': 1}
            },
            {
                'name': 'page_size',
                'in': 'query',
                'description': 'Number of items per page',
                'required': False,
                'schema': {'type': 'integer', 'default': 20}
            },
            {
                'name': 'ordering',
                'in': 'query',
                'description': 'Field to order by (e.g., -created_at, -updated_at)',
                'required': False,
                'schema': {'type': 'string', 'default': '-updated_at'}
            }
        ],
        responses={
            200: {"description": "Archived articles retrieved successfully"},
            401: {"description": "Authentication required"}
        },
        tags=["Article Archiving"]
    )
    def archived(self, request):
        """Get archived articles. Admins see all, others see only their own."""
        # Must be authenticated
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # Get archived articles - include both general archiving (status='archived')
        # and category-specific archiving (primary_category_archived_at or secondary_categories_archived_at)
        now = timezone.now()
        archived_articles = Article.objects.filter(
            is_deleted=False
        ).annotate(
            has_archived_secondary=Count('archived_secondary_categories')
        ).filter(
            Q(status='archived') |
            Q(primary_category_archived_at__isnull=False) |
            Q(secondary_categories_archived_at__isnull=False) |
            Q(has_archived_secondary__gt=0) |
            Q(primary_category_expires_at__lte=now, primary_category_expires_at__isnull=False) |
            Q(secondary_categories_expire_at__lte=now, secondary_categories_expire_at__isnull=False)
        )

        # Admins/staff see all, others see only their own
        if not (request.user.role == 'admin' or request.user.is_staff):
            archived_articles = archived_articles.filter(author=request.user)

        archived_articles = archived_articles.select_related(
            'author', 'primary_category'
        ).prefetch_related(
            'tags', 'secondary_categories', 'archived_secondary_categories'
        ).distinct()
        
        # Apply ordering
        ordering = request.GET.get('ordering', '-updated_at')
        if ordering.lstrip('-') in ['created_at', 'updated_at', 'published_at', 'view_count', 'like_count']:
            archived_articles = archived_articles.order_by(ordering)
        else:
            archived_articles = archived_articles.order_by('-updated_at')
        
        # Pagination
        page = self.paginate_queryset(archived_articles)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(archived_articles, many=True, context={'request': request})
        return APIResponse.success(
            data=serializer.data,
            message=f"Retrieved {len(serializer.data)} archived article(s)"
        )

    @action(detail=False, methods=['get'])
    @extend_schema(
        summary="Get Draft Articles",
        description="Get draft articles. Admins/editors see all drafts, reporters see only their own.",
        parameters=[
            {
                'name': 'page',
                'in': 'query',
                'description': 'Page number for pagination',
                'required': False,
                'schema': {'type': 'integer', 'default': 1}
            },
            {
                'name': 'page_size',
                'in': 'query',
                'description': 'Number of items per page',
                'required': False,
                'schema': {'type': 'integer', 'default': 20}
            },
            {
                'name': 'ordering',
                'in': 'query',
                'description': 'Field to order by (e.g., -created_at)',
                'required': False,
                'schema': {'type': 'string', 'default': '-created_at'}
            }
        ],
        responses={
            200: {"description": "Draft articles retrieved successfully"},
            401: {"description": "Authentication required"}
        },
        tags=["Articles"]
    )
    def drafts(self, request):
        """Get draft articles. Admins/editors see all, reporters see only their own."""
        if not request.user.is_authenticated:
            return APIResponse.error(
                message="Authentication required.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        draft_articles = Article.objects.filter(is_deleted=False, status='draft')

        # Admins and editors see all drafts; reporters see only their own
        if request.user.role not in ['admin', 'editor'] and not request.user.is_staff:
            draft_articles = draft_articles.filter(author=request.user)

        draft_articles = draft_articles.select_related(
            'author', 'primary_category'
        ).prefetch_related(
            'tags', 'secondary_categories'
        )

        ordering = request.GET.get('ordering', '-created_at')
        if ordering.lstrip('-') in ['created_at', 'updated_at', 'published_at', 'view_count', 'like_count']:
            draft_articles = draft_articles.order_by(ordering)
        else:
            draft_articles = draft_articles.order_by('-created_at')

        page = self.paginate_queryset(draft_articles)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(draft_articles, many=True, context={'request': request})
        return APIResponse.success(
            data=serializer.data,
            message=f"Retrieved {len(serializer.data)} draft article(s)"
        )

    @action(detail=True, methods=['post'])
    @extend_schema(
        summary="Archive Article",
        description="Archive an article by setting its status to 'archived'",
        responses={
            200: {"description": "Article archived successfully"},
            400: {"description": "Article is already archived"},
            404: {"description": "Article not found"}
        },
        tags=["Article Archiving"]
    )
    def archive(self, request, pk=None):
        """Archive an article by setting status to 'archived'."""
        article = self.get_object()
        
        # Check if article is already archived
        if article.status == 'archived':
            return APIResponse.error(
                message="Article is already archived.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Archive the article
        success, previous_status = article.archive()
        
        if success:
            serializer = self.get_serializer(article, context={'request': request})
            return APIResponse.success(
                data=serializer.data,
                message=f"Article archived successfully (previous status: '{previous_status}')"
            )
        else:
            return APIResponse.error(
                message="Failed to archive article",
                status_code=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    @extend_schema(
        summary="Unarchive/Restore Article",
        description="Restore an archived article by changing its status from 'archived' to another status",
        request={
            "type": "object",
            "properties": {
                "restore_to_status": {
                    "type": "string",
                    "enum": ["draft", "pending", "published"],
                    "description": "Status to restore the article to (default: 'draft')",
                    "default": "draft"
                }
            },
            "required": []
        },
        responses={
            200: {"description": "Article unarchived successfully"},
            400: {"description": "Article is not archived"},
            403: {"description": "Permission denied"},
            404: {"description": "Article not found"}
        },
        tags=["Article Archiving"]
    )
    def unarchive(self, request, pk=None):
        """Unarchive/restore an article."""
        article = self.get_object()
        
        # Refresh from database to ensure we have the latest status
        article.refresh_from_db()
        
        # Check if article is archived in any way
        is_generally_archived = article.status == 'archived'
        is_primary_archived = article.is_primary_archived
        is_secondary_archived = article.is_secondary_archived
        
        if not (is_generally_archived or is_primary_archived or is_secondary_archived):
            return APIResponse.error(
                message=f"Article is not archived. Current status: '{article.status}'. Only archived articles can be unarchived.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Track what was unarchived
        unarchived_items = []
        
        # Handle general archiving (status='archived')
        if is_generally_archived:
            restore_to_status = request.data.get('restore_to_status', 'draft')
            success, new_status = article.unarchive(restore_to_status=restore_to_status)
            if success:
                unarchived_items.append(f"status restored to '{new_status}'")
            else:
                return APIResponse.error(
                    message="Failed to unarchive article status",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        # Handle primary category archiving
        if is_primary_archived:
            if article.restore_from_primary_category():
                unarchived_items.append("primary category")
            else:
                return APIResponse.error(
                    message="Failed to unarchive from primary category",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        # Handle secondary categories archiving
        if is_secondary_archived:
            if article.restore_from_secondary_categories():
                unarchived_items.append("secondary categories")
            else:
                return APIResponse.error(
                    message="Failed to unarchive from secondary categories",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
        
        # Refresh from database to get updated fields
        article.refresh_from_db()
        serializer = self.get_serializer(article, context={'request': request})
        
        message = f"Article unarchived: {', '.join(unarchived_items)}"
        return APIResponse.success(
            data=serializer.data,
            message=message
        )


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
        
        # Ensure uploads directory exists and is writable
        from django.conf import settings
        uploads_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(uploads_dir, mode=0o775, exist_ok=True)
        
        # Reset file pointer to beginning (in case it was read)
        if hasattr(file, 'seek'):
            file.seek(0)
        
        # IMPORTANT: Read file content into memory to avoid file handle issues
        # Django's FileField consumes the file object, so we need to preserve it
        file_content = file.read()
        file.seek(0)  # Reset for Django to read it
        
        # Save file explicitly using ContentFile to ensure it's actually written
        # This avoids issues with Django's FileField not saving correctly
        from django.core.files.base import ContentFile
        import logging
        logger = logging.getLogger(__name__)
        
        # Create media file record WITHOUT the file first
        media_file = MediaFile(
            name=file.name,
            file_type=file_type,
            file_size=file.size,
            mime_type=mime_type,
            alt_text=request.data.get('alt_text', ''),
            caption=request.data.get('caption', ''),
            uploaded_by=request.user,
            article_id=request.data.get('article_id') if request.data.get('article_id') else None
        )
        
        # Save the model first (without file) to get ID
        media_file.save()
        
        # Now save the file explicitly using ContentFile with preserved content
        # Use just the original filename - Django will add the suffix and use upload_to
        original_filename = file.name
        
        try:
            # Create ContentFile from preserved content
            content_file = ContentFile(file_content, name=original_filename)
            
            # Save the file - Django will handle the upload_to path and unique suffix
            media_file.file.save(original_filename, content_file, save=True)
            
            # Get the actual file path after Django saves it
            file_path = os.path.join(settings.MEDIA_ROOT, media_file.file.name)
            
            # Refresh from DB to get the actual filename Django generated
            media_file.refresh_from_db()
            file_path = os.path.join(settings.MEDIA_ROOT, media_file.file.name)
            
            # Verify it was saved
            if os.path.exists(file_path):
                logger.info(f"File saved successfully: {file_path}")
            else:
                # Check permissions and directory
                logger.error(
                    f"File save failed. Path: {file_path}\n"
                    f"MEDIA_ROOT: {settings.MEDIA_ROOT}\n"
                    f"MEDIA_ROOT exists: {os.path.exists(settings.MEDIA_ROOT)}\n"
                    f"MEDIA_ROOT writable: {os.access(settings.MEDIA_ROOT, os.W_OK)}\n"
                    f"uploads/ exists: {os.path.exists(uploads_dir)}\n"
                    f"uploads/ writable: {os.access(uploads_dir, os.W_OK)}\n"
                    f"File size: {len(file_content)} bytes\n"
                    f"Generated filename: {media_file.file.name}"
                )
                raise Exception(f"File could not be saved to {file_path}. Check permissions.")
        except Exception as e:
            logger.error(f"Failed to save file: {e}", exc_info=True)
            # Clean up the record if file save failed
            media_file.delete()
            raise
        
        # Get image dimensions if it's an image
        if file_type == 'image' and os.path.exists(file_path):
            try:
                with Image.open(file_path) as img:  # Open from saved file path, not file object
                    media_file.width, media_file.height = img.size
                    media_file.save(update_fields=['width', 'height'])
            except Exception as e:
                # If we can't get dimensions, continue without them
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not get image dimensions: {e}")
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
    
    def destroy(self, request, *args, **kwargs):
        """
        Hard delete the video.
        Per user requirement, this is a permanent delete.
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        instance.hard_delete()
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
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


class ContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Contact submissions.
    """
    
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_permissions(self):
        """
        Allow any user to create a contact submission.
        Only admins can list/retrieve submissions.
        """
        if self.action == 'create':
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAdminUser]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Save contact submission."""
        serializer.save()
        
    @extend_schema(
        summary="Submit Contact Form",
        description="Submit a new contact message.",
        responses={201: ContactSerializer},
        tags=["Contact"]
    )
    def create(self, request, *args, **kwargs):
        """Create a new contact submission."""
        return super().create(request, *args, **kwargs)

class BannerViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Banner management.

    Public (no auth): GET list filtered by slot + is_active, POST /view/, POST /click/
    Admin only: create, update, delete, activate, deactivate
    """

    queryset         = Banner.objects.all()
    serializer_class = BannerSerializer
    permission_classes = [IsAdminOrReadOnly]
    parser_classes   = [MultiPartParser, FormParser]
    filter_backends  = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['slot', 'is_active']
    ordering_fields  = ['slot', 'created_at']
    ordering         = ['slot', '-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        # Public reads get only active banners within their scheduled window
        if self.request.method == 'GET' and not (
            self.request.user and self.request.user.is_staff
        ):
            now = timezone.now()
            qs = qs.filter(is_active=True).filter(
                Q(starts_at__isnull=True) | Q(starts_at__lte=now)
            ).filter(
                Q(ends_at__isnull=True) | Q(ends_at__gte=now)
            )
        return qs

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def view(self, request, pk=None):
        """Track an impression. No authentication required."""
        Banner.objects.filter(pk=pk).update(view_count=models.F('view_count') + 1)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], permission_classes=[permissions.AllowAny])
    def click(self, request, pk=None):
        """Track a click. No authentication required."""
        Banner.objects.filter(pk=pk).update(click_count=models.F('click_count') + 1)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Set is_active = True."""
        banner = self.get_object()
        banner.is_active = True
        banner.save(update_fields=['is_active', 'updated_at'])
        return Response({'id': banner.id, 'is_active': True})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Set is_active = False."""
        banner = self.get_object()
        banner.is_active = False
        banner.save(update_fields=['is_active', 'updated_at'])
        return Response({'id': banner.id, 'is_active': False})


def prerender_article(request, pk):
    from django.conf import settings as django_settings
    SITE_URL = getattr(django_settings, 'SITE_URL', 'https://somalireport.com')
    FALLBACK_IMAGE = f'{SITE_URL}/og-default.png'
    try:
        article = Article.objects.select_related('author').get(pk=pk, status='published')
    except Article.DoesNotExist:
        return HttpResponse(status=404)

    display_url = article.featured_image_display_url
    if display_url:
        if display_url.startswith('http://') or display_url.startswith('https://'):
            image_url = display_url
        else:
            image_url = f'{SITE_URL}{display_url}'
    else:
        image_url = FALLBACK_IMAGE

    article_url = f'{SITE_URL}/article/{article.id}/{article.slug}'
    title = escape(article.meta_title or article.title)
    description = escape((article.meta_description or article.excerpt or '')[:200])

    parts = ['<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>']
    parts.append(f'<title>{title} | Somali Report</title>')
    parts.append(f'<meta property="og:type" content="article"/>')
    parts.append(f'<meta property="og:site_name" content="Somali Report"/>')
    parts.append(f'<meta property="og:title" content="{title}"/>')
    parts.append(f'<meta property="og:description" content="{description}"/>')
    parts.append(f'<meta property="og:url" content="{article_url}"/>')
    parts.append(f'<meta property="og:image" content="{image_url}"/>')
    parts.append(f'<meta property="og:image:width" content="1200"/>')
    parts.append(f'<meta property="og:image:height" content="630"/>')
    parts.append(f'<meta name="twitter:card" content="summary_large_image"/>')
    parts.append(f'<meta name="twitter:site" content="@SomaliReport"/>')
    parts.append(f'<meta name="twitter:creator" content="@SomaliReport"/>')
    parts.append(f'<meta name="twitter:title" content="{title}"/>')
    parts.append(f'<meta name="twitter:description" content="{description}"/>')
    parts.append(f'<meta name="twitter:image" content="{image_url}"/>')
    parts.append(f'</head><body><a href="{article_url}">{title}</a></body></html>')
    return HttpResponse(''.join(parts), content_type='text/html; charset=utf-8')
