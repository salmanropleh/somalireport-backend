"""
URL patterns for accounts app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, UserProfileViewSet, AuthViewSet, UserSessionViewSet,
    CustomTokenObtainPairView, CustomTokenRefreshView, LogoutView, TokenStatusView,
    AuthorViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'profiles', UserProfileViewSet)
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'sessions', UserSessionViewSet, basename='sessions')
router.register(r'authors', AuthorViewSet, basename='authors')

app_name = 'accounts'

urlpatterns = [
    path('', include(router.urls)),
    # JWT Authentication endpoints
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('token/status/', TokenStatusView.as_view(), name='token_status'),
    path('logout/', LogoutView.as_view(), name='logout'),
]
