import json
import logging
import os
import urllib.request

logger = logging.getLogger(__name__)

_INDEXING_ENDPOINT = 'https://indexing.googleapis.com/v3/urlNotifications:publish'
_SCOPES = ['https://www.googleapis.com/auth/indexing']


def notify_google(url: str, action: str = 'URL_UPDATED') -> None:
    """Ping the Google Indexing API for a given URL.

    Requires GOOGLE_SA_CREDENTIALS_FILE env var pointing to a service account
    JSON key that has been added as an Owner in Google Search Console.
    Fails silently so article saves are never blocked.
    """
    credentials_path = os.environ.get('GOOGLE_SA_CREDENTIALS_FILE')
    if not credentials_path:
        logger.warning('GOOGLE_SA_CREDENTIALS_FILE not set — skipping Indexing API ping for %s', url)
        return

    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as GoogleRequest

        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=_SCOPES
        )
        creds.refresh(GoogleRequest())

        payload = json.dumps({'url': url, 'type': action}).encode()
        req = urllib.request.Request(
            _INDEXING_ENDPOINT,
            data=payload,
            headers={
                'Authorization': f'Bearer {creds.token}',
                'Content-Type': 'application/json',
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info('Google Indexing API notified: %s → HTTP %s', url, resp.status)

    except Exception as exc:
        logger.error('Google Indexing API failed for %s: %s', url, exc)
