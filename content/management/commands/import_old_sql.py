import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from content.models import Banner, Category, ContentItem, LegacyRedirect


DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
ZERO_DATETIME = '0000-00-00 00:00:00'
ZERO_DATE = '0000-00-00'
YOUTUBE_PATTERNS = [
    re.compile(r'https?://(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]{6,})'),
    re.compile(r'https?://(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{6,})'),
    re.compile(r'https?://youtu\.be/([A-Za-z0-9_-]{6,})'),
]
IMG_SRC_RE = re.compile(r'<img[^>]+src=(["\'])(.+?)\1', re.IGNORECASE)
ATTR_RE = re.compile(r'(?P<attr>href|src)=(?P<quote>["\'])(?P<value>.+?)(?P=quote)', re.IGNORECASE)
OLD_DOMAIN_RE = re.compile(r'https?://(?:www\.)?ohranatruda\.of\.by/', re.IGNORECASE)
BLOCKED_REDIRECT_PREFIXES = (
    'component/',
    'modules/',
    'plugins/',
    'templates/',
    'administrator/',
    'cache/',
    'tmp/',
    'language/',
    'wp-',
    '.well-known',
    'apple-touch-icon',
    'favicon',
    'robots.txt',
    'sitemap',
    'index.php',
)
BLOCKED_REDIRECT_EXTENSIONS = (
    '.php', '.ico', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.css',
    '.js', '.xml', '.txt', '.json', '.zip', '.rar', '.7z', '.mp3', '.mp4',
)


@dataclass
class ImportedCategory:
    old_id: int
    old_alias: str
    old_path: str
    slug: str
    title: str
    description: str
    color: str
    icon: str
    sort_order: int
    is_active: bool

    @property
    def new_path(self):
        return f'/{self.slug}/'


@dataclass
class ImportedItem:
    old_id: int
    original_alias: str
    category_old_id: int
    category_slug: str
    slug: str
    title: str
    excerpt: str
    content: str
    content_type: str
    image: str
    video_url: str
    file_path: str
    file_title: str
    author: str
    views: int
    is_featured: bool
    is_main_slider: bool
    published_date: datetime | None
    event_date: datetime | None
    price: Decimal | None
    tags: str
    seo_title: str
    seo_description: str
    status: str
    created_at: datetime
    updated_at: datetime
    category_slug_for_url: str

    @property
    def new_path(self):
        return f'/{self.category_slug_for_url}/{self.slug}/'


class DumpParser:
    ESCAPE_MAP = {
        '0': '\0',
        'b': '\b',
        'n': '\n',
        'r': '\r',
        't': '\t',
        'Z': '\x1a',
        '\\': '\\',
        "'": "'",
        '"': '"',
    }

    def __init__(self, dump_text: str):
        self.dump_text = dump_text
        self._columns_cache: dict[str, list[str]] = {}

    def get_columns(self, table: str) -> list[str]:
        if table in self._columns_cache:
            return self._columns_cache[table]

        marker = f'CREATE TABLE `{table}` ('
        start = self.dump_text.find(marker)
        if start == -1:
            raise CommandError(f'Не найдена структура таблицы {table} в old.sql')
        start += len(marker)
        end = self.dump_text.find(') ENGINE=', start)
        columns = []
        for line in self.dump_text[start:end].splitlines():
            line = line.strip()
            if line.startswith('`'):
                columns.append(line.split('`', 2)[1])
        self._columns_cache[table] = columns
        return columns

    def iter_rows(self, table: str):
        prefix = f'INSERT INTO `{table}` VALUES '
        columns = self.get_columns(table)
        position = 0

        while True:
            start = self.dump_text.find(prefix, position)
            if start == -1:
                break
            start += len(prefix)
            end = self.dump_text.find(';\n', start)
            if end == -1:
                end = len(self.dump_text)
            values_blob = self.dump_text[start:end]
            for raw_row in self._parse_values_blob(values_blob):
                converted = [self._convert(token, quoted) for token, quoted in raw_row]
                yield dict(zip(columns, converted))
            position = end + 2

    @staticmethod
    def _parse_values_blob(blob: str):
        rows = []
        index = 0
        length = len(blob)

        while index < length:
            while index < length and blob[index] != '(':
                index += 1
            if index >= length:
                break

            index += 1
            row = []
            current = []
            in_string = False
            escape = False
            quoted = False

            while index < length:
                char = blob[index]
                if in_string:
                    if escape:
                        current.append(DumpParser.ESCAPE_MAP.get(char, char))
                        escape = False
                    elif char == '\\':
                        escape = True
                    elif char == "'":
                        in_string = False
                    else:
                        current.append(char)
                else:
                    if char == "'":
                        in_string = True
                        quoted = True
                    elif char == ',':
                        row.append((''.join(current), quoted))
                        current = []
                        quoted = False
                    elif char == ')':
                        row.append((''.join(current), quoted))
                        rows.append(row)
                        index += 1
                        break
                    else:
                        current.append(char)
                index += 1

        return rows

    @staticmethod
    def _convert(token: str, quoted: bool):
        if quoted:
            return token
        token = token.strip()
        if token == 'NULL':
            return None
        if token == '':
            return ''
        try:
            return int(token)
        except ValueError:
            try:
                return float(token)
            except ValueError:
                return token


