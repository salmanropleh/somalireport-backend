"""
URL patterns for comments app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CommentViewSet, CommentReportViewSet, CommentSubscriptionViewSet,
    get_content_types
)

router = DefaultRouter()
router.register(r'comments', CommentViewSet)
router.register(r'reports', CommentReportViewSet)
router.register(r'subscriptions', CommentSubscriptionViewSet)

app_name = 'comments'

urlpatterns = [
    path('content-types/', get_content_types, name='content-types'),
    path('', include(router.urls)),
]
