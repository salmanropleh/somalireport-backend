"""
Serializers for accounts app.
"""

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User, UserProfile, UserSession, PasswordResetToken
from core.utils import ValidationHelper


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
    Serializer for password reset confirmation.
    """
    
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    new_password_confirm = serializers.CharField()
    
    def validate_token(self, value):
        """Validate reset token."""
        try:
            reset_token = PasswordResetToken.objects.get(token=value)
            if not reset_token.is_valid():
                raise serializers.ValidationError("Invalid or expired token.")
            return value
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token.")
    
    def validate(self, attrs):
        """Validate new password confirmation."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match.")
        return attrs


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
