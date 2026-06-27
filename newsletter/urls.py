"""
URL patterns for newsletter app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NewsletterViewSet, NewsletterSubscriptionViewSet, NewsletterPublicViewSet, public_subscribe, public_unsubscribe

router = DefaultRouter()
router.register(r'newsletter-subscriptions', NewsletterSubscriptionViewSet, basename='newsletter-subscription')
router.register(r'newsletters/public', NewsletterPublicViewSet, basename='newsletter-public')
router.register(r'newsletters', NewsletterViewSet, basename='newsletter')

app_name = 'newsletter'

urlpatterns = [
    path('newsletter-subscriptions/subscribe/', public_subscribe, name='public-subscribe'),
    path('newsletter-subscriptions/unsubscribe/', public_unsubscribe, name='public-unsubscribe'),
    path('', include(router.urls)),
]
