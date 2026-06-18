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


def apply_public_slug_updates(apps, schema_editor):
    Category = apps.get_model('content', 'Category')
    used = set(Category.objects.exclude(public_slug__isnull=True).exclude(public_slug='').values_list('public_slug', flat=True))

    for slug, target_slug in PUBLIC_SLUG_UPDATES.items():
        category = Category.objects.filter(slug=slug).first()
        if not category:
            continue

        current_public_slug = category.public_slug or ''
        if current_public_slug in used:
            used.discard(current_public_slug)

        candidate = target_slug
        if candidate in used:
            index = 2
            while f'{target_slug}-{index}' in used:
                index += 1
            candidate = f'{target_slug}-{index}'

        category.public_slug = candidate
        category.save(update_fields=['public_slug'])
        used.add(candidate)


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0007_cleanup_conflicting_legacy_redirects'),
    ]

    operations = [
        migrations.RunPython(apply_public_slug_updates, migrations.RunPython.noop),
    ]
