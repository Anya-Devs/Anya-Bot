
"""
═════════════════════════════════════════════════════════════════════════════════════════════════════
🎮 GAME CONSTANTS & CONFIGURATION
═════════════════════════════════════════════════════════════════════════════════════════════════════"""

import logging
import json
from pathlib import Path
from PIL import ImageFont
import discord


# ═══════════════════════════════════════════════════════════════
# 📝 LOGGER SETUP
# ═══════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# 🎨 LEGACY FONT CONFIGURATION (DEPRECATED)
# ═══════════════════════════════════════════════════════════════

# ⚠️ DEPRECATED: Font loading moved to fonts.py
# Keeping for backward compatibility only
FONT_DIR = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts"
EMOJI_FONT_PATH = FONT_DIR / "seguiemj.ttf"
PRIMARY_FONT_PATH = FONT_DIR / "arial.ttf"

def _load_emoji_font(size: int) -> ImageFont.ImageFont:
    """
    ⚠️ DEPRECATED: Use fonts._load_emoji_font() instead
    
    Legacy font loading function for backward compatibility.
    This will be removed in a future update.
    """
    for font_path in (EMOJI_FONT_PATH, PRIMARY_FONT_PATH):
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size)
            except OSError:
                continue
    return ImageFont.load_default()

# ═══════════════════════════════════════════════════════════════
# 📁 CONFIGURATION LOADING
# ═══════════════════════════════════════════════════════════════

def load_config(filename: str) -> dict:
    """
    Load a JSON configuration file from the minigames directory.
    
    📁 PATH: data/commands/minigames/{filename}
    
    📏 PARAMETERS:
        filename (str): Name of the JSON config file
    
    🔄 RETURNS:
        dict: Loaded configuration or empty dict if failed
    
    ⚠️ ERROR HANDLING:
        - Returns empty dict if file not found
        - Logs errors for debugging
        - Graceful fallback to defaults
    """
    try:
        path = Path(__file__).parent.parent.parent / "data" / "commands" / "minigames" / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            # File doesn't exist, return empty dict silently
            return {}
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}")
        return {}

# ═══════════════════════════════════════════════════════════════
# 🎰 GAMBLING CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Load gambling game settings
GAMBLING_CONFIG = load_config("gambling.json")

# Slot machine symbols with weights and multipliers
SLOT_SYMBOLS = GAMBLING_CONFIG.get("slots", {}).get("symbols", {
    "🍒": {"name": "Cherry", "multiplier": 2, "weight": 30},    # Common - 30% chance
    "🍋": {"name": "Lemon", "multiplier": 3, "weight": 25},      # Common - 25% chance  
    "🍊": {"name": "Orange", "multiplier": 4, "weight": 20},     # Uncommon - 20% chance
    "🍇": {"name": "Grape", "multiplier": 5, "weight": 15},      # Uncommon - 15% chance
    "🔔": {"name": "Bell", "multiplier": 10, "weight": 7},       # Rare - 7% chance
    "⭐": {"name": "Star", "multiplier": 25, "weight": 2},        # Epic - 2% chance
    "💎": {"name": "Diamond", "multiplier": 50, "weight": 1},    # Legendary - 1% chance
})

# ═══════════════════════════════════════════════════════════════
# 🃏 CARD GAME RARITY SYSTEM
# ═══════════════════════════════════════════════════════════════

# Rarity configuration for gacha and card games
# Heavier weight on commons/uncommons to make rares feel special
RARITY_CONFIG = {
    "common": {
        "chance": 0.65, 
        "color": discord.Color.light_grey(), 
        "multiplier": 1, 
        "stars": "⭐"
    },
    "uncommon": {
        "chance": 0.23, 
        "color": discord.Color.green(), 
        "multiplier": 2, 
        "stars": "⭐⭐"
    },
    "rare": {
        "chance": 0.09, 
        "color": discord.Color.blue(), 
        "multiplier": 5, 
        "stars": "⭐⭐⭐"
    },
    "epic": {
        "chance": 0.02, 
        "color": discord.Color.purple(), 
        "multiplier": 15, 
        "stars": "⭐⭐⭐⭐"
    },
    "legendary": {
        "chance": 0.01, 
        "color": discord.Color.gold(), 
        "multiplier": 50, 
        "stars": "⭐⭐⭐⭐⭐"
    },
}

