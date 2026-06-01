import os
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from content.models import Article

count = Article.objects.count()
print(f"Final article count: {count}")
with open('final_count.txt', 'w') as f:
    f.write(str(count))

if count == 0:
    print("SUCCESS: Database is empty.")
else:
    print("FAILED: Database is not empty.")
