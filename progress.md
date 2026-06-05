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
