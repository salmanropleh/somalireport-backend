"""
URL patterns for content app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, TagViewSet, ArticleViewSet, MediaFileViewSet, VideoViewSet, ContactViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'tags', TagViewSet)
router.register(r'articles', ArticleViewSet)
router.register(r'media', MediaFileViewSet)
router.register(r'videos', VideoViewSet)
router.register(r'contact', ContactViewSet)

app_name = 'content'

urlpatterns = [
    path('', include(router.urls)),
]
