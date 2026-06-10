# Backend Progress Log

---

## 2026-06-10 — Restore Features Lost in Merge

Another developer merged a new branch (Google Indexing API, sitemap, newsletter) via `4fcea1e`. The merge restored `AuthorViewSet` and `prerender_article` but dropped three of our previous features from `content/views.py` and `content/serializers.py`.

### Lost and Restored: `author_username` (`content/serializers.py`)
- `author_username = serializers.SerializerMethodField()` and `get_author_username()` were missing from both `ArticleListSerializer` and `ArticleDetailSerializer`
- **Impact**: Frontend author profile links were completely broken — the link condition `!show_manual_author && author_username` was always false because the API returned `null`, so author names rendered as plain unclickable text instead of links to `/author/:username`
- **Fix**: Restored field declaration, `'author_username'` in Meta fields, and `get_author_username()` method in both serializers

### Lost and Restored: `/articles/drafts/` endpoint (`content/views.py`)
- The entire `drafts` action was missing from `ArticleViewSet`
- **Impact**: Draft tab in admin showed no articles
- **Fix**: Restored full `drafts` action — authenticated admins/editors see all drafts, reporters see only their own, unauthenticated returns 401

### Lost and Restored: Prerender fixes (`content/views.py`)
- `prerender_article` was restored by the other dev but in an older broken form:
  - `BACKEND_URL = 'https://salmanr.pythonanywhere.com'` was gone — reverted to `request.build_absolute_uri()` which builds image URLs pointing to `somalireport.com` (no `/media/` route there), breaking Twitter/WhatsApp image previews
  - `twitter:title` and `twitter:description` meta tags were missing
- **Fix**: Restored `BACKEND_URL`, hardcoded image URL construction, and both twitter meta tags

### New from other developer (untouched)
- Google Indexing API (`content/indexing.py`, `content/signals.py`) — auto-submits published articles to Google
- Sitemap (`content/sitemaps.py`) — dynamic sitemap via Django
- `robots.txt` template
- Newsletter app (full new Django app)
- `published_at` auto-set on status transition to published
- New migrations (0006–0012)

---

## 2026-06-09 — WSGI Crash Fix: `delay=True` on FileHandler

### Incident
The backend was completely down from approximately 09:54 to 12:52 (UTC+3). Every incoming request triggered a new WSGI worker, which immediately crashed with:
```
ValueError: Unable to configure handler 'file'
```
This meant Django couldn't start at all — no requests were served during this window.

### Root Cause
PythonAnywhere hosts home directories on NFS (network filesystem). Starting around 07:48, the NFS had a transient write failure (`OSError: write error` visible in `django.log`). Around 09:54, PythonAnywhere's automatic WSGI worker recycling kicked in and tried to start a new worker. Django's startup calls `dictConfig()` on the `LOGGING` setting, which immediately tries to open `django.log` via `logging.FileHandler`. With NFS still flaky, this open failed — wrapped and re-raised as `ValueError: Unable to configure handler 'file'`. Every subsequent worker recycle produced the same crash loop until NFS recovered at ~12:52.

No deployment was made on June 9. The crash was triggered purely by routine worker recycling during an NFS hiccup.

### Fix: `config/settings/base.py`
Added `'delay': True` to the `'file'` logging handler:
```python
'file': {
    'class': 'logging.FileHandler',
    'filename': BASE_DIR / 'logs' / 'django.log',
    'formatter': 'verbose',
    'delay': True,  # <-- this line
},
```
`delay=True` defers file opening until the first log record is written, instead of at handler creation time (during `dictConfig()`). A transient NFS failure at worker startup can no longer crash the app — Django starts successfully and degrades gracefully if the first write later fails.

### Other findings
- `django.db.utils.OperationalError: database is locked` visible in the log before the crash — SQLite lock contention from multiple WSGI workers. Not the cause of this outage but worth monitoring.
- Disk space is not an issue: 1.3 TB free on the NFS volume.

---

## 2026-06-05 — Author Profile Endpoint

### New: `AuthorViewSet` (`accounts/views.py`)
Added a public ViewSet with two actions:

- `GET /api/v1/authors/` — returns all users who have at least one published article
- `GET /api/v1/authors/{id_or_username}/` — returns author profile + paginated published articles (10/page)

Lookup supports both integer ID and username string (e.g. `/authors/1/` or `/authors/MikeManyibe/`).

