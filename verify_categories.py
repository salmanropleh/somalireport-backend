import os
import django
from django.conf import settings

import sys
sys.path.append(os.getcwd())
# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from content.models import Category
from rest_framework.test import APIRequestFactory
from content.views import CategoryViewSet
from content.serializers import CategorySerializer

def verify_inactive_categories():
    print("Verifying inactive categories are returned...")
    
    # Create an inactive category
    category_name = "Test Inactive Category"
    category_slug = "test-inactive-category"
    
    # Clean up if exists
    Category.objects.filter(slug=category_slug).delete()
    
    category = Category.objects.create(
        name=category_name,
        slug=category_slug,
        is_active=False,
        is_deleted=False
    )
    print(f"Created inactive category: {category.name} (is_active={category.is_active})")
    
    try:
        # Simulate request
        factory = APIRequestFactory()
        request = factory.get('/api/content/categories/')
        view = CategoryViewSet.as_view({'get': 'list'})
        
        response = view(request)
        
        if response.status_code == 200:
            data = response.data
            # Pagination handling
            if 'results' in data:
                categories = data['results']
            elif 'data' in data and 'results' in data['data']: # APIResponse structure
                categories = data['data']['results']
            elif 'data' in data and isinstance(data['data'], list): # APIResponse structure list
                 categories = data['data']
            else:
                categories = data

            found = False
            for cat in categories:
                if cat['slug'] == category_slug:
                    found = True
                    break
            
            if found:
                print("SUCCESS: Inactive category was found in the response.")
            else:
                print("FAILURE: Inactive category was NOT found in the response.")
                print("Categories returned:", [c['name'] for c in categories])
                
        else:
            print(f"FAILURE: API returned status code {response.status_code}")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
    finally:
        # Cleanup
        category.hard_delete()
        print("Cleaned up test category.")

if __name__ == "__main__":
    verify_inactive_categories()
