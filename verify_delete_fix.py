import os
import django
from django.conf import settings

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from content.models import Article
from content.views import ArticleViewSet
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

User = get_user_model()

def test_delete_article_visibility():
    print("Setting up test...")
    
    # Create a test user with unique data
    import uuid
    uid = str(uuid.uuid4())[:8]
    user, created = User.objects.get_or_create(
        username=f'test_verifier_{uid}', 
        email=f'test_{uid}@example.com'
    )
    if created:
        user.set_password('password')
        user.save()
        
    # Create a test article
    article = Article.objects.create(
        title='Test Article to Delete',
        content='This article should disappear after deletion.',
        author=user,
        status='published'
    )
    print(f"Created article: {article.title} (ID: {article.id})")
    
    # Setup request factory
    factory = APIRequestFactory()
    view = ArticleViewSet.as_view({'get': 'list'})
    
    # 1. Verify article is visible initially
    request = factory.get('/content/articles/')
    force_authenticate(request, user=user)
    response = view(request)
    
    found = any(item['id'] == article.id for item in response.data['results'])
    print(f"Article visible before delete: {found}")
    
    if not found:
        print("FAILED: Article not found initially!")
        return

    # 2. Delete the article (Soft Delete)
    print("Soft deleting article...")
    article.delete()  # This should set is_deleted=True due to SoftDeleteModel
    
    # Verify soft delete happened
    article.refresh_from_db()
    print(f"Article is_deleted: {article.is_deleted}")
    
    # 3. Verify article is GONE from list
    request = factory.get('/content/articles/')
    force_authenticate(request, user=user)
    response = view(request)
    
    found_after = any(item['id'] == article.id for item in response.data['results'])
    print(f"Article visible after delete: {found_after}")
    
    with open('result.txt', 'w') as f:
        if not found_after:
            f.write("SUCCESS: Article is no longer visible in the list.")
            print("SUCCESS: Article is no longer visible in the list.")
        else:
            f.write("FAILED: Article is STILL visible in the list!")
            print("FAILED: Article is STILL visible in the list!")

    # Cleanup (Hard delete to really remove it)
    article.hard_delete()
    print("Test cleanup done.")

if __name__ == "__main__":
    try:
        test_delete_article_visibility()
    except Exception as e:
        print(f"An error occurred: {e}")
