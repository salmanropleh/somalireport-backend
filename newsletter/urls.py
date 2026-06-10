"""
URL patterns for newsletter app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NewsletterViewSet, NewsletterSubscriptionViewSet

router = DefaultRouter()
router.register(r'subscriptions', NewsletterSubscriptionViewSet, basename='subscription')
router.register(r'newsletters', NewsletterViewSet, basename='newsletter')

app_name = 'newsletter'

urlpatterns = [
    path('', include(router.urls)),
]
