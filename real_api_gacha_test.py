#!/usr/bin/env python3
"""
🎰 REAL ANIME GACHA SIMULATOR - 3-CARD PULLS
Rarity determined SOLELY by character popularity (favorites count)
Popular = Rare | Iconic = Legendary
"""

import asyncio
import aiohttp
import random
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# -------------------------
# Gacha Configs
# -------------------------
RARITY_CHANCES = {
    "common": 0.60,
    "uncommon": 0.30,
    "rare": 0.08,
    "epic": 0.015,
    "legendary": 0.005,
}

POPULARITY_MULTIPLIERS = {
    (0, 999):       [1.2, 1.0, 0.5, 0.1, 0.01],
    (1000, 2999):   [0.9, 1.3, 2.0, 3.0, 5.0],
    (3000, 5999):   [0.5, 0.8, 5.0, 15.0, 30.0],
    (6000, 9999):   [0.2, 0.4, 8.0, 40.0, 100.0],
    (10000, float('inf')): [0.05, 0.1, 5.0, 80.0, 300.0],
}

GACHA_API_CONFIG = {
    "jikan": {
        "base_url": "https://api.jikan.moe/v4",
        "character_endpoint": "/characters/{}/full",
        "timeout": 5,
        "bias_toward_low_favorites": 0.99,
        "low_id_range": (5001, 20000),  # Swapped for low favorites
        "high_id_range": (1, 5000),     # Swapped for high favorites
    },
    "anilist": {
        "base_url": "https://graphql.anilist.co",
        "pool_query": '''
        query ($page: Int, $perPage: Int) {
            Page(page: $page, perPage: $perPage) {
                characters(sort: FAVOURITES_DESC) {
                    id
                    name { full }
                    image { large }
                    favourites
                    gender
                    media(sort: POPULARITY_DESC, perPage: 1) {
                        nodes { title { romaji } }
                    }
                }
            }
        }
        ''',
        "timeout": 4,
        "bias_toward_low_favorites": 0.99,
        "low_page_range": (300, 1000),
        "high_page_range": (1, 100)
    },
    "kitsu": {
        "base_url": "https://kitsu.io/api/edge",
        "character_endpoint": "/characters",
        "timeout": 5,
        "bias_toward_low_favorites": 0.99,
        "low_offset_range": (5000, 15000),
        "high_offset_range": (0, 5000),
        "include_media": "mediaCharacters.media"
    }
}

GACHA_COST = 50
GACHA_CARDS_PER_DRAW = 3
GACHA_CLAIM_TIMEOUT = 30

COLLECTION_FILE = "collection.json"

# -------------------------
# Utility Functions
# -------------------------
def get_popularity_multiplier(favorites: int, rarity: str) -> float:
    for (low, high), multipliers in POPULARITY_MULTIPLIERS.items():
        if low <= favorites < high or (high == float('inf') and favorites >= low):
            idx = ["common", "uncommon", "rare", "epic", "legendary"].index(rarity)
            return multipliers[idx]
    return 1.0

def determine_rarity(favorites: int, pull_index: int = 0) -> str:
    rarities = list(RARITY_CHANCES.keys())
    weights = []

    for rarity in rarities:
        base = RARITY_CHANCES[rarity]
        mult = get_popularity_multiplier(favorites, rarity)

        # Cap multiplier to avoid instant legendary
        if rarity == "legendary":
            mult = min(mult, 10)  # cap at 10× instead of 300×

        weights.append(base * mult)

    # Bias first 2 cards toward common/uncommon
    if pull_index < 2:
        weights = [w * (2 if r in ["common", "uncommon"] else 0.5)
                   for r, w in zip(rarities, weights)]

    total = sum(weights)
    if total == 0:
        return "common"

    normalized = [w / total for w in weights]
    return random.choices(rarities, weights=normalized, k=1)[0]

def load_collection() -> List[Dict]:
    if os.path.exists(COLLECTION_FILE):
        with open(COLLECTION_FILE, 'r') as f:
            return json.load(f)
    return []

def save_collection(collection: List[Dict]):
    with open(COLLECTION_FILE, 'w') as f:
        json.dump(collection, f, indent=4)

