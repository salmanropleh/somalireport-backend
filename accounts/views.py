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

from .models import User, UserProfile, UserSession, PasswordResetCode
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserSerializer,
    UserUpdateSerializer, UserProfileSerializer, PasswordChangeSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    UserSessionSerializer, CustomTokenObtainPairSerializer, TokenRefreshSerializer,
    AuthorPublicSerializer
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
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
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
    
    def update(self, request, *args, **kwargs):
        """
        Update user instance.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            serializer.save()
            return APIResponse.success(
                data=UserSerializer(instance).data,
                message="User updated successfully"
            )
        return APIResponse.error(
            message="Update failed",
            errors=serializer.errors,
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    def partial_update(self, request, *args, **kwargs):
        """
        Partially update user instance.
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def update_role(self, request, pk=None):
        """
        Update user role (admin only).
        """
        user = self.get_object()
        new_role = request.data.get('role')
        
        if not new_role:
            return APIResponse.error(
                message="Role is required",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate role
        valid_roles = ['reader', 'reporter', 'editor', 'admin']
        if new_role not in valid_roles:
            return APIResponse.error(
                message=f"Invalid role. Must be one of: {', '.join(valid_roles)}",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        # Update role
        old_role = user.role
        user.role = new_role
        user.save()
        
        return APIResponse.success(
            data=UserSerializer(user).data,
            message=f"User role updated from {old_role} to {new_role}"
        )
    
    @extend_schema(
        summary="Change Password",
        description="Change the authenticated user's password",
        request=PasswordChangeSerializer,
        responses={
            200: {"description": "Password changed successfully"},
            400: {"description": "Invalid password data"}
        },
        tags=["Users"]
    )
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
        Request password reset code.
        """
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                
                # Generate reset code
                code = PasswordResetCode.generate_code()
                
                # Invalidate any existing codes for this user
                PasswordResetCode.objects.filter(user=user, is_used=False).update(is_used=True)
                
                # Create new reset code
                reset_code = PasswordResetCode.objects.create(
                    user=user,
                    code=code,
                    expires_at=timezone.now() + timezone.timedelta(minutes=15)  # 15 minutes expiry
                )
                
                # Send reset email
                try:
                    send_mail(
                        'Password Reset Code - Somali Report',
                        f'Hello {user.first_name},\n\nYou requested a password reset for your Somali Report account.\n\nYour reset code is: {code}\n\nThis code will expire in 15 minutes.\n\nIf you did not request this password reset, please ignore this email.\n\nBest regards,\nSomali Report Team',
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )
                    logger.info(f"Password reset code sent successfully to {email}")
                    return APIResponse.success(message="Password reset code sent")
                except Exception as e:
                    logger.error(f"Failed to send password reset email to {email}: {e}")
                    return APIResponse.error(message="Failed to send reset code")
            except User.DoesNotExist:
                logger.warning(f"Password reset requested for non-existent email: {email}")
                # Don't reveal if email exists or not for security
                return APIResponse.success(message="If the email exists, a password reset code has been sent")
        
        return APIResponse.error(message="Invalid email", errors=serializer.errors)
    
    @action(detail=False, methods=['post'])
    def password_reset_confirm(self, request):
        """
        Confirm password reset using code.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            reset_code = serializer.validated_data['reset_code']
            new_password = serializer.validated_data['new_password']
            user = reset_code.user
            
            # Update password
            user.set_password(new_password)
            user.save()
            
            # Mark code as used
            reset_code.is_used = True
            reset_code.save()
            
            logger.info(f"Password reset successful for user {user.email}")
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


# JWT Authentication Views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken


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
    serializer_class = TokenRefreshSerializer
    
    @extend_schema(
        summary="Refresh JWT Token",
        description="Get a new access token using a valid refresh token",
        request=TokenRefreshSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "access": {"type": "string", "description": "New JWT access token"},
                    "refresh": {"type": "string", "description": "New JWT refresh token (if rotating refresh tokens enabled)"},
                    "message": {"type": "string", "description": "Success message"}
                }
            },
            400: {"description": "Invalid refresh token"}
        },
        tags=["JWT Authentication"]
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            response.data['message'] = 'Token refreshed successfully'
        
        return response


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


class TokenStatusView(APIView):
    """
    View to check JWT token status and get token information.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @extend_schema(
        summary="Check Token Status",
        description="Get information about the current JWT token",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "valid": {"type": "boolean", "description": "Whether the token is valid"},
                    "expires_at": {"type": "string", "description": "Token expiration timestamp"},
                    "time_until_expiry": {"type": "integer", "description": "Seconds until token expires"},
                    "user": {"type": "object", "description": "User information"},
                    "refresh_suggested": {"type": "boolean", "description": "Whether token refresh is suggested"}
                }
            },
            401: {"description": "Invalid or expired token"}
        },
        tags=["JWT Authentication"]
    )
    def get(self, request):
        """Check the status of the current JWT token."""
        try:
            # Get token from Authorization header
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Bearer '):
                return APIResponse.error(
                    message="No valid token provided",
                    status_code=status.HTTP_401_UNAUTHORIZED
                )
            
            token_string = auth_header.split(' ')[1]
            token = AccessToken(token_string)
            
            # Get token expiration info
            import datetime
            now = timezone.now()
            token_exp = token.get('exp')
            token_exp_datetime = datetime.datetime.fromtimestamp(token_exp, tz=timezone.utc)
            time_until_expiry = int((token_exp_datetime - now).total_seconds())
            
            # Determine if refresh is suggested (within 30 minutes)
            refresh_suggested = time_until_expiry < 1800
            
            return APIResponse.success(
                data={
                    'valid': True,
                    'expires_at': token_exp_datetime.isoformat(),
                    'time_until_expiry': max(0, time_until_expiry),
                    'user': UserSerializer(request.user).data,
                    'refresh_suggested': refresh_suggested
                },
                message="Token status retrieved successfully"
            )
            
        except Exception as e:
            return APIResponse.error(
                message="Invalid token",
                status_code=status.HTTP_401_UNAUTHORIZED
            )

class AuthorViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        from content.models import Article
        author_ids = Article.objects.filter(
            status='published', is_deleted=False
        ).values_list('author_id', flat=True).distinct()
        authors = User.objects.filter(id__in=author_ids).order_by('first_name')
        serializer = AuthorPublicSerializer(authors, many=True, context={'request': request})
        return APIResponse.success(data=serializer.data, message="Authors retrieved")

    def retrieve(self, request, pk=None):
        from content.models import Article
        from content.serializers import ArticleListSerializer
        from rest_framework.pagination import PageNumberPagination

        try:
            if str(pk).isdigit():
                author = User.objects.get(pk=pk)
            else:
                author = User.objects.get(username=pk)
        except User.DoesNotExist:
            return APIResponse.error(message="Author not found", status_code=404)

        articles = Article.objects.filter(
            author=author, status='published', is_deleted=False
        ).select_related('author', 'primary_category').prefetch_related(
            'tags', 'secondary_categories'
        ).order_by('-published_at')

        paginator = PageNumberPagination()
        paginator.page_size = 10
        page = paginator.paginate_queryset(articles, request)
        articles_data = ArticleListSerializer(page, many=True, context={'request': request}).data

        return APIResponse.success(data={
            'author': AuthorPublicSerializer(author, context={'request': request}).data,
            'stats': {'article_count': articles.count()},
            'articles': {
                'count': articles.count(),
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
                'results': articles_data,
            }
        }, message="Author profile retrieved")
