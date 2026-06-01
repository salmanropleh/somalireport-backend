"""
Core utilities for Somali Report Backend.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import models
from django.http import HttpRequest
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


class APIResponse:
    """
    Standardized API response utility.
    """
    
    @staticmethod
    def success(data: Any = None, message: str = "Success", status_code: int = status.HTTP_200_OK) -> Response:
        """Create a successful API response."""
        response_data = {
            'success': True,
            'message': message,
            'data': data,
            'timestamp': timezone.now().isoformat()
        }
        return Response(response_data, status=status_code)
    
    @staticmethod
    def error(message: str = "Error", errors: List[str] = None, status_code: int = status.HTTP_400_BAD_REQUEST) -> Response:
        """Create an error API response."""
        response_data = {
            'success': False,
            'message': message,
            'errors': errors or [],
            'timestamp': timezone.now().isoformat()
        }
        return Response(response_data, status=status_code)
    
    @staticmethod
    def paginated(data: List[Any], page: int, page_size: int, total_count: int, message: str = "Success") -> Response:
        """Create a paginated API response."""
        response_data = {
            'success': True,
            'message': message,
            'data': data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size,
                'has_next': page * page_size < total_count,
                'has_previous': page > 1
            },
            'timestamp': timezone.now().isoformat()
        }
        return Response(response_data)


class PaginationHelper:
    """
    Helper class for pagination.
    """
    
    @staticmethod
    def paginate_queryset(queryset, page: int = 1, page_size: int = 20):
        """Paginate a queryset."""
        paginator = Paginator(queryset, page_size)
        try:
            page_obj = paginator.page(page)
        except Exception:
            page_obj = paginator.page(1)
        
        return {
            'results': page_obj.object_list,
            'pagination': {
                'page': page_obj.number,
                'page_size': page_size,
                'total_count': paginator.count,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        }


class ValidationHelper:
    """
    Helper class for validation.
    """
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format."""
        import re
        pattern = r'^\+?1?\d{9,15}$'
        return re.match(pattern, phone) is not None


class FileHelper:
    """
    Helper class for file operations.
    """
    
    @staticmethod
    def generate_unique_filename(original_filename: str) -> str:
        """Generate a unique filename."""
        import os
        name, ext = os.path.splitext(original_filename)
        unique_id = str(uuid.uuid4())[:8]
        return f"{name}_{unique_id}{ext}"
    
    @staticmethod
    def get_file_size(file) -> int:
        """Get file size in bytes."""
        if hasattr(file, 'size'):
            return file.size
        return 0
    
    @staticmethod
    def is_image_file(filename: str) -> bool:
        """Check if file is an image."""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        return any(filename.lower().endswith(ext) for ext in image_extensions)


class CacheHelper:
    """
    Helper class for caching operations.
    """
    
    @staticmethod
    def get_cache_key(prefix: str, *args) -> str:
        """Generate a cache key."""
        return f"{prefix}:{':'.join(str(arg) for arg in args)}"
    
    @staticmethod
    def invalidate_pattern(cache, pattern: str):
        """Invalidate cache keys matching a pattern."""
        try:
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(pattern)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache pattern {pattern}: {e}")


class LoggingHelper:
    """
    Helper class for logging operations.
    """
    
    @staticmethod
    def log_request(request: HttpRequest, response: Response = None):
        """Log HTTP request details."""
        logger.info(f"Request: {request.method} {request.path} - User: {getattr(request.user, 'id', 'Anonymous')}")
        if response:
            logger.info(f"Response: {response.status_code}")
    
    @staticmethod
    def log_error(error: Exception, context: str = ""):
        """Log error with context."""
        logger.error(f"Error in {context}: {str(error)}", exc_info=True)


class StringHelper:
    """
    Helper class for string operations.
    """
    
    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to URL-friendly slug."""
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text.strip('-')
    
    @staticmethod
    def truncate(text: str, length: int = 100, suffix: str = "...") -> str:
        """Truncate text to specified length."""
        if len(text) <= length:
            return text
        return text[:length - len(suffix)] + suffix
    
    @staticmethod
    def extract_excerpt(text: str, length: int = 150) -> str:
        """Extract excerpt from text."""
        # Remove HTML tags
        import re
        clean_text = re.sub(r'<[^>]+>', '', text)
        return StringHelper.truncate(clean_text, length)
