import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from content.management.commands.import_old_sql import DumpParser
from content.models import CatalogCategory, CatalogItem, CatalogItemFile, CatalogItemImage, LegacyRedirect, repair_text, translit_slug


DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
ZERO_DATETIME = '0000-00-00 00:00:00'
ZERO_DATE = '0000-00-00'
LEADING_ID_RE = re.compile(r'^(?P<id>\d+)-')


@dataclass
class ImportedCatalogCategory:
    old_id: int
    old_alias: str
    parent_old_id: int | None
    title: str
    slug: str
    public_slug: str
    description: str
    seo_title: str
    seo_description: str
    heading: str
    sort_order: int
    is_active: bool
    created_at: timezone.datetime | None
    updated_at: timezone.datetime | None
    image_fullpath: str

    @property
    def new_path(self):
        return f'/catalog/{self.public_slug}/'


@dataclass
class ImportedCatalogItem:
    old_id: int
    old_alias: str
    category_old_id: int
    title: str
    slug: str
    public_slug: str
    excerpt: str
    content: str
    price: Decimal | None
    special_price: Decimal | None
    sku: str
    address: str
    city: str
    postcode: str
    phone: str
    mobile: str
    fax: str
    website: str
    email: str
    is_available: bool
    is_featured: bool
    views: int
    seo_title: str
    seo_description: str
    sort_order: int
    is_active: bool
    published_date: timezone.datetime | None
    created_at: timezone.datetime | None
    updated_at: timezone.datetime | None
    image_fullpaths: list[tuple[str, str, int]]
    file_fullpaths: list[tuple[str, str, int, int]]
    category_public_slug: str

    @property
    def new_path(self):
        return f'/catalog/{self.category_public_slug}/{self.public_slug}.html'


class MediaExtractor:
    def __init__(self, zip_path: Path):
        self.zip_path = zip_path
        self.archive = zipfile.ZipFile(zip_path)
        self.entries = {name.replace('\\', '/'): name for name in self.archive.namelist()}
        self.entries_by_basename = defaultdict(list)
        for normalized in self.entries:
            self.entries_by_basename[Path(normalized).name.lower()].append(normalized)
        self.cache = {}

    def close(self):
        self.archive.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def extract(self, kind: str, fullpath: str, relative_target: str) -> str:
        normalized_target = Path(relative_target).as_posix()
        if not fullpath:
            return ''
        cache_key = (kind, fullpath, normalized_target)
        if cache_key in self.cache:
            return self.cache[cache_key]

        normalized_fullpath = fullpath.strip('/').replace('\\', '/')
        member_name = self._resolve_member(kind, normalized_fullpath)
        if not member_name:
            self.cache[cache_key] = ''
            return ''

        destination = Path(settings.MEDIA_ROOT) / normalized_target
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            with self.archive.open(self.entries[member_name]) as source:
                destination.write_bytes(source.read())

        self.cache[cache_key] = normalized_target
        return normalized_target

    def _resolve_member(self, kind: str, normalized_fullpath: str) -> str:
        prefixes = []
        if kind == 'image':
            prefixes = [
                f'public_html/media/djcatalog2/images/{normalized_fullpath}',
                f'media/djcatalog2/images/{normalized_fullpath}',
            ]
        elif kind == 'file':
            prefixes = [
                f'public_html/media/djcatalog2/files/{normalized_fullpath}',
                f'media/djcatalog2/files/{normalized_fullpath}',
            ]

        for candidate in prefixes:
            candidate = candidate.replace('\\', '/')
            if candidate in self.entries:
                return candidate

        basename = Path(normalized_fullpath).name.lower()
        for candidate in self.entries_by_basename.get(basename, []):
            if candidate.endswith(normalized_fullpath):
                return candidate
        return ''