Response shape:
```json
{
  "author": { "id", "full_name", "username", "bio", "avatar", "role", "date_joined" },
  "stats": { "article_count" },
  "articles": { "count", "next", "previous", "results": [...] }
}
```

### New: `AuthorPublicSerializer` (`accounts/serializers.py`)
Serializer exposing safe public fields: `id`, `full_name`, `username`, `bio`, `avatar`, `role`, `date_joined`.

### Updated: `accounts/urls.py`
Registered `AuthorViewSet` on the `authors` router prefix.

### Updated: `content/serializers.py`
Added `author_username` field to both `ArticleListSerializer` and `ArticleDetailSerializer`.
Returns the linked author's username, or `null` for manual/anonymous authors.
Used by the frontend to build clean author profile URLs (`/author/username`).

### Updated: `accounts/views.py` — Username lookup
`AuthorViewSet.retrieve()` now supports both integer ID and username string lookup:
- `/authors/1/` — lookup by ID
- `/authors/MikeManyibe/` — lookup by username

---

## 2026-06-06 — Social Share Prerender Fix

### Updated: `content/views.py` — `prerender_article`
- Removed `<meta http-equiv="refresh" content="0; url=..."/>` from the prerender HTML
  - **Why**: WhatsApp and Twitter bots were following the redirect to `somalireport.com/article/...` (the React SPA), which has no OG tags at render time. Both platforms showed only the domain name with no image or title.
  - **To revert**: add back `parts.append(f'<meta http-equiv="refresh" content="0; url={article_url}"/>')`
- Added explicit `twitter:title` and `twitter:description` meta tags
  - Previously only `twitter:card` and `twitter:image` were present; Twitter was falling back to `og:` tags inconsistently

### Nginx Fix Pending (Digital Ocean Droplet)
The droplet's nginx proxies bot prerender requests to `localhost:8000` but no Django process runs there. Until fixed, WhatsApp previews will not show images/title. Fix: update `/etc/nginx/sites-available/somalireport`:

**Current (broken):**
```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Replace with:**
```nginx
location /api/ {
    proxy_pass https://salmanr.pythonanywhere.com;
    proxy_set_header Host salmanr.pythonanywhere.com;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_ssl_server_name on;
}
```
Then: `nginx -t && systemctl reload nginx`

---

## 2026-06-07 — OG Image URL Fix + Slug Uniqueness

### Updated: `content/views.py` — `prerender_article` image URL
- Changed `request.build_absolute_uri(article.featured_image.url)` → `f'{BACKEND_URL}{article.featured_image.url}'`
  - **Why**: `request.build_absolute_uri()` was using the incoming request host (`somalireport.com`) to build the image URL. When Twitter/WhatsApp bots fetched `og:image` at `https://somalireport.com/media/uploads/...`, the droplet nginx has no `/media/` route and returned the SPA instead of the image — Twitter showed a newspaper icon, WhatsApp showed only the domain.
  - **Fix**: hardcode `BACKEND_URL = 'https://salmanr.pythonanywhere.com'` so the image URL always points directly to PythonAnywhere where media files are served.
  - Confirmed working: Twitter card shows full article image; WhatsApp cached URLs (previously shared before the fix) expire naturally in 1–3 days.

### New: `GET /articles/drafts/` endpoint (`content/views.py`)
- Added `drafts` action to `ArticleViewSet`, mirroring the existing `archived` pattern
- Authenticated admins/editors see all draft articles; reporters see only their own; unauthenticated requests return 401
- Supports `ordering` and pagination query params
- **Why**: the generic `/articles/?status=draft` route was having its auth token stripped by the frontend's `isPublicEndpoint()` check, so the backend always saw an anonymous user and returned empty results for the Draft tab

---

### Updated: `content/models.py` — Slug uniqueness for `Article` and `Video`
- Both `Article.save()` and `Video.save()` previously called `StringHelper.slugify(self.title)` and saved it directly, causing `IntegrityError: UNIQUE constraint failed: articles.slug` if two articles shared a title.
- **Fix**: generate `base_slug`, then loop checking `Article.objects.exclude(pk=self.pk).filter(slug=slug).exists()` — appends `-2`, `-3`, etc. until unique.
- Same logic applied to `Video.save()`.
- **Why this matters**: editors may publish follow-up articles under the same headline (e.g. breaking news updates). Without this fix, the second article throws a 500 and is lost.

---
