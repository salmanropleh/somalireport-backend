"""
Celery tasks for newsletter app.
"""

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def _get_recipients(newsletter):
    """
    Return list of (email, unsubscribe_token_or_None) tuples based on recipients_type.
    """
    from django.contrib.auth import get_user_model
    from .models import NewsletterSubscription

    User = get_user_model()

    if newsletter.recipients_type == 'subscribers':
        subs = NewsletterSubscription.objects.filter(is_active=True, is_deleted=False)
        return [(s.email, s.unsubscribe_token) for s in subs]

    elif newsletter.recipients_type == 'all_users':
        users = User.objects.filter(is_active=True).values_list('email', flat=True)
        return [(email, None) for email in users if email]

    elif newsletter.recipients_type == 'custom':
        emails = [e.strip() for e in newsletter.custom_recipients.split(',') if e.strip()]
        return [(email, None) for email in emails]

    return []


def _get_ordered_articles(newsletter):
    """Return newsletter articles in admin-specified order."""
    articles = list(newsletter.articles.filter(status='published'))
    if newsletter.article_order:
        order_map = {aid: idx for idx, aid in enumerate(newsletter.article_order)}
        articles.sort(key=lambda a: order_map.get(a.id, 9999))
    return articles


def _text_to_html(text):
    """Convert plain text with blank-line paragraph breaks into inline-styled HTML paragraphs."""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    parts = []
    for i, para in enumerate(paragraphs):
        margin = '0 0 14px 0' if i < len(paragraphs) - 1 else '0'
        para = para.replace('\n', '<br>')
        parts.append(f'<p style="margin:{margin};font-family:Georgia,\'Times New Roman\',serif;font-size:15px;line-height:1.8;color:#333333;">{para}</p>')
    return ''.join(parts)


def build_combined_content(articles, text_blocks):
    """
    Merge articles and text blocks into an ordered list for template rendering.
    Text block position: 0 = before all articles, N = after Nth article.
    """
    blocks_by_pos = {}
    for block in (text_blocks or []):
        pos = block.get('position', 9999)
        blocks_by_pos.setdefault(pos, []).append(block)

    def make_text_block(tb):
        data = dict(tb)
        data['content_html'] = _text_to_html(tb.get('content', ''))
        return {'type': 'text_block', 'data': data}

    combined = []
    for tb in blocks_by_pos.get(0, []):
        combined.append(make_text_block(tb))

    for i, article in enumerate(articles):
        combined.append({'type': 'article', 'data': article})
        for tb in blocks_by_pos.get(i + 1, []):
            combined.append(make_text_block(tb))

    for pos in sorted(blocks_by_pos):
        if pos > len(articles):
            for tb in blocks_by_pos[pos]:
                combined.append(make_text_block(tb))

    return combined


def send_campaign_email(email_address, newsletter, unsubscribe_token=None, is_test=False):
    """
    Send a single campaign email (newsletter or direct) to one address.
    """
    try:
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        social_links = getattr(settings, 'SOCIAL_LINKS', {})

        if unsubscribe_token:
            unsubscribe_url = f"{frontend_url}/unsubscribe?token={unsubscribe_token}"
        else:
            unsubscribe_url = f"{frontend_url}/unsubscribe"

        articles = _get_ordered_articles(newsletter) if newsletter.email_type == 'newsletter' else []
        combined_content = build_combined_content(articles, newsletter.text_blocks) if newsletter.email_type == 'newsletter' else []

        context = {
            'newsletter': newsletter,
            'articles': articles,
            'combined_content': combined_content,
            'frontend_url': frontend_url,
            'unsubscribe_url': unsubscribe_url,
            'recipient_email': email_address,
            'social_links': social_links,
            'send_date': timezone.now().strftime('%B %-d, %Y'),
            'send_time': timezone.now().strftime('%I:%M %p UTC'),
            'is_preview': False,
            'is_test': is_test,
        }

        if newsletter.email_type == 'newsletter':
            template_html = 'email/newsletter_template.html'
            template_txt = 'email/newsletter_template_text.html'
        else:
            template_html = 'email/direct_email_template.html'
            template_txt = 'email/direct_email_template_text.html'

        html_content = render_to_string(template_html, context)
        text_content = render_to_string(template_txt, context)

        subject = f"[TEST] {newsletter.subject}" if is_test else newsletter.subject
        from_email = f"Somali Report <{settings.EMAIL_HOST_USER}>" if settings.EMAIL_HOST_USER else settings.DEFAULT_FROM_EMAIL

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[email_address]
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        logger.info(f"Campaign '{newsletter.title}' sent to {email_address}")
        return True

    except Exception as e:
        logger.error(f"Failed to send campaign to {email_address}: {e}")
        return False


