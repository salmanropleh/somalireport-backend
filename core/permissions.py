"""
Custom permissions for Somali Report Backend.
"""

from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the object.
        return obj.created_by == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit objects.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to admin users.
        return request.user.is_authenticated and request.user.is_staff


class IsEditorOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow editors and admins to edit objects.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are allowed to editors and admins.
        return request.user.is_authenticated and (
            request.user.is_staff or 
            hasattr(request.user, 'role') and request.user.role in ['editor', 'admin']
        )


class IsReporterOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow reporters, editors and admins to edit objects.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are allowed to reporters, editors and admins.
        return request.user.is_authenticated and (
            request.user.is_staff or 
            hasattr(request.user, 'role') and request.user.role in ['reporter', 'editor', 'admin']
        )


class IsAuthenticatedOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow authenticated users to edit objects.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to authenticated users.
        return request.user.is_authenticated


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow owners or admins to access objects.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin users have full access
        if request.user.is_staff:
            return True
        
        # Owners have full access
        if hasattr(obj, 'created_by') and obj.created_by == request.user:
            return True
        
        # Check if user is the object itself (for user profile access)
        if obj == request.user:
            return True
        
        return False


class IsPublicOrAuthenticated(permissions.BasePermission):
    """
    Custom permission to allow public read access or authenticated write access.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to authenticated users
        return request.user.is_authenticated


class IsActiveUser(permissions.BasePermission):
    """
    Custom permission to only allow active users.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_active
