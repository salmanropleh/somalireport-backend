from django.conf import settings
from django.contrib.sitemaps import Sitemap

from core.utils import StringHelper
from .models import Article, Category, Tag

SITE_DOMAIN = getattr(settings, 'SITE_URL', 'https://somalireport.com').replace('https://', '').replace('http://', '').rstrip('/')


class _SomaliSitemap(Sitemap):
    """Base class that always uses the canonical production domain."""
    protocol = 'https'

    def get_domain(self, site=None):
        return SITE_DOMAIN


class StaticSitemap(_SomaliSitemap):

    def items(self):
        return [
            ('/', '1.0', 'daily'),
            ('/news', '0.9', 'hourly'),
            ('/about', '0.3', 'monthly'),
            ('/contact', '0.3', 'monthly'),
        ]

    def location(self, item):
        return item[0]

    def priority(self, item):
        return item[1]

    def changefreq(self, item):
        return item[2]


class ArticleSitemap(_SomaliSitemap):
    changefreq = 'weekly'

    def items(self):
        return Article.objects.filter(status='published').order_by('-published_at')

    def location(self, obj):
        slug = obj.slug or StringHelper.slugify(obj.title)
        return f'/article/{obj.id}/{slug}'

    def lastmod(self, obj):
        return obj.updated_at or obj.published_at

    def priority(self, obj):
        if obj.is_breaking:
            return 0.9
        if obj.is_featured:
            return 0.8
        return 0.7


class CategorySitemap(_SomaliSitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return Category.objects.filter(is_active=True)

    def location(self, obj):
        return f'/category/{obj.id}'

    def lastmod(self, obj):
        return obj.updated_at


class TagSitemap(_SomaliSitemap):
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        return Tag.objects.filter(is_active=True)

    def location(self, obj):
        slug = obj.slug or StringHelper.slugify(obj.name)
        return f'/tags/{obj.id}/{slug}'

    def lastmod(self, obj):
        return obj.updated_at
