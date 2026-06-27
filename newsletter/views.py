"""
Views for newsletter app.
"""

from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from .models import Newsletter, NewsletterSubscription, NewsletterRead
from .serializers import (
    NewsletterSubscribeSerializer,
    NewsletterUnsubscribeSerializer,
    NewsletterSubscriptionSerializer,
    NewsletterSubscriptionAdminSerializer,
    NewsletterListSerializer,
    NewsletterDetailSerializer,
    NewsletterCreateUpdateSerializer,
    NewsletterSendSerializer,
    NewsletterPublicListSerializer,
    NewsletterPublicDetailSerializer,
)
from core.utils import APIResponse
import logging

logger = logging.getLogger(__name__)


class IsAdminUser(permissions.BasePermission):
    """
    Permission to only allow admin users.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_staff or
            getattr(request.user, 'role', None) == 'admin'
        )


class NewsletterSubscriptionViewSet(viewsets.GenericViewSet):
    """
    ViewSet for newsletter subscription management.
    """

    queryset = NewsletterSubscription.objects.filter(is_deleted=False)
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action == 'subscribe':
            return NewsletterSubscribeSerializer
        elif self.action == 'unsubscribe':
            return NewsletterUnsubscribeSerializer
        elif self.action == 'my_subscription':
            return NewsletterSubscriptionSerializer
        return NewsletterSubscriptionSerializer

    @extend_schema(
        summary="Subscribe to Newsletter",
        description="Subscribe with an email address to receive newsletters. Anyone can subscribe.",
        request=NewsletterSubscribeSerializer,
        responses={201: NewsletterSubscriptionSerializer},
        tags=["Newsletter Subscription"]
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def subscribe(self, request):
        """Subscribe to the newsletter with email."""
        serializer = NewsletterSubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email'].lower().strip()

        # Check for existing inactive subscription to reactivate
        existing = NewsletterSubscription.objects.filter(
            email=email,
            is_deleted=False
        ).first()

        if existing:
            if existing.is_active:
                return APIResponse.error(
                    message="This email is already subscribed.",
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            else:
                # Reactivate the subscription
                existing.is_active = True
                existing.unsubscribed_at = None
                existing.unsubscribe_token = NewsletterSubscription.generate_unsubscribe_token()
                existing.save()
                subscription = existing
        else:
            # Create new subscription
            subscription = NewsletterSubscription.objects.create(
                email=email,
                user=request.user if request.user.is_authenticated else None
            )

        response_serializer = NewsletterSubscriptionSerializer(subscription)
        return APIResponse.success(
            data=response_serializer.data,
            message="Successfully subscribed to the newsletter.",
            status_code=status.HTTP_201_CREATED
        )

    @extend_schema(
        summary="Unsubscribe from Newsletter",
        description="Unsubscribe using the unsubscribe token from email.",
        request=NewsletterUnsubscribeSerializer,
        responses={200: {"description": "Unsubscribed successfully"}},
        tags=["Newsletter Subscription"]
    )
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def unsubscribe(self, request):
        """Unsubscribe from the newsletter using token."""
        serializer = NewsletterUnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data['token']

        subscription = NewsletterSubscription.objects.filter(
            unsubscribe_token=token,
            is_active=True,
            is_deleted=False
        ).first()

        if not subscription:
            return APIResponse.error(
                message="Invalid or expired unsubscribe token.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Deactivate subscription
        subscription.is_active = False
        subscription.unsubscribed_at = timezone.now()
        subscription.save()

        return APIResponse.success(
            message="Successfully unsubscribed from the newsletter."
        )

    @extend_schema(
        summary="Get My Subscription",
        description="Get the current user's newsletter subscription status.",
        responses={200: NewsletterSubscriptionSerializer},
        tags=["Newsletter Subscription"]
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_subscription(self, request):
        """Get current user's subscription status."""
        try:
            subscription = NewsletterSubscription.objects.get(
                user=request.user,
                is_deleted=False
            )
            serializer = NewsletterSubscriptionSerializer(subscription)
            return APIResponse.success(
                data=serializer.data,
                message="Subscription retrieved successfully."
            )
        except NewsletterSubscription.DoesNotExist:
            # Check if subscribed by email
            try:
                subscription = NewsletterSubscription.objects.get(
                    email=request.user.email,
                    is_deleted=False
                )
                serializer = NewsletterSubscriptionSerializer(subscription)
                return APIResponse.success(
                    data=serializer.data,
                    message="Subscription retrieved successfully."
                )
            except NewsletterSubscription.DoesNotExist:
                return APIResponse.success(
                    data=None,
                    message="Not subscribed to the newsletter."
                )


