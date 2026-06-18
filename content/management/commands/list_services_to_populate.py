from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db.models.functions import Length
from content.models import CatalogCategory, CatalogItem

class Command(BaseCommand):
    help = 'Lists services with little content.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-length',
            type=int,
            default=1000,
            help='The maximum content length to be considered "little text".'
        )

    def handle(self, *args, **options):
        self.stdout.reconfigure(encoding='utf-8')
        max_length = options['max_length']

        ROOT_CATEGORY_NAMES = [
            "Услуги по пожарной безопасности",
            "Проектирование, монтаж, пусконаладка",
            "Продукция по пожарной безопасности",
            "Ремонт обслуживание инженерных систем",
            "Услуги по охране труда",
            "Услуги по экологии",
        ]

        root_categories = CatalogCategory.objects.filter(parent__isnull=True, title__in=ROOT_CATEGORY_NAMES)
        
        all_categories_map = {c.id: c for c in CatalogCategory.objects.all()}
        children_map = {}
        for cat in all_categories_map.values():
            if cat.parent_id:
                if cat.parent_id not in children_map:
                    children_map[cat.parent_id] = []
                children_map[cat.parent_id].append(cat)

        def get_descendants(cat_id):
            descendants = []
            children_to_process = children_map.get(cat_id, [])
            while children_to_process:
                child = children_to_process.pop(0)
                descendants.append(child)
                children_to_process.extend(children_map.get(child.id, []))
            return descendants

        all_target_categories = []
        for root_cat in root_categories:
            all_target_categories.append(root_cat)
            all_target_categories.extend(get_descendants(root_cat.id))
        
        target_items = CatalogItem.objects.annotate(
            content_len=Length('content')
        ).filter(
            category__in=all_target_categories,
            content_len__lt=max_length
        ).order_by('content_len', 'category__id', 'sort_order', 'title')

        self.stdout.write(f"Found {target_items.count()} services to update:")
        for item in target_items:
            self.stdout.write(f"- ID: {item.id}, Title: {item.title} (Content Length: {item.content_len})")
