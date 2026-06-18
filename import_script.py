import re
import sqlite3
from datetime import datetime
import csv
import json
import os
import shutil

# This script will parse the old.sql file and import the data into the new Django database.
# It will focus on migrating categories, content items, and their associated images.

def repair_text(value):
    """Replicates the text repair function from Django models."""
    if not value or not isinstance(value, str):
        return value
    try:
        repaired = value.encode('cp1251').decode('utf-8')
        return repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value

def parse_sql_values(values_str):
    """A simple CSV-based parser for a single row of SQL VALUES."""
    reader = csv.reader([values_str], quotechar="'", escapechar='\\')
    try:
        return next(reader)
    except StopIteration:
        return []

def move_images_and_get_new_path(images_json_str):
    """Parses image JSON, moves the file, and returns the new path."""
    try:
        images_data = json.loads(images_json_str)
        image_path = images_data.get('image_intro')
        if not image_path:
            return None

        # Correctly join path for source
        source_path = os.path.join('media', image_path)

        if os.path.exists(source_path):
            # Create a new path in the uploads directory
            new_dir = os.path.join('media', 'uploads', 'images')
            os.makedirs(new_dir, exist_ok=True)
            
            filename = os.path.basename(image_path)
            new_path = os.path.join(new_dir, filename)
            
            # Move the file
            shutil.move(source_path, new_path)
            
            # Return the Django-friendly path
            return os.path.join('uploads', 'images', filename).replace('\\', '/')
    except (json.JSONDecodeError, TypeError):
        return None
    return None

def import_data():
    """Parses the SQL dump and imports data into the SQLite database."""
    filepath = 'old.sql'
    
    print("Connecting to database...")
    conn = sqlite3.connect('db.sqlite3')
    cursor = conn.cursor()

    print("Clearing old content data...")
    cursor.execute("DELETE FROM content_contentitem;")
    cursor.execute("DELETE FROM content_category;")
    conn.commit()

    print("Parsing SQL dump file... This may take a moment.")
    with open(filepath, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # --- Import Categories ---
    print("Importing categories...")
    category_count = 0
    cat_regex = re.compile(r"INSERT INTO `pkulc_categories` VALUES \((.*?)\);")
    for match in cat_regex.finditer(sql_content):
        values = parse_sql_values(match.group(1))
        if not values or len(values) < 27:
            continue
        
        legacy_id = int(values[0])
        parent_id = int(values[2]) if values[2] != '0' else None
        title = repair_text(values[8])
        alias = values[9]
        description = repair_text(values[11])
        published = bool(int(values[12]))
        
        try:
            cursor.execute(
                """
                INSERT INTO content_category (id, parent_id, title, slug, public_slug, description, is_active, color, icon, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'blue', '📁', 0)
                """,
                (legacy_id, parent_id, title, alias, alias, description, published)
            )
            category_count += 1
        except sqlite3.IntegrityError as e:
            print(f"Skipping category with ID {legacy_id} due to integrity error: {e}")

    print(f"Imported {category_count} categories.")
    conn.commit()

    # --- Import Content ---
    print("Importing content items...")
    content_count = 0
    content_regex = re.compile(r"INSERT INTO `pkulc_content` VALUES \((.*?)\);")
    for match in content_regex.finditer(sql_content):
        values = parse_sql_values(match.group(1))
        if not values or len(values) < 31:
            continue

        legacy_id = int(values[0])
        title = repair_text(values[2])
        alias = values[3]
        introtext = repair_text(values[4])
        fulltext = repair_text(values[5])
        state = int(values[6])
        catid = int(values[7])
        created = values[8]
        modified = values[11]
        images_json = values[18]
        hits = int(values[25])
        featured = bool(int(values[27]))

        content = introtext
        if fulltext:
            content += "<hr>" + fulltext

        status_map = {1: 'published', 0: 'draft', -2: 'archived'}
        status = status_map.get(state, 'draft')

        try:
            created_at = datetime.strptime(created, '%Y-%m-%d %H:%M:%S').isoformat()
        except ValueError:
            created_at = datetime.now().isoformat()
        
        try:
            updated_at = datetime.strptime(modified, '%Y-%m-%d %H:%M:%S').isoformat()
        except ValueError:
            updated_at = created_at
            
        new_image_path = move_images_and_get_new_path(images_json)

        try:
            cursor.execute(
                """
                INSERT INTO content_contentitem (id, category_id, title, slug, public_slug, excerpt, content, status, created_at, updated_at, views, is_featured, image, content_type, is_main_slider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'article', 0)
                """,
                (legacy_id, catid, title, alias, alias, introtext, content, status, created_at, updated_at, hits, featured, new_image_path)
            )
            content_count += 1
        except sqlite3.IntegrityError as e:
            print(f"Skipping content item with ID {legacy_id} due to integrity error: {e}")

    print(f"Imported {content_count} content items.")
    conn.commit()
    conn.close()
    print("Data import script finished.")

if __name__ == '__main__':
    import_data()
