from django.db import migrations, models


CATEGORY_PUBLIC_SLUGS = {
    'news': 'dokumenty',
    'news-pozharnaya-bezopasnost': 'pozharnaya-bezopasnost',
    'health': 'prombez',
    'news-grazhdanskaya-oborona': 'attestatsiya-rabochikh-mest',
    'chasto-zadavaemye-voprosy-po-okhrane-truda': 'vopros-otvet',
    'news-ekologiya': 'obshchie-voprosy-po-ekologii',
    'football': 'okhrana-atmosfernogo-vozdukha',
    'category-53': 'obrashchenie-s-otkhodami-proizvodstva',
    'cricket': 'okhrana-vodnoj-sredy',
    'tennis': 'okhrana-pochvennogo-sloya',
    'box': 'sistema-upravleniya-okruzhayushchej-sredoj',
    'space': 'instruktsii-po-okhrane-truda',
    '2011-05-22-18-52-41': 'sanitariya-i-gigiena',
    'okhrana-truda-zhenshchin': 'elektrobezopasnost',
}


def fill_public_slugs(apps, schema_editor):
    Category = apps.get_model('content', 'Category')
    ContentItem = apps.get_model('content', 'ContentItem')
    used_category_slugs = set()
    used_item_slugs = set()

    def make_unique(base_slug, fallback_slug, used):
        candidate = base_slug or fallback_slug
        if candidate not in used:
            used.add(candidate)
            return candidate
        if fallback_slug not in used:
            used.add(fallback_slug)
            return fallback_slug
        index = 2
        while True:
            candidate = f'{base_slug}-{index}'
            if candidate not in used:
                used.add(candidate)
                return candidate
            index += 1

    for category in Category.objects.all():
        if not category.public_slug:
            base_slug = CATEGORY_PUBLIC_SLUGS.get(category.slug, category.slug)
            category.public_slug = make_unique(base_slug, category.slug, used_category_slugs)
            category.save(update_fields=['public_slug'])

    for item in ContentItem.objects.all():
        if not item.public_slug:
            item.public_slug = make_unique(item.slug, item.slug, used_item_slugs)
            item.save(update_fields=['public_slug'])


def clear_public_slugs(apps, schema_editor):
    Category = apps.get_model('content', 'Category')
    ContentItem = apps.get_model('content', 'ContentItem')
    Category.objects.update(public_slug=None)
    ContentItem.objects.update(public_slug=None)


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0005_legacyredirect'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='public_slug',
            field=models.SlugField(blank=True, max_length=200, null=True, unique=True, verbose_name='Публичный URL'),
        ),
        migrations.AddField(
            model_name='contentitem',
            name='public_slug',
            field=models.SlugField(blank=True, max_length=500, null=True, unique=True, verbose_name='Публичный URL'),
        ),
        migrations.RunPython(fill_public_slugs, clear_public_slugs),
    ]
