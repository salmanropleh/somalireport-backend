"""
User models for Somali Report Backend.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from core.models import BaseModel


class User(AbstractUser):
    """
    Custom User model with additional fields for news platform.
    """
    
    ROLE_CHOICES = [
        ('reader', 'Reader'),
        ('reporter', 'Reporter'),
        ('editor', 'Editor'),
        ('admin', 'Admin'),
    ]
    
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='reader')
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True, null=True)
    last_activity = models.DateTimeField(default=timezone.now)
    
    # Override username field to use email
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def is_reporter(self):
        """Check if user is a reporter."""
        return self.role == 'reporter'
    
    @property
    def is_editor(self):
        """Check if user is an editor."""
        return self.role == 'editor'
    
    @property
    def is_admin(self):
        """Check if user is an admin."""
        return self.role == 'admin' or self.is_staff
    
    def can_publish_articles(self):
        """Check if user can publish articles."""
        return self.role in ['reporter', 'editor', 'admin'] or self.is_staff
    
    def can_moderate_content(self):
        """Check if user can moderate content."""
        return self.role in ['editor', 'admin'] or self.is_staff


class UserProfile(BaseModel):
    """
    Extended user profile information.
    """
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    date_of_birth = models.DateField(blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    social_media = models.JSONField(default=dict, blank=True)
    preferences = models.JSONField(default=dict, blank=True)
    notification_settings = models.JSONField(default=dict, blank=True)
    
    class Meta:
        db_table = 'user_profiles'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.email} Profile"


class UserSession(BaseModel):
    """
    Track user sessions for security and analytics.
    """
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=100, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'user_sessions'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
    
    def __str__(self):
        return f"{self.user.email} - {self.session_key}"


class PasswordResetToken(BaseModel):
    """
    Store password reset tokens.
    """
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=100, unique=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'password_reset_tokens'
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'
    
    def __str__(self):
        return f"Password reset token for {self.user.email}"
    
    def is_expired(self):
        """Check if token is expired."""
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if token is valid."""
        return not self.is_used and not self.is_expired()