"""
Views for newsletter app.
"""

from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action, api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q
from django.template.loader import render_to_string
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
    ArticlePickerSerializer,
    NewsletterPublicListSerializer,
    NewsletterPublicDetailSerializer,
)
from core.utils import APIResponse
import logging

logger = logging.getLogger(__name__)


class IsAdminUser(permissions.BasePermission):
    """Permission to only allow admin users."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_staff or
            getattr(request.user, 'role', None) == 'admin'
        )


class NewsletterSubscriptionViewSet(viewsets.GenericViewSet):
    """ViewSet for newsletter subscription management."""

    queryset = NewsletterSubscription.objects.filter(is_deleted=False)
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

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
                existing.is_active = True
                existing.unsubscribed_at = None
                existing.unsubscribe_token = NewsletterSubscription.generate_unsubscribe_token()
                existing.save()
                subscription = existing
        else:
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
    """ViewSet for email campaign (newsletter) management."""

    queryset = Newsletter.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'email_type']
    search_fields = ['title', 'subject', 'excerpt']
    ordering_fields = ['created_at', 'sent_at', 'recipient_count', 'open_count']
    ordering = ['-created_at']
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_serializer_class(self):
        if self.action == 'list':
            return NewsletterListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return NewsletterCreateUpdateSerializer
        elif self.action == 'send':
            return NewsletterSendSerializer
        return NewsletterDetailSerializer

    def get_permissions(self):
        if self.action in ['my_newsletters', 'mark_read']:
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['list', 'retrieve']:
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
        queryset = Newsletter.objects.filter(is_deleted=False)

        if self.request.user.is_authenticated and (
            self.request.user.is_staff or
            getattr(self.request.user, 'role', None) == 'admin'
        ):
            return queryset

        return queryset.filter(status='sent')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.hard_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Search Articles for Campaign Picker",
        description="Search published articles for use in newsletter article picker (admin only).",
        tags=["Newsletter Admin"]
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser], url_path='article-picker')
    def article_picker(self, request):
        """Search published articles for the campaign composer."""
        from content.models import Article

        search = request.query_params.get('search', '').strip()
        queryset = Article.objects.filter(
            status='published',
            is_deleted=False
        ).order_by('-published_at')

        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(excerpt__icontains=search)
            )

        queryset = queryset[:50]
        serializer = ArticlePickerSerializer(queryset, many=True, context={'request': request})
        return APIResponse.success(
            data=serializer.data,
            message=f"Found {len(serializer.data)} articles."
        )

    @extend_schema(
        summary="Preview Email Campaign",
        description="Returns the rendered HTML preview for the campaign (admin only).",
        tags=["Newsletter Admin"]
    )
    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser])
    def preview(self, request, pk=None):
        """Return rendered HTML preview of the campaign email."""
        from django.conf import settings as django_settings
        from .tasks import build_combined_content
        from django.utils import timezone

        newsletter = self.get_object()
        frontend_url = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:3000')
        social_links = getattr(django_settings, 'SOCIAL_LINKS', {})

        articles = []
        if newsletter.email_type == 'newsletter':
            articles = list(newsletter.articles.filter(status='published'))
            if newsletter.article_order:
                order_map = {aid: idx for idx, aid in enumerate(newsletter.article_order)}
                articles.sort(key=lambda a: order_map.get(a.id, 9999))

        combined_content = build_combined_content(articles, newsletter.text_blocks) if newsletter.email_type == 'newsletter' else []

        context = {
            'newsletter': newsletter,
            'articles': articles,
            'combined_content': combined_content,
            'frontend_url': frontend_url,
            'unsubscribe_url': f"{frontend_url}/unsubscribe?token=PREVIEW_TOKEN",
            'recipient_email': request.user.email,
            'social_links': social_links,
            'send_date': timezone.now().strftime('%B %-d, %Y'),
            'send_time': timezone.now().strftime('%I:%M %p UTC'),
            'is_preview': True,
            'is_test': False,
        }

        if newsletter.email_type == 'newsletter':
            template_name = 'email/newsletter_template.html'
        else:
            template_name = 'email/direct_email_template.html'

        try:
            html = render_to_string(template_name, context, request=request)
            # Inject responsive overrides so the fixed-600px email layout fits
            # the preview iframe without horizontal scroll. This CSS is only
            # added for browser preview and never reaches email clients.
            preview_css = (
                '<style>'
                'table[width="600"]{width:100%!important;}'
                'body{overflow-x:hidden!important;}'
                'img{max-width:100%!important;height:auto!important;}'
                '.email-body *{max-width:100%!important;word-break:break-word;}'
                '</style>'
            )
            html = html.replace('</head>', preview_css + '</head>', 1)
            return APIResponse.success(
                data={'html': html},
                message="Preview generated successfully."
            )
        except Exception as e:
            logger.error(f"Preview render failed: {e}")
            return APIResponse.error(
                message=f"Failed to render preview: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @extend_schema(
        summary="Send Email Campaign",
        description="Send the campaign to recipients. Optionally send a test email first.",
        request=NewsletterSendSerializer,
        responses={200: {"description": "Campaign sent successfully"}},
        tags=["Newsletter Admin"]
    )
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def send(self, request, pk=None):
        """Send campaign to recipients or a test email."""
        newsletter = self.get_object()

        if newsletter.status == 'sent':
            return APIResponse.error(
                message="This campaign has already been sent.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        serializer = NewsletterSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test_email = serializer.validated_data.get('test_email')

        if test_email:
            from .tasks import send_test_newsletter_task
            try:
                send_test_newsletter_task(newsletter.id, test_email)
                return APIResponse.success(
                    message=f"Test campaign sent to {test_email}."
                )
            except Exception as e:
                logger.error(f"Failed to send test campaign: {e}")
                return APIResponse.error(
                    message=f"Failed to send test campaign: {str(e)}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            from .tasks import send_newsletter_task
            try:
                recipient_count = self._estimate_recipient_count(newsletter)

                if recipient_count == 0:
                    return APIResponse.error(
                        message="No recipients found for this campaign.",
                        status_code=status.HTTP_400_BAD_REQUEST
                    )

                send_newsletter_task(newsletter.id)

                newsletter.status = 'sent'
                newsletter.sent_at = timezone.now()
                newsletter.recipient_count = recipient_count
                newsletter.save(update_fields=['status', 'sent_at', 'recipient_count'])

                return APIResponse.success(
                    data={
                        'newsletter_id': newsletter.id,
                        'recipient_count': recipient_count,
                        'sent_at': newsletter.sent_at.isoformat()
                    },
                    message=f"Campaign sent to {recipient_count} recipients."
                )
            except Exception as e:
                logger.error(f"Failed to send campaign: {e}")
                return APIResponse.error(
                    message=f"Failed to send campaign: {str(e)}",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

    def _estimate_recipient_count(self, newsletter):
        """Estimate recipient count based on recipients_type."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if newsletter.recipients_type == 'subscribers':
            return NewsletterSubscription.objects.filter(
                is_active=True,
                is_deleted=False
            ).count()
        elif newsletter.recipients_type == 'all_users':
            return User.objects.filter(is_active=True).count()
        elif newsletter.recipients_type == 'custom':
            emails = [e.strip() for e in newsletter.custom_recipients.split(',') if e.strip()]
            return len(emails)
        return 0

    @extend_schema(
        summary="Get My Newsletters",
        description="Get newsletters for the current subscribed user.",
        responses={200: NewsletterListSerializer(many=True)},
        tags=["Newsletter User"]
    )
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_newsletters(self, request):
        """Get newsletters for the authenticated user."""
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

        read_record, created = NewsletterRead.objects.get_or_create(
            newsletter=newsletter,
            subscription=subscription
        )

        if created:
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

    @extend_schema(
        summary="Delete a Subscriber",
        description="Permanently delete a newsletter subscriber record (admin only).",
        tags=["Newsletter Admin"]
    )
    @action(detail=False, methods=['delete'], permission_classes=[IsAdminUser],
            url_path='subscribers/(?P<subscriber_id>[0-9]+)')
    def delete_subscriber(self, request, subscriber_id=None):
        """Hard-delete a single subscriber by id."""
        try:
            sub = NewsletterSubscription.objects.get(id=subscriber_id, is_deleted=False)
        except NewsletterSubscription.DoesNotExist:
            return APIResponse.error(message="Subscriber not found.", status_code=status.HTTP_404_NOT_FOUND)
        sub.delete()
        return APIResponse.success(message="Subscriber deleted.")

    @extend_schema(
        summary="Import Subscribers from CSV",
        description="Upload a CSV file with an 'email' column to bulk-import subscribers (admin only).",
        tags=["Newsletter Admin"]
    )
    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser],
            url_path='subscribers/import', parser_classes=[MultiPartParser, FormParser])
    def import_subscribers(self, request):
        """Import subscribers from an uploaded CSV file."""
        import csv
        import io

        file = request.FILES.get('file')
        if not file:
            return APIResponse.error(message="No file uploaded.", status_code=status.HTTP_400_BAD_REQUEST)

        if not file.name.endswith('.csv'):
            return APIResponse.error(message="File must be a .csv", status_code=status.HTTP_400_BAD_REQUEST)

        try:
            decoded = file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))
        except Exception as e:
            return APIResponse.error(message=f"Could not read file: {e}", status_code=status.HTTP_400_BAD_REQUEST)

        # Accept 'email', 'Email', 'EMAIL' column
        fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]
        if 'email' not in fieldnames:
            return APIResponse.error(
                message="CSV must have an 'email' column.",
                status_code=status.HTTP_400_BAD_REQUEST
            )

        created = skipped = errors = 0
        for row in reader:
            # Normalise key lookup
            email_val = None
            for k, v in row.items():
                if k.strip().lower() == 'email':
                    email_val = v
                    break
            if not email_val:
                continue
            email = email_val.strip().lower()
            if not email or '@' not in email:
                errors += 1
                continue
            existing = NewsletterSubscription.objects.filter(email=email, is_deleted=False).first()
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    existing.unsubscribed_at = None
                    existing.unsubscribe_token = NewsletterSubscription.generate_unsubscribe_token()
                    existing.save()
                    created += 1
                else:
                    skipped += 1
            else:
                NewsletterSubscription.objects.create(email=email)
                created += 1

        return APIResponse.success(
            data={'created': created, 'skipped': skipped, 'errors': errors},
            message=f"Import complete: {created} added, {skipped} already subscribed, {errors} invalid.",
            status_code=status.HTTP_201_CREATED
        )


