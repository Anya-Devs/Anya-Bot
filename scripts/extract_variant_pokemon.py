#!/usr/bin/env python3
"""
Script to extract variant Pokémon from labels_v2.json and add them to the CSV files.
This handles Pokémon with underscores in their names (variants/forms).
"""

import json
import csv
import os
import re
from pathlib import Path

# File paths
LABELS_FILE = "data/events/poketwo_spawns/model/labels_v2.json"
IMAGE_URLS_FILE = "data/events/poketwo_spawns/image_urls.json"
POKEMON_CSV = "data/commands/pokemon/pokemon_full_data.csv"
ALT_NAMES_CSV = "data/commands/pokemon/alt_names.csv"

def load_json_file(filepath):
    """Load JSON file and return data."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def normalize_name_for_csv(name):
    """Convert underscore variant names to hyphen format for CSV storage."""
    # Convert underscores to hyphens for CSV storage
    return name.replace('_', '-')

def normalize_name_for_image_lookup(name):
    """Convert variant names to base form for image URL lookup."""
    # Remove variant parts and get base Pokémon name
    base_name = name.split('_')[0] if '_' in name else name
    # Handle special cases
    if base_name.endswith('-eared'):
        base_name = base_name.replace('-eared', '')
    if base_name.endswith('-flower'):
        base_name = base_name.replace('-flower', '')
    if base_name.endswith('-trim'):
        base_name = base_name.replace('-trim', '')
    return base_name

def extract_variant_pokemon():
    """Extract variant Pokémon from labels_v2.json."""
    print("Loading labels_v2.json...")
    labels_data = load_json_file(LABELS_FILE)
    
    print("Loading image_urls.json...")
    image_urls = load_json_file(IMAGE_URLS_FILE)
    
    # Find all Pokémon with underscores (variants)
    variant_pokemon = []
    
    for label_id, pokemon_name in labels_data.items():
        if '_' in pokemon_name:
            # This is a variant Pokémon
            base_name = normalize_name_for_image_lookup(pokemon_name)
            csv_name = normalize_name_for_csv(pokemon_name)
            
            # Check if base form exists in image URLs
            image_url = image_urls.get(base_name, "")
            
            variant_info = {
                'label_id': label_id,
                'variant_name': pokemon_name,  # Original with underscores
                'csv_name': csv_name,          # Hyphens for CSV
                'base_name': base_name,        # For image lookup
                'image_url': image_url,
                'display_name': pokemon_name.replace('_', ' ').title()
            }
            
            variant_pokemon.append(variant_info)
    
    print(f"Found {len(variant_pokemon)} variant Pokémon")
    return variant_pokemon

def create_alt_names_entries(variant_pokemon):
    """Create alt_names.csv entries for variant Pokémon."""
    alt_names_entries = []
    
    for variant in variant_pokemon:
        # Add entry for the variant name with underscores -> CSV name with hyphens
        alt_names_entries.append({
            'alt_name': variant['variant_name'],  # spiky-eared_pichu
            'real_name': variant['csv_name']      # spiky-eared-pichu
        })
        
        # Add entry for display name -> CSV name
        display_name_normalized = variant['display_name'].lower().replace(' ', '-')
        if display_name_normalized != variant['csv_name']:
            alt_names_entries.append({
                'alt_name': display_name_normalized,  # spiky-eared-pichu
                'real_name': variant['csv_name']       # spiky-eared-pichu
            })
    
    return alt_names_entries

def update_alt_names_csv(alt_names_entries):
    """Update alt_names.csv with variant Pokémon entries."""
    print(f"Adding {len(alt_names_entries)} entries to alt_names.csv...")
    
    # Read existing alt names
    existing_alt_names = set()
    if os.path.exists(ALT_NAMES_CSV):
        with open(ALT_NAMES_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_alt_names.add(row['alt_name'])
    
    # Write updated alt names
    with open(ALT_NAMES_CSV, 'a', newline='', encoding='utf-8') as f:
        fieldnames = ['alt_name', 'real_name']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        # Write header if file is empty
        if os.path.getsize(ALT_NAMES_CSV) == 0:
            writer.writeheader()
        
        # Add new entries
        added_count = 0
        for entry in alt_names_entries:
            if entry['alt_name'] not in existing_alt_names:
                writer.writerow(entry)
                existing_alt_names.add(entry['alt_name'])
                added_count += 1
        
        print(f"Added {added_count} new alt name entries")

def create_pokemon_csv_entries(variant_pokemon):
    """Create basic CSV entries for variant Pokémon."""
    csv_entries = []
    
    for i, variant in enumerate(variant_pokemon, start=10000):  # Start from high ID to avoid conflicts
        # Create basic entry - user will need to fill in proper descriptions
        entry = {
            'id': i,
            'dex_number': 0,  # Will need to be filled
            'region': 'variant',
            'slug': variant['csv_name'],
            'description': f"A variant form of {variant['base_name']}. Description needed.",
            'credit': 'generation-variant',
            'enabled': 1,
            'catchable': 1,
            'abundance': 'common',
            'gender_rate': 4,
            'has_gender_differences': 'False',
            'name.en': variant['display_name'],
            'type.0': '',  # Will need to be filled
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
            'form_item': variant['base_name']
        }
        csv_entries.append(entry)
    
    return csv_entries

def main():
    """Main function to extract and process variant Pokémon."""
    print("Starting variant Pokémon extraction...")
    
    # Extract variant Pokémon
    variant_pokemon = extract_variant_pokemon()
    
    if not variant_pokemon:
        print("No variant Pokémon found!")
        return
    
    # Create alt names entries
    alt_names_entries = create_alt_names_entries(variant_pokemon)
    
    # Update alt_names.csv
    update_alt_names_csv(alt_names_entries)
    
    # Create CSV entries for variant Pokémon
    csv_entries = create_pokemon_csv_entries(variant_pokemon)
    
    # Save variant Pokémon info for manual review
    output_file = "variant_pokemon_info.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'variant_pokemon': variant_pokemon,
            'csv_entries': csv_entries
        }, f, indent=2, ensure_ascii=False)
    
    print(f"Variant Pokémon info saved to {output_file}")
    print("Manual steps needed:")
    print("1. Review the generated CSV entries")
    print("2. Fill in proper descriptions, types, and stats")
    print("3. Add entries to pokemon_full_data.csv")
    print("4. Update the collection/hunt commands to handle variant names")

if __name__ == "__main__":
    main()