class Command(BaseCommand):
    help = 'Импортирует старый каталог DJ-Catalog2 из old.sql и name.zip в новые таблицы каталога.'

    def add_arguments(self, parser):
        parser.add_argument('--sql-path', default='old.sql', help='Путь к дампу old.sql')
        parser.add_argument('--zip-path', default='name.zip', help='Путь к архиву со старым сайтом')
        parser.add_argument('--clear', action='store_true', help='Полностью очистить текущий каталог перед импортом')

    def handle(self, *args, **options):
        sql_path = Path(options['sql_path'])
        if not sql_path.is_absolute():
            sql_path = Path(settings.BASE_DIR) / sql_path
        if not sql_path.exists():
            raise CommandError(f'Не найден SQL-дамп: {sql_path}')

        zip_path = Path(options['zip_path'])
        if not zip_path.is_absolute():
            zip_path = Path(settings.BASE_DIR) / zip_path
        if not zip_path.exists():
            raise CommandError(f'Не найден архив со старым сайтом: {zip_path}')

        parser = DumpParser(sql_path.read_text(encoding='utf-8'))
        category_rows = list(parser.iter_rows('pkulc_djc2_categories'))
        item_rows = [row for row in parser.iter_rows('pkulc_djc2_items') if int(row.get('published') or 0) == 1]
        image_rows = list(parser.iter_rows('pkulc_djc2_images'))
        file_rows = list(parser.iter_rows('pkulc_djc2_files'))
        sh404_rows = list(parser.iter_rows('pkulc_sh404sef_urls'))
        menu_rows = list(parser.iter_rows('pkulc_menu'))

        imported_categories = self.build_categories(category_rows, item_rows, image_rows)
        imported_items = self.build_items(item_rows, image_rows, file_rows, imported_categories)
        redirect_map = self.build_redirects(imported_categories, imported_items, sh404_rows, menu_rows)

        self.stdout.write(
            f'Подготовлено к импорту: {len(imported_categories)} категорий, '
            f'{len(imported_items)} позиций, {len(redirect_map)} redirect-ов.'
        )

        with MediaExtractor(zip_path) as extractor, transaction.atomic():
            if options['clear']:
                CatalogItemFile.objects.all().delete()
                CatalogItemImage.objects.all().delete()
                CatalogItem.objects.all().delete()
                CatalogCategory.objects.all().delete()
                LegacyRedirect.objects.filter(new_path=reverse('catalog')).delete()
                LegacyRedirect.objects.filter(new_path__startswith='/catalog/').delete()
                self.stdout.write(self.style.WARNING('Текущий каталог очищен перед импортом.'))

            category_map = self.persist_categories(imported_categories, extractor)
            self.persist_items(imported_items, category_map, extractor)
            self.persist_redirects(redirect_map)

        self.stdout.write(
            self.style.SUCCESS(
                f'Каталог импортирован: {CatalogCategory.objects.count()} категорий, '
                f'{CatalogItem.objects.count()} позиций, '
                f'{CatalogItemImage.objects.count()} изображений, '
                f'{CatalogItemFile.objects.count()} файлов.'
            )
        )

    def build_categories(self, category_rows, item_rows, image_rows):
        rows_by_id = {int(row['id']): row for row in category_rows}
        included_ids = {
            int(row['id'])
            for row in category_rows
            if int(row.get('published') or 0) == 1
        }
        included_ids.update(int(row.get('cat_id') or 0) for row in item_rows if int(row.get('cat_id') or 0))

        for category_id in list(included_ids):
            self._include_ancestors(category_id, rows_by_id, included_ids)

        category_image_map = defaultdict(list)
        for row in image_rows:
            if row.get('type') == 'category' and int(row.get('exclude') or 0) == 0:
                category_image_map[int(row['item_id'])].append(row)
        for rows in category_image_map.values():
            rows.sort(key=lambda row: (int(row.get('ordering') or 0), int(row.get('id') or 0)))

        used_slugs = set()
        used_public_slugs = set()
        imported = {}
        for row in sorted(
            (rows_by_id[category_id] for category_id in included_ids),
            key=lambda current: (self._category_depth(current, rows_by_id), int(current.get('ordering') or 0), int(current['id'])),
        ):
            old_id = int(row['id'])
            alias = self.clean_slug(row.get('alias') or row.get('name') or f'catalog-category-{old_id}')
            title = repair_text(row.get('name') or '').strip() or f'Категория {old_id}'
            public_slug = self.ensure_unique(alias, used_public_slugs, f'catalog-category-{old_id}', 255)
            slug = self.ensure_unique(alias, used_slugs, f'catalog-category-{old_id}', 255)
            parent_old_id = int(row.get('parent_id') or 0) or None
            image_row = category_image_map.get(old_id, [])
            imported[old_id] = ImportedCatalogCategory(
                old_id=old_id,
                old_alias=alias,
                parent_old_id=parent_old_id if parent_old_id in included_ids else None,
                title=title,
                slug=slug,
                public_slug=public_slug,
                description=repair_text(row.get('description') or '').strip(),
                seo_title=repair_text(row.get('metatitle') or '').strip(),
                seo_description=repair_text(row.get('metadesc') or '').strip(),
                heading=repair_text(row.get('heading') or '').strip(),
                sort_order=int(row.get('ordering') or 0),
                is_active=True,
                created_at=self.parse_datetime(row.get('created')),
                updated_at=self.parse_datetime(row.get('created')),
                image_fullpath=(image_row[0].get('fullpath') if image_row else '') or '',
            )
        return imported

    def build_items(self, item_rows, image_rows, file_rows, imported_categories):
        image_map = defaultdict(list)
        for row in image_rows:
            if row.get('type') == 'item' and int(row.get('exclude') or 0) == 0:
                image_map[int(row['item_id'])].append(row)
        for rows in image_map.values():
            rows.sort(key=lambda row: (int(row.get('ordering') or 0), int(row.get('id') or 0)))

        file_map = defaultdict(list)
        for row in file_rows:
            if row.get('type') == 'item':
                file_map[int(row['item_id'])].append(row)
        for rows in file_map.values():
            rows.sort(key=lambda row: (int(row.get('ordering') or 0), int(row.get('id') or 0)))

        used_slugs = set()
        used_public_by_category = defaultdict(set)
        imported = {}
        for row in sorted(item_rows, key=lambda current: (int(current.get('cat_id') or 0), int(current.get('ordering') or 0), int(current['id']))):
            old_id = int(row['id'])
            category_old_id = int(row.get('cat_id') or 0)
            if category_old_id not in imported_categories:
                continue

            alias = self.clean_slug(row.get('alias') or row.get('name') or f'catalog-item-{old_id}')
            title = repair_text(row.get('name') or '').strip() or f'Позиция {old_id}'
            slug = self.ensure_unique(alias, used_slugs, f'catalog-item-{old_id}', 500)
            public_slug = self.ensure_unique(
                alias,
                used_public_by_category[category_old_id],
                f'catalog-item-{old_id}',
                500,
            )

            image_payloads = [
                (
                    image_row.get('fullpath') or '',
                    repair_text(image_row.get('caption') or '').strip(),
                    int(image_row.get('ordering') or 0),
                )
                for image_row in image_map.get(old_id, [])
            ]
            file_payloads = [
                (
                    file_row.get('fullpath') or '',
                    repair_text(file_row.get('caption') or '').strip(),
                    int(file_row.get('ordering') or 0),
                    int(file_row.get('hits') or 0),
                )
                for file_row in file_map.get(old_id, [])
            ]

            imported[old_id] = ImportedCatalogItem(
                old_id=old_id,
                old_alias=alias,
                category_old_id=category_old_id,
                title=title,
                slug=slug,
                public_slug=public_slug,
                excerpt=self.strip_and_shorten(row.get('intro_desc') or row.get('description') or '', 420),
                content=self.combine_html(row.get('intro_desc') or '', row.get('description') or ''),
                price=self.parse_decimal(row.get('price')),
                special_price=self.parse_decimal(row.get('special_price')),
                sku=repair_text(row.get('sku') or '').strip(),
                address=repair_text(row.get('address') or '').strip(),
                city=repair_text(row.get('city') or '').strip(),
                postcode=repair_text(row.get('postcode') or '').strip(),
                phone=repair_text(row.get('phone') or '').strip(),
                mobile=repair_text(row.get('mobile') or '').strip(),
                fax=repair_text(row.get('fax') or '').strip(),
                website=repair_text(row.get('website') or '').strip(),
                email=repair_text(row.get('email') or '').strip(),
                is_available=bool(int(row.get('available') or 0)),
                is_featured=bool(int(row.get('featured') or 0)),
                views=int(row.get('hits') or 0),
                seo_title=repair_text(row.get('metatitle') or '').strip(),
                seo_description=repair_text(row.get('metadesc') or '').strip(),
                sort_order=int(row.get('ordering') or 0),
                is_active=True,
                published_date=self.parse_datetime(row.get('publish_up')) or self.parse_datetime(row.get('created')),
                created_at=self.parse_datetime(row.get('created')),
                updated_at=self.parse_datetime(row.get('modified')) or self.parse_datetime(row.get('created')),
                image_fullpaths=image_payloads,
                file_fullpaths=file_payloads,
                category_public_slug=imported_categories[category_old_id].public_slug,
            )
        return imported

    def persist_categories(self, imported_categories, extractor):
        category_map = {}
        pending = dict(imported_categories)

        while pending:
            progressed = False
            for old_id, payload in list(pending.items()):
                if payload.parent_old_id and payload.parent_old_id not in category_map:
                    continue
                image_path = ''
                if payload.image_fullpath:
                    image_path = extractor.extract(
                        'image',
                        payload.image_fullpath,
                        f'uploads/catalog/categories/{payload.old_id}/{Path(payload.image_fullpath).name}',
                    )
                category_map[old_id] = CatalogCategory.objects.create(
                    title=payload.title,
                    slug=payload.slug,
                    public_slug=payload.public_slug,
                    parent=category_map.get(payload.parent_old_id),
                    description=payload.description,
                    seo_title=payload.seo_title,
                    seo_description=payload.seo_description,
                    heading=payload.heading,
                    image=image_path or None,
                    legacy_id=payload.old_id,
                    sort_order=payload.sort_order,
                    is_active=payload.is_active,
                    created_at=payload.created_at,
                    updated_at=payload.updated_at,
                )
                del pending[old_id]
                progressed = True
            if not progressed:
                raise CommandError('Не удалось выстроить иерархию категорий каталога.')

        return category_map

    def persist_items(self, imported_items, category_map, extractor):
        for payload in imported_items.values():
            main_image = ''
            extracted_images = []
            for fullpath, caption, ordering in payload.image_fullpaths:
                extracted = extractor.extract(
                    'image',
                    fullpath,
                    f'uploads/catalog/items/gallery/{payload.old_id}/{Path(fullpath).name}',
                )
                if extracted:
                    if not main_image:
                        main_image = extracted
                    extracted_images.append((extracted, caption, ordering))

            item = CatalogItem.objects.create(
                category=category_map[payload.category_old_id],
                title=payload.title,
                slug=payload.slug,
                public_slug=payload.public_slug,
                excerpt=payload.excerpt,
                content=payload.content,
                image=main_image or None,
                sku=payload.sku,
                price=payload.price,
                special_price=payload.special_price,
                address=payload.address,
                city=payload.city,
                postcode=payload.postcode,
                phone=payload.phone,
                mobile=payload.mobile,
                fax=payload.fax,
                website=payload.website,
                email=payload.email,
                is_available=payload.is_available,
                is_featured=payload.is_featured,
                views=payload.views,
                seo_title=payload.seo_title,
                seo_description=payload.seo_description,
                legacy_id=payload.old_id,
                sort_order=payload.sort_order,
                is_active=payload.is_active,
                published_date=payload.published_date,
                created_at=payload.created_at,
                updated_at=payload.updated_at,
            )

            CatalogItemImage.objects.bulk_create(
                [
                    CatalogItemImage(
                        item=item,
                        image=image_path,
                        caption=caption,
                        sort_order=ordering,
                    )
                    for image_path, caption, ordering in extracted_images
                ],
                batch_size=100,
            )

            CatalogItemFile.objects.bulk_create(
                [
                    CatalogItemFile(
                        item=item,
                        file=extractor.extract(
                            'file',
                            fullpath,
                            f'uploads/catalog/files/{payload.old_id}/{Path(fullpath).name}',
                        ),
                        title=title,
                        sort_order=ordering,
                        downloads=downloads,
                    )
                    for fullpath, title, ordering, downloads in payload.file_fullpaths
                    if extractor.extract(
                        'file',
                        fullpath,
                        f'uploads/catalog/files/{payload.old_id}/{Path(fullpath).name}',
                    )
                ],
                batch_size=100,
            )

    def persist_redirects(self, redirect_map):
        if not redirect_map:
            return
        LegacyRedirect.objects.filter(old_path__in=redirect_map.keys()).delete()
        LegacyRedirect.objects.bulk_create(
            [LegacyRedirect(old_path=old_path, new_path=new_path) for old_path, new_path in sorted(redirect_map.items())],
            batch_size=500,
        )

    def build_redirects(self, imported_categories, imported_items, sh404_rows, menu_rows):
        catalog_root_path = reverse('catalog')
        redirect_map = {}
        category_by_id = {category.old_id: category for category in imported_categories.values()}
        item_by_id = {item.old_id: item for item in imported_items.values()}
        category_aliases = {category.old_alias for category in imported_categories.values() if category.old_alias}

        for row in menu_rows:
            link = str(row.get('link') or '')
            path = self.normalize_old_path(row.get('path') or '')
            if int(row.get('published') or 0) != 1:
                continue
            if 'option=com_djcatalog2&view=items' not in link:
                continue
            if path and not path.startswith('com-djcatalog2'):
                self.add_redirect(redirect_map, path, catalog_root_path)

        for category in imported_categories.values():
            self.add_redirect(redirect_map, f'items/{category.old_id}-{category.old_alias}.html', category.new_path)
            self.add_redirect(redirect_map, f'{category.old_id}-{category.old_alias}.html', category.new_path)

        for item in imported_items.values():
            category = imported_categories[item.category_old_id]
            variants = {
                f'item/{category.old_id}-{category.old_alias}/{item.old_id}-{item.old_alias}.html',
                f'{category.old_id}-{category.old_alias}/{item.old_id}-{item.old_alias}.html',
            }
            if category.parent_old_id and category.parent_old_id in imported_categories:
                parent = imported_categories[category.parent_old_id]
                variants.add(f'item/{parent.old_id}-{parent.old_alias}/{item.old_id}-{item.old_alias}.html')
                variants.add(f'{parent.old_id}-{parent.old_alias}/{item.old_id}-{item.old_alias}.html')
            for variant in variants:
                self.add_redirect(redirect_map, variant, item.new_path)

        for row in sh404_rows:
            old_path = self.normalize_old_path(row.get('oldurl') or '')
            if not old_path:
                continue
            newurl = str(row.get('newurl') or '')
            target = ''
            if 'com_djcatalog2' in newurl:
                target = self.resolve_newurl_target(newurl, category_by_id, item_by_id, catalog_root_path)
            if not target:
                target = self.guess_target_from_old_path(old_path, category_by_id, item_by_id, category_aliases, catalog_root_path)
            if target:
                self.add_redirect(redirect_map, old_path, target)

        return redirect_map

    def resolve_newurl_target(self, newurl, category_by_id, item_by_id, catalog_root_path):
        query = urlsplit(newurl).query
        params = parse_qs(query)
        view = (params.get('view') or [''])[0]
        if view == 'item':
            item_id = self.safe_int((params.get('id') or [''])[0])
            if item_id in item_by_id:
                return item_by_id[item_id].new_path
        if view == 'items':
            category_id = self.safe_int((params.get('cid') or [''])[0])
            if category_id in category_by_id:
                return category_by_id[category_id].new_path
            return catalog_root_path
        return ''

    def guess_target_from_old_path(self, old_path, category_by_id, item_by_id, category_aliases, catalog_root_path):
        probe = old_path.lower()
        if (
            not probe.startswith(('item/', 'items/'))
            and not any(alias in probe for alias in category_aliases)
            and 'kupit-tovary' not in probe
            and 'tovary-i-uslugi' not in probe
        ):
            return ''

        if 'kupit-tovary-i-zakazat-uslugi' in probe or 'tovary-i-uslugi-po-' in probe:
            return catalog_root_path

        segments = [segment for segment in old_path.split('/') if segment]
        filtered_segments = segments[1:] if segments and segments[0] in {'item', 'items'} else segments
        if filtered_segments:
            item_id = self.extract_leading_id(filtered_segments[-1])
            if item_id in item_by_id:
                return item_by_id[item_id].new_path
            category_id = self.extract_leading_id(filtered_segments[-1])
            if category_id in category_by_id:
                return category_by_id[category_id].new_path
        return ''

    def add_redirect(self, redirect_map, old_path, new_path):
        old_path = self.normalize_old_path(old_path)
        if not old_path or not new_path:
            return
        if old_path == new_path.strip('/'):
            return
        redirect_map.setdefault(old_path, new_path)

    def _include_ancestors(self, category_id, rows_by_id, included_ids):
        current_id = category_id
        while current_id:
            row = rows_by_id.get(current_id)
            if row is None:
                break
            included_ids.add(current_id)
            current_id = int(row.get('parent_id') or 0)

    def _category_depth(self, row, rows_by_id):
        depth = 0
        current_id = int(row.get('parent_id') or 0)
        while current_id and current_id in rows_by_id:
            depth += 1
            current_id = int(rows_by_id[current_id].get('parent_id') or 0)
        return depth

    def clean_slug(self, value):
        value = repair_text(str(value or '').strip())
        if not value:
            return ''
        if re.fullmatch(r'[0-9A-Za-z_-]+', value):
            return value.lower()
        return translit_slug(value)

    def ensure_unique(self, candidate, used, fallback, max_length):
        base = (candidate or fallback or 'catalog').strip('-').lower()[:max_length].strip('-')
        if not base:
            base = fallback
        current = base
        suffix = 2
        while current in used:
            current = f'{base[: max_length - len(str(suffix)) - 1]}-{suffix}'.strip('-')
            suffix += 1
        used.add(current)
        return current

    def combine_html(self, intro_html, description_html):
        intro_html = repair_text(intro_html or '').strip()
        description_html = repair_text(description_html or '').strip()
        if intro_html and description_html and intro_html != description_html:
            return f'{intro_html}\n<hr>\n{description_html}'
        return description_html or intro_html

    def strip_and_shorten(self, html, limit):
        text = re.sub(r'\s+', ' ', strip_tags(repair_text(html or '')).replace('\xa0', ' ')).strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip(' .,;:') + '...'

    def parse_datetime(self, raw_value):
        if not raw_value or raw_value in {ZERO_DATETIME, ZERO_DATE, '0'}:
            return None
        raw_value = str(raw_value).strip()
        if len(raw_value) == 10:
            raw_value = f'{raw_value} 00:00:00'
        try:
            parsed = timezone.datetime.strptime(raw_value, DATETIME_FORMAT)
        except ValueError:
            return None
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    def parse_decimal(self, raw_value):
        if raw_value in (None, '', 0, 0.0, '0', '0.0'):
            return None
        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, ValueError):
            return None
        if value <= 0:
            return None
        return value

    def normalize_old_path(self, path):
        if not path:
            return ''
        path = str(path).strip()
        if not path:
            return ''
        if path.startswith(('http://', 'https://')):
            path = urlsplit(path).path or ''
        path = path.split('?', 1)[0].split('#', 1)[0]
        path = path.replace('\\', '/').strip('/')
        if '.html' in path and not path.endswith('.html'):
            html_index = path.find('.html')
            path = path[:html_index + 5]
        return re.sub(r'/+', '/', path)

    def extract_leading_id(self, segment):
        normalized = segment.strip()
        if normalized.endswith('.html'):
            normalized = normalized[:-5]
        match = LEADING_ID_RE.match(normalized)
        if not match:
            return None
        return int(match.group('id'))

    def safe_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
