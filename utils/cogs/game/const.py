
"""
═════════════════════════════════════════════════════════════════════════════════════════════════════
🎮 GAME CONSTANTS & CONFIGURATION
═════════════════════════════════════════════════════════════════════════════════════════════════════"""

import logging
import json
from pathlib import Path
from datetime import timedelta
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
        # Fix the path calculation - go up 4 levels from utils/cogs/game to root
        path = Path(__file__).parent.parent.parent.parent / "data" / "commands" / "minigames" / filename
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
# Extremely difficult to get rares - designed for long-term collection
RARITY_CONFIG = {
    "common": {
        "chance": 0.85, 
        "color": discord.Color.light_grey(), 
        "multiplier": 1, 
        "stars": "⭐"
    },
    "uncommon": {
        "chance": 0.12, 
        "color": discord.Color.green(), 
        "multiplier": 2, 
        "stars": "⭐⭐"
    },
    "rare": {
        "chance": 0.025, 
        "color": discord.Color.blue(), 
        "multiplier": 5, 
        "stars": "⭐⭐⭐"
    },
    "epic": {
        "chance": 0.004, 
        "color": discord.Color.purple(), 
        "multiplier": 15, 
        "stars": "⭐⭐⭐⭐"
    },
    "legendary": {
        "chance": 0.001, 
        "color": discord.Color.gold(), 
        "multiplier": 50, 
        "stars": "⭐⭐⭐⭐⭐"
    },
}

# ═══════════════════════════════════════════════════════════════
# ⏰ FLEXIBLE TIMER SYSTEM
# ═══════════════════════════════════════════════════════════════

# Timer configuration for different game commands
# Each command can have: max_uses (usage limit), command_cooldown (short delay between uses), and cooldown (main cooldown after limit reached)
# Only claim is a true daily command - others use usage-based limits
TIMER_CONFIG = {
    "pokemon": {"max_uses": 5, "command_cooldown": 5, "cooldown": 1800},      # 5 draws, 5s between, 30min cooldown after limit
    "anime": {"max_uses": 5, "command_cooldown": 5, "cooldown": 1800},        # 5 draws, 5s between, 30min cooldown after limit  
    "slots": {"max_uses": 3, "command_cooldown": 5, "cooldown": 1800},        # 3 plays, 5s between, 30min cooldown after limit
    "dice": {"max_uses": 5, "command_cooldown": 5, "cooldown": 300},          # 5 rolls, 5s between, 5min cooldown after limit
    "coinflip": {"max_uses": 5, "command_cooldown": 5, "cooldown": 300},      # 5 flips, 5s between, 5min cooldown after limit
    "guess": {"max_uses": 5, "command_cooldown": 5, "cooldown": 600},         # 5 guesses, 5s between, 10min cooldown after limit
    "hangman": {"max_uses": 20, "command_cooldown": 5, "cooldown": 300},      # 20 games, 5s between, 5min cooldown after limit
    "wordle": {"max_uses": 10, "command_cooldown": 5, "cooldown": 1800},      # 10 games, 5s between, 30min cooldown after limit
    "work": {"max_uses": 999, "command_cooldown": 5, "cooldown": 3600},       # Effectively unlimited, 5s between, 1h cooldown after limit
    "job": {"max_uses": 10, "command_cooldown": 5, "cooldown": 3600},         # 10 applications, 5s between, 1h cooldown after limit
    "rob": {"max_uses": 5, "command_cooldown": 5, "cooldown": 7200},          # 5 attempts, 5s between, 2h cooldown after limit
    "crime": {"max_uses": 999, "command_cooldown": 5, "cooldown": 3600},      # Effectively unlimited, 5s between, 1h cooldown after limit
    "gacha": {"max_uses": 5, "command_cooldown": 5, "cooldown": 1800},       # 5 draws, 5s between, 30min cooldown after limit
    "claim": {"max_uses": 1, "command_cooldown": 5, "cooldown": 86400},        # TRUE DAILY: 1 claim per day
}

# Helper function to get timer config for a command
def get_timer_config(command: str) -> dict:
    """Get timer configuration for a specific command."""
    return TIMER_CONFIG.get(command, {"max_uses": 5, "command_cooldown": 5, "cooldown": 300})

# Helper function to format cooldown message
def format_cooldown_message(remaining: timedelta, command: str = "") -> str:
    """Format a cooldown message with the remaining time."""
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

# Helper function to determine if command uses daily reset or cooldown reset
def uses_daily_reset(command: str) -> bool:
    """Determine if a command should reset daily or based on cooldown."""
    config = get_timer_config(command)
    # Commands with 24+ hour cooldowns use daily reset
    return config["cooldown"] >= 86400

# Helper function to get time period description
def get_time_period_description(cooldown_seconds: int) -> str:
    """Get human-readable time period description based on cooldown."""
    cooldown_hours = cooldown_seconds / 3600
    if cooldown_hours >= 24:
        return "per day"
    elif cooldown_hours >= 1:
        return f"per {int(cooldown_hours)} hour{'s' if int(cooldown_hours) > 1 else ''}"
    else:
        minutes = cooldown_seconds // 60
        return f"per {minutes} minute{'s' if minutes > 1 else ''}"

# ═══════════════════════════════════════════════════════════════
# 🎰 GACHA SYSTEM CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# Gacha rarity tiers with weights and visual styling
# Extremely rare system - designed for long-term collection goals
GACHA_RARITY_TIERS = {
    "common": {"weight": 850, "color": 0x9E9E9E, "stars": 1, "emoji": "⚪"},      # 85% chance
    "uncommon": {"weight": 120, "color": 0x4CAF50, "stars": 2, "emoji": "🟢"},    # 12% chance
    "rare": {"weight": 25, "color": 0x2196F3, "stars": 3, "emoji": "🔵"},         # 2.5% chance
    "epic": {"weight": 4, "color": 0x9C27B0, "stars": 4, "emoji": "🟣"},          # 0.4% chance
    "legendary": {"weight": 1, "color": 0xFFD700, "stars": 5, "emoji": "🌟"},       # 0.1% chance (1 in 1000)
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
