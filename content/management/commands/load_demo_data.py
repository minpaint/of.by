from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from content.models import Category, ContentItem


CATEGORIES = [
    {
        'title': 'Охрана труда',
        'slug': 'okhrana-truda',
        'color': 'blue',
        'icon': '🛡️',
        'sort_order': 1,
        'description': 'Документы, инструкции и статьи по охране труда.',
    },
    {
        'title': 'Пожарная безопасность',
        'slug': 'pozharnaya-bezopasnost',
        'color': 'red',
        'icon': '🔥',
        'sort_order': 2,
        'description': 'Практические материалы по пожарной безопасности.',
    },
    {
        'title': 'Промышленная безопасность',
        'slug': 'promyshlennaya-bezopasnost',
        'color': 'orange',
        'icon': '🏭',
        'sort_order': 3,
        'description': 'Материалы для специалистов по промышленной безопасности.',
    },
    {
        'title': 'Экология',
        'slug': 'ekologiya',
        'color': 'green',
        'icon': '🌿',
        'sort_order': 4,
        'description': 'Нормативные и практические материалы по экологии.',
    },
    {
        'title': 'АРМ',
        'slug': 'arm',
        'color': 'purple',
        'icon': '💼',
        'sort_order': 5,
        'description': 'Материалы по аттестации рабочих мест.',
    },
    {
        'title': 'Гражданская оборона',
        'slug': 'grazhdanskaya-oborona',
        'color': 'gray',
        'icon': '🛟',
        'sort_order': 6,
        'description': 'Материалы по гражданской обороне и чрезвычайным ситуациям.',
    },
    {
        'title': 'Вопрос-ответ',
        'slug': 'vopros-otvet',
        'color': 'indigo',
        'icon': '❓',
        'sort_order': 7,
        'description': 'Подборка ответов на практические вопросы специалистов.',
    },
]

ITEMS = [
    {
        'category_slug': 'okhrana-truda',
        'title': 'Новые требования к инструктажам по охране труда',
        'excerpt': 'Краткий обзор изменений в порядке проведения инструктажей и проверке знаний.',
        'content_type': 'article',
        'is_featured': True,
        'is_main_slider': True,
    },
    {
        'category_slug': 'okhrana-truda',
        'title': 'Типовая инструкция по охране труда для офисных работников',
        'excerpt': 'Готовый шаблон инструкции для работников, использующих персональные компьютеры.',
        'content_type': 'instruction',
        'is_featured': True,
    },
    {
        'category_slug': 'okhrana-truda',
        'title': 'Постановление по общим требованиям охраны труда',
        'excerpt': 'Сводный документ с базовыми требованиями к организации безопасных работ.',
        'content_type': 'document',
        'is_main_slider': True,
    },
    {
        'category_slug': 'okhrana-truda',
        'title': 'Вебинар по организации работы службы охраны труда',
        'excerpt': 'Практический вебинар для специалистов и инженеров по охране труда.',
        'content_type': 'webinar',
        'video_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    },
    {
        'category_slug': 'okhrana-truda',
        'title': 'Программа подготовки к проверке знаний',
        'excerpt': 'Учебный продукт для подготовки специалистов по охране труда.',
        'content_type': 'product',
        'price': 120.00,
    },
    {
        'category_slug': 'pozharnaya-bezopasnost',
        'title': 'Требования пожарной безопасности к офисным помещениям',
        'excerpt': 'Разбор актуальных норм и типовых нарушений для административных зданий.',
        'content_type': 'article',
        'is_featured': True,
        'is_main_slider': True,
    },
    {
        'category_slug': 'pozharnaya-bezopasnost',
        'title': 'Инструкция о мерах пожарной безопасности в организации',
        'excerpt': 'Шаблон инструкции с основными пунктами для локального акта предприятия.',
        'content_type': 'instruction',
    },
    {
        'category_slug': 'promyshlennaya-bezopasnost',
        'title': 'Изменения в законодательстве по промышленной безопасности',
        'excerpt': 'Краткий обзор последних нормативных требований к опасным производственным объектам.',
        'content_type': 'article',
        'is_featured': True,
    },
    {
        'category_slug': 'ekologiya',
        'title': 'Экологический паспорт предприятия: порядок разработки',
        'excerpt': 'Пошаговое описание подготовки экологического паспорта организации.',
        'content_type': 'article',
        'is_featured': True,
        'is_main_slider': True,
    },
    {
        'category_slug': 'arm',
        'title': 'Аттестация рабочих мест: пошаговое руководство',
        'excerpt': 'Основные этапы подготовки и проведения аттестации рабочих мест.',
        'content_type': 'article',
        'is_featured': True,
    },
    {
        'category_slug': 'grazhdanskaya-oborona',
        'title': 'Гражданская оборона на предприятии: основные требования',
        'excerpt': 'Краткий обзор обязанностей и документации по гражданской обороне.',
        'content_type': 'article',
    },
    {
        'category_slug': 'vopros-otvet',
        'title': 'Когда нужен внеплановый инструктаж?',
        'excerpt': 'Ответ на один из самых частых практических вопросов специалистов.',
        'content_type': 'article',
        'is_featured': True,
    },
]


class Command(BaseCommand):
    help = 'Загружает демонстрационные категории и материалы для портала.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Удалить существующие данные перед загрузкой')

    def handle(self, *args, **options):
        if options['clear']:
            ContentItem.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING('Существующие данные удалены.'))

        category_map = {}
        for data in CATEGORIES:
            category, _ = Category.objects.update_or_create(
                slug=data['slug'],
                defaults={
                    'title': data['title'],
                    'color': data['color'],
                    'icon': data['icon'],
                    'sort_order': data['sort_order'],
                    'description': data['description'],
                    'is_active': True,
                },
            )
            category_map[data['slug']] = category

        created_count = 0
        for index, data in enumerate(ITEMS, start=1):
            base_slug = slugify(data['title']) or f'item-{index}'
            slug = base_slug
            suffix = 1
            while ContentItem.objects.exclude(title=data['title']).filter(slug=slug).exists():
                slug = f'{base_slug}-{suffix}'
                suffix += 1

            published_date = timezone.now() - timezone.timedelta(days=index * 3)

            _, created = ContentItem.objects.update_or_create(
                title=data['title'],
                defaults={
                    'category': category_map[data['category_slug']],
                    'slug': slug,
                    'excerpt': data['excerpt'],
                    'content': f"<p>{data['excerpt']}</p>",
                    'content_type': data['content_type'],
                    'video_url': data.get('video_url', ''),
                    'price': data.get('price'),
                    'is_featured': data.get('is_featured', False),
                    'is_main_slider': data.get('is_main_slider', False),
                    'status': 'published',
                    'published_date': published_date,
                    'views': 100 + index * 17,
                    'author': 'Редакция портала',
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Готово: обновлено {len(category_map)} категорий, создано {created_count} новых материалов.'
        ))
