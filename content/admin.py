from django import forms
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import (
    Banner,
    CatalogCategory,
    CatalogItem,
    CatalogItemFile,
    CatalogItemImage,
    Category,
    ContentItem,
    ContentFeedBlock,
    LeadSettings,
    LegacyRedirect,
    SectionBranding,
    SiteCounter,
    SmtpSettings,
    build_unique_slug,
)


admin.site.site_header = 'of.by'
admin.site.site_title = 'of.by admin'
admin.site.index_title = 'Управление сайтом'


WIDE_INPUT_STYLE = 'width: 100%; max-width: none;'
WIDE_TEXTAREA_STYLE = 'width: 100%; max-width: none; min-height: 120px;'


class WideTitleSlugAdminMixin:
    wide_field_names = ('title', 'public_slug')

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        for field_name in self.wide_field_names:
            if field_name in form.base_fields:
                widget = form.base_fields[field_name].widget
                existing_style = widget.attrs.get('style', '')
                widget.attrs['style'] = f'{existing_style}; {WIDE_INPUT_STYLE}'.strip('; ').strip()
                widget.attrs.pop('size', None)
            if field_name in form.declared_fields:
                widget = form.declared_fields[field_name].widget
                existing_style = widget.attrs.get('style', '')
                widget.attrs['style'] = f'{existing_style}; {WIDE_INPUT_STYLE}'.strip('; ').strip()
                widget.attrs.pop('size', None)
        return form


class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = (
            'title',
            'public_slug',
            'parent',
            'branding',
            'related_categories',
            'color',
            'icon',
            'description',
            'sort_order',
            'is_active',
        )
        widgets = {
            'title': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'public_slug': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'icon': forms.TextInput(attrs={'style': 'width: 260px;', 'size': 24}),
            'description': forms.Textarea(attrs={'style': WIDE_TEXTAREA_STYLE, 'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].label = 'Название'
        self.fields['title'].help_text = 'Название раздела или подкатегории.'
        self.fields['public_slug'].required = False
        self.fields['public_slug'].label = 'Публичный URL'
        self.fields['public_slug'].help_text = 'Адрес раздела на сайте. Если оставить пустым, заполнится автоматически.'
        self.fields['parent'].label = 'Родительская категория'
        self.fields['branding'].label = 'Брендинг шапки'
        self.fields['branding'].help_text = 'Опционально. Если выбрать пресет, логотип в шапке будет браться из него.'
        self.fields['related_categories'].label = 'Родственные категории'
        self.fields['description'].label = 'Описание'
        self.fields['description'].help_text = 'Краткое описание раздела для интерфейса и SEO.'
        self.fields['color'].label = 'Цвет'
        self.fields['icon'].label = 'Иконка'
        self.fields['sort_order'].label = 'Порядок'
        self.fields['is_active'].label = 'Активна'

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.slug:
            instance.slug = build_unique_slug(Category, 'slug', instance.title, instance.pk)
        if not instance.public_slug:
            instance.public_slug = build_unique_slug(Category, 'public_slug', instance.title, instance.pk)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ContentItemAdminForm(forms.ModelForm):
    excerpt = forms.CharField(
        required=False,
        label='Краткое описание',
        widget=CKEditor5Widget(
            attrs={'style': 'width: 100%; max-width: none;'},
            config_name='default',
        ),
    )

    class Meta:
        model = ContentItem
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'public_slug': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'video_url': forms.URLInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 140}),
            'file_title': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 140}),
            'author': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 100}),
            'tags': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 140}),
            'seo_title': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 140}),
            'seo_description': forms.Textarea(attrs={'style': WIDE_TEXTAREA_STYLE, 'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].label = 'Заголовок'
        self.fields['title'].help_text = 'Из заголовка автоматически формируются публичный URL и SEO-заголовок.'
        self.fields['category'].label = 'Категория'
        self.fields['category'].help_text = 'Выберите основной раздел, в котором материал будет опубликован.'
        category_widget = self.fields['category'].widget
        for attr in ('can_add_related', 'can_change_related', 'can_delete_related', 'can_view_related'):
            if hasattr(category_widget, attr):
                setattr(category_widget, attr, False)
        self.fields['content_type'].label = 'Тип материала'
        self.fields['content_type'].choices = [
            ('article', 'Материал'),
            ('video', 'Видео'),
            ('event', 'Событие'),
            ('product', 'Товар/услуга'),
        ]
        self.fields['content_type'].help_text = 'Для обычных публикаций оставляйте «Материал». Отдельные типы нужны только для видео и событий.'
        self.fields['status'].label = 'Статус'
        self.fields['is_featured'].label = 'В избранном'
        self.fields['is_main_slider'].label = 'В главном слайдере'

        self.fields['public_slug'].required = False
        self.fields['public_slug'].label = 'Публичный URL'
        self.fields['public_slug'].help_text = 'Адрес, который будет отображаться на сайте. Если оставить пустым, заполнится автоматически.'

        self.fields['seo_title'].required = False
        self.fields['seo_title'].label = 'SEO заголовок'
        self.fields['seo_title'].help_text = 'Если оставить пустым, сохранится заголовок статьи. Потом можно отредактировать вручную.'
        self.fields['seo_description'].label = 'SEO описание'

        self.fields['excerpt'].help_text = 'Короткое вступление или анонс статьи. Используется в списках, на главной и в карточках.'
        self.fields['video_url'].label = 'Ссылка на видео'
        self.fields['video_url'].help_text = 'Оставьте пустым для обычной статьи. Поддерживаются ссылки YouTube и embed URL.'
        self.fields['file'].label = 'Файл'
        self.fields['file_title'].label = 'Название файла'
        self.fields['file_title'].help_text = 'Как подписывать ссылку на скачивание, если у материала есть вложенный файл.'
        self.fields['image'].label = 'Обложка'
        self.fields['image'].help_text = 'Главная картинка материала. Показывается в слайдере, карточках и на странице статьи.'
        self.fields['author'].label = 'Автор'
        self.fields['tags'].label = 'Теги'
        self.fields['published_date'].label = 'Дата публикации'
        self.fields['event_date'].label = 'Дата события'
        self.fields['price'].label = 'Цена'

        if 'content' in self.fields:
            self.fields['content'].label = 'Содержимое'
            self.fields['content'].help_text = 'Основной текст статьи.'
            self.fields['content'].widget.attrs.update(
                {
                    'style': 'width: 100%; max-width: none;',
                    'rows': 34,
                    'cols': 220,
                }
            )


class BannerAdminForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'subtitle': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 140}),
            'url': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 140}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].label = 'Заголовок'
        self.fields['title'].help_text = 'Заголовок баннера.'
        self.fields['subtitle'].label = 'Подзаголовок'
        self.fields['subtitle'].help_text = 'Дополнительный текст или призыв к действию.'
        self.fields['url'].label = 'Ссылка'
        self.fields['url'].help_text = 'Ссылка, по которой должен вести баннер.'
        self.fields['placement'].label = 'Размещение'
        self.fields['category'].label = 'Раздел'
        self.fields['is_active'].label = 'Активен'
        self.fields['sort_order'].label = 'Порядок'

