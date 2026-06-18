import os
from pathlib import Path
from importlib.util import find_spec

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-lrio2p^arg-^6qs7s0$g!vbo2ios!&pqg!=y*1!vp@t3j$a@%_'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django_ckeditor_5',
    'content',
]

if find_spec('jazzmin') is not None:
    INSTALLED_APPS.insert(0, 'jazzmin')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'content.context_processors.header_banner',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(os.environ.get('OF_BY_DB_PATH', r'C:\projects\of_by\db.sqlite3')),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Minsk'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOCAL_CACHE_ROOT = Path(
    os.environ.get('OF_BY_CACHE_DIR')
    or (Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'of_by_cache')
)
LOCAL_CACHE_ROOT.mkdir(parents=True, exist_ok=True)

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(LOCAL_CACHE_ROOT),
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 2000,
        },
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

JAZZMIN_SETTINGS = {
    'site_title': 'of.by admin',
    'site_header': 'of.by',
    'site_brand': 'of.by',
    'welcome_sign': 'Управление структурой сайта и материалами',
    'copyright': 'of.by',
    'search_model': ['content.Category', 'content.ContentItem', 'content.Banner', 'content.LeadSettings', 'content.SmtpSettings'],
    'topmenu_links': [
        {'name': 'Открыть сайт', 'url': '/', 'new_window': True},
        {'model': 'content.Category'},
        {'model': 'content.ContentItem'},
        {'model': 'content.Banner'},
        {'model': 'content.LeadSettings'},
        {'model': 'content.SmtpSettings'},
    ],
    'icons': {
        'auth': 'fas fa-users-cog',
        'auth.user': 'fas fa-user',
        'auth.Group': 'fas fa-users',
        'content.Category': 'fas fa-sitemap',
        'content.ContentItem': 'fas fa-newspaper',
        'content.ContentFeedBlock': 'fas fa-layer-group',
        'content.Banner': 'fas fa-image',
        'content.LeadSettings': 'fas fa-envelope-open-text',
        'content.LegacyRedirect': 'fas fa-route',
        'content.SmtpSettings': 'fas fa-cogs',
    },
    'order_with_respect_to': [
        'content',
        'content.Category',
        'content.ContentItem',
        'content.ContentFeedBlock',
        'content.Banner',
        'content.LeadSettings',
        'content.SmtpSettings',
        'content.LegacyRedirect',
    ],
    'show_sidebar': True,
    'navigation_expanded': True,
    'changeform_format': 'horizontal_tabs',
    'related_modal_active': True,
    'custom_css': 'css/admin-overrides.css',
}

CKEDITOR_5_UPLOAD_PATH = 'uploads/'
CKEDITOR_5_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
CKEDITOR_5_USER_LANGUAGE = True
CKEDITOR_5_ALLOW_ALL_FILE_TYPES = False

CKEDITOR_5_CUSTOM_COLOR_PALETTE = [
    {'color': 'hsl(4, 90%, 58%)', 'label': 'Red'},
    {'color': 'hsl(340, 82%, 52%)', 'label': 'Pink'},
    {'color': 'hsl(291, 64%, 42%)', 'label': 'Purple'},
    {'color': 'hsl(262, 52%, 47%)', 'label': 'Deep Purple'},
    {'color': 'hsl(231, 48%, 48%)', 'label': 'Indigo'},
    {'color': 'hsl(207, 90%, 54%)', 'label': 'Blue'},
    {'color': 'hsl(122, 39%, 49%)', 'label': 'Green'},
    {'color': 'hsl(36, 100%, 50%)', 'label': 'Orange'},
    {'color': 'hsl(0, 0%, 0%)', 'label': 'Black'},
    {'color': 'hsl(0, 0%, 100%)', 'label': 'White'},
]

