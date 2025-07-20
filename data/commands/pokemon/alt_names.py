import aiohttp
import asyncio
import csv
import json
import os
from tqdm import tqdm
from pathlib import Path

POKEMON_LIST_URL = "https://pokeapi.co/api/v2/pokemon-species"
POKEMON_SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{}"
OUTPUT_CSV = "data/commands/pokemon/alt_name_v2.csv"
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

LANG_CODES = list(FLAG_EMOJI_MAP.keys())

async def fetch_json(session, url):
    async with session.get(url) as res:
        return await res.json() if res.status == 200 else None

async def fetch_all_species_names():
    names = []
    url = POKEMON_LIST_URL
    async with aiohttp.ClientSession() as session:
        while url:
            data = await fetch_json(session, url)
            if not data:
                break
            names += [r["name"] for r in data["results"]]
            url = data.get("next")
    return names

async def fetch_species_names_by_lang(species_name, session):
    url = POKEMON_SPECIES_URL.format(species_name)
    data = await fetch_json(session, url)
    if not data:
        return None, {}

    # Map lang_code -> list of names
    lang_name_map = {lang: [] for lang in LANG_CODES}

    for name_entry in data.get("names", []):
        lang = name_entry["language"]["name"]
        if lang in LANG_CODES:
            lang_name_map[lang].append(name_entry["name"])

    # Include varieties (pokemon forms) names too under "en" as fallback
    varieties = data.get("varieties", [])
    for variety in varieties:
        poke_name = variety.get("pokemon", {}).get("name")
        if poke_name:
            lang_name_map["en"].append(poke_name)

    # Deduplicate and join multiple names with comma
    for lang in lang_name_map:
        lang_name_map[lang] = ", ".join(sorted(set(lang_name_map[lang])))

    return species_name, lang_name_map

async def gather_all_alt_names(pokemon_names):
    results = []
    async with aiohttp.ClientSession() as session:
        for species_name in tqdm(pokemon_names, desc="Scanning Pokémon species"):
            species, lang_map = await fetch_species_names_by_lang(species_name, session)
            if species is None:
                continue
            row = [species] + [lang_map.get(lang, "") for lang in LANG_CODES]
            results.append(row)
    return results

def write_csv(data):
    Path(os.path.dirname(OUTPUT_CSV)).mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["pokemon_species"] + [f"{FLAG_EMOJI_MAP.get(lang, lang)} ({lang})" for lang in LANG_CODES]
        writer.writerow(header)
        writer.writerows(data)

def write_flag_map():
    Path(os.path.dirname(FLAG_MAP_JSON)).mkdir(parents=True, exist_ok=True)
    with open(FLAG_MAP_JSON, "w", encoding="utf-8") as f:
        json.dump(FLAG_EMOJI_MAP, f, indent=2, ensure_ascii=False)

async def main():
    print("🔍 Fetching all Pokémon species...")
    species_names = await fetch_all_species_names()
    all_alt_names = await gather_all_alt_names(species_names)
    write_csv(all_alt_names)
    write_flag_map()
    print(f"✅ Done! Saved {len(all_alt_names)} species with alt names by language.")

if __name__ == "__main__":
    asyncio.run(main())
