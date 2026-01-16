from django.core.management.base import BaseCommand
from content.models import Article
import sys

class Command(BaseCommand):
    help = 'Wipes ALL articles from the database (Hard Delete)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Do not prompt for confirmation',
        )

    def handle(self, *args, **options):
        count = Article.objects.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING("No articles found to delete."))
            return

        if not options['no_input']:
            self.stdout.write(self.style.WARNING(
                f"WARNING: This will PERMANENTLY delete {count} articles."
            ))
            self.stdout.write(self.style.WARNING(
                "This action cannot be undone. Are you sure? (yes/no)"
            ))
            
            confirm = input().lower()
            if confirm != 'yes':
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return

        self.stdout.write(f"Deleting {count} articles...")
        
        # Perform hard delete on all articles
        # We iterate to ensure hard_delete() is called on each instance
        # Bulk delete() on queryset might bypass model methods depending on implementation,
        # so explicit iteration is safer for custom hard_delete logic unless we have a custom manager method.
        # Given we want to be absolutely sure:
        
        deleted_count = 0
        for article in Article.objects.all():
            article.hard_delete()
            deleted_count += 1
            if deleted_count % 100 == 0:
                 self.stdout.write(f"Deleted {deleted_count}...")

        self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} articles."))
