"""
Views for scraper app.
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction

from .models import NewsSource, ScrapedArticle, ScrapingJob, ScrapingLog
from .serializers import (
    NewsSourceSerializer, ScrapedArticleListSerializer,
    ScrapedArticleDetailSerializer, ScrapingJobSerializer,
    ScrapingLogSerializer, ScrapeRequestSerializer
)
from .services import NewsScrapingService
from core.utils import APIResponse
from core.permissions import IsEditorOrReadOnly


class NewsSourceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for NewsSource management.
    """
    
    queryset = NewsSource.objects.all()
    serializer_class = NewsSourceSerializer
    permission_classes = [IsEditorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'source_type']
    search_fields = ['name', 'url', 'description']
    ordering_fields = ['name', 'created_at', 'last_scraped']
    ordering = ['name']
    
    @action(detail=True, methods=['post'])
    def scrape(self, request, pk=None):
        """Trigger scraping for a specific source."""
        source = self.get_object()
        
        max_articles = request.data.get('max_articles', 100)
        force_update = request.data.get('force_update', False)
        
        try:
            # Create scraping job
            job = ScrapingJob.objects.create(
                source=source,
                max_articles=max_articles,
                force_update=force_update
            )
            
            # Start scraping
            job.start()
            
            # Initialize scraping service
            scraping_service = NewsScrapingService(source)
            
            # Scrape articles
            articles_found, articles_scraped, articles_processed = scraping_service.scrape_articles(
                max_articles=max_articles,
                force_update=force_update
            )
            
            # Complete job
            job.complete(articles_found, articles_scraped, articles_processed)
            
            # Get latest logs for summary
            recent_logs = ScrapingLog.objects.filter(source=source).order_by('-created_at')[:5]
            log_summaries = [f"[{log.level}] {log.message}" for log in recent_logs]
            
            return APIResponse.success(
                data={
                    'job_id': job.id,
                    'articles_found': articles_found,
                    'articles_scraped': articles_scraped,
                    'articles_processed': articles_processed,
                    'duplicates': max(0, articles_found - articles_scraped),
                    'log_summary': log_summaries
                },
                message=f"Scraping completed for {source.name}"
            )
            
        except Exception as e:
            if 'job' in locals():
                job.fail(str(e))
            
            return APIResponse.error(
                message=f"Scraping failed: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def latest_jobs(self, request, pk=None):
        """Get latest scraping jobs for this source."""
        source = self.get_object()
        jobs = ScrapingJob.objects.filter(source=source).order_by('-created_at')[:10]
        
        serializer = ScrapingJobSerializer(jobs, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Latest jobs retrieved")
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get statistics for this source."""
        source = self.get_object()
        
        return APIResponse.success(
            data={
                'id': source.id,
                'name': source.name,
                'success_rate': source.success_rate,
                'total_scraped': source.total_scraped,
                'successful_scrapes': source.successful_scrapes,
                'failed_scrapes': source.failed_scrapes,
                'last_scraped': source.last_scraped,
                'pending_articles': ScrapedArticle.objects.filter(source=source, status='pending').count(),
                'approved_articles': ScrapedArticle.objects.filter(source=source, status='approved').count(),
                'published_articles': ScrapedArticle.objects.filter(source=source, status='published').count()
            },
            message="Statistics retrieved"
        )


class ScrapedArticleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ScrapedArticle management.
    """
    
    queryset = ScrapedArticle.objects.all()
    permission_classes = [IsEditorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'source', 'quality_score', 'language']
    search_fields = ['title', 'content', 'excerpt']
    ordering_fields = ['scraped_at', 'published_at', 'quality_score']
    ordering = ['-scraped_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return ScrapedArticleListSerializer
        return ScrapedArticleDetailSerializer
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve scraped article."""
        article = self.get_object()
        article.approve(request.user)
        
        serializer = self.get_serializer(article, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Article approved")
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject scraped article."""
        article = self.get_object()
        article.reject(request.user)
        
        serializer = self.get_serializer(article, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Article rejected")
    
    @action(detail=True, methods=['post'])
    def mark_duplicate(self, request, pk=None):
        """Mark scraped article as duplicate."""
        article = self.get_object()
        article.mark_duplicate(request.user)
        
        serializer = self.get_serializer(article, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Article marked as duplicate")
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Convert scraped article to published article."""
        from content.models import Article, Category
        
        scraped_article = self.get_object()
        
        if scraped_article.status != 'approved':
            return APIResponse.error(
                message="Article must be approved before publishing",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Optionally download and save image
            download_image = request.data.get('download_image', False)
            featured_image = None
            featured_image_url = scraped_article.image_url
            
            if download_image and scraped_article.image_url:
                from .services import NewsScrapingService
                media_file = NewsScrapingService.download_and_save_image(
                    image_url=scraped_article.image_url,
                    article_title=scraped_article.title,
                    user=request.user
                )
                if media_file:
                    featured_image = media_file.file
                    # Keep URL as fallback
                    featured_image_url = scraped_article.image_url
            
            # Create article from scraped article
            article = Article.objects.create(
                title=scraped_article.title,
                excerpt=scraped_article.excerpt or scraped_article.content[:500],
                content=scraped_article.content,
                author=request.user,
                status='published',
                featured_image=featured_image,
                featured_image_url=featured_image_url,
                published_at=scraped_article.published_at,
                primary_category=scraped_article.category  # Apply category from scraped article
            )
            
            # Apply tags from scraped article
            if scraped_article.tags.exists():
                article.tags.set(scraped_article.tags.all())
            
            # Update scraped article status
            scraped_article.status = 'published'
            scraped_article.save()
            
            return APIResponse.success(
                data={
                    'article_id': article.id,
                    'image_downloaded': featured_image is not None
                },
                message=f"Article '{article.title}' published successfully"
            )
            
        except Exception as e:
            return APIResponse.error(
                message=f"Failed to publish article: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get pending articles."""
        pending_articles = self.get_queryset().filter(status='pending')
        serializer = self.get_serializer(pending_articles, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Pending articles retrieved")
    
    @action(detail=False, methods=['get'])
    def approved(self, request):
        """Get approved articles."""
        approved_articles = self.get_queryset().filter(status='approved')
        serializer = self.get_serializer(approved_articles, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Approved articles retrieved")
    
    @action(detail=False, methods=['get'])
    def high_quality(self, request):
        """Get high-quality articles (quality_score >= 0.8)."""
        high_quality_articles = self.get_queryset().filter(quality_score__gte=0.8)
        serializer = self.get_serializer(high_quality_articles, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="High-quality articles retrieved")


class ScrapingJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ScrapingJob (read-only, jobs are created automatically).
    """
    
    queryset = ScrapingJob.objects.all()
    serializer_class = ScrapingJobSerializer
    permission_classes = [IsEditorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'source']
    ordering_fields = ['created_at', 'started_at', 'completed_at']
    ordering = ['-created_at']
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get logs for a scraping job."""
        job = self.get_object()
        logs = ScrapingLog.objects.filter(job=job).order_by('-created_at')
        
        serializer = ScrapingLogSerializer(logs, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Job logs retrieved")


class ScrapingLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ScrapingLog (read-only).
    """
    
    queryset = ScrapingLog.objects.all()
    serializer_class = ScrapingLogSerializer
    permission_classes = [IsEditorOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['source', 'level', 'job']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
