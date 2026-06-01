import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from content.models import Video

count = Video.objects.count()
print(f"Final video count: {count}")

with open('final_video_count.txt', 'w') as f:
    f.write(str(count))
