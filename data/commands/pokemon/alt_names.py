import aiohttp
import asyncio
import csv
import os
from tqdm import tqdm
from pathlib import Path

POKEMON_API_URL = "https://pokeapi.co/api/v2/pokemon"
POKEMON_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{}"
POKEMON_LANGUAGES_URL = "https://pokeapi.co/api/v2/language"
OUTPUT_CSV = "data/commands/pokemon/alt_names.csv"

async def fetch_json(session, url):
    async with session.get(url) as res:
        return await res.json() if res.status == 200 else None

async def fetch_all_languages(session):
    langs = []
    url = POKEMON_LANGUAGES_URL
    pbar = tqdm(desc="Fetching languages", unit="page")
    while url:
        data = await fetch_json(session, url)
        if not data:
            break
        langs.extend([lang["name"] for lang in data["results"]])
        url = data.get("next")
        pbar.update(1)
    pbar.close()
    return langs

async def fetch_all_pokemon_names(session):
    pokemon_names = []
    url = f"{POKEMON_API_URL}?limit=10000"  # fetch all in one request (no pagination)
    data = await fetch_json(session, url)
    if data and "results" in data:
        pokemon_names.extend([r["name"] for r in data["results"]])
    return pokemon_names

async def fetch_species_names_by_lang(species_name, session, lang_codes):
    url = POKEMON_SPECIES_URL.format(species_name)
    data = await fetch_json(session, url)
    if not data:
        return None, {}

    lang_name_map = {lang: set() for lang in lang_codes}

    for name_entry in data.get("names", []):
        lang = name_entry["language"]["name"]
        if lang in lang_codes:
            lang_name_map[lang].add(name_entry["name"])

    # Include all variety (form) Pokémon names under "en"
    varieties = data.get("varieties", [])
    for variety in varieties:
        poke_name = variety.get("pokemon", {}).get("name")
        if poke_name:
            lang_name_map["en"].add(poke_name)

    for lang in lang_name_map:
        lang_name_map[lang] = ", ".join(sorted(lang_name_map[lang]))

    return species_name, lang_name_map

async def gather_all_alt_names(pokemon_names, lang_codes, session):
    results = []
    pbar = tqdm(pokemon_names, desc="Fetching Pokémon alt names", unit="species")
    for species_name in pbar:
        species, lang_map = await fetch_species_names_by_lang(species_name, session, lang_codes)
        if species is None:
            continue
        row = [species] + [lang_map.get(lang, "") for lang in lang_codes]
        results.append(row)
    pbar.close()
    return results

def write_csv(data, lang_codes):
    Path(os.path.dirname(OUTPUT_CSV)).mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pokemon_species"] + lang_codes)
        writer.writerows(data)

async def main():
    async with aiohttp.ClientSession() as session:
        print("Fetching all language codes...")
        lang_codes = await fetch_all_languages(session)
        print(f"Found {len(lang_codes)} languages.")

        print("Fetching all Pokémon names...")
        pokemon_names = await fetch_all_pokemon_names(session)
        print(f"Found {len(pokemon_names)} Pokémon.")

        print("Fetching all alt names for each Pokémon...")
        all_alt_names = await gather_all_alt_names(pokemon_names, lang_codes, session)

    write_csv(all_alt_names, lang_codes)
    print(f"Done! Saved {len(all_alt_names)} species alt names to {OUTPUT_CSV}")

if __name__ == "__main__":
    asyncio.run(main())
