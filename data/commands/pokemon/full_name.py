import aiohttp
import asyncio
import csv
import os
from pathlib import Path
from tqdm import tqdm

POKEMON_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{}"
POKEMON_API_URL = "https://pokeapi.co/api/v2/pokemon?limit=10000"
OUTPUT_CSV = "data/commands/pokemon/pokemon_full_data.csv"

CSV_STATIC_HEADER = [
    "id","dex_number","region","slug","description","credit","enabled","catchable","abundance",
    "gender_rate","has_gender_differences"
]

semaphore = asyncio.Semaphore(5)

REGION_MAP = {
    "generation-i": "kanto",
    "generation-ii": "johto",
    "generation-iii": "hoenn",
    "generation-iv": "sinnoh",
    "generation-v": "unova",
    "generation-vi": "kalos",
    "generation-vii": "alola",
    "generation-viii": "galar",
    "generation-ix": "paldea",
}

def get_region(species_data):
    gen_name = species_data.get("generation", {}).get("name", "")
    return REGION_MAP.get(gen_name, "kanto")

async def fetch_json(session, url):
    async with semaphore:
        try:
            async with session.get(url) as res:
                if res.status == 200:
                    return await res.json()
                return None
        except Exception:
            return None

async def fetch_pokemon_species(session, species_name):
    species_data = await fetch_json(session, POKEMON_SPECIES_URL.format(species_name))
    if not species_data:
        return None

    species_id = species_data.get("id")
    dex_number = species_data.get("id")
    is_legendary = species_data.get("is_legendary", False)
    is_mythical = species_data.get("is_mythical", False)

    # Description
    description = ""
    for entry in species_data.get("flavor_text_entries", []):
        if entry["language"]["name"] == "en":
            description = entry["flavor_text"].replace("\n", " ").replace("\x0c", " ")
            break

    # Credit
    credit = species_data.get("generation", {}).get("name", "")

    # Ultra beast detection
    ultra_beast_flag = any(
        "ultra beast" in entry["flavor_text"].lower()
        for entry in species_data.get("flavor_text_entries", [])
        if entry["language"]["name"] == "en"
    )

    # Dynamically detect all available alt names
    alt_languages = [entry["language"]["name"] for entry in species_data.get("names", [])]
    name_map = {lang: species_data["name"] for lang in alt_languages}
    for entry in species_data.get("names", []):
        lang = entry["language"]["name"]
        name_map[lang] = entry["name"]

    rows = []

    for variety in species_data.get("varieties", []):
        var_name = variety["pokemon"]["name"]
        pokemon_detail_url = variety["pokemon"]["url"]
        detail_data = await fetch_json(session, pokemon_detail_url) or {}

        region = get_region(species_data)
        slug = var_name
        types = [t["type"]["name"] for t in detail_data.get("types", [])] + [""] * 2
        stats = {s["stat"]["name"]: s["base_stat"] for s in detail_data.get("stats", [])}

        # Evolution info
        evo_from = evo_to = ""
        if species_data.get("evolution_chain"):
            evo_chain_url = species_data["evolution_chain"]["url"]
            evo_data = await fetch_json(session, evo_chain_url) or {}
            chain = evo_data.get("chain", {})

            def traverse(chain_node, parent_name=None):
                nonlocal evo_from, evo_to
                if chain_node["species"]["name"] == species_name:
                    if parent_name:
                        evo_from = parent_name
                    if chain_node.get("evolves_to"):
                        evo_to = chain_node["evolves_to"][0]["species"]["name"]
                for next_node in chain_node.get("evolves_to", []):
                    traverse(next_node, chain_node["species"]["name"])
            traverse(chain)

        # Mega evolution detection
        evo_mega = evo_mega_x = evo_mega_y = ""
        if "mega" in var_name:
            evo_mega = species_name
            if "x" in var_name:
                evo_mega_x = species_name
            elif "y" in var_name:
                evo_mega_y = species_name

        # Event / catchable / abundance with proper rarity
        event_flag = False
        catchable = 1
        if ultra_beast_flag:
            abundance = "ultra beast"
        elif is_mythical:
            abundance = "mythical"
        elif is_legendary:
            abundance = "legendary"
        else:
            abundance = "common"  # can add "uncommon" logic if needed

        is_form = not variety.get("is_default", True)
        form_item = variety.get("form_name", "")

        row = [
            species_id, dex_number, region, slug, description, credit, 1, catchable, abundance,
            species_data.get("gender_rate", ""), species_data.get("has_gender_differences", "")
        ] + [name_map[lang] for lang in alt_languages] + [
            types[0], types[1], is_mythical, is_legendary, ultra_beast_flag, event_flag,
            detail_data.get("height", ""), detail_data.get("weight", ""), evo_to, evo_from,
            stats.get("hp", ""), stats.get("attack", ""), stats.get("defense", ""),
            stats.get("special-attack", ""), stats.get("special-defense", ""), stats.get("speed", ""),
            evo_mega, evo_mega_x, evo_mega_y, is_form, form_item
        ]

        rows.append(row)
    return rows, alt_languages

async def main():
    async with aiohttp.ClientSession() as session:
        data = await fetch_json(session, POKEMON_API_URL)
        pokemon_names = [p["name"] for p in data.get("results", [])]

        all_rows = []
        all_languages = set()
        tasks = [fetch_pokemon_species(session, name) for name in pokemon_names]

        for coro in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Fetching Pokémon"):
            result = await coro
            if result:
                rows, langs = result
                all_languages.update(langs)
                all_rows.extend(rows)

        # Build final CSV header
        all_languages = sorted(list(all_languages))
        CSV_HEADER = CSV_STATIC_HEADER + [f"name.{lang}" for lang in all_languages] + [
            "type.0","type.1","mythical","legendary","ultra_beast","event","height",
            "weight","evo.to","evo.from","base.hp","base.atk","base.def","base.satk","base.sdef","base.spd",
            "evo.mega","evo.mega_x","evo.mega_y","is_form","form_item"
        ]

    Path(os.path.dirname(OUTPUT_CSV)).mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(all_rows)

    print(f"✅ Saved {len(all_rows)} Pokémon to {OUTPUT_CSV}")

if __name__ == "__main__":
    asyncio.run(main())