class LeadSettingsAdminForm(forms.ModelForm):
    class Meta:
        model = LeadSettings
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'recipient_email': forms.EmailInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 120}),
            'sender_name': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 120}),
            'success_message': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 140}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].help_text = 'Служебное название набора настроек.'
        self.fields['recipient_email'].help_text = (
            'Сюда будут приходить заявки с сайта. Это отдельное поле-получатель, а не SMTP-конфиг.'
        )
        self.fields['sender_name'].help_text = 'Как подписывать отправителя в уведомлениях и автоответах.'
        self.fields['success_message'].help_text = 'Текст, который увидит пользователь после отправки формы.'


class ContentFeedBlockAdminForm(forms.ModelForm):
    content_type_filters = forms.MultipleChoiceField(
        required=False,
        choices=(
            ('video', 'Видео'),
            ('event', 'События'),
        ),
        label='Типы материалов',
        widget=forms.CheckboxSelectMultiple,
        help_text='Используйте фильтр только для видео и событий. Обычные материалы теперь разделяются по категориям.',
    )

    class Meta:
        model = ContentFeedBlock
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 120}),
            'title': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'link_text': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE, 'size': 80}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].help_text = 'Внутреннее название блока для админки.'
        self.fields['placement'].label = 'Где показывать'
        self.fields['target_category'].label = 'Раздел показа'
        self.fields['source_category'].label = 'Категория-источник'
        self.fields['source_category'].help_text = (
            'Для главного слайдера поле необязательно. Если заполнить, слайдер и блок '
            '"Другие новости" будут брать материалы только из этой категории.'
        )
        self.fields['display_category'].label = 'Категория в заголовке'
        self.fields['title'].label = 'Заголовок блока'
        self.fields['link_text'].label = 'Текст ссылки'
        self.fields['include_child_categories'].label = 'Включать подкатегории'
        self.fields['item_limit'].label = 'Количество материалов'
        self.fields['item_limit'].help_text = (
            'Для обычных блоков это общее число карточек. Для блока "Главный слайдер" '
            'это количество материалов в самом слайдере.'
        )
        self.fields['secondary_item_limit'].label = 'Количество карточек "Другие новости"'
        self.fields['secondary_item_limit'].help_text = (
            'Используется только у блока "Главный слайдер".'
        )
        self.fields['exclude_main_slider_items'].label = 'Не брать материалы главного слайдера'
        self.fields['exclude_main_slider_items'].help_text = (
            'Для блока "Главный слайдер" управляет тем, будут ли карточки "Другие новости" '
            'повторять материалы из слайдера.'
        )
        self.fields['hide_if_empty'].label = 'Скрывать пустой блок'
        self.fields['is_active'].label = 'Активен'
        self.fields['sort_order'].label = 'Порядок'
        self.fields['content_type_filters'].initial = self.instance.content_type_list

    def clean(self):
        cleaned_data = super().clean()
        placement = cleaned_data.get('placement')
        target_category = cleaned_data.get('target_category')
        source_category = cleaned_data.get('source_category')
        item_limit = cleaned_data.get('item_limit')

        secondary_item_limit = cleaned_data.get('secondary_item_limit')

        if placement == ContentFeedBlock.PLACEMENT_SECTION and not target_category:
            self.add_error('target_category', 'Для блока страницы раздела нужно выбрать раздел показа.')

        if placement == ContentFeedBlock.PLACEMENT_HOME and not source_category:
            self.add_error('source_category', 'Для блока на главной выберите категорию-источник.')

        if item_limit is not None and item_limit < 1:
            self.add_error('item_limit', 'Количество материалов должно быть не меньше 1.')

        if secondary_item_limit is not None and secondary_item_limit < 1:
            self.add_error('secondary_item_limit', 'Количество карточек должно быть не меньше 1.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.content_types = ','.join(self.cleaned_data.get('content_type_filters', []))
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CatalogItemAdminForm(forms.ModelForm):
    excerpt = forms.CharField(
        required=False,
        label='Краткое описание',
        widget=CKEditor5Widget(
            attrs={'style': 'width: 100%; max-width: none;'},
            config_name='default',
        ),
    )

    class Meta:
        model = CatalogItem
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'public_slug': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'sku': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'phone': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'mobile': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'email': forms.EmailInput(attrs={'style': WIDE_INPUT_STYLE}),
            'website': forms.URLInput(attrs={'style': WIDE_INPUT_STYLE}),
            'city': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'postcode': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'address': forms.Textarea(attrs={'style': WIDE_TEXTAREA_STYLE, 'rows': 3}),
            'seo_title': forms.TextInput(attrs={'style': WIDE_INPUT_STYLE}),
            'seo_description': forms.Textarea(attrs={'style': WIDE_TEXTAREA_STYLE, 'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].label = 'Название'
        self.fields['public_slug'].label = 'Публичный URL'
        self.fields['public_slug'].required = False
        self.fields['public_slug'].help_text = 'Адрес позиции на сайте. Если оставить пустым, будет заполнен автоматически.'
        self.fields['category'].label = 'Категория'
        self.fields['sort_order'].label = 'Порядок'
        self.fields['sku'].label = 'Артикул'
        self.fields['is_active'].label = 'Активен'
        self.fields['is_featured'].label = 'Рекомендуемый'
        self.fields['content'].label = 'Полное описание'
        self.fields['content'].help_text = 'Основной текст карточки товара или услуги.'
        self.fields['content'].widget.attrs.update(
            {
                'style': 'width: 100%; max-width: none;',
                'rows': 24,
                'cols': 180,
            }
        )
        self.fields['price'].label = 'Цена'
        self.fields['special_price'].label = 'Спеццена'
        self.fields['phone'].label = 'Телефон'
        self.fields['mobile'].label = 'Мобильный'
        self.fields['email'].label = 'Email'
        self.fields['website'].label = 'Сайт'
        self.fields['city'].label = 'Город'
        self.fields['postcode'].label = 'Индекс'
        self.fields['address'].label = 'Адрес'
        self.fields['seo_title'].label = 'SEO заголовок'
        self.fields['seo_description'].label = 'SEO описание'

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.slug:
            instance.slug = build_unique_slug(CatalogItem, 'slug', instance.title, instance.pk)
        if not instance.public_slug:
            instance.public_slug = build_unique_slug(CatalogItem, 'public_slug', instance.title, instance.pk)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


@admin.register(Category)
class CategoryAdmin(WideTitleSlugAdminMixin, admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = (
        'indented_title',
        'parent',
        'branding',
        'public_slug',
        'color',
        'children_count',
        'items_count',
        'sort_order',
        'is_active',
    )
    list_editable = ('sort_order', 'is_active')
    search_fields = ('title', 'slug', 'public_slug')
    list_filter = ('is_active', 'color', 'parent')
    filter_horizontal = ('related_categories',)
    ordering = ('parent__sort_order', 'parent__title', 'sort_order', 'title')
    fieldsets = (
        ('Основное', {
            'fields': (
                ('title', 'parent'),
                'description',
            ),
            'description': 'Название, место в дереве и краткое описание раздела.',
        }),
        ('Структура и публикация', {
            'fields': (
                ('sort_order', 'is_active'),
                'related_categories',
            ),
            'description': 'Порядок вывода, активность и связи с родственными категориями.',
        }),
        ('Оформление и URL', {
            'fields': (
                ('color', 'icon'),
                'branding',
                'public_slug',
            ),
            'description': 'Визуальные атрибуты, бренд шапки и публичный адрес раздела.',
        }),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('parent')
            .annotate(_children_count=Count('children', distinct=True), _items_count=Count('items', distinct=True))
        )

    def indented_title(self, obj):
        return obj.tree_title

    indented_title.short_description = 'Категория'

    def children_count(self, obj):
        return obj._children_count

    children_count.short_description = 'Подкатегорий'

    def items_count(self, obj):
        return obj._items_count

    items_count.short_description = 'Материалов'


@admin.register(SectionBranding)
class SectionBrandingAdmin(admin.ModelAdmin):
    list_display = ('name', 'key', 'title', 'icon_name', 'theme_color', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    list_filter = ('is_active', 'theme_color', 'icon_name')
    search_fields = ('name', 'key', 'title', 'subtitle')
    readonly_fields = ('logo_preview',)
    ordering = ('sort_order', 'name')

    fieldsets = (
        ('Основное', {
            'fields': (
                ('name', 'key'),
                ('title', 'theme_color'),
                'subtitle',
            ),
        }),
        ('Логотип', {
            'fields': (
                ('icon_name', 'is_active'),
                ('logo_image', 'logo_preview'),
                'sort_order',
            ),
            'description': 'Если загрузить картинку логотипа, она будет использована в шапке вместо стандартной иконки.',
        }),
    )

    def logo_preview(self, obj):
        if obj.logo_image:
            return format_html('<img src="{}" style="max-height:80px;">', obj.logo_image.url)
        return format_html('<img src="{}" style="max-height:48px;">', obj.icon_asset_url)

    logo_preview.short_description = 'Превью'


@admin.register(ContentItem)
class ContentItemAdmin(WideTitleSlugAdminMixin, admin.ModelAdmin):
    form = ContentItemAdminForm
    list_select_related = ('category',)
    list_per_page = 50
    show_full_result_count = False
    list_display = (
        'title',
        'category',
        'public_slug',
        'content_type',
        'status',
        'is_featured',
        'is_main_slider',
        'views',
        'published_date',
    )
    list_filter = ('status', 'content_type', 'category', 'is_featured', 'is_main_slider')
    list_editable = ('status', 'is_featured', 'is_main_slider')
    search_fields = ('title', 'excerpt', 'tags', 'slug', 'public_slug')
    readonly_fields = ('views', 'created_at', 'updated_at', 'image_preview')
    date_hierarchy = 'published_date'
    ordering = ('-published_date',)

    fieldsets = (
        ('Основное и содержание', {
            'fields': (
                'title',
                'public_slug',
                ('category', 'content_type', 'status'),
                ('is_featured', 'is_main_slider'),
                'excerpt',
                'content',
            ),
            'description': 'Здесь собраны базовые параметры материала, короткий анонс и основной текст, чтобы все ключевые данные можно было заполнить в одном месте.',
        }),
        ('Медиа', {
            'fields': (
                'image',
                'image_preview',
                'video_url',
                ('file', 'file_title'),
            ),
            'description': 'Обложка, видео и вложенный файл. Всё, что влияет на визуальную подачу и дополнительные материалы.',
        }),
        ('Публикация', {
            'fields': (
                ('author', 'published_date', 'event_date'),
                'tags',
            ),
            'description': 'Авторство, даты и теги для внутренней организации контента и вывода на сайте.',
        }),
        ('Товар или услуга', {
            'fields': ('price',),
            'description': 'Используйте только для материалов каталога, услуг и карточек с ценой.',
        }),
        ('SEO', {
            'fields': (
                'seo_title',
                'seo_description',
            ),
            'description': 'Поисковые метаданные страницы. Если оставить SEO-заголовок пустым, сайт возьмёт обычный заголовок.',
        }),
        ('Служебное', {
            'fields': (('views', 'created_at', 'updated_at'),),
            'description': 'Технические поля, которые заполняются автоматически.',
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height:120px;">', obj.image.url)
        return '—'

    image_preview.short_description = 'Превью'

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('category')
            .defer('content', 'excerpt', 'seo_description')
        )


@admin.register(Banner)
class BannerAdmin(WideTitleSlugAdminMixin, admin.ModelAdmin):
    form = BannerAdminForm
    list_display = ('title', 'placement', 'category', 'is_active', 'sort_order', 'banner_preview')
    list_editable = ('is_active', 'sort_order')
    list_filter = ('placement', 'is_active', 'category')
    readonly_fields = ('banner_preview',)

    fieldsets = (
        ('Основное', {
            'fields': (
                ('title', 'placement'),
                ('category', 'is_active'),
                ('subtitle', 'url'),
                'sort_order',
            ),
        }),
        ('Изображение', {
            'fields': ('image', 'banner_preview'),
            'description': 'Рекомендуемый размер: 900x120 px для разделов и 520x80 px для шапки.',
        }),
    )

    def banner_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:80px;max-width:600px;border-radius:4px;">',
                obj.image.url,
            )
        return '—'

    banner_preview.short_description = 'Превью'


@admin.register(ContentFeedBlock)
class ContentFeedBlockAdmin(WideTitleSlugAdminMixin, admin.ModelAdmin):
    form = ContentFeedBlockAdminForm
    list_display = (
        'name',
        'placement',
        'target_category',
        'source_category',
        'display_category',
        'item_limit',
        'secondary_item_limit',
        'sort_order',
        'is_active',
    )
    list_editable = ('item_limit', 'secondary_item_limit', 'sort_order', 'is_active')
    list_filter = ('placement', 'is_active', 'include_child_categories', 'exclude_main_slider_items')
    search_fields = ('name', 'title', 'source_category__title', 'target_category__title', 'display_category__title')
    autocomplete_fields = ('target_category', 'source_category', 'display_category')
    fieldsets = (
        ('Размещение', {
            'fields': (
                ('name', 'placement'),
                ('target_category', 'source_category'),
                'display_category',
            ),
            'description': 'Где показывать блок и из какой категории брать материалы.',
        }),
        ('Содержимое', {
            'fields': (
                ('title', 'link_text'),
                'content_type_filters',
                ('include_child_categories', 'exclude_main_slider_items'),
                ('item_limit', 'secondary_item_limit', 'hide_if_empty'),
            ),
            'description': 'Настройка заголовка, состава материалов и количества карточек в блоке.',
        }),
        ('Публикация', {
            'fields': (
                ('sort_order', 'is_active'),
            ),
            'description': 'Порядок показа блока среди других блоков на той же странице.',
        }),
    )


@admin.register(LegacyRedirect)
class LegacyRedirectAdmin(admin.ModelAdmin):
    list_display = ('old_path', 'new_path')
    search_fields = ('old_path', 'new_path')


@admin.register(SiteCounter)
class SiteCounterAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'sort_order', 'updated_at')
    list_editable = ('is_active', 'sort_order')
    search_fields = ('title', 'informer_code', 'counter_code')
    readonly_fields = ('updated_at',)

    fieldsets = (
        ('Основное', {
            'fields': (
                'title',
                'is_active',
                'sort_order',
            ),
        }),
        ('Коды', {
            'fields': (
                'informer_code',
                'counter_code',
            ),
        }),
        ('Служебное', {
            'fields': ('updated_at',),
        }),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change=change, **kwargs)
        for field_name in ('informer_code', 'counter_code'):
            if field_name in form.base_fields:
                form.base_fields[field_name].widget = forms.Textarea(
                    attrs={'style': 'width: 100%; min-height: 180px; font-family: monospace;', 'rows': 8}
                )
        return form


@admin.register(LeadSettings)
class LeadSettingsAdmin(admin.ModelAdmin):
    form = LeadSettingsAdminForm
    list_display = ('title', 'recipient_email', 'is_active', 'updated_at')
    list_editable = ('is_active',)
    readonly_fields = ('updated_at',)

    fieldsets = (
        ('Основное', {
            'fields': (
                'title',
                'recipient_email',
                'sender_name',
                'success_message',
                'is_active',
            ),
        }),
        ('Служебное', {
            'fields': ('updated_at',),
        }),
    )

    def has_add_permission(self, request):
        if LeadSettings.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(SmtpSettings)
class SmtpSettingsAdmin(admin.ModelAdmin):
    list_display = ('title', 'host', 'port', 'username', 'is_active', 'updated_at')
    list_editable = ('is_active',)
    readonly_fields = ('updated_at',)

    fieldsets = (
        ('Основное', {
            'fields': (
                'title',
                ('host', 'port'),
                ('username', 'password'),
                ('use_tls', 'use_ssl'),
                'is_active',
            ),
        }),
        ('Служебное', {
            'fields': ('updated_at',),
        }),
    )

    def has_add_permission(self, request):
        if SmtpSettings.objects.exists():
            return False
        return super().has_add_permission(request)


class CatalogItemImageInline(admin.TabularInline):
    model = CatalogItemImage
    extra = 0
    fields = ('image', 'caption', 'sort_order')


class CatalogItemFileInline(admin.TabularInline):
    model = CatalogItemFile
    extra = 0
    fields = ('file', 'title', 'downloads', 'sort_order')


@admin.register(CatalogCategory)
class CatalogCategoryAdmin(WideTitleSlugAdminMixin, admin.ModelAdmin):
    list_display = ('tree_title', 'branding', 'public_slug', 'parent', 'items_count', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('title', 'slug', 'public_slug', 'seo_title', 'seo_description')
    readonly_fields = ('legacy_id', 'created_at', 'updated_at', 'image_preview')
    ordering = ('parent__sort_order', 'parent__title', 'sort_order', 'title')

    fieldsets = (
        ('Основное', {
            'fields': (
                ('title', 'parent'),
                'branding',
                ('public_slug', 'sort_order'),
                'description',
                ('heading', 'is_active'),
            ),
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description'),
        }),
        ('Медиа', {
            'fields': ('image', 'image_preview'),
        }),
        ('Служебное', {
            'fields': ('legacy_id', 'created_at', 'updated_at'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_items_count=Count('items', distinct=True))

    def items_count(self, obj):
        return obj._items_count

    items_count.short_description = 'Позиции'

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height:120px;">', obj.image.url)
        return '—'

    image_preview.short_description = 'Превью'


@admin.register(CatalogItem)
class CatalogItemAdmin(WideTitleSlugAdminMixin, admin.ModelAdmin):
    change_form_template = 'admin/content/catalogitem/change_form.html'
    form = CatalogItemAdminForm
    list_select_related = ('category',)
    list_per_page = 50
    show_full_result_count = False
    list_display = ('title', 'category', 'public_slug', 'display_price', 'views', 'is_featured', 'is_active')
    list_editable = ('is_featured', 'is_active')
    list_filter = ('is_active', 'is_featured', 'category')
    search_fields = ('title', 'slug', 'public_slug', 'excerpt', 'sku', 'seo_title', 'seo_description')
    readonly_fields = ('legacy_id', 'views', 'created_at', 'updated_at', 'image_preview')
    ordering = ('category__sort_order', 'category__title', 'sort_order', 'title')
    inlines = (CatalogItemImageInline, CatalogItemFileInline)

    fieldsets = (
        ('Основное и описание', {
            'fields': (
                'title',
                'public_slug',
                ('category', 'sort_order'),
                ('sku', 'is_active', 'is_featured'),
                'excerpt',
                'content',
            ),
            'description': 'Основные данные позиции, краткое описание и полный текст собраны в одном блоке, чтобы не переключаться между вкладками.',
        }),
        ('Медиа', {
            'fields': ('image', 'image_preview'),
        }),
        ('Цена и контакты', {
            'fields': (
                ('price', 'special_price'),
                ('phone', 'mobile'),
                ('email', 'website'),
                ('city', 'postcode'),
                'address',
            ),
        }),
        ('SEO', {
            'fields': ('seo_title', 'seo_description'),
        }),
        ('Служебное', {
            'fields': ('legacy_id', 'views', 'published_date', 'created_at', 'updated_at'),
        }),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height:120px;">', obj.image.url)
        return '—'

    image_preview.short_description = 'Превью'
