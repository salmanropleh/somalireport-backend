"""
Scraping services for scraper app.
"""

import requests
import hashlib
import logging
import re
import os
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
from scraper.models import NewsSource, ScrapedArticle, ScrapingLog
from content.models import MediaFile
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
                    
                    # Extract image from RSS item
                    image_url = self._extract_image_from_rss_item(item, link_text)
                    
                    # Create scraped article
                    article = self._create_scraped_article(
                        title=title_text,
                        content=description_text,
                        source_url=link_text,
                        published_at=published_at,
                        image_url=image_url
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
                    
                    # Extract image from API response
                    image_url = self._extract_image_from_api_response(article_data)
                    
                    article = self._create_scraped_article(
                        title=title,
                        content=content,
                        source_url=url,
                        published_at=published_at,
                        image_url=image_url
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
                        
                        # Extract image from web page
                        image_url = self._extract_image_from_web_page(article_response.text, link)
                        
                        article = self._create_scraped_article(
                            title=title,
                            content=content,
                            source_url=link,
                            published_at=timezone.now(),
                            image_url=image_url
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
    
    def _create_scraped_article(self, title, content, source_url, published_at, image_url=None):
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
            
            # Ensure we have an image URL (use fallback if needed)
            if not image_url:
                image_url = self._get_fallback_image_url(content, source_url)
            
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
                category=self.source.category,  # Inherit category from source
                image_url=image_url
            )
            
            # Add tags from source
            if self.source.tags.exists():
                article.tags.set(self.source.tags.all())
            
            self.log('info', f"Created scraped article: {title} (image: {'yes' if image_url else 'no'})")
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
    
    def _extract_image_from_rss_item(self, item, article_url):
        """Extract image URL from RSS item."""
        try:
            # Try media:content (Media RSS)
            media_content = item.find('.//{http://search.yahoo.com/mrss/}content')
            if media_content is not None and media_content.get('type', '').startswith('image/'):
                return media_content.get('url')
            
            # Try enclosure with image type
            enclosure = item.find('enclosure')
            if enclosure is not None and enclosure.get('type', '').startswith('image/'):
                return enclosure.get('url')
            
            # Try media:thumbnail
            media_thumbnail = item.find('.//{http://search.yahoo.com/mrss/}thumbnail')
            if media_thumbnail is not None:
                return media_thumbnail.get('url')
            
            # Try image tag
            image = item.find('image')
            if image is not None:
                url = image.find('url')
                if url is not None and url.text:
                    return url.text
            
            # Try extracting from description HTML
            description = item.find('description')
            if description is not None and description.text:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description.text)
                if img_match:
                    img_url = img_match.group(1)
                    # Make absolute URL if relative
                    return urljoin(article_url, img_url)
            
            return None
        except Exception as e:
            self.log('warning', f"Failed to extract image from RSS item: {str(e)}")
            return None
    
    def _extract_image_from_api_response(self, article_data):
        """Extract image URL from API response."""
        try:
            # Common image field names in APIs
            image_fields = [
                'image', 'imageUrl', 'image_url', 'imageURL',
                'thumbnail', 'thumbnailUrl', 'thumbnail_url',
                'featuredImage', 'featured_image', 'featuredImageUrl',
                'urlToImage', 'url_to_image', 'media', 'picture'
            ]
            
            for field in image_fields:
                if field in article_data and article_data[field]:
                    img_url = article_data[field]
                    if isinstance(img_url, str) and img_url.strip():
                        return img_url.strip()
                    elif isinstance(img_url, dict) and 'url' in img_url:
                        return img_url['url']
            
            # Try extracting from content if it's HTML
            content = article_data.get('content', '') or article_data.get('description', '')
            if content:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
                if img_match:
                    return img_match.group(1)
            
            return None
        except Exception as e:
            self.log('warning', f"Failed to extract image from API response: {str(e)}")
            return None
    
    def _extract_image_from_web_page(self, html_content, page_url):
        """Extract image URL from web page HTML."""
        try:
            # If custom image selector is configured, try to use it
            # (This would require BeautifulSoup - for now, we'll use regex)
            if self.source.image_selector:
                # Basic CSS selector support (simplified)
                # In production, use BeautifulSoup with CSS selectors
                pass
            
            # Try Open Graph image
            og_image_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if og_image_match:
                return urljoin(page_url, og_image_match.group(1))
            
            # Try Twitter Card image
            twitter_image_match = re.search(r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if twitter_image_match:
                return urljoin(page_url, twitter_image_match.group(1))
            
            # Try article:image
            article_image_match = re.search(r'<meta[^>]+property=["\']article:image["\'][^>]+content=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
            if article_image_match:
                return urljoin(page_url, article_image_match.group(1))
            
            # Try to find the first large image in the content
            # Look for img tags with reasonable dimensions or class names
            img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
            img_matches = re.findall(img_pattern, html_content)
            
            for img_url in img_matches:
                # Skip small images (likely icons, logos)
                if any(skip in img_url.lower() for skip in ['icon', 'logo', 'avatar', 'thumb', 'spacer', 'pixel']):
                    continue
                # Make absolute URL
                full_url = urljoin(page_url, img_url)
                # Validate it's a real image URL
                if self._is_valid_image_url(full_url):
                    return full_url
            
            return None
        except Exception as e:
            self.log('warning', f"Failed to extract image from web page: {str(e)}")
            return None
    
    def _is_valid_image_url(self, url):
        """Check if URL is likely a valid image."""
        try:
            parsed = urlparse(url)
            # Check file extension
            path = parsed.path.lower()
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
            if any(path.endswith(ext) for ext in image_extensions):
                return True
            # Check if it's a data URL
            if url.startswith('data:image/'):
                return True
            return False
        except:
            return False
    
    def _get_fallback_image_url(self, content, source_url):
        """Get fallback image URL if no image was found."""
        try:
            # 1. Try to extract first image from content HTML
            if content:
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
                if img_match:
                    img_url = img_match.group(1)
                    # Make absolute URL if relative
                    full_url = urljoin(source_url, img_url)
                    if self._is_valid_image_url(full_url):
                        return full_url
            
            # 2. Use source icon if available
            if self.source.icon_url:
                return self.source.icon_url
            
            # 3. Use a default placeholder image
            # You can configure this in settings or use a service like placeholder.com
            default_image = getattr(settings, 'SCRAPER_DEFAULT_IMAGE_URL', None)
            if default_image:
                return default_image
            
            # 4. Use a generic placeholder service as last resort
            # Using placeholder.com with article title as text
            return f"https://via.placeholder.com/800x450/0066CC/FFFFFF?text=News"
            
        except Exception as e:
            self.log('warning', f"Failed to get fallback image: {str(e)}")
            # Return a basic placeholder
            return "https://via.placeholder.com/800x450/0066CC/FFFFFF?text=News"
    
    @staticmethod
    def download_and_save_image(image_url, article_title, user=None):
        """
        Download an image from URL and save it as a MediaFile.
        
        Args:
            image_url: URL of the image to download
            article_title: Title of the article (for naming)
            user: User who will own the media file (optional)
        
        Returns:
            MediaFile instance or None if download fails
        """
        try:
            from content.models import MediaFile
            from django.contrib.auth import get_user_model
            from PIL import Image as PILImage
            import io
            
            User = get_user_model()
            
            # Skip placeholder images
            if 'placeholder.com' in image_url or 'via.placeholder' in image_url:
                return None
            
            # Download image
            response = requests.get(image_url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"URL does not point to an image: {image_url}")
                return None
            
            # Read image data
            image_data = response.content
            
            # Validate it's actually an image
            try:
                img = PILImage.open(io.BytesIO(image_data))
                img.verify()
            except Exception as e:
                logger.warning(f"Invalid image data from {image_url}: {str(e)}")
                return None
            
            # Reset image for saving
            img = PILImage.open(io.BytesIO(image_data))
            
            # Generate filename
            parsed_url = urlparse(image_url)
            filename = os.path.basename(parsed_url.path)
            if not filename or '.' not in filename:
                # Generate filename from title
                safe_title = re.sub(r'[^\w\s-]', '', article_title)[:50]
                safe_title = re.sub(r'[-\s]+', '-', safe_title)
                ext = content_type.split('/')[-1] if '/' in content_type else 'jpg'
                filename = f"{safe_title}.{ext}"
            
            # Create MediaFile
            media_file = MediaFile(
                name=filename,
                file_type='image',
                file_size=len(image_data),
                mime_type=content_type,
                alt_text=article_title[:200],
                uploaded_by=user or User.objects.filter(is_superuser=True).first()
            )
            
            # Save file
            media_file.file.save(
                filename,
                ContentFile(image_data),
                save=True
            )
            
            # Get image dimensions
            try:
                media_file.width, media_file.height = img.size
                media_file.save(update_fields=['width', 'height'])
            except:
                pass
            
            logger.info(f"Downloaded and saved image: {filename} from {image_url}")
            return media_file
            
        except Exception as e:
            logger.error(f"Failed to download image from {image_url}: {str(e)}")
            return None
    
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
