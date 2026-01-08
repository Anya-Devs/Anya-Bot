"""Game Constants & Configuration"""

import logging
import json
import random
from pathlib import Path
from datetime import timedelta
from PIL import ImageFont
import discord

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION LOADING
# ═══════════════════════════════════════════════════════════════

def load_config(filename: str) -> dict:
    """Load JSON config from data/commands/minigames/{filename}"""
    try:
        path = Path(__file__).parent.parent.parent.parent / "data" / "commands" / "minigames" / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}")
        return {}

# ═══════════════════════════════════════════════════════════════
# EMOJI CONSTANTS
# ═══════════════════════════════════════════════════════════════

class GameEmojis:
    """Centralized emoji constants for easy editing"""
    
    LEGENDARY = "🌟"
    EPIC = "🟣"
    RARE = "🔵"
    UNCOMMON = "🟢"
    COMMON = "⚪"
    
    CHERRY = "🍒"
    LEMON = "🍋"
    ORANGE = "🍊"
    GRAPE = "🍇"
    BELL = "🔔"
    STAR = "⭐"
    DIAMOND = "💎"
    
    GAME = "🎮"
    SLOTS = "🎰"
    DICE = "🎲"
    CARDS = "🎴"
    COIN = "🪙"
    
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    LOADING = "⏳"
    TIMER = "⏰"
    
    MONEY = "💰"
    CREDIT_CARD = "💳"
    CHART_DOWN = "📉"
    CHART_UP = "📈"
    HEARTS = "❤️"
    
    BOX = "📦"
    SPARKLES = "✨"
    GIFT = "🎁"
    TROPHY = "🏆"
    
    FEMALE = "♀️"
    MALE = "♂️"
    NONBINARY = "⚧"
    
    FIRE = "🔥"
    BOOM = "💥"
    CELEBRATION = "🎉"
    SKULL = "💀"

RARITY_EMOJIS = {
    "legendary": GameEmojis.LEGENDARY,
    "epic": GameEmojis.EPIC,
    "rare": GameEmojis.RARE,
    "uncommon": GameEmojis.UNCOMMON,
    "common": GameEmojis.COMMON,
}

# ═══════════════════════════════════════════════════════════════
# GAMBLING CONFIGURATION
# ═══════════════════════════════════════════════════════════════

GAMBLING_CONFIG = load_config("gambling.json")

SLOT_SYMBOLS = GAMBLING_CONFIG.get("slots", {}).get("symbols", {
    "🍒": {"name": "Cherry", "multiplier": 2, "weight": 30},
    "🍋": {"name": "Lemon", "multiplier": 3, "weight": 25},
    "🍊": {"name": "Orange", "multiplier": 4, "weight": 20},
    "🍇": {"name": "Grape", "multiplier": 5, "weight": 15},
    "🔔": {"name": "Bell", "multiplier": 10, "weight": 7},
    "⭐": {"name": "Star", "multiplier": 25, "weight": 2},
    "💎": {"name": "Diamond", "multiplier": 50, "weight": 1},
})

SLOT_BG_COLOR = (30, 30, 40)
SLOT_FRAME_COLOR = (255, 215, 0)
SLOT_REEL_BG = (20, 20, 30)
SLOT_TEXT_COLOR = (255, 255, 255)

SLOT_SYMBOL_COLORS = {
    "🍒": (220, 20, 60),
    "🍋": (255, 255, 0),
    "🍊": (255, 165, 0),
    "🍇": (128, 0, 128),
    "🔔": (255, 215, 0),
    "⭐": (255, 255, 100),
    "💎": (0, 191, 255),
    "🥜": (139, 69, 19),
}

# ═══════════════════════════════════════════════════════════════
# CARD GAME RARITY SYSTEM
# ═══════════════════════════════════════════════════════════════

RARITY_CONFIG = {
    "common": {"chance": 0.85, "color": discord.Color.light_grey(), "multiplier": 1, "stars": "⭐"},
    "uncommon": {"chance": 0.12, "color": discord.Color.green(), "multiplier": 2, "stars": "⭐⭐"},
    "rare": {"chance": 0.025, "color": discord.Color.blue(), "multiplier": 5, "stars": "⭐⭐⭐"},
    "epic": {"chance": 0.004, "color": discord.Color.purple(), "multiplier": 15, "stars": "⭐⭐⭐⭐"},
    "legendary": {"chance": 0.001, "color": discord.Color.gold(), "multiplier": 50, "stars": "⭐⭐⭐⭐⭐"},
}

