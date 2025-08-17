import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import csv
from tqdm import tqdm
import os

POKEMON_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{}"
POKEMON_LIST_URL = "https://pokeapi.co/api/v2/pokemon-species/?limit=10000"
OUTPUT_FILE = "data/commands/pokemon/pokemon_special_names.csv"
REGIONAL_VARIANTS = ["alola", "hisui", "galar", "paldea", "totem", "cap"]

def fetch_species_forms(species_name):
    try:
        data = requests.get(POKEMON_SPECIES_URL.format(species_name), timeout=5).json()
    except Exception:
        return [], []

    rare_pokemon = []
    regional_pokemon = []

    is_legendary = data.get("is_legendary", False)
    is_mythical = data.get("is_mythical", False)
    
    # Detect Ultra Beast or Alstra Beast
    flavor_texts = [entry["flavor_text"].lower() 
                    for entry in data.get("flavor_text_entries", []) 
                    if entry["language"]["name"] == "en"]
    ultra_beast_flag = any("ultra beast" in t for t in flavor_texts)
    alstra_beast_flag = any("alstra beast" in t for t in flavor_texts)

    # Check all varieties for regional variants
    for variety in data.get("varieties", []):
        form_name = variety["pokemon"]["name"]
        for v in REGIONAL_VARIANTS:
            if f"-{v}" in form_name:
                regional_pokemon.append(form_name)
                break

    if is_legendary or is_mythical or ultra_beast_flag or alstra_beast_flag:
        rare_pokemon.append(species_name)

    return rare_pokemon, regional_pokemon

def save_csv(rare_list, regional_list):
    Path(os.path.dirname(OUTPUT_FILE)).mkdir(parents=True, exist_ok=True)
    max_len = max(len(rare_list), len(regional_list))
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Rare Pokémon", "Regional Pokémon"])
        for i in range(max_len):
            rare = rare_list[i] if i < len(rare_list) else ""
            regional = regional_list[i] if i < len(regional_list) else ""
            writer.writerow([rare, regional])

def main():
    species_list = requests.get(POKEMON_LIST_URL).json()["results"]
    species_names = [s["name"] for s in species_list]

    rare_set = set()
    regional_set = set()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_species_forms, name): name for name in species_names}
        for f in tqdm(as_completed(futures), total=len(futures), desc="Processing Pokémon"):
            rare, regional = f.result()
            rare_set.update(rare)
            regional_set.update(regional)

    rare_sorted = sorted(rare_set)
    regional_sorted = sorted(regional_set)
    save_csv(rare_sorted, regional_sorted)
    print(f"✅ Saved {len(rare_sorted)} rare and {len(regional_sorted)} regional Pokémon to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
