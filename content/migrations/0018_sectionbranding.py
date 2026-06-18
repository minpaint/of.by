from django.db import migrations, models
import django.db.models.deletion


def seed_section_branding(apps, schema_editor):
    SectionBranding = apps.get_model('content', 'SectionBranding')
    Category = apps.get_model('content', 'Category')
    CatalogCategory = apps.get_model('content', 'CatalogCategory')

    presets = [
        {
            'key': 'okhrana-truda',
            'name': 'Охрана труда',
            'title': 'Охрана труда',
            'subtitle': 'Портал для инженеров по охране труда Беларуси',
            'icon_name': 'shield',
            'theme_color': 'blue',
            'sort_order': 10,
        },
        {
            'key': 'pozharnaya-bezopasnost',
            'name': 'Пожарная безопасность',
            'title': 'Пожарная безопасность',
            'subtitle': 'Портал по пожарной безопасности Беларуси',
            'icon_name': 'fire',
            'theme_color': 'red',
            'sort_order': 20,
        },
        {
            'key': 'promyshlennaya-bezopasnost',
            'name': 'Промышленная безопасность',
            'title': 'Промышленная безопасность',
            'subtitle': 'Портал по промышленной безопасности Беларуси',
            'icon_name': 'factory',
            'theme_color': 'orange',
            'sort_order': 30,
        },
        {
            'key': 'ekologiya',
            'name': 'Экология',
            'title': 'Экология',
            'subtitle': 'Портал по экологии и охране окружающей среды',
            'icon_name': 'leaf',
            'theme_color': 'green',
            'sort_order': 40,
        },
        {
            'key': 'arm',
            'name': 'Аттестация рабочих мест',
            'title': 'Аттестация рабочих мест',
            'subtitle': 'Материалы по аттестации рабочих мест Беларуси',
            'icon_name': 'briefcase',
            'theme_color': 'purple',
            'sort_order': 50,
        },
        {
            'key': 'grazhdanskaya-oborona',
            'name': 'Гражданская оборона',
            'title': 'Гражданская оборона',
            'subtitle': 'Материалы по гражданской обороне и ЧС',
            'icon_name': 'lifebuoy',
            'theme_color': 'gray',
            'sort_order': 60,
        },
        {
            'key': 'vopros-otvet',
            'name': 'Вопрос-ответ',
            'title': 'Вопрос-ответ',
            'subtitle': 'Подборка практических ответов для специалистов',
            'icon_name': 'question',
            'theme_color': 'indigo',
            'sort_order': 70,
        },
        {
            'key': 'catalog',
            'name': 'Товары и услуги',
            'title': 'Товары и услуги',
            'subtitle': 'Каталог товаров и услуг по направлениям безопасности',
            'icon_name': 'box',
            'theme_color': 'blue',
            'sort_order': 80,
        },
    ]

    branding_by_key = {}
    for payload in presets:
        branding, _ = SectionBranding.objects.update_or_create(
            key=payload['key'],
            defaults=payload,
        )
        branding_by_key[payload['key']] = branding

    category_map = {
        'okhrana-truda': 'okhrana-truda',
        'dokumenty': 'okhrana-truda',
        'videos': 'okhrana-truda',
        'video': 'okhrana-truda',
        'events': 'okhrana-truda',
        'webinars': 'okhrana-truda',
        'stati-po-okhrane-truda': 'okhrana-truda',
        'obraztsy-blanki-primery-dokumentov-po-okhrane-truda': 'okhrana-truda',
        'news-pozharnaya-bezopasnost': 'pozharnaya-bezopasnost',
        'pozharnaya-bezopasnost': 'pozharnaya-bezopasnost',
        'health': 'promyshlennaya-bezopasnost',
        'prombez': 'promyshlennaya-bezopasnost',
        'promyshlennaya-bezopasnost': 'promyshlennaya-bezopasnost',
        'ekologiya': 'ekologiya',
        'news-ekologiya': 'ekologiya',
        'news-grazhdanskaya-oborona': 'arm',
        'arm': 'arm',
        'attestatsiya-rabochikh-mest': 'arm',
        'grazhdanskaya-oborona': 'grazhdanskaya-oborona',
        'chasto-zadavaemye-voprosy-po-okhrane-truda': 'vopros-otvet',
        'vopros-otvet': 'vopros-otvet',
    }

    for slug, branding_key in category_map.items():
        Category.objects.filter(slug=slug).update(branding=branding_by_key[branding_key])
        Category.objects.filter(public_slug=slug).update(branding=branding_by_key[branding_key])

    for category in CatalogCategory.objects.filter(parent__isnull=True):
        title = (category.title or '').lower()
        branding_key = 'catalog'
        if 'пожар' in title:
            branding_key = 'pozharnaya-bezopasnost'
        elif 'эколог' in title:
            branding_key = 'ekologiya'
        elif 'аттестац' in title:
            branding_key = 'arm'
        elif ('охран' in title and 'труд' in title) or 'журнал' in title:
            branding_key = 'okhrana-truda'
        elif 'инженер' in title or 'проект' in title or 'монтаж' in title or 'эксперт' in title:
            branding_key = 'promyshlennaya-bezopasnost'
        CatalogCategory.objects.filter(pk=category.pk).update(branding=branding_by_key[branding_key])


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0017_smtpsettings'),
    ]

    operations = [
        migrations.CreateModel(
            name='SectionBranding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='Название пресета')),
                ('key', models.SlugField(max_length=80, unique=True, verbose_name='Ключ')),
                ('title', models.CharField(max_length=160, verbose_name='Заголовок в логотипе')),
                ('subtitle', models.CharField(blank=True, max_length=255, verbose_name='Подзаголовок в логотипе')),
                ('icon_name', models.CharField(choices=[('shield', 'Щит'), ('fire', 'Пожар'), ('factory', 'Промышленность'), ('leaf', 'Экология'), ('briefcase', 'Портфель'), ('lifebuoy', 'Спасательный круг'), ('question', 'Вопрос'), ('box', 'Коробка'), ('folder', 'Папка')], default='shield', max_length=30, verbose_name='Иконка')),
                ('logo_image', models.ImageField(blank=True, null=True, upload_to='uploads/branding/', verbose_name='Картинка логотипа')),
                ('theme_color', models.CharField(choices=[('blue', 'Синий'), ('red', 'Красный'), ('orange', 'Оранжевый'), ('green', 'Зеленый'), ('purple', 'Фиолетовый'), ('gray', 'Серый'), ('indigo', 'Индиго')], default='blue', max_length=20, verbose_name='Цвет темы')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
            ],
            options={
                'verbose_name': 'Брендинг раздела',
                'verbose_name_plural': 'Брендинг разделов',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.AddField(
            model_name='category',
            name='branding',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='content_categories', to='content.sectionbranding', verbose_name='Брендинг шапки'),
        ),
        migrations.AddField(
            model_name='catalogcategory',
            name='branding',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='catalog_categories', to='content.sectionbranding', verbose_name='Брендинг шапки'),
        ),
        migrations.RunPython(seed_section_branding, migrations.RunPython.noop),
    ]
