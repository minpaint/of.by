from django.core.management.base import BaseCommand
from content.models import CatalogItem
import json
import textwrap

class Command(BaseCommand):
    help = 'Updates the content of specific CatalogItems from a JSON file.'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Path to the JSON file containing the updates.')
        parser.add_argument('--commit', action='store_true', help='Actually save the changes to the database.')

    def handle(self, *args, **options):
        self.stdout.reconfigure(encoding='utf-8')
        file_path = options['file']
        commit = options['commit']

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                updates = json.load(f)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found at {file_path}"))
            return
        except json.JSONDecodeError as e:
            self.stderr.write(self.style.ERROR(f"Invalid JSON in {file_path}: {e}"))
            return

        if not commit:
            self.stdout.write(self.style.WARNING("--- DRY RUN ---"))

        for item_id, new_content in updates.items():
            try:
                item = CatalogItem.objects.get(pk=int(item_id))
                self.stdout.write(f"--- Preparing to update item ID: {item.id} ({item.title}) ---")
                
                if commit:
                    item.content = textwrap.dedent(new_content)
                    item.save()
                    self.stdout.write(self.style.SUCCESS(f"Successfully updated content for item {item.id}."))
                else:
                    self.stdout.write(f"Would update with content starting with: '{textwrap.dedent(new_content)[:70]}...'")
            
            except CatalogItem.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Item with ID {item_id} not found. Skipping."))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"An error occurred for item {item_id}: {e}"))

        if commit:
            self.stdout.write(self.style.SUCCESS("
Batch update complete."))
        else:
            self.stdout.write(self.style.WARNING("
This was a dry run. No changes were saved. Use --commit to save."))
