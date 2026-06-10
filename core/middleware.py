"""
Custom middleware for Somali Report Backend.
"""

import logging
import time
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

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


class JWTTokenRefreshMiddleware(MiddlewareMixin):
    """
    Middleware to automatically refresh JWT tokens when they're about to expire.
    """
    
    def process_response(self, request, response):
        """Add token refresh information to response headers."""
        if (request.path.startswith('/api/') and 
            hasattr(request, 'user') and 
            request.user.is_authenticated and
            response.status_code == 200):
            
            # Check if there's an Authorization header
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token_string = auth_header.split(' ')[1]
                try:
                    token = AccessToken(token_string)
                    
                    # Check if token expires within the next 30 minutes
                    import datetime
                    now = timezone.now()
                    token_exp = token.get('exp')
                    token_exp_datetime = datetime.datetime.fromtimestamp(token_exp, tz=timezone.utc)
                    
                    # If token expires within 30 minutes, add refresh hint
                    if (token_exp_datetime - now).total_seconds() < 1800:  # 30 minutes
                        response['X-Token-Refresh-Suggested'] = 'true'
                        response['X-Token-Expires-At'] = token_exp_datetime.isoformat()
                        
                except (TokenError, InvalidToken, ValueError):
                    # Token is invalid, don't add headers
                    pass
        
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
