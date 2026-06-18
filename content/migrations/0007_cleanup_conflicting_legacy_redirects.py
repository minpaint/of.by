from django.db import migrations


def cleanup_conflicting_redirects(apps, schema_editor):
    ContentItem = apps.get_model('content', 'ContentItem')
    LegacyRedirect = apps.get_model('content', 'LegacyRedirect')

    public_item_paths = set()
    for item in ContentItem.objects.filter(status='published').only('slug', 'public_slug'):
        public_slug = item.public_slug or item.slug
        if public_slug:
            public_item_paths.add(f'{public_slug}.html')

    if public_item_paths:
        LegacyRedirect.objects.filter(old_path__in=public_item_paths).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0006_category_public_slug_contentitem_public_slug'),
    ]

    operations = [
        migrations.RunPython(cleanup_conflicting_redirects, migrations.RunPython.noop),
    ]
