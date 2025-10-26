"""
Scraping services for scraper app.
"""

import requests
import hashlib
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from scraper.models import NewsSource, ScrapedArticle, ScrapingLog
from core.utils import StringHelper

logger = logging.getLogger(__name__)


class NewsScrapingService:
    """
    Service for scraping news from various sources.
    """
    
    def __init__(self, source):
        self.source = source
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def scrape_articles(self, max_articles=100, force_update=False):
        """
        Scrape articles from the source.
        
        Returns:
            tuple: (articles_found, articles_scraped, articles_processed)
        """
        try:
            self.log('info', f"Starting scraping for {self.source.name}")
            
            articles_found = 0
            articles_scraped = 0
            articles_processed = 0
            
            if self.source.source_type == 'rss':
                articles_found, articles_scraped, articles_processed = self._scrape_rss(max_articles, force_update)
            elif self.source.source_type == 'api':
                articles_found, articles_scraped, articles_processed = self._scrape_api(max_articles, force_update)
            elif self.source.source_type == 'scraper':
                articles_found, articles_scraped, articles_processed = self._scrape_web(max_articles, force_update)
            
            # Update source statistics
            self.source.update_stats(success=True)
            
            self.log('info', f"Scraping completed for {self.source.name}")
            return articles_found, articles_scraped, articles_processed
            
        except Exception as e:
            self.log('error', f"Scraping failed for {self.source.name}: {str(e)}")
            self.source.update_stats(success=False)
            raise e
    
    def _scrape_rss(self, max_articles, force_update):
        """Scrape articles from RSS feed."""
        try:
            response = self.session.get(self.source.url, timeout=30)
            response.raise_for_status()
            
            # Parse RSS feed (simplified - in production, use feedparser)
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            articles_found = 0
            articles_scraped = 0
            articles_processed = 0
            duplicates = 0
            errors = 0
            
            for item in root.findall('.//item')[:max_articles]:
                articles_found += 1
                
                title = item.find('title')
                link = item.find('link')
                description = item.find('description')
                pub_date = item.find('pubDate')
                
                if title is not None and link is not None:
                    title_text = title.text or ''
                    link_text = link.text or ''
                    description_text = description.text if description is not None else ''
                    pub_date_text = pub_date.text if pub_date is not None else ''
                    
                    # Parse publication date
                    published_at = self._parse_date(pub_date_text)
                    
                    # Create scraped article
                    article = self._create_scraped_article(
                        title=title_text,
                        content=description_text,
                        source_url=link_text,
                        published_at=published_at
                    )
                    
                    if article:
                        articles_scraped += 1
                        if article.status == 'approved':
                            articles_processed += 1
                    else:
                        duplicates += 1
                else:
                    errors += 1
                    self.log('warning', f"Skipped article due to missing title or link")
            
            self.log('info', f"RSS scraping summary: {articles_found} found, {articles_scraped} scraped, {duplicates} duplicates, {errors} errors")
            return articles_found, articles_scraped, articles_processed
            
        except Exception as e:
            self.log('error', f"RSS scraping failed: {str(e)}")
            raise e
    
    def _scrape_api(self, max_articles, force_update):
        """Scrape articles from API."""
        try:
            headers = {}
            if self.source.api_key:
                headers['Authorization'] = f'Bearer {self.source.api_key}'
            
            response = self.session.get(self.source.url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            articles_found = 0
            articles_scraped = 0
            articles_processed = 0
            
            # Process API response (simplified - adapt based on API structure)
            articles = data.get('articles', [])[:max_articles]
            
            for article_data in articles:
                articles_found += 1
                
                title = article_data.get('title', '')
                content = article_data.get('content', '')
                url = article_data.get('url', '')
                published_at = article_data.get('publishedAt', '')
                
                if title and url:
                    published_at = self._parse_date(published_at)
                    
                    article = self._create_scraped_article(
                        title=title,
                        content=content,
                        source_url=url,
                        published_at=published_at
                    )
                    
                    if article:
                        articles_scraped += 1
                        if article.status == 'approved':
                            articles_processed += 1
            
            return articles_found, articles_scraped, articles_processed
            
        except Exception as e:
            self.log('error', f"API scraping failed: {str(e)}")
            raise e
    
    def _scrape_web(self, max_articles, force_update):
        """Scrape articles from web pages."""
        try:
            response = self.session.get(self.source.url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML (simplified - in production, use BeautifulSoup)
            import re
            
            articles_found = 0
            articles_scraped = 0
            articles_processed = 0
            
            # Extract article links (simplified pattern)
            article_links = re.findall(r'href="([^"]*article[^"]*)"', response.text)
            
            for link in article_links[:max_articles]:
                articles_found += 1
                
                try:
                    # Scrape individual article
                    article_response = self.session.get(link, timeout=30)
                    article_response.raise_for_status()
                    
                    # Extract title and content (simplified)
                    title_match = re.search(r'<title[^>]*>([^<]+)</title>', article_response.text)
                    content_match = re.search(r'<p[^>]*>([^<]+)</p>', article_response.text)
                    
                    if title_match and content_match:
                        title = title_match.group(1)
                        content = content_match.group(1)
                        
                        article = self._create_scraped_article(
                            title=title,
                            content=content,
                            source_url=link,
                            published_at=timezone.now()
                        )
                        
                        if article:
                            articles_scraped += 1
                            if article.status == 'approved':
                                articles_processed += 1
                
                except Exception as e:
                    self.log('warning', f"Failed to scrape article {link}: {str(e)}")
                    continue
            
            return articles_found, articles_scraped, articles_processed
            
        except Exception as e:
            self.log('error', f"Web scraping failed: {str(e)}")
            raise e
    
    def _create_scraped_article(self, title, content, source_url, published_at):
        """Create a scraped article."""
        try:
            # Generate hashes for duplicate detection
            content_hash = hashlib.md5(content.encode()).hexdigest()
            title_hash = hashlib.md5(title.encode()).hexdigest()
            
            # Check for duplicates
            if ScrapedArticle.objects.filter(
                source=self.source,
                content_hash=content_hash
            ).exists():
                self.log('info', f"Duplicate article found: {title}")
                return None
            
            # Create scraped article with category and tags from source
            article = ScrapedArticle.objects.create(
                source=self.source,
                source_url=source_url,
                title=title,
                content=content,
                excerpt=StringHelper.extract_excerpt(content),
                published_at=published_at,
                content_hash=content_hash,
                title_hash=title_hash,
                quality_score=self._calculate_quality_score(title, content),
                category=self.source.category  # Inherit category from source
            )
            
            # Add tags from source
            if self.source.tags.exists():
                article.tags.set(self.source.tags.all())
            
            self.log('info', f"Created scraped article: {title}")
            return article
            
        except Exception as e:
            self.log('error', f"Failed to create scraped article: {str(e)}")
            return None
    
    def _parse_date(self, date_string):
        """Parse date string to datetime."""
        try:
            # Simple date parsing (in production, use dateutil)
            from datetime import datetime
            return datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
        except:
            return timezone.now()
    
    def _calculate_quality_score(self, title, content):
        """Calculate quality score for article."""
        score = 0.0
        
        # Title length score
        if 10 <= len(title) <= 100:
            score += 0.2
        
        # Content length score
        if 100 <= len(content) <= 5000:
            score += 0.3
        
        # Content quality indicators
        if any(word in content.lower() for word in ['news', 'report', 'update', 'breaking']):
            score += 0.2
        
        if any(word in title.lower() for word in ['breaking', 'urgent', 'important']):
            score += 0.3
        
        return min(score, 1.0)
    
    def log(self, level, message, details=None):
        """Log scraping activity."""
        ScrapingLog.objects.create(
            source=self.source,
            level=level,
            message=message,
            details=details or {}
        )
        
        # Also log to Django logger
        getattr(logger, level)(f"[{self.source.name}] {message}")
