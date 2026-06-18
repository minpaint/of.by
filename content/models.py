import html
import re
from pathlib import Path

from django.conf import settings
from django.db import models
from django.templatetags.static import static
from django.utils.text import slugify
from django_ckeditor_5.fields import CKEditor5Field

_HTML_TAG_RE = re.compile(r'<[^>]+>')


def repair_text(value):
    if not value or not isinstance(value, str):
        return value
    try:
        repaired = value.encode('cp1251').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        repaired = value
    repaired = _HTML_TAG_RE.sub('', repaired)
    repaired = html.unescape(repaired)
    repaired = repaired.replace('\xa0', ' ').strip()
    return repaired


_asset_cache: dict = {}

def first_existing_generated_asset(*relative_paths):
    if relative_paths in _asset_cache:
        return _asset_cache[relative_paths]
    for relative_path in relative_paths:
        full_path = Path(settings.BASE_DIR) / 'static' / relative_path.replace('/', '\\')
        if full_path.exists():
            result = static(relative_path)
            _asset_cache[relative_paths] = result
            return result
    result = static(relative_paths[-1])
    _asset_cache[relative_paths] = result
    return result


TRANSLIT_MAP = str.maketrans(
    {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'і': 'i', 'ї': 'yi', 'є': 'e',
        'А': 'a', 'Б': 'b', 'В': 'v', 'Г': 'g', 'Д': 'd', 'Е': 'e', 'Ё': 'e',
        'Ж': 'zh', 'З': 'z', 'И': 'i', 'Й': 'y', 'К': 'k', 'Л': 'l', 'М': 'm',
        'Н': 'n', 'О': 'o', 'П': 'p', 'Р': 'r', 'С': 's', 'Т': 't', 'У': 'u',
        'Ф': 'f', 'Х': 'h', 'Ц': 'ts', 'Ч': 'ch', 'Ш': 'sh', 'Щ': 'sch',
        'Ъ': '', 'Ы': 'y', 'Ь': '', 'Э': 'e', 'Ю': 'yu', 'Я': 'ya',
        'І': 'i', 'Ї': 'yi', 'Є': 'e',
    }
)


def translit_slug(value):
    normalized = repair_text(value or '')
    transliterated = normalized.translate(TRANSLIT_MAP)
    return slugify(transliterated, allow_unicode=False)


def build_unique_slug(model, field_name, base_value, instance_pk=None):
    base_slug = translit_slug(base_value) or 'material'
    candidate = base_slug
    counter = 2
    manager = model._default_manager

    while True:
        lookup = {field_name: candidate}
        qs = manager.filter(**lookup)
        if instance_pk is not None:
            qs = qs.exclude(pk=instance_pk)
        if not qs.exists():
            return candidate
        candidate = f'{base_slug}-{counter}'
        counter += 1

class SectionBranding(models.Model):
    ICON_CHOICES = [
        ('shield', 'Щит'),
        ('fire', 'Пожар'),
        ('factory', 'Промышленность'),
        ('leaf', 'Экология'),
        ('briefcase', 'Портфель'),
        ('lifebuoy', 'Спасательный круг'),
        ('question', 'Вопрос'),
        ('box', 'Коробка'),
        ('folder', 'Папка'),
    ]

    COLOR_CHOICES = [
        ('blue', 'Синий'),
        ('red', 'Красный'),
        ('orange', 'Оранжевый'),
        ('green', 'Зеленый'),
        ('purple', 'Фиолетовый'),
        ('gray', 'Серый'),
        ('indigo', 'Индиго'),
    ]

    name = models.CharField('Название пресета', max_length=120)
    key = models.SlugField('Ключ', max_length=80, unique=True)
    title = models.CharField('Заголовок в логотипе', max_length=160)
    subtitle = models.CharField('Подзаголовок в логотипе', max_length=255, blank=True)
    icon_name = models.CharField('Иконка', max_length=30, choices=ICON_CHOICES, default='shield')
    logo_image = models.ImageField('Картинка логотипа', upload_to='uploads/branding/', blank=True, null=True)
    theme_color = models.CharField('Цвет темы', max_length=20, choices=COLOR_CHOICES, default='blue')
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Брендинг раздела'
        verbose_name_plural = 'Брендинг разделов'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    @property
    def icon_asset_url(self):
        return static(f'img/icons/{self.icon_name}.svg')

    @property
    def logo_asset_url(self):
        if self.logo_image:
            return self.logo_image.url
        return self.icon_asset_url