class Command(BaseCommand):
    help = 'Импортирует опубликованные категории, статьи и legacy redirect-ы из old.sql в SQLite.'

    def add_arguments(self, parser):
        parser.add_argument('--sql-path', default='old.sql', help='Путь к MySQL-дампу old.sql')
        parser.add_argument('--clear', action='store_true', help='Очистить демонстрационные данные перед импортом')

    def handle(self, *args, **options):
        sql_path = Path(options['sql_path'])
        if not sql_path.is_absolute():
            sql_path = Path(settings.BASE_DIR) / sql_path
        if not sql_path.exists():
            raise CommandError(f'Файл дампа не найден: {sql_path}')

        self.stdout.write(f'Читаю дамп: {sql_path}')
        parser = DumpParser(sql_path.read_text(encoding='utf-8'))

        category_rows = [
            row for row in parser.iter_rows('pkulc_categories')
            if row['extension'] == 'com_content' and int(row['published']) == 1 and int(row['id']) != 1
        ]
        item_rows = [
            row for row in parser.iter_rows('pkulc_content')
            if int(row['state']) == 1
        ]
        sh404_rows = list(parser.iter_rows('pkulc_sh404sef_urls'))

        imported_categories = self.build_categories(category_rows)
        imported_items = self.build_items(item_rows, imported_categories)
        redirect_map = self.build_redirects(imported_categories, imported_items, sh404_rows)

        self.stdout.write(
            f'Подготовлено: {len(imported_categories)} категорий, '
            f'{len(imported_items)} материалов, {len(redirect_map)} redirect-ов.'
        )

        with transaction.atomic():
            if options['clear']:
                Banner.objects.all().delete()
                LegacyRedirect.objects.all().delete()
                ContentItem.objects.all().delete()
                Category.objects.all().delete()
                self.stdout.write(self.style.WARNING('Существующие демонстрационные данные удалены.'))

            self.persist_categories(imported_categories)
            category_map = {category.slug: category for category in Category.objects.all()}
            self.persist_items(imported_items, category_map)
            self.persist_redirects(redirect_map)

        self.stdout.write(self.style.SUCCESS(
            f'Импорт завершён: {Category.objects.count()} категорий, '
            f'{ContentItem.objects.count()} материалов, {LegacyRedirect.objects.count()} redirect-ов.'
        ))

    def build_categories(self, rows):
        alias_counts = Counter((row['alias'] or '').strip() for row in rows)
        used_slugs = set()
        imported = {}

        for row in sorted(rows, key=lambda item: (int(item['lft']), int(item['id']))):
            old_alias = (row['alias'] or '').strip()
            old_path = self.normalize_old_path(row['path'] or '')
            slug = self.make_category_slug(row, alias_counts, used_slugs)
            imported[int(row['id'])] = ImportedCategory(
                old_id=int(row['id']),
                old_alias=old_alias,
                old_path=old_path,
                slug=slug,
                title=(row['title'] or '').strip() or slug,
                description=self.coalesce_text(row['metadesc'], self.strip_and_shorten(row['description'], 240)),
                color=self.detect_category_color(old_path, row['title'] or '', old_alias),
                icon=self.detect_category_icon(old_path, row['title'] or '', old_alias),
                sort_order=int(row['lft']),
                is_active=True,
            )
            used_slugs.add(slug)

        if 2 not in imported:
            imported[2] = ImportedCategory(
                old_id=2,
                old_alias='uncategorised',
                old_path='uncategorised',
                slug='uncategorised',
                title='Uncategorised',
                description='Материалы без явной категории.',
                color='gray',
                icon='📁',
                sort_order=999999,
                is_active=True,
            )

        return imported

    def build_items(self, rows, imported_categories):
        alias_counts = Counter((row['alias'] or '').strip() for row in rows)
        used_slugs = set()
        imported = []

        for row in rows:
            category_old_id = int(row['catid']) if row['catid'] is not None else 2
            if category_old_id not in imported_categories:
                category_old_id = 2

            category = imported_categories[category_old_id]
            original_alias = (row['alias'] or '').strip()
            slug = self.make_item_slug(row, category.slug, alias_counts, used_slugs)
            content_html = self.combine_content(row['introtext'] or '', row['fulltext'] or '')
            content_html = self.rewrite_html(content_html)
            excerpt = self.strip_and_shorten(row['introtext'] or content_html, 420)
            image_path = self.extract_image_path(row, content_html)
            video_url = self.extract_video_url(content_html)
            content_type = self.detect_content_type(row, category.old_path, content_html, video_url)
            published_date = self.parse_datetime(row['publish_up']) or self.parse_datetime(row['created']) or self.parse_datetime(row['modified'])
            updated_at = self.parse_datetime(row['modified']) or published_date or timezone.now()
            created_at = self.parse_datetime(row['created']) or published_date or updated_at

            imported.append(
                ImportedItem(
                    old_id=int(row['id']),
                    original_alias=original_alias,
                    category_old_id=category_old_id,
                    category_slug=category.slug,
                    slug=slug,
                    title=(row['title'] or '').strip() or slug,
                    excerpt=excerpt,
                    content=content_html,
                    content_type=content_type,
                    image=image_path,
                    video_url=video_url,
                    file_path='',
                    file_title='',
                    author=(row['created_by_alias'] or '').strip(),
                    views=int(row['hits'] or 0),
                    is_featured=bool(int(row['featured'] or 0)),
                    is_main_slider=bool(int(row['featured'] or 0)),
                    published_date=published_date,
                    event_date=None,
                    price=None,
                    tags=self.normalize_tags(row['metakey']),
                    seo_title=(row['title'] or '').strip(),
                    seo_description=self.coalesce_text(row['metadesc'], excerpt),
                    status='published',
                    created_at=created_at,
                    updated_at=updated_at,
                    category_slug_for_url=category.slug,
                )
            )
            used_slugs.add(slug)

        return imported

    def build_redirects(self, categories, items, sh404_rows):
        redirect_map = {}
        category_by_path = {category.old_path: category for category in categories.values() if category.old_path}
        unique_category_alias_map = self.make_unique_lookup([category.old_alias for category in categories.values()])
        category_by_alias = {category.old_alias: category for category in categories.values() if category.old_alias in unique_category_alias_map}

        unique_item_aliases = self.make_unique_lookup([item.original_alias for item in items])
        item_by_alias = {item.original_alias: item for item in items if item.original_alias in unique_item_aliases}

        for category in categories.values():
            self.add_redirect(redirect_map, category.old_path, category.new_path)
            if category.old_alias and category.old_alias in unique_category_alias_map:
                self.add_redirect(redirect_map, category.old_alias, category.new_path)

        for item in items:
            category = categories[item.category_old_id]
            guessed_paths = {
                f'{category.old_path}/{item.original_alias}.html' if category.old_path and item.original_alias else '',
                f'{category.old_path}/{item.original_alias}' if category.old_path and item.original_alias else '',
                f'{item.original_alias}.html' if item.original_alias else '',
                item.original_alias,
            }
            for guessed_path in guessed_paths:
                self.add_redirect(redirect_map, guessed_path, item.new_path)

        for row in sh404_rows:
            old_path = self.normalize_old_path(row.get('oldurl') or '')
            if not self.should_keep_sh404_path(old_path):
                continue

            if old_path in category_by_path:
                self.add_redirect(redirect_map, old_path, category_by_path[old_path].new_path)
                continue

            last_segment = self.extract_last_segment(old_path)
            if last_segment in item_by_alias:
                self.add_redirect(redirect_map, old_path, item_by_alias[last_segment].new_path)
                continue
            if last_segment in category_by_alias:
                self.add_redirect(redirect_map, old_path, category_by_alias[last_segment].new_path)

        return redirect_map

    def persist_categories(self, categories):
        Category.objects.bulk_create([
            Category(
                title=category.title,
                slug=category.slug,
                color=category.color,
                icon=category.icon,
                description=category.description,
                sort_order=category.sort_order,
                is_active=category.is_active,
            )
            for category in categories.values()
        ])

    def persist_items(self, imported_items, category_map):
        objects = []
        for item in imported_items:
            category = category_map.get(item.category_slug)
            objects.append(
                ContentItem(
                    category=category,
                    content_type=item.content_type,
                    title=item.title,
                    slug=item.slug,
                    excerpt=item.excerpt,
                    content=item.content,
                    image=item.image or None,
                    video_url=item.video_url,
                    file=item.file_path or None,
                    file_title=item.file_title,
                    author=item.author,
                    views=item.views,
                    is_featured=item.is_featured,
                    is_main_slider=item.is_main_slider,
                    published_date=item.published_date,
                    event_date=item.event_date,
                    price=item.price,
                    tags=item.tags,
                    seo_title=item.seo_title,
                    seo_description=item.seo_description,
                    status=item.status,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
            )

        ContentItem.objects.bulk_create(objects, batch_size=200)

        slider_ids = list(
            ContentItem.objects.filter(status='published', is_featured=True, image__isnull=False)
            .exclude(image='')
            .order_by('-views', '-published_date')
            .values_list('id', flat=True)[:12]
        )
        ContentItem.objects.exclude(id__in=slider_ids).update(is_main_slider=False)
        if slider_ids:
            ContentItem.objects.filter(id__in=slider_ids).update(is_main_slider=True)

    def persist_redirects(self, redirect_map):
        LegacyRedirect.objects.bulk_create(
            [LegacyRedirect(old_path=old_path, new_path=new_path) for old_path, new_path in sorted(redirect_map.items())],
            batch_size=500,
        )

    def make_category_slug(self, row, alias_counts, used_slugs):
        alias = (row['alias'] or '').strip()
        path = self.normalize_old_path(row['path'] or '')
        candidates = []
        if alias and alias_counts[alias] == 1:
            candidates.append(alias)
        if path:
            candidates.append(path.replace('/', '-'))
            candidates.append(path.split('/')[-1])
        if alias:
            candidates.append(f'{alias}-{int(row["id"])}')
        candidates.append(f'category-{int(row["id"])}')
        return self.pick_unique_slug(candidates, used_slugs, max_length=200)

    def make_item_slug(self, row, category_slug, alias_counts, used_slugs):
        alias = (row['alias'] or '').strip()
        candidates = []
        if alias and alias_counts[alias] == 1:
            candidates.append(alias)
        if alias:
            candidates.append(f'{category_slug}-{alias}')
            candidates.append(f'{alias}-{int(row["id"])}')
        candidates.append(f'item-{int(row["id"])}')
        return self.pick_unique_slug(candidates, used_slugs, max_length=500)

    @staticmethod
    def pick_unique_slug(candidates, used_slugs, max_length):
        for candidate in candidates:
            cleaned = re.sub(r'[^0-9A-Za-z_-]+', '-', (candidate or '').strip()).strip('-').lower()
            cleaned = cleaned[:max_length].strip('-')
            if cleaned and cleaned not in used_slugs:
                return cleaned
        base = 'item'
        suffix = 1
        while f'{base}-{suffix}' in used_slugs:
            suffix += 1
        return f'{base}-{suffix}'

    @staticmethod
    def detect_category_color(path, title, alias):
        probe = f'{path} {title} {alias}'.lower()
        if 'pozhar' in probe or 'fire' in probe:
            return 'red'
        if 'ekolog' in probe:
            return 'green'
        if 'health' in probe or 'prom' in probe or 'industrial' in probe:
            return 'orange'
        if 'arm' in probe or 'attest' in probe or 'biznes' in probe or 'business' in probe:
            return 'purple'
        if 'grazhdansk' in probe or 'go' in probe:
            return 'gray'
        if 'vopros' in probe or 'otvet' in probe:
            return 'indigo'
        return 'blue'

    @staticmethod
    def detect_category_icon(path, title, alias):
        color = Command.detect_category_color(path, title, alias)
        return {
            'blue': '🛡️',
            'red': '🔥',
            'orange': '🏭',
            'green': '🌿',
            'purple': '💼',
            'gray': '🛟',
            'indigo': '❓',
        }.get(color, '📁')

    def combine_content(self, introtext, fulltext):
        introtext = (introtext or '').strip()
        fulltext = (fulltext or '').strip()
        if introtext and fulltext:
            return f'{introtext}\n<hr>\n{fulltext}'
        return introtext or fulltext

    def rewrite_html(self, html):
        if not html:
            return ''

        html = OLD_DOMAIN_RE.sub('/', html)

        def replace_attr(match):
            attr = match.group('attr')
            quote = match.group('quote')
            value = match.group('value').strip()
            normalized = value

            if normalized.startswith(('http://', 'https://', '//', 'mailto:', 'tel:', '#', 'data:')):
                return match.group(0)

            normalized = normalized.lstrip('./')
            normalized = normalized.lstrip('/')

            if normalized.startswith('images/'):
                new_value = f'/media/{normalized}'
            elif normalized.startswith('media/'):
                new_value = f'/{normalized}'
            elif normalized.endswith('.html') or normalized.startswith((
                'news/', 'informatsiya/', 'viewcategory/', 'view.download/', 'm/', 'mobile/', 'grazhdanskaya-oborona',
                'novosti-zakonodatelstva', 'pozharnaya-bezopasnost', 'okhrana-truda', 'ekologiya',
            )):
                new_value = f'/{normalized}'
            else:
                return match.group(0)

            return f'{attr}={quote}{new_value}{quote}'

        return ATTR_RE.sub(replace_attr, html)

    def extract_image_path(self, row, content_html):
        json_candidate = self.extract_image_from_json(row.get('images') or '')
        if json_candidate:
            return json_candidate

        match = IMG_SRC_RE.search(content_html or '')
        if not match:
            return ''
        return self.normalize_media_path(match.group(2))

    @staticmethod
    def extract_image_from_json(raw_json):
        if not raw_json:
            return ''
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            return ''

        for key in ('image_intro', 'image_fulltext'):
            value = payload.get(key)
            normalized = Command.normalize_media_path(value)
            if normalized:
                return normalized
        return ''

    @staticmethod
    def extract_video_url(content_html):
        if not content_html:
            return ''
        for pattern in YOUTUBE_PATTERNS:
            match = pattern.search(content_html)
            if match:
                return match.group(0)
        iframe_match = re.search(r'<iframe[^>]+src=(["\'])(.+?)\1', content_html, re.IGNORECASE)
        if iframe_match:
            return iframe_match.group(2)
        return ''

    @staticmethod
    def detect_content_type(row, category_path, content_html, video_url):
        title = (row.get('title') or '').lower()
        probe = f'{title} {category_path} {(content_html or "").lower()}'
        if video_url:
            if 'webinar' in probe or 'вебинар' in probe:
                return 'event'
            return 'video'
        return 'article'

    @staticmethod
    def normalize_media_path(value):
        if not value:
            return ''
        value = value.strip()
        if value.startswith(('http://', 'https://', '//')):
            return ''
        value = value.lstrip('/')
        value = value.replace('\\', '/')
        if value.startswith('media/'):
            value = value[len('media/'):]
        if value.startswith('images/'):
            return value
        if value.startswith('/media/images/'):
            return value[len('/media/'):]
        if value.startswith('/images/'):
            return value[1:]
        if value.startswith('uploads/'):
            return value
        return ''

    @staticmethod
    def strip_and_shorten(html, limit):
        if not html:
            return ''
        text = re.sub(r'\s+', ' ', strip_tags(html).replace('\xa0', ' ')).strip()
        if len(text) <= limit:
            return text
        return text[:limit].rstrip(' .,;:') + '...'

    @staticmethod
    def coalesce_text(*values):
        for value in values:
            if value:
                cleaned = str(value).strip()
                if cleaned:
                    return cleaned
        return ''

    @staticmethod
    def normalize_tags(raw_tags):
        if not raw_tags:
            return ''
        parts = [part.strip() for part in re.split(r'[,;]+', str(raw_tags)) if part.strip()]
        return ', '.join(parts[:20])

    @staticmethod
    def parse_datetime(raw_value):
        if not raw_value or raw_value in {ZERO_DATETIME, ZERO_DATE, '0'}:
            return None
        raw_value = str(raw_value).strip()
        if len(raw_value) == 10:
            raw_value = f'{raw_value} 00:00:00'
        try:
            parsed = datetime.strptime(raw_value, DATETIME_FORMAT)
        except ValueError:
            return None
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed

    @staticmethod
    def parse_decimal(raw_value):
        if raw_value in (None, ''):
            return None
        try:
            return Decimal(str(raw_value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def make_unique_lookup(values):
        counts = Counter(value for value in values if value)
        return {value for value, count in counts.items() if count == 1}

    @staticmethod
    def extract_last_segment(path):
        normalized = (path or '').strip('/')
        if not normalized:
            return ''
        last = normalized.split('/')[-1]
        if last.endswith('.html'):
            last = last[:-5]
        return last

    @staticmethod
    def normalize_old_path(path):
        if not path:
            return ''
        path = str(path).strip()
        if not path:
            return ''

        if path.startswith(('http://', 'https://')):
            split = urlsplit(path)
            path = split.path or ''

        path = path.split('?', 1)[0].split('#', 1)[0]
        path = path.replace('\\', '/').strip('/')
        path = re.sub(r'/+', '/', path)
        return path

    @staticmethod
    def should_keep_sh404_path(path):
        if not path or path == 'index.php':
            return False
        if path.startswith(BLOCKED_REDIRECT_PREFIXES):
            return False
        if path.endswith(BLOCKED_REDIRECT_EXTENSIONS):
            return False
        if path.startswith('images/'):
            return False
        return True

    @staticmethod
    def add_redirect(redirect_map, old_path, new_path):
        old_path = Command.normalize_old_path(old_path)
        if not old_path or not new_path:
            return
        current_path = new_path.strip('/')
        if old_path == current_path:
            return
        redirect_map.setdefault(old_path, new_path)
