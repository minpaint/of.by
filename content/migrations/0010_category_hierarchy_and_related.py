from django.db import migrations, models


TOP_LEVEL_SLUGS = {
    'okhrana-truda',
    'news-pozharnaya-bezopasnost',
    'health',
    'ekologiya',
    'news-grazhdanskaya-oborona',
    'grazhdanskaya-oborona',
    'chasto-zadavaemye-voprosy-po-okhrane-truda',
}

SECTION_CHILDREN = {
    'okhrana-truda': [
        'obshchie-voprosy-po-ot',
        'sluzhba-po-okhrane-truda',
        'obuchenie-instruktazh-proverka-znanij',
        'space',
        'mezhotraslevye-pravila-po-okhrane-truda',
        '2011-05-22-18-52-41',
        'meditsinskie-osmotry',
        'sredstva-individualnoj-zashchity',
        'okhrana-truda-zhenshchin',
        'rassledovanie-neschastnykh-sluchaev',
        'informatsionnye-pisma',
        'suot',
        'stroitelnye-normy',
    ],
    'news-pozharnaya-bezopasnost': [
        'africa',
        'spetsificheskie-trebovaniya-po-pozharnoj-bezopasnosti',
        'us-canada',
        'europe',
    ],
    'health': [
        'gruzopod-emnye-krany',
        'perevozka-opasnykh-gruzov',
        'obshchie-voprosy-promyshlennoj-bezopasnosti',
        'mobilnye-pod-emnye-platformy',
    ],
    'ekologiya': [
        'news-ekologiya',
        'football',
        'category-53',
        'cricket',
        'tennis',
        'box',
        'otchety-po-ekologii',
    ],
    'news-grazhdanskaya-oborona': [
        'obshchie-voprosy-po-arm',
        'engineering',
        'mathematics',
        'obraztsy-prikazov-po-arm',
    ],
    'grazhdanskaya-oborona': [
        'voprosy-po-preduprezhdeniyu-i-likvidatsii-chrezvychajnykh-situatsij',
    ],
    'chasto-zadavaemye-voprosy-po-okhrane-truda': [
        'voprosy-po-trudovomu-zakonodatelstvu-respubliki-belarus',
        'voprosy-po-organizatsii-raboty-po-okhrane-truda',
        'upravlenie-nadzor-i-kontrol-za-deyatelnostyu-po-okhrane-truda',
        'okhrana-truda-pri-ekspluatatsii-proizvodstvennogo-oborudovaniya',
        'okhrana-truda-pri-provedenii-proizvodstvennykh-protsessov',
        'trebovaniya-bezopasnosti-dlya-opasnykh-proizvodstvennykh-ob-ektov',
        'okhrana-truda-pri-ekspluatatsii-transportnykh-sredstv-transportirovke-razmeshchenii-i-skladirovanii-gruzov',
        'okhrana-truda-pri-stroitelstve-i-ekspluatatsii-zdanij-i-sooruzhenij-i-ikh-territorii',
        'okhrana-truda-pri-ekspluatatsii-elektricheskikh-i-teploispolzuyushchikh-ustanovok-elektricheskikh-i-teplovykh-setej',
        'voprosy-po-pozharnoj-bezopasnosti',
        'voprosy-po-radiatsionnoj-bezopasnosti',
        'voprosy-po-lazernoj-bezopasnosti',
        'voprosy-proizvodstvennoj-sanitarii-i-gigieny-truda',
        'psikhofiziologicheskie-faktory-v-okhrane-truda',
        'voprosy-obespecheniya-sredstvami-individualnoj-zashchity',
        'voprosy-sanitarno-bytovogo-i-lechebno-profilakticheskogo-obespecheniya',
        'voprosy-po-rassledovaniyu-i-uchetu-neschastnykh-sluchaev-na-proizvodstve-i-profzabolevanij',
        'voprosy-po-strakhovaniyu-ot-neschastnykh-sluchaev-na-proizvodstve-i-profzabolevanij',
    ],
}

EXTRA_RELATED = {
    'grazhdanskaya-oborona': ['news-grazhdanskaya-oborona'],
    'news-grazhdanskaya-oborona': ['grazhdanskaya-oborona'],
    'health': ['news-pozharnaya-bezopasnost', 'okhrana-truda'],
    'news-pozharnaya-bezopasnost': ['health', 'okhrana-truda'],
    'okhrana-truda': ['health', 'news-pozharnaya-bezopasnost', 'chasto-zadavaemye-voprosy-po-okhrane-truda'],
    'chasto-zadavaemye-voprosy-po-okhrane-truda': ['okhrana-truda', 'health', 'news-pozharnaya-bezopasnost'],
    'ekologiya': ['health', 'okhrana-truda'],
}


def populate_hierarchy(apps, schema_editor):
    Category = apps.get_model('content', 'Category')
    categories = {category.slug: category for category in Category.objects.all()}

    for category in categories.values():
        if category.slug in TOP_LEVEL_SLUGS:
            category.parent_id = None
            category.save(update_fields=['parent'])

    for parent_slug, child_slugs in SECTION_CHILDREN.items():
        parent = categories.get(parent_slug)
        if parent is None:
            continue

        siblings = []
        for child_slug in child_slugs:
            child = categories.get(child_slug)
            if child is None:
                continue
            child.parent_id = parent.id
            child.save(update_fields=['parent'])
            siblings.append(child)

            parent.related_categories.add(child)
            child.related_categories.add(parent)

        for sibling in siblings:
            sibling.related_categories.add(*[item for item in siblings if item.id != sibling.id])

    for slug, related_slugs in EXTRA_RELATED.items():
        category = categories.get(slug)
        if category is None:
            continue
        category.related_categories.add(*[categories[item] for item in related_slugs if item in categories])


def clear_hierarchy(apps, schema_editor):
    Category = apps.get_model('content', 'Category')
    Category.related_categories.through.objects.all().delete()
    Category.objects.exclude(parent__isnull=True).update(parent=None)


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0009_force_category_public_slugs'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='children', to='content.category', verbose_name='Родительская категория'),
        ),
        migrations.AddField(
            model_name='category',
            name='related_categories',
            field=models.ManyToManyField(blank=True, symmetrical=False, to='content.category', verbose_name='Родственные категории'),
        ),
        migrations.RunPython(populate_hierarchy, clear_hierarchy),
    ]