class Category(models.Model):
    LEGACY_PUBLIC_SLUGS = {
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

    COLOR_CHOICES = [
        ('blue', 'Синий (Охрана труда)'),
        ('red', 'Красный (Пожарная безопасность)'),
        ('orange', 'Оранжевый (Промышленная безопасность)'),
        ('green', 'Зеленый (Экология)'),
        ('purple', 'Фиолетовый (АРМ)'),
        ('gray', 'Серый (ГО)'),
        ('indigo', 'Индиго (Вопрос-ответ)'),
    ]

    FALLBACK_TITLES = {
        'okhrana-truda': 'Охрана труда',
        'pozharnaya-bezopasnost': 'Пожарная безопасность',
        'promyshlennaya-bezopasnost': 'Промышленная безопасность',
        'ekologiya': 'Экология',
        'arm': 'АРМ',
        'grazhdanskaya-oborona': 'Гражданская оборона',
        'vopros-otvet': 'Вопрос-ответ',
    }

    SHORT_TITLES = {
        'okhrana-truda': 'Охрана труда',
        'pozharnaya-bezopasnost': 'Пожбез',
        'promyshlennaya-bezopasnost': 'Промбез',
        'ekologiya': 'Экология',
        'arm': 'АРМ',
        'grazhdanskaya-oborona': 'ГО',
        'vopros-otvet': 'Вопрос-ответ',
    }

    FALLBACK_DESCRIPTIONS = {
        'okhrana-truda': 'Документы, инструкции и статьи по охране труда.',
        'pozharnaya-bezopasnost': 'Материалы по пожарной безопасности и профилактике.',
        'promyshlennaya-bezopasnost': 'Нормативные материалы по промышленной безопасности.',
        'ekologiya': 'Документы и статьи по охране окружающей среды.',
        'arm': 'Материалы по аттестации рабочих мест.',
        'grazhdanskaya-oborona': 'Материалы по гражданской обороне и ЧС.',
        'vopros-otvet': 'Подборка ответов на практические вопросы специалистов.',
    }

    FALLBACK_ICONS = {
        'okhrana-truda': 'ОТ',
        'pozharnaya-bezopasnost': 'ПБ',
        'promyshlennaya-bezopasnost': 'ПР',
        'ekologiya': 'ЭК',
        'arm': 'АРМ',
        'grazhdanskaya-oborona': 'ГО',
        'vopros-otvet': 'QA',
    }

    title = models.CharField('Название', max_length=200)
    slug = models.SlugField('Слаг', max_length=200, unique=True, allow_unicode=True)
    public_slug = models.SlugField('Публичный URL', max_length=200, unique=True, blank=True, null=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительская категория',
    )
    branding = models.ForeignKey(
        SectionBranding,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='content_categories',
        verbose_name='Брендинг шапки',
    )
    related_categories = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        verbose_name='Родственные категории',
    )
    color = models.CharField('Цвет', max_length=20, choices=COLOR_CHOICES, default='blue')
    icon = models.CharField('Иконка (emoji)', max_length=10, blank=True, default='📋')
    description = models.TextField('Описание', blank=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.display_title

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse('section', kwargs={'slug': self.resolved_public_slug})

    @property
    def resolved_public_slug(self):
        return self.public_slug or self.LEGACY_PUBLIC_SLUGS.get(self.slug, self.slug)

    @property
    def display_title(self):
        return self.FALLBACK_TITLES.get(self.slug, repair_text(self.title))

    @property
    def tree_title(self):
        depth = 0
        current = self.parent
        while current is not None:
            depth += 1
            current = current.parent
        return f'{"— " * depth}{self.display_title}'

    @property
    def display_description(self):
        return self.FALLBACK_DESCRIPTIONS.get(self.slug, repair_text(self.description))

    @property
    def display_icon(self):
        return self.FALLBACK_ICONS.get(self.slug, repair_text(self.icon) or '📁')

    @property
    def short_title(self):
        return self.SHORT_TITLES.get(self.slug, self.display_title)

    @property
    def icon_asset_url(self):
        icon_name = {
            'okhrana-truda': 'shield',
            'pozharnaya-bezopasnost': 'fire',
            'promyshlennaya-bezopasnost': 'factory',
            'ekologiya': 'leaf',
            'arm': 'briefcase',
            'grazhdanskaya-oborona': 'lifebuoy',
            'vopros-otvet': 'question',
        }.get(self.slug, 'folder')
        return static(f'img/icons/{icon_name}.svg')

    @property
    def resolved_branding(self):
        current = self
        while current is not None:
            if current.branding_id and current.branding and current.branding.is_active:
                return current.branding
            current = current.parent
        return None


class ContentItem(models.Model):
    TYPE_CHOICES = [
        ('article', 'Статья'),
        ('instruction', 'Инструкция'),
        ('document', 'Документ'),
        ('video', 'Видео'),
        ('webinar', 'Вебинар'),
        ('event', 'Событие'),
        ('product', 'Товар/услуга'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('published', 'Опубликовано'),
        ('archived', 'Архив'),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Категория',
        related_name='items',
    )
    content_type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES, default='article')
    title = models.CharField('Заголовок', max_length=500)
    slug = models.SlugField('Слаг', max_length=500, unique=True, allow_unicode=True)
    public_slug = models.SlugField('Публичный URL', max_length=500, unique=True, blank=True, null=True)
    excerpt = models.TextField('Краткое описание', blank=True)
    content = CKEditor5Field('Содержимое', config_name='default', blank=True)
    image = models.ImageField('Изображение', upload_to='uploads/images/', blank=True, null=True)
    video_url = models.URLField('Ссылка на видео (YouTube)', blank=True)
    file = models.FileField('Файл', upload_to='uploads/files/', blank=True, null=True)
    file_title = models.CharField('Название файла', max_length=300, blank=True)
    author = models.CharField('Автор', max_length=200, blank=True)
    views = models.PositiveIntegerField('Просмотры', default=0)
    is_featured = models.BooleanField('В избранном', default=False)
    is_main_slider = models.BooleanField('В главном слайдере', default=False)
    published_date = models.DateTimeField('Дата публикации', null=True, blank=True)
    event_date = models.DateTimeField('Дата события', null=True, blank=True)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2, null=True, blank=True)
    tags = models.CharField('Теги', max_length=500, blank=True)
    seo_title = models.CharField('SEO заголовок', max_length=200, blank=True)
    seo_description = models.TextField('SEO описание', blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Изменено', auto_now=True)

    class Meta:
        verbose_name = 'Материал'
        verbose_name_plural = 'Материалы'
        ordering = ['-published_date', '-created_at']
        indexes = [
            models.Index(fields=['status', 'published_date']),
            models.Index(fields=['status', 'category', 'published_date']),
            models.Index(fields=['status', 'content_type', 'published_date']),
            models.Index(fields=['status', 'is_main_slider', 'published_date']),
            models.Index(fields=['status', 'is_featured', 'published_date']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        generated_slug = build_unique_slug(ContentItem, 'slug', self.title, self.pk)
        generated_public_slug = build_unique_slug(ContentItem, 'public_slug', self.title, self.pk)
        if not self.slug:
            self.slug = generated_slug
        if not self.public_slug:
            self.public_slug = generated_public_slug
        if not self.seo_title:
            self.seo_title = repair_text(self.title)
        super().save(*args, **kwargs)

    @property
    def display_title(self):
        return repair_text(self.title)

    @property
    def display_excerpt(self):
        return repair_text(self.excerpt)

    @property
    def display_author(self):
        return repair_text(self.author)

    @property
    def display_file_title(self):
        return repair_text(self.file_title)

    @property
    def display_tags(self):
        return repair_text(self.tags)

    @property
    def normalized_content_type(self):
        if self.content_type in {'instruction', 'document'}:
            return 'article'
        if self.content_type == 'webinar':
            return 'event'
        return self.content_type

    @property
    def display_type_badge(self):
        return {
            'video': 'Видео',
            'event': 'Событие',
        }.get(self.normalized_content_type, '')

    @property
    def fallback_image_url(self):
        if self.category:
            art_name = {
                'okhrana-truda': 'safety-hero',
                'pozharnaya-bezopasnost': 'fire-briefing',
                'promyshlennaya-bezopasnost': 'industrial-site',
                'ekologiya': 'eco-report',
                'arm': 'workplace-audit',
                'grazhdanskaya-oborona': 'civil-defense',
                'vopros-otvet': 'safety-qa',
            }.get(self.category.slug)
            if art_name:
                return first_existing_generated_asset(
                    f'img/generated/{art_name}.jpg',
                    f'img/generated/{art_name}.jpeg',
                    f'img/generated/{art_name}.png',
                    f'img/generated/{art_name}.webp',
                    f'img/generated/{art_name}.svg',
                )
        return first_existing_generated_asset(
            'img/generated/safety-hero.jpg',
            'img/generated/safety-hero.jpeg',
            'img/generated/safety-hero.png',
            'img/generated/safety-hero.webp',
            'img/generated/safety-hero.svg',
        )

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse('content_detail_public', kwargs={'slug': self.resolved_public_slug})

    @property
    def resolved_public_slug(self):
        return self.public_slug or self.slug

    def get_youtube_embed_url(self):
        url = self.video_url
        if not url:
            return ''
        if 'youtu.be/' in url:
            vid = url.split('youtu.be/')[-1].split('?')[0]
            return f'https://www.youtube.com/embed/{vid}'
        if 'watch?v=' in url:
            vid = url.split('watch?v=')[-1].split('&')[0]
            return f'https://www.youtube.com/embed/{vid}'
        return url

    def get_youtube_thumbnail(self):
        url = self.video_url
        if not url:
            return ''
        if 'youtu.be/' in url:
            vid = url.split('youtu.be/')[-1].split('?')[0]
        elif 'watch?v=' in url:
            vid = url.split('watch?v=')[-1].split('&')[0]
        else:
            return ''
        return f'https://img.youtube.com/vi/{vid}/hqdefault.jpg'


class ContentFeedBlock(models.Model):
    PLACEMENT_HOME = 'home'
    PLACEMENT_SECTION = 'section'
    PLACEMENT_HOME_SLIDER = 'home_slider'
    PLACEMENT_CHOICES = [
        (PLACEMENT_HOME, 'Главная страница'),
        (PLACEMENT_SECTION, 'Страница раздела'),
        (PLACEMENT_HOME_SLIDER, 'Главный слайдер'),
    ]

    CONTENT_TYPE_CHOICES = [
        ('article', 'Статьи'),
        ('instruction', 'Инструкции'),
        ('document', 'Документы'),
        ('video', 'Видео'),
        ('webinar', 'Вебинары'),
        ('event', 'События'),
    ]

    name = models.CharField('Название блока', max_length=200)
    placement = models.CharField('Где показывать', max_length=20, choices=PLACEMENT_CHOICES, default=PLACEMENT_HOME)
    target_category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='target_feed_blocks',
        verbose_name='Раздел показа',
        null=True,
        blank=True,
        help_text='Для блока на странице раздела выберите раздел, внутри которого этот блок должен отображаться.',
    )
    source_category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='source_feed_blocks',
        verbose_name='Категория-источник',
        null=True,
        blank=True,
        help_text='Из этой категории будут подбираться материалы для блока.',
    )
    display_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='display_feed_blocks',
        verbose_name='Категория в заголовке',
        null=True,
        blank=True,
        help_text='Необязательно. Если указать, её название, цвет и иконка будут использованы в оформлении блока.',
    )
    title = models.CharField(
        'Заголовок блока',
        max_length=200,
        blank=True,
        help_text='Если оставить пустым, будет использовано название категории в заголовке.',
    )
    link_text = models.CharField('Текст ссылки', max_length=100, blank=True, default='Все материалы')
    content_types = models.CharField(
        'Типы материалов',
        max_length=200,
        blank=True,
        help_text='Внутреннее поле. Выбирается через список в админке.',
    )
    include_child_categories = models.BooleanField(
        'Включать подкатегории',
        default=True,
        help_text='Если включено, в блок попадут материалы из выбранной категории и всех её дочерних разделов.',
    )
    item_limit = models.PositiveSmallIntegerField(
        'Количество материалов',
        default=8,
        help_text='Общее количество материалов в блоке, включая главный материал.',
    )
    secondary_item_limit = models.PositiveSmallIntegerField(
        'Количество карточек "Другие новости"',
        default=4,
        help_text='Используется только для блока "Главный слайдер" на главной странице.',
    )
    exclude_main_slider_items = models.BooleanField(
        'Не брать материалы главного слайдера',
        default=True,
        help_text='Полезно для главной страницы, чтобы один и тот же материал не повторялся в разных блоках.',
    )
    hide_if_empty = models.BooleanField(
        'Скрывать пустой блок',
        default=True,
        help_text='Если подходящих материалов нет, блок не будет показан.',
    )
    is_active = models.BooleanField('Активен', default=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Блок вывода материалов'
        verbose_name_plural = 'Блоки вывода материалов'
        ordering = ['placement', 'sort_order', 'id']

    def __str__(self):
        return repair_text(self.name)

    @property
    def content_type_list(self):
        return [value for value in (self.content_types or '').split(',') if value]

    @property
    def resolved_source_category(self):
        return self.source_category or self.target_category

    @property
    def resolved_display_category(self):
        return self.display_category or self.source_category or self.target_category

    @property
    def resolved_title(self):
        if self.title:
            return repair_text(self.title)
        category = self.resolved_display_category
        if category:
            return category.display_title
        return repair_text(self.name)

    @property
    def resolved_url(self):
        category = self.resolved_display_category or self.resolved_source_category
        if category:
            return category.get_absolute_url()
        return '#'


class Banner(models.Model):
    PLACEMENT_HEADER = 'header'
    PLACEMENT_SECTION = 'section'
    PLACEMENT_SIDEBAR = 'sidebar'
    PLACEMENT_CHOICES = [
        (PLACEMENT_HEADER, 'Шапка сайта (правый блок)'),
        (PLACEMENT_SECTION, 'Блок раздела на главной'),
        (PLACEMENT_SIDEBAR, 'Сайдбар статьи (sticky)'),
    ]

    placement = models.CharField(
        'Место размещения',
        max_length=20,
        choices=PLACEMENT_CHOICES,
        default=PLACEMENT_SECTION,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        verbose_name='Раздел',
        related_name='banners',
        null=True,
        blank=True,
        help_text='Для баннера в шапке оставьте поле пустым. Для баннера раздела выберите раздел.',
    )
    title = models.CharField('Заголовок баннера', max_length=200)
    subtitle = models.CharField('Подзаголовок / CTA', max_length=300, blank=True)
    image = models.ImageField(
        'Картинка баннера',
        upload_to='uploads/banners/',
        blank=True,
        null=True,
        help_text='Шапка: 520x80 px. Раздел: 900x100 px. Сайдбар статьи: ~680px по ширине (горизонтальный баннер).',
    )
    url = models.CharField('Ссылка (URL)', max_length=500, blank=True)
    is_active = models.BooleanField('Активен', default=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Баннер'
        verbose_name_plural = 'Баннеры'
        ordering = ['sort_order', 'id']

    def __str__(self):
        cat = repair_text(self.category.title) if self.category else 'глобальный'
        return f'{self.title} [{cat}]'


class CatalogCategory(models.Model):
    title = models.CharField('Название', max_length=255)
    slug = models.SlugField('Служебный слаг', max_length=255, unique=True, allow_unicode=True)
    public_slug = models.SlugField('Публичный URL', max_length=255, unique=True, allow_unicode=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительская категория',
    )
    branding = models.ForeignKey(
        SectionBranding,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='catalog_categories',
        verbose_name='Брендинг шапки',
    )
    description = models.TextField('Описание', blank=True)
    seo_title = models.CharField('SEO заголовок', max_length=255, blank=True)
    seo_description = models.TextField('SEO описание', blank=True)
    heading = models.CharField('Заголовок страницы', max_length=255, blank=True)
    image = models.ImageField('Изображение', upload_to='uploads/catalog/categories/', blank=True, null=True)
    legacy_id = models.PositiveIntegerField('ID в старой базе', unique=True, db_index=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активна', default=True)
    created_at = models.DateTimeField('Создано', null=True, blank=True)
    updated_at = models.DateTimeField('Изменено', null=True, blank=True)

    class Meta:
        verbose_name = 'Категория каталога'
        verbose_name_plural = 'Категории каталога'
        ordering = ['sort_order', 'title']

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return repair_text(self.title)

    @property
    def display_description(self):
        return repair_text(self.description)

    @property
    def display_heading(self):
        return repair_text(self.heading) or self.display_title

    @property
    def resolved_seo_title(self):
        return repair_text(self.seo_title) or self.display_title

    @property
    def resolved_seo_description(self):
        return repair_text(self.seo_description) or self.display_description

    @property
    def icon_asset_url(self):
        probe = f'{self.root.display_title if self.parent_id else self.display_title} {self.display_title}'.lower()
        if 'пожар' in probe:
            icon_name = 'fire'
        elif 'эколог' in probe:
            icon_name = 'leaf'
        elif 'инженер' in probe or 'проект' in probe or 'монтаж' in probe:
            icon_name = 'factory'
        elif 'аттестац' in probe:
            icon_name = 'briefcase'
        elif 'журнал' in probe:
            icon_name = 'folder'
        else:
            icon_name = 'shield'
        return static(f'img/icons/{icon_name}.svg')

    @property
    def root(self):
        node = self
        while node.parent_id:
            node = node.parent
        return node

    @property
    def tree_title(self):
        depth = 0
        current = self.parent
        while current is not None:
            depth += 1
            current = current.parent
        return f'{"— " * depth}{self.display_title}'

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse('catalog_category', kwargs={'slug': self.public_slug})

    @property
    def resolved_branding(self):
        current = self
        while current is not None:
            if current.branding_id and current.branding and current.branding.is_active:
                return current.branding
            current = current.parent
        return None


class CatalogItem(models.Model):
    category = models.ForeignKey(
        CatalogCategory,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Категория',
    )
    title = models.CharField('Название', max_length=500)
    slug = models.SlugField('Служебный слаг', max_length=500, unique=True, allow_unicode=True)
    public_slug = models.SlugField('Публичный URL', max_length=500, db_index=True, allow_unicode=True)
    excerpt = models.TextField('Краткое описание', blank=True)
    content = CKEditor5Field('Описание', config_name='default', blank=True)
    image = models.ImageField('Основное изображение', upload_to='uploads/catalog/items/', blank=True, null=True)
    sku = models.CharField('Артикул', max_length=120, blank=True)
    price = models.DecimalField('Цена', max_digits=12, decimal_places=2, null=True, blank=True)
    special_price = models.DecimalField('Спеццена', max_digits=12, decimal_places=2, null=True, blank=True)
    address = models.CharField('Адрес', max_length=500, blank=True)
    city = models.CharField('Город', max_length=120, blank=True)
    postcode = models.CharField('Индекс', max_length=30, blank=True)
    phone = models.CharField('Телефон', max_length=120, blank=True)
    mobile = models.CharField('Мобильный', max_length=120, blank=True)
    fax = models.CharField('Факс', max_length=120, blank=True)
    website = models.URLField('Сайт', blank=True)
    email = models.EmailField('Email', blank=True)
    is_available = models.BooleanField('Доступен', default=True)
    is_featured = models.BooleanField('Рекомендуемый', default=False)
    views = models.PositiveIntegerField('Просмотры', default=0)
    seo_title = models.CharField('SEO заголовок', max_length=255, blank=True)
    seo_description = models.TextField('SEO описание', blank=True)
    legacy_id = models.PositiveIntegerField('ID в старой базе', unique=True, db_index=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активен', default=True)
    published_date = models.DateTimeField('Дата публикации', null=True, blank=True)
    created_at = models.DateTimeField('Создано', null=True, blank=True)
    updated_at = models.DateTimeField('Изменено', null=True, blank=True)

    class Meta:
        verbose_name = 'Позиция каталога'
        verbose_name_plural = 'Позиции каталога'
        ordering = ['sort_order', 'title']
        indexes = [
            models.Index(fields=['category', 'public_slug']),
            models.Index(fields=['is_active', 'views']),
        ]

    def __str__(self):
        return self.display_title

    @property
    def display_title(self):
        return repair_text(self.title)

    @property
    def display_excerpt(self):
        return repair_text(self.excerpt)

    @property
    def resolved_seo_title(self):
        return repair_text(self.seo_title) or self.display_title

    @property
    def resolved_seo_description(self):
        return repair_text(self.seo_description) or self.display_excerpt

    @property
    def display_price(self):
        return self.special_price or self.price

    @property
    def fallback_image_url(self):
        if self.image:
            return self.image.url
        if self.category and self.category.image:
            return self.category.image.url
        return first_existing_generated_asset(
            'img/generated/safety-hero.jpg',
            'img/generated/safety-hero.jpeg',
            'img/generated/safety-hero.png',
            'img/generated/safety-hero.webp',
            'img/generated/safety-hero.svg',
        )

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse(
            'catalog_item_detail',
            kwargs={'category_slug': self.category.public_slug, 'slug': self.public_slug},
        )


class CatalogItemImage(models.Model):
    item = models.ForeignKey(
        CatalogItem,
        on_delete=models.CASCADE,
        related_name='gallery_images',
        verbose_name='Позиция каталога',
    )
    image = models.ImageField('Изображение', upload_to='uploads/catalog/items/gallery/')
    caption = models.CharField('Подпись', max_length=255, blank=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Изображение позиции каталога'
        verbose_name_plural = 'Изображения позиций каталога'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.caption or self.image.name


class CatalogItemFile(models.Model):
    item = models.ForeignKey(
        CatalogItem,
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Позиция каталога',
    )
    file = models.FileField('Файл', upload_to='uploads/catalog/files/')
    title = models.CharField('Название', max_length=255, blank=True)
    sort_order = models.PositiveIntegerField('Порядок', default=0)
    downloads = models.PositiveIntegerField('Скачивания', default=0)

    class Meta:
        verbose_name = 'Файл позиции каталога'
        verbose_name_plural = 'Файлы позиций каталога'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.title or Path(self.file.name).name


class LegacyRedirect(models.Model):
    old_path = models.CharField('Старый путь', max_length=1024, unique=True, db_index=True)
    new_path = models.CharField('Новый путь', max_length=1024)

    class Meta:
        verbose_name = 'Legacy redirect'
        verbose_name_plural = 'Legacy redirects'
        ordering = ['old_path']

    def __str__(self):
        return f'{self.old_path} -> {self.new_path}'


class LeadSettings(models.Model):
    title = models.CharField('Название', max_length=120, default='Настройки заявок')
    recipient_email = models.EmailField('Email для заявок', blank=True)
    sender_name = models.CharField('Подпись отправителя', max_length=255, blank=True)
    success_message = models.CharField(
        'Сообщение после отправки',
        max_length=255,
        blank=True,
        default='Спасибо! Ваша заявка отправлена. Мы свяжемся с вами в ближайшее время.',
    )
    is_active = models.BooleanField('Активно', default=True)
    updated_at = models.DateTimeField('Изменено', auto_now=True)

    class Meta:
        verbose_name = 'Настройки заявок'
        verbose_name_plural = 'Настройки заявок'

    def __str__(self):
        return self.title or 'Настройки заявок'


class SmtpSettings(models.Model):
    title = models.CharField('Название', max_length=120, default='Настройки SMTP')
    host = models.CharField('SMTP хост', max_length=255)
    port = models.PositiveIntegerField('SMTP порт', default=587)
    username = models.CharField('Имя пользователя', max_length=255, blank=True)
    password = models.CharField('Пароль', max_length=255, blank=True) # Note: Consider encrypted fields for production
    use_tls = models.BooleanField('Использовать TLS', default=True)
    use_ssl = models.BooleanField('Использовать SSL', default=False)
    is_active = models.BooleanField('Активно', default=False)
    updated_at = models.DateTimeField('Изменено', auto_now=True)

    class Meta:
        verbose_name = 'Настройки SMTP'
        verbose_name_plural = 'Настройки SMTP'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.is_active:
            # Ensure only one setting is active at a time
            SmtpSettings.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)