# ═══════════════════════════════════════════════════════════════
# TIMER SYSTEM
# ═══════════════════════════════════════════════════════════════

TIMER_CONFIG = {
    "pokemon": {"max_uses": 6, "command_cooldown": 5, "cooldown": 1800},
    "anime": {"max_uses": 6, "command_cooldown": 5, "cooldown": 1800},
    "slots": {"max_uses": 6, "command_cooldown": 5, "cooldown": 1800},
    "dice": {"max_uses": 6, "command_cooldown": 5, "cooldown": 300},
    "coinflip": {"max_uses": 6, "command_cooldown": 5, "cooldown": 300},
    "guess": {"max_uses": 5, "command_cooldown": 5, "cooldown": 600},
    "hangman": {"max_uses": 20, "command_cooldown": 5, "cooldown": 300},
    "wordle": {"max_uses": 10, "command_cooldown": 5, "cooldown": 1800},
    "work": {"max_uses": 4, "command_cooldown": 5, "cooldown": 3600},
    "job": {"max_uses": 10, "command_cooldown": 5, "cooldown": 3600},
    "rob": {"max_uses": 5, "command_cooldown": 5, "cooldown": 7200},
    "crime": {"max_uses": 3, "command_cooldown": 5, "cooldown": 3600},
    "gacha": {"max_uses": 5, "command_cooldown": 5, "cooldown": 1800},
    "claim": {"max_uses": 1, "command_cooldown": 5, "cooldown": 86400},
}

def get_timer_config(command: str) -> dict:
    return TIMER_CONFIG.get(command, {"max_uses": 5, "command_cooldown": 5, "cooldown": 300})

