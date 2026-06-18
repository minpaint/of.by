from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView, TemplateView
from django.views.static import serve as serve_static
from content import views as content_views
from content.sitemaps import sitemaps

# Отдаём media независимо от DEBUG: панель проксирует напрямую на gunicorn,
# отдельного nginx для /media/ в этой цепочке нет.
media_urlpatterns = [
    re_path(
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'),
        serve_static,
        {'document_root': settings.MEDIA_ROOT},
    ),
]

urlpatterns = [
    path('adminka', RedirectView.as_view(url='/adminka/', permanent=False)),
    path('adminka/', admin.site.urls),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
] + media_urlpatterns + [
    path('', include('content.urls')),
    re_path(r'^(?P<url_path>.+?)/?$', content_views.legacy_path, name='legacy_path'),
]