# -------------------------
# Gacha Puller Class
# -------------------------
class GachaPuller:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def fetch_character(self) -> Optional[Dict]:
        apis = [
            self.fetch_jikan,
            self.fetch_anilist,
            self.fetch_kitsu
        ]
        random.shuffle(apis)
        for api in apis:
            try:
                char = await api()
                if char:
                    return char
            except:
                continue
        return None

    # -------------------------
    # Jikan API
    # -------------------------
    async def fetch_jikan(self) -> Optional[Dict]:
        config = GACHA_API_CONFIG["jikan"]
        if random.random() < config["bias_toward_low_favorites"]:
            cid = random.randint(*config["low_id_range"])
        else:
            cid = random.randint(*config["high_id_range"])

        url = config["base_url"] + config["character_endpoint"].format(cid)
        try:
            async with self.session.get(url, timeout=config["timeout"]) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                c = data.get("data")
                if not c:
                    return None

                favorites = c.get("favorites", 0)
                name = c.get("name", "Unknown")
                anime = "Unknown Anime"
                if c.get("anime"):
                    anime = c["anime"][0]["anime"].get("title", anime)

                return {
                    "name": name,
                    "anime": anime,
                    "favorites": favorites,
                    "image_url": c.get("images", {}).get("jpg", {}).get("image_url"),
                    "api_source": "Jikan"
                }
        except:
            return None

    # -------------------------
    # AniList API
    # -------------------------
    async def fetch_anilist(self) -> Optional[Dict]:
        config = GACHA_API_CONFIG["anilist"]
        if random.random() < config["bias_toward_low_favorites"]:
            page_range = config["low_page_range"]
        else:
            page_range = config["high_page_range"]
        page = random.randint(*page_range)
        query = config["pool_query"]
        variables = {"page": page, "perPage": 1}

        try:
            async with self.session.post(
                config["base_url"],
                json={"query": query, "variables": variables},
                timeout=config["timeout"]
            ) as resp:
                if resp.status != 200:
                    return None
                result = await resp.json()
                chars = result.get("data", {}).get("Page", {}).get("characters", [])
                if not chars:
                    return None

                c = chars[0]
                media_title = "Unknown"
                if c.get("media", {}).get("nodes"):
                    media_title = c["media"]["nodes"][0]["title"]["romaji"]

                return {
                    "name": c["name"]["full"],
                    "anime": media_title,
                    "favorites": c.get("favourites", 0),
                    "image_url": c["image"]["large"],
                    "api_source": "AniList"
                }
        except:
            return None

    # -------------------------
    # Kitsu API
    # -------------------------
    async def fetch_kitsu(self) -> Optional[Dict]:
        config = GACHA_API_CONFIG["kitsu"]
        if random.random() < config["bias_toward_low_favorites"]:
            offset_range = config["low_offset_range"]
        else:
            offset_range = config["high_offset_range"]
        offset = random.randint(*offset_range)
        params = {
            "page[limit]": 1,
            "page[offset]": offset,
            "include": config["include_media"]
        }

        try:
            async with self.session.get(
                config["base_url"] + config["character_endpoint"],
                params=params,
                timeout=config["timeout"]
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if not data.get("data"):
                    return None

                char = data["data"][0]
                attrs = char["attributes"]
                name = attrs.get("canonicalName") or attrs.get("name") or "Unknown"
                favorites = max(100, 18000 - int(char["id"]) * 2)  # Approx popularity

                anime = "Unknown Anime"
                for inc in data.get("included", []):
                    if inc["type"] == "media":
                        titles = inc["attributes"]["titles"]
                        anime = titles.get("en") or titles.get("en_jp") or titles.get("ja_jp", anime)
                        break

                return {
                    "name": name,
                    "anime": anime,
                    "favorites": favorites,
                    "image_url": attrs.get("image", {}).get("original"),
                    "api_source": "Kitsu"
                }
        except:
            return None

    # -------------------------
    # Pull 3 Cards
    # -------------------------
    async def pull_three_cards(self) -> List[Dict]:
        print("🎰 Pulling 3 cards...\n")
        cards = []
        for i in range(3):
            char = await self.fetch_character()
            if char:
                char["rarity"] = determine_rarity(char["favorites"], pull_index=i)
                emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵", "epic": "🟣", "legendary": "🌟"}[char["rarity"]]
                print(f"{emoji} CARD {i+1}: {char['rarity'].upper()} | {char['name']} ({char['favorites']:,} ❤️)")
                print(f"   From: {char['anime']} • Source: {char['api_source']}\n")
                if char["rarity"] == "legendary":
                    print("\n🌟 🌟 🌟 LEGENDARY PULL! Congratulations! 🌟 🌟 🌟\n")
                cards.append(char)
            else:
                print(f"❌ CARD {i+1}: Failed to load\n")
        return cards

# -------------------------
# Main Loop
# -------------------------
async def main():
    print("🎮 ANIME GACHA - REAL API PULL SIMULATOR")
    print("Rarity based entirely on character popularity!\n")
    print("Commands: pull (to draw 3 cards), inventory (to view collection), quit (to exit)\n")

    collection = load_collection()

    async with GachaPuller() as puller:
        try:
            while True:
                cmd = input("> ").strip().lower()
                if cmd == "pull":
                    cards = await puller.pull_three_cards()
                    if cards:
                        collection.extend(cards)
                        save_collection(collection)
                        print("Added to your collection!\n")
                    print("-" * 60 + "\n")
                elif cmd == "inventory":
                    if not collection:
                        print("Your collection is empty.\n")
                    else:
                        print("Your collection:")
                        for card in collection:
                            print(f"- {card['rarity'].upper()}: {card['name']} from {card['anime']} ({card['favorites']:,} ❤️)")
                        print("\n")
                elif cmd == "quit":
                    break
                else:
                    print("Unknown command. Try 'pull', 'inventory', or 'quit'.\n")
        except KeyboardInterrupt:
            print("\n👋 Goodbye! Thanks for pulling!")

if __name__ == "__main__":
    asyncio.run(main())