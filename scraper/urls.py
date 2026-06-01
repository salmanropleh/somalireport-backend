"""
URL patterns for scraper app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NewsSourceViewSet, ScrapedArticleViewSet, ScrapingJobViewSet, ScrapingLogViewSet

router = DefaultRouter()
router.register(r'sources', NewsSourceViewSet, basename='newssource')
router.register(r'articles', ScrapedArticleViewSet, basename='scrapedarticle')
router.register(r'jobs', ScrapingJobViewSet, basename='scrapingjob')
router.register(r'logs', ScrapingLogViewSet, basename='scrapinglog')

app_name = 'scraper'

urlpatterns = [
    path('', include(router.urls)),
]