class NewsletterViewSet(viewsets.ModelViewSet):
    """
    ViewSet for newsletter management.
    """

    queryset = Newsletter.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['title', 'subject', 'excerpt']
    ordering_fields = ['created_at', 'sent_at', 'recipient_count', 'open_count']
    ordering = ['-created_at']
    parser_classes = [MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == 'list':
            return NewsletterListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return NewsletterCreateUpdateSerializer
        elif self.action == 'send':
            return NewsletterSendSerializer
        return NewsletterDetailSerializer

    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['my_newsletters', 'mark_read']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['list', 'retrieve']:
            # Admins can list all, users can only see sent newsletters
            if self.request.user.is_authenticated and (
                self.request.user.is_staff or
                getattr(self.request.user, 'role', None) == 'admin'
            ):
                permission_classes = [IsAdminUser]
            else:
                permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = Newsletter.objects.filter(is_deleted=False)

        # Admins can see all newsletters
        if self.request.user.is_authenticated and (
            self.request.user.is_staff or
            getattr(self.request.user, 'role', None) == 'admin'
        ):
            return queryset

        # Regular users can only see sent newsletters
        return queryset.filter(status='sent')

    def perform_create(self, serializer):
        """Set created_by when creating newsletter."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set updated_by when updating newsletter."""
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Hard delete the newsletter."""
        instance = self.get_object()
        instance.hard_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Send Newsletter",
        description="Send the newsletter to all active subscribers. Optionally send to a test email first.",
        request=NewsletterSendSerializer,
        responses={200: {"description": "Newsletter sent successfully"}},
        tags=["Newsletter Admin"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def send(self, request, pk=None):
        """Send newsletter to all subscribers."""
        newsletter = self.get_object()

        if newsletter.status == 'sent':
            return APIResponse.error(
                message="This newsletter has already been sent.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer = NewsletterSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_email = serializer.validated_data.get('test_email')

        if test_email:
            # Send test email
            from .tasks import send_test_newsletter_task
            try:
                send_test_newsletter_task(newsletter.id, test_email)
                return APIResponse.success(
                    message=f"Test newsletter sent to {test_email}."
                )
            except Exception as e:
                logger.error(f"Failed to send test newsletter: {e}")
                return APIResponse.error(
                    message=f"Failed to send test newsletter: {str(e)}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            # Send to all subscribers
            from .tasks import send_newsletter_task
            try:
                # Get active subscriber count
                subscriber_count = NewsletterSubscription.objects.filter(
                    is_active=True,
                    is_deleted=False
                ).count()

                if subscriber_count == 0:
                    return APIResponse.error(
                        message="No active subscribers to send the newsletter to.",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

                # Queue the task
                send_newsletter_task.delay(newsletter.id)

                # Update newsletter status
                newsletter.status = 'sent'
                newsletter.sent_at = timezone.now()
                newsletter.recipient_count = subscriber_count
                newsletter.save()

                return APIResponse.success(
                    data={
                        'newsletter_id': newsletter.id,
                        'recipient_count': subscriber_count,
                        'sent_at': newsletter.sent_at.isoformat()
                    },
                    message=f"Newsletter queued for sending to {subscriber_count} subscribers."
                )
            except Exception as e:
                logger.error(f"Failed to queue newsletter: {e}")
                return APIResponse.error(
                    message=f"Failed to send newsletter: {str(e)}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    @extend_schema(
        summary="Get My Newsletters",
        description="Get newsletters for the current subscribed user.",
        responses={200: NewsletterListSerializer(many=True)},
        tags=["Newsletter User"]
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_newsletters(self, request):
        """Get newsletters for the authenticated user."""
        # Check if user is subscribed
        subscription = NewsletterSubscription.objects.filter(
            Q(user=request.user) | Q(email=request.user.email),
            is_active=True,
            is_deleted=False
        ).first()

        if not subscription:
            return APIResponse.success(
                data=[],
                message="You are not subscribed to the newsletter."
            )

        # Get sent newsletters
        newsletters = Newsletter.objects.filter(
            status='sent',
            is_deleted=False
        ).order_by('-sent_at')

        page = self.paginate_queryset(newsletters)
        if page is not None:
            serializer = NewsletterListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = NewsletterListSerializer(newsletters, many=True, context={'request': request})
        return APIResponse.success(
            data=serializer.data,
            message="Newsletters retrieved successfully."
        )

    @extend_schema(
        summary="Mark Newsletter as Read",
        description="Mark a newsletter as read for the current user.",
        responses={200: {"description": "Newsletter marked as read"}},
        tags=["Newsletter User"]
    )
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def mark_read(self, request, pk=None):
        """Mark newsletter as read for current user."""
        newsletter = self.get_object()

        # Get user's subscription
        subscription = NewsletterSubscription.objects.filter(
            Q(user=request.user) | Q(email=request.user.email),
            is_active=True,
            is_deleted=False
        ).first()

        if not subscription:
            return APIResponse.error(
                message="You are not subscribed to the newsletter.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Create or get read record
        read_record, created = NewsletterRead.objects.get_or_create(
            newsletter=newsletter,
            subscription=subscription
        )

        if created:
            # Increment open count
            newsletter.open_count += 1
            newsletter.save(update_fields=['open_count'])
            message = "Newsletter marked as read."
        else:
            message = "Newsletter was already read."

        return APIResponse.success(
            data={
                'newsletter_id': newsletter.id,
                'read_at': read_record.read_at.isoformat()
            },
            message=message
        )

    @extend_schema(
        summary="List All Subscribers",
        description="List all newsletter subscribers (admin only).",
        responses={200: NewsletterSubscriptionAdminSerializer(many=True)},
        tags=["Newsletter Admin"]
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def subscribers(self, request):
        """List all newsletter subscribers."""
        filter_active = request.query_params.get('active')

        subscribers = NewsletterSubscription.objects.filter(is_deleted=False)

        if filter_active is not None:
            is_active = filter_active.lower() == 'true'
            subscribers = subscribers.filter(is_active=is_active)

        # Ordering
        ordering = request.query_params.get('ordering', '-created_at')
        if ordering.lstrip('-') in ['created_at', 'email', 'is_active']:
            subscribers = subscribers.order_by(ordering)

        page = self.paginate_queryset(subscribers)
        if page is not None:
            serializer = NewsletterSubscriptionAdminSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = NewsletterSubscriptionAdminSerializer(subscribers, many=True)
        return APIResponse.success(
            data=serializer.data,
            message=f"Retrieved {len(serializer.data)} subscribers."
        )


class NewsletterPublicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only access to sent newsletter editions — no authentication required.

    GET /newsletters/public/       → paginated list of sent editions
    GET /newsletters/public/{id}/  → full edition with content_html
    """

    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Newsletter.objects.filter(
            status='sent',
            is_deleted=False
        ).order_by('-sent_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return NewsletterPublicDetailSerializer
        return NewsletterPublicListSerializer