# ---------------------------------------------------------------------------
# Standalone public views — bypass the ViewSet router entirely so the
# subscription endpoint is reachable without authentication.
# ---------------------------------------------------------------------------

@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def public_subscribe(request):
    """Public endpoint: subscribe an email to the newsletter."""
    from .serializers import NewsletterSubscribeSerializer, NewsletterSubscriptionSerializer

    serializer = NewsletterSubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email'].lower().strip()

    existing = NewsletterSubscription.objects.filter(email=email, is_deleted=False).first()
    if existing:
        if existing.is_active:
            return APIResponse.error(
                message="This email is already subscribed.",
                status_code=status.HTTP_400_BAD_REQUEST
            )
        existing.is_active = True
        existing.unsubscribed_at = None
        existing.unsubscribe_token = NewsletterSubscription.generate_unsubscribe_token()
        existing.save()
        subscription = existing
    else:
        subscription = NewsletterSubscription.objects.create(
            email=email,
            user=request.user if request.user.is_authenticated else None,
        )

    return APIResponse.success(
        data=NewsletterSubscriptionSerializer(subscription).data,
        message="Successfully subscribed to the newsletter.",
        status_code=status.HTTP_201_CREATED
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def public_unsubscribe(request):
    """Public endpoint: unsubscribe via token."""
    from .serializers import NewsletterUnsubscribeSerializer

    serializer = NewsletterUnsubscribeSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    token = serializer.validated_data['token']

    subscription = NewsletterSubscription.objects.filter(
        unsubscribe_token=token, is_active=True, is_deleted=False
    ).first()

    if not subscription:
        return APIResponse.error(
            message="Invalid or expired unsubscribe token.",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    subscription.is_active = False
    subscription.unsubscribed_at = timezone.now()
    subscription.save()

    return APIResponse.success(message="Successfully unsubscribed from the newsletter.")


class NewsletterPublicViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only access to sent newsletter editions — no authentication required.

    GET /newsletters/public/       → paginated list of sent editions
    GET /newsletters/public/{id}/  → full edition with content_html
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get_queryset(self):
        return Newsletter.objects.filter(
            status='sent',
            email_type='newsletter',
            is_deleted=False
        ).order_by('-sent_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return NewsletterPublicDetailSerializer
        return NewsletterPublicListSerializer