# Keep old name as alias so existing call-sites don't break
def send_newsletter_email(subscription, newsletter, base_url=None):
    """Legacy helper — wraps send_campaign_email for subscriber objects."""
    return send_campaign_email(
        subscription.email,
        newsletter,
        unsubscribe_token=subscription.unsubscribe_token
    )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_newsletter_task(self, newsletter_id):
    """
    Celery task to send an email campaign to all configured recipients.
    """
    from .models import Newsletter

    try:
        newsletter = Newsletter.objects.get(id=newsletter_id)
    except Newsletter.DoesNotExist:
        logger.error(f"Newsletter with ID {newsletter_id} not found")
        return {'status': 'error', 'message': 'Newsletter not found'}

    recipients = _get_recipients(newsletter)
    total = len(recipients)
    sent = 0
    failed = 0

    # Save the rendered HTML to content_html so the web archive reader can display it
    if newsletter.email_type == 'newsletter':
        from django.template.loader import render_to_string
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
        social_links = getattr(settings, 'SOCIAL_LINKS', {})
        articles = _get_ordered_articles(newsletter)
        combined_content = build_combined_content(articles, newsletter.text_blocks)
        context = {
            'newsletter': newsletter,
            'articles': articles,
            'combined_content': combined_content,
            'frontend_url': frontend_url,
            'unsubscribe_url': f"{frontend_url}/unsubscribe",
            'recipient_email': '',
            'social_links': social_links,
            'send_date': timezone.now().strftime('%B %-d, %Y'),
            'send_time': timezone.now().strftime('%I:%M %p UTC'),
            'is_preview': False,
            'is_test': False,
        }
        newsletter.content_html = render_to_string('email/newsletter_template.html', context)
        newsletter.save(update_fields=['content_html'])

    logger.info(f"Sending campaign '{newsletter.title}' to {total} recipients")

    for email_address, token in recipients:
        success = send_campaign_email(email_address, newsletter, unsubscribe_token=token)
        if success:
            sent += 1
        else:
            failed += 1

    newsletter.recipient_count = sent
    newsletter.save(update_fields=['recipient_count'])

    result = {
        'status': 'completed',
        'newsletter_id': newsletter_id,
        'total': total,
        'sent': sent,
        'failed': failed,
    }
    logger.info(f"Campaign sending completed: {result}")
    return result


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_test_newsletter_task(self, newsletter_id, test_email):
    """
    Celery task to send a test campaign to a single email address.
    """
    from .models import Newsletter

    try:
        newsletter = Newsletter.objects.get(id=newsletter_id)
    except Newsletter.DoesNotExist:
        logger.error(f"Newsletter with ID {newsletter_id} not found")
        return {'status': 'error', 'message': 'Newsletter not found'}

    try:
        send_campaign_email(test_email, newsletter, unsubscribe_token=None, is_test=True)
        logger.info(f"Test campaign '{newsletter.title}' sent to {test_email}")
        return {'status': 'success', 'newsletter_id': newsletter_id, 'test_email': test_email}
    except Exception as e:
        logger.error(f"Failed to send test campaign to {test_email}: {e}")
        raise self.retry(exc=e)
