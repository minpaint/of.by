from django.db import migrations


PUBLIC_SLUG_UPDATES = {
    'uncategorised': 'bez-rubriki',
    'africa': 'obshchie-voprosy-pozharnoj-bezopasnosti',
    'us-canada': 'normy-pozharnoj-bezopasnosti',
    'europe': 'tekhnicheskie-kodeksy-ustoyavshejsya-praktiki',
    'engineering': 'karty-fotografii-rabochego-vremeni',
    'mathematics': 'arm-po-professiyam',
    'suot': 'sistema-upravleniya-okhranoj-truda',
    'events': 'vebinary',
    'videos': 'video',
    'online': 'online-marafony',
    '2011-03-28-13-46-36': 'online-marafon-attestatsiya-rabochikh-mest',
    'media': 'media-arhiv',
    'informatsiya': 'informatsiya-arhiv',
    'dokumenty': 'dokumenty-arhiv',
}


def force_public_slug_updates(apps, schema_editor):
    Category = apps.get_model('content', 'Category')
    for slug, public_slug in PUBLIC_SLUG_UPDATES.items():
        Category.objects.filter(slug=slug).update(public_slug=public_slug)


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0008_refine_category_public_slugs'),
    ]

    operations = [
        migrations.RunPython(force_public_slug_updates, migrations.RunPython.noop),
    ]
