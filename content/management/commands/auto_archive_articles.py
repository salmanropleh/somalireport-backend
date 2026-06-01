"""
Management command to auto-archive articles from categories.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from content.models import Article


class Command(BaseCommand):
    help = 'Auto-archive articles from categories based on expiration dates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived without actually archiving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        # Archive from primary categories
        primary_expired = Article.objects.filter(
            primary_category_expires_at__lte=now,
            primary_category_archived_at__isnull=True,
            primary_category__isnull=False
        )
        
        # Archive from secondary categories
        secondary_expired = Article.objects.filter(
            secondary_categories_expire_at__lte=now,
            secondary_categories_archived_at__isnull=True
        ).exclude(secondary_categories__isnull=True)
        
        primary_count = primary_expired.count()
        secondary_count = secondary_expired.count()
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would archive {primary_count} articles from primary categories')
            )
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would archive {secondary_count} articles from secondary categories')
            )
            
            for article in primary_expired:
                self.stdout.write(f'  - {article.title} (Primary: {article.primary_category.name})')
            
            for article in secondary_expired:
                secondary_cats = ', '.join([cat.name for cat in article.secondary_categories.all()])
                self.stdout.write(f'  - {article.title} (Secondary: {secondary_cats})')
        else:
            # Actually archive the articles
            archived_primary = 0
            archived_secondary = 0
            
            for article in primary_expired:
                if article.archive_from_primary_category(manual=False):
                    archived_primary += 1
                    self.stdout.write(f'Archived from primary: {article.title}')
            
            for article in secondary_expired:
                if article.archive_from_secondary_categories(manual=False):
                    archived_secondary += 1
                    self.stdout.write(f'Archived from secondary: {article.title}')
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully archived {archived_primary} articles from primary categories')
            )
            self.stdout.write(
                self.style.SUCCESS(f'Successfully archived {archived_secondary} articles from secondary categories')
            )
