import aiohttp
import asyncio
import csv
import os
from pathlib import Path
from tqdm import tqdm
import ssl

POKEMON_API_URL = "https://pokeapi.co/api/v2/pokemon"
POKEMON_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{}"
OUTPUT_FILE = "data/commands/pokemon/pokemon_with_rarity.csv"

def get_form_region(form_name, base_name):
    parts = form_name.replace(base_name, "").strip("-").split("-")
    return parts[-1] if len(parts) > 0 and parts[-1] else "kanto"

async def fetch_json(session, url):
    async with session.get(url) as resp:
        return await resp.json() if resp.status == 200 else None

async def fetch_pokemon_species_list(session):
    url = f"{POKEMON_SPECIES_URL.split('{}')[0]}?limit=10000"
    data = await fetch_json(session, url)
    return [entry["name"] for entry in data["results"]] if data else []

async def fetch_pokemon_forms(species_name, session):
    url = POKEMON_SPECIES_URL.format(species_name)
    data = await fetch_json(session, url)
    if not data:
        return []

    pid = data["id"]
    is_legendary = data.get("is_legendary", False)
    is_mythical = data.get("is_mythical", False)

    ultra_beast_flag = False
    for entry in data.get("pokedex_numbers", []):
        if entry.get("pokedex", {}).get("name") == "ultra-beast":
            ultra_beast_flag = True
            break

    rows = []
    for variety in data.get("varieties", []):
        form_url = variety["pokemon"]["url"]
        form_data = await fetch_json(session, form_url)
        if not form_data:
            continue

        form_name = form_data["name"]
        form_id = form_data["id"]
        is_default = form_data.get("is_default", True)

        if ultra_beast_flag:
            rarity = "ultra beast"
        elif is_mythical:
            rarity = "mythical"
        elif is_legendary:
            rarity = "legendary"
        elif not is_default:
            rarity = "regional"
        else:
            rarity = "common"

        region = get_form_region(form_name, species_name) if rarity == "regional" else "kanto"

        rows.append((form_id, form_name, rarity, region))

    return rows

async def gather_all_data(species_list, session):
    results = []
    seen = set()
    pbar = tqdm(species_list, desc="Processing Pokémon", unit="mon")
    for name in pbar:
        rows = await fetch_pokemon_forms(name, session)
        for row in rows:
            if row[1] not in seen:
                seen.add(row[1])
                results.append(row)
    pbar.close()
    return sorted(results, key=lambda x: x[0])

def save_to_csv(rows):
    Path(os.path.dirname(OUTPUT_FILE)).mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "rarity", "region"])
        writer.writerows(rows)

async def main():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        print("Fetching all Pokémon species...")
        species_list = await fetch_pokemon_species_list(session)
        print(f"Found {len(species_list)} species.")

        print("Processing all Pokémon forms...")
        all_data = await gather_all_data(species_list, session)

        save_to_csv(all_data)
        print(f"Saved {len(all_data)} entries to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
