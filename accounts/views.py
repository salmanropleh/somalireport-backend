"""
Views for accounts app.
"""

from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.contrib.auth import login, logout
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import uuid
import logging

from .models import User, UserProfile, UserSession, PasswordResetToken
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    UserProfileSerializer, PasswordChangeSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    UserSessionSerializer, CustomTokenObtainPairSerializer
)
from core.utils import APIResponse
from core.permissions import IsOwnerOrAdmin

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management.
    """
    
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == 'create':
            permission_classes = [permissions.AllowAny]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsOwnerOrAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        """
        Return the serializer class for the current action.
        """
        if self.action == 'create':
            return UserRegistrationSerializer
        return UserSerializer
    
    def create(self, request, *args, **kwargs):
        """
        Register a new user.
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return APIResponse.success(
                data=UserSerializer(user).data,
                message="User registered successfully",
                status_code=status.HTTP_201_CREATED
            )
        return APIResponse.error(
            message="Registration failed",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """
        Get current user's profile.
        """
        serializer = self.get_serializer(request.user)
        return APIResponse.success(data=serializer.data, message="User profile retrieved")
    
    @action(detail=False, methods=['put', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def update_me(self, request):
        """
        Update current user's profile.
        """
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return APIResponse.success(data=serializer.data, message="Profile updated successfully")
        return APIResponse.error(message="Update failed", errors=serializer.errors)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        """
        Change user password.
        """
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return APIResponse.success(message="Password changed successfully")
        return APIResponse.error(message="Password change failed", errors=serializer.errors)


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user profile management.
    """
    
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsOwnerOrAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_profile(self, request):
        """
        Get current user's profile.
        """
        try:
            profile = request.user.profile
            serializer = self.get_serializer(profile)
            return APIResponse.success(data=serializer.data, message="Profile retrieved")
        except UserProfile.DoesNotExist:
            return APIResponse.error(
                message="Profile not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['put', 'patch'], permission_classes=[permissions.IsAuthenticated])
    def update_my_profile(self, request):
        """
        Update current user's profile.
        """
        try:
            profile = request.user.profile
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return APIResponse.success(data=serializer.data, message="Profile updated successfully")
            return APIResponse.error(message="Update failed", errors=serializer.errors)
        except UserProfile.DoesNotExist:
            return APIResponse.error(
                message="Profile not found",
                status_code=status.HTTP_404_NOT_FOUND
            )


@extend_schema_view(
    register=extend_schema(
        summary="User Registration",
        description="Register a new user account",
        request=UserRegistrationSerializer,
        responses={
            201: UserSerializer,
            400: {"description": "Invalid registration data"}
        },
        tags=["Authentication"]
    ),
    login=extend_schema(
        summary="User Login",
        description="Authenticate user with email and password",
        request=UserLoginSerializer,
        responses={
            200: UserSerializer,
            400: {"description": "Invalid credentials"}
        },
        tags=["Authentication"]
    ),
    logout=extend_schema(
        summary="User Logout",
        description="Logout current user",
        responses={
            200: {"description": "Logout successful"}
        },
        tags=["Authentication"]
    ),
    password_reset_request=extend_schema(
        summary="Request Password Reset",
        description="Request password reset email",
        request=PasswordResetRequestSerializer,
        responses={
            200: {"description": "Password reset email sent"},
            400: {"description": "Invalid email"}
        },
        tags=["Authentication"]
    ),
    password_reset_confirm=extend_schema(
        summary="Confirm Password Reset",
        description="Confirm password reset with token",
        request=PasswordResetConfirmSerializer,
        responses={
            200: {"description": "Password reset successful"},
            400: {"description": "Invalid token or password"}
        },
        tags=["Authentication"]
    ),
)
class AuthViewSet(viewsets.ViewSet):
    """
    ViewSet for authentication operations.
    """
    
    permission_classes = [permissions.AllowAny]
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """
        Register a new user.
        """
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return APIResponse.success(
                data=UserSerializer(user).data,
                message="Registration successful",
                status_code=status.HTTP_201_CREATED
            )
        return APIResponse.error(
            message="Registration failed",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """
        User login.
        """
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            
            # Update last activity
            user.last_activity = timezone.now()
            user.save()
            
            # Create session record
            UserSession.objects.create(
                user=user,
                session_key=request.session.session_key,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return APIResponse.success(
                data=UserSerializer(user).data,
                message="Login successful"
            )
        return APIResponse.error(message="Login failed", errors=serializer.errors)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """
        User logout.
        """
        # Deactivate current session
        try:
            session = UserSession.objects.get(
                user=request.user,
                session_key=request.session.session_key
            )
            session.is_active = False
            session.save()
        except UserSession.DoesNotExist:
            pass
        
        logout(request)
        return APIResponse.success(message="Logout successful")
    
    @action(detail=False, methods=['post'])
    def password_reset_request(self, request):
        """
        Request password reset.
        """
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)
            
            # Generate reset token
            token = str(uuid.uuid4())
            PasswordResetToken.objects.create(
                user=user,
                token=token,
                expires_at=timezone.now() + timezone.timedelta(hours=24)
            )
            
            # Send reset email
            try:
                send_mail(
                    'Password Reset Request',
                    f'Click the link to reset your password: {settings.FRONTEND_URL}/reset-password/{token}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                return APIResponse.success(message="Password reset email sent")
            except Exception as e:
                logger.error(f"Failed to send password reset email: {e}")
                return APIResponse.error(message="Failed to send reset email")
        
        return APIResponse.error(message="Invalid email", errors=serializer.errors)
    
    @action(detail=False, methods=['post'])
    def password_reset_confirm(self, request):
        """
        Confirm password reset.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            token = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']
            
            reset_token = PasswordResetToken.objects.get(token=token)
            user = reset_token.user
            
            # Update password
            user.set_password(new_password)
            user.save()
            
            # Mark token as used
            reset_token.is_used = True
            reset_token.save()
            
            return APIResponse.success(message="Password reset successful")
        
        return APIResponse.error(message="Password reset failed", errors=serializer.errors)


class UserSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for user session management.
    """
    
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Return sessions for the current user.
        """
        return UserSession.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """
        Terminate a specific session.
        """
        try:
            session = self.get_object()
            session.is_active = False
            session.save()
            return APIResponse.success(message="Session terminated")
        except UserSession.DoesNotExist:
            return APIResponse.error(
                message="Session not found",
                status_code=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'])
    def terminate_all(self, request):
        """
        Terminate all sessions except current one.
        """
        UserSession.objects.filter(
            user=request.user,
            session_key__ne=request.session.session_key
        ).update(is_active=False)
        
        return APIResponse.success(message="All other sessions terminated")


# JWT Authentication Views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token obtain view that returns user data along with tokens.
    """
    serializer_class = CustomTokenObtainPairSerializer
    
    @extend_schema(
        summary="Obtain JWT Token",
        description="Get JWT access and refresh tokens by providing email and password",
        request=CustomTokenObtainPairSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "access": {"type": "string", "description": "JWT access token"},
                    "refresh": {"type": "string", "description": "JWT refresh token"},
                    "user": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "username": {"type": "string"},
                            "email": {"type": "string"},
                            "first_name": {"type": "string"},
                            "last_name": {"type": "string"},
                            "role": {"type": "string"},
                            "is_verified": {"type": "boolean"}
                        }
                    }
                }
            },
            400: {"description": "Invalid credentials"}
        },
        tags=["JWT Authentication"]
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Add user data to response
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                user = serializer.user
                response.data['user'] = UserSerializer(user).data
                response.data['message'] = 'Login successful'
        
        return response


class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom JWT token refresh view.
    """
    
    @extend_schema(
        summary="Refresh JWT Token",
        description="Get a new access token using a valid refresh token",
        request={
            "type": "object",
            "properties": {
                "refresh": {"type": "string", "description": "JWT refresh token"}
            },
            "required": ["refresh"]
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "access": {"type": "string", "description": "New JWT access token"}
                }
            },
            400: {"description": "Invalid refresh token"}
        },
        tags=["JWT Authentication"]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    """
    Logout view that blacklists the refresh token.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Logout",
        description="Logout user and blacklist refresh token",
        request={
            "type": "object",
            "properties": {
                "refresh": {"type": "string", "description": "JWT refresh token to blacklist"}
            },
            "required": ["refresh"]
        },
        responses={
            200: {"description": "Logout successful"},
            400: {"description": "Logout failed"}
        },
        tags=["JWT Authentication"]
    )
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return APIResponse.success(message="Logout successful")
        except Exception as e:
            return APIResponse.error(message="Logout failed", status_code=status.HTTP_400_BAD_REQUEST)