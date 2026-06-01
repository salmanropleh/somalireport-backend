"""
Management commands for scraper app.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from scraper.models import NewsSource, ScrapingJob, ScrapedArticle
from scraper.services import NewsScrapingService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Management command to scrape news from configured sources.
    """
    
    help = 'Scrape news from configured sources'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            help='Specific source ID to scrape',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if recently scraped',
        )
        parser.add_argument(
            '--max-articles',
            type=int,
            default=100,
            help='Maximum articles to scrape per source',
        )
    
    def handle(self, *args, **options):
        """Handle the scraping command."""
        source_id = options.get('source')
        force_update = options.get('force', False)
        max_articles = options.get('max_articles', 100)
        
        try:
            if source_id:
                # Scrape specific source
                sources = NewsSource.objects.filter(id=source_id, is_active=True)
                if not sources.exists():
                    raise CommandError(f"Source with ID {source_id} not found or inactive")
            else:
                # Scrape all active sources
                sources = NewsSource.objects.filter(is_active=True)
            
            if not sources.exists():
                self.stdout.write(self.style.WARNING('No active sources found'))
                return
            
            total_scraped = 0
            total_processed = 0
            
            for source in sources:
                self.stdout.write(f"Scraping source: {source.name}")
                
                # Create scraping job
                job = ScrapingJob.objects.create(
                    source=source,
                    max_articles=max_articles,
                    force_update=force_update
                )
                
                try:
                    # Start scraping
                    job.start()
                    
                    # Initialize scraping service
                    scraping_service = NewsScrapingService(source)
                    
                    # Scrape articles
                    articles_found, articles_scraped, articles_processed = scraping_service.scrape_articles(
                        max_articles=max_articles,
                        force_update=force_update
                    )
                    
                    # Complete job
                    job.complete(articles_found, articles_scraped, articles_processed)
                    
                    total_scraped += articles_scraped
                    total_processed += articles_processed
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully scraped {articles_scraped} articles from {source.name}"
                        )
                    )
                    
                except Exception as e:
                    # Mark job as failed
                    job.fail(str(e))
                    self.stdout.write(
                        self.style.ERROR(f"Failed to scrape {source.name}: {str(e)}")
                    )
                    logger.error(f"Scraping failed for {source.name}: {str(e)}")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"Scraping completed. Total articles scraped: {total_scraped}, "
                    f"Total processed: {total_processed}"
                )
            )
            
        except Exception as e:
            raise CommandError(f"Scraping failed: {str(e)}")