def format_cooldown_message(remaining: timedelta, command: str = "") -> str:
    total_seconds = int(remaining.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        time_str = f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        time_str = f"{minutes}m {seconds}s"
    else:
        time_str = f"{seconds}s"
    
    command_name = command.replace("_", " ").title()
    return f"⏰ {command_name} is cooling down! Wait {time_str} before playing again."

def uses_daily_reset(command: str) -> bool:
    config = get_timer_config(command)
    return config["cooldown"] >= 86400

def get_time_period_description(cooldown_seconds: int) -> str:
    cooldown_hours = cooldown_seconds / 3600
    if cooldown_hours >= 24:
        return "per day"
    elif cooldown_hours >= 1:
        return f"per {int(cooldown_hours)} hour{'s' if int(cooldown_hours) > 1 else ''}"
    else:
        minutes = cooldown_seconds // 60
        return f"per {minutes} minute{'s' if minutes > 1 else ''}"

# ═══════════════════════════════════════════════════════════════
# GACHA SYSTEM
# ═══════════════════════════════════════════════════════════════

GACHA_RARITY_TIERS = {
    "common": {"weight": 980000, "color": 0x9E9E9E, "stars": 1, "emoji": GameEmojis.COMMON},
    "uncommon": {"weight": 19000, "color": 0x4CAF50, "stars": 2, "emoji": GameEmojis.UNCOMMON},
    "rare": {"weight": 950, "color": 0x2196F3, "stars": 3, "emoji": GameEmojis.RARE},
    "epic": {"weight": 45, "color": 0x9C27B0, "stars": 4, "emoji": GameEmojis.EPIC},
    "legendary": {"weight": 5, "color": 0xFFD700, "stars": 5, "emoji": GameEmojis.LEGENDARY},
}

# Anime popularity thresholds (based on MAL members/AniList popularity)
GACHA_ANIME_POPULARITY_THRESHOLDS = {
    "legendary": 2000000,  # 2M+ members (Attack on Titan, Demon Slayer, Frieren)
    "epic": 1000000,       # 1M+ members (Jujutsu Kaisen, Spy x Family)
    "rare": 500000,        # 500K+ members (Popular seasonal anime)
    "uncommon": 100000,    # 100K+ members (Well-known anime)
    "common": 0,           # Everything else
}

# Character favorites thresholds (PRIMARY factor - this determines rarity!)
GACHA_CHARACTER_FAVORITES_THRESHOLDS = {
    "legendary": 7000,     # 7K+ favorites (Itachi: 18,686, Levi: 31,576, Izuku: 11,413)
    "epic": 3000,          # 3K+ favorites (Very popular characters)
    "rare": 800,           # 800+ favorites (Popular characters)
    "uncommon": 150,       # 150+ favorites (Known characters)
    "common": 0,           # Everything else
}

GACHA_API_CONFIG = {
    "jikan": {
        "base_url": "https://api.jikan.moe/v4",
        "character_endpoint": "/characters/{}/full",
        "anime_endpoint": "/anime/{}",
        "timeout": 2,  # Reduced for speed
        # ID ranges for character fetching (lower IDs = older/more established)
        "character_id_ranges": {
            "legendary": (1, 5000),      # Very popular characters
            "epic": (1, 15000),          # Popular characters
            "rare": (1, 40000),          # Moderately known
            "uncommon": (1, 80000),      # Less known
            "common": (1, 150000),       # Any character
        }
    },
    "anilist": {
        "base_url": "https://graphql.anilist.co",
        # Query to get characters from anime with specific popularity ranges
        "anime_query": '''
        query ($popularityMin: Int, $popularityMax: Int) {
            Page(page: 1, perPage: 50) {
                media(type: ANIME, popularity_greater: $popularityMin, popularity_lesser: $popularityMax, sort: POPULARITY_DESC) {
                    id
                    title { romaji }
                    popularity
                    characters(sort: FAVOURITES_DESC, perPage: 10) {
                        nodes {
                            id
                            name { full }
                            image { large }
                            favourites
                            gender
                        }
                    }
                }
            }
        }
        ''',
        "character_query": '''
        query ($id: Int) {
            Character(id: $id) {
                id
                name { full }
                image { large }
                favourites
                gender
                media(sort: POPULARITY_DESC, perPage: 1, type: ANIME) {
                    nodes {
                        id
                        title { romaji }
                        popularity
                        members
                    }
                }
            }
        }
        ''',
        "timeout": 2,  # Reduced for speed
        # Popularity ranges for anime (higher = more popular)
        "anime_popularity_ranges": {
            "legendary": (200000, 999999),  # Extremely popular anime
            "epic": (100000, 199999),       # Very popular anime
            "rare": (50000, 99999),         # Popular anime
            "uncommon": (20000, 49999),     # Moderately popular
            "common": (1, 19999),           # Less popular
        }
    },
}

GACHA_COST = 50
GACHA_CARDS_PER_DRAW = 3
GACHA_CLAIM_TIMEOUT = 30

# ═══════════════════════════════════════════════════════════════
# GACHA HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def roll_gacha_rarity() -> str:
    roll = random.randint(1, 1000000)
    cumulative = 0
    for rarity in ["legendary", "epic", "rare", "uncommon", "common"]:
        cumulative += GACHA_RARITY_TIERS[rarity]["weight"]
        if roll <= cumulative:
            return rarity
    return "common"

def get_rarity_from_anime_popularity(popularity: int) -> str:
    """Determine rarity based on anime popularity (primary factor).
    Higher popularity = rarer character.
    """
    if popularity >= GACHA_ANIME_POPULARITY_THRESHOLDS["legendary"]:
        return "legendary"
    elif popularity >= GACHA_ANIME_POPULARITY_THRESHOLDS["epic"]:
        return "epic"
    elif popularity >= GACHA_ANIME_POPULARITY_THRESHOLDS["rare"]:
        return "rare"
    elif popularity >= GACHA_ANIME_POPULARITY_THRESHOLDS["uncommon"]:
        return "uncommon"
    return "common"

def get_rarity_from_favorites(favorites: int) -> str:
    """Determine rarity based on character favorites (secondary factor)."""
    if favorites >= GACHA_CHARACTER_FAVORITES_THRESHOLDS["legendary"]:
        return "legendary"
    elif favorites >= GACHA_CHARACTER_FAVORITES_THRESHOLDS["epic"]:
        return "epic"
    elif favorites >= GACHA_CHARACTER_FAVORITES_THRESHOLDS["rare"]:
        return "rare"
    elif favorites >= GACHA_CHARACTER_FAVORITES_THRESHOLDS["uncommon"]:
        return "uncommon"
    return "common"

def get_combined_rarity(anime_popularity: int, char_favorites: int) -> str:
    """Fast rarity calculation using CHARACTER FAVORITES (80%) + anime popularity (20%).
    Character favorites are the PRIMARY factor - popular characters should be legendary!
    Optimized for speed with direct threshold checks.
    """
    # Direct threshold checks - faster than string comparisons
    # Character favorites are PRIMARY (80% weight)
    char_score = (
        5 if char_favorites >= 7000 else
        4 if char_favorites >= 3000 else
        3 if char_favorites >= 800 else
        2 if char_favorites >= 150 else 1
    )
    
    # Anime popularity is SECONDARY (20% weight)
    anime_score = (
        5 if anime_popularity >= 2000000 else
        4 if anime_popularity >= 1000000 else
        3 if anime_popularity >= 500000 else
        2 if anime_popularity >= 100000 else 1
    )
    
    # Weighted average: 80% character favorites, 20% anime popularity
    # This ensures popular characters like Itachi (18,686 favs) are legendary!
    combined_score = (char_score * 0.8) + (anime_score * 0.2)
    
    # Direct return - fastest path
    return (
        "legendary" if combined_score >= 4.5 else
        "epic" if combined_score >= 3.5 else
        "rare" if combined_score >= 2.5 else
        "uncommon" if combined_score >= 1.5 else
        "common"
    )

def matches_target_rarity(actual_rarity: str, target_rarity: str) -> bool:
    """Fast rarity matching check - single function for all validation."""
    if target_rarity == "legendary":
        return actual_rarity == "legendary"
    elif target_rarity == "epic":
        return actual_rarity in ("epic", "rare")
    elif target_rarity == "rare":
        return actual_rarity in ("rare", "uncommon")
    elif target_rarity == "uncommon":
        return actual_rarity in ("uncommon", "common", "rare")
    else:  # common
        return actual_rarity in ("common", "uncommon")

def get_gacha_rates_display() -> str:
    return (
        f"{GameEmojis.LEGENDARY} **5★ Legendary** - 0.0005% (1/200,000)\n"
        f"{GameEmojis.EPIC} **4★ Epic** - 0.0045% (1/22,222)\n"
        f"{GameEmojis.RARE} **3★ Rare** - 0.095% (1/1,053)\n"
        f"{GameEmojis.UNCOMMON} **2★ Uncommon** - 1.9%\n"
        f"{GameEmojis.COMMON} **1★ Common** - 98%"
    )

def generate_uid() -> str:
    import uuid
    return uuid.uuid4().hex[:8].upper()

def calculate_release_value(favorites: int, rarity: str, char_name: str = "unknown") -> int:
    """Calculate dynamic release value with seed-based randomization.
    Format: base + favorites_bonus + seed_variance
    Example: Uncommon with 150 favs = 500 + (150*2) + seed(50-150) = 850-950 pts
    """
    import hashlib
    
    # Base values per rarity tier
    base_values = {"common": 200, "uncommon": 500, "rare": 1200, "epic": 3000, "legendary": 7500}
    base = base_values.get(rarity, 200)
    
    # Favorites bonus calculation (scaled)
    if favorites == 0:
        favorites_bonus = 0
    elif favorites <= 100:
        favorites_bonus = int(favorites * 1.5)
    elif favorites <= 500:
        favorites_bonus = 150 + int((favorites - 100) * 2)
    elif favorites <= 2000:
        favorites_bonus = 950 + int((favorites - 500) * 2.5)
    elif favorites <= 8000:
        favorites_bonus = 4700 + int((favorites - 2000) * 3)
    else:
        favorites_bonus = 22700 + int((favorites - 8000) * 3.5)
    
    # Rarity multipliers for favorites bonus
    rarity_multipliers = {"common": 0.8, "uncommon": 1.0, "rare": 1.2, "epic": 1.4, "legendary": 1.6}
    favorites_bonus = int(favorites_bonus * rarity_multipliers.get(rarity, 1.0))
    
    # Seed-based variance (deterministic per character)
    seed_input = f"{char_name}_{favorites}_{rarity}"
    hash_object = hashlib.md5(seed_input.encode())
    seed_value = int(hash_object.hexdigest()[:8], 16)
    random.seed(seed_value)
    
    # Variance range based on base value (±10-30%)
    variance_range = base * 0.2
    seed_variance = int(random.uniform(-variance_range, variance_range))
    random.seed()  # Reset seed
    
    total_value = base + favorites_bonus + seed_variance
    return max(500, min(total_value, 100000))

# ═══════════════════════════════════════════════════════════════
# API FETCH FUNCTIONS
# ═══════════════════════════════════════════════════════════════

async def fetch_jikan_character(session, target_rarity: str):
    """Fast Jikan API fetch - optimized for speed with parallel requests."""
    config = GACHA_API_CONFIG["jikan"]
    id_ranges = config.get("character_id_ranges", {})
    id_range = id_ranges.get(target_rarity, (1, 150000))
    timeout = config["timeout"]
    
    # Try fewer attempts but faster
    max_attempts = 8
    for attempt in range(max_attempts):
        cid = random.randint(*id_range)
        char_url = config["base_url"] + config["character_endpoint"].format(cid)
        
        try:
            async with session.get(char_url, timeout=timeout) as resp:
                if resp.status != 200:
                    continue
                data = await resp.json()
                c = data.get("data")
                if not c:
                    continue

                favorites = c.get("favorites", 0)
                name = c.get("name", "Unknown")
                gender = "Unknown"
                anime_title = "Unknown Anime"
                anime_members = 0
                
                # Get anime info
                if c.get("anime") and len(c["anime"]) > 0:
                    anime_data = c["anime"][0]
                    anime_title = anime_data.get("title", anime_title)
                    anime_mal_id = anime_data.get("mal_id")
                    
                    # Fetch anime details
                    if anime_mal_id:
                        anime_url = config["base_url"] + config["anime_endpoint"].format(anime_mal_id)
                        try:
                            async with session.get(anime_url, timeout=timeout) as anime_resp:
                                if anime_resp.status == 200:
                                    anime_full = await anime_resp.json()
                                    anime_members = anime_full.get("data", {}).get("members", 0)
                        except:
                            pass

                # Fast rarity check using consolidated function
                char_rarity = get_combined_rarity(anime_members, favorites)
                if not matches_target_rarity(char_rarity, target_rarity):
                    continue

                # Validate required fields
                image_url = c.get("images", {}).get("jpg", {}).get("image_url")
                if not image_url:
                    continue  # Skip characters without images
                if anime_title == "Unknown Anime":
                    continue  # Skip characters without anime source

                return {
                    "id": cid,
                    "name": name,
                    "anime": anime_title,
                    "anime_popularity": anime_members,
                    "favorites": favorites,
                    "gender": gender,
                    "image_url": image_url,
                    "api_source": "Jikan"
                }
        except:
            continue
    
    return None

async def fetch_anilist_character(session, target_rarity: str):
    """Fast AniList API fetch - optimized for speed."""
    config = GACHA_API_CONFIG["anilist"]
    popularity_ranges = config.get("anime_popularity_ranges", {})
    pop_range = popularity_ranges.get(target_rarity, (1, 19999))
    timeout = config["timeout"]
    
    # Try fewer attempts but faster
    max_attempts = 8
    for attempt in range(max_attempts):
        try:
            variables = {
                "popularityMin": pop_range[0],
                "popularityMax": pop_range[1]
            }
            
            async with session.post(
                config["base_url"],
                json={"query": config["anime_query"], "variables": variables},
                timeout=timeout
            ) as resp:
                if resp.status != 200:
                    continue
                result = await resp.json()
                anime_list = result.get("data", {}).get("Page", {}).get("media", [])
                if not anime_list:
                    continue

                anime = random.choice(anime_list)
                anime_title = anime["title"]["romaji"]
                anime_popularity = anime.get("popularity", 0)
                
                characters = anime.get("characters", {}).get("nodes", [])
                if not characters:
                    continue
                
                c = random.choice(characters)
                gender = c.get("gender", "Unknown")
                if gender:
                    gender = gender.title()

                favorites = c.get("favourites", 0)
                
                # Fast rarity check using consolidated function
                char_rarity = get_combined_rarity(anime_popularity, favorites)
                if not matches_target_rarity(char_rarity, target_rarity):
                    continue

                # Validate required fields
                image_url = c.get("image", {}).get("large") if c.get("image") else None
                char_name = c.get("name", {}).get("full") if c.get("name") else None
                
                if not image_url or not char_name or not anime_title:
                    continue  # Skip characters with missing data

                return {
                    "id": c.get("id"),
                    "name": char_name,
                    "anime": anime_title,
                    "anime_popularity": anime_popularity,
                    "favorites": favorites,
                    "gender": gender or "Unknown",
                    "image_url": image_url,
                    "api_source": "AniList"
                }
        except:
            continue
    
    return None

# ═══════════════════════════════════════════════════════════════
# CLASSIC GAMES & ECONOMY
# ═══════════════════════════════════════════════════════════════

CLASSIC_CONFIG = load_config("classic.json")
GROUNDED_CONFIG = load_config("grounded.json")

# ═══════════════════════════════════════════════════════════════
# LEGACY COMPATIBILITY
# ═══════════════════════════════════════════════════════════════

FONT_DIR = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts"
EMOJI_FONT_PATH = FONT_DIR / "seguiemj.ttf"
PRIMARY_FONT_PATH = FONT_DIR / "arial.ttf"

def _load_emoji_font(size: int) -> ImageFont.ImageFont:
    """DEPRECATED: Use fonts._load_emoji_font() instead"""
    for font_path in (EMOJI_FONT_PATH, PRIMARY_FONT_PATH):
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size)
            except OSError:
                continue
    return ImageFont.load_default()
