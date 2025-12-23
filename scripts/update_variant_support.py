#!/usr/bin/env python3
"""
Script to update the Pokémon system with variant support.
This script:
1. Merges variant alt names into the main alt_names.csv
2. Updates the pokemon_full_data.csv with variant entries
3. Creates a backup of existing files
"""

import csv
import os
import shutil
from datetime import datetime

def backup_file(filepath):
    """Create a backup of the file with timestamp."""
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{filepath}.backup_{timestamp}"
        shutil.copy2(filepath, backup_path)
        print(f"Backed up {filepath} to {backup_path}")
        return backup_path
    return None

def merge_alt_names():
    """Merge variant alt names into the main alt_names.csv file."""
    main_alt_names = "data/commands/pokemon/alt_names.csv"
    variant_alt_names = "data/commands/pokemon/variant_alt_names.csv"
    
    if not os.path.exists(variant_alt_names):
        print(f"Variant alt names file not found: {variant_alt_names}")
        return False
    
    # Backup the main file
    backup_file(main_alt_names)
    
    # Read existing alt names to avoid duplicates
    existing_alt_names = set()
    if os.path.exists(main_alt_names):
        with open(main_alt_names, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Handle different possible column names
                alt_name = row.get('alt_name') or row.get('en', '').split(',')[0].strip()
                if alt_name:
                    existing_alt_names.add(alt_name.lower())
    
    # Read variant alt names
    variant_entries = []
    with open(variant_alt_names, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            alt_name = row['alt_name'].strip()
            real_name = row['real_name'].strip()
            if alt_name and real_name and alt_name.lower() not in existing_alt_names:
                variant_entries.append({'alt_name': alt_name, 'real_name': real_name})
                existing_alt_names.add(alt_name.lower())
    
    # Append variant entries to main alt names file
    if variant_entries:
        # Check if the main file has the correct format
        needs_conversion = False
        if os.path.exists(main_alt_names):
            with open(main_alt_names, 'r', encoding='utf-8') as f:
                header = f.readline().strip()
                if 'alt_name' not in header:
                    needs_conversion = True
        
        if needs_conversion:
            # Create new format file
            new_alt_names = []
            with open(main_alt_names, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pokemon_name = row.get('pokemon_species', '')
                    en_names = row.get('en', '').split(',')
                    for name in en_names:
                        name = name.strip()
                        if name and name != pokemon_name:
                            new_alt_names.append({'alt_name': name, 'real_name': pokemon_name})
            
            # Write new format with variant entries
            with open(main_alt_names, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ['alt_name', 'real_name']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(new_alt_names)
                writer.writerows(variant_entries)
        else:
            # Append to existing format
            with open(main_alt_names, 'a', newline='', encoding='utf-8') as f:
                fieldnames = ['alt_name', 'real_name']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writerows(variant_entries)
        
        print(f"Added {len(variant_entries)} variant alt name entries to {main_alt_names}")
    else:
        print("No new variant alt names to add")
    
    return True

def add_variant_pokemon_to_full_data():
    """Add variant Pokémon entries to pokemon_full_data.csv."""
    full_data_csv = "data/commands/pokemon/pokemon_full_data.csv"
    variant_entries_csv = "data/commands/pokemon/variant_pokemon_entries.csv"
    
    if not os.path.exists(variant_entries_csv):
        print(f"Variant entries file not found: {variant_entries_csv}")
        return False
    
    if not os.path.exists(full_data_csv):
        print(f"Pokemon full data file not found: {full_data_csv}")
        return False
    
    # Backup the main file
    backup_file(full_data_csv)
    
    # Read existing pokemon to avoid duplicates
    existing_slugs = set()
    existing_entries = []
    with open(full_data_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            existing_entries.append(row)
            slug = row.get('slug', '').lower()
            if slug:
                existing_slugs.add(slug)
    
    # Read variant entries
    variant_entries = []
    with open(variant_entries_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        next_id = max([int(row.get('id', 0)) for row in existing_entries if row.get('id', '').isdigit()], default=0) + 1
        
        for row in reader:
            slug = row['slug'].strip().lower()
            if slug not in existing_slugs:
                # Create full data entry for variant
                variant_entry = {
                    'id': next_id,
                    'dex_number': 0,  # Variants don't have dex numbers
                    'region': 'variant',
                    'slug': slug,
                    'description': row['description'],
                    'credit': 'generation-variant',
                    'enabled': 1,
                    'catchable': 1,
                    'abundance': 'common',
                    'gender_rate': 4,
                    'has_gender_differences': 'False',
                    'name.en': row['display_name'],
                    'type.0': '',  # Will need to be filled manually
                    'type.1': '',
                    'mythical': 'False',
                    'legendary': 'False',
                    'ultra_beast': 'False',
                    'event': 'False',
                    'height': 0,
                    'weight': 0,
                    'base.hp': 0,
                    'base.atk': 0,
                    'base.def': 0,
                    'base.satk': 0,
                    'base.sdef': 0,
                    'base.spd': 0,
                    'is_form': 'True',
                    'form_item': row['base_name']
                }
                
                # Fill in missing fields with empty values
                for field in fieldnames:
                    if field not in variant_entry:
                        variant_entry[field] = ''
                
                variant_entries.append(variant_entry)
                existing_slugs.add(slug)
                next_id += 1
    
    if variant_entries:
        # Write updated full data
        with open(full_data_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(existing_entries)
            writer.writerows(variant_entries)
        
        print(f"Added {len(variant_entries)} variant Pokémon entries to {full_data_csv}")
    else:
        print("No new variant Pokémon to add to full data")
    
    return True

def main():
    """Main function to update variant support."""
    print("Starting variant Pokémon support update...")
    
    # Change to the correct directory
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    success = True
    
    # Merge alt names
    print("\n1. Merging variant alt names...")
    if not merge_alt_names():
        success = False
    
    # Add variant entries to full data
    print("\n2. Adding variant Pokémon to full data...")
    if not add_variant_pokemon_to_full_data():
        success = False
    
    if success:
        print("\n✅ Variant Pokémon support update completed successfully!")
        print("\nNext steps:")
        print("1. The system now supports variant Pokémon names")
        print("2. Users can use commands like:")
        print("   - .pt cl add blue flower flabebe")
        print("   - .pt sh spiky eared pichu")
        print("   - .pt cl add autumn deerling")
        print("3. Names with underscores, spaces, or hyphens will be normalized")
        print("4. Image URLs will map to base Pokémon forms")
    else:
        print("\n❌ Some errors occurred during the update")
    
    return success

if __name__ == "__main__":
    main()
