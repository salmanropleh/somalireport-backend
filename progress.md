# Backend Progress Log

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

### Updated: `content/models.py` — Slug uniqueness for `Article` and `Video`
- Both `Article.save()` and `Video.save()` previously called `StringHelper.slugify(self.title)` and saved it directly, causing `IntegrityError: UNIQUE constraint failed: articles.slug` if two articles shared a title.
- **Fix**: generate `base_slug`, then loop checking `Article.objects.exclude(pk=self.pk).filter(slug=slug).exists()` — appends `-2`, `-3`, etc. until unique.
- Same logic applied to `Video.save()`.
- **Why this matters**: editors may publish follow-up articles under the same headline (e.g. breaking news updates). Without this fix, the second article throws a 500 and is lost.

---
