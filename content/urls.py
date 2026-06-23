from django.urls import path, re_path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('search', views.search, name='search_noslash'),
    path('search/', views.search, name='search'),
    path('rezultaty-poiska.html', views.yandex_search_results, name='yandex_search_results'),
    path('catalog/<slug:category_slug>/<slug:slug>.html', views.catalog_item_detail, name='catalog_item_detail'),
    path('catalog/<slug:slug>/', views.catalog_category, name='catalog_category'),
    path(
        'kupit-tovary-i-zakazat-uslugi-po-okhrane-truda-pozharnoj-bezopasnosti-ecologii-v-minske-i-po-belarusi.html',
        views.catalog,
        name='catalog',
    ),
    path('catalog', views.catalog, name='catalog_short_noslash'),
    path('catalog/', views.catalog, name='catalog_short'),
    path('<slug:slug>.html', views.content_detail_public, name='content_detail_public'),
    path('<slug:slug>.html/', views.content_detail_public, name='content_detail_public_slash'),
    path('<slug:cat_slug>/<slug:slug>', views.content_detail, name='content_detail_noslash'),
    path('<slug:slug>', views.section, name='section_noslash'),
    path('<slug:slug>/', views.section, name='section'),
    path('<slug:cat_slug>/<slug:slug>/', views.content_detail, name='content_detail'),
]
