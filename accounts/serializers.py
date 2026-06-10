"""
Serializers for accounts app.
"""

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, UserProfile, UserSession, PasswordResetCode
from core.utils import ValidationHelper
import requests
from urllib.parse import urlparse
import os
import logging

logger = logging.getLogger(__name__)


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    """
    
    password = serializers.CharField(
        write_only=True, 
        validators=[validate_password],
        help_text="Password must be at least 8 characters long",
        label="Password",
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        help_text="Confirm your password",
        label="Confirm Password",
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 
            'password', 'password_confirm', 'phone', 'bio'
        ]
        extra_kwargs = {
            'email': {
                'required': True,
                'help_text': 'Valid email address'
            },
            'first_name': {
                'required': True,
                'help_text': 'Your first name'
            },
            'last_name': {
                'required': True,
                'help_text': 'Your last name'
            },
            'username': {
                'help_text': 'Unique username (optional)'
            },
            'phone': {
                'help_text': 'Phone number (optional)'
            },
            'bio': {
                'help_text': 'Short bio about yourself (optional)'
            }
        }
    
    def validate_email(self, value):
        """Validate email format and uniqueness."""
        if not ValidationHelper.validate_email(value):
            raise serializers.ValidationError("Invalid email format.")
        
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("User with this email already exists.")
        
        return value.lower()
    
    def validate_phone(self, value):
        """Validate phone number format."""
        if value and not ValidationHelper.validate_phone(value):
            raise serializers.ValidationError("Invalid phone number format.")
        return value
    
    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs
    
    def create(self, validated_data):
        """Create new user."""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        
        # User profile is automatically created by signal
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    """
    
    email = serializers.EmailField(
        help_text="User's email address",
        label="Email Address"
    )
    password = serializers.CharField(
        help_text="User's password",
        label="Password",
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """Validate login credentials."""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid credentials.")
            if not user.is_active:
                raise serializers.ValidationError("User account is disabled.")
            attrs['user'] = user
        else:
            raise serializers.ValidationError("Must include email and password.")
        
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user data.
    """
    
    full_name = serializers.ReadOnlyField()
    is_reporter = serializers.ReadOnlyField()
    is_editor = serializers.ReadOnlyField()
    is_admin = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'full_name', 'role', 'bio', 'avatar', 'phone', 
            'is_verified', 'is_active', 'date_joined', 'last_login',
            'is_reporter', 'is_editor', 'is_admin'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user data including role-based fields.
    """
    
    full_name = serializers.ReadOnlyField()
    is_reporter = serializers.ReadOnlyField()
    is_editor = serializers.ReadOnlyField()
    is_admin = serializers.ReadOnlyField()
    avatar = serializers.ImageField(required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'full_name', 'role', 'bio', 'avatar', 'phone', 
            'is_verified', 'is_active', 'date_joined', 'last_login',
            'is_reporter', 'is_editor', 'is_admin'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def validate_username(self, value):
        request = self.context.get('request')
        if request and self.instance:
            if value != self.instance.username:
                if not (request.user.is_admin or request.user.is_staff):
                    raise serializers.ValidationError("Only admins can change usernames.")
                if User.objects.filter(username=value).exclude(pk=self.instance.pk).exists():
                    raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        request = self.context.get('request')
        if request and self.instance:
            if value != self.instance.email:
                if not (request.user.is_admin or request.user.is_staff):
                    raise serializers.ValidationError("Only admins can change email addresses.")
                if User.objects.filter(email=value.lower()).exclude(pk=self.instance.pk).exists():
                    raise serializers.ValidationError("This email is already taken.")
        return value.lower()

    def validate_avatar(self, value):
        """Validate avatar - can be a file or URL string."""
        # If it's already a file (InMemoryUploadedFile or TemporaryUploadedFile), return as is
        if hasattr(value, 'read'):
            return value
        
        # If it's a string (URL), we'll handle it in update method
        if isinstance(value, str):
            return value
        
        return value
    
    def validate_role(self, value):
        """Validate role changes."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Only admins can change roles
            if not (request.user.is_admin or request.user.is_staff):
                raise serializers.ValidationError("Only admins can change user roles.")
        return value
    
    def _download_image_from_url(self, url):
        """Download image from URL and return as ContentFile."""
        try:
            # Skip placeholder images
            if 'placeholder.com' in url or 'via.placeholder' in url:
                raise ValueError("Placeholder images are not allowed")
            
            # Download image
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                raise ValueError(f"URL does not point to an image: {content_type}")
            
            # Read image data
            image_data = response.content
            
            # Generate filename from URL
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename or '.' not in filename:
                # Default to jpg if no extension
                filename = f"avatar_{parsed_url.netloc.replace('.', '_')}.jpg"
            
            # Create ContentFile
            return ContentFile(image_data, name=filename)
        except Exception as e:
            logger.error(f"Error downloading image from URL {url}: {str(e)}")
            raise serializers.ValidationError(f"Failed to download image from URL: {str(e)}")
    
    def update(self, instance, validated_data):
        """Update user instance."""
        # Handle avatar URL if provided as string
        if 'avatar' in validated_data:
            avatar_value = validated_data['avatar']
            # If avatar is a URL string, download it
            if isinstance(avatar_value, str):
                try:
                    downloaded_file = self._download_image_from_url(avatar_value)
                    validated_data['avatar'] = downloaded_file
                except serializers.ValidationError:
                    raise
                except Exception as e:
                    raise serializers.ValidationError({'avatar': f"Failed to process avatar URL: {str(e)}"})
        
        # Update the role field which will automatically update the is_* properties
        if 'role' in validated_data:
            instance.role = validated_data['role']
        
        # Update other fields
        for attr, value in validated_data.items():
            if attr != 'role':
                setattr(instance, attr, value)
        
        instance.save()
        return instance


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile data.
    """
    
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'date_of_birth', 'location', 'website',
            'social_media', 'preferences', 'notification_settings',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for password change.
    """
    
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate_old_password(self, value):
        """Validate old password."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value
    
    def validate(self, attrs):
        """Validate new password confirmation."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match.")
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request.
    """
    
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Validate email exists."""
        if not User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation using code.
    """
    
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate_code(self, value):
        """Validate reset code format."""
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("Code must be a 6-digit number.")
        return value
    
    def validate(self, attrs):
        """Validate reset code and password confirmation."""
        email = attrs.get('email')
        code = attrs.get('code')
        
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match.")
        
        try:
            reset_code = PasswordResetCode.objects.get(
                user__email=email,
                code=code
            )
            
            if not reset_code.is_valid():
                if reset_code.is_expired():
                    raise serializers.ValidationError("Reset code has expired.")
                elif reset_code.is_used:
                    raise serializers.ValidationError("Reset code has already been used.")
                elif reset_code.attempts >= reset_code.max_attempts:
                    raise serializers.ValidationError("Too many failed attempts. Please request a new code.")
                else:
                    raise serializers.ValidationError("Invalid reset code.")
            
            attrs['reset_code'] = reset_code
            return attrs
            
        except PasswordResetCode.DoesNotExist:
            raise serializers.ValidationError("Invalid email or reset code.")


class UserSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for user session data.
    """
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'session_key', 'ip_address', 'user_agent',
            'is_active', 'last_activity', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT token serializer that includes user data.
    """
    
    email = serializers.EmailField(
        help_text="User's email address",
        label="Email Address"
    )
    password = serializers.CharField(
        help_text="User's password",
        label="Password",
        style={'input_type': 'password'}
    )
    
    def validate(self, attrs):
        """Validate credentials and return tokens with user data."""
        data = super().validate(attrs)
        
        # Add user data to response
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': self.user.role,
            'is_verified': self.user.is_verified,
        }
        
        return data


class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for JWT token refresh.
    """
    
    refresh = serializers.CharField(
        help_text="JWT refresh token",
        label="Refresh Token"
    )