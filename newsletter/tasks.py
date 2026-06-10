"""
Celery tasks for newsletter app.
"""

from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)


def send_newsletter_email(subscription, newsletter, base_url=None):
    """
    Helper function to send a newsletter email to a single subscriber.

    Args:
        subscription: NewsletterSubscription instance
        newsletter: Newsletter instance
        base_url: Optional base URL for building unsubscribe links
    """
    try:
        # Build unsubscribe URL
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        unsubscribe_url = f"{frontend_url}/unsubscribe?token={subscription.unsubscribe_token}"

        # Prepare email content with unsubscribe link
        html_content = f"""
        {newsletter.content_html}
        <br><br>
        <hr>
        <p style="color: #666; font-size: 12px;">
            You are receiving this email because you subscribed to our newsletter.
            <a href="{unsubscribe_url}">Unsubscribe</a>
        </p>
        """

        text_content = f"""
        {newsletter.content_text}

        ---
        You are receiving this email because you subscribed to our newsletter.
        To unsubscribe, visit: {unsubscribe_url}
        """

        # Create email message
        email = EmailMultiAlternatives(
            subject=newsletter.subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[subscription.email]
        )
        email.attach_alternative(html_content, "text/html")

        # Send email
        email.send(fail_silently=False)

        logger.info(f"Newsletter '{newsletter.title}' sent to {subscription.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send newsletter to {subscription.email}: {e}")
        return False


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_newsletter_task(self, newsletter_id):
    """
    Celery task to send newsletter to all active subscribers.

    Args:
        newsletter_id: ID of the Newsletter to send
    """
    from .models import Newsletter, NewsletterSubscription

    try:
        newsletter = Newsletter.objects.get(id=newsletter_id)
    except Newsletter.DoesNotExist:
        logger.error(f"Newsletter with ID {newsletter_id} not found")
        return {'status': 'error', 'message': 'Newsletter not found'}

    # Get all active subscribers
    subscribers = NewsletterSubscription.objects.filter(
        is_active=True,
        is_deleted=False
    )

    total = subscribers.count()
    sent = 0
    failed = 0

    logger.info(f"Starting to send newsletter '{newsletter.title}' to {total} subscribers")

    for subscription in subscribers:
        success = send_newsletter_email(subscription, newsletter)
        if success:
            sent += 1
        else:
            failed += 1

    # Update newsletter stats
    newsletter.recipient_count = sent
    newsletter.save(update_fields=['recipient_count'])

    result = {
        'status': 'completed',
        'newsletter_id': newsletter_id,
        'total_subscribers': total,
        'sent': sent,
        'failed': failed
    }

    logger.info(f"Newsletter sending completed: {result}")
    return result


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_test_newsletter_task(self, newsletter_id, test_email):
    """
    Celery task to send a test newsletter to a single email.

    Args:
        newsletter_id: ID of the Newsletter to send
        test_email: Email address to send the test to
    """
    from .models import Newsletter

    try:
        newsletter = Newsletter.objects.get(id=newsletter_id)
    except Newsletter.DoesNotExist:
        logger.error(f"Newsletter with ID {newsletter_id} not found")
        return {'status': 'error', 'message': 'Newsletter not found'}

    try:
        # Build test email content
        html_content = f"""
        <div style="background: #fff3cd; padding: 10px; margin-bottom: 20px; border: 1px solid #ffc107; border-radius: 5px;">
            <strong>TEST EMAIL</strong> - This is a test of the newsletter. It was not sent to subscribers.
        </div>
        {newsletter.content_html}
        <br><br>
        <hr>
        <p style="color: #666; font-size: 12px;">
            You are receiving this test email because you requested it.
            [Unsubscribe link would appear here for real subscribers]
        </p>
        """

        text_content = f"""
        *** TEST EMAIL ***
        This is a test of the newsletter. It was not sent to subscribers.

        ---

        {newsletter.content_text}

        ---
        You are receiving this test email because you requested it.
        [Unsubscribe link would appear here for real subscribers]
        """

        # Create and send email
        email = EmailMultiAlternatives(
            subject=f"[TEST] {newsletter.subject}",
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[test_email]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        logger.info(f"Test newsletter '{newsletter.title}' sent to {test_email}")
        return {
            'status': 'success',
            'newsletter_id': newsletter_id,
            'test_email': test_email
        }

    except Exception as e:
        logger.error(f"Failed to send test newsletter to {test_email}: {e}")
        raise self.retry(exc=e)
