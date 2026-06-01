import os
import django
import uuid

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from content.models import Video
from django.contrib.auth import get_user_model

User = get_user_model()

def create_dummies():
    print("Creating dummy videos...")
    
    # Create a test user
    uid = str(uuid.uuid4())[:8]
    user, created = User.objects.get_or_create(
        username=f'video_delete_tester_{uid}', 
        email=f'video_{uid}@example.com'
    )
    if created:
        user.set_password('password')
        user.save()
        
    # Create 5 videos
    for i in range(5):
        Video.objects.create(
            title=f'Dummy Video {i} {uid}',
            uploaded_by=user,
            status='published'
        )
    
    count = Video.objects.count()
    print(f"Total videos in DB: {count}")

if __name__ == "__main__":
    create_dummies()
