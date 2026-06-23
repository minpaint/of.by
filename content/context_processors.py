from django.core.cache import cache
from django.templatetags.static import static

from .models import Banner, CatalogCategory, CatalogItem, Category, ContentItem, SiteCounter

BANNER_CACHE_TTL = 300


BRANDING_CONFIG = {
    'okhrana-truda': {
        'title': 'Охрана труда',
        'subtitle': 'Портал для инженеров по охране труда Беларуси',
        'icon_url': static('img/icons/shield.svg'),
        'theme_color': 'blue',
    },
    'pozharnaya-bezopasnost': {
        'title': 'Пожарная безопасность',
        'subtitle': 'Портал по пожарной безопасности Беларуси',
        'icon_url': static('img/icons/fire.svg'),
        'theme_color': 'red',
    },
    'promyshlennaya-bezopasnost': {
        'title': 'Промышленная безопасность',
        'subtitle': 'Портал по промышленной безопасности Беларуси',
        'icon_url': static('img/icons/factory.svg'),
        'theme_color': 'orange',
    },
    'ekologiya': {
        'title': 'Экология',
        'subtitle': 'Портал по экологии и охране окружающей среды',
        'icon_url': static('img/icons/leaf.svg'),
        'theme_color': 'green',
    },
    'arm': {
        'title': 'Аттестация рабочих мест',
        'subtitle': 'Материалы по аттестации рабочих мест Беларуси',
        'icon_url': static('img/icons/briefcase.svg'),
        'theme_color': 'purple',
    },
    'grazhdanskaya-oborona': {
        'title': 'Гражданская оборона',
        'subtitle': 'Материалы по гражданской обороне и ЧС',
        'icon_url': static('img/icons/lifebuoy.svg'),
        'theme_color': 'gray',
    },
    'vopros-otvet': {
        'title': 'Вопрос-ответ',
        'subtitle': 'Подборка практических ответов для специалистов',
        'icon_url': static('img/icons/question.svg'),
        'theme_color': 'indigo',
    },
    'catalog': {
        'title': 'Товары и услуги',
        'subtitle': 'Каталог товаров и услуг по направлениям безопасности',
        'icon_url': static('img/icons/box.svg'),
        'theme_color': 'blue',
    },
}

