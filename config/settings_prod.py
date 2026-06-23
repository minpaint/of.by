from .settings import *

DEBUG = False

SECRET_KEY = os.environ['SECRET_KEY']

ALLOWED_HOSTS = [
    'ohranatruda.of.by', 'www.ohranatruda.of.by',
    'of.by', 'www.of.by',
    '127.0.0.1', 'localhost',
    '192.168.37.10', '192.168.37.55',
]

CSRF_TRUSTED_ORIGINS = [
    'https://ohranatruda.of.by', 'https://www.ohranatruda.of.by',
    'https://of.by', 'https://www.of.by',
]

# За https-прокси CWP (терминация SSL на 192.168.37.55) Django получает запрос
# по http; этот заголовок сообщает ему, что исходный запрос был https.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(os.environ.get('OF_BY_DB_PATH', '/home/django/webapps/ofby/db.sqlite3')),
        # SQLite под несколькими воркерами gunicorn: WAL позволяет читателям и
        # писателю работать одновременно, busy timeout заставляет короткую
        # блокировку подождать вместо ошибки, а IMMEDIATE-транзакции берут
        # запись-лок сразу и не упираются в «database is locked».
        'OPTIONS': {
            'timeout': 20,
            'transaction_mode': 'IMMEDIATE',
            'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;',
        },
    }
}

STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise: gunicorn сам отдаёт статику (панель проксирует напрямую на gunicorn,
# минуя локальный nginx). Middleware вставляем сразу после SecurityMiddleware.
MIDDLEWARE = MIDDLEWARE[:1] + [
    'whitenoise.middleware.WhiteNoiseMiddleware',
] + MIDDLEWARE[1:]

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': os.environ.get('OF_BY_CACHE_DIR', '/home/django/webapps/ofby/cache'),
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 2000,
        },
    }
}

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True

# Дефолт Django 'same-origin' не передаёт реферер на сторонние домены,
# из-за чего YouTube-эмбеды падали с «Ошибка 153». 'strict-origin-when-cross-origin'
# передаёт только origin (https://ohranatruda.of.by) — достаточно для плеера, без утечки пути.
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
