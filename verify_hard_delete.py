import os
import django
import uuid

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from content.models import Article
from content.views import ArticleViewSet
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

User = get_user_model()

def test_hard_delete_article():
    print("Setting up hard delete test...")
    
    # Create a test user with unique data
    uid = str(uuid.uuid4())[:8]
    user, created = User.objects.get_or_create(
        username=f'test_verifier_{uid}', 
        email=f'test_{uid}@example.com'
    )
    if created:
        user.set_password('password')
        user.role = 'reporter'  # Must be reporter to delete
        user.save()
        
    # Create a test article
    article = Article.objects.create(
        title=f'Test Hard Delete Article {uid}',
        content='This article should be permanently deleted.',
        author=user,
        status='published'
    )
    article_id = article.id
    print(f"Created article: {article.title} (ID: {article.id})")
    
    # Setup request factory
    factory = APIRequestFactory()
    view = ArticleViewSet.as_view({'delete': 'destroy'})
    
    # Send DELETE request
    print("Performing HARD delete...")
    request = factory.delete(f'/content/articles/{article_id}/')
    force_authenticate(request, user=user)
    response = view(request, pk=article_id)
    print(f"Delete response status: {response.status_code}")
    
    # Verify article is completely gone from DB
    # We query objects.all() directly, which might still show soft-deleted items if standard manager was used,
    # but we will check specific flags or existence.
    # Actually, we should check if the record exists AT ALL in the raw table or simplified query.
    # Since SoftDeleteModel is used, standard .objects.get() might filter it out if is_deleted=True,
    # so we should check specifically for the ID via a raw check or simple filter.
    
    print("Verifying persistence...")
    try:
        # Try to find it even if deleted
        # Note: If hard delete worked, this should throw DoesNotExist even if we try to bypass managers
        # or it should be gone.
        
        # Check using a fresh filtered query that explicitly looks for ID
        # If it was soft deleted, it would still exist but have is_deleted=True.
        # If hard deleted, it should not exist.
        
        # Let's use a lower level check or just try to get it
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM articles WHERE id = %s", [article_id])
            count = cursor.fetchone()[0]
        
        with open('result_hard_delete.txt', 'w') as f:
            if count == 0:
                msg = "SUCCESS: Article record is completely GONE from database."
                f.write(msg)
                print(msg)
            else:
                # If it exists, check if it's soft deleted just to be sure what happened
                article_check = Article.objects.filter(id=article_id).first()
                if article_check:
                    msg = f"FAILED: Article still exists in DB! is_deleted={article_check.is_deleted}"
                else:
                    # If ORM can't find it but SQL can, it's soft deleted (if manager filters)
                    # But we want it hard deleted.
                    msg = "FAILED: Article still exists in DB (likely soft deleted)."
                f.write(msg)
                print(msg)

    except Exception as e:
        print(f"Error during verification: {e}")

if __name__ == "__main__":
    test_hard_delete_article()
