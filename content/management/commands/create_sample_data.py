"""
Django management command to create sample categories and tags.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from content.models import Category, Tag
from core.utils import StringHelper


class Command(BaseCommand):
    help = 'Create sample categories and tags for the Somali Report platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing categories and tags before creating new ones',
        )

    def handle(self, *args, **options):
        """Execute the command."""
        if options['clear']:
            self.stdout.write('Clearing existing categories and tags...')
            Category.objects.all().delete()
            Tag.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS('Successfully cleared existing data')
            )

        with transaction.atomic():
            # Create categories
            categories = self.create_categories()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {len(categories)} categories')
            )

            # Create tags
            tags = self.create_tags()
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created {len(tags)} tags')
            )

        self.stdout.write(
            self.style.SUCCESS('\nSample data creation completed successfully!')
        )

    def create_categories(self):
        """Create sample categories."""
        categories_data = [
            {
                'name': 'Breaking News',
                'description': 'Latest breaking news and urgent updates from Somalia and around the world',
                'color': '#dc3545',  # Red for urgency
                'icon': 'fas fa-bolt',
                'sort_order': 1
            },
            {
                'name': 'Business News',
                'description': 'Business updates, economic news, and financial developments in Somalia',
                'color': '#28a745',  # Green for business
                'icon': 'fas fa-chart-line',
                'sort_order': 2
            },
            {
                'name': 'Politics',
                'description': 'Political news, government updates, and policy changes',
                'color': '#007bff',  # Blue for politics
                'icon': 'fas fa-landmark',
                'sort_order': 3
            },
            {
                'name': 'Sports',
                'description': 'Sports news, match results, and athlete updates',
                'color': '#ffc107',  # Yellow for sports
                'icon': 'fas fa-futbol',
                'sort_order': 4
            },
            {
                'name': 'Technology',
                'description': 'Technology news, innovations, and digital developments',
                'color': '#6f42c1',  # Purple for technology
                'icon': 'fas fa-microchip',
                'sort_order': 5
            }
        ]

        categories = []
        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'description': cat_data['description'],
                    'color': cat_data['color'],
                    'icon': cat_data['icon'],
                    'sort_order': cat_data['sort_order'],
                    'is_active': True
                }
            )
            categories.append(category)
            
            if created:
                self.stdout.write(f'Created category: {category.name}')
            else:
                self.stdout.write(f'Category already exists: {category.name}')

        return categories

    def create_tags(self):
        """Create sample tags."""
        tags_data = [
            {
                'name': 'Trending',
                'description': 'Currently trending topics and popular stories',
                'color': '#e83e8c'  # Pink for trending
            },
            {
                'name': 'Recent',
                'description': 'Recently published articles and updates',
                'color': '#20c997'  # Teal for recent
            },
            {
                'name': 'Politicians',
                'description': 'News related to political figures and leaders',
                'color': '#6c757d'  # Gray for politicians
            },
            {
                'name': 'Economy',
                'description': 'Economic news and financial updates',
                'color': '#fd7e14'  # Orange for economy
            },
            {
                'name': 'Security',
                'description': 'Security updates and safety-related news',
                'color': '#dc3545'  # Red for security
            },
            {
                'name': 'Education',
                'description': 'Educational news and academic updates',
                'color': '#17a2b8'  # Cyan for education
            },
            {
                'name': 'Health',
                'description': 'Health news and medical updates',
                'color': '#28a745'  # Green for health
            },
            {
                'name': 'Culture',
                'description': 'Cultural events and traditional news',
                'color': '#6f42c1'  # Purple for culture
            },
            {
                'name': 'International',
                'description': 'International news and global updates',
                'color': '#007bff'  # Blue for international
            },
            {
                'name': 'Local',
                'description': 'Local news and community updates',
                'color': '#ffc107'  # Yellow for local
            }
        ]

        tags = []
        for tag_data in tags_data:
            tag, created = Tag.objects.get_or_create(
                name=tag_data['name'],
                defaults={
                    'description': tag_data['description'],
                    'color': tag_data['color'],
                    'is_active': True
                }
            )
            tags.append(tag)
            
            if created:
                self.stdout.write(f'Created tag: {tag.name}')
            else:
                self.stdout.write(f'Tag already exists: {tag.name}')

        return tags
