"""
URL patterns for comments app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CommentViewSet, CommentReportViewSet, CommentSubscriptionViewSet

router = DefaultRouter()
router.register(r'comments', CommentViewSet)
router.register(r'reports', CommentReportViewSet)
router.register(r'subscriptions', CommentSubscriptionViewSet)

app_name = 'comments'

urlpatterns = [
    path('', include(router.urls)),
]
