import os
import django
import uuid

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from content.models import Article
from django.contrib.auth import get_user_model

User = get_user_model()

def create_dummies():
    print("Creating dummy articles...")
    
    # Create a test user
    uid = str(uuid.uuid4())[:8]
    user, created = User.objects.get_or_create(
        username=f'bulk_delete_tester_{uid}', 
        email=f'bulk_{uid}@example.com'
    )
    if created:
        user.set_password('password')
        user.save()
        
    # Create 5 articles
    for i in range(5):
        Article.objects.create(
            title=f'Dummy Article {i} {uid}',
            content='Delete me.',
            author=user,
            status='published'
        )
    
    count = Article.objects.count()
    print(f"Total articles in DB: {count}")

if __name__ == "__main__":
    create_dummies()