# ═══════════════════════════════════════════════════════════════
# 📊 DAILY LIMITS & ECONOMY
# ═══════════════════════════════════════════════════════════════

# Daily usage limits for different game commands
DAILY_LIMITS = {
    "pokemon": 15,      # Pokémon-related commands
    "anime": 15,        # Anime-related commands  
    "slots": 50,        # Slot machine plays
    "dice": 50,         # Dice rolls
    "coinflip": 100,    # Coin flips
    "guess": 30,        # Number guessing games
    "hangman": 20,      # Hangman games
    "wordle": 10,       # Wordle games
    "work": 999,        # Work commands (effectively unlimited)
    "job": 999,         # Job applications
    "rob": 999,         # Robbery attempts
    "crime": 999,       # Crime attempts
    "gacha": 200,       # Gacha pulls
}

# ═══════════════════════════════════════════════════════════════
# 🎰 GACHA SYSTEM CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Gacha rarity tiers with weights and visual styling
GACHA_RARITY_TIERS = {
    "common": {"weight": 50, "color": 0x9E9E9E, "stars": 1, "emoji": "⚪"},      # 50% chance
    "uncommon": {"weight": 25, "color": 0x4CAF50, "stars": 2, "emoji": "🟢"},    # 25% chance
    "rare": {"weight": 15, "color": 0x2196F3, "stars": 3, "emoji": "🔵"},        # 15% chance
    "epic": {"weight": 7, "color": 0x9C27B0, "stars": 4, "emoji": "🟣"},         # 7% chance
    "legendary": {"weight": 3, "color": 0xFFD700, "stars": 5, "emoji": "🌟"},     # 3% chance
}

# Gacha system economics
GACHA_COST = 50              # Cost per draw in stella points
GACHA_CARDS_PER_DRAW = 3     # Number of cards shown per draw
GACHA_CLAIM_TIMEOUT = 30     # Seconds to claim cards before they're lost

# ═══════════════════════════════════════════════════════════════
# 🎰 SLOT MACHINE VISUAL CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Slot machine color scheme
SLOT_BG_COLOR = (30, 30, 40)          # Dark background
SLOT_FRAME_COLOR = (255, 215, 0)     # Gold frame
SLOT_REEL_BG = (20, 20, 30)          # Reel background
SLOT_TEXT_COLOR = (255, 255, 255)    # White text

# Slot symbol colors for visual rendering
SLOT_SYMBOL_COLORS = {
    "🍒": (220, 20, 60),    # Cherry - Red
    "🍋": (255, 255, 0),    # Lemon - Yellow
    "🍊": (255, 165, 0),    # Orange - Orange
    "🍇": (128, 0, 128),    # Grape - Purple
    "🔔": (255, 215, 0),    # Bell - Gold
    "⭐": (255, 255, 100),  # Star - Light Yellow
    "💎": (0, 191, 255),    # Diamond - Blue
    "🥜": (139, 69, 19),    # Peanut - Brown
}

# ═══════════════════════════════════════════════════════════════
# 📋 CLASSIC GAMES CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Load classic game settings
CLASSIC_CONFIG = load_config("classic.json")

# Load economy system settings
GROUNDED_CONFIG = load_config("grounded.json")

# ═══════════════════════════════════════════════════════════════
# 🔄 LEGACY COMPATIBILITY & MIGRATION NOTES
# ═══════════════════════════════════════════════════════════════

"""
📝 MIGRATION GUIDE:

This file is being restructured for better maintainability:

✅ COMPLETED:
    • Font loading moved to fonts.py
    • Added comprehensive documentation
    • Organized constants by category

🔄 IN PROGRESS:
    • Moving game-specific configs to separate modules
    • Standardizing configuration format

📋 PLANNED:
    • Split into multiple config files by game type
    • Add configuration validation
    • Implement hot-reloading for config changes

⚠️ DEPRECATION NOTICES:
    • Direct font imports from this file - use fonts.py instead
    • Hardcoded game constants - move to config files
    • Mixed configuration formats - standardize to JSON

🎯 RECOMMENDATIONS:
    • Use fonts._load_emoji_font() for new code
    • Store game-specific settings in respective config files
    • Follow the established naming conventions
"""

# ═══════════════════════════════════════════════════════════════
# 🚀 END OF CONSTANTS FILE
# ═══════════════════════════════════════════════════════════════
