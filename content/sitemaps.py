from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Category, ContentItem, CatalogCategory, CatalogItem


class StaticSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        return ['home', 'catalog']

    def location(self, item):
        return reverse(item)


class SectionSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return list(Category.objects.filter(is_active=True, parent__isnull=True).order_by('sort_order'))

    def location(self, obj):
        return obj.get_absolute_url()


class ArticleSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return (
            ContentItem.objects.filter(status='published')
            .exclude(content_type='product')
            .only('id', 'slug', 'public_slug', 'published_date', 'updated_at')
            .order_by('-published_date')
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


class CatalogCategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return CatalogCategory.objects.filter(is_active=True).order_by('sort_order')

    def location(self, obj):
        return obj.get_absolute_url()


class CatalogItemSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return (
            CatalogItem.objects.filter(is_active=True)
            .only('id', 'slug', 'public_slug', 'category_id', 'updated_at')
            .select_related('category')
            .order_by('-views')
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()


sitemaps = {
    'static': StaticSitemap,
    'sections': SectionSitemap,
    'articles': ArticleSitemap,
    'catalog_categories': CatalogCategorySitemap,
    'catalog_items': CatalogItemSitemap,
}