CATEGORY_BRAND_ALIASES = {
    'okhrana-truda': 'okhrana-truda',
    'dokumenty': 'okhrana-truda',
    'videos': 'okhrana-truda',
    'video': 'okhrana-truda',
    'events': 'okhrana-truda',
    'webinars': 'okhrana-truda',
    'stati-po-okhrane-truda': 'okhrana-truda',
    'obraztsy-blanki-primery-dokumentov-po-okhrane-truda': 'okhrana-truda',
    'space': 'okhrana-truda',
    'sanitariya-i-gigiena': 'okhrana-truda',
    'elektrobezopasnost': 'okhrana-truda',
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


def _get_branding_config(key):
    branding = dict(BRANDING_CONFIG['okhrana-truda'])
    branding.update(BRANDING_CONFIG.get(key, {}))
    branding['key'] = key if key in BRANDING_CONFIG else 'okhrana-truda'
    return branding


def _build_branding_from_record(branding):
    return {
        'key': branding.key,
        'title': branding.title,
        'subtitle': branding.subtitle,
        'icon_url': branding.logo_asset_url,
        'theme_color': branding.theme_color,
    }


def _resolve_category_brand_key(category):
    current = category
    while current is not None:
        for candidate in (
            getattr(current, 'resolved_public_slug', None),
            getattr(current, 'public_slug', None),
            getattr(current, 'slug', None),
        ):
            if candidate in CATEGORY_BRAND_ALIASES:
                return CATEGORY_BRAND_ALIASES[candidate]
        current = getattr(current, 'parent', None)
    return 'okhrana-truda'


def _resolve_catalog_brand_key(catalog_category):
    probe = catalog_category.root.display_title.lower()
    if 'пожар' in probe:
        return 'pozharnaya-bezopasnost'
    if 'эколог' in probe:
        return 'ekologiya'
    if 'аттестац' in probe:
        return 'arm'
    if 'охран' in probe and 'труд' in probe:
        return 'okhrana-truda'
    if 'инженер' in probe or 'проект' in probe or 'монтаж' in probe or 'эксперт' in probe:
        return 'promyshlennaya-bezopasnost'
    if 'охрана труда' in probe or 'журнал' in probe:
        return 'okhrana-truda'
    return 'catalog'


def _get_current_branding(request):
    cache_key = f'ctx:branding:{request.path}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    result = _resolve_branding(request)
    cache.set(cache_key, result, BANNER_CACHE_TTL)
    return result


def _resolve_branding(request):
    resolver_match = getattr(request, 'resolver_match', None)
    if resolver_match is None:
        return _get_branding_config('okhrana-truda')

    view_name = resolver_match.view_name
    kwargs = resolver_match.kwargs

    if view_name in {'catalog', 'catalog_short', 'catalog_short_noslash'}:
        return _get_branding_config('catalog')

    if view_name in {'catalog_category', 'catalog_item_detail'}:
        category_slug = kwargs.get('category_slug') or kwargs.get('slug')
        if category_slug:
            if view_name == 'catalog_item_detail':
                catalog_item = (
                    CatalogItem.objects.select_related('category', 'category__parent', 'category__branding', 'category__parent__branding')
                    .filter(category__public_slug=kwargs.get('category_slug'), public_slug=kwargs.get('slug'), is_active=True)
                    .first()
                )
                if catalog_item is not None:
                    if catalog_item.category and catalog_item.category.resolved_branding is not None:
                        return _build_branding_from_record(catalog_item.category.resolved_branding)
                    return _get_branding_config(_resolve_catalog_brand_key(catalog_item.category))
            catalog_category = (
                CatalogCategory.objects.select_related('parent', 'branding', 'parent__branding')
                .filter(public_slug=category_slug, is_active=True)
                .first()
            )
            if catalog_category is not None:
                if catalog_category.resolved_branding is not None:
                    return _build_branding_from_record(catalog_category.resolved_branding)
                return _get_branding_config(_resolve_catalog_brand_key(catalog_category))
        return _get_branding_config('catalog')

    if view_name in {'section', 'section_noslash'}:
        category = (
            Category.objects.select_related('parent', 'branding', 'parent__branding')
            .filter(public_slug=kwargs.get('slug'))
            .first()
            or Category.objects.select_related('parent', 'branding', 'parent__branding').filter(slug=kwargs.get('slug')).first()
        )
        if category is not None:
            if category.resolved_branding is not None:
                return _build_branding_from_record(category.resolved_branding)
            return _get_branding_config(_resolve_category_brand_key(category))

    if view_name in {'content_detail', 'content_detail_noslash'}:
        item = (
            ContentItem.objects.select_related('category', 'category__parent', 'category__branding', 'category__parent__branding')
            .filter(
                status='published',
                category__public_slug=kwargs.get('cat_slug'),
                public_slug=kwargs.get('slug'),
            )
            .first()
        )
        if item is None:
            item = (
                ContentItem.objects.select_related('category', 'category__parent', 'category__branding', 'category__parent__branding')
                .filter(
                    status='published',
                    category__slug=kwargs.get('cat_slug'),
                    public_slug=kwargs.get('slug'),
                )
                .first()
            )
        if item is not None and item.category is not None:
            if item.category.resolved_branding is not None:
                return _build_branding_from_record(item.category.resolved_branding)
            return _get_branding_config(_resolve_category_brand_key(item.category))

    if view_name in {'content_detail_public', 'content_detail_public_slash'}:
        item = (
            ContentItem.objects.select_related('category', 'category__parent', 'category__branding', 'category__parent__branding')
            .filter(public_slug=kwargs.get('slug'), status='published')
            .first()
            or ContentItem.objects.select_related('category', 'category__parent', 'category__branding', 'category__parent__branding')
            .filter(slug=kwargs.get('slug'), status='published')
            .first()
        )
        if item is not None and item.category is not None:
            if item.category.resolved_branding is not None:
                return _build_branding_from_record(item.category.resolved_branding)
            return _get_branding_config(_resolve_category_brand_key(item.category))

    return _get_branding_config('okhrana-truda')


def header_banner(request):
    cache_key = 'ctx:header_banner'
    banner = cache.get(cache_key)
    if banner is None:
        banner = (
            Banner.objects
            .filter(placement=Banner.PLACEMENT_HEADER, is_active=True)
            .order_by('sort_order')
            .first()
        )
        cache.set(cache_key, banner, BANNER_CACHE_TTL)

    sidebar_cache_key = 'ctx:sidebar_banner'
    sidebar_banner = cache.get(sidebar_cache_key)
    if sidebar_banner is None:
        sidebar_banner = (
            Banner.objects
            .filter(placement=Banner.PLACEMENT_SIDEBAR, is_active=True)
            .order_by('sort_order')
            .first()
        )
        cache.set(sidebar_cache_key, sidebar_banner, BANNER_CACHE_TTL)

    counters_cache_key = 'ctx:site_counters'
    site_counters = cache.get(counters_cache_key)
    if site_counters is None:
        site_counters = list(
            SiteCounter.objects
            .filter(is_active=True)
            .order_by('sort_order', 'title')
        )
        cache.set(counters_cache_key, site_counters, BANNER_CACHE_TTL)

    return {
        'header_banner': banner,
        'sidebar_banner': sidebar_banner,
        'current_branding': _get_current_branding(request),
        'site_counters': site_counters,
    }
