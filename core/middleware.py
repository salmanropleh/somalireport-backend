"""
Custom middleware for Somali Report Backend.
"""

import logging
import time
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log HTTP requests and responses.
    """
    
    def process_request(self, request):
        """Log incoming request."""
        request.start_time = time.time()
        logger.info(f"Request: {request.method} {request.path} - User: {getattr(request.user, 'id', 'Anonymous')}")
    
    def process_response(self, request, response):
        """Log outgoing response."""
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            logger.info(f"Response: {response.status_code} - Duration: {duration:.3f}s")
        return response


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Middleware to handle errors and return standardized error responses.
    """
    
    def process_exception(self, request, exception):
        """Handle exceptions and return JSON error response."""
        logger.error(f"Exception in {request.path}: {str(exception)}", exc_info=True)
        
        if request.path.startswith('/api/'):
            if isinstance(exception, ValidationError):
                return JsonResponse({
                    'success': False,
                    'message': 'Validation Error',
                    'errors': exception.messages if hasattr(exception, 'messages') else [str(exception)],
                    'timestamp': timezone.now().isoformat()
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return JsonResponse({
                'success': False,
                'message': 'Internal Server Error',
                'errors': ['An unexpected error occurred'],
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return None


class CORSMiddleware(MiddlewareMixin):
    """
    Custom CORS middleware for additional control.
    """
    
    def process_response(self, request, response):
        """Add CORS headers to response."""
        if request.path.startswith('/api/'):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response['Access-Control-Allow-Credentials'] = 'true'
        
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers.
    """
    
    def process_response(self, request, response):
        """Add security headers to response."""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response
