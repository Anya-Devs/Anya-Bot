import aiohttp
import asyncio
import csv
import json
import os
from tqdm import tqdm
from pathlib import Path

# URLs for species and forms
POKEMON_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{}"
POKEMON_FORMS_URL = "https://pokeapi.co/api/v2/pokemon-form/{}"
POKEMON_SPECIES_LIST_URL = "https://pokeapi.co/api/v2/pokemon-species?limit=10000"
POKEMON_FORMS_LIST_URL = "https://pokeapi.co/api/v2/pokemon-form?limit=10000"

OUTPUT_CSV = "data/commands/pokemon/alt_names.csv"
FLAG_MAP_JSON = "data/commands/pokemon/flag_map.json"

FLAG_EMOJI_MAP = {
    "en": "🇬🇧", "fr": "🇫🇷", "es": "🇪🇸", "de": "🇩🇪", "it": "🇮🇹", "ja": "🇯🇵",
    "ko": "🇰🇷", "zh-Hans": "🇨🇳", "ru": "🇷🇺", "es-MX": "🇲🇽", "pt": "🇵🇹",
    "nl": "🇳🇱", "tr": "🇹🇷", "ar": "🇸🇦", "th": "🇹🇭", "vi": "🇻🇳", "pl": "🇵🇱",
    "sv": "🇸🇪", "da": "🇩🇰", "no": "🇳🇴", "fi": "🇫🇮", "el": "🇬🇷", "id": "🇮🇩",
    "ms": "🇲🇾", "fil": "🇵🇭", "hu": "🇭🇺", "cs": "🇨🇿", "sk": "🇸🇰", "ro": "🇷🇴",
    "uk": "🇺🇦", "hr": "🇭🇷", "bg": "🇧🇬", "et": "🇪🇪", "lv": "🇱🇻", "lt": "🇱🇹",
    "sl": "🇸🇮", "mt": "🇲🇹", "sq": "🇦🇱", "mk": "🇲🇰", "bs": "🇧🇦", "sr": "🇷🇸",
    "cy": "🇨🇾", "ga": "🇮🇪", "gd": "🏴", "kw": "🇰🇾", "br": "🇧🇷", "af": "🇿🇦",
    "xh": "🇿🇦", "zu": "🇿🇦", "tn": "🇿🇦", "st": "🇿🇦", "ss": "🇿🇦", "nr": "🇿🇦",
    "nso": "🇿🇦", "ts": "🇿🇦", "ve": "🇿🇦", "xog": "🇺🇬", "lg": "🇺🇬", "ak": "🇬🇭",
    "tw": "🇬🇭", "bm": "🇧🇫", "my": "🇲🇲", "km": "🇰🇭", "lo": "🇱🇦", "am": "🇪🇹",
    "ti": "🇪🇹", "om": "🇪🇹", "so": "🇸🇴", "sw": "🇰🇪", "rw": "🇷🇼", "yo": "🇳🇬",
    "ig": "🇳🇬", "ha": "🇳🇬", "bn": "🇧🇩", "pa": "🇮🇳", "gu": "🇮🇳", "or": "🇮🇳",
    "ta": "🇮🇳", "te": "🇮🇳", "kn": "🇮🇳", "ml": "🇮🇳", "si": "🇱🇰", "ne": "🇳🇵",
    "dz": "🇧🇹", "be": "🇧🇾", "kk": "🇰🇿", "uz": "🇺🇿", "ky": "🇰🇬"
}

BATCH_SIZE = 30  # Adjust batch size to be kind to API and speed up


async def fetch_json(session, url):
    async with session.get(url) as res:
        if res.status == 200:
            return await res.json()
        else:
            return None


async def fetch_all_species(session):
    data = await fetch_json(session, POKEMON_SPECIES_LIST_URL)
    return [entry["name"] for entry in data.get("results", [])] if data else []


async def fetch_all_forms(session):
    data = await fetch_json(session, POKEMON_FORMS_LIST_URL)
    return [entry["name"] for entry in data.get("results", [])] if data else []


async def fetch_species_names(name, session):
    data = await fetch_json(session, POKEMON_SPECIES_URL.format(name))
    if not data or "names" not in data:
        return []
    return [entry["name"] for entry in data["names"]]


async def fetch_form_names(name, session):
    data = await fetch_json(session, POKEMON_FORMS_URL.format(name))
    if not data or "names" not in data:
        return []
    return [entry["name"] for entry in data["names"]]


async def batch_fetch_names(names, fetch_func, session):
    results = {}
    for i in tqdm(range(0, len(names), BATCH_SIZE), desc=f"Fetching {fetch_func.__name__}"):
        batch = names[i : i + BATCH_SIZE]
        tasks = [fetch_func(name, session) for name in batch]
        batch_results = await asyncio.gather(*tasks)
        for name, alt_names in zip(batch, batch_results):
            results[name] = alt_names
    return results


async def main():
    Path(os.path.dirname(OUTPUT_CSV)).mkdir(parents=True, exist_ok=True)
    Path(os.path.dirname(FLAG_MAP_JSON)).mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        species_names = await fetch_all_species(session)
        form_names = await fetch_all_forms(session)

        species_alt_names = await batch_fetch_names(species_names, fetch_species_names, session)
        form_alt_names = await batch_fetch_names(form_names, fetch_form_names, session)

    # Combine alt names for species + forms keyed by species or form name
    combined = {}

    # Species alt names keyed by species name
    for species, names in species_alt_names.items():
        combined[species] = set(names)

    # For forms, group by form name (some forms may overlap with species, keep separate)
    for form, names in form_alt_names.items():
        if form in combined:
            combined[form].update(names)
        else:
            combined[form] = set(names)

    # Convert to list and prepare CSV rows: [pokemon_or_form_name, alt_names_comma_separated]
    csv_rows = []
    for key, names_set in combined.items():
        alt_names_str = ", ".join(sorted(names_set))
        csv_rows.append([key, alt_names_str])

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pokemon_or_form_name", "alt_names"])
        writer.writerows(csv_rows)

    # Write flag map JSON as-is
    with open(FLAG_MAP_JSON, "w", encoding="utf-8") as f:
        json.dump(FLAG_EMOJI_MAP, f, indent=2, ensure_ascii=False)

    print(f"✅ Done! Saved {len(csv_rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    asyncio.run(main())