CKEDITOR_5_CONFIGS = {
    'default': {
        'blockToolbar': [
            'paragraph',
            'heading1',
            'heading2',
            'heading3',
            '|',
            'bulletedList',
            'numberedList',
            'todoList',
            '|',
            'blockQuote',
            'insertTable',
            'mediaEmbed',
            'codeBlock',
        ],
        'toolbar': {
            'items': [
                'heading', 'style', '|',
                'outdent', 'indent', 'alignment', '|',
                'bold', 'italic', 'underline', 'strikethrough', 'code', 'subscript', 'superscript', 'highlight', '|',
                'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', '|',
                'link', 'insertImage', 'mediaEmbed', 'insertTable', 'blockQuote', 'codeBlock', 'htmlEmbed', 'horizontalLine', 'pageBreak', 'specialCharacters', '|',
                'bulletedList', 'numberedList', 'todoList', '|',
                'removeFormat', 'showBlocks', 'findAndReplace', 'selectAll', 'sourceEditing', '|',
                'undo', 'redo',
            ],
            'shouldNotGroupWhenFull': True,
        },
        'language': 'ru',
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragraph', 'class': 'ck-heading_paragraph'},
                {'model': 'heading1', 'view': 'h1', 'title': 'Heading 1', 'class': 'ck-heading_heading1'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2', 'class': 'ck-heading_heading2'},
                {'model': 'heading3', 'view': 'h3', 'title': 'Heading 3', 'class': 'ck-heading_heading3'},
                {'model': 'heading4', 'view': 'h4', 'title': 'Heading 4', 'class': 'ck-heading_heading4'},
            ]
        },
        'list': {
            'properties': {
                'styles': True,
                'startIndex': True,
                'reversed': True,
            }
        },
        'image': {
            'toolbar': [
                'imageTextAlternative',
                'toggleImageCaption',
                '|',
                'imageStyle:inline',
                'imageStyle:block',
                'imageStyle:side',
                'imageStyle:alignLeft',
                'imageStyle:alignCenter',
                'imageStyle:alignRight',
                '|',
                'resizeImage',
            ],
            'styles': [
                'full',
                'side',
                'alignLeft',
                'alignCenter',
                'alignRight',
            ],
        },
        'table': {
            'contentToolbar': [
                'tableColumn',
                'tableRow',
                'mergeTableCells',
                'tableProperties',
                'tableCellProperties',
            ],
            'tableProperties': {
                'borderColors': CKEDITOR_5_CUSTOM_COLOR_PALETTE,
                'backgroundColors': CKEDITOR_5_CUSTOM_COLOR_PALETTE,
            },
            'tableCellProperties': {
                'borderColors': CKEDITOR_5_CUSTOM_COLOR_PALETTE,
                'backgroundColors': CKEDITOR_5_CUSTOM_COLOR_PALETTE,
            },
        },
        'fontFamily': {
            'supportAllValues': True,
        },
        'fontSize': {
            'options': [10, 12, 14, 'default', 18, 20, 22, 24, 28, 32, 36],
            'supportAllValues': True,
        },
        'htmlSupport': {
            'allow': [
                {
                    'name': '.*',
                    'attributes': True,
                    'classes': True,
                    'styles': True,
                }
            ]
        },
        'height': 760,
        'width': '100%',
    },
}

# General site settings
SITE_NAME = 'of.by'
SITE_DOMAIN = 'https://of.by'
DEFAULT_FROM_EMAIL = 'webmaster@localhost' # Default fallback

# Dynamically load SMTP settings from the database
try:
    from content.models import SmtpSettings
    # This check is to prevent errors during migrations when the table does not exist yet
    from django.db import connection
    if 'content_smtpsettings' in connection.introspection.table_names():
        smtp_settings = SmtpSettings.objects.filter(is_active=True).first()
        if smtp_settings:
            EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
            EMAIL_HOST = smtp_settings.host
            EMAIL_PORT = smtp_settings.port
            EMAIL_HOST_USER = smtp_settings.username
            EMAIL_HOST_PASSWORD = smtp_settings.password
            EMAIL_USE_TLS = smtp_settings.use_tls
            EMAIL_USE_SSL = smtp_settings.use_ssl
except Exception as e:
    # This might fail if the database is not ready yet, e.g., during migrations
    # It's better to use a lazy loading mechanism in production
    print(f"Could not load SMTP settings from database: {e}")
