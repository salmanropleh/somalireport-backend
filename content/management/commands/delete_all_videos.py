from django.core.management.base import BaseCommand
from content.models import Video
import sys

class Command(BaseCommand):
    help = 'Wipes ALL videos from the database (Hard Delete)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Do not prompt for confirmation',
        )

    def handle(self, *args, **options):
        count = Video.objects.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING("No videos found to delete."))
            return

        if not options['no_input']:
            self.stdout.write(self.style.WARNING(
                f"WARNING: This will PERMANENTLY delete {count} videos."
            ))
            self.stdout.write(self.style.WARNING(
                "This action cannot be undone. Are you sure? (yes/no)"
            ))
            
            confirm = input().lower()
            if confirm != 'yes':
                self.stdout.write(self.style.ERROR("Operation cancelled."))
                return

        self.stdout.write(f"Deleting {count} videos...")
        
        # Perform hard delete on all videos
        deleted_count = 0
        for video in Video.objects.all():
            video.hard_delete()
            deleted_count += 1
            if deleted_count % 100 == 0:
                 self.stdout.write(f"Deleted {deleted_count}...")

        self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} videos."))
