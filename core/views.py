"""
Core views for Somali Report Backend.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.http import JsonResponse
from core.utils import APIResponse


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint.
    """
    return APIResponse.success(
        data={'status': 'healthy', 'service': 'Somali Report API'},
        message='Service is running'
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def api_info(request):
    """
    API information endpoint.
    """
    info = {
        'name': 'Somali Report API',
        'version': '1.0.0',
        'description': 'API for Somali Report News Platform',
        'endpoints': {
            'authentication': '/api/v1/auth/',
            'users': '/api/v1/users/',
            'articles': '/api/v1/articles/',
            'categories': '/api/v1/categories/',
            'comments': '/api/v1/comments/',
            'docs': '/api/docs/',
        }
    }
    return APIResponse.success(data=info, message='API Information')


@api_view(['GET'])
@permission_classes([AllowAny])
def error_test(request):
    """
    Test endpoint for error handling.
    """
    try:
        # This will raise an exception for testing
        raise ValueError("This is a test error")
    except Exception as e:
        return APIResponse.error(
            message="Test error occurred",
            errors=[str(e)],
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )