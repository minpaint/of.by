from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.core.mail import send_mail # New import
from django.contrib import messages # New import
from django.views.decorators.cache import cache_page

from .forms import LeadForm # New import
from .models import (
    Banner,
    CatalogCategory,
    CatalogItem,
    Category,
    ContentFeedBlock,
    ContentItem,
    LegacyRedirect,
    LeadSettings, # New import
)


CONTENT_TYPE_LINKS = [
    ('event', 'События'),
    ('video', 'Видео'),
]

CATEGORY_CACHE_TTL = 300
NAV_CACHE_TTL = 300
CATALOG_CACHE_TTL = 300
BLOCK_CACHE_TTL = 300


def content_listing_queryset():
    return (
        ContentItem.objects.select_related('category')
        .defer('content', 'seo_description')
        .order_by('-published_date', '-id')
        .only(
            'id',
            'category',
            'content_type',
            'title',
            'slug',
            'public_slug',
            'excerpt',
            'image',
            'views',
            'published_date',
            'price',
            'category__id',
            'category__title',
            'category__slug',
            'category__public_slug',
            'category__parent_id',
            'category__color',
            'category__icon',
            'category__description',
            'category__sort_order',
            'category__is_active',
        )
    )


def collect_category_branch(category, all_categories):
    if category is None:
        return []

    by_parent = {}
    for item in all_categories:
        by_parent.setdefault(item.parent_id, []).append(item)

    branch = []
    seen = set()

    def add_node(node):
        if node.pk in seen:
            return
        seen.add(node.pk)
        branch.append(node)
        for child in by_parent.get(node.pk, []):
            add_node(child)

    add_node(category)
    return branch


def get_active_feed_blocks(placement, target_category=None):
    qs = (
        ContentFeedBlock.objects.filter(is_active=True, placement=placement)
        .select_related('target_category', 'source_category', 'display_category')
        .order_by('sort_order', 'id')
    )
    if placement == ContentFeedBlock.PLACEMENT_SECTION:
        qs = qs.filter(target_category=target_category)
    return list(qs)


def build_feed_block_queryset(block, all_categories):
    if block.resolved_source_category is None:
        return content_listing_queryset().none()
    qs = content_listing_queryset().filter(status='published')
    qs = filter_queryset_for_feed_block(qs, block, all_categories)
    return qs.exclude(content_type='product')


def filter_queryset_for_feed_block(qs, block, all_categories):
    source_category = block.resolved_source_category
    if source_category is not None:
        categories = [source_category]
        if block.include_child_categories:
            categories = collect_category_branch(source_category, all_categories)
        qs = qs.filter(category__in=categories)

    if block.content_type_list:
        normalized_types = []
        for value in block.content_type_list:
            if value in {'article', 'instruction', 'document'}:
                continue
            if value == 'webinar':
                value = 'event'
            if value not in normalized_types:
                normalized_types.append(value)
        if normalized_types:
            qs = qs.filter(content_type__in=normalized_types)
    return qs


def get_home_slider_block():
    cache_key = 'content:home_slider_block'
    block = cache.get(cache_key)
    if block is None:
        block = (
            ContentFeedBlock.objects.filter(
                placement=ContentFeedBlock.PLACEMENT_HOME_SLIDER,
                is_active=True,
            )
            .select_related('target_category', 'source_category', 'display_category')
            .order_by('sort_order', 'id')
            .first()
        )
        cache.set(cache_key, block, BLOCK_CACHE_TTL)
    return block


def build_homepage_feed_blocks(all_categories, excluded_ids):
    excluded_key = ','.join(str(pk) for pk in excluded_ids)
    cache_key = f'content:home_blocks:{excluded_key}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    active_blocks = get_active_feed_blocks(ContentFeedBlock.PLACEMENT_HOME)
    if not active_blocks:
        return []

    banner_map = {}
    for banner in Banner.objects.filter(is_active=True).select_related('category'):
        key = banner.category_id or '__global__'
        if key not in banner_map:
            banner_map[key] = banner

    blocks = []
    for block in active_blocks:
        qs = build_feed_block_queryset(block, all_categories)
        if excluded_ids and block.exclude_main_slider_items:
            qs = qs.exclude(pk__in=excluded_ids)
        limit = block.item_limit or 8
        items = list(qs[:limit])
        if not items and block.hide_if_empty:
            continue

        display_category = block.resolved_display_category
        blocks.append(
            {
                'config': block,
                'category': display_category,
                'title': block.resolved_title,
                'url': block.resolved_url,
                'lead': items[0] if items else None,
                'latest': items[1:],
                'documents': [],
                'banner': banner_map.get(getattr(display_category, 'pk', None)) or banner_map.get('__global__'),
            }
        )
    cache.set(cache_key, blocks, BLOCK_CACHE_TTL)
    return blocks


def build_section_feed_blocks(category, all_categories, excluded_ids):
    excluded_key = ','.join(str(pk) for pk in excluded_ids)
    cache_key = f'content:section_blocks:{category.pk}:{excluded_key}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    blocks = []
    for block in get_active_feed_blocks(ContentFeedBlock.PLACEMENT_SECTION, target_category=category):
        qs = build_feed_block_queryset(block, all_categories)
        if block.exclude_main_slider_items and excluded_ids:
            qs = qs.exclude(pk__in=excluded_ids)
        items = list(qs[: block.item_limit or 6])
        if not items and block.hide_if_empty:
            continue

        display_category = block.resolved_display_category
        blocks.append(
            {
                'config': block,
                'category': display_category,
                'title': block.resolved_title,
                'url': block.resolved_url,
                'lead': items[0] if items else None,
                'items': items[1:],
            }
        )
    cache.set(cache_key, blocks, BLOCK_CACHE_TTL)
    return blocks

CATALOG_SECTIONS = [
    {
        'slug': 'fire-services',
        'title': 'Услуги по пожарной безопасности',
        'subtitle': 'Аудиты, аутсорсинг, разработка документации, изготовление планов эвакуации и сопровождение при проверках.',
        'image': '/static/img/generated/fire-briefing.svg',
        'accent': 'fire',
        'items': [
            {
                'title': 'Аудит пожарной безопасности объекта',
                'description': 'Оценка пожарного состояния объекта, выявление рисков и подготовка практических рекомендаций.',
            },
            {
                'title': 'Аутсорсинг пожарной безопасности (функции инженера по ПБ)',
                'description': 'Передача функций по организации пожарной безопасности на сопровождение профильным специалистам.',
            },
            {
                'title': 'Обучение ПТМ, проведение инструктажей',
                'description': 'Подготовка сотрудников по программам пожарно-технического минимума и проведение инструктажей.',
            },
            {
                'title': 'Подготовка документации по обеспечению противопожарного режима',
                'description': 'Разработка полного комплекта локальных документов с учетом специфики предприятия.',
            },
            {
                'title': 'Представление интересов заказчика в органах МЧС и при проверках',
                'description': 'Сопровождение при взаимодействии с контролирующими органами и защита позиции заказчика.',
            },
            {
                'title': 'Испытания пожарных лестниц и ограждений крыш',
                'description': 'Проведение испытаний аккредитованной лабораторией с оформлением необходимой документации.',
            },
            {
                'title': 'Проверка технического состояния пожарных кранов и гидрантов',
                'description': 'Проверка работоспособности, ревизия узлов, перекатка рукавов и сервисное обслуживание.',
            },
            {
                'title': 'Разработка и изготовление планов эвакуации',
                'description': 'Подготовка и выпуск планов эвакуации для зданий и помещений любой сложности.',
            },
            {
                'title': 'Стенды информационные',
                'description': 'Изготовление стендов по пожарной безопасности и смежной тематике в нужных форматах.',
            },
            {
                'title': 'Таблички и информационные знаки',
                'description': 'Производство указательных, запрещающих и предписывающих табличек и наклеек.',
            },
        ],
    },
    {
        'slug': 'engineering',
        'title': 'Проектирование, монтаж, пусконаладка',
        'subtitle': 'Комплексные инженерные решения для систем пожарной автоматики, безопасности, связи и вентиляции.',
        'image': '/static/img/generated/industrial-site.svg',
        'accent': 'industrial',
        'items': [
            {
                'title': 'Пожарная сигнализация',
                'description': 'Полный комплекс услуг по проектированию, монтажу и пусконаладочным работам систем пожарной сигнализации.',
            },
            {
                'title': 'Системы автоматического пожаротушения',
                'description': 'Разработка, монтаж и ввод в эксплуатацию систем пожаротушения под ключ.',
            },
            {
                'title': 'Охранная сигнализация',
                'description': 'Проектирование и запуск систем охранной сигнализации для объектов различного назначения.',
            },
            {
                'title': 'Системы видеонаблюдения',
                'description': 'Проектирование, монтаж и пусконаладка систем видеонаблюдения любой сложности.',
            },
            {
                'title': 'Системы контроля доступа и связи',
                'description': 'Организация пропускного режима, связи и контроля доступа от проекта до ввода в эксплуатацию.',
            },
            {
                'title': 'Системы дымоудаления и вентиляции',
                'description': 'Разработка и внедрение систем дымоудаления и вентиляции с согласованием в надзорных органах.',
            },
            {
                'title': 'Нанесение и восстановление огнезащитных составов',
                'description': 'Огнезащитная обработка конструкций и оформление сопроводительной документации.',
            },
        ],
    },
    {
        'slug': 'fire-products',
        'title': 'Продукция по пожарной безопасности',
        'subtitle': 'Категория товарных позиций для оснащения объектов средствами пожарной безопасности.',
        'image': '/static/img/generated/safety-hero.svg',
        'accent': 'fire',
        'groups': [
            'Огнетушители порошковые',
            'Огнетушители углекислотные',
            'Пожарные рукава',
            'Головки соединительные пожарные',
            'Пожарные щиты',
            'Пожарные извещатели',
            'Самоспасатели',
            'Кронштейны и подставки для огнетушителей',
            'Стволы для пожарного рукава',
            'Шкафы для огнетушителей',
            'Ящики для песка пожарные',
            'Инвентарь для пожарного щита',
        ],
        'items': [
            {
                'title': 'Оснащение объектов противопожарной продукцией',
                'description': 'Подбор серийных изделий и комплектующих под требования объекта и действующие нормы.',
            },
            {
                'title': 'Поставка типовых средств пожаротушения',
                'description': 'Комплектация организаций основными средствами пожаротушения и сопутствующим инвентарем.',
            },
            {
                'title': 'Комплексные поставки по заявке предприятия',
                'description': 'Формирование партии продукции под конкретный список помещений, цехов и участков.',
            },
        ],
    },
    {
        'slug': 'maintenance',
        'title': 'Ремонт и обслуживание инженерных систем',
        'subtitle': 'Техническое сопровождение инженерных систем для стабильной и безопасной эксплуатации.',
        'image': '/static/img/generated/workplace-audit.svg',
        'accent': 'ot',
        'items': [
            {
                'title': 'Ремонт и техническое обслуживание систем электроснабжения',
                'description': 'Обслуживание систем электроснабжения, в том числе выполнение функций ответственного за электрохозяйство.',
            },
            {
                'title': 'Ремонт и техническое обслуживание систем вентиляции и кондиционирования',
                'description': 'Профилактика и устранение неисправностей вентиляции, кондиционирования и газовентканалов.',
            },
            {
                'title': 'Ремонт и техническое обслуживание систем водоснабжения и отопления',
                'description': 'Поддержание систем водоснабжения и отопления в исправном и устойчивом состоянии.',
            },
            {
                'title': 'Ремонт и техническое обслуживание систем охранно-пожарной сигнализации',
                'description': 'Поддержание сигнализации в рабочем состоянии и оперативное устранение неисправностей.',
            },
            {
                'title': 'Ремонт и техническое обслуживание систем видеонаблюдения и связи',
                'description': 'Поддержка систем связи и видеонаблюдения, диагностика и устранение поломок.',
            },
            {
                'title': 'Ремонт и техническое обслуживание систем автоматического пожаротушения и дымоудаления',
                'description': 'Плановое и внеплановое техническое обслуживание противопожарных инженерных систем.',
            },
        ],
    },
    {
        'slug': 'labour',
        'title': 'Услуги по охране труда',
        'subtitle': 'Практическое сопровождение работодателя по охране труда, обучению, документации и проверкам.',
        'image': '/static/img/generated/workplace-audit.svg',
        'accent': 'ot',
        'items': [
            {
                'title': 'Аудит охраны труда на предприятиях',
                'description': 'Проверка состояния охраны труда в организации и выдача рекомендаций по устранению нарушений.',
            },
            {
                'title': 'Аутсорсинг охраны труда (выполнение функций инженера по ОТ)',
                'description': 'Полное сопровождение функций инженера по охране труда внешней командой специалистов.',
            },
            {
                'title': 'Обучение по охране труда, подготовка к экзамену в Исполкоме',
                'description': 'Подготовка руководителей и специалистов к проверке знаний по охране труда.',
            },
            {
                'title': 'Проведение инструктажей по охране труда и пожарной безопасности',
                'description': 'Организация и проведение инструктажей с учетом специфики предприятия и производственных рисков.',
            },
            {
                'title': 'Подготовка комплекта документов по охране труда',
                'description': 'Разработка приказов, инструкций, журналов и других локальных документов.',
            },
            {
                'title': 'Разработка, внедрение и сертификация систем управления охраной труда',
                'description': 'Выстраивание СУОТ с подготовкой предприятия к внедрению и сертификации.',
            },
            {
                'title': 'Расследование несчастных случаев',
                'description': 'Сопровождение расследований с анализом причин и подготовкой корректирующих мер.',
            },
            {
                'title': 'Представление интересов заказчика в Минтруда и при проверках',
                'description': 'Поддержка во взаимодействии с инспекцией и контролирующими органами.',
            },
        ],
    },
    {
        'slug': 'ecology',
        'title': 'Услуги по экологии',
        'subtitle': 'Документация, аудит и сопровождение природоохранной деятельности организации.',
        'image': '/static/img/generated/eco-report.svg',
        'accent': 'eco',
        'items': [
            {
                'title': 'Аутсорсинг по экологии (функции инженера-эколога)',
                'description': 'Комплексное сопровождение организации в области охраны окружающей среды.',
            },
            {
                'title': 'Разработка документов по обращению с отходами',
                'description': 'Подготовка инструкций, инвентаризации, разрешений и иных природоохранных документов.',
            },
            {
                'title': 'Разработка экологического паспорта предприятия или проекта',
                'description': 'Систематизация данных об использовании ресурсов, отходах, выбросах и воздействиях.',
            },
            {
                'title': 'Экологический аудит',
                'description': 'Независимая проверка соблюдения экологических требований и поиск узких мест.',
            },
            {
                'title': 'Разработка инструкций по производственному экологическому наблюдению',
                'description': 'Подготовка документов по ПЭК с описанием контроля, отбора проб и периодичности.',
            },
            {
                'title': 'Охрана атмосферного воздуха',
                'description': 'Инвентаризация выбросов и получение разрешительной документации.',
            },
            {
                'title': 'Охрана земель и недр, растительного мира',
                'description': 'Сбор, оформление и систематизация данных по природным объектам на территории предприятия.',
            },
            {
                'title': 'Представление интересов заказчика в Минприроды и при проверках',
                'description': 'Сопровождение при проверках и взаимодействии с контролирующими органами.',
            },
        ],
    },
    {
        'slug': 'expert',
        'title': 'Экспертное сопровождение проектов',
        'subtitle': 'Подготовка специальных разделов проектной документации и сопровождение на стадиях экспертизы и согласований.',
        'image': '/static/img/generated/civil-defense.svg',
        'accent': 'industrial',
        'items': [
            {
                'title': 'Разработка раздела проекта «Обеспечение пожарной безопасности»',
                'description': 'Подготовка профильного раздела с учетом действующих норм и требований к объекту.',
            },
            {
                'title': 'Разработка раздела проекта «Антитеррористическая защита»',
                'description': 'Проработка рисков и мероприятий по обеспечению устойчивости и защищенности объекта.',
            },
            {
                'title': 'Консультации в области пожарной безопасности',
                'description': 'Экспертные консультации по проектным и эксплуатационным вопросам.',
            },
            {
                'title': 'Расчеты в области пожарной безопасности',
                'description': 'Выполнение необходимых расчетов по пожарным рискам и инженерным решениям.',
            },
            {
                'title': 'Экспертное сопровождение объектов строительства и проектирования',
                'description': 'Проверка проектных решений, поиск отклонений и подготовка к согласованию.',
            },
            {
                'title': 'Участие в перепрофилировании объектов',
                'description': 'Сопровождение изменения целевого назначения помещений и объектов.',
            },
            {
                'title': 'Представление интересов заказчика в органах МЧС и экспертизы',
                'description': 'Работа с замечаниями экспертизы и сопровождение на стадии согласований.',
            },
            {
                'title': 'Разработка раздела проекта «Инженерно-технические мероприятия гражданской обороны»',
                'description': 'Подготовка проектных решений по ГО и ЧС со всеми обоснованиями и графическими материалами.',
            },
            {
                'title': 'Разработка раздела проекта «Охрана окружающей среды»',
                'description': 'Формирование обязательного раздела ООС для строительных и производственных проектов.',
            },
        ],
    },
    {
        'slug': 'journals',
        'title': 'Бланки журналов',
        'subtitle': 'Печатная продукция для учета и регистрации по охране труда, пожарной безопасности и смежным направлениям.',
        'image': '/static/img/generated/safety-qa.svg',
        'accent': 'qa',
        'groups': [
            'Журналы по охране труда',
            'Специализированные журналы',
            'Журналы по БДД',
        ],
        'items': [
            {
                'title': 'Журналы по охране труда',
                'description': 'Базовый комплект регистрационных журналов для специалистов и служб охраны труда.',
            },
            {
                'title': 'Специализированные журналы',
                'description': 'Профильные журналы для отдельных видов работ, процессов и участков.',
            },
            {
                'title': 'Журналы по БДД',
                'description': 'Журналы для учета мероприятий, инструктажей и контроля в области безопасности дорожного движения.',
            },
        ],
    },
]

SECTION_STRUCTURE = {
    'okhrana-truda': {
        'documents_title': 'Документы по ОТ',
        'latest_title': 'Последние документы по охране труда',
        'subsections': [
            'Общие вопросы по охране труда',
            'Служба по охране труда',
            'Обучение, инструктаж, проверка знаний',
            'Инструкции по охране труда',
            'Правила по охране труда',
            'Санитария и гигиена',
            'Медицинские осмотры',
            'Средства индивидуальной защиты',
            'Электробезопасность',
            'Расследование несчастных случаев',
            'Информационные письма',
            'Система управления охраной труда',
            'Строительные нормы',
        ],
    },
    'pozharnaya-bezopasnost': {
        'documents_title': 'Документы по ПБ',
        'latest_title': 'Последние документы по пожарной безопасности',
        'subsections': [
            'Общие вопросы пожарной безопасности',
            'Специфические требования по ПБ',
            'Нормы пожарной безопасности',
            'Технические кодексы устоявшейся практики',
        ],
    },
    'promyshlennaya-bezopasnost': {
        'documents_title': 'Документы по промышленной безопасности',
        'latest_title': 'Последние документы по промышленной безопасности',
        'subsections': [
            'Грузоподъемные краны',
            'Перевозка опасных грузов',
            'Общие вопросы промышленной безопасности',
            'Мобильные подъемные платформы',
        ],
    },
    'ekologiya': {
        'documents_title': 'Документы по экологии',
        'latest_title': 'Последние документы по охране окружающей среды',
        'subsections': [
            'Общие вопросы по экологии',
            'Охрана атмосферного воздуха',
            'Обращение с отходами производства',
            'Охрана водной среды',
            'Охрана почвенного слоя',
            'Система управления окружающей средой',
            'Отчеты по экологии',
        ],
    },
    'arm': {
        'documents_title': 'Документы по АРМ',
        'latest_title': 'Последние документы по АРМ',
        'subsections': [
            'Общие вопросы по АРМ',
            'Карты фотографии рабочего времени',
            'АРМ по профессиям',
            'Образцы документов по АРМ',
        ],
    },
    'grazhdanskaya-oborona': {
        'documents_title': 'Документы по ГО',
        'latest_title': 'Последние материалы по гражданской обороне',
        'subsections': [
            'Общие вопросы гражданской обороны',
            'Планирование и документация',
            'Оповещение и действия персонала',
            'Защитные мероприятия и обучение',
        ],
    },
    'vopros-otvet': {
        'documents_title': 'Вопросы и ответы',
        'latest_title': 'Последние ответы специалистов',
        'subsections': [
            'Охрана труда',
            'Пожарная безопасность',
            'Промышленная безопасность',
            'Экология и АРМ',
        ],
    },
}
SECTION_META_ALIASES = {
    'okhrana-truda': 'okhrana-truda',
    'news-pozharnaya-bezopasnost': 'pozharnaya-bezopasnost',
    'health': 'promyshlennaya-bezopasnost',
    'ekologiya': 'ekologiya',
    'news-grazhdanskaya-oborona': 'arm',
    'grazhdanskaya-oborona': 'grazhdanskaya-oborona',
    'chasto-zadavaemye-voprosy-po-okhrane-truda': 'vopros-otvet',
}

MAIN_NAV_SPECS = [
    {'label': 'Охрана труда', 'slugs': ['okhrana-truda']},
    {'label': 'Пожбез', 'slugs': ['news-pozharnaya-bezopasnost', 'pozharnaya-bezopasnost']},
    {'label': 'Промбез', 'slugs': ['health', 'promyshlennaya-bezopasnost']},
    {'label': 'Экология', 'slugs': ['ekologiya']},
    {'label': 'АРМ', 'slugs': ['news-grazhdanskaya-oborona', 'arm']},
    {'label': 'ГО', 'slugs': ['grazhdanskaya-oborona']},
    {'label': 'Вопрос-ответ', 'slugs': ['chasto-zadavaemye-voprosy-po-okhrane-truda', 'vopros-otvet']},
    {'label': 'Наш форум', 'external_url': 'http://www.ohrana-truda.by/'},
]

TOP_NAV_SPECS = [
    {'label': 'Товары и услуги', 'route': ('catalog', None)},
    {'label': 'События', 'route': ('search', {'type': 'event'})},
    {'label': 'Видео', 'route': ('search', {'type': 'video'})},
    {'label': 'Статьи', 'slugs': ['stati-po-okhrane-truda']},
    {'label': 'Образцы документов', 'slugs': ['obraztsy-blanki-primery-dokumentov-po-okhrane-truda']},
]


def get_all_active_categories():
    cache_key = 'content:all_active_categories'
    categories = cache.get(cache_key)
    if categories is None:
        categories = list(Category.objects.filter(is_active=True).order_by('sort_order', 'id'))
        cache.set(cache_key, categories, CATEGORY_CACHE_TTL)
    return categories


def resolve_category_by_slugs(categories, slugs):
    for slug in slugs:
        for category in categories:
            if category.slug == slug:
                return category
    return None


def get_category_by_public_slug(slug, categories):
    for category in categories:
        if category.resolved_public_slug == slug or category.slug == slug:
            return category
    return None


def build_nav_link(spec, categories):
    if spec.get('external_url'):
        return {
            'title': spec['label'],
            'url': spec['external_url'],
            'external': True,
            'category': None,
        }

    category = resolve_category_by_slugs(categories, spec.get('slugs', []))
    if category is not None:
        return {
            'title': spec['label'],
            'url': category.get_absolute_url(),
            'external': False,
            'category': category,
        }

    route_name, params = spec.get('route', (None, None))
    if route_name:
        url = reverse(route_name)
        if params:
            url = f'{url}?{urlencode(params)}'
        return {
            'title': spec['label'],
            'url': url,
            'external': False,
            'category': None,
        }

    return None


def get_top_nav_links(categories):
    links = []
    for spec in TOP_NAV_SPECS:
        link = build_nav_link(spec, categories)
        if link:
            links.append(link)
    return links


def get_main_nav_links(categories):
    links = []
    for spec in MAIN_NAV_SPECS:
        link = build_nav_link(spec, categories)
        if link:
            links.append(link)
    return links


def get_nav_categories():
    cache_key = 'content:nav_categories'
    nav_categories = cache.get(cache_key)
    if nav_categories is None:
        categories = get_all_active_categories()
        nav_categories = []
        seen = set()
        for spec in MAIN_NAV_SPECS:
            category = resolve_category_by_slugs(categories, spec.get('slugs', []))
            if category and category.pk not in seen:
                nav_categories.append(category)
                seen.add(category.pk)
        cache.set(cache_key, nav_categories, NAV_CACHE_TTL)
    return nav_categories


def get_section_meta(category):
    section_key = SECTION_META_ALIASES.get(category.slug, category.slug)
    return SECTION_STRUCTURE.get(
        section_key,
        {
            'documents_title': f'Материалы по разделу «{category.display_title}»',
            'latest_title': f'Последние публикации по разделу «{category.display_title}»',
            'subsections': [],
        },
    )


def get_section_categories(category, all_categories):
    by_parent = {}
    for cat in all_categories:
        by_parent.setdefault(cat.parent_id, []).append(cat)

    section_categories = []
    seen = set()

    def add_branch(node):
        if node.pk in seen:
            return
        seen.add(node.pk)
        section_categories.append(node)
        for child in by_parent.get(node.pk, []):
            add_branch(child)

    if by_parent.get(category.pk):
        add_branch(category)
        return section_categories

    title_map = {cat.display_title.casefold(): cat for cat in all_categories}
    add_branch(category)

    for subsection_title in get_section_meta(category)['subsections']:
        subsection = title_map.get(subsection_title.casefold())
        if subsection is not None:
            add_branch(subsection)

    return section_categories


def get_section_queryset(category, all_categories):
    section_categories = get_section_categories(category, all_categories)
    return (
        content_listing_queryset().filter(status='published', category__in=section_categories)
        .exclude(content_type='product')
    )


def get_subsection_blocks(category, all_categories, limit=6):
    cache_key = f'content:subsection_blocks:{category.pk}:{limit}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    child_categories = [cat for cat in all_categories if cat.parent_id == category.pk]
    subsection_categories = sorted(child_categories, key=lambda cat: (cat.sort_order, cat.title))
    if not subsection_categories:
        title_map = {cat.display_title.casefold(): cat for cat in all_categories}
        subsection_categories = []
        for subsection_title in get_section_meta(category)['subsections']:
            subsection = title_map.get(subsection_title.casefold())
            if subsection is not None:
                subsection_categories.append(subsection)

    blocks = []
    for subsection in subsection_categories:
        branch_cat_ids = [cat.pk for cat in get_section_categories(subsection, all_categories)]
        if not branch_cat_ids:
            continue
        items = list(
            content_listing_queryset()
            .filter(status='published', category_id__in=branch_cat_ids)
            .exclude(content_type='product')
            [:limit]
        )
        if not items:
            continue
        blocks.append(
            {
                'category': subsection,
                'title': subsection.display_title,
                'url': subsection.get_absolute_url(),
                'lead': items[0],
                'items': items[1:],
            }
        )

    cache.set(cache_key, blocks, BLOCK_CACHE_TTL)
    return blocks


def resolve_legacy_response(url_path):
    normalized = (url_path or '').strip().strip('/')
    if not normalized:
        return None

    if normalized.startswith('images/'):
        media_candidate = Path(settings.MEDIA_ROOT) / normalized.replace('/', '\\')
        if media_candidate.exists():
            return redirect(f'{settings.MEDIA_URL}{normalized}', permanent=True)
        filename = Path(normalized).name
        if filename:
            matches = list((Path(settings.MEDIA_ROOT) / 'images').rglob(filename))
            if len(matches) == 1:
                relative_path = matches[0].relative_to(Path(settings.MEDIA_ROOT)).as_posix()
                return redirect(f'{settings.MEDIA_URL}{relative_path}', permanent=True)

    redirect_rule = LegacyRedirect.objects.filter(old_path=normalized).first()
    if redirect_rule:
        return redirect(redirect_rule.new_path, permanent=True)

    return None


def resolve_catalog_image_url(category):
    if category.image:
        return category.image.url
    probe = category.root.display_title.lower()
    if 'пожар' in probe:
        return '/static/img/generated/fire-briefing.svg'
    if 'эколог' in probe:
        return '/static/img/generated/eco-report.svg'
    if 'инженер' in probe or 'монтаж' in probe or 'проект' in probe:
        return '/static/img/generated/industrial-site.svg'
    if 'аттестац' in probe:
        return '/static/img/generated/workplace-audit.svg'
    return '/static/img/generated/safety-hero.svg'


def get_catalog_tree():
    cache_key = 'content:catalog_tree'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    categories = list(
        CatalogCategory.objects.filter(is_active=True)
        .select_related('parent')
        .order_by('sort_order', 'title')
    )
    if not categories:
        return None

    items = list(
        CatalogItem.objects.filter(is_active=True)
        .select_related('category', 'category__parent')
        .defer('content', 'seo_description')
        .only(
            'id',
            'category',
            'title',
            'slug',
            'public_slug',
            'excerpt',
            'image',
            'price',
            'views',
            'sort_order',
            'is_featured',
            'is_active',
            'published_date',
            'category__id',
            'category__title',
            'category__slug',
            'category__public_slug',
            'category__parent_id',
        )
        .order_by('-views', 'sort_order', 'title')
    )

    by_id = {category.id: category for category in categories}
    children_map = defaultdict(list)
    for category in categories:
        children_map[category.parent_id].append(category)

    items_map = defaultdict(list)
    for item in items:
        items_map[item.category_id].append(item)

    total_item_count_cache = {}

    def get_total_item_count(category_id):
        if category_id in total_item_count_cache:
            return total_item_count_cache[category_id]
        total = len(items_map.get(category_id, []))
        for child in children_map.get(category_id, []):
            total += get_total_item_count(child.id)
        total_item_count_cache[category_id] = total
        return total

    roots = []
    for root in children_map.get(None, []):
        children = children_map.get(root.id, [])
        roots.append(
            {
                'category': root,
                'slug': root.public_slug,
                'title': root.display_title,
                'subtitle': root.resolved_seo_description or root.display_description,
                'image_url': resolve_catalog_image_url(root),
                'url': root.get_absolute_url(),
                'children': children,
                'child_cards': [
                    {
                        'category': child,
                        'title': child.display_title,
                        'description': child.resolved_seo_description or child.display_description,
                        'url': child.get_absolute_url(),
                        'item_count': get_total_item_count(child.id),
                        'image_url': resolve_catalog_image_url(child),
                    }
                    for child in children
                ],
                'items_preview': items_map.get(root.id, [])[:8],
                'direct_item_count': len(items_map.get(root.id, [])),
                'total_item_count': get_total_item_count(root.id),
            }
        )

    result = {
        'roots': roots,
        'categories': categories,
        'items_map': items_map,
        'children_map': children_map,
        'total_items': len(items),
        'root_count': len(roots),
    }
    cache.set(cache_key, result, CATALOG_CACHE_TTL)
    return result


def get_catalog_sidebar_sections():
    cache_key = 'content:catalog_sidebar_sections'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    root_categories = list(
        CatalogCategory.objects.filter(is_active=True, parent__isnull=True)
        .order_by('sort_order', 'title')
    )
    if root_categories:
        result = [
            {
                'title': category.display_title,
                'slug': category.public_slug,
                'url': category.get_absolute_url(),
                'icon_url': category.icon_asset_url,
            }
            for category in root_categories
        ]
        cache.set(cache_key, result, CATALOG_CACHE_TTL)
        return result
    fallback_icon_map = {
        'fire-services': '/static/img/icons/fire.svg',
        'engineering': '/static/img/icons/factory.svg',
        'fire-products': '/static/img/icons/shield.svg',
        'maintenance': '/static/img/icons/factory.svg',
        'labour': '/static/img/icons/shield.svg',
        'ecology': '/static/img/icons/leaf.svg',
        'attestation': '/static/img/icons/briefcase.svg',
        'expert': '/static/img/icons/folder.svg',
        'journals': '/static/img/icons/folder.svg',
    }
    return [
        {
            'title': section['title'],
            'slug': section['slug'],
            'url': f"{reverse('catalog')}#{section['slug']}",
            'icon_url': fallback_icon_map.get(section['slug'], '/static/img/icons/folder.svg'),
        }
        for section in CATALOG_SECTIONS
    ]


def get_catalog_home_products(limit=8):
    products = list(
        CatalogItem.objects.filter(is_active=True)
        .select_related('category')
        .defer('content', 'seo_description')
        .only(
            'id',
            'category',
            'title',
            'slug',
            'public_slug',
            'excerpt',
            'image',
            'price',
            'special_price',
            'views',
            'sort_order',
            'is_featured',
            'is_active',
            'published_date',
            'category__id',
            'category__title',
            'category__slug',
            'category__public_slug',
            'category__parent_id',
        )
        .order_by('-views', 'sort_order', 'title')[:limit]
    )
    if products:
        return products
    return list(
        content_listing_queryset().filter(
            status='published',
            content_type='product',
        )[:limit]
    )


def get_catalog_section_groups(category, limit=4):
    section_branding = category.resolved_branding if category else None
    catalog_categories = list(
        CatalogCategory.objects.filter(is_active=True)
        .select_related('parent', 'branding')
        .order_by('sort_order', 'title')
    )
    if not catalog_categories:
        return []

    catalog_by_parent = defaultdict(list)
    for catalog_category in catalog_categories:
        catalog_by_parent[catalog_category.parent_id].append(catalog_category)

    matched_roots = []
    if section_branding:
        matched_roots = [
            catalog_category
            for catalog_category in catalog_categories
            if catalog_category.parent_id is None
            and catalog_category.resolved_branding
            and catalog_category.resolved_branding.pk == section_branding.pk
        ]

    if not matched_roots:
        return []

    def collect_catalog_branch_ids(node, branch_ids):
        if node.pk in branch_ids:
            return
        branch_ids.add(node.pk)
        for child in catalog_by_parent.get(node.pk, []):
            collect_catalog_branch_ids(child, branch_ids)

    groups = []
    for root in matched_roots:
        branch_ids = set()
        collect_catalog_branch_ids(root, branch_ids)
        root_items = list(
            CatalogItem.objects.filter(is_active=True, category_id__in=branch_ids)
            .select_related('category')
            .order_by('-is_featured', '-views', 'sort_order', 'title')[:limit]
        )
        if not root_items:
            continue
        groups.append(
            {
                'title': root.display_title,
                'url': root.get_absolute_url(),
                'lead': root_items[0],
                'items': root_items[1:],
            }
        )

    return groups


def get_catalog_category_ancestors(category):
    ancestors = []
    current = category.parent
    while current is not None:
        ancestors.append(current)
        current = current.parent
    return list(reversed(ancestors))


@cache_page(BLOCK_CACHE_TTL)
def home(request):
    all_categories = get_all_active_categories()
    categories = get_nav_categories()
    catalog_sidebar_sections = get_catalog_sidebar_sections()
    home_slider_block = get_home_slider_block()
    slider_limit = home_slider_block.item_limit if home_slider_block else 4
    featured_limit = home_slider_block.secondary_item_limit if home_slider_block else 4

    slider_queryset = content_listing_queryset().filter(
        status='published',
        is_main_slider=True,
    )
    if home_slider_block:
        slider_queryset = filter_queryset_for_feed_block(slider_queryset, home_slider_block, all_categories)
    slider_items = list(slider_queryset[:slider_limit])
    slider_item_ids = [item.pk for item in slider_items]

    featured_queryset = content_listing_queryset().filter(status='published', is_featured=True)
    if home_slider_block:
        featured_queryset = filter_queryset_for_feed_block(featured_queryset, home_slider_block, all_categories)
        if home_slider_block.exclude_main_slider_items:
            featured_queryset = featured_queryset.exclude(pk__in=slider_item_ids)
    else:
        featured_queryset = featured_queryset.exclude(pk__in=slider_item_ids)
    featured_items = list(featured_queryset[:featured_limit])

    products = get_catalog_home_products(limit=8)

    events = content_listing_queryset().filter(
        status='published', content_type='event'
    )[:5]

    videos = list(
        content_listing_queryset().filter(
            status='published',
            content_type='video',
        )
        .order_by('-views', '-published_date')[:5]
    )

    section_blocks = build_homepage_feed_blocks(all_categories, slider_item_ids)
    if not section_blocks:
        section_blocks = []
        for cat in categories:
            meta = get_section_meta(cat)
            section_qs = get_section_queryset(cat, all_categories)
            latest_items = list(
                section_qs
                .exclude(pk__in=slider_item_ids)
                [:8]
            )
            if latest_items:
                section_blocks.append(
                    {
                        'category': cat,
                        'meta': meta,
                        'title': cat.display_title,
                        'url': cat.get_absolute_url(),
                        'lead': latest_items[0],
                        'latest': latest_items[1:7],
                        'documents': [],
                    }
                )

    # Баннеры: словарь {category_slug: banner}
    banners_qs = Banner.objects.filter(is_active=True).select_related('category')
    banners_by_slug = {}
    for b in banners_qs:
        key = b.category.slug if b.category else '__global__'
        if key not in banners_by_slug:
            banners_by_slug[key] = b

    # Прикрепляем баннер к каждому блоку (сначала ищем тематический, потом глобальный)
    for block in section_blocks:
        category_obj = block.get('category')
        if not category_obj:
            block['banner'] = banners_by_slug.get('__global__')
            continue
        slug = category_obj.slug
        block['banner'] = block.get('banner') or banners_by_slug.get(slug) or banners_by_slug.get('__global__')

    context = {
        'categories': categories,
        'top_nav_links': get_top_nav_links(all_categories),
        'main_nav_links': get_main_nav_links(all_categories),
        'slider_items': slider_items,
        'featured_items': featured_items,
        'catalog_sidebar_sections': catalog_sidebar_sections,
        'home_slider_block': home_slider_block,
        'products': products,
        'events': events,
        'videos': videos,
        'section_blocks': section_blocks,
        'content_type_links': CONTENT_TYPE_LINKS,
    }
    return render(request, 'home.html', context)


def catalog(request):
    all_categories = get_all_active_categories()
    categories = get_nav_categories()
    catalog_tree = get_catalog_tree()
    if catalog_tree:
        context = {
            'categories': categories,
            'top_nav_links': get_top_nav_links(all_categories),
            'main_nav_links': get_main_nav_links(all_categories),
            'catalog_sections': catalog_tree['roots'],
            'catalog_total_items': catalog_tree['total_items'],
            'catalog_root_count': catalog_tree['root_count'],
            'content_type_links': CONTENT_TYPE_LINKS,
        }
        return render(request, 'catalog.html', context)

    context = {
        'categories': categories,
        'top_nav_links': get_top_nav_links(all_categories),
        'main_nav_links': get_main_nav_links(all_categories),
        'catalog_sections': CATALOG_SECTIONS,
        'catalog_total_items': sum(len(section.get('items', [])) for section in CATALOG_SECTIONS),
        'catalog_root_count': len(CATALOG_SECTIONS),
        'content_type_links': CONTENT_TYPE_LINKS,
    }
    return render(request, 'catalog.html', context)


def catalog_category(request, slug):
    all_categories = get_all_active_categories()
    categories = get_nav_categories()
    category = get_object_or_404(
        CatalogCategory.objects.select_related('parent'),
        public_slug=slug,
        is_active=True,
    )

    child_categories = list(
        category.children.filter(is_active=True)
        .annotate(active_items_count=Count('items', filter=Q(items__is_active=True), distinct=True))
        .order_by('sort_order', 'title')
    )
    items_qs = (
        CatalogItem.objects.filter(category=category, is_active=True)
        .select_related('category')
        .order_by('sort_order', 'title')
    )
    paginator = Paginator(items_qs, 24)
    page_obj = paginator.get_page(request.GET.get('page'))

    related_items = list(
        CatalogItem.objects.filter(is_active=True, category__parent=category)
        .select_related('category')
        .order_by('-views', 'sort_order', 'title')[:8]
    )
    if not related_items:
        related_items = list(
            CatalogItem.objects.filter(is_active=True, category=category)
            .select_related('category')
            .order_by('-views', 'sort_order', 'title')[:8]
        )

    context = {
        'categories': categories,
        'top_nav_links': get_top_nav_links(all_categories),
        'main_nav_links': get_main_nav_links(all_categories),
        'catalog_roots': get_catalog_sidebar_sections(),
        'catalog_category': category,
        'catalog_ancestors': get_catalog_category_ancestors(category),
        'child_categories': child_categories,
        'page_obj': page_obj,
        'related_items': related_items,
        'content_type_links': CONTENT_TYPE_LINKS,
    }
    return render(request, 'catalog_category.html', context)


def catalog_item_detail(request, category_slug, slug):
    all_categories = get_all_active_categories()
    categories = get_nav_categories()
    item = get_object_or_404(
        CatalogItem.objects.select_related('category', 'category__parent').prefetch_related('gallery_images', 'files'),
        category__public_slug=category_slug,
        public_slug=slug,
        is_active=True,
    )

    form = LeadForm(initial={'item_pk': item.pk}) # Initialize form for GET or invalid POST

    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            phone = form.cleaned_data['phone']
            message = form.cleaned_data['message']
            item_pk_from_form = form.cleaned_data['item_pk'] # Renamed to avoid conflict

            # Ensure item_pk matches the current item to prevent tampering
            if item_pk_from_form != item.pk:
                form.add_error(None, 'Произошла ошибка при отправке заявки. Пожалуйста, попробуйте еще раз.')
            else:
                lead_settings = LeadSettings.objects.first() # Get the first (and likely only) LeadSettings instance

                if lead_settings and lead_settings.recipient_email:
                    subject = f'Новая заявка с сайта {settings.SITE_NAME} на "{item.display_title}"'
                    email_body = (
                        f"Название товара/услуги: {item.display_title}\n"
                        f"Ссылка на товар/услугу: {request.build_absolute_uri(item.get_absolute_url())}\n\n"
                        f"Имя: {name}\n"
                        f"Email: {email}\n"
                    )
                    if phone:
                        email_body += f"Телефон: {phone}\n"
                    if message:
                        email_body += f"Сообщение: {message}\n"

                    try:
                        send_mail(
                            subject,
                            email_body,
                            lead_settings.sender_name or settings.DEFAULT_FROM_EMAIL,
                            [lead_settings.recipient_email],
                            fail_silently=False,
                        )
                        messages.success(request, lead_settings.success_message)
                        return redirect(request.path_info)
                    except Exception as e:
                        print(f"Error sending email: {e}") # For debugging purposes
                        messages.error(request, 'Произошла ошибка при отправке email. Пожалуйста, попробуйте позже.')
                        form.add_error(None, 'Произошла ошибка при отправке email. Пожалуйста, попробуйте позже.')
                else:
                    messages.error(request, 'Настройки email для заявок не найдены.')
                    form.add_error(None, 'Настройки email для заявок не найдены.')
        else:
            # Form is invalid, messages will be added below if needed or handled by template
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')


    CatalogItem.objects.filter(pk=item.pk).update(views=item.views + 1)
    item.views += 1

    related_items = list(
        CatalogItem.objects.filter(is_active=True, category=item.category)
        .exclude(pk=item.pk)
        .select_related('category')
        .order_by('-views', 'sort_order', 'title')[:6]
    )

    context = {
        'categories': categories,
        'top_nav_links': get_top_nav_links(all_categories),
        'main_nav_links': get_main_nav_links(all_categories),
        'catalog_roots': get_catalog_sidebar_sections(),
        'item': item,
        'catalog_category': item.category,
        'catalog_ancestors': get_catalog_category_ancestors(item.category),
        'related_items': related_items,
        'content_type_links': CONTENT_TYPE_LINKS,
        'lead_form': form, # Always pass the form to the context
    }
    return render(request, 'catalog_item_detail.html', context)


@cache_page(BLOCK_CACHE_TTL)
def section(request, slug):
    all_categories = get_all_active_categories()
    category = get_category_by_public_slug(slug, all_categories)
    if category is None:
        legacy_response = resolve_legacy_response(slug)
        if legacy_response:
            return legacy_response
        raise Http404()
    if slug != category.resolved_public_slug:
        return redirect(category.get_absolute_url(), permanent=True)
    categories = get_nav_categories()
    section_meta = get_section_meta(category)

    qs = get_section_queryset(category, all_categories)
    # Fetch slider + rail in one query, then split in Python
    prefetched = list(qs[:20])
    slider_items = [item for item in prefetched if item.is_main_slider][:4]
    if not slider_items:
        slider_items = prefetched[:4]
    slider_item_ids = [item.pk for item in slider_items]
    slider_id_set = set(slider_item_ids)
    rail_items = [item for item in prefetched if item.pk not in slider_id_set][:6]
    section_items_page = Paginator(qs, 12).get_page(request.GET.get('page'))
    subsection_blocks = build_section_feed_blocks(category, all_categories, slider_item_ids)
    if not subsection_blocks:
        subsection_blocks = get_subsection_blocks(category, all_categories)
    section_catalog_groups = get_catalog_section_groups(category, limit=4)

    context = {
        'categories': categories,
        'top_nav_links': get_top_nav_links(all_categories),
        'main_nav_links': get_main_nav_links(all_categories),
        'category': category,
        'section_meta': section_meta,
        'slider_items': slider_items,
        'rail_items': rail_items,
        'section_items_page': section_items_page,
        'subsection_blocks': subsection_blocks,
        'section_catalog_groups': section_catalog_groups,
    }
    return render(request, 'section.html', context)


def content_detail_public(request, slug):
    item = (
        ContentItem.objects.select_related('category')
        .filter(Q(public_slug=slug) | Q(slug=slug), status='published')
        .first()
    )
    if item is None:
        legacy_response = resolve_legacy_response(f'{slug}.html')
        if legacy_response:
            return legacy_response
        raise Http404()

    category = item.category
    all_categories = get_all_active_categories()
    categories = get_nav_categories()

    ContentItem.objects.filter(pk=item.pk).update(views=item.views + 1)
    item.views += 1

    related = (
        content_listing_queryset().filter(
            status='published',
            category__in=[category, *category.related_categories.all()],
        )
        .exclude(pk=item.pk)
        [:4]
    )

    context = {
        'categories': categories,
        'top_nav_links': get_top_nav_links(all_categories),
        'main_nav_links': get_main_nav_links(all_categories),
        'category': category,
        'item': item,
        'related': related,
        'content_type_links': CONTENT_TYPE_LINKS,
    }
    return render(request, 'article_detail.html', context)


def content_detail(request, cat_slug, slug):
    legacy_response = resolve_legacy_response(f'{cat_slug}/{slug}')
    if legacy_response:
        return legacy_response

    category = get_object_or_404(Category, slug=cat_slug)
    item = get_object_or_404(ContentItem, slug=slug, category=category, status='published')
    return redirect(item.get_absolute_url(), permanent=True)


@cache_page(60)
def search(request):
    all_categories = get_all_active_categories()
    categories = get_nav_categories()
    query = request.GET.get('q', '').strip()
    content_type = request.GET.get('type', '').strip()
    content_type_label = dict(CONTENT_TYPE_LINKS).get(content_type, content_type)
    results = []

    qs = content_listing_queryset().filter(status='published')
    if content_type == 'video':
        qs = qs.filter(content_type='video')
    elif content_type == 'event':
        qs = qs.filter(content_type='event')
    else:
        content_type = ''
        content_type_label = ''
    if query:
        qs = qs.filter(title__icontains=query)
    if query or content_type:
        results = qs[:30]

    context = {
        'categories': categories,
        'top_nav_links': get_top_nav_links(all_categories),
        'main_nav_links': get_main_nav_links(all_categories),
        'query': query,
        'results': results,
        'content_type': content_type,
        'content_type_label': content_type_label,
        'content_type_links': CONTENT_TYPE_LINKS,
    }
    return render(request, 'search.html', context)


def legacy_path(request, url_path):
    legacy_response = resolve_legacy_response(url_path)
    if legacy_response:
        return legacy_response
    raise Http404()
