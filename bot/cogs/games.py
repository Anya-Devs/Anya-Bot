import discord
from discord.ext import commands
import random
import asyncio
import aiohttp
import logging
import json
import io
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

logger = logging.getLogger(__name__)

# Load config files
def load_config(filename: str) -> dict:
    """Load a JSON config file from data/commands/minigames/"""
    try:
        path = Path(__file__).parent.parent.parent / "data" / "commands" / "minigames" / filename
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}")
        return {}

GAMBLING_CONFIG = load_config("gambling.json")
CLASSIC_CONFIG = load_config("classic.json")
GROUNDED_CONFIG = load_config("grounded.json")

# Slot machine symbols from config or fallback
SLOT_SYMBOLS = GAMBLING_CONFIG.get("slots", {}).get("symbols", {
    "🍒": {"name": "Cherry", "multiplier": 2, "weight": 30},
    "🍋": {"name": "Lemon", "multiplier": 3, "weight": 25},
    "🍊": {"name": "Orange", "multiplier": 4, "weight": 20},
    "🍇": {"name": "Grape", "multiplier": 5, "weight": 15},
    "🔔": {"name": "Bell", "multiplier": 10, "weight": 7},
    "⭐": {"name": "Star", "multiplier": 25, "weight": 2},
    "💎": {"name": "Diamond", "multiplier": 50, "weight": 1},
})

# Rarity config for card games
RARITY_CONFIG = {
    "common": {"chance": 0.50, "color": discord.Color.light_grey(), "multiplier": 1, "stars": "⭐"},
    "uncommon": {"chance": 0.30, "color": discord.Color.green(), "multiplier": 2, "stars": "⭐⭐"},
    "rare": {"chance": 0.15, "color": discord.Color.blue(), "multiplier": 5, "stars": "⭐⭐⭐"},
    "epic": {"chance": 0.04, "color": discord.Color.purple(), "multiplier": 15, "stars": "⭐⭐⭐⭐"},
    "legendary": {"chance": 0.01, "color": discord.Color.gold(), "multiplier": 50, "stars": "⭐⭐⭐⭐⭐"},
}

# Daily limits
DAILY_LIMITS = {
    "pokemon": 15,
    "anime": 15,
    "slots": 50,
    "dice": 50,
    "coinflip": 100,
    "guess": 30,
    "hangman": 20,
    "wordle": 10,
    "work": 999,
    "job": 999,
    "rob": 999,
    "crime": 999,
    "gacha": 10,
}

# ═══════════════════════════════════════════════════════════════
# GACHA SYSTEM CONFIGURATION
# ═══════════════════════════════════════════════════════════════

GACHA_RARITY_TIERS = {
    "common": {"weight": 50, "color": 0x9E9E9E, "stars": 1, "emoji": "⚪"},
    "uncommon": {"weight": 25, "color": 0x4CAF50, "stars": 2, "emoji": "🟢"},
    "rare": {"weight": 15, "color": 0x2196F3, "stars": 3, "emoji": "🔵"},
    "epic": {"weight": 7, "color": 0x9C27B0, "stars": 4, "emoji": "🟣"},
    "legendary": {"weight": 3, "color": 0xFFD700, "stars": 5, "emoji": "🌟"},
}

GACHA_COST = 50  # Cost per draw
GACHA_CARDS_PER_DRAW = 3  # Cards shown per draw
GACHA_CLAIM_TIMEOUT = 30  # Seconds to claim

# Slot machine colors
SLOT_BG_COLOR = (30, 30, 40)
SLOT_FRAME_COLOR = (255, 215, 0)  # Gold
SLOT_REEL_BG = (20, 20, 30)
SLOT_TEXT_COLOR = (255, 255, 255)

# Slot symbol images (emoji text fallback)
SLOT_SYMBOL_COLORS = {
    "🍒": (220, 20, 60),   # Cherry - Red
    "🍋": (255, 255, 0),   # Lemon - Yellow
    "🍊": (255, 165, 0),   # Orange
    "🍇": (128, 0, 128),   # Grape - Purple
    "🔔": (255, 215, 0),   # Bell - Gold
    "⭐": (255, 255, 100), # Star - Yellow
    "💎": (0, 191, 255),   # Diamond - Blue
    "🥜": (139, 69, 19)    # Peanut - Brown
}

# Official Wordle colors (exact from NYT Wordle) + Enhanced UI colors
WORDLE_COLORS = {
    "correct": (83, 141, 78),      # #538D4E - Official green
    "present": (181, 159, 59),     # #B59F3B - Official yellow  
    "absent": (58, 58, 60),        # #3A3A3C - Official dark gray
    "empty": (18, 18, 19),         # #121213 - Empty cell (same as bg)
    "empty_border": (58, 58, 60),  # #3A3A3C - Empty cell border
    "background": (18, 18, 19),    # #121213 - Official dark background
    "text": (255, 255, 255),       # White text
    "header_bg": (32, 32, 34),     # Header background
    "title": (255, 255, 255),      # Title text
    "subtitle": (129, 131, 132),   # #818384 - Muted text
    "status_playing": (66, 135, 245),   # Blue - playing
    "status_won": (83, 141, 78),        # Green - won
    "status_lost": (180, 70, 70),       # Red - lost
    "divider": (62, 62, 64),            # Divider line
    "card_bg": (26, 26, 28),            # Card background
    "accent": (83, 141, 78),            # Accent color (green)
}

WORDLE_CELL_SIZE = 52
WORDLE_CELL_GAP = 5
WORDLE_PADDING = 12

async def fetch_avatar_bytes(session, avatar_url: str, size: int = 64) -> Optional[bytes]:
    """Fetch user avatar and return as bytes."""
    try:
        async with session.get(str(avatar_url)) as resp:
            if resp.status == 200:
                return await resp.read()
    except:
        pass
    return None


def generate_wordle_board_image(attempts: list, word: str, show_word: bool = False, 
                                 avatar_bytes: bytes = None, player_name: str = None) -> io.BytesIO:
    """Generate a Wordle board image using Pillow.
    
    Args:
        attempts: List of dicts with 'word' and 'result' keys
        word: The target word (for calculating results if needed)
        show_word: Whether to reveal the word at the bottom
        avatar_bytes: Optional avatar image bytes to display
        player_name: Optional player name to display
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    rows = 6
    cols = 5
    
    # Calculate dimensions - add space for avatar header if provided
    header_height = 70 if avatar_bytes or player_name else 0
    width = WORDLE_PADDING * 2 + cols * WORDLE_CELL_SIZE + (cols - 1) * WORDLE_CELL_GAP
    height = WORDLE_PADDING * 2 + rows * WORDLE_CELL_SIZE + (rows - 1) * WORDLE_CELL_GAP + header_height
    if show_word:
        height += 40  # Extra space for revealed word
    
    # Create image
    img = Image.new('RGB', (width, height), WORDLE_COLORS["background"])
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, fallback to default
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            font = ImageFont.truetype(str(font_path), 36)
            small_font = ImageFont.truetype(str(font_path), 20)
            name_font = ImageFont.truetype(str(font_path), 18)
        else:
            font = ImageFont.load_default()
            small_font = font
            name_font = font
    except:
        font = ImageFont.load_default()
        small_font = font
        name_font = font
    
    # Draw avatar and player name header if provided
    if avatar_bytes or player_name:
        avatar_size = 50
        avatar_x = WORDLE_PADDING
        avatar_y = 10
        
        # Draw avatar if available
        if avatar_bytes:
            try:
                avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                
                # Create circular mask
                mask = Image.new('L', (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                
                # Apply circular mask
                output = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
                output.paste(avatar_img, (0, 0), mask)
                
                # Paste onto main image
                img.paste(output, (avatar_x, avatar_y), output)
            except:
                pass
        
        # Draw player name
        if player_name:
            name_x = avatar_x + avatar_size + 10 if avatar_bytes else WORDLE_PADDING
            name_y = avatar_y + (avatar_size - 20) // 2 if avatar_bytes else 25
            draw.text((name_x, name_y), player_name[:20], fill=WORDLE_COLORS["text"], font=name_font)
    
    # Draw grid (offset by header height)
    grid_offset_y = header_height
    for row in range(rows):
        for col in range(cols):
            x = WORDLE_PADDING + col * (WORDLE_CELL_SIZE + WORDLE_CELL_GAP)
            y = WORDLE_PADDING + row * (WORDLE_CELL_SIZE + WORDLE_CELL_GAP) + grid_offset_y
            
            # Determine cell color and letter
            if row < len(attempts):
                attempt = attempts[row]
                letter = attempt["word"][col] if col < len(attempt["word"]) else ""
                result_char = attempt["result"][col] if col < len(attempt["result"]) else "⬜"
                
                if result_char == "🟩":
                    color = WORDLE_COLORS["correct"]
                elif result_char == "🟨":
                    color = WORDLE_COLORS["present"]
                else:
                    color = WORDLE_COLORS["absent"]
            else:
                letter = ""
                color = WORDLE_COLORS["empty"]
            
            # Draw cell - official Wordle style (no outline for colored cells)
            if color == WORDLE_COLORS["empty"]:
                # Empty cells have border
                draw.rectangle(
                    [x, y, x + WORDLE_CELL_SIZE, y + WORDLE_CELL_SIZE],
                    fill=color,
                    outline=WORDLE_COLORS["empty_border"],
                    width=2
                )
            else:
                # Colored cells have no border (official style)
                draw.rectangle(
                    [x, y, x + WORDLE_CELL_SIZE, y + WORDLE_CELL_SIZE],
                    fill=color
                )
            
            # Draw letter
            if letter:
                bbox = draw.textbbox((0, 0), letter, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = x + (WORDLE_CELL_SIZE - text_width) // 2
                text_y = y + (WORDLE_CELL_SIZE - text_height) // 2 - 5
                draw.text((text_x, text_y), letter, fill=WORDLE_COLORS["text"], font=font)
    
    # Show revealed word if game over
    if show_word:
        text = f"Word: {word}"
        bbox = draw.textbbox((0, 0), text, font=small_font)
        text_width = bbox[2] - bbox[0]
        text_x = (width - text_width) // 2
        text_y = height - 35
        draw.text((text_x, text_y), text, fill=WORDLE_COLORS["text"], font=small_font)
    
    # Save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def generate_wordle_live_image(players_data: dict, bot, title: str = "WORDLE", game_status: str = "live") -> io.BytesIO:
    """Generate a professional multiplayer Wordle leaderboard image.
    
    Args:
        players_data: Dict of user_id -> player data with attempts
        bot: Bot instance to fetch usernames
        title: Game title to display
        game_status: "live", "ended", or custom status text
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    # Try to load fonts
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            title_font = ImageFont.truetype(str(font_path), 24)
            status_font = ImageFont.truetype(str(font_path), 12)
            name_font = ImageFont.truetype(str(font_path), 13)
            cell_font = ImageFont.truetype(str(font_path), 18)
            attempts_font = ImageFont.truetype(str(font_path), 10)
        else:
            title_font = name_font = cell_font = status_font = attempts_font = ImageFont.load_default()
    except:
        title_font = name_font = cell_font = status_font = attempts_font = ImageFont.load_default()
    
    if not players_data:
        img = Image.new('RGB', (320, 120), WORDLE_COLORS["background"])
        draw = ImageDraw.Draw(img)
        draw.text((120, 50), "Waiting for players...", fill=WORDLE_COLORS["subtitle"], font=name_font)
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
    
    # Layout constants
    title_height = 50
    player_card_height = 52
    card_padding = 8
    mini_cell = 32
    mini_gap = 3
    grid_width = 5 * mini_cell + 4 * mini_gap
    card_width = grid_width + 120  # Extra space for avatar + name + status
    
    num_players = len(players_data)
    total_width = card_width + 40
    total_height = title_height + (player_card_height + card_padding) * num_players + 20
    
    # Create image
    img = Image.new('RGB', (total_width, total_height), WORDLE_COLORS["background"])
    draw = ImageDraw.Draw(img)
    
    # Draw title header
    draw.rectangle([0, 0, total_width, title_height], fill=WORDLE_COLORS["header_bg"])
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_x = (total_width - (title_bbox[2] - title_bbox[0])) // 2
    draw.text((title_x, 12), title, fill=WORDLE_COLORS["text"], font=title_font)
    
    # Status indicator (LIVE dot or ENDED)
    if game_status == "live":
        status_text = "LIVE"
        status_color = (255, 80, 80)  # Red dot
        # Draw pulsing dot
        draw.ellipse([total_width - 55, 20, total_width - 45, 30], fill=status_color)
        draw.text((total_width - 42, 18), status_text, fill=status_color, font=status_font)
    elif game_status == "ended":
        status_text = "ENDED"
        draw.text((total_width - 55, 18), status_text, fill=WORDLE_COLORS["subtitle"], font=status_font)
    
    # Draw player count
    player_count = f"{num_players} player{'s' if num_players != 1 else ''}"
    draw.text((15, 18), player_count, fill=WORDLE_COLORS["subtitle"], font=status_font)
    
    # Draw divider line
    draw.line([(10, title_height - 1), (total_width - 10, title_height - 1)], fill=WORDLE_COLORS["divider"], width=1)
    
    # Draw each player card
    for idx, (user_id, player_data) in enumerate(players_data.items()):
        card_y = title_height + 10 + idx * (player_card_height + card_padding)
        
        # Card background
        draw.rounded_rectangle(
            [15, card_y, total_width - 15, card_y + player_card_height],
            radius=6,
            fill=WORDLE_COLORS["card_bg"]
        )
        
        # Player status and color
        status = player_data.get("status", "playing")
        if status == "won":
            status_color = WORDLE_COLORS["status_won"]
            status_text = "WON"
            status_icon = "✓"
        elif status == "lost":
            status_color = WORDLE_COLORS["status_lost"]
            status_text = "LOST"
            status_icon = "✗"
        else:
            status_color = WORDLE_COLORS["status_playing"]
            status_text = "PLAYING"
            status_icon = "●"
        
        # Status indicator bar on left
        draw.rectangle([15, card_y, 19, card_y + player_card_height], fill=status_color)
        
        # Avatar
        avatar_size = 36
        avatar_x = 28
        avatar_y = card_y + (player_card_height - avatar_size) // 2
        
        avatar_bytes = player_data.get("avatar_bytes")
        if avatar_bytes:
            try:
                avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert('RGBA')
                avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                
                mask = Image.new('L', (avatar_size, avatar_size), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                
                output = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
                output.paste(avatar_img, (0, 0), mask)
                img.paste(output, (avatar_x, avatar_y), output)
            except:
                # Draw placeholder circle
                draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], 
                           fill=WORDLE_COLORS["empty_border"])
        else:
            draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], 
                       fill=WORDLE_COLORS["empty_border"])
        
        # Player name
        player_name = player_data.get("display_name", f"Player {idx + 1}")
        if len(player_name) > 14:
            player_name = player_name[:12] + ".."
        name_x = avatar_x + avatar_size + 10
        name_y = card_y + 10
        draw.text((name_x, name_y), player_name, fill=WORDLE_COLORS["text"], font=name_font)
        
        # Attempt counter
        attempts = player_data.get("attempts", [])
        attempt_text = f"{len(attempts)}/6"
        draw.text((name_x, name_y + 18), attempt_text, fill=WORDLE_COLORS["subtitle"], font=attempts_font)
        
        # Status badge
        badge_x = name_x + 45
        badge_y = name_y + 16
        draw.text((badge_x, badge_y), status_icon, fill=status_color, font=attempts_font)
        
        # Mini Wordle grid (last row only for compact view, or full mini grid)
        grid_x = total_width - grid_width - 25
        grid_y = card_y + (player_card_height - mini_cell) // 2
        
        # Show last attempt or empty row
        if attempts:
            last_attempt = attempts[-1]
            for col in range(5):
                cell_x = grid_x + col * (mini_cell + mini_gap)
                letter = last_attempt["word"][col] if col < len(last_attempt["word"]) else ""
                result_char = last_attempt["result"][col] if col < len(last_attempt["result"]) else "⬜"
                
                if result_char == "🟩":
                    color = WORDLE_COLORS["correct"]
                elif result_char == "🟨":
                    color = WORDLE_COLORS["present"]
                else:
                    color = WORDLE_COLORS["absent"]
                
                draw.rectangle([cell_x, grid_y, cell_x + mini_cell, grid_y + mini_cell], fill=color)
                
                if letter:
                    bbox = draw.textbbox((0, 0), letter, font=cell_font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                    tx = cell_x + (mini_cell - tw) // 2
                    ty = grid_y + (mini_cell - th) // 2 - 2
                    draw.text((tx, ty), letter, fill=WORDLE_COLORS["text"], font=cell_font)
        else:
            # Empty row
            for col in range(5):
                cell_x = grid_x + col * (mini_cell + mini_gap)
                draw.rectangle(
                    [cell_x, grid_y, cell_x + mini_cell, grid_y + mini_cell],
                    fill=WORDLE_COLORS["empty"],
                    outline=WORDLE_COLORS["empty_border"],
                    width=1
                )
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


async def generate_waiting_room_image(
    game_name: str,
    host_name: str,
    host_avatar_bytes: bytes = None,
    players: list = None,
    max_players: int = 5,
    countdown: int = None,
    extra_info: str = None
) -> io.BytesIO:
    """Generate a visual waiting room image for multiplayer games.
    
    Args:
        game_name: Name of the game (e.g., "WORDLE", "HANGMAN")
        host_name: Display name of the host
        host_avatar_bytes: Host's avatar as bytes
        players: List of dicts with 'name' and 'avatar_bytes' keys
        max_players: Maximum number of players allowed
        countdown: Seconds remaining (optional)
        extra_info: Additional info like word length (optional)
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    players = players or []
    
    # Try to load fonts
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            title_font = ImageFont.truetype(str(font_path), 28)
            subtitle_font = ImageFont.truetype(str(font_path), 14)
            name_font = ImageFont.truetype(str(font_path), 13)
            host_font = ImageFont.truetype(str(font_path), 11)
            countdown_font = ImageFont.truetype(str(font_path), 18)
        else:
            title_font = subtitle_font = name_font = host_font = countdown_font = ImageFont.load_default()
    except:
        title_font = subtitle_font = name_font = host_font = countdown_font = ImageFont.load_default()
    
    # Layout constants
    header_height = 80
    player_slot_size = 70
    player_slot_gap = 12
    footer_height = 50
    padding = 20
    
    # Calculate dimensions
    slots_width = max_players * player_slot_size + (max_players - 1) * player_slot_gap
    total_width = max(slots_width + padding * 2, 380)
    total_height = header_height + player_slot_size + 40 + footer_height
    
    # Create image
    img = Image.new('RGB', (total_width, total_height), WORDLE_COLORS["background"])
    draw = ImageDraw.Draw(img)
    
    # Header background
    draw.rectangle([0, 0, total_width, header_height], fill=WORDLE_COLORS["header_bg"])
    
    # Game title
    title_bbox = draw.textbbox((0, 0), game_name, font=title_font)
    title_x = (total_width - (title_bbox[2] - title_bbox[0])) // 2
    draw.text((title_x, 12), game_name, fill=WORDLE_COLORS["text"], font=title_font)
    
    # Host section
    host_avatar_size = 28
    host_section_y = 48
    
    # Draw host avatar
    host_x = (total_width - 150) // 2
    if host_avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(host_avatar_bytes)).convert('RGBA')
            avatar_img = avatar_img.resize((host_avatar_size, host_avatar_size), Image.Resampling.LANCZOS)
            
            mask = Image.new('L', (host_avatar_size, host_avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, host_avatar_size, host_avatar_size), fill=255)
            
            output = Image.new('RGBA', (host_avatar_size, host_avatar_size), (0, 0, 0, 0))
            output.paste(avatar_img, (0, 0), mask)
            img.paste(output, (host_x, host_section_y), output)
        except:
            draw.ellipse([host_x, host_section_y, host_x + host_avatar_size, host_section_y + host_avatar_size],
                        fill=WORDLE_COLORS["empty_border"])
    else:
        draw.ellipse([host_x, host_section_y, host_x + host_avatar_size, host_section_y + host_avatar_size],
                    fill=WORDLE_COLORS["empty_border"])
    
    # Host name and "is hosting" text
    host_text = f"{host_name[:15]} is hosting"
    draw.text((host_x + host_avatar_size + 8, host_section_y + 6), host_text, 
              fill=WORDLE_COLORS["subtitle"], font=host_font)
    
    # Divider
    draw.line([(padding, header_height - 1), (total_width - padding, header_height - 1)], 
              fill=WORDLE_COLORS["divider"], width=1)
    
    # Player slots section
    slots_start_x = (total_width - slots_width) // 2
    slots_y = header_height + 20
    
    for i in range(max_players):
        slot_x = slots_start_x + i * (player_slot_size + player_slot_gap)
        
        if i < len(players):
            # Filled slot
            player = players[i]
            
            # Slot background (filled)
            draw.rounded_rectangle(
                [slot_x, slots_y, slot_x + player_slot_size, slots_y + player_slot_size],
                radius=8,
                fill=WORDLE_COLORS["card_bg"]
            )
            
            # Green border for joined player
            draw.rounded_rectangle(
                [slot_x, slots_y, slot_x + player_slot_size, slots_y + player_slot_size],
                radius=8,
                outline=WORDLE_COLORS["status_won"],
                width=2
            )
            
            # Player avatar
            avatar_size = 36
            avatar_x = slot_x + (player_slot_size - avatar_size) // 2
            avatar_y = slots_y + 8
            
            if player.get("avatar_bytes"):
                try:
                    p_avatar = Image.open(io.BytesIO(player["avatar_bytes"])).convert('RGBA')
                    p_avatar = p_avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                    
                    mask = Image.new('L', (avatar_size, avatar_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                    
                    output = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
                    output.paste(p_avatar, (0, 0), mask)
                    img.paste(output, (avatar_x, avatar_y), output)
                except:
                    draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size],
                               fill=WORDLE_COLORS["status_playing"])
            else:
                draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size],
                           fill=WORDLE_COLORS["status_playing"])
            
            # Player name (truncated)
            p_name = player.get("name", "Player")[:8]
            name_bbox = draw.textbbox((0, 0), p_name, font=name_font)
            name_w = name_bbox[2] - name_bbox[0]
            name_x = slot_x + (player_slot_size - name_w) // 2
            draw.text((name_x, slots_y + 48), p_name, fill=WORDLE_COLORS["text"], font=name_font)
        else:
            # Empty slot
            draw.rounded_rectangle(
                [slot_x, slots_y, slot_x + player_slot_size, slots_y + player_slot_size],
                radius=8,
                fill=WORDLE_COLORS["empty"],
                outline=WORDLE_COLORS["empty_border"],
                width=2
            )
            
            # "?" placeholder
            q_bbox = draw.textbbox((0, 0), "?", font=title_font)
            q_w = q_bbox[2] - q_bbox[0]
            q_x = slot_x + (player_slot_size - q_w) // 2
            draw.text((q_x, slots_y + 18), "?", fill=WORDLE_COLORS["empty_border"], font=title_font)
    
    # Footer section
    footer_y = slots_y + player_slot_size + 15
    
    # Player count
    count_text = f"{len(players)}/{max_players} players"
    draw.text((padding, footer_y + 5), count_text, fill=WORDLE_COLORS["subtitle"], font=subtitle_font)
    
    # Extra info (like word length)
    if extra_info:
        info_bbox = draw.textbbox((0, 0), extra_info, font=subtitle_font)
        info_x = (total_width - (info_bbox[2] - info_bbox[0])) // 2
        draw.text((info_x, footer_y + 5), extra_info, fill=WORDLE_COLORS["subtitle"], font=subtitle_font)
    
    # Countdown
    if countdown is not None:
        cd_text = f"{countdown}s"
        cd_bbox = draw.textbbox((0, 0), cd_text, font=countdown_font)
        circle_size = 32
        circle_x = total_width - padding - circle_size
        circle_y = footer_y
        draw.ellipse([circle_x, circle_y, circle_x + circle_size, circle_y + circle_size],
                    outline=WORDLE_COLORS["status_playing"], width=2)
        cd_text_x = circle_x + (circle_size - (cd_bbox[2] - cd_bbox[0])) // 2
        cd_text_y = circle_y + (circle_size - (cd_bbox[3] - cd_bbox[1])) // 2 - 2
        draw.text((cd_text_x, cd_text_y), cd_text, fill=WORDLE_COLORS["status_playing"], font=countdown_font)
    
    # "Click to join" text at bottom
    join_text = "Click Join Game to play!"
    join_bbox = draw.textbbox((0, 0), join_text, font=host_font)
    join_x = (total_width - (join_bbox[2] - join_bbox[0])) // 2
    draw.text((join_x, footer_y + 25), join_text, fill=WORDLE_COLORS["accent"], font=host_font)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# CARD DRAW IMAGE GENERATOR
# ═══════════════════════════════════════════════════════════════

RARITY_CARD_COLORS = {
    "common": {"border": (169, 169, 169), "glow": (100, 100, 100), "stars": 1},
    "uncommon": {"border": (76, 175, 80), "glow": (56, 142, 60), "stars": 2},
    "rare": {"border": (33, 150, 243), "glow": (25, 118, 210), "stars": 3},
    "epic": {"border": (156, 39, 176), "glow": (123, 31, 162), "stars": 4},
    "legendary": {"border": (255, 193, 7), "glow": (255, 160, 0), "stars": 5},
}

async def generate_card_image(
    name: str,
    subtitle: str,
    rarity: str,
    sprite_url: str = None,
    multiplier: int = 1,
    card_type: str = "pokemon"
) -> io.BytesIO:
    """Generate a gacha card image with rarity border.
    
    Args:
        name: Character/Pokemon name
        subtitle: Type or anime name
        rarity: Rarity level (common, uncommon, rare, epic, legendary)
        sprite_url: URL to sprite/image
        multiplier: Reward multiplier
        card_type: "pokemon" or "anime"
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    card_width = 200
    card_height = 280
    border_width = 6
    
    rarity_data = RARITY_CARD_COLORS.get(rarity, RARITY_CARD_COLORS["common"])
    border_color = rarity_data["border"]
    glow_color = rarity_data["glow"]
    stars = rarity_data["stars"]
    
    # Create card
    img = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            name_font = ImageFont.truetype(str(font_path), 16)
            sub_font = ImageFont.truetype(str(font_path), 12)
            star_font = ImageFont.truetype(str(font_path), 18)
            mult_font = ImageFont.truetype(str(font_path), 14)
        else:
            name_font = sub_font = star_font = mult_font = ImageFont.load_default()
    except:
        name_font = sub_font = star_font = mult_font = ImageFont.load_default()
    
    # Draw outer glow/border
    draw.rounded_rectangle(
        [0, 0, card_width - 1, card_height - 1],
        radius=12,
        fill=glow_color,
        outline=border_color,
        width=border_width
    )
    
    # Inner card background
    inner_margin = border_width + 4
    draw.rounded_rectangle(
        [inner_margin, inner_margin, card_width - inner_margin - 1, card_height - inner_margin - 1],
        radius=8,
        fill=(30, 30, 35)
    )
    
    # Stars at top
    star_text = "⭐" * stars
    star_bbox = draw.textbbox((0, 0), star_text, font=star_font)
    star_x = (card_width - (star_bbox[2] - star_bbox[0])) // 2
    draw.text((star_x, inner_margin + 8), star_text, fill=(255, 215, 0), font=star_font)
    
    # Sprite area
    sprite_y = inner_margin + 35
    sprite_size = 100
    sprite_x = (card_width - sprite_size) // 2
    
    # Draw sprite placeholder or fetch sprite
    if sprite_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(sprite_url) as resp:
                    if resp.status == 200:
                        sprite_data = await resp.read()
                        sprite_img = Image.open(io.BytesIO(sprite_data)).convert('RGBA')
                        sprite_img = sprite_img.resize((sprite_size, sprite_size), Image.Resampling.LANCZOS)
                        img.paste(sprite_img, (sprite_x, sprite_y), sprite_img)
        except:
            # Draw placeholder
            draw.ellipse([sprite_x + 20, sprite_y + 20, sprite_x + sprite_size - 20, sprite_y + sprite_size - 20],
                        fill=(50, 50, 55))
    else:
        draw.ellipse([sprite_x + 20, sprite_y + 20, sprite_x + sprite_size - 20, sprite_y + sprite_size - 20],
                    fill=(50, 50, 55))
    
    # Name
    name_y = sprite_y + sprite_size + 15
    # Truncate name if too long
    display_name = name[:18] + ".." if len(name) > 20 else name
    name_bbox = draw.textbbox((0, 0), display_name, font=name_font)
    name_x = (card_width - (name_bbox[2] - name_bbox[0])) // 2
    draw.text((name_x, name_y), display_name, fill=(255, 255, 255), font=name_font)
    
    # Subtitle (type or anime)
    sub_y = name_y + 22
    display_sub = subtitle[:25] + ".." if len(subtitle) > 27 else subtitle
    sub_bbox = draw.textbbox((0, 0), display_sub, font=sub_font)
    sub_x = (card_width - (sub_bbox[2] - sub_bbox[0])) // 2
    draw.text((sub_x, sub_y), display_sub, fill=(150, 150, 150), font=sub_font)
    
    # Rarity badge
    rarity_y = sub_y + 25
    rarity_text = rarity.upper()
    rarity_bbox = draw.textbbox((0, 0), rarity_text, font=sub_font)
    rarity_w = rarity_bbox[2] - rarity_bbox[0]
    rarity_x = (card_width - rarity_w) // 2
    
    # Badge background
    badge_padding = 8
    draw.rounded_rectangle(
        [rarity_x - badge_padding, rarity_y - 3, rarity_x + rarity_w + badge_padding, rarity_y + 15],
        radius=4,
        fill=border_color
    )
    draw.text((rarity_x, rarity_y), rarity_text, fill=(255, 255, 255), font=sub_font)
    
    # Multiplier badge at bottom
    if multiplier > 1:
        mult_text = f"×{multiplier}"
        mult_bbox = draw.textbbox((0, 0), mult_text, font=mult_font)
        mult_x = card_width - inner_margin - (mult_bbox[2] - mult_bbox[0]) - 10
        mult_y = card_height - inner_margin - 25
        draw.text((mult_x, mult_y), mult_text, fill=(255, 215, 0), font=mult_font)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# GACHA MULTI-CARD DRAW IMAGE - PREMIUM DESIGN
# ═══════════════════════════════════════════════════════════════

# Rarity frame materials - realistic metallic/wood textures
RARITY_FRAMES = {
    # Common = Rustic Wood
    "common": {
        "base": (92, 72, 52),      # Dark wood
        "highlight": (138, 110, 78),  # Light wood grain
        "shadow": (58, 44, 30),    # Wood shadow
        "accent": (110, 88, 62),   # Mid wood
        "banner": (72, 56, 40),    # Dark wood banner
        "text": (220, 200, 170),   # Cream text
    },
    # Uncommon = Bronze
    "uncommon": {
        "base": (140, 100, 55),    # Bronze base
        "highlight": (195, 155, 95),  # Bronze shine
        "shadow": (95, 65, 35),    # Bronze shadow
        "accent": (165, 125, 70),  # Bronze mid
        "banner": (110, 78, 45),   # Dark bronze
        "text": (255, 235, 200),   # Warm cream
    },
    # Rare = Silver
    "rare": {
        "base": (160, 165, 175),   # Silver base
        "highlight": (220, 225, 235),  # Silver shine
        "shadow": (100, 105, 115), # Silver shadow
        "accent": (185, 190, 200), # Silver mid
        "banner": (120, 125, 135), # Dark silver
        "text": (255, 255, 255),   # White text
    },
    # Epic = Gold
    "epic": {
        "base": (200, 160, 50),    # Gold base
        "highlight": (255, 220, 100),  # Gold shine
        "shadow": (140, 100, 20),  # Gold shadow
        "accent": (225, 185, 70),  # Gold mid
        "banner": (160, 120, 30),  # Dark gold
        "text": (255, 250, 220),   # Warm white
    },
    # Legendary = Platinum/Diamond
    "legendary": {
        "base": (200, 210, 225),   # Platinum base
        "highlight": (255, 255, 255),  # Pure white shine
        "shadow": (140, 150, 170), # Platinum shadow
        "accent": (225, 235, 250), # Platinum mid
        "banner": (170, 180, 200), # Dark platinum
        "text": (255, 255, 255),   # White text
        "sparkle": True,           # Special sparkle effect
    },
}

async def generate_gacha_draw_image(characters: list, claimed_indices: list = None, ownership_info: dict = None) -> io.BytesIO:
    """Generate hyper-realistic anime gacha cards with ownership display.
    
    Args:
        characters: List of dicts with name, anime, image_url, rarity, gender
        claimed_indices: List of indices that have been claimed (greyed out)
        ownership_info: Dict mapping index to owner info {user_id, username, avatar_url}
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    if claimed_indices is None:
        claimed_indices = []
    if ownership_info is None:
        ownership_info = {}
    
    card_width = 200
    card_height = 300
    padding = 20
    num_cards = len(characters)
    
    total_width = (card_width * num_cards) + (padding * (num_cards + 1))
    total_height = card_height + 40  # compact (no title/footer)
    
    # Transparent background
    img = Image.new('RGBA', (total_width, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            title_font = ImageFont.truetype(str(font_path), 22)
            name_font = ImageFont.truetype(str(font_path), 14)
            small_font = ImageFont.truetype(str(font_path), 11)
            number_font = ImageFont.truetype(str(font_path), 28)
        else:
            title_font = name_font = small_font = number_font = ImageFont.load_default()
    except:
        title_font = name_font = small_font = number_font = ImageFont.load_default()
    
    # Fetch all images first (character images + owner avatars)
    char_images = []
    owner_avatars = {}
    
    async with aiohttp.ClientSession() as session:
        # Fetch character images
        for char in characters:
            char_img = None
            if char.get("image_url"):
                try:
                    async with session.get(char["image_url"]) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            char_img = Image.open(io.BytesIO(img_data)).convert('RGBA')
                except:
                    pass
            char_images.append(char_img)
        
        # Fetch owner avatars
        for idx, owner_data in ownership_info.items():
            if owner_data.get("avatar_url"):
                try:
                    async with session.get(owner_data["avatar_url"]) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            avatar = Image.open(io.BytesIO(img_data)).convert('RGBA')
                            avatar = avatar.resize((36, 36), Image.Resampling.LANCZOS)
                            # Make circular
                            mask = Image.new('L', (36, 36), 0)
                            mask_draw = ImageDraw.Draw(mask)
                            mask_draw.ellipse([0, 0, 35, 35], fill=255)
                            avatar.putalpha(mask)
                            owner_avatars[idx] = avatar
                except:
                    pass
    
    # Draw each card - clean design with rarity shown through frame only
    for i, char in enumerate(characters):
        card_x = padding + i * (card_width + padding)
        card_y = 50
        
        rarity = char.get("rarity", "common")
        frame = RARITY_FRAMES.get(rarity, RARITY_FRAMES["common"])
        
        is_claimed = i in claimed_indices
        is_owned = i in ownership_info
        
        # Create card canvas
        card_bg = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_bg)
        
        # === HYPER-APPEALING FRAME DESIGN ===
        if is_claimed:
            # Greyed out
            card_draw.rounded_rectangle([0, 0, card_width - 1, card_height - 1], radius=8, fill=(45, 45, 50), outline=(65, 65, 70), width=3)
        else:
            # Material-based frame (Wood/Bronze/Silver/Gold/Platinum)
            base = frame["base"]
            highlight = frame["highlight"]
            shadow = frame["shadow"]
            accent = frame["accent"]
            
            # Outer frame - thick material border
            card_draw.rounded_rectangle([0, 0, card_width - 1, card_height - 1], radius=8, fill=base, outline=shadow, width=3)
            
            # Inner highlight (metallic shine effect)
            card_draw.rounded_rectangle([3, 3, card_width - 4, card_height - 4], radius=6, outline=highlight, width=2)
            
            # Accent line (depth)
            card_draw.rounded_rectangle([6, 6, card_width - 7, card_height - 7], radius=5, outline=accent, width=1)
            
            # Corner embellishments for epic/legendary
            if rarity in ["legendary", "epic"]:
                # Top corners - triangular accents
                card_draw.polygon([(3, 3), (20, 3), (3, 20)], fill=highlight)
                card_draw.polygon([(card_width - 4, 3), (card_width - 21, 3), (card_width - 4, 20)], fill=highlight)
                # Bottom corners
                card_draw.polygon([(3, card_height - 4), (20, card_height - 4), (3, card_height - 21)], fill=highlight)
                card_draw.polygon([(card_width - 4, card_height - 4), (card_width - 21, card_height - 4), (card_width - 4, card_height - 21)], fill=highlight)
            
            # Sparkle effect for legendary
            if frame.get("sparkle"):
                sparkle_positions = [(15, 15), (card_width - 16, 15), (15, card_height - 16), (card_width - 16, card_height - 16)]
                for sx, sy in sparkle_positions:
                    card_draw.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=(255, 255, 255, 200))
                    card_draw.ellipse([sx - 1, sy - 1, sx + 1, sy + 1], fill=(255, 255, 255, 255))
        
        # === NAME BANNER AT TOP ===
        banner_h = 30
        banner_margin = 10
        if not is_claimed:
            # Metallic banner with gradient effect
            card_draw.rounded_rectangle([banner_margin, banner_margin, card_width - banner_margin, banner_margin + banner_h], radius=4, fill=frame["banner"])
            # Shine line at top of banner
            card_draw.line([(banner_margin + 4, banner_margin + 2), (card_width - banner_margin - 4, banner_margin + 2)], fill=(*frame["highlight"], 150), width=1)
            # Shadow line at bottom
            card_draw.line([(banner_margin + 4, banner_margin + banner_h - 2), (card_width - banner_margin - 4, banner_margin + banner_h - 2)], fill=(*frame["shadow"], 100), width=1)
        else:
            card_draw.rounded_rectangle([banner_margin, banner_margin, card_width - banner_margin, banner_margin + banner_h], radius=4, fill=(55, 55, 60))
        
        # Character name in banner
        name = char.get("name", "Unknown")
        if len(name) > 14:
            name = name[:12] + "..."
        name_bbox = card_draw.textbbox((0, 0), name, font=name_font)
        name_x = (card_width - (name_bbox[2] - name_bbox[0])) // 2
        text_color = frame.get("text", (255, 255, 255)) if not is_claimed else (130, 130, 130)
        # Text shadow for depth
        card_draw.text((name_x + 1, banner_margin + 8), name, fill=(0, 0, 0, 80), font=name_font)
        card_draw.text((name_x, banner_margin + 7), name, fill=text_color, font=name_font)
        
        # === CHARACTER IMAGE - Main focus ===
        img_area_x = 8
        img_area_y = 8 + banner_h + 4
        img_area_w = card_width - 16
        img_area_h = card_height - banner_h - 56  # Space for bottom banner
        
        char_img = char_images[i]
        if char_img:
            # Resize to fill (cover art style)
            img_ratio = char_img.width / char_img.height
            target_ratio = img_area_w / img_area_h
            
            if img_ratio > target_ratio:
                new_height = img_area_h
                new_width = int(new_height * img_ratio)
            else:
                new_width = img_area_w
                new_height = int(new_width / img_ratio)
            
            char_img = char_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Center crop
            left = (new_width - img_area_w) // 2
            top = (new_height - img_area_h) // 2
            char_img = char_img.crop((left, top, left + img_area_w, top + img_area_h))
            
            # Pinterest-quality enhancement
            if is_claimed:
                # Desaturate and darken claimed cards
                char_img = char_img.convert('LA').convert('RGBA')
                enhancer = ImageEnhance.Brightness(char_img)
                char_img = enhancer.enhance(0.4)
            elif is_owned:
                # Slight desaturation for owned
                enhancer = ImageEnhance.Color(char_img)
                char_img = enhancer.enhance(0.75)
            else:
                # ENHANCE unclaimed cards - Pinterest quality
                # Boost sharpness
                from PIL import ImageFilter
                char_img = char_img.filter(ImageFilter.SHARPEN)
                
                # Boost contrast for pop
                enhancer = ImageEnhance.Contrast(char_img)
                char_img = enhancer.enhance(1.25)
                
                # Boost color saturation
                enhancer = ImageEnhance.Color(char_img)
                char_img = enhancer.enhance(1.15)
                
                # Slight brightness boost
                enhancer = ImageEnhance.Brightness(char_img)
                char_img = enhancer.enhance(1.05)
            
            # Round corners
            img_mask = Image.new('L', (img_area_w, img_area_h), 0)
            mask_draw = ImageDraw.Draw(img_mask)
            mask_draw.rounded_rectangle([0, 0, img_area_w - 1, img_area_h - 1], radius=4, fill=255)
            char_img.putalpha(img_mask)
            
            card_bg.paste(char_img, (img_area_x, img_area_y), char_img)
        else:
            # Placeholder
            card_draw.rounded_rectangle([img_area_x, img_area_y, img_area_x + img_area_w, img_area_y + img_area_h], radius=4, fill=(40, 40, 45))
            card_draw.text((img_area_x + 75, img_area_y + 80), "?", fill=(70, 70, 80), font=title_font)
        
        # === OWNED BANNER (if owned) ===
        if is_owned and not is_claimed:
            owner = ownership_info[i]
            owner_banner_y = img_area_y + img_area_h - 38
            
            card_draw.rounded_rectangle(
                [img_area_x + 4, owner_banner_y, img_area_x + img_area_w - 4, owner_banner_y + 34],
                radius=4, fill=(0, 0, 0, 200)
            )
            card_draw.rounded_rectangle(
                [img_area_x + 4, owner_banner_y, img_area_x + img_area_w - 4, owner_banner_y + 34],
                radius=4, outline=(255, 80, 80), width=2
            )
            
            # Owner avatar
            if i in owner_avatars:
                card_bg.paste(owner_avatars[i], (img_area_x + 8, owner_banner_y + -1), owner_avatars[i])
            
            card_draw.text((img_area_x + 48, owner_banner_y + 2), "OWNED", fill=(255, 80, 80), font=small_font)
            owner_name = owner.get("username", "Someone")[:10]
            card_draw.text((img_area_x + 48, owner_banner_y + 16), f"by {owner_name}", fill=(180, 180, 180), font=small_font)
        
        # === ANIME NAME BANNER AT BOTTOM ===
        bottom_banner_y = card_height - 42
        banner_margin = 10
        if not is_claimed:
            card_draw.rounded_rectangle([banner_margin, bottom_banner_y, card_width - banner_margin, bottom_banner_y + 26], radius=4, fill=frame["banner"])
            # Shine line
            card_draw.line([(banner_margin + 4, bottom_banner_y + 2), (card_width - banner_margin - 4, bottom_banner_y + 2)], fill=(*frame["highlight"], 120), width=1)
        else:
            card_draw.rounded_rectangle([banner_margin, bottom_banner_y, card_width - banner_margin, bottom_banner_y + 26], radius=4, fill=(55, 55, 60))
        
        anime = char.get("anime", "Unknown")
        if len(anime) > 18:
            anime = anime[:16] + "..."
        anime_bbox = card_draw.textbbox((0, 0), anime, font=small_font)
        anime_x = (card_width - (anime_bbox[2] - anime_bbox[0])) // 2
        anime_text_color = frame.get("text", (220, 220, 220)) if not is_claimed else (120, 120, 120)
        # Text shadow
        card_draw.text((anime_x + 1, bottom_banner_y + 7), anime, fill=(0, 0, 0, 60), font=small_font)
        card_draw.text((anime_x, bottom_banner_y + 6), anime, fill=anime_text_color, font=small_font)
        
        # Paste card onto main image
        img.paste(card_bg, (card_x, card_y), card_bg)
    
    # Save with transparency
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', quality=95)
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# GUESS GAME THERMOMETER IMAGE
# ═══════════════════════════════════════════════════════════════

def generate_guess_thermometer(guesses: list, secret: int, attempts_left: int) -> io.BytesIO:
    """Generate a thermometer/gradient bar showing how close guesses are.
    
    Args:
        guesses: List of guess values
        secret: The secret number
        attempts_left: Remaining attempts
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    width = 400
    height = 100
    bar_height = 30
    
    # Colors
    bg_color = (24, 24, 28)
    cold_color = (66, 135, 245)  # Blue - cold
    warm_color = (255, 193, 7)   # Yellow - warm
    hot_color = (244, 67, 54)    # Red - hot
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load font
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            font = ImageFont.truetype(str(font_path), 14)
            small_font = ImageFont.truetype(str(font_path), 11)
        else:
            font = ImageFont.load_default()
            small_font = font
    except:
        font = ImageFont.load_default()
        small_font = font
    
    # Draw gradient bar
    bar_y = 35
    bar_x = 20
    bar_width = width - 40
    
    for x in range(bar_width):
        # Create gradient from cold (blue) -> warm (yellow) -> hot (red)
        progress = x / bar_width
        if progress < 0.5:
            # Blue to Yellow
            t = progress * 2
            r = int(cold_color[0] + (warm_color[0] - cold_color[0]) * t)
            g = int(cold_color[1] + (warm_color[1] - cold_color[1]) * t)
            b = int(cold_color[2] + (warm_color[2] - cold_color[2]) * t)
        else:
            # Yellow to Red
            t = (progress - 0.5) * 2
            r = int(warm_color[0] + (hot_color[0] - warm_color[0]) * t)
            g = int(warm_color[1] + (hot_color[1] - warm_color[1]) * t)
            b = int(warm_color[2] + (hot_color[2] - warm_color[2]) * t)
        
        draw.line([(bar_x + x, bar_y), (bar_x + x, bar_y + bar_height)], fill=(r, g, b))
    
    # Draw markers for 1, 50, 100
    for val, label in [(1, "1"), (50, "50"), (100, "100")]:
        x_pos = bar_x + int((val - 1) / 99 * bar_width)
        draw.line([(x_pos, bar_y + bar_height), (x_pos, bar_y + bar_height + 5)], fill=(255, 255, 255), width=1)
        bbox = draw.textbbox((0, 0), label, font=small_font)
        tw = bbox[2] - bbox[0]
        draw.text((x_pos - tw // 2, bar_y + bar_height + 7), label, fill=(150, 150, 150), font=small_font)
    
    # Draw secret position (hidden marker)
    secret_x = bar_x + int((secret - 1) / 99 * bar_width)
    draw.polygon([(secret_x, bar_y - 8), (secret_x - 6, bar_y - 16), (secret_x + 6, bar_y - 16)], 
                fill=(255, 255, 255, 100))
    
    # Draw guess markers
    for i, guess in enumerate(guesses):
        x_pos = bar_x + int((guess - 1) / 99 * bar_width)
        diff = abs(guess - secret)
        
        # Color based on closeness
        if diff <= 5:
            marker_color = hot_color
            temp = "🔥"
        elif diff <= 15:
            marker_color = warm_color
            temp = "🌡️"
        elif diff <= 30:
            marker_color = (255, 140, 0)  # Orange
            temp = "☀️"
        else:
            marker_color = cold_color
            temp = "❄️"
        
        # Draw marker
        draw.ellipse([x_pos - 6, bar_y + bar_height // 2 - 6, x_pos + 6, bar_y + bar_height // 2 + 6], 
                    fill=marker_color, outline=(255, 255, 255), width=2)
        draw.text((x_pos - 3, bar_y + bar_height // 2 - 5), str(i + 1), fill=(255, 255, 255), font=small_font)
    
    # Draw header
    header_text = f"Attempts: {3 - attempts_left}/3"
    draw.text((bar_x, 10), header_text, fill=(200, 200, 200), font=font)
    
    # Temperature indicator for last guess
    if guesses:
        last_guess = guesses[-1]
        diff = abs(last_guess - secret)
        if diff <= 5:
            temp_text = "🔥 HOT!"
        elif diff <= 15:
            temp_text = "🌡️ Warm"
        elif diff <= 30:
            temp_text = "☀️ Getting there"
        else:
            temp_text = "❄️ Cold"
        
        bbox = draw.textbbox((0, 0), temp_text, font=font)
        draw.text((width - bar_x - (bbox[2] - bbox[0]), 10), temp_text, fill=(255, 255, 255), font=font)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def generate_guess_result_image(guesses: list, secret: int, won: bool, winnings: int) -> io.BytesIO:
    """Generate a result image showing the path of guesses.
    
    Args:
        guesses: List of guess values
        secret: The secret number
        won: Whether player won
        winnings: Amount won/lost
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    width = 400
    height = 140
    
    bg_color = (24, 24, 28)
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load font
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            font = ImageFont.truetype(str(font_path), 16)
            big_font = ImageFont.truetype(str(font_path), 24)
            small_font = ImageFont.truetype(str(font_path), 11)
        else:
            font = big_font = small_font = ImageFont.load_default()
    except:
        font = big_font = small_font = ImageFont.load_default()
    
    # Draw title
    title = "🎯 PERFECT!" if won and guesses and guesses[-1] == secret else ("✅ Close!" if winnings > 0 else "💀 Game Over")
    title_color = (255, 215, 0) if won else ((100, 200, 100) if winnings > 0 else (200, 80, 80))
    title_bbox = draw.textbbox((0, 0), title, font=big_font)
    draw.text(((width - (title_bbox[2] - title_bbox[0])) // 2, 10), title, fill=title_color, font=big_font)
    
    # Draw path chart
    chart_y = 50
    chart_height = 50
    chart_x = 30
    chart_width = width - 60
    
    # Background
    draw.rectangle([chart_x, chart_y, chart_x + chart_width, chart_y + chart_height], 
                  fill=(35, 35, 40), outline=(60, 60, 65))
    
    # Draw secret line
    secret_y_norm = (secret - 1) / 99
    secret_y = chart_y + chart_height - int(secret_y_norm * chart_height)
    draw.line([(chart_x, secret_y), (chart_x + chart_width, secret_y)], 
             fill=(83, 141, 78), width=2)
    draw.text((chart_x + chart_width + 5, secret_y - 7), str(secret), fill=(83, 141, 78), font=small_font)
    
    # Draw guess path
    if guesses:
        points = []
        for i, guess in enumerate(guesses):
            x = chart_x + int((i / max(len(guesses) - 1, 1)) * chart_width) if len(guesses) > 1 else chart_x + chart_width // 2
            y_norm = (guess - 1) / 99
            y = chart_y + chart_height - int(y_norm * chart_height)
            points.append((x, y))
        
        # Draw lines between points
        if len(points) > 1:
            draw.line(points, fill=(66, 135, 245), width=2)
        
        # Draw points
        for i, (x, y) in enumerate(points):
            draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(66, 135, 245), outline=(255, 255, 255), width=2)
    
    # Draw result
    result_text = f"Answer: {secret} | Result: {winnings:+,} pts"
    result_bbox = draw.textbbox((0, 0), result_text, font=font)
    draw.text(((width - (result_bbox[2] - result_bbox[0])) // 2, height - 25), result_text, 
             fill=(200, 200, 200), font=font)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# PROFILE CARD IMAGE GENERATOR
# ═══════════════════════════════════════════════════════════════

async def generate_profile_card(
    user_name: str,
    avatar_url: str,
    balance: int,
    job_title: str = None,
    job_emoji: str = "💼",
    daily_streak: int = 0,
    total_games: int = 0,
    total_earned: int = 0
) -> io.BytesIO:
    """Generate a profile card image.
    
    Args:
        user_name: User's display name
        avatar_url: URL to user's avatar
        balance: Current stella points balance
        job_title: Current job title
        job_emoji: Job emoji
        daily_streak: Current daily claim streak
        total_games: Total games played
        total_earned: Total points earned lifetime
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    width = 400
    height = 200
    
    # Colors
    bg_color = (24, 24, 28)
    card_bg = (35, 35, 40)
    accent = (88, 101, 242)  # Discord blurple
    gold = (255, 193, 7)
    text_color = (255, 255, 255)
    subtitle_color = (150, 150, 160)
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load fonts
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            name_font = ImageFont.truetype(str(font_path), 20)
            stat_font = ImageFont.truetype(str(font_path), 14)
            small_font = ImageFont.truetype(str(font_path), 11)
            big_font = ImageFont.truetype(str(font_path), 24)
        else:
            name_font = stat_font = small_font = big_font = ImageFont.load_default()
    except:
        name_font = stat_font = small_font = big_font = ImageFont.load_default()
    
    # Draw card background
    draw.rounded_rectangle([10, 10, width - 10, height - 10], radius=12, fill=card_bg)
    
    # Draw accent bar at top
    draw.rectangle([10, 10, width - 10, 50], fill=accent)
    draw.rounded_rectangle([10, 10, width - 10, 55], radius=12, fill=accent)
    draw.rectangle([10, 45, width - 10, 55], fill=accent)
    
    # Fetch and draw avatar
    avatar_size = 70
    avatar_x = 25
    avatar_y = 25
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    avatar = Image.open(io.BytesIO(data)).convert('RGBA')
                    avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                    
                    # Make circular with border
                    mask = Image.new('L', (avatar_size, avatar_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                    
                    output = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
                    output.paste(avatar, (0, 0), mask)
                    
                    # Draw border
                    draw.ellipse([avatar_x - 3, avatar_y - 3, avatar_x + avatar_size + 3, avatar_y + avatar_size + 3],
                               outline=(255, 255, 255), width=3)
                    
                    img.paste(output, (avatar_x, avatar_y), output)
    except:
        draw.ellipse([avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size], fill=(60, 60, 65))
    
    # Draw username
    name_x = avatar_x + avatar_size + 15
    name_y = 30
    draw.text((name_x, name_y), user_name[:20], fill=text_color, font=name_font)
    
    # Draw job under name
    if job_title:
        job_text = f"{job_emoji} {job_title}"
    else:
        job_text = "💼 Unemployed"
    draw.text((name_x, name_y + 25), job_text, fill=subtitle_color, font=small_font)
    
    # Stats section
    stats_y = 110
    stat_width = (width - 40) // 3
    
    # Balance (centered, larger)
    balance_text = f"💰 {balance:,}"
    balance_bbox = draw.textbbox((0, 0), balance_text, font=big_font)
    balance_x = (width - (balance_bbox[2] - balance_bbox[0])) // 2
    draw.text((balance_x, stats_y - 30), balance_text, fill=gold, font=big_font)
    draw.text((balance_x, stats_y - 5), "Stella Points", fill=subtitle_color, font=small_font)
    
    # Stats row
    stats = [
        ("🔥", f"{daily_streak}", "Streak"),
        ("🎮", f"{total_games:,}", "Games"),
        ("📈", f"{total_earned:,}", "Earned"),
    ]
    
    for i, (emoji, value, label) in enumerate(stats):
        stat_x = 20 + i * stat_width + stat_width // 2
        
        # Value
        stat_text = f"{emoji} {value}"
        stat_bbox = draw.textbbox((0, 0), stat_text, font=stat_font)
        text_x = stat_x - (stat_bbox[2] - stat_bbox[0]) // 2
        draw.text((text_x, stats_y + 30), stat_text, fill=text_color, font=stat_font)
        
        # Label
        label_bbox = draw.textbbox((0, 0), label, font=small_font)
        label_x = stat_x - (label_bbox[2] - label_bbox[0]) // 2
        draw.text((label_x, stats_y + 50), label, fill=subtitle_color, font=small_font)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# PAYCHECK IMAGE GENERATOR (Work)
# ═══════════════════════════════════════════════════════════════

def generate_paycheck_image(
    job_title: str,
    job_emoji: str,
    base_pay: int,
    bonus: int = 0,
    overtime: bool = False,
    character_bonus: int = 0
) -> io.BytesIO:
    """Generate a paycheck image for the work command.
    
    Args:
        job_title: Job title
        job_emoji: Job emoji
        base_pay: Base pay amount
        bonus: Any bonus amount
        overtime: Whether this was an overtime shift
        character_bonus: Character-specific bonus
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    width = 350
    height = 180
    
    # Colors
    bg_color = (245, 245, 240)  # Off-white paper
    border_color = (180, 160, 140)
    text_color = (40, 40, 40)
    accent_color = (0, 100, 0) if not overtime else (180, 140, 0)  # Green or gold for overtime
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load font
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            title_font = ImageFont.truetype(str(font_path), 16)
            main_font = ImageFont.truetype(str(font_path), 14)
            small_font = ImageFont.truetype(str(font_path), 11)
            big_font = ImageFont.truetype(str(font_path), 22)
        else:
            title_font = main_font = small_font = big_font = ImageFont.load_default()
    except:
        title_font = main_font = small_font = big_font = ImageFont.load_default()
    
    # Draw border
    draw.rectangle([0, 0, width - 1, height - 1], outline=border_color, width=3)
    
    # Draw decorative lines
    draw.line([(10, 35), (width - 10, 35)], fill=border_color, width=1)
    draw.line([(10, height - 45), (width - 10, height - 45)], fill=border_color, width=1)
    
    # Title
    title = "💵 PAYCHECK" if not overtime else "⭐ OVERTIME PAYCHECK"
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    title_x = (width - (title_bbox[2] - title_bbox[0])) // 2
    draw.text((title_x, 10), title, fill=accent_color, font=title_font)
    
    # Job info
    job_text = f"{job_emoji} {job_title}"
    job_bbox = draw.textbbox((0, 0), job_text, font=main_font)
    job_x = (width - (job_bbox[2] - job_bbox[0])) // 2
    draw.text((job_x, 45), job_text, fill=text_color, font=main_font)
    
    # Pay breakdown
    y_pos = 70
    
    # Base pay
    draw.text((20, y_pos), "Base Pay:", fill=text_color, font=small_font)
    draw.text((width - 80, y_pos), f"{base_pay:,} pts", fill=text_color, font=small_font)
    y_pos += 18
    
    # Bonuses
    if bonus > 0:
        draw.text((20, y_pos), "Task Bonus:", fill=text_color, font=small_font)
        draw.text((width - 80, y_pos), f"+{bonus:,} pts", fill=(0, 128, 0), font=small_font)
        y_pos += 18
    
    if character_bonus > 0:
        draw.text((20, y_pos), "Character Bonus:", fill=text_color, font=small_font)
        draw.text((width - 80, y_pos), f"+{character_bonus:,} pts", fill=(0, 128, 0), font=small_font)
        y_pos += 18
    
    if overtime:
        overtime_bonus = base_pay  # Double pay for overtime
        draw.text((20, y_pos), "Overtime (2x):", fill=text_color, font=small_font)
        draw.text((width - 80, y_pos), f"+{overtime_bonus:,} pts", fill=(180, 140, 0), font=small_font)
    
    # Total
    total = base_pay + bonus + character_bonus + (base_pay if overtime else 0)
    total_text = f"TOTAL: {total:,} pts"
    total_bbox = draw.textbbox((0, 0), total_text, font=big_font)
    total_x = (width - (total_bbox[2] - total_bbox[0])) // 2
    draw.text((total_x, height - 38), total_text, fill=accent_color, font=big_font)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# CRIME SCENE IMAGE GENERATOR (Rob)
# ═══════════════════════════════════════════════════════════════

async def generate_crime_scene_image(
    robber_avatar_url: str,
    victim_avatar_url: str,
    robber_name: str,
    victim_name: str,
    success: bool,
    amount: int
) -> io.BytesIO:
    """Generate a crime scene image for rob command.
    
    Args:
        robber_avatar_url: URL for robber's avatar
        victim_avatar_url: URL for victim's avatar
        robber_name: Robber's display name
        victim_name: Victim's display name
        success: Whether the robbery was successful
        amount: Amount stolen or fined
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    width = 350
    height = 150
    avatar_size = 60
    
    # Colors
    if success:
        bg_color = (25, 45, 25)  # Dark green tint
        accent = (76, 175, 80)
    else:
        bg_color = (45, 25, 25)  # Dark red tint
        accent = (244, 67, 54)
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load font
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            font = ImageFont.truetype(str(font_path), 14)
            small_font = ImageFont.truetype(str(font_path), 11)
            big_font = ImageFont.truetype(str(font_path), 18)
        else:
            font = small_font = big_font = ImageFont.load_default()
    except:
        font = small_font = big_font = ImageFont.load_default()
    
    # Fetch avatars
    async def fetch_avatar(url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        avatar = Image.open(io.BytesIO(data)).convert('RGBA')
                        avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                        
                        # Make circular
                        mask = Image.new('L', (avatar_size, avatar_size), 0)
                        mask_draw = ImageDraw.Draw(mask)
                        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)
                        
                        output = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
                        output.paste(avatar, (0, 0), mask)
                        return output
        except:
            pass
        return None
    
    robber_avatar = await fetch_avatar(robber_avatar_url)
    victim_avatar = await fetch_avatar(victim_avatar_url)
    
    # Positions
    robber_x = 30
    victim_x = width - 30 - avatar_size
    avatar_y = 35
    
    # Draw avatars with borders
    for x, avatar, name in [(robber_x, robber_avatar, robber_name), (victim_x, victim_avatar, victim_name)]:
        # Border
        draw.ellipse([x - 3, avatar_y - 3, x + avatar_size + 3, avatar_y + avatar_size + 3], 
                    outline=accent, width=3)
        
        if avatar:
            img.paste(avatar, (x, avatar_y), avatar)
        else:
            draw.ellipse([x, avatar_y, x + avatar_size, avatar_y + avatar_size], fill=(60, 60, 65))
        
        # Name below
        name_text = name[:10] + ".." if len(name) > 12 else name
        name_bbox = draw.textbbox((0, 0), name_text, font=small_font)
        name_x = x + (avatar_size - (name_bbox[2] - name_bbox[0])) // 2
        draw.text((name_x, avatar_y + avatar_size + 5), name_text, fill=(200, 200, 200), font=small_font)
    
    # Draw money transfer animation in center
    center_x = width // 2
    center_y = height // 2
    
    if success:
        # Money flying from victim to robber
        draw.text((center_x - 20, center_y - 20), "💰", font=big_font, fill=(255, 255, 255))
        draw.text((center_x + 5, center_y - 5), "💵", font=font, fill=(255, 255, 255))
        draw.text((center_x - 10, center_y + 5), "💸", font=font, fill=(255, 255, 255))
        
        # Arrow
        draw.line([(victim_x - 20, center_y), (robber_x + avatar_size + 20, center_y)], 
                 fill=accent, width=3)
        # Arrow head
        draw.polygon([(robber_x + avatar_size + 20, center_y), 
                     (robber_x + avatar_size + 30, center_y - 8),
                     (robber_x + avatar_size + 30, center_y + 8)], fill=accent)
        
        # Amount text
        amount_text = f"+{amount:,}"
    else:
        # Police lights
        draw.text((center_x - 15, center_y - 15), "🚨", font=big_font, fill=(255, 255, 255))
        draw.text((center_x + 10, center_y - 5), "🚔", font=font, fill=(255, 255, 255))
        
        # X mark
        draw.line([(center_x - 25, center_y - 25), (center_x + 25, center_y + 25)], fill=(200, 60, 60), width=4)
        draw.line([(center_x + 25, center_y - 25), (center_x - 25, center_y + 25)], fill=(200, 60, 60), width=4)
        
        # Amount text
        amount_text = f"-{amount:,}"
    
    # Title at top
    title = "ROBBERY SUCCESSFUL!" if success else "CAUGHT!"
    title_bbox = draw.textbbox((0, 0), title, font=big_font)
    title_x = (width - (title_bbox[2] - title_bbox[0])) // 2
    draw.text((title_x, 8), title, fill=accent, font=big_font)
    
    # Amount at bottom
    amount_bbox = draw.textbbox((0, 0), amount_text, font=font)
    amount_x = (width - (amount_bbox[2] - amount_bbox[0])) // 2
    draw.text((amount_x, height - 25), amount_text, fill=accent, font=font)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# DICE ROLLING GIF GENERATOR
# ═══════════════════════════════════════════════════════════════

def generate_dice_gif(result: int) -> io.BytesIO:
    """Generate an animated dice rolling GIF.
    
    Args:
        result: Final dice value (1-6)
    
    Returns:
        BytesIO buffer containing the GIF
    """
    frames = []
    frame_count = 12
    dice_size = 80
    img_size = 120
    
    bg_color = (24, 24, 28)
    dice_color = (255, 255, 255)
    dot_color = (30, 30, 35)
    
    # Dot positions for each face (relative to center, normalized)
    dot_patterns = {
        1: [(0.5, 0.5)],
        2: [(0.25, 0.25), (0.75, 0.75)],
        3: [(0.25, 0.25), (0.5, 0.5), (0.75, 0.75)],
        4: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75)],
        5: [(0.25, 0.25), (0.75, 0.25), (0.5, 0.5), (0.25, 0.75), (0.75, 0.75)],
        6: [(0.25, 0.25), (0.75, 0.25), (0.25, 0.5), (0.75, 0.5), (0.25, 0.75), (0.75, 0.75)]
    }
    
    def draw_dice(draw, x, y, size, value, rotation=0):
        """Draw a dice face with dots"""
        # Draw dice body
        margin = 6
        draw.rounded_rectangle(
            [x, y, x + size, y + size],
            radius=10,
            fill=dice_color,
            outline=(200, 200, 200),
            width=2
        )
        
        # Draw dots
        dot_radius = size // 10
        for dx, dy in dot_patterns.get(value, []):
            dot_x = x + int(dx * size)
            dot_y = y + int(dy * size)
            draw.ellipse(
                [dot_x - dot_radius, dot_y - dot_radius, 
                 dot_x + dot_radius, dot_y + dot_radius],
                fill=dot_color
            )
    
    # Generate rolling frames
    for i in range(frame_count):
        img = Image.new('RGB', (img_size, img_size), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Random dice face for rolling animation (except last 3 frames)
        if i < frame_count - 3:
            face = random.randint(1, 6)
            # Add slight position variation for rolling effect
            offset_x = random.randint(-5, 5)
            offset_y = random.randint(-5, 5)
        else:
            face = result
            offset_x = 0
            offset_y = 0
        
        dice_x = (img_size - dice_size) // 2 + offset_x
        dice_y = (img_size - dice_size) // 2 + offset_y
        
        draw_dice(draw, dice_x, dice_y, dice_size, face)
        frames.append(img)
    
    # Add extra frames at the end showing result
    for _ in range(5):
        frames.append(frames[-1].copy())
    
    # Save as GIF
    buffer = io.BytesIO()
    frames[0].save(
        buffer,
        format='GIF',
        save_all=True,
        append_images=frames[1:],
        duration=70,
        loop=0
    )
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# COINFLIP GIF GENERATOR & VIEW
# ═══════════════════════════════════════════════════════════════

def generate_coinflip_gif(result: str) -> io.BytesIO:
    """Generate an animated coin flip GIF.
    
    Args:
        result: "heads" or "tails"
    
    Returns:
        BytesIO buffer containing the GIF
    """
    frames = []
    frame_count = 10
    coin_size = 120
    img_size = 160
    
    # Colors
    bg_color = (24, 24, 28)
    gold_color = (255, 215, 0)
    gold_dark = (200, 165, 0)
    heads_color = (255, 223, 100)
    tails_color = (192, 192, 210)
    
    # Try to load font
    try:
        font_path = Path(__file__).parent.parent.parent / "data" / "assets" / "fonts" / "arial.ttf"
        if font_path.exists():
            font = ImageFont.truetype(str(font_path), 28)
            small_font = ImageFont.truetype(str(font_path), 14)
        else:
            font = ImageFont.load_default()
            small_font = font
    except:
        font = ImageFont.load_default()
        small_font = font
    
    # Generate spinning frames
    for i in range(frame_count):
        img = Image.new('RGB', (img_size, img_size), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Calculate coin "width" for spin effect (oscillating)
        progress = i / (frame_count - 1)
        
        if i < frame_count - 2:
            # Spinning frames - coin gets thinner/wider
            spin_phase = (i * 2) % 4
            if spin_phase == 0:
                width_factor = 1.0
                side = "H"
                coin_color = heads_color
            elif spin_phase == 1:
                width_factor = 0.3
                side = ""
                coin_color = gold_color
            elif spin_phase == 2:
                width_factor = 1.0
                side = "T"
                coin_color = tails_color
            else:
                width_factor = 0.3
                side = ""
                coin_color = gold_color
        else:
            # Final frames - show result
            width_factor = 1.0
            if result == "heads":
                side = "H"
                coin_color = heads_color
            else:
                side = "T"
                coin_color = tails_color
        
        # Draw coin (ellipse for 3D effect)
        coin_width = int(coin_size * width_factor)
        coin_height = coin_size
        x1 = (img_size - coin_width) // 2
        y1 = (img_size - coin_height) // 2
        x2 = x1 + coin_width
        y2 = y1 + coin_height
        
        # Coin shadow
        shadow_offset = 4
        draw.ellipse([x1 + shadow_offset, y1 + shadow_offset, x2 + shadow_offset, y2 + shadow_offset], 
                    fill=(20, 20, 24))
        
        # Main coin
        draw.ellipse([x1, y1, x2, y2], fill=coin_color, outline=gold_dark, width=3)
        
        # Draw letter on coin if wide enough
        if width_factor > 0.5 and side:
            bbox = draw.textbbox((0, 0), side, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = (img_size - tw) // 2
            ty = (img_size - th) // 2 - 5
            draw.text((tx, ty), side, fill=(60, 50, 30), font=font)
        
        frames.append(img)
    
    # Add extra frames at the end showing result
    for _ in range(5):
        frames.append(frames[-1].copy())
    
    # Save as GIF
    buffer = io.BytesIO()
    frames[0].save(
        buffer,
        format='GIF',
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0
    )
    buffer.seek(0)
    return buffer


class DoubleOrNothingView(discord.ui.View):
    """View for Double or Nothing after winning coinflip"""
    def __init__(self, cog, user_id: str, guild_id: str, winnings: int):
        super().__init__(timeout=30)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.winnings = winnings
        self.used = False
    
    @discord.ui.button(label="Double or Nothing!", style=discord.ButtonStyle.green, emoji="🎲")
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
        
        if self.used:
            return await interaction.response.send_message("❌ Already used!", ephemeral=True)
        
        self.used = True
        self.stop()
        
        # 50/50 chance
        won = random.choice([True, False])
        
        if won:
            new_winnings = self.winnings * 2
            await self.cog.quest_data.add_balance(self.user_id, self.guild_id, self.winnings)
            balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
            
            embed = discord.Embed(
                title="🎉 DOUBLED!",
                description=f"You turned **{self.winnings:,}** into **{new_winnings:,}** pts!",
                color=discord.Color.gold()
            )
            embed.add_field(name="💰 Total Won", value=f"+**{new_winnings:,}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{balance:,}** pts", inline=True)
            
            # Offer another double
            new_view = DoubleOrNothingView(self.cog, self.user_id, self.guild_id, new_winnings)
            await interaction.response.edit_message(embed=embed, view=new_view)
        else:
            await self.cog.quest_data.add_balance(self.user_id, self.guild_id, -self.winnings)
            balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
            
            embed = discord.Embed(
                title="💀 BUSTED!",
                description=f"You lost your **{self.winnings:,}** pts!",
                color=discord.Color.red()
            )
            embed.add_field(name="📉 Lost", value=f"-**{self.winnings:,}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{balance:,}** pts", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.secondary, emoji="💰")
    async def cashout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
        
        if self.used:
            return await interaction.response.send_message("❌ Already cashed out!", ephemeral=True)
        
        self.used = True
        self.stop()
        
        balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
        
        embed = discord.Embed(
            title="💰 Cashed Out!",
            description=f"Smart move! You kept your **{self.winnings:,}** pts.",
            color=discord.Color.green()
        )
        embed.add_field(name="💳 Balance", value=f"**{balance:,}** pts", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def on_timeout(self):
        # Auto cash-out on timeout
        pass


# ═══════════════════════════════════════════════════════════════
# GACHA SYSTEM VIEWS
# ═══════════════════════════════════════════════════════════════

class GachaClaimView(discord.ui.View):
    """View for claiming a character from gacha draw - prevents double claiming"""
    def __init__(self, cog, user: discord.Member, guild_id: str, characters: list, message=None):
        super().__init__(timeout=GACHA_CLAIM_TIMEOUT)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.characters = characters
        self.message = message
        self.claimed = False
        self.claimed_indices = []  # Track which cards have been claimed
    
    async def claim_character(self, interaction: discord.Interaction, index: int):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your draw!", ephemeral=True)
        
        if self.claimed:
            return await interaction.response.send_message("❌ You already claimed a character!", ephemeral=True)
        
        if index in self.claimed_indices:
            return await interaction.response.send_message("❌ This character was already claimed!", ephemeral=True)
        
        if index < 0 or index >= len(self.characters):
            return await interaction.response.send_message("❌ Invalid choice!", ephemeral=True)
        
        self.claimed = True
        self.claimed_indices.append(index)
        self.stop()
        
        char = self.characters[index]
        user_id = str(self.user.id)
        
        # Add to inventory in MongoDB
        await self.cog.add_character_to_inventory(user_id, self.guild_id, char)
        
        # Regenerate image with claimed card marked
        img_buffer = await generate_gacha_draw_image(self.characters, claimed_indices=self.claimed_indices)
        file = discord.File(img_buffer, filename="gacha_claimed.png")
        
        rarity_data = GACHA_RARITY_TIERS.get(char.get("rarity", "common"))
        
        # Update embed to show claim
        embed = discord.Embed(
            title=f"🎉 {char['name']} Claimed!",
            description=f"*{char.get('anime', 'Unknown')}*",
            color=rarity_data["color"]
        )
        embed.set_image(url="attachment://gacha_claimed.png")
        embed.set_footer(text="Use .draw collection to view your collection!")
        
        await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
    
    def _update_buttons(self):
        """Disable buttons for claimed characters"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label == "1" and 0 in self.claimed_indices:
                    item.disabled = True
                    item.style = discord.ButtonStyle.secondary
                elif item.label == "2" and 1 in self.claimed_indices:
                    item.disabled = True
                    item.style = discord.ButtonStyle.secondary
                elif item.label == "3" and 2 in self.claimed_indices:
                    item.disabled = True
                    item.style = discord.ButtonStyle.secondary
    
    @discord.ui.button(label="1", style=discord.ButtonStyle.success, emoji="1️⃣")
    async def claim_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_character(interaction, 0)
    
    @discord.ui.button(label="2", style=discord.ButtonStyle.success, emoji="2️⃣")
    async def claim_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_character(interaction, 1)
    
    @discord.ui.button(label="3", style=discord.ButtonStyle.success, emoji="3️⃣")
    async def claim_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_character(interaction, 2)
    
    @discord.ui.button(label="Skip", style=discord.ButtonStyle.danger, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your draw!", ephemeral=True)
        
        self.claimed = True
        self.stop()
        
        # Keep showing cards, just remove buttons
        await interaction.response.edit_message(content="⏭️ **Skipped** - No character claimed", embed=None, view=None)
    
    async def on_timeout(self):
        if not self.claimed and self.message:
            try:
                # Keep showing cards, just remove buttons
                await self.message.edit(content="⏰ **Time's up** - No character claimed", embed=None, view=None)
            except:
                pass


class InventoryView(discord.ui.View):
    """Paginated inventory view with filters"""
    def __init__(self, cog, user: discord.Member, guild_id: str, characters: list, filter_type: str = "all"):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.all_characters = characters
        self.filter_type = filter_type
        self.page = 0
        self.per_page = 10
        
        self.filtered_chars = self._filter_characters()
        self.max_pages = max(1, (len(self.filtered_chars) + self.per_page - 1) // self.per_page)
        
        # Add filter select menu
        self.add_item(InventoryFilterSelect(self))
    
    def _filter_characters(self):
        if self.filter_type == "all":
            return self.all_characters
        elif self.filter_type == "waifu":
            return [c for c in self.all_characters if c.get("gender") == "Female"]
        elif self.filter_type == "husbando":
            return [c for c in self.all_characters if c.get("gender") == "Male"]
        elif self.filter_type == "legendary":
            return [c for c in self.all_characters if c.get("rarity") == "legendary"]
        elif self.filter_type == "epic":
            return [c for c in self.all_characters if c.get("rarity") in ["epic", "legendary"]]
        else:
            return self.all_characters
    
    def get_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page
        page_chars = self.filtered_chars[start:end]
        
        filter_labels = {
            "all": "All Characters",
            "waifu": "Waifus ♀️",
            "husbando": "Husbandos ♂️",
            "legendary": "Legendary ⭐⭐⭐⭐⭐",
            "epic": "Epic+ 🟣"
        }
        
        embed = discord.Embed(
            title=f"📦 {self.user.display_name}'s Collection",
            description=f"**Filter:** {filter_labels.get(self.filter_type, 'All')}\n"
                       f"**Total:** {len(self.filtered_chars)} characters",
            color=discord.Color.blurple()
        )
        
        if page_chars:
            char_lines = []
            for i, char in enumerate(page_chars, start=start + 1):
                rarity_data = GACHA_RARITY_TIERS.get(char.get("rarity", "common"))
                stars = "⭐" * rarity_data["stars"]
                gender = "♀️" if char.get("gender") == "Female" else "♂️" if char.get("gender") == "Male" else "⚧"
                char_lines.append(f"`{i}.` {stars} **{char['name']}** {gender}\n-# {char.get('anime', 'Unknown')}")
            
            embed.add_field(name="Characters", value="\n".join(char_lines), inline=False)
        else:
            embed.add_field(name="No Characters", value="No characters match this filter.", inline=False)
        
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages}")
        return embed
    
    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Not your inventory!", ephemeral=True)
        
        self.page = (self.page - 1) % self.max_pages
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
    
    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ Not your inventory!", ephemeral=True)
        
        self.page = (self.page + 1) % self.max_pages
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


class InventoryFilterSelect(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label="All Characters", value="all", emoji="📦", default=parent_view.filter_type == "all"),
            discord.SelectOption(label="Waifus", value="waifu", emoji="♀️", default=parent_view.filter_type == "waifu"),
            discord.SelectOption(label="Husbandos", value="husbando", emoji="♂️", default=parent_view.filter_type == "husbando"),
            discord.SelectOption(label="Legendary", value="legendary", emoji="🌟", default=parent_view.filter_type == "legendary"),
            discord.SelectOption(label="Epic+", value="epic", emoji="🟣", default=parent_view.filter_type == "epic"),
        ]
        super().__init__(placeholder="Filter characters...", options=options, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.user.id:
            return await interaction.response.send_message("❌ Not your inventory!", ephemeral=True)
        
        self.parent_view.filter_type = self.values[0]
        self.parent_view.filtered_chars = self.parent_view._filter_characters()
        self.parent_view.max_pages = max(1, (len(self.parent_view.filtered_chars) + self.parent_view.per_page - 1) // self.parent_view.per_page)
        self.parent_view.page = 0
        
        # Update default selection
        for opt in self.options:
            opt.default = opt.value == self.values[0]
        
        await interaction.response.edit_message(embed=self.parent_view.get_embed(), view=self.parent_view)


# ═══════════════════════════════════════════════════════════════
# MULTIPLAYER GAME VIEWS
# ═══════════════════════════════════════════════════════════════

class HangmanJoinView(discord.ui.View):
    """View for joining hangman game with visual waiting room"""
    def __init__(self, cog, game_id: str, host_user: discord.User = None):
        super().__init__(timeout=30)
        self.cog = cog
        self.game_id = game_id
        self.host_user = host_user
    
    async def _update_waiting_room(self, message):
        """Update the waiting room image with current players"""
        game = self.cog.active_games.get(self.game_id)
        if not game:
            return
        
        # Build player list with avatars
        players = []
        async with aiohttp.ClientSession() as session:
            for user_id in game["players"].keys():
                try:
                    user = await self.cog.bot.fetch_user(int(user_id))
                    avatar_bytes = None
                    if user.avatar:
                        avatar_bytes = await fetch_avatar_bytes(session, user.avatar.url)
                    players.append({"name": user.display_name, "avatar_bytes": avatar_bytes})
                except:
                    players.append({"name": "Player", "avatar_bytes": None})
        
        # Get host avatar
        host_avatar = None
        host_name = "Unknown"
        if self.host_user:
            host_name = self.host_user.display_name
            if self.host_user.avatar:
                async with aiohttp.ClientSession() as session:
                    host_avatar = await fetch_avatar_bytes(session, self.host_user.avatar.url)
        
        # Generate waiting room image
        word_len = len(game.get("word", ""))
        img_buffer = await generate_waiting_room_image(
            game_name="HANGMAN",
            host_name=host_name,
            host_avatar_bytes=host_avatar,
            players=players,
            max_players=5,
            extra_info=f"{word_len} letters • 6 lives"
        )
        
        file = discord.File(img_buffer, filename="hangman_lobby.png")
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_image(url="attachment://hangman_lobby.png")
        embed.set_footer(text="Game starts in 30 seconds or when full!")
        
        await message.edit(embed=embed, attachments=[file])
    
    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green, emoji="🎮")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game no longer exists!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        user_id = str(interaction.user.id)
        
        if game["started"]:
            return await interaction.response.send_message("❌ Game already started!", ephemeral=True)
        
        if user_id in game["players"]:
            return await interaction.response.send_message("✅ You're already in this game!", ephemeral=True)
        
        if len(game["players"]) >= 5:
            return await interaction.response.send_message("❌ Game is full (5 players max)!", ephemeral=True)
        
        # Add player
        game["players"][user_id] = {
            "guessed": set(),
            "wrong": 0,
            "display": " ".join("_" for _ in game["word"]),
            "status": "playing",
            "dm_msg": None,
            "view": None
        }
        
        await interaction.response.send_message(f"✅ Joined! Check your DMs when the game starts.", ephemeral=True)
        
        # Update waiting room image
        await self._update_waiting_room(interaction.message)
        
        # Start early if 5 players
        if len(game["players"]) >= 5:
            game["started"] = True
            self.stop()
            await self.cog._start_hangman_game(self.game_id)


# Hangman ASCII art stages
HANGMAN_STAGES = [
    "```\n  +---+\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]


class HangmanLetterView(discord.ui.View):
    """View for guessing letters in hangman with pagination"""
    def __init__(self, cog, game_id: str, user_id: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.game_id = game_id
        self.user_id = user_id
        self.page = 0
        
        # Letter pages: 5 letters per row, 3 rows = 15 letters per page
        self.letter_pages = [
            "ABCDEFGHIJKLMNO",  # Page 0: A-O
            "PQRSTUVWXYZ"       # Page 1: P-Z
        ]
        
        self._build_buttons()
    
    def _build_buttons(self):
        """Build the current page of letter buttons"""
        self.clear_items()
        
        letters = self.letter_pages[self.page]
        game = self.cog.active_games.get(self.game_id)
        if not game:
            return
        
        player = game["players"].get(self.user_id)
        if not player:
            return
        
        # Add letter buttons (5 per row, up to 3 rows)
        for i, letter in enumerate(letters):
            # Determine button style based on guess status
            if letter in player.get("guessed", set()):
                if letter in game["word"]:
                    style = discord.ButtonStyle.success  # Green for correct
                else:
                    style = discord.ButtonStyle.danger   # Red for wrong
                disabled = True
            else:
                style = discord.ButtonStyle.primary
                disabled = False
            
            button = discord.ui.Button(
                label=letter,
                style=style,
                disabled=disabled,
                row=i // 5
            )
            button.callback = self._create_letter_callback(letter)
            self.add_item(button)
        
        # Add navigation buttons on row 4
        if len(self.letter_pages) > 1:
            prev_btn = discord.ui.Button(
                label="⬅️ Back",
                style=discord.ButtonStyle.secondary,
                disabled=(self.page == 0),
                row=4
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)
            
            next_btn = discord.ui.Button(
                label="Next ➡️",
                style=discord.ButtonStyle.secondary,
                disabled=(self.page == len(self.letter_pages) - 1),
                row=4
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)
    
    async def _prev_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if self.page > 0:
            self.page -= 1
            self._build_buttons()
            
            game = self.cog.active_games.get(self.game_id)
            player = game["players"].get(self.user_id)
            guessed_str = ", ".join(sorted(player["guessed"])) or "None"
            
            embed = discord.Embed(
                title="🕵️ Hangman",
                description=f"{HANGMAN_STAGES[player['wrong']]}\n**Word:** `{player['display']}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Guessed", value=guessed_str, inline=True)
            embed.add_field(name="Wrong", value=f"{player['wrong']}/6", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def _next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if self.page < len(self.letter_pages) - 1:
            self.page += 1
            self._build_buttons()
            
            game = self.cog.active_games.get(self.game_id)
            player = game["players"].get(self.user_id)
            guessed_str = ", ".join(sorted(player["guessed"])) or "None"
            
            embed = discord.Embed(
                title="🕵️ Hangman",
                description=f"{HANGMAN_STAGES[player['wrong']]}\n**Word:** `{player['display']}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Guessed", value=guessed_str, inline=True)
            embed.add_field(name="Wrong", value=f"{player['wrong']}/6", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=self)
    
    def _create_letter_callback(self, letter: str):
        """Create callback for letter button"""
        async def callback(interaction: discord.Interaction):
            if self.game_id not in self.cog.active_games:
                return await interaction.response.send_message("❌ Game ended!", ephemeral=True)
            
            game = self.cog.active_games[self.game_id]
            player = game["players"].get(self.user_id)
            
            if not player or player["status"] != "playing":
                return await interaction.response.send_message("❌ You're not playing!", ephemeral=True)
            
            if letter in player["guessed"]:
                return await interaction.response.send_message(f"❌ Already guessed **{letter}**!", ephemeral=True)
            
            # Process guess
            player["guessed"].add(letter)
            guild_id = game["guild_id"]
            
            # Check if letter is in word
            is_correct = letter in game["word"]
            if not is_correct:
                player["wrong"] += 1
                await self.cog.quest_data.add_balance(self.user_id, guild_id, -10)
            
            # Update display
            player["display"] = " ".join(c if c in player["guessed"] else "_" for c in game["word"])
            
            # Rebuild buttons FIRST to update colors
            self._build_buttons()
            
            # Check win/lose
            if "_" not in player["display"]:
                player["status"] = "won"
                word_len = len(game["word"])
                winnings = 100 + (word_len * 10) + ((6 - player["wrong"]) * 20)
                await self.cog.quest_data.add_balance(self.user_id, guild_id, winnings)
                
                # Check if this is the first winner
                other_winners = [p for uid, p in game["players"].items() if uid != self.user_id and p["status"] == "won"]
                is_first_winner = len(other_winners) == 0
                
                embed = discord.Embed(
                    title="🏆 You Won!",
                    description=f"{HANGMAN_STAGES[player['wrong']]}\n**Word:** {game['word']}\n\n💰 Won **+{winnings}** stella points!",
                    color=discord.Color.green()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                
                # If first winner, notify channel and end game for all players
                if is_first_winner:
                    await self.cog._end_hangman_game(self.game_id, self.user_id)
            elif player["wrong"] >= 6:
                player["status"] = "lost"
                embed = discord.Embed(
                    title="💀 Game Over!",
                    description=f"{HANGMAN_STAGES[6]}\n**Word was:** {game['word']}",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                # Update DM with hangman drawing
                guessed_str = ", ".join(sorted(player["guessed"])) or "None"
                
                embed = discord.Embed(
                    title="🕵️ Hangman",
                    description=f"{HANGMAN_STAGES[player['wrong']]}\n**Word:** `{player['display']}`",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Guessed", value=guessed_str, inline=True)
                embed.add_field(name="Wrong", value=f"{player['wrong']}/6", inline=True)
                
                await interaction.response.edit_message(embed=embed, view=self)
            
            # Update leaderboard
            await self.cog._update_hangman_leaderboard(self.game_id)
        
        return callback


class WordleJoinView(discord.ui.View):
    """View for joining wordle game with visual waiting room"""
    def __init__(self, cog, game_id: str, host_user: discord.User = None):
        super().__init__(timeout=30)
        self.cog = cog
        self.game_id = game_id
        self.host_user = host_user
    
    async def _update_waiting_room(self, message):
        """Update the waiting room image with current players"""
        game = self.cog.active_games.get(self.game_id)
        if not game:
            return
        
        # Build player list with avatars
        players = []
        async with aiohttp.ClientSession() as session:
            for user_id in game["players"].keys():
                try:
                    user = await self.cog.bot.fetch_user(int(user_id))
                    avatar_bytes = None
                    if user.avatar:
                        avatar_bytes = await fetch_avatar_bytes(session, user.avatar.url)
                    players.append({"name": user.display_name, "avatar_bytes": avatar_bytes})
                except:
                    players.append({"name": f"Player", "avatar_bytes": None})
        
        # Get host avatar
        host_avatar = None
        host_name = "Unknown"
        if self.host_user:
            host_name = self.host_user.display_name
            if self.host_user.avatar:
                async with aiohttp.ClientSession() as session:
                    host_avatar = await fetch_avatar_bytes(session, self.host_user.avatar.url)
        
        # Generate waiting room image
        img_buffer = await generate_waiting_room_image(
            game_name="WORDLE",
            host_name=host_name,
            host_avatar_bytes=host_avatar,
            players=players,
            max_players=5,
            extra_info="5-letter word • 6 attempts"
        )
        
        file = discord.File(img_buffer, filename="wordle_lobby.png")
        embed = discord.Embed(color=discord.Color.green())
        embed.set_image(url="attachment://wordle_lobby.png")
        embed.set_footer(text="Game starts in 30 seconds or when full!")
        
        await message.edit(embed=embed, attachments=[file])
    
    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green, emoji="🎮")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game no longer exists!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        user_id = str(interaction.user.id)
        
        if game["started"]:
            return await interaction.response.send_message("❌ Game already started!", ephemeral=True)
        
        if user_id in game["players"]:
            return await interaction.response.send_message("✅ You're already in this game!", ephemeral=True)
        
        if len(game["players"]) >= 5:
            return await interaction.response.send_message("❌ Game is full (5 players max)!", ephemeral=True)
        
        # Add player
        game["players"][user_id] = {
            "attempts": [],
            "status": "playing",
            "dm_msg": None,
            "view": None
        }
        
        await interaction.response.send_message(f"✅ Joined! Check your DMs when the game starts.", ephemeral=True)
        
        # Update waiting room image
        await self._update_waiting_room(interaction.message)
        
        # Start early if 5 players
        if len(game["players"]) >= 5:
            game["started"] = True
            self.stop()
            await self.cog._start_wordle_game(self.game_id)


class WordleGuessModal(discord.ui.Modal, title="Submit Your Guess"):
    """Modal for submitting wordle guesses"""
    guess_input = discord.ui.TextInput(
        label="Enter a 5-letter word",
        placeholder="AGENT",
        min_length=5,
        max_length=5,
        required=True
    )
    
    def __init__(self, cog, game_id: str, user_id: str):
        super().__init__()
        self.cog = cog
        self.game_id = game_id
        self.user_id = user_id
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game ended!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        player = game["players"].get(self.user_id)
        
        if not player or player["status"] != "playing":
            return await interaction.response.send_message("❌ You're not playing!", ephemeral=True)
        
        guess = self.guess_input.value.upper()
        
        if not guess.isalpha():
            return await interaction.response.send_message("❌ Only letters allowed!", ephemeral=True)
        
        # Calculate result
        def get_result(guess_word, answer):
            result = []
            answer_chars = list(answer)
            for i, (g, a) in enumerate(zip(guess_word, answer)):
                if g == a:
                    result.append("🟩")
                    answer_chars[i] = None
                else:
                    result.append(None)
            for i, g in enumerate(guess_word):
                if result[i] is None:
                    if g in answer_chars:
                        result[i] = "🟨"
                        answer_chars[answer_chars.index(g)] = None
                    else:
                        result[i] = "⬛"
            return "".join(result)
        
        result = get_result(guess, game["word"])
        
        # Deduct points if not correct
        if guess != game["word"]:
            guild_id = game["guild_id"]
            await self.cog.quest_data.add_balance(self.user_id, guild_id, -15)
        
        # Add attempt
        player["attempts"].append({"word": guess, "result": result})
        
        # Check win/lose
        payouts = {1: 500, 2: 400, 3: 300, 4: 200, 5: 150, 6: 100}
        
        # Fetch user avatar for the image
        user = interaction.user
        player_name = user.display_name
        avatar_bytes = None
        try:
            session = await self.cog.get_session()
            avatar_url = user.display_avatar.with_size(64).url
            avatar_bytes = await fetch_avatar_bytes(session, avatar_url)
        except:
            pass
        
        if guess == game["word"]:
            player["status"] = "won"
            attempt_num = len(player["attempts"])
            winnings = payouts.get(attempt_num, 100)
            guild_id = game["guild_id"]
            await self.cog.quest_data.add_balance(self.user_id, guild_id, winnings)
            
            # Generate win image with avatar
            img_buffer = generate_wordle_board_image(
                player["attempts"], game["word"], show_word=False,
                avatar_bytes=avatar_bytes, player_name=player_name
            )
            file = discord.File(img_buffer, filename="wordle_win.png")
            
            embed = discord.Embed(
                title="🏆 You Won!",
                description=f"💰 Won **+{winnings}** stella points!",
                color=discord.Color.gold()
            )
            embed.set_image(url="attachment://wordle_win.png")
            await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
            
            # End game for everyone and ping winner in channel
            await self.cog._end_wordle_game(self.game_id, self.user_id)
        elif len(player["attempts"]) >= 6:
            player["status"] = "lost"
            
            # Generate loss image with avatar
            img_buffer = generate_wordle_board_image(
                player["attempts"], game["word"], show_word=True,
                avatar_bytes=avatar_bytes, player_name=player_name
            )
            file = discord.File(img_buffer, filename="wordle_loss.png")
            
            embed = discord.Embed(
                title="💀 Game Over!",
                description=f"**Word was:** {game['word']}",
                color=discord.Color.red()
            )
            embed.set_image(url="attachment://wordle_loss.png")
            await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
            
            # Check if all players are done
            await self.cog._check_wordle_game_end(self.game_id)
        else:
            # Continue playing - generate board image with avatar
            img_buffer = generate_wordle_board_image(
                player["attempts"], game["word"],
                avatar_bytes=avatar_bytes, player_name=player_name
            )
            file = discord.File(img_buffer, filename="wordle_board.png")
            
            embed = discord.Embed(
                title="🟩 Your Wordle Game",
                description=f"Click **Submit Guess** to enter a 5-letter word!\n"
                           f"❌ Wrong guess = **-15 stella points**",
                color=discord.Color.green()
            )
            embed.set_image(url="attachment://wordle_board.png")
            embed.add_field(name="Attempts", value=f"{len(player['attempts'])}/6", inline=True)
            
            await interaction.response.edit_message(embed=embed, attachments=[file])
        
        # Update leaderboard with live image
        await self.cog._update_wordle_leaderboard(self.game_id)


class WordleGuessView(discord.ui.View):
    """View for wordle game with submit button and view others"""
    def __init__(self, cog, game_id: str, user_id: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.game_id = game_id
        self.user_id = user_id
    
    @discord.ui.button(label="Submit Guess", style=discord.ButtonStyle.green, emoji="📝")
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WordleGuessModal(self.cog, self.game_id, self.user_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="View Others", style=discord.ButtonStyle.secondary, emoji="👀")
    async def view_others_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View other players' Wordle boards"""
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game ended!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        other_players = {uid: pdata for uid, pdata in game["players"].items() if uid != self.user_id}
        
        if not other_players:
            return await interaction.response.send_message("👤 No other players in this game!", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        # Generate live image showing all other players' boards
        players_with_names = {}
        for uid, pdata in other_players.items():
            players_with_names[uid] = pdata.copy()
            if "display_name" not in players_with_names[uid]:
                try:
                    user = await self.cog.bot.fetch_user(int(uid))
                    players_with_names[uid]["display_name"] = user.display_name
                except:
                    players_with_names[uid]["display_name"] = "Player"
        
        img_buffer = generate_wordle_live_image(players_with_names, self.cog.bot)
        file = discord.File(img_buffer, filename="wordle_others.png")
        
        # Build status summary
        status_lines = []
        for uid, pdata in other_players.items():
            name = pdata.get("display_name", "Player")
            status = pdata.get("status", "playing")
            attempts = len(pdata.get("attempts", []))
            
            if status == "won":
                status_lines.append(f"🏆 **{name}** - Won!")
            elif status == "lost":
                status_lines.append(f"**{name}** - Lost ({attempts}/6)")
            elif status == "ended":
                status_lines.append(f"**{name}** - Game ended ({attempts}/6)")
            else:
                status_lines.append(f"**{name}** - Playing ({attempts}/6)")
        
        embed = discord.Embed(
            title="👀 Other Players' Progress",
            description="\n".join(status_lines) if status_lines else "No other players",
            color=discord.Color.blue()
        )
        embed.set_image(url="attachment://wordle_others.png")
        embed.set_footer(text="Their boards are hidden - only showing progress!")
        
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# SLOT MACHINE VIEW
# ═══════════════════════════════════════════════════════════════

class SlotMachineView(discord.ui.View):
    """View for slot machine with Play Again button"""
    def __init__(self, cog, user_id: str, guild_id: str, last_bet: int, results: list = None):
        super().__init__(timeout=180)  # Extended timeout for cooldown
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.last_bet = last_bet
        self.results = results or []
        self.cooldown_end = None
        
        # Start cooldown immediately
        import time
        self.cooldown_end = time.time() + 3600  # 60 minutes
    
    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.green, emoji="🎰")
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
        
        # Check cooldown
        import time
        if self.cooldown_end and time.time() < self.cooldown_end:
            remaining = int(self.cooldown_end - time.time())
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60
            
            if hours > 0:
                time_str = f"**{hours}h {minutes}m {seconds}s**"
            else:
                time_str = f"**{minutes}m {seconds}s**"
                
            return await interaction.response.send_message(
                f"⏰ Slot machine is cooling down! Wait {time_str} before playing again.",
                ephemeral=True
            )
        
        # Check balance
        balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
        if balance < self.last_bet:
            return await interaction.response.send_message(
                f"❌ You need **{self.last_bet:,}** but only have **{balance:,}** stella points!", 
                ephemeral=True
            )
        
        # Disable button and start new game
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Run the slot machine
        await self.cog._run_slot_machine(interaction.channel, interaction.user, self.last_bet)
    
    @discord.ui.button(label="Change Bet", style=discord.ButtonStyle.secondary, emoji="💰")
    async def change_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
        
        modal = SlotBetModal(self.cog, self.user_id, self.guild_id)
        await interaction.response.send_modal(modal)


class SlotBetModal(discord.ui.Modal, title="Change Bet Amount"):
    """Modal for changing slot bet"""
    bet_input = discord.ui.TextInput(
        label="Enter bet amount (10 - 10,000)",
        placeholder="100",
        min_length=1,
        max_length=6,
        required=True
    )
    
    def __init__(self, cog, user_id: str, guild_id: str):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_input.value.replace(",", ""))
            if bet < 10:
                return await interaction.response.send_message("❌ Minimum bet is **10** pts!", ephemeral=True)
            if bet > 10000:
                return await interaction.response.send_message("❌ Maximum bet is **10,000** pts!", ephemeral=True)
            
            balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
            if balance < bet:
                return await interaction.response.send_message(
                    f"❌ You need **{bet:,}** but only have **{balance:,}** pts!", 
                    ephemeral=True
                )
            
            await interaction.response.defer()
            await self.cog._run_slot_machine(interaction.channel, interaction.user, bet)
        except ValueError:
            await interaction.response.send_message("❌ Invalid bet amount!", ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# JOB SYSTEM VIEWS
# ═══════════════════════════════════════════════════════════════

class JobSelectMenu(discord.ui.Select):
    """Dropdown menu for selecting a job to apply for"""
    def __init__(self, cog, user: discord.Member, guild_id: str, user_stats: dict):
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.user_stats = user_stats
        
        jobs_config = GROUNDED_CONFIG.get("jobs_system", {}).get("available_jobs", [])
        
        options = []
        for job in jobs_config:
            reqs = job.get("requirements", {})
            qualified = (
                user_stats["stars"] >= reqs.get("min_stars", 0) and
                user_stats["activity"] >= reqs.get("min_activity", 0) and
                user_stats["balance"] >= reqs.get("min_balance", 0)
            )
            
            desc = f"Pay: {job['pay_range'][0]}-{job['pay_range'][1]} pts"
            if not qualified:
                desc = f"🔒 Requires: ⭐{reqs.get('min_stars', 0)} 📊{reqs.get('min_activity', 0)}"
            
            options.append(discord.SelectOption(
                label=job["title"],
                value=job["id"],
                description=desc[:100],
                emoji=job.get("emoji", "💼")
            ))
        
        super().__init__(
            placeholder="Select a job to apply for...",
            min_values=1,
            max_values=1,
            options=options[:25]
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your job board!", ephemeral=True)
        
        job_id = self.values[0]
        job_data = self.cog.get_job_by_id(job_id)
        
        if not job_data:
            return await interaction.response.send_message("❌ Job not found!", ephemeral=True)
        
        # Check requirements
        reqs = job_data.get("requirements", {})
        if (self.user_stats["stars"] < reqs.get("min_stars", 0) or
            self.user_stats["activity"] < reqs.get("min_activity", 0) or
            self.user_stats["balance"] < reqs.get("min_balance", 0)):
            
            # Build requirement status with checkmarks
            stars_ok = "✅" if self.user_stats["stars"] >= reqs.get("min_stars", 0) else "❌"
            activity_ok = "✅" if self.user_stats["activity"] >= reqs.get("min_activity", 0) else "❌"
            balance_ok = "✅" if self.user_stats["balance"] >= reqs.get("min_balance", 0) else "❌"
            
            embed = discord.Embed(
                title="❌ Requirements Not Met",
                description=f"You don't qualify for **{job_data['title']}** yet!\n\n"
                           f"**Requirements:**\n"
                           f"{stars_ok} ⭐ Stars: {reqs.get('min_stars', 0):,} (You: {self.user_stats['stars']:,})\n"
                           f"{activity_ok} 📊 Activity: {reqs.get('min_activity', 0)} (You: {self.user_stats['activity']})\n"
                           f"{balance_ok} 💰 Balance: {reqs.get('min_balance', 0):,} (You: {self.user_stats['balance']:,})",
                color=discord.Color.red()
            )
            
            # Add tips on how to earn each requirement
            tips = []
            if self.user_stats["stars"] < reqs.get("min_stars", 0):
                tips.append("⭐ **Stars** = Total stella points earned lifetime. Use `.work` at your current job to earn more!")
            if self.user_stats["activity"] < reqs.get("min_activity", 0):
                tips.append("📊 **Activity** = Commands used. Keep using bot commands to increase!")
            if self.user_stats["balance"] < reqs.get("min_balance", 0):
                tips.append("💰 **Balance** = Current stella points. Earn with `.work`, `.claim`, games, etc.")
            
            embed.add_field(
                name="💡 How to Qualify",
                value="\n".join(tips) if tips else "Keep playing to meet requirements!",
                inline=False
            )
            
            # Suggest a job they might qualify for
            embed.set_footer(text="Tip: Start with entry-level jobs and work your way up!")
            
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Apply for job
        user_id = str(interaction.user.id)
        await self.cog.set_user_job(user_id, self.guild_id, job_id)
        
        embed = discord.Embed(
            title="✅ Job Application Accepted!",
            description=f"Congratulations! You are now employed as a **{job_data['emoji']} {job_data['title']}**!\n\n"
                       f"Use `.work` to start earning stella points!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="💰 Pay Range",
            value=f"{job_data['pay_range'][0]}-{job_data['pay_range'][1]} pts per shift",
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


class JobBoardView(discord.ui.View):
    """View for the job board with apply/quit buttons"""
    def __init__(self, cog, user: discord.Member, guild_id: str, current_job_id: Optional[str]):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.current_job_id = current_job_id
        self.user_stats = {}
    
    async def setup(self):
        """Async setup to fetch user stats"""
        user_id = str(self.user.id)
        self.user_stats = {
            "stars": await self.cog.get_user_stars(user_id, self.guild_id),
            "activity": await self.cog.get_user_activity(user_id, self.guild_id),
            "balance": await self.cog.quest_data.get_balance(user_id, self.guild_id)
        }
        
        # Add job select menu
        self.add_item(JobSelectMenu(self.cog, self.user, self.guild_id, self.user_stats))
    
    @discord.ui.button(label="Quit Job", style=discord.ButtonStyle.danger, emoji="🚪", row=1)
    async def quit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your job board!", ephemeral=True)
        
        user_id = str(interaction.user.id)
        current_job_id = await self.cog.get_user_job(user_id, self.guild_id)
        
        if not current_job_id:
            return await interaction.response.send_message("❌ You don't have a job to quit!", ephemeral=True)
        
        job_data = self.cog.get_job_by_id(current_job_id)
        job_name = job_data["title"] if job_data else "Unknown"
        
        await self.cog.set_user_job(user_id, self.guild_id, None)
        
        embed = discord.Embed(
            title="👋 Job Quit",
            description=f"You quit your job as **{job_name}**.\n\n"
                       f"Use `.jobs` to find a new job!",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your job board!", ephemeral=True)
        
        # Refresh stats and rebuild view
        user_id = str(interaction.user.id)
        current_job_id = await self.cog.get_user_job(user_id, self.guild_id)
        balance = await self.cog.quest_data.get_balance(user_id, self.guild_id)
        stars = await self.cog.get_user_stars(user_id, self.guild_id)
        activity = await self.cog.get_user_activity(user_id, self.guild_id)
        
        jobs_config = GROUNDED_CONFIG.get("jobs_system", {})
        available_jobs = jobs_config.get("available_jobs", [])
        categories = jobs_config.get("job_categories", {})
        
        embed = discord.Embed(
            title="📋 Job Board",
            description="Apply for a job to start earning stella points with `.work`!\n\n"
                       f"**Your Stats:**\n"
                       f"⭐ Stars: **{stars:,}**\n"
                       f"📊 Activity: **{activity}**\n"
                       f"💰 Balance: **{balance:,}**",
            color=discord.Color.blue()
        )
        
        if current_job_id:
            current_job = self.cog.get_job_by_id(current_job_id)
            if current_job:
                embed.add_field(
                    name="💼 Current Job",
                    value=f"{current_job['emoji']} **{current_job['title']}**\n"
                          f"Pay: {current_job['pay_range'][0]}-{current_job['pay_range'][1]} pts",
                    inline=False
                )
        
        jobs_by_category = {}
        for job in available_jobs:
            cat = job.get("category", "entry")
            if cat not in jobs_by_category:
                jobs_by_category[cat] = []
            jobs_by_category[cat].append(job)
        
        for cat_id, cat_jobs in jobs_by_category.items():
            cat_info = categories.get(cat_id, {"name": cat_id.title(), "emoji": "📋"})
            job_lines = []
            for job in cat_jobs:
                reqs = job.get("requirements", {})
                qualified = (
                    stars >= reqs.get("min_stars", 0) and
                    activity >= reqs.get("min_activity", 0) and
                    balance >= reqs.get("min_balance", 0)
                )
                status = "✅" if qualified else "🔒"
                job_lines.append(f"{status} {job['emoji']} **{job['title']}** - {job['pay_range'][0]}-{job['pay_range'][1]} pts")
            
            embed.add_field(
                name=f"{cat_info['emoji']} {cat_info['name']}",
                value="\n".join(job_lines) if job_lines else "No jobs",
                inline=False
            )
        
        # Update user stats for the select menu
        self.user_stats = {"stars": stars, "activity": activity, "balance": balance}
        
        await interaction.response.edit_message(embed=embed)


class TaskSelectMenu(discord.ui.Select):
    """Dropdown menu for selecting a work task"""
    def __init__(self, cog, user: discord.Member, guild_id: str, job_data: dict):
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.job_data = job_data
        
        tasks = job_data.get("tasks", [])
        options = []
        for i, task in enumerate(tasks):
            options.append(discord.SelectOption(
                label=task["name"],
                value=str(i),
                description=task["message"][:100] if len(task["message"]) > 100 else task["message"],
                emoji="📝"
            ))
        
        super().__init__(
            placeholder="Choose your task...",
            min_values=1,
            max_values=1,
            options=options if options else [discord.SelectOption(label="Work", value="0")]
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your work shift!", ephemeral=True)
        
        user_id = str(interaction.user.id)
        task_idx = int(self.values[0])
        tasks = self.job_data.get("tasks", [])
        
        if task_idx < len(tasks):
            task = tasks[task_idx]
            task_name = task["name"]
            task_message = task["message"]
        else:
            task_name = "Work"
            task_message = "You completed your work shift!"
        
        # Calculate reward
        pay_min, pay_max = self.job_data.get("pay_range", [50, 100])
        reward = random.randint(pay_min, pay_max)
        
        # Apply character bonus if any
        character = await self.cog.get_user_character(user_id, self.guild_id)
        if character:
            work_config = GROUNDED_CONFIG.get("work", {})
            char_bonus = work_config.get("character_bonuses", {}).get(character, {})
            multiplier = char_bonus.get("multiplier", 1.0)
            reward = int(reward * multiplier)
        
        # Add reward and set cooldown
        await self.cog.quest_data.add_balance(user_id, self.guild_id, reward)
        await self.cog.set_cooldown(user_id, "work")
        
        # Track total stars earned
        try:
            db = self.cog.quest_data.mongoConnect[self.cog.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": self.guild_id},
                {"$inc": {f"members.{user_id}.total_stars_earned": reward}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error tracking stars: {e}")
        
        new_balance = await self.cog.quest_data.get_balance(user_id, self.guild_id)
        
        embed = discord.Embed(
            title=f"{self.job_data['emoji']} {task_name}",
            description=task_message,
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Earned", value=f"+**{reward}** pts", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        if character:
            embed.set_footer(text=f"🌟 {character} bonus applied!")
        
        await interaction.response.edit_message(embed=embed, view=None)


class WorkTaskView(discord.ui.View):
    """View for selecting work tasks"""
    def __init__(self, cog, user: discord.Member, guild_id: str, job_data: dict):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.job_data = job_data
        
        # Add task select menu
        self.add_item(TaskSelectMenu(cog, user, guild_id, job_data))
    
    @discord.ui.button(label="Quick Work", style=discord.ButtonStyle.green, emoji="⚡", row=1)
    async def quick_work_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Do a random task quickly"""
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your work shift!", ephemeral=True)
        
        user_id = str(interaction.user.id)
        tasks = self.job_data.get("tasks", [])
        
        if tasks:
            task = random.choice(tasks)
            task_name = task["name"]
            task_message = task["message"]
        else:
            task_name = "Work"
            task_message = "You completed your work shift!"
        
        # Calculate base reward
        pay_min, pay_max = self.job_data.get("pay_range", [50, 100])
        base_reward = random.randint(pay_min, pay_max)
        
        # Check for overtime event (10% chance)
        is_overtime = random.random() < 0.10
        overtime_bonus = base_reward if is_overtime else 0
        
        # Apply character bonus
        character = await self.cog.get_user_character(user_id, self.guild_id)
        char_bonus_amount = 0
        if character:
            work_config = GROUNDED_CONFIG.get("work", {})
            char_bonus = work_config.get("character_bonuses", {}).get(character, {})
            multiplier = char_bonus.get("multiplier", 1.0)
            char_bonus_amount = int(base_reward * (multiplier - 1))
        
        # Task bonus (random 0-20%)
        task_bonus = int(base_reward * random.uniform(0, 0.2))
        
        # Total reward
        total_reward = base_reward + char_bonus_amount + task_bonus + overtime_bonus
        
        # Add reward and set cooldown
        await self.cog.quest_data.add_balance(user_id, self.guild_id, total_reward)
        await self.cog.set_cooldown(user_id, "work")
        
        # Track total stars earned
        try:
            db = self.cog.quest_data.mongoConnect[self.cog.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": self.guild_id},
                {"$inc": {f"members.{user_id}.total_stars_earned": total_reward}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error tracking stars: {e}")
        
        new_balance = await self.cog.quest_data.get_balance(user_id, self.guild_id)
        
        # Generate paycheck image
        paycheck_buffer = generate_paycheck_image(
            job_title=self.job_data.get("title", "Worker"),
            job_emoji=self.job_data.get("emoji", "💼"),
            base_pay=base_reward,
            bonus=task_bonus,
            overtime=is_overtime,
            character_bonus=char_bonus_amount
        )
        file = discord.File(paycheck_buffer, filename="paycheck.png")
        
        if is_overtime:
            embed = discord.Embed(
                title=f"⭐ OVERTIME! {task_name}",
                description=f"{task_message}\n\n🎉 **You worked overtime and earned DOUBLE pay!**",
                color=discord.Color.gold()
            )
        else:
            embed = discord.Embed(
                title=f"{self.job_data['emoji']} {task_name}",
                description=task_message,
                color=discord.Color.green()
            )
        
        embed.set_image(url="attachment://paycheck.png")
        embed.add_field(name="💳 New Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        if character:
            embed.set_footer(text=f"🌟 {character} bonus applied!")
        
        await interaction.response.edit_message(embed=embed, attachments=[file], view=None)


class Games(commands.Cog):
    """🎮 Mini-games that use stella points - Gamble, Classic Games & Grounded Economy!"""
    
    def __init__(self, bot):
        self.bot = bot
        from utils.cogs.quest import Quest_Data
        self.quest_data = Quest_Data(bot)
        self.session: Optional[aiohttp.ClientSession] = None
        self.active_games: Dict[str, Dict] = {}  # Track active hangman/wordle games
        self.user_cooldowns: Dict[str, Dict[str, datetime]] = {}  # Track cooldowns
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self.session
    
    def cog_unload(self):
        """Cleanup when cog unloads."""
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())
    
    async def get_user_character(self, user_id: str, guild_id: str) -> Optional[str]:
        """Get the user's selected Spy x Family character if any."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.selected_character": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("inventory", {}).get("selected_character")
        except Exception as e:
            logger.error(f"Error getting character: {e}")
        return None
    
    async def check_cooldown(self, user_id: str, action: str, cooldown_seconds: int) -> Optional[timedelta]:
        """Check if user is on cooldown. Returns remaining time or None if ready."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            # Get last action time from DB
            result = await server_col.find_one(
                {"guild_id": "global_cooldowns"},
                {f"cooldowns.{user_id}.{action}": 1}
            )
            
            if result:
                last_time_str = result.get("cooldowns", {}).get(user_id, {}).get(action)
                if last_time_str:
                    last_time = datetime.fromisoformat(last_time_str)
                    elapsed = datetime.now(timezone.utc) - last_time
                    if elapsed.total_seconds() < cooldown_seconds:
                        return timedelta(seconds=cooldown_seconds) - elapsed
        except Exception as e:
            logger.error(f"Cooldown check error: {e}")
        return None
    
    async def set_cooldown(self, user_id: str, action: str):
        """Set cooldown timestamp for an action."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            await server_col.update_one(
                {"guild_id": "global_cooldowns"},
                {"$set": {f"cooldowns.{user_id}.{action}": datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Set cooldown error: {e}")
    
    async def get_daily_streak(self, user_id: str, guild_id: str) -> int:
        """Get user's daily claim streak."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.daily_streak": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("daily_streak", 0)
        except Exception as e:
            logger.error(f"Error getting streak: {e}")
        return 0
    
    async def update_daily_streak(self, user_id: str, guild_id: str, streak: int):
        """Update user's daily claim streak."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.daily_streak": streak}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating streak: {e}")
    
    def format_time(self, td: timedelta) -> str:
        """Format timedelta to readable string."""
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    async def _get_daily_game_plays(self, user_id: str, guild_id: str, game: str) -> int:
        """Get how many times user played a game today."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]
            
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            result = await server_collection.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.games.{game}.{today}": 1}
            )
            
            if result:
                return result.get("members", {}).get(user_id, {}).get("games", {}).get(game, {}).get(today, 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting daily plays: {e}")
            return 0
    
    async def _increment_daily_game_plays(self, user_id: str, guild_id: str, game: str):
        """Increment the daily play count for a game."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]
            
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            await server_collection.update_one(
                {"guild_id": guild_id},
                {"$inc": {f"members.{user_id}.games.{game}.{today}": 1}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error incrementing daily plays: {e}")
    
    async def get_daily_plays(self, user_id: str, guild_id: str, game: str) -> int:
        """Get how many times user played a game today."""
        return await self._get_daily_game_plays(user_id, guild_id, game)
    
    async def increment_daily_plays(self, user_id: str, guild_id: str, game: str):
        """Increment the daily play count for a game."""
        await self._increment_daily_game_plays(user_id, guild_id, game)
    
    def get_random_rarity(self) -> str:
        """Get a random rarity based on chances (gacha-style)."""
        roll = random.random()
        cumulative = 0
        for rarity, data in RARITY_CONFIG.items():
            cumulative += data["chance"]
            if roll <= cumulative:
                return rarity
        return "common"
    
    def get_slot_symbol(self) -> str:
        """Get a weighted random slot symbol."""
        symbols = list(SLOT_SYMBOLS.keys())
        weights = [SLOT_SYMBOLS[s]["weight"] for s in symbols]
        return random.choices(symbols, weights=weights, k=1)[0]
    
    async def fetch_pokemon_info(self, pokemon_id: int) -> Optional[Dict[str, Any]]:
        """Fetch Pokemon info from API (just for display, not rarity)."""
        session = await self.get_session()
        
        try:
            async with session.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "name": data["name"].replace("-", " ").title(),
                        "id": data["id"],
                        "sprite": data["sprites"]["other"]["official-artwork"]["front_default"] 
                                  or data["sprites"]["front_default"],
                        "types": [t["type"]["name"].title() for t in data.get("types", [])],
                    }
        except Exception as e:
            logger.debug(f"Pokemon API error (using fallback): {e}")
        
        return None
    
    async def fetch_anime_character_info(self) -> Optional[Dict[str, Any]]:
        """Fetch random anime character info from API (just for display, not rarity)."""
        session = await self.get_session()
        
        try:
            # Random character ID (1-5000 for faster response)
            char_id = random.randint(1, 5000)
            
            async with session.get(f"https://api.jikan.moe/v4/characters/{char_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    char = data.get("data", {})
                    
                    if char:
                        # Get anime they're from
                        anime_name = "Unknown Anime"
                        if char.get("anime"):
                            anime_list = char.get("anime", [])
                            if anime_list:
                                anime_name = anime_list[0].get("anime", {}).get("title", "Unknown Anime")
                        
                        return {
                            "name": char.get("name", "Unknown"),
                            "anime": anime_name,
                            "image": char.get("images", {}).get("jpg", {}).get("image_url"),
                            "favorites": char.get("favorites", 0),
                        }
        except Exception as e:
            logger.debug(f"Jikan API error (using fallback): {e}")
        
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # GACHA SYSTEM METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def get_gacha_rarity(self, favorites: int = 0) -> str:
        """Determine rarity with realistic distribution - not just based on favorites.
        
        Uses weighted random with favorites as a modifier.
        Base rates: Common 50%, Uncommon 25%, Rare 15%, Epic 7%, Legendary 3%
        """
        # Roll for rarity first (realistic gacha rates)
        roll = random.random() * 100
        
        # Favorites give a small boost to rarity chance
        boost = min(favorites / 10000, 0.3)  # Max 30% boost
        
        if roll < (3 + boost * 5):  # ~3-8% legendary
            return "legendary"
        elif roll < (10 + boost * 10):  # ~7-17% epic
            return "epic"
        elif roll < (25 + boost * 15):  # ~15-30% rare
            return "rare"
        elif roll < (50 + boost * 10):  # ~25-35% uncommon
            return "uncommon"
        else:
            return "common"  # ~50%+ common
    
    async def fetch_gacha_characters(self, count: int = 3, gender_filter: str = None) -> list:
        """Fetch multiple random anime characters FAST - parallel requests.
        
        Args:
            count: Number of characters to fetch
            gender_filter: "Female" or "Male" to filter by gender, None for all
        """
        session = await self.get_session()
        
        # Fetch all characters in parallel for speed
        async def fetch_one_char(api_choice: str):
            try:
                if api_choice == "jikan":
                    char_id = random.randint(1, 10000)
                    # Use full endpoint to get anime info included
                    async with session.get(f"https://api.jikan.moe/v4/characters/{char_id}/full", timeout=aiohttp.ClientTimeout(total=4)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            char = data.get("data", {})
                            
                            if char and char.get("name"):
                                # Get anime from the full response
                                anime_name = "Original Character"
                                anime_list = char.get("anime", [])
                                if anime_list and len(anime_list) > 0:
                                    first_anime = anime_list[0].get("anime", {})
                                    anime_name = first_anime.get("title") or first_anime.get("name") or "Original Character"
                                
                                favorites = char.get("favorites", 0)
                                
                                # Quick gender check
                                about = (char.get("about", "") or "").lower()
                                gender = "Unknown"
                                if any(x in about for x in ["she ", "her ", "female", "woman", "girl"]):
                                    gender = "Female"
                                elif any(x in about for x in ["he ", "his ", "male", "man ", "boy"]):
                                    gender = "Male"
                                
                                if gender_filter and gender != gender_filter:
                                    return None
                                
                                images = char.get("images", {}).get("jpg", {})
                                image_url = images.get("large_image_url") or images.get("image_url")
                                
                                return {
                                    "id": char.get("mal_id"),
                                    "name": char.get("name", "Unknown"),
                                    "anime": anime_name,
                                    "image_url": image_url,
                                    "favorites": favorites,
                                    "rarity": self.get_gacha_rarity(favorites),
                                    "gender": gender,
                                }
                
                elif api_choice == "anilist":
                    query = '''
                    query ($page: Int) {
                        Page(page: $page, perPage: 1) {
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
                    '''
                    
                    variables = {"page": random.randint(1, 500)}
                    
                    async with session.post(
                        "https://graphql.anilist.co",
                        json={"query": query, "variables": variables},
                        timeout=aiohttp.ClientTimeout(total=3)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            chars = data.get("data", {}).get("Page", {}).get("characters", [])
                            
                            if chars:
                                char = chars[0]
                                gender = char.get("gender", "Unknown")
                                
                                if gender_filter and gender != gender_filter:
                                    return None
                                
                                anime_name = "Unlisted (AniList)"
                                media = char.get("media", {}).get("nodes", [])
                                if media:
                                    anime_name = media[0].get("title", {}).get("romaji", "Unknown Anime")
                                
                                return {
                                    "id": char.get("id"),
                                    "name": char.get("name", {}).get("full", "Unknown"),
                                    "anime": anime_name,
                                    "image_url": char.get("image", {}).get("large"),
                                    "favorites": char.get("favourites", 0),
                                    "rarity": self.get_gacha_rarity(char.get("favourites", 0)),
                                    "gender": gender,
                                }
                
                elif api_choice == "kitsu":
                    offset = random.randint(0, 5000)
                    # Include media castings to get anime name
                    async with session.get(
                        f"https://kitsu.io/api/edge/characters?page[limit]=1&page[offset]={offset}&include=mediaCharacters.media",
                        timeout=aiohttp.ClientTimeout(total=4)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            chars = data.get("data", [])
                            
                            if chars:
                                char = chars[0]
                                attrs = char.get("attributes", {})
                                
                                name = attrs.get("canonicalName") or attrs.get("name", "Unknown")
                                image_url = None
                                if attrs.get("image"):
                                    image_url = attrs["image"].get("original") or attrs["image"].get("large")
                                
                                char_id = int(char.get("id", 0))
                                favorites = max(100, 10000 - (char_id % 9000))
                                
                                desc = (attrs.get("description") or "").lower()
                                gender = "Unknown"
                                if any(x in desc for x in ["she ", "her ", "female", "woman", "girl"]):
                                    gender = "Female"
                                elif any(x in desc for x in ["he ", "his ", "male", "man ", "boy"]):
                                    gender = "Male"
                                
                                if gender_filter and gender != gender_filter:
                                    return None
                                
                                # Get anime name from included media
                                anime_name = "Original Character"
                                included = data.get("included", [])
                                for inc in included:
                                    if inc.get("type") == "anime" or inc.get("type") == "manga":
                                        inc_attrs = inc.get("attributes", {})
                                        title = inc_attrs.get("canonicalTitle") or inc_attrs.get("titles", {}).get("en") or inc_attrs.get("titles", {}).get("en_jp")
                                        if title:
                                            anime_name = title
                                            break
                                
                                return {
                                    "id": char_id,
                                    "name": name,
                                    "anime": anime_name,
                                    "image_url": image_url,
                                    "favorites": favorites,
                                    "rarity": self.get_gacha_rarity(favorites),
                                    "gender": gender,
                                }
            except:
                return None
        
        # Launch parallel requests
        api_sources = ["jikan", "anilist", "kitsu"]
        tasks = [fetch_one_char(api_sources[i % 3]) for i in range(count * 3)]  # Fetch extra in case some fail
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter valid results
        characters = [r for r in results if r and isinstance(r, dict)][:count]
        
        # Fill with fallback characters if needed - with realistic rarity distribution
        fallback_pool = [
            # Common characters (50%)
            {"name": "Konohamaru", "anime": "Naruto", "gender": "Male", "favorites": 500},
            {"name": "Tenten", "anime": "Naruto", "gender": "Female", "favorites": 800},
            {"name": "Krillin", "anime": "Dragon Ball", "gender": "Male", "favorites": 600},
            {"name": "Usopp", "anime": "One Piece", "gender": "Male", "favorites": 700},
            {"name": "Mineta", "anime": "My Hero Academia", "gender": "Male", "favorites": 300},
            {"name": "Sakura Haruno", "anime": "Naruto", "gender": "Female", "favorites": 900},
            # Uncommon characters (25%)
            {"name": "Rock Lee", "anime": "Naruto", "gender": "Male", "favorites": 2000},
            {"name": "Shikamaru", "anime": "Naruto", "gender": "Male", "favorites": 3000},
            {"name": "Yamcha", "anime": "Dragon Ball", "gender": "Male", "favorites": 1500},
            {"name": "Nami", "anime": "One Piece", "gender": "Female", "favorites": 4000},
            # Rare characters (15%)
            {"name": "Kakashi", "anime": "Naruto", "gender": "Male", "favorites": 8000},
            {"name": "Vegeta", "anime": "Dragon Ball", "gender": "Male", "favorites": 12000},
            {"name": "Zoro", "anime": "One Piece", "gender": "Male", "favorites": 15000},
            {"name": "Hinata Hyuga", "anime": "Naruto", "gender": "Female", "favorites": 10000},
            # Epic characters (7%)
            {"name": "Levi Ackerman", "anime": "Attack on Titan", "gender": "Male", "favorites": 25000},
            {"name": "Yor Forger", "anime": "Spy x Family", "gender": "Female", "favorites": 30000},
            {"name": "Loid Forger", "anime": "Spy x Family", "gender": "Male", "favorites": 28000},
            # Legendary characters (3%) - rare to get!
            {"name": "Goku", "anime": "Dragon Ball", "gender": "Male", "favorites": 80000},
            {"name": "Naruto Uzumaki", "anime": "Naruto", "gender": "Male", "favorites": 90000},
            {"name": "Luffy", "anime": "One Piece", "gender": "Male", "favorites": 85000},
            {"name": "Anya Forger", "anime": "Spy x Family", "gender": "Female", "favorites": 100000},
            {"name": "Mikasa Ackerman", "anime": "Attack on Titan", "gender": "Female", "favorites": 75000},
        ]
        
        # Assign rarity using the realistic distribution
        fallback_chars = []
        for char in fallback_pool:
            char_copy = char.copy()
            char_copy["rarity"] = self.get_gacha_rarity(char.get("favorites", 0))
            fallback_chars.append(char_copy)
        
        # Filter fallbacks by gender if needed
        if gender_filter:
            fallback_chars = [c for c in fallback_chars if c["gender"] == gender_filter]
        
        while len(characters) < count:
            fallback = random.choice(fallback_chars).copy()
            fallback["id"] = random.randint(100000, 999999)
            characters.append(fallback)
        
        return characters[:count]
    
    async def add_character_to_inventory(self, user_id: str, guild_id: str, character: dict):
        """Add a character to user's inventory in MongoDB."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            char_data = {
                "id": character.get("id", random.randint(1, 999999)),
                "name": character.get("name"),
                "anime": character.get("anime"),
                "image_url": character.get("image_url"),
                "rarity": character.get("rarity", "common"),
                "gender": character.get("gender", "Unknown"),
                "claimed_at": datetime.now(timezone.utc).isoformat(),
            }
            
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$push": {f"members.{user_id}.gacha_inventory": char_data}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error adding character to inventory: {e}")
    
    async def get_user_inventory(self, user_id: str, guild_id: str) -> list:
        """Get user's character inventory from MongoDB."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            server_data = await server_col.find_one({"guild_id": guild_id})
            if server_data and "members" in server_data:
                member_data = server_data["members"].get(user_id, {})
                return member_data.get("gacha_inventory", [])
        except Exception as e:
            logger.error(f"Error fetching inventory: {e}")
        
        return []
    
    async def check_character_ownership(self, guild: discord.Guild, characters: list) -> dict:
        """Check if any characters are already owned by members in this server.
        
        Returns dict mapping character index to owner info (user_id, username, avatar_url)
        """
        ownership = {}
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            guild_id = str(guild.id)
            
            server_data = await server_col.find_one({"guild_id": guild_id})
            if not server_data or "members" not in server_data:
                return ownership
            
            # Check each character against all member inventories
            for i, char in enumerate(characters):
                char_name = char.get("name", "").lower()
                char_id = char.get("id")
                
                for user_id, member_data in server_data.get("members", {}).items():
                    inventory = member_data.get("gacha_inventory", [])
                    
                    for owned_char in inventory:
                        # Match by ID or name
                        if (owned_char.get("id") == char_id or 
                            owned_char.get("name", "").lower() == char_name):
                            
                            # Try to get the member info
                            try:
                                member = guild.get_member(int(user_id))
                                if member:
                                    ownership[i] = {
                                        "user_id": user_id,
                                        "username": member.display_name,
                                        "avatar_url": member.display_avatar.url if member.display_avatar else None
                                    }
                                    break
                            except:
                                pass
                    
                    if i in ownership:
                        break
                        
        except Exception as e:
            logger.debug(f"Error checking ownership: {e}")
        
        return ownership
    
    @commands.group(name="game", aliases=["games"], invoke_without_command=True)
    async def game(self, ctx):
        """🎮 Play mini-games to win stella points!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Get user character for bonus display
        character = await self.get_user_character(user_id, guild_id)
        balance = await self.quest_data.get_balance(user_id, guild_id)
        
        embed = discord.Embed(
            title="🎮 Anya's Game Corner",
            description=f"*Waku waku!* Play games to win stella points!\n\n"
                        f"💰 **Balance:** {balance:,} stella points",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        
        if character:
            embed.description += f"\n🌟 **Character:** {character}"
        
        # Gambling Games
        embed.add_field(
            name="🎰 **GAMBLING**",
            value=f"`{ctx.prefix}slots <bet>` - Slot Machine\n"
                  f"`{ctx.prefix}coinflip <bet> <h/t>` - Flip a Coin\n"
                  f"`{ctx.prefix}guess <bet>` - Number Guess",
            inline=False
        )
        
        # Card Games
        embed.add_field(
            name="🃏 **CARD DRAWS**",
            value=f"`{ctx.prefix}game pokemon` - 100 pts\n"
                  f"`{ctx.prefix}game anime` - 100 pts",
            inline=True
        )
        
        # Classic Games
        embed.add_field(
            name="**CLASSIC**",
            value=f"`{ctx.prefix}hangman` - Word Game\n"
                  f"`{ctx.prefix}wordle` - 5-Letter Puzzle",
            inline=True
        )
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        # Grounded/Economy Games
        embed.add_field(
            name="💼 **GROUNDED** (Spy x Family)",
            value=f"`{ctx.prefix}work` - Earn points\n"
                  f"`{ctx.prefix}job` - Risky mission\n"
                  f"`{ctx.prefix}rob @user` - Steal points\n"
                  f"`{ctx.prefix}claim` - Daily reward",
            inline=False
        )
        
        embed.set_footer(text="💡 Get a character from .shop for bonuses!")
        await ctx.reply(embed=embed, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # GAMBLING GAMES
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="slots", aliases=["slot", "spin"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def slots_command(self, ctx, bet: int = 50):
        """🎰 Spin the slot machine! Match symbols to win big."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check daily limit
        daily_plays = await self._get_daily_game_plays(user_id, guild_id, "slots")
        if daily_plays >= DAILY_LIMITS["slots"]:
            return await ctx.reply(f"❌ Daily limit reached! You've played **{daily_plays}/{DAILY_LIMITS['slots']}** times today. Try again tomorrow!", mention_author=False)
        
        # Validate bet
        if bet < 10:
            return await ctx.reply("❌ Minimum bet is **10** stella points!", mention_author=False)
        if bet > 10000:
            return await ctx.reply("❌ Maximum bet is **10,000** stella points!", mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ You need **{bet:,}** but only have **{balance:,}** stella points!", mention_author=False)
        
        # Increment daily play count
        await self._increment_daily_game_plays(user_id, guild_id, "slots")
        
        await self._run_slot_machine(ctx.channel, ctx.author, bet)
    
    def _generate_slot_gif(self, results: list) -> io.BytesIO:
        """Generate hyper-realistic slot machine GIF with physics-based animation"""
        import math
        
        frames = []
        durations = []
        all_symbols = list(SLOT_SYMBOLS.keys())
        num_symbols = len(all_symbols)
        
        # Determine result type for outline colors
        is_jackpot = results[0] == results[1] == results[2]
        is_two_match = (results[0] == results[1] or results[1] == results[2] or results[0] == results[2]) and not is_jackpot
        
        # Dimensions
        width, height = 360, 140
        reel_width = 80
        reel_height = 90
        symbol_height = 45  # Height per symbol in the reel strip
        reel_y = 25
        reel_positions = [40, 140, 240]
        
        # Colors
        bg_dark = (15, 12, 20)
        frame_gold = (200, 170, 60)
        frame_shadow = (90, 75, 35)
        reel_bg = (5, 5, 10)
        
        # Result colors
        if is_jackpot:
            result_color = (255, 215, 0)
            result_glow = (255, 255, 120)
        elif is_two_match:
            result_color = (50, 220, 50)
            result_glow = (120, 255, 120)
        else:
            result_color = (200, 50, 50)
            result_glow = (255, 100, 100)
        
        # Load font
        try:
            font = ImageFont.truetype("data/assets/fonts/seguiemj.ttf", 28)
        except:
            try:
                font = ImageFont.truetype("data/assets/fonts/arial.ttf", 28)
            except:
                font = ImageFont.load_default()
        
        # Physics: each reel has its own spin state
        # Reel positions are in "symbol units" (0 = first symbol at center)
        # We'll track continuous position and velocity for each reel
        
        # Find the index of each result symbol
        result_indices = []
        for r in results:
            result_indices.append(all_symbols.index(r))
        
        # Animation parameters - smoother physics
        initial_velocity = 18.0  # symbols per second at start
        
        # Each reel stops at different times
        reel_stop_times = [1.6, 2.6, 3.8]  # seconds
        
        # Higher fps for smoother animation
        fps = 30
        total_duration = 5.0  # seconds
        total_frames = int(total_duration * fps)
        
        # Initialize reel states - track target position for smooth landing
        reel_positions_anim = [0.0, 0.0, 0.0]  # Current position in symbol units
        reel_velocities = [initial_velocity, initial_velocity, initial_velocity]
        reel_stopped = [False, False, False]
        reel_landing = [False, False, False]  # True when easing into final position
        
        for frame_idx in range(total_frames):
            current_time = frame_idx / fps
            
            img = Image.new('RGB', (width, height), bg_dark)
            draw = ImageDraw.Draw(img)
            
            # Draw machine frame with 3D effect
            # Outer shadow
            draw.rounded_rectangle([3, 3, width-1, height-1], radius=15, fill=frame_shadow)
            # Main frame
            draw.rounded_rectangle([0, 0, width-4, height-4], radius=15, fill=bg_dark, outline=frame_gold, width=4)
            # Inner highlight
            draw.rounded_rectangle([8, 8, width-12, height-12], radius=12, outline=(40, 35, 50), width=1)
            
            # Update physics for each reel
            for reel_idx in range(3):
                stop_time = reel_stop_times[reel_idx]
                target_pos = result_indices[reel_idx]
                
                if reel_stopped[reel_idx]:
                    # Already stopped - stay at target
                    reel_positions_anim[reel_idx] = target_pos
                    reel_velocities[reel_idx] = 0
                elif current_time >= stop_time - 0.4 and not reel_landing[reel_idx]:
                    # Start landing phase - smooth ease to target
                    reel_landing[reel_idx] = True
                
                if reel_landing[reel_idx] and not reel_stopped[reel_idx]:
                    # Smooth interpolation to target position
                    landing_progress = (current_time - (stop_time - 0.4)) / 0.4
                    landing_progress = min(1.0, max(0.0, landing_progress))
                    
                    # Smooth step function (ease in-out)
                    smooth = landing_progress * landing_progress * (3 - 2 * landing_progress)
                    
                    # Get current spinning position
                    spin_pos = reel_positions_anim[reel_idx]
                    
                    # Interpolate toward target
                    # Make sure we approach from the right direction (wrapping)
                    diff = target_pos - (spin_pos % num_symbols)
                    if diff < -num_symbols / 2:
                        diff += num_symbols
                    elif diff > num_symbols / 2:
                        diff -= num_symbols
                    
                    reel_positions_anim[reel_idx] = spin_pos + diff * smooth * 0.15
                    reel_velocities[reel_idx] = initial_velocity * (1 - smooth) * 0.3
                    
                    if landing_progress >= 1.0:
                        reel_stopped[reel_idx] = True
                        reel_positions_anim[reel_idx] = target_pos
                        reel_velocities[reel_idx] = 0
                        
                elif not reel_landing[reel_idx]:
                    # Normal spinning with gradual slowdown
                    time_to_landing = (stop_time - 0.4) - current_time
                    if time_to_landing < 0.8:
                        # Gradual slowdown before landing
                        ease = time_to_landing / 0.8
                        ease = 0.4 + ease * 0.6  # Never go below 40% speed
                        current_vel = initial_velocity * ease
                    else:
                        current_vel = initial_velocity
                    
                    reel_velocities[reel_idx] = current_vel
                    reel_positions_anim[reel_idx] += current_vel / fps
                    
                    # Wrap position
                    reel_positions_anim[reel_idx] = reel_positions_anim[reel_idx] % num_symbols
            
            # Draw each reel
            for reel_idx, x in enumerate(reel_positions):
                # Reel background with depth
                draw.rounded_rectangle([x-3, reel_y-3, x + reel_width+3, reel_y + reel_height+3], 
                                       radius=8, fill=(3, 3, 6))
                draw.rounded_rectangle([x, reel_y, x + reel_width, reel_y + reel_height], 
                                       radius=6, fill=reel_bg)
                
                # Create a clipping region for the reel
                reel_center_y = reel_y + reel_height // 2
                
                # Get current position
                pos = reel_positions_anim[reel_idx]
                is_stopped = reel_stopped[reel_idx]
                velocity = reel_velocities[reel_idx]
                
                # Draw 3 symbols: above, center, below
                for offset in [-1, 0, 1]:
                    symbol_idx = int(pos + offset) % num_symbols
                    symbol = all_symbols[symbol_idx]
                    
                    # Calculate y position based on fractional position
                    frac = pos - int(pos)
                    symbol_y = reel_center_y + (offset - frac) * symbol_height
                    
                    # Only draw if visible in reel window
                    if reel_y - symbol_height < symbol_y < reel_y + reel_height + symbol_height:
                        symbol_color = SLOT_SYMBOL_COLORS.get(symbol, (255, 255, 255))
                        
                        # Motion blur effect when spinning fast
                        if velocity > 5 and not is_stopped:
                            # Fade based on speed
                            fade = max(0.3, 1.0 - (velocity / initial_velocity) * 0.6)
                            symbol_color = tuple(int(c * fade) for c in symbol_color)
                        
                        # Center symbol in reel
                        bbox = draw.textbbox((0, 0), symbol, font=font)
                        text_w = bbox[2] - bbox[0]
                        text_x = x + (reel_width - text_w) // 2
                        text_y = int(symbol_y - symbol_height // 2 + 5)
                        
                        # Only draw center symbol with full opacity, others faded
                        if offset == 0 and is_stopped:
                            # Glow effect for stopped center symbol
                            glow = tuple(min(255, int(c * 0.4)) for c in symbol_color)
                            for glow_offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                draw.text((text_x + glow_offset[0], text_y + glow_offset[1]), 
                                         symbol, font=font, fill=glow)
                        
                        draw.text((text_x, text_y), symbol, font=font, fill=symbol_color)
                
                # Reel window overlay - gradient fade at top and bottom
                for i in range(12):
                    alpha = int((12 - i) / 12 * 200)
                    fade_color = (bg_dark[0], bg_dark[1], bg_dark[2])
                    # Top fade
                    draw.line([(x, reel_y + i), (x + reel_width, reel_y + i)], 
                             fill=tuple(int(c * (1 - i/12)) for c in fade_color), width=1)
                    # Bottom fade
                    draw.line([(x, reel_y + reel_height - i), (x + reel_width, reel_y + reel_height - i)], 
                             fill=tuple(int(c * (1 - i/12)) for c in fade_color), width=1)
                
                # Result highlight when stopped
                if is_stopped:
                    draw.rounded_rectangle([x-1, reel_y-1, x + reel_width+1, reel_y + reel_height+1], 
                                           radius=7, outline=result_color, width=2)
            
            # Center payline indicator
            line_y = reel_y + reel_height // 2
            # Left arrow
            draw.polygon([(32, line_y), (18, line_y - 10), (18, line_y + 10)], fill=frame_gold)
            # Right arrow
            draw.polygon([(width - 32, line_y), (width - 18, line_y - 10), (width - 18, line_y + 10)], fill=frame_gold)
            # Payline
            draw.line([(35, line_y), (width - 35, line_y)], fill=(frame_gold[0]//3, frame_gold[1]//3, frame_gold[2]//3), width=1)
            
            frames.append(img)
            
            # Consistent frame timing for smooth playback (33ms = ~30fps)
            durations.append(33)
        
        # Add final hold frames to show result
        for _ in range(12):
            frames.append(frames[-1])
            durations.append(120)
        
        # Save GIF
        gif_buffer = io.BytesIO()
        frames[0].save(
            gif_buffer,
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0  # Loop forever so user can watch again
        )
        gif_buffer.seek(0)
        return gif_buffer
    
    async def _run_slot_machine(self, channel, user, bet: int):
        """Run the slot machine game with anticipation-building progressive reveals"""
        guild_id = str(channel.guild.id)
        user_id = str(user.id)
        
        # Get balance before deducting
        balance = await self.quest_data.get_balance(user_id, guild_id)
        
        # Deduct bet
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Pre-generate final results
        results = [self.get_slot_symbol() for _ in range(3)]
        
        # Generate the GIF in background while spinning
        gif_task = asyncio.get_event_loop().run_in_executor(
            None, self._generate_slot_gif, results
        )
        
        # Simple spinning message
        spin_embed = discord.Embed(
            title="🎰 Slot Machine",
            description=f"**{user.display_name}** is spinning...\n💰 Bet: **{bet:,}** pts",
            color=discord.Color.blue()
        )
        spin_msg = await channel.send(embed=spin_embed)
        
        # Wait for gif to be ready
        gif_buffer = await gif_task
        
        # Determine outcome
        winnings = 0
        if results[0] == results[1] == results[2]:
            # JACKPOT!
            multiplier = SLOT_SYMBOLS[results[0]]["multiplier"]
            winnings = bet * multiplier
            final_title = "🎰 Jackpot!"
            final_color = discord.Color.gold()
        elif results[0] == results[1] or results[1] == results[2] or results[0] == results[2]:
            # Two match
            winnings = int(bet * 1.5)
            final_title = "🎰 Double Match!"
            final_color = discord.Color.green()
        else:
            final_title = "🎰 No Match"
            final_color = discord.Color.red()
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        # Create clean final embed with GIF
        final_embed = discord.Embed(
            title=final_title,
            #description=f"{results[0]} {results[1]} {results[2]}",
            color=final_color
        )
        
        if profit > 0:
            final_embed.add_field(name="Won", value=f"+{profit:,} pts", inline=True)
        else:
            final_embed.add_field(name="Lost", value=f"{abs(profit):,} pts", inline=True)
        
        final_embed.add_field(name="Balance", value=f"{new_balance:,} pts", inline=True)
        final_embed.set_image(url="attachment://slots.gif")
        
        # Create view with Play Again button
        view = SlotMachineView(self, user_id, guild_id, bet, results)
        
        file = discord.File(gif_buffer, filename="slots.gif")
        await spin_msg.edit(embed=final_embed, attachments=[file], view=view)
    
    def parse_bet(self, bet_str: str) -> int:
        """Parse a bet string that may contain commas (e.g., '5,000' -> 5000)."""
        if bet_str is None:
            return 50
        # Remove commas and convert to int
        cleaned = str(bet_str).replace(",", "").replace(" ", "")
        return int(cleaned)
    
    @commands.command(name="coinflip", aliases=["cf", "flip"])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def coinflip_command(self, ctx, bet: str = "50", choice: str = None):
        """🪙 Flip a coin! Call heads or tails to double your bet."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if choice is None:
            embed = discord.Embed(
                title="🪙 Coin Flip",
                description=f"**How to play:**\n"
                           f"`{ctx.prefix}coinflip <bet> <heads/tails>`\n\n"
                           f"Call it right and **double** your bet!\n\n"
                           f"**Example:** `{ctx.prefix}coinflip 100 heads`",
                color=discord.Color.gold()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Parse bet (handles commas like "5,000")
        try:
            bet = self.parse_bet(bet)
        except ValueError:
            return await ctx.reply("❌ Invalid bet amount! Use numbers like `100` or `5,000`", mention_author=False)
        
        # Normalize choice
        choice = choice.lower()
        if choice in ["h", "head", "heads"]:
            choice = "heads"
        elif choice in ["t", "tail", "tails"]:
            choice = "tails"
        else:
            return await ctx.reply("❌ Choose **heads** or **tails**!", mention_author=False)
        
        # Validate bet
        if bet < 10:
            return await ctx.reply("❌ Minimum bet is **10** stella points!", mention_author=False)
        if bet > 5000:
            return await ctx.reply("❌ Maximum bet is **5,000** stella points!", mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ You need **{bet:,}** but only have **{balance:,}** stella points!", mention_author=False)
        
        # Deduct bet
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Flip!
        result = random.choice(["heads", "tails"])
        won = result == choice
        
        # Generate coin flip GIF
        gif_buffer = generate_coinflip_gif(result)
        file = discord.File(gif_buffer, filename="coinflip.gif")
        
        # Send spinning message first
        spin_embed = discord.Embed(
            title="🪙 Flipping...",
            description=f"You called **{choice.upper()}**!",
            color=discord.Color.gold()
        )
        spin_embed.set_image(url="attachment://coinflip.gif")
        msg = await ctx.reply(embed=spin_embed, file=file, mention_author=False)
        
        # Wait for animation
        await asyncio.sleep(1.2)
        
        if won:
            winnings = bet * 2
            await self.quest_data.add_balance(user_id, guild_id, winnings)
            profit = bet
            title = "🎉 You Won!"
            color = discord.Color.green()
            result_emoji = "👑" if result == "heads" else "🦅"
        else:
            winnings = 0
            profit = -bet
            title = "💸 You Lost!"
            color = discord.Color.red()
            result_emoji = "👑" if result == "heads" else "🦅"
        
        new_balance = balance - bet + winnings
        
        embed = discord.Embed(
            title=title,
            description=f"{result_emoji} The coin landed on **{result.upper()}**!\n"
                       f"You called **{choice}**.",
            color=color
        )
        
        if profit > 0:
            embed.add_field(name="💰 Won", value=f"+**{profit:,}** pts", inline=True)
        else:
            embed.add_field(name="📉 Lost", value=f"**{profit:,}** pts", inline=True)
        
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        # Add Double or Nothing for winners
        if won:
            view = DoubleOrNothingView(self, user_id, guild_id, profit)
            embed.set_footer(text="Double your winnings or cash out!")
            await msg.edit(embed=embed, view=view)
        else:
            await msg.edit(embed=embed)
    
    @commands.command(name="dice", aliases=["roll", "d6"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def dice_command(self, ctx, bet: str = "50", guess: int = None):
        """🎲 Roll the dice! Guess 1-6 to win big."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if guess is None:
            embed = discord.Embed(
                title="🎲 Dice Game",
                description=f"**How to play:**\n"
                           f"`{ctx.prefix}dice <bet> <guess>`\n\n"
                           f"Guess the exact number for **5x** your bet!\n"
                           f"Off by 1 = **2x** your bet\n\n"
                           f"**Example:** `{ctx.prefix}dice 100 4`",
                color=discord.Color.blue()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Parse bet
        try:
            bet = self.parse_bet(bet)
        except ValueError:
            return await ctx.reply("❌ Invalid bet amount!", mention_author=False)
        
        if guess < 1 or guess > 6:
            return await ctx.reply("❌ Guess between **1** and **6**!", mention_author=False)
        if bet < 10 or bet > 5000:
            return await ctx.reply("❌ Bet between **10** and **5,000** pts!", mention_author=False)
        
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ Need **{bet:,}** but have **{balance:,}** pts!", mention_author=False)
        
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Roll!
        roll = random.randint(1, 6)
        
        # Generate dice GIF
        gif_buffer = generate_dice_gif(roll)
        file = discord.File(gif_buffer, filename="dice.gif")
        
        # Send rolling message first
        roll_embed = discord.Embed(
            title="🎲 Rolling...",
            description=f"You guessed **{guess}**!",
            color=discord.Color.blue()
        )
        roll_embed.set_image(url="attachment://dice.gif")
        msg = await ctx.reply(embed=roll_embed, file=file, mention_author=False)
        
        # Wait for animation
        await asyncio.sleep(1.3)
        
        # Calculate winnings
        diff = abs(roll - guess)
        if diff == 0:
            winnings = bet * 5
            result = "🎯 **PERFECT!**"
            color = discord.Color.gold()
        elif diff == 1:
            winnings = bet * 2
            result = "✨ **Close!**"
            color = discord.Color.green()
        else:
            winnings = 0
            result = "💨 **Miss!**"
            color = discord.Color.red()
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        dice_faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
        
        embed = discord.Embed(
            title=result,
            description=f"{dice_faces[roll]} Rolled **{roll}** | You guessed **{guess}**",
            color=color
        )
        
        if profit > 0:
            embed.add_field(name="💰 Won", value=f"+**{profit:,}** pts", inline=True)
        else:
            embed.add_field(name="📉 Lost", value=f"**{profit:,}** pts", inline=True)
        
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await msg.edit(embed=embed)
    
    @commands.command(name="guess", aliases=["number", "guessnumber"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def guess_command(self, ctx, bet: int = 50):
        """🔢 Guess a number 1-100! Closer guesses win more."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check daily limit
        daily_plays = await self._get_daily_game_plays(user_id, guild_id, "guess")
        if daily_plays >= DAILY_LIMITS["guess"]:
            return await ctx.reply(f"❌ Daily limit reached! You've played **{daily_plays}/{DAILY_LIMITS['guess']}** times today. Try again tomorrow!", mention_author=False)
        
        # Validate bet
        if bet < 20:
            return await ctx.reply("❌ Minimum bet is **20** stella points!", mention_author=False)
        if bet > 5000:
            return await ctx.reply("❌ Maximum bet is **5,000** stella points!", mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ You need **{bet:,}** but only have **{balance:,}** stella points!", mention_author=False)
        
        # Increment daily play count
        await self._increment_daily_game_plays(user_id, guild_id, "guess")
        
        # Deduct bet upfront - no refunds!
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Generate secret number
        secret = random.randint(1, 100)
        attempts_left = 3
        guesses_list = []
        
        # Generate initial thermometer
        img_buffer = generate_guess_thermometer([], secret, attempts_left)
        file = discord.File(img_buffer, filename="guess.png")
        
        embed = discord.Embed(
            title="🔢 Number Guessing",
            description=f"Guess a number between **1-100**\nBet: **{bet:,}** pts",
            color=discord.Color.orange()
        )
        embed.set_image(url="attachment://guess.png")
        msg = await ctx.reply(embed=embed, file=file, mention_author=False)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
        
        perfect_win = False
        while attempts_left > 0:
            try:
                guess_msg = await self.bot.wait_for("message", timeout=45.0, check=check)
                guess = int(guess_msg.content)
                
                if guess < 1 or guess > 100:
                    await ctx.send("Please guess between 1-100!", delete_after=3)
                    continue
                
                guesses_list.append(guess)
                attempts_left -= 1
                diff = abs(secret - guess)
                
                if diff == 0:
                    # Perfect guess!
                    perfect_win = True
                    winnings = bet * 5
                    await self.quest_data.add_balance(user_id, guild_id, winnings)
                    new_balance = balance - bet + winnings
                    
                    # Generate result image
                    img_buffer = generate_guess_result_image(guesses_list, secret, True, winnings - bet)
                    file = discord.File(img_buffer, filename="guess_result.png")
                    
                    embed = discord.Embed(
                        title="🎯 PERFECT!",
                        description=f"You got it in **{len(guesses_list)}** {'guess' if len(guesses_list) == 1 else 'guesses'}!\n"
                                   f"💰 Won: **+{winnings - bet:,}** pts\n💳 Balance: **{new_balance:,}** pts",
                        color=discord.Color.gold()
                    )
                    embed.set_image(url="attachment://guess_result.png")
                    return await msg.edit(embed=embed, attachments=[file])
                
                # Update thermometer with guess
                img_buffer = generate_guess_thermometer(guesses_list, secret, attempts_left)
                file = discord.File(img_buffer, filename="guess.png")
                
                # Temperature hint
                if diff <= 5:
                    temp = "🔥 **HOT!**"
                elif diff <= 15:
                    temp = "🌡️ Warm"
                elif diff <= 30:
                    temp = "☀️ Getting there"
                else:
                    temp = "❄️ Cold"
                
                direction = "⬆️ Higher" if guess < secret else "⬇️ Lower"
                
                embed = discord.Embed(
                    title="🔢 Number Guessing",
                    description=f"Your guess: **{guess}** → {direction}\n{temp}\n\n"
                               f"Attempts left: **{attempts_left}**",
                    color=discord.Color.orange()
                )
                embed.set_image(url="attachment://guess.png")
                await msg.edit(embed=embed, attachments=[file])
                
            except asyncio.TimeoutError:
                break
        
        # Game over - much stricter partial winnings
        if guesses_list:
            closest = min(guesses_list, key=lambda x: abs(x - secret))
            diff = abs(closest - secret)
            
            if diff == 1:
                winnings = bet * 2
            elif diff <= 3:
                winnings = int(bet * 1.2)
            else:
                winnings = 0
        else:
            winnings = 0
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        # Generate result image
        img_buffer = generate_guess_result_image(guesses_list, secret, False, profit)
        file = discord.File(img_buffer, filename="guess_result.png")
        
        embed = discord.Embed(
            title="💀 Game Over" if profit <= 0 else "✅ Close!",
            description=f"The number was **{secret}**\n"
                       f"{'📉 Lost' if profit <= 0 else '💰 Won'}: **{profit:+,}** pts\n"
                       f"💳 Balance: **{new_balance:,}** pts",
            color=discord.Color.green() if profit > 0 else discord.Color.red()
        )
        embed.set_image(url="attachment://guess_result.png")
        await msg.edit(embed=embed, attachments=[file])
    
    # ═══════════════════════════════════════════════════════════════
    # CARD DRAW GAMES (kept from original)
    # ═══════════════════════════════════════════════════════════════
    
    @game.command(name="pokemon", aliases=["poke", "pkm"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pokemon_draw(self, ctx):
        """🃏 Draw a random Pokémon card for 100 points."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cost = 100
        
        # Check daily limit
        plays_today = await self.get_daily_plays(user_id, guild_id, "pokemon")
        if plays_today >= DAILY_LIMITS["pokemon"]:
            embed = discord.Embed(
                title="⏰ Daily Limit Reached!",
                description=f"You've used all **{DAILY_LIMITS['pokemon']}** Pokémon draws today.\n"
                           f"Come back tomorrow!",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            embed = discord.Embed(
                title="❌ Not Enough Points!",
                description=f"You need **{cost}** stella points but only have **{balance:,}**.\n"
                           f"Complete quests to earn more!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Deduct cost and increment plays
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        await self.increment_daily_plays(user_id, guild_id, "pokemon")
        
        # Random rarity (gacha-style)
        rarity = self.get_random_rarity()
        rarity_data = RARITY_CONFIG[rarity]
        reward = cost * rarity_data["multiplier"]
        
        # Fetch Pokemon info
        pokemon_id = random.randint(1, 1025)
        pokemon = await self.fetch_pokemon_info(pokemon_id)
        
        # Add reward
        await self.quest_data.add_balance(user_id, guild_id, reward)
        new_balance = balance - cost + reward
        profit = reward - cost
        
        # Generate card image
        if pokemon:
            types_str = " / ".join(pokemon["types"])
            card_buffer = await generate_card_image(
                name=pokemon["name"],
                subtitle=types_str,
                rarity=rarity,
                sprite_url=pokemon["sprite"],
                multiplier=rarity_data["multiplier"],
                card_type="pokemon"
            )
        else:
            card_buffer = await generate_card_image(
                name=f"Mystery #{pokemon_id}",
                subtitle="Unknown Type",
                rarity=rarity,
                multiplier=rarity_data["multiplier"],
                card_type="pokemon"
            )
        
        file = discord.File(card_buffer, filename="pokemon_card.png")
        
        embed = discord.Embed(
            title="🃏 Pokémon Card Draw",
            color=rarity_data["color"]
        )
        embed.set_image(url="attachment://pokemon_card.png")
        
        result_name = "💰 Won" if profit > 0 else "📉 Result"
        embed.add_field(name=result_name, value=f"**{profit:+,}** pts", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        plays_left = DAILY_LIMITS["pokemon"] - plays_today - 1
        embed.set_footer(text=f"Draws left today: {plays_left}")
        await ctx.reply(embed=embed, file=file, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # ANIME GACHA - DRAW COMMANDS (Group)
    # ═══════════════════════════════════════════════════════════════
    
    @commands.group(name="draw", aliases=["d"], invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw(self, ctx):
        """🎴 Draw anime characters! Use `.draw` to pull or `.draw help` for info."""
        await self._execute_draw(ctx, gender_filter=None)
    
    @draw.command(name="waifu", aliases=["w", "female", "girl"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw_waifu(self, ctx):
        """🎴 Draw only female characters (waifus)."""
        await self._execute_draw(ctx, gender_filter="Female")
    
    @draw.command(name="husbando", aliases=["h", "male", "boy"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw_husbando(self, ctx):
        """🎴 Draw only male characters (husbandos)."""
        await self._execute_draw(ctx, gender_filter="Male")
    
    @draw.command(name="collection", aliases=["c", "inv", "inventory"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw_collection(self, ctx, member: discord.Member = None):
        """📦 View your anime character collection."""
        target = member or ctx.author
        guild_id = str(ctx.guild.id)
        user_id = str(target.id)
        
        inventory = await self.get_user_inventory(user_id, guild_id)
        
        if not inventory:
            if target == ctx.author:
                embed = discord.Embed(
                    title="📦 Empty Collection",
                    description=f"You haven't collected any characters yet!\nUse `{ctx.prefix}draw` to start collecting.",
                    color=discord.Color.greyple()
                )
            else:
                embed = discord.Embed(
                    title="📦 Empty Collection",
                    description=f"**{target.display_name}** hasn't collected any characters yet!",
                    color=discord.Color.greyple()
                )
            return await ctx.reply(embed=embed, mention_author=False)
        
        view = InventoryView(self, target, guild_id, inventory, filter_type="all")
        await ctx.reply(embed=view.get_embed(), view=view, mention_author=False)
    
    @draw.command(name="info", aliases=["help", "rates", "?"])
    async def draw_info(self, ctx):
        """📊 Show gacha rates and command help."""
        embed = discord.Embed(
            title="🎴 Anime Gacha - Draw Info",
            description="Collect anime characters from 3 sources!",
            color=discord.Color.gold()
        )
        
        # Commands
        embed.add_field(
            name="📜 Commands",
            value=(
                f"`{ctx.prefix}draw` - Draw 3 random characters\n"
                f"`{ctx.prefix}draw waifu` - Draw female characters only\n"
                f"`{ctx.prefix}draw husbando` - Draw male characters only\n"
                f"`{ctx.prefix}draw collection` - View your collection\n"
                f"`{ctx.prefix}draw info` - This help menu"
            ),
            inline=False
        )
        
        # Rates
        embed.add_field(
            name="⭐ Rarity Rates",
            value=(
                "⚪ **Common** (1★) - 50%\n"
                "🟢 **Uncommon** (2★) - 25%\n"
                "🔵 **Rare** (3★) - 15%\n"
                "🟣 **Epic** (4★) - 7%\n"
                "🌟 **Legendary** (5★) - 3%"
            ),
            inline=True
        )
        
        # Cost info
        embed.add_field(
            name="💰 Cost & Limits",
            value=f"**{GACHA_COST}** pts per draw\n**{DAILY_LIMITS['gacha']}** draws per day",
            inline=True
        )
        
        embed.set_footer(text="Rarity is based on character popularity (favorites count)")
        await ctx.reply(embed=embed, mention_author=False)
    
    async def _execute_draw(self, ctx, gender_filter: str = None):
        """Core draw logic shared by all draw commands."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cost = GACHA_COST
        
        # Check daily limit
        plays_today = await self.get_daily_plays(user_id, guild_id, "gacha")
        if plays_today >= DAILY_LIMITS["gacha"]:
            return await ctx.reply(
                embed=discord.Embed(
                    title="⏰ Daily Limit!",
                    description=f"Used all **{DAILY_LIMITS['gacha']}** draws today.\nCome back tomorrow!",
                    color=discord.Color.orange()
                ), mention_author=False
            )
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            return await ctx.reply(f"❌ Need **{cost}** but have **{balance:,}** pts!", mention_author=False)
        
        # Deduct cost and increment plays
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        await self.increment_daily_plays(user_id, guild_id, "gacha")
        
        # Filter text for title
        filter_text = ""
        if gender_filter == "Female":
            filter_text = " ♀️ Waifu"
        elif gender_filter == "Male":
            filter_text = " ♂️ Husbando"
        
        # Fetch characters instantly
        characters = await self.fetch_gacha_characters(GACHA_CARDS_PER_DRAW, gender_filter=gender_filter)
        
        # Check ownership for each character
        ownership_info = await self.check_character_ownership(ctx.guild, characters)
        
        # Generate draw image with ownership info
        img_buffer = await generate_gacha_draw_image(characters, ownership_info=ownership_info)
        file = discord.File(img_buffer, filename="gacha_draw.png")
        
        # Send image directly without embed
        new_balance = balance - cost
        draws_left = DAILY_LIMITS['gacha'] - plays_today - 1
        content = f"**{ctx.author.display_name}**'s Draw | ⏱️ {GACHA_CLAIM_TIMEOUT}s | 💰 {new_balance:,} pts | 🎯 {draws_left} left"
        
        # Create claim view and send instantly
        view = GachaClaimView(self, ctx.author, guild_id, characters)
        msg = await ctx.reply(content=content, file=file, view=view, mention_author=False)
        view.message = msg

    # Keep old slots/dice as game subcommands for backwards compatibility
    @game.command(name="slots", hidden=True)
    async def game_slots(self, ctx, bet: int = 50):
        """Redirect to main slots command."""
        await ctx.invoke(self.slots_command, bet=bet)
    
    @game.command(name="dice", aliases=["roll"], hidden=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def dice_game(self, ctx, bet: int = 50, guess: int = None):
        """🎲 Guess the dice roll! Guess 1-6 to play."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if guess is None:
            embed = discord.Embed(
                title="🎲 Dice Game",
                description=f"`{ctx.prefix}game dice <bet> <guess>`\n\n"
                           f"Guess 1-6. Exact = **5x**, Off by 1 = **2x**",
                color=discord.Color.blue()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        if guess < 1 or guess > 6:
            return await ctx.reply("❌ Guess between **1** and **6**!", mention_author=False)
        if bet < 10 or bet > 5000:
            return await ctx.reply("❌ Bet between **10** and **5,000** pts!", mention_author=False)
        
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ Need **{bet:,}** but have **{balance:,}** pts!", mention_author=False)
        
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        roll = random.randint(1, 6)
        dice_faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
        
        diff = abs(roll - guess)
        if diff == 0:
            winnings = bet * 5
            result = "🎯 **PERFECT!**"
            color = discord.Color.gold()
        elif diff == 1:
            winnings = bet * 2
            result = "✨ **Close!**"
            color = discord.Color.green()
        else:
            winnings = 0
            result = "💨 **Miss!**"
            color = discord.Color.red()
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        embed = discord.Embed(title="🎲 Dice Game", color=color)
        embed.add_field(name="Roll", value=f"{dice_faces[roll]} **{roll}**", inline=True)
        embed.add_field(name="Guess", value=f"**{guess}**", inline=True)
        embed.add_field(name="Result", value=result, inline=False)
        embed.add_field(
            name="💰 Won" if profit > 0 else "📉 Lost",
            value=f"**{profit:+,}** pts",
            inline=True
        )
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await ctx.reply(embed=embed, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # MULTIPLAYER GAMES - HANGMAN
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="hangman", aliases=["hm"])
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def hangman_game(self, ctx):
        """Multiplayer Hangman! Play in DMs, results shown in channel."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check daily limit
        daily_plays = await self._get_daily_game_plays(user_id, guild_id, "hangman")
        if daily_plays >= DAILY_LIMITS["hangman"]:
            return await ctx.reply(f"❌ Daily limit reached! You've played **{daily_plays}/{DAILY_LIMITS['hangman']}** times today. Try again tomorrow!", mention_author=False)
        
        guild_id = str(ctx.guild.id)
        game_id = f"{guild_id}_{ctx.channel.id}_hangman_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Get word from API or fallback
        word = None
        try:
            session = await self.get_session()
            async with session.get("https://random-word-api.herokuapp.com/word") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data[0]) >= 4:
                        word = data[0].upper()
        except:
            pass
        
        if not word:
            fallback = CLASSIC_CONFIG.get("hangman", {}).get("fallback_words", [
                "MISSION", "SECRET", "AGENT", "FORGER", "TWILIGHT", "CIPHER", "PUZZLE", "MYSTERY"
            ])
            word = random.choice(fallback).upper()
        
        # Initialize multiplayer game
        self.active_games[game_id] = {
            "word": word,
            "players": {},
            "channel": ctx.channel,
            "guild_id": guild_id,
            "started": False,
            "game_msg": None
        }
        
        # Generate initial waiting room image
        host_avatar = None
        if ctx.author.avatar:
            async with aiohttp.ClientSession() as session:
                host_avatar = await fetch_avatar_bytes(session, ctx.author.avatar.url)
        
        img_buffer = await generate_waiting_room_image(
            game_name="HANGMAN",
            host_name=ctx.author.display_name,
            host_avatar_bytes=host_avatar,
            players=[],
            max_players=5,
            extra_info=f"{len(word)} letters • 6 lives"
        )
        
        file = discord.File(img_buffer, filename="hangman_lobby.png")
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_image(url="attachment://hangman_lobby.png")
        embed.set_footer(text="Game starts in 30 seconds or when full!")
        
        view = HangmanJoinView(self, game_id, host_user=ctx.author)
        msg = await ctx.reply(embed=embed, file=file, view=view, mention_author=False)
        self.active_games[game_id]["game_msg"] = msg
        
        # Wait for players
        await asyncio.sleep(30)
        
        if game_id in self.active_games:
            game = self.active_games[game_id]
            if len(game["players"]) == 0:
                embed.description = "❌ No players joined! Game cancelled."
                embed.color = discord.Color.red()
                await msg.edit(embed=embed, view=None)
                del self.active_games[game_id]
            else:
                game["started"] = True
                view.stop()
                await self._start_hangman_game(game_id)
    
    async def _start_hangman_game(self, game_id: str):
        """Start the multiplayer hangman game"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        channel = game["channel"]
        failed_users = []
        
        # Send DMs to all players
        for user_id, player_data in game["players"].items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                view = HangmanLetterView(self, game_id, user_id)
                
                word_display = " ".join("_" for _ in game["word"])
                embed = discord.Embed(
                    title="🕵️ Hangman",
                    description=f"{HANGMAN_STAGES[0]}\n**Word:** `{word_display}`",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Guessed", value="None", inline=True)
                embed.add_field(name="Wrong", value="0/6", inline=True)
                
                dm_msg = await user.send(embed=embed, view=view)
                player_data["dm_msg"] = dm_msg
                player_data["view"] = view
            except discord.Forbidden:
                logger.warning(f"Cannot DM user {user_id} - DMs disabled")
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    failed_users.append(user_obj.mention)
                except:
                    failed_users.append(f"<@{user_id}>")
                player_data["status"] = "failed"
            except Exception as e:
                logger.error(f"Error sending hangman DM to {user_id}: {e}")
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    failed_users.append(user_obj.mention)
                except:
                    failed_users.append(f"<@{user_id}>")
                player_data["status"] = "failed"
        
        # Notify about failed DMs with mentions
        if failed_users:
            try:
                await channel.send(
                    f"⚠️ {' '.join(failed_users)} - Could not send you DMs!\n"
                    f"Please enable DMs from server members to play!",
                    delete_after=15
                )
            except:
                pass
        
        # Update channel message
        await self._update_hangman_leaderboard(game_id)
    
    async def _update_hangman_leaderboard(self, game_id: str):
        """Update the leaderboard in the channel"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        msg = game["game_msg"]
        
        # Build leaderboard
        leaderboard = []
        for user_id, player_data in game["players"].items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                display = player_data["display"]
                wrong = player_data["wrong"]
                status = player_data["status"]
                
                if status == "won":
                    emoji = "🏆"
                elif status == "lost":
                    emoji = "💀"
                else:
                    emoji = "🎮"
                
                lives = "❤️" * (6 - wrong)
                leaderboard.append(f"{emoji} **{user.display_name}** - `{display}` {lives}")
            except:
                pass
        
        embed = discord.Embed(
            title="🕵️ Hangman - Live Results",
            description="\n".join(leaderboard) if leaderboard else "No players",
            color=discord.Color.blue()
        )
        embed.add_field(name="Word Length", value=f"{len(game['word'])} letters", inline=True)
        
        # Check if game is over
        all_done = all(p["status"] != "playing" for p in game["players"].values())
        if all_done:
            winners = [uid for uid, p in game["players"].items() if p["status"] == "won"]
            embed.add_field(name="Game Over!", value=f"Word was: **{game['word']}**", inline=False)
            if winners:
                embed.color = discord.Color.green()
            else:
                embed.color = discord.Color.red()
        
        try:
            await msg.edit(embed=embed)
        except:
            pass
    
    async def _end_hangman_game(self, game_id: str, winner_user_id: str):
        """End the hangman game when someone wins and notify all players"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        channel = game["channel"]
        
        try:
            # Get winner info
            winner = await self.bot.fetch_user(int(winner_user_id))
            winner_name = winner.display_name
            
            # Send notification to channel
            embed = discord.Embed(
                title="🏆 Hangman Game Won!",
                description=f"**{winner_name}** solved the word first!\n\n**Word:** `{game['word']}`\n\nGame ended automatically for all players.",
                color=discord.Color.green()
            )
            await channel.send(embed=embed)
            
            # End game for all remaining players
            for user_id, player_data in game["players"].items():
                if player_data["status"] == "playing":
                    player_data["status"] = "ended"
                    
                    # Update their DM to show game ended
                    try:
                        if player_data.get("dm_msg") and player_data.get("view"):
                            end_embed = discord.Embed(
                                title="🏁 Game Ended",
                                description=f"**{winner_name}** won the game!\n\n**Word was:** `{game['word']}`\n\nBetter luck next time!",
                                color=discord.Color.orange()
                            )
                            await player_data["dm_msg"].edit(embed=end_embed, view=None)
                    except Exception as e:
                        logger.error(f"Error updating DM for user {user_id}: {e}")
            
            # Final leaderboard update
            await self._update_hangman_leaderboard(game_id)
            
        except Exception as e:
            logger.error(f"Error ending hangman game {game_id}: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # MULTIPLAYER GAMES - WORDLE
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="wordle")
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def wordle_game(self, ctx):
        """🟩 Multiplayer Wordle! Play in DMs, results shown in channel."""
        guild_id = str(ctx.guild.id)
        game_id = f"{guild_id}_{ctx.channel.id}_wordle_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Get 5-letter word
        word = None
        try:
            session = await self.get_session()
            async with session.get("https://random-word-api.herokuapp.com/word?length=5") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        word = data[0].upper()
        except:
            pass
        
        if not word:
            fallback = ["AGENT", "CODES", "QUEST", "SWORD", "FLAME", "STORM", "PEACE", "DREAM", "MAGIC", "BRAVE"]
            word = random.choice(fallback)
        
        # Initialize multiplayer game
        self.active_games[game_id] = {
            "word": word,
            "players": {},
            "channel": ctx.channel,
            "guild_id": guild_id,
            "started": False,
            "game_msg": None
        }
        
        # Generate initial waiting room image
        host_avatar = None
        if ctx.author.avatar:
            async with aiohttp.ClientSession() as session:
                host_avatar = await fetch_avatar_bytes(session, ctx.author.avatar.url)
        
        img_buffer = await generate_waiting_room_image(
            game_name="WORDLE",
            host_name=ctx.author.display_name,
            host_avatar_bytes=host_avatar,
            players=[],
            max_players=5,
            extra_info="5-letter word • 6 attempts"
        )
        
        file = discord.File(img_buffer, filename="wordle_lobby.png")
        embed = discord.Embed(color=discord.Color.green())
        embed.set_image(url="attachment://wordle_lobby.png")
        embed.set_footer(text="Game starts in 30 seconds or when full!")
        
        view = WordleJoinView(self, game_id, host_user=ctx.author)
        msg = await ctx.reply(embed=embed, file=file, view=view, mention_author=False)
        self.active_games[game_id]["game_msg"] = msg
        
        # Wait for players
        await asyncio.sleep(30)
        
        if game_id in self.active_games:
            game = self.active_games[game_id]
            if len(game["players"]) == 0:
                embed.description = "❌ No players joined! Game cancelled."
                embed.color = discord.Color.red()
                await msg.edit(embed=embed, view=None)
                del self.active_games[game_id]
            else:
                game["started"] = True
                view.stop()
                await self._start_wordle_game(game_id)
    
    async def _start_wordle_game(self, game_id: str):
        """Start the multiplayer wordle game"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        channel = game["channel"]
        failed_users = []
        
        # Send DMs to all players with Pillow image
        for user_id, player_data in game["players"].items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                player_data["display_name"] = user.display_name
                view = WordleGuessView(self, game_id, user_id)
                
                # Fetch avatar for the image
                avatar_bytes = None
                try:
                    session = await self.get_session()
                    avatar_url = user.display_avatar.with_size(64).url
                    avatar_bytes = await fetch_avatar_bytes(session, avatar_url)
                    player_data["avatar_bytes"] = avatar_bytes
                except:
                    pass
                
                # Generate empty board image with avatar
                img_buffer = generate_wordle_board_image(
                    [], game["word"],
                    avatar_bytes=avatar_bytes, player_name=user.display_name
                )
                file = discord.File(img_buffer, filename="wordle_board.png")
                
                embed = discord.Embed(
                    title="🟩 Your Wordle Game",
                    description=f"Click **Submit Guess** to enter a 5-letter word!\n"
                               f"❌ Wrong guess = **-15 stella points**",
                    color=discord.Color.green()
                )
                embed.set_image(url="attachment://wordle_board.png")
                embed.add_field(name="Attempts", value="0/6", inline=True)
                
                dm_msg = await user.send(embed=embed, file=file, view=view)
                player_data["dm_msg"] = dm_msg
                player_data["view"] = view
            except discord.Forbidden:
                logger.warning(f"Cannot DM user {user_id} - DMs disabled")
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    failed_users.append(user_obj.mention)
                except:
                    failed_users.append(f"<@{user_id}>")
                player_data["status"] = "failed"
            except Exception as e:
                logger.error(f"Error sending wordle DM to {user_id}: {e}")
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    failed_users.append(user_obj.mention)
                except:
                    failed_users.append(f"<@{user_id}>")
                player_data["status"] = "failed"
        
        # Notify about failed DMs with mentions
        if failed_users:
            try:
                await channel.send(
                    f"⚠️ {' '.join(failed_users)} - Could not send you DMs!\n"
                    f"Please enable DMs from server members to play!",
                    delete_after=15
                )
            except:
                pass
        
        # Update channel message with live image
        await self._update_wordle_leaderboard(game_id)
    
    async def _end_wordle_game(self, game_id: str, winner_id: str):
        """End the wordle game when someone wins - stops for everyone and pings winner"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        channel = game["channel"]
        
        # Mark game as ended
        game["ended"] = True
        
        # Get winner info
        try:
            winner = await self.bot.fetch_user(int(winner_id))
            winner_mention = winner.mention
            winner_name = winner.display_name
        except:
            winner_mention = f"<@{winner_id}>"
            winner_name = "Unknown"
        
        # End game for all other players - delete old DM and send new final one
        for user_id, player_data in game["players"].items():
            if user_id == winner_id:
                continue
            
            if player_data["status"] == "playing":
                player_data["status"] = "ended"
            
            # Delete old DM and send new final embed
            try:
                dm_msg = player_data.get("dm_msg")
                if dm_msg:
                    # Delete the old message
                    try:
                        await dm_msg.delete()
                    except:
                        pass
                    
                    # Send new final message
                    avatar_bytes = player_data.get("avatar_bytes")
                    player_name = player_data.get("display_name", "Player")
                    
                    img_buffer = generate_wordle_board_image(
                        player_data["attempts"], 
                        game["word"], 
                        show_word=True,
                        avatar_bytes=avatar_bytes,
                        player_name=player_name
                    )
                    file = discord.File(img_buffer, filename="wordle_final.png")
                    
                    embed = discord.Embed(
                        title="🏁 Game Over!",
                        description=f"**Word was:** {game['word']}",
                        color=discord.Color.orange()
                    )
                    embed.set_image(url="attachment://wordle_final.png")
                    
                    # Get user to send DM
                    try:
                        user = await self.bot.fetch_user(int(user_id))
                        await user.send(
                            content=f"🏆 **{winner_name}** won the Wordle game!",
                            embed=embed,
                            file=file
                        )
                    except:
                        pass
            except Exception as e:
                logger.error(f"Error updating DM for {user_id}: {e}")
        
        # Also update winner's DM - delete old and send new
        winner_data = game["players"].get(winner_id)
        if winner_data:
            try:
                dm_msg = winner_data.get("dm_msg")
                if dm_msg:
                    try:
                        await dm_msg.delete()
                    except:
                        pass
            except:
                pass
        
        # Generate final live image showing all boards
        players_with_names = {}
        for uid, pdata in game["players"].items():
            players_with_names[uid] = pdata.copy()
            if "display_name" not in players_with_names[uid]:
                try:
                    user = await self.bot.fetch_user(int(uid))
                    players_with_names[uid]["display_name"] = user.display_name
                except:
                    players_with_names[uid]["display_name"] = f"Player"
        
        img_buffer = generate_wordle_live_image(players_with_names, self.bot)
        file = discord.File(img_buffer, filename="wordle_final.png")
        
        # Create final embed
        embed = discord.Embed(
            title="🏆 Wordle Complete!",
            description=f"**Word:** {game['word']}",
            color=discord.Color.gold()
        )
        embed.set_image(url="attachment://wordle_final.png")
        
        # Delete old channel message and send new one with winner ping
        try:
            msg = game["game_msg"]
            try:
                await msg.delete()
            except:
                pass
            
            # Send new final message with winner ping in content
            await channel.send(
                content=f"🎉 Congratulations {winner_mention}! You won the Wordle!",
                embed=embed,
                file=file
            )
        except Exception as e:
            logger.error(f"Error sending wordle final message: {e}")
        
    async def _check_wordle_game_end(self, game_id: str):
        """Check if all players are done and end the game if so"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        
        # Check if all players are done
        all_done = all(p["status"] != "playing" for p in game["players"].values())
        if all_done:
            # Mark game as ended
            game["ended"] = True
            
            # No winner - everyone lost
            channel = game["channel"]
            
            # Delete old DMs and send new final ones for all players
            for user_id, player_data in game["players"].items():
                try:
                    dm_msg = player_data.get("dm_msg")
                    if dm_msg:
                        # Delete old message
                        try:
                            await dm_msg.delete()
                        except:
                            pass
                        
                        # Send new final message
                        avatar_bytes = player_data.get("avatar_bytes")
                        player_name = player_data.get("display_name", "Player")
                        
                        img_buffer = generate_wordle_board_image(
                            player_data["attempts"], 
                            game["word"], 
                            show_word=True,
                            avatar_bytes=avatar_bytes,
                            player_name=player_name
                        )
                        file = discord.File(img_buffer, filename="wordle_final.png")
                        
                        embed = discord.Embed(
                            title="💀 Game Over!",
                            description=f"**Word was:** {game['word']}",
                            color=discord.Color.red()
                        )
                        embed.set_image(url="attachment://wordle_final.png")
                        
                        try:
                            user = await self.bot.fetch_user(int(user_id))
                            await user.send(
                                content="😔 No one won the Wordle game!",
                                embed=embed,
                                file=file
                            )
                        except:
                            pass
                except Exception as e:
                    logger.error(f"Error updating DM for {user_id}: {e}")
            
            # Generate final live image
            players_with_names = {}
            for uid, pdata in game["players"].items():
                players_with_names[uid] = pdata.copy()
                if "display_name" not in players_with_names[uid]:
                    try:
                        user = await self.bot.fetch_user(int(uid))
                        players_with_names[uid]["display_name"] = user.display_name
                    except:
                        players_with_names[uid]["display_name"] = f"Player"
            
            img_buffer = generate_wordle_live_image(players_with_names, self.bot)
            file = discord.File(img_buffer, filename="wordle_final.png")
            
            embed = discord.Embed(
                title="💀 Wordle - Game Over!",
                description=f"**Word was:** {game['word']}",
                color=discord.Color.red()
            )
            embed.set_image(url="attachment://wordle_final.png")
            
            # Delete old channel message and send new one
            try:
                msg = game["game_msg"]
                try:
                    await msg.delete()
                except:
                    pass
                
                # Send new final message with "no one won" in content
                await channel.send(
                    content="😔 **No one won the Wordle!** Better luck next time!",
                    embed=embed,
                    file=file
                )
            except Exception as e:
                logger.error(f"Error sending wordle final message: {e}")
            
            # Clean up
            await asyncio.sleep(60)
            if game_id in self.active_games:
                del self.active_games[game_id]

    async def _update_wordle_leaderboard(self, game_id: str):
        """Update the wordle leaderboard in the channel with live image"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        
        # Don't update if game already ended
        if game.get("ended"):
            return
        
        msg = game["game_msg"]
        
        # Build player data with display names for image
        players_with_names = {}
        for user_id, player_data in game["players"].items():
            players_with_names[user_id] = player_data.copy()
            if "display_name" not in players_with_names[user_id]:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    players_with_names[user_id]["display_name"] = user.display_name
                    # Also store in original for future use
                    player_data["display_name"] = user.display_name
                except:
                    players_with_names[user_id]["display_name"] = f"Player"
        
        # Generate live image showing all boards
        img_buffer = generate_wordle_live_image(players_with_names, self.bot)
        file = discord.File(img_buffer, filename="wordle_live.png")
        
        # Build text leaderboard as well
        leaderboard = []
        for user_id, player_data in game["players"].items():
            try:
                attempts = len(player_data["attempts"])
                status = player_data["status"]
                name = player_data.get("display_name", "Player")
                
                if status == "won":
                    emoji = "🏆"
                elif status == "lost":
                    emoji = "💀"
                elif status == "ended":
                    emoji = "🏁"
                else:
                    emoji = "🎮"
                
                leaderboard.append(f"{emoji} **{name}** - {attempts}/6")
            except:
                pass
        
        embed = discord.Embed(
            title="🟩 Wordle - Live Results",
            description="\n".join(leaderboard) if leaderboard else "Waiting for players...",
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://wordle_live.png")
        embed.set_footer(text="First to guess correctly wins!")
        
        try:
            await msg.edit(embed=embed, attachments=[file])
        except Exception as e:
            logger.error(f"Error updating wordle leaderboard: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # CLASSIC GAMES - WORDLE (OLD - KEEPING FOR COMPATIBILITY)
    # ═══════════════════════════════════════════════════════════════
    
    async def _old_wordle_timeout_handler(self, game, game_key, msg):
        """Handle old wordle timeout"""
        def get_result(guess, answer):
            result = []
            answer_chars = list(answer)
            for i, (g, a) in enumerate(zip(guess, answer)):
                if g == a:
                    result.append("🟩")
                    answer_chars[i] = None
                else:
                    result.append(None)
            for i, g in enumerate(guess):
                if result[i] is None:
                    if g in answer_chars:
                        result[i] = "🟨"
                        answer_chars[answer_chars.index(g)] = None
                    else:
                        result[i] = "⬛"
            return "".join(result)
        
        def build_embed(game, status="playing"):
            if status == "win":
                title = "🎉 You Won!"
                color = discord.Color.green()
            elif status == "lose":
                title = "❌ Game Over!"
                color = discord.Color.red()
            else:
                title = "🟩 Wordle"
                color = discord.Color.blue()
            embed = discord.Embed(title=title, color=color)
            grid = []
            for attempt in game["attempts"]:
                result = get_result(attempt, game["word"])
                grid.append(f"{result} `{attempt}`")
            for _ in range(6 - len(game["attempts"])):
                grid.append("⬜⬜⬜⬜⬜")
            embed.description = "\n".join(grid)
            embed.add_field(name="Attempts", value=f"{len(game['attempts'])}/6", inline=True)
            return embed
        
        embed = build_embed(game, "lose")
        embed.add_field(name="⏰ Timeout!", value=f"The word was **{game['word']}**", inline=False)
        await msg.edit(embed=embed)
        del self.active_games[game_key]
        return

    # ═══════════════════════════════════════════════════════════════
    # GROUNDED GAMES (Spy x Family Themed Economy)
    # ═══════════════════════════════════════════════════════════════
    
    async def get_user_job(self, user_id: str, guild_id: str) -> Optional[str]:
        """Get the user's current job ID."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.current_job": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("current_job")
        except Exception as e:
            logger.error(f"Error getting user job: {e}")
        return None
    
    async def set_user_job(self, user_id: str, guild_id: str, job_id: Optional[str]):
        """Set the user's current job."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            if job_id is None:
                await server_col.update_one(
                    {"guild_id": guild_id},
                    {"$unset": {f"members.{user_id}.current_job": ""}},
                    upsert=True
                )
            else:
                await server_col.update_one(
                    {"guild_id": guild_id},
                    {"$set": {f"members.{user_id}.current_job": job_id}},
                    upsert=True
                )
        except Exception as e:
            logger.error(f"Error setting user job: {e}")
    
    async def get_user_activity(self, user_id: str, guild_id: str) -> int:
        """Get user's activity score (based on messages, commands used, etc.)."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.activity_score": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("activity_score", 0)
        except Exception as e:
            logger.error(f"Error getting activity: {e}")
        return 0
    
    async def increment_activity(self, user_id: str, guild_id: str, amount: int = 1):
        """Increment user's activity score."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$inc": {f"members.{user_id}.activity_score": amount}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error incrementing activity: {e}")
    
    async def get_user_stars(self, user_id: str, guild_id: str) -> int:
        """Get user's total stella stars earned (lifetime earnings)."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.total_stars_earned": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("total_stars_earned", 0)
        except Exception as e:
            logger.error(f"Error getting stars: {e}")
        return 0
    
    def get_job_by_id(self, job_id: str) -> Optional[Dict]:
        """Get job data by ID from config."""
        jobs_config = GROUNDED_CONFIG.get("jobs_system", {}).get("available_jobs", [])
        for job in jobs_config:
            if job.get("id") == job_id:
                return job
        return None
    
    @commands.command(name="jobs", aliases=["job_list", "careers"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def jobs_command(self, ctx):
        """📋 View available jobs and apply for one!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Increment activity for using commands
        await self.increment_activity(user_id, guild_id, 1)
        
        # Get user stats
        current_job_id = await self.get_user_job(user_id, guild_id)
        balance = await self.quest_data.get_balance(user_id, guild_id)
        stars = await self.get_user_stars(user_id, guild_id)
        activity = await self.get_user_activity(user_id, guild_id)
        
        jobs_config = GROUNDED_CONFIG.get("jobs_system", {})
        available_jobs = jobs_config.get("available_jobs", [])
        categories = jobs_config.get("job_categories", {})
        
        # Build embed
        embed = discord.Embed(
            title="📋 Job Board",
            description="Apply for a job to start earning stella points with `.work`!\n\n"
                       f"**Your Stats:**\n"
                       f"⭐ Stars: **{stars:,}**\n"
                       f"📊 Activity: **{activity}**\n"
                       f"💰 Balance: **{balance:,}**",
            color=discord.Color.blue()
        )
        
        if current_job_id:
            current_job = self.get_job_by_id(current_job_id)
            if current_job:
                embed.add_field(
                    name="💼 Current Job",
                    value=f"{current_job['emoji']} **{current_job['title']}**\n"
                          f"Pay: {current_job['pay_range'][0]}-{current_job['pay_range'][1]} pts",
                    inline=False
                )
        
        # Group jobs by category
        jobs_by_category = {}
        for job in available_jobs:
            cat = job.get("category", "entry")
            if cat not in jobs_by_category:
                jobs_by_category[cat] = []
            jobs_by_category[cat].append(job)
        
        for cat_id, cat_jobs in jobs_by_category.items():
            cat_info = categories.get(cat_id, {"name": cat_id.title(), "emoji": "📋"})
            job_lines = []
            for job in cat_jobs:
                reqs = job.get("requirements", {})
                qualified = (
                    stars >= reqs.get("min_stars", 0) and
                    activity >= reqs.get("min_activity", 0) and
                    balance >= reqs.get("min_balance", 0)
                )
                status = "✅" if qualified else "🔒"
                job_lines.append(f"{status} {job['emoji']} **{job['title']}** - {job['pay_range'][0]}-{job['pay_range'][1]} pts")
            
            embed.add_field(
                name=f"{cat_info['emoji']} {cat_info['name']}",
                value="\n".join(job_lines) if job_lines else "No jobs",
                inline=False
            )
        
        # Create view with job select and buttons
        view = JobBoardView(self, ctx.author, guild_id, current_job_id)
        await view.setup()  # Async setup to add the select menu with user stats
        await ctx.reply(embed=embed, view=view, mention_author=False)
    
    @commands.command(name="work")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def work_command(self, ctx):
        """💼 Work at your job to earn stella points!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Increment activity
        await self.increment_activity(user_id, guild_id, 1)
        
        # Check if user has a job
        current_job_id = await self.get_user_job(user_id, guild_id)
        if not current_job_id:
            embed = discord.Embed(
                title="❌ No Job!",
                description="You don't have a job yet!\n\n"
                           f"Use `{ctx.prefix}jobs` to view available jobs and apply for one.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Get job data
        job_data = self.get_job_by_id(current_job_id)
        if not job_data:
            # Job no longer exists, clear it
            await self.set_user_job(user_id, guild_id, None)
            embed = discord.Embed(
                title="❌ Job Not Found!",
                description=f"Your job no longer exists. Use `{ctx.prefix}jobs` to find a new one.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Check cooldown
        cooldown = job_data.get("cooldown", 1800)
        remaining = await self.check_cooldown(user_id, "work", cooldown)
        if remaining:
            return await ctx.reply(f"⏳ You can work again in **{self.format_time(remaining)}**", mention_author=False)
        
        # Show task selection view
        view = WorkTaskView(self, ctx.author, guild_id, job_data)
        
        embed = discord.Embed(
            title=f"{job_data['emoji']} {job_data['title']}",
            description=f"**Choose a task to complete:**\n\n"
                       f"Select a task from the dropdown below to start working!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="💰 Pay Range",
            value=f"{job_data['pay_range'][0]}-{job_data['pay_range'][1]} pts",
            inline=True
        )
        
        await ctx.reply(embed=embed, view=view, mention_author=False)
    
    
    @commands.command(name="rob", aliases=["steal"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rob_command(self, ctx, target: discord.Member = None):
        """💰 Attempt to steal stella points from another user. High risk!"""
        if target is None:
            return await ctx.reply(f"`{ctx.prefix}rob @user`", mention_author=False)
        
        if target.id == ctx.author.id:
            return await ctx.reply("You can't rob yourself!", mention_author=False)
        
        if target.bot:
            return await ctx.reply("You can't rob bots!", mention_author=False)
        
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        target_id = str(target.id)
        
        # Check cooldown (2 hours)
        remaining = await self.check_cooldown(user_id, "rob", 7200)
        if remaining:
            return await ctx.reply(f"⏳ You can rob again in **{self.format_time(remaining)}**", mention_author=False)
        
        # Check target balance
        target_balance = await self.quest_data.get_balance(target_id, guild_id)
        if target_balance < 500:
            return await ctx.reply(f"{target.display_name} doesn't have enough to steal (min 500 pts)", mention_author=False)
        
        config = GROUNDED_CONFIG.get("rob", {})
        base_success = config.get("success_rate", 0.4)
        steal_min, steal_max = config.get("steal_percent", [10, 30])
        fine_min, fine_max = config.get("fail_fine_percent", [15, 25])
        
        character = await self.get_user_character(user_id, guild_id)
        success_rate = base_success
        
        if character:
            char_bonus = config.get("character_bonuses", {}).get(character, {})
            success_rate += char_bonus.get("success_boost", 0)
        
        await self.set_cooldown(user_id, "rob")
        
        # Get avatar URLs for crime scene image
        robber_avatar_url = ctx.author.display_avatar.with_size(128).url
        victim_avatar_url = target.display_avatar.with_size(128).url
        
        if random.random() < success_rate:
            steal_percent = random.randint(steal_min, steal_max) / 100
            stolen = int(target_balance * steal_percent)
            
            await self.quest_data.add_balance(target_id, guild_id, -stolen)
            await self.quest_data.add_balance(user_id, guild_id, stolen)
            new_balance = await self.quest_data.get_balance(user_id, guild_id)
            
            success_msgs = config.get("success_messages", ["You stole their points!"])
            
            # Generate crime scene image
            img_buffer = await generate_crime_scene_image(
                robber_avatar_url, victim_avatar_url,
                ctx.author.display_name, target.display_name,
                success=True, amount=stolen
            )
            file = discord.File(img_buffer, filename="robbery.png")
            
            embed = discord.Embed(
                title="💰 Robbery Successful!",
                description=f"{random.choice(success_msgs)}",
                color=discord.Color.green()
            )
            embed.set_image(url="attachment://robbery.png")
            embed.add_field(name="💰 Stolen", value=f"+**{stolen}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
            
            await ctx.reply(embed=embed, file=file, mention_author=False)
        else:
            user_balance = await self.quest_data.get_balance(user_id, guild_id)
            fine_percent = random.randint(fine_min, fine_max) / 100
            fine = int(user_balance * fine_percent) if user_balance > 0 else 50
            fine = max(50, fine)
            
            await self.quest_data.add_balance(user_id, guild_id, -fine)
            new_balance = await self.quest_data.get_balance(user_id, guild_id)
            
            fail_msgs = config.get("fail_messages", ["You got caught!"])
            
            # Generate crime scene image
            img_buffer = await generate_crime_scene_image(
                robber_avatar_url, victim_avatar_url,
                ctx.author.display_name, target.display_name,
                success=False, amount=fine
            )
            file = discord.File(img_buffer, filename="caught.png")
            
            embed = discord.Embed(
                title="🚔 Caught!",
                description=f"{random.choice(fail_msgs)}",
                color=discord.Color.red()
            )
            embed.set_image(url="attachment://caught.png")
            embed.add_field(name="💸 Fine", value=f"-**{fine}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
            
            await ctx.reply(embed=embed, file=file, mention_author=False)
    
    @commands.command(name="claim", aliases=["daily"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def claim_command(self, ctx):
        """🎁 Claim your daily stella points reward!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check cooldown (24 hours)
        remaining = await self.check_cooldown(user_id, "claim", 86400)
        if remaining:
            return await ctx.reply(f"⏳ Next daily in **{self.format_time(remaining)}**", mention_author=False)
        
        config = GROUNDED_CONFIG.get("claim", {})
        base_min, base_max = config.get("base_reward", [100, 200])
        streak_bonus = config.get("streak_bonus", 25)
        max_streak = config.get("max_streak", 30)
        milestones = config.get("streak_milestone_bonuses", {})
        
        # Get and update streak
        streak = await self.get_daily_streak(user_id, guild_id)
        streak = min(streak + 1, max_streak)
        await self.update_daily_streak(user_id, guild_id, streak)
        
        # Calculate reward
        base_reward = random.randint(base_min, base_max)
        streak_reward = streak * streak_bonus
        
        # Character bonus
        character = await self.get_user_character(user_id, guild_id)
        char_bonus = 0
        if character:
            char_bonuses = config.get("character_bonuses", {}).get(character, {})
            char_bonus = char_bonuses.get("base_bonus", 0)
        
        # Milestone bonus
        milestone_bonus = milestones.get(str(streak), 0)
        
        total_reward = base_reward + streak_reward + char_bonus + milestone_bonus
        
        await self.quest_data.add_balance(user_id, guild_id, total_reward)
        await self.set_cooldown(user_id, "claim")
        
        new_balance = await self.quest_data.get_balance(user_id, guild_id)
        
        embed = discord.Embed(
            title="🎁 Daily Claimed!",
            color=discord.Color.gold()
        )
        
        breakdown = f"Base: +{base_reward}\nStreak ({streak}d): +{streak_reward}"
        if char_bonus > 0:
            breakdown += f"\n{character}: +{char_bonus}"
        if milestone_bonus > 0:
            breakdown += f"\n🏆 Milestone: +{milestone_bonus}"
        
        embed.add_field(name="💰 Reward", value=f"**+{total_reward}** pts\n-# {breakdown}", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        embed.add_field(name="🔥 Streak", value=f"**{streak}** days", inline=True)
        
        if milestone_bonus > 0:
            embed.set_footer(text=f"🎉 {streak}-day milestone bonus!")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="stats", aliases=["me"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def stats_command(self, ctx, member: discord.Member = None):
        """📊 View your profile card with game stats!"""
        target = member or ctx.author
        guild_id = str(ctx.guild.id)
        user_id = str(target.id)
        
        # Get user data
        balance = await self.quest_data.get_balance(user_id, guild_id)
        
        # Get job info
        current_job_id = await self.get_user_job(user_id, guild_id)
        job_data = self.get_job_by_id(current_job_id) if current_job_id else None
        job_title = job_data.get("title") if job_data else None
        job_emoji = job_data.get("emoji", "💼") if job_data else "💼"
        
        # Get streak
        daily_streak = await self.get_daily_streak(user_id, guild_id)
        
        # Get total earned and games played from database
        total_earned = 0
        total_games = 0
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            server_data = await server_col.find_one({"guild_id": guild_id})
            if server_data and "members" in server_data:
                member_data = server_data["members"].get(user_id, {})
                total_earned = member_data.get("total_stars_earned", 0)
                # Sum up game plays
                game_plays = member_data.get("daily_game_plays", {})
                for game_type, plays in game_plays.items():
                    if isinstance(plays, int):
                        total_games += plays
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
        
        # Generate profile card
        avatar_url = target.display_avatar.with_size(128).url
        
        img_buffer = await generate_profile_card(
            user_name=target.display_name,
            avatar_url=avatar_url,
            balance=balance,
            job_title=job_title,
            job_emoji=job_emoji,
            daily_streak=daily_streak,
            total_games=total_games,
            total_earned=total_earned
        )
        
        file = discord.File(img_buffer, filename="profile.png")
        
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_image(url="attachment://profile.png")
        embed.set_footer(text=f"Use {ctx.prefix}stats @user to view someone else's profile")
        
        await ctx.reply(embed=embed, file=file, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # ERROR HANDLERS
    # ═══════════════════════════════════════════════════════════════
    
    @slots_command.error
    @coinflip_command.error
    @guess_command.error
    @hangman_game.error
    @wordle_game.error
    @jobs_command.error
    @work_command.error
    @rob_command.error
    @claim_command.error
    async def game_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏳ Cooldown",
                description=f"Please wait **{error.retry_after:.1f}s** before playing again!",
                color=discord.Color.orange()
            )
            await ctx.reply(embed=embed, mention_author=False)
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ Invalid Input",
                description="Please enter valid numbers!",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, mention_author=False)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply("❌ Member not found!", mention_author=False)
        else:
            logger.error(f"Game error: {error}")
            raise error


    @commands.command(name="memo")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def memo_game(self, ctx):
        """🧠 Memory game - Remember the emoji!"""
        from utils.cogs.fun import Memo
        from data.local.const import primary_color
        
        emojis = ["😀","😊","😂","😍","😎","😢","😠","😱","😡","😐","🥳","😏","🙃","😇","😅","😜","😌","😋"]
        shuffled = emojis * 2
        random.shuffle(shuffled)
        chosen = random.choice(emojis)
        
        if not hasattr(self, 'correct_emojis'):
            self.correct_emojis = {}
        self.correct_emojis[ctx.channel.id] = chosen

        embed = discord.Embed(
            description=f"Remember this emoji: {chosen}",
            color=primary_color()
        )
        msg = await ctx.reply(embed=embed, mention_author=False)
        await asyncio.sleep(2)

        view = Memo(ctx, shuffled, chosen, msg)
        future = int((datetime.now(timezone.utc) + timedelta(seconds=13)).timestamp())
        
        def timestamp_gen(ts: int) -> str:
            return f"<t:{int(ts)}:R>"
        
        embed = discord.Embed(
            description=f"React with the emoji you remembered.\n`Remaining Time:` {timestamp_gen(future)}",
            color=primary_color(),
        )
        try:
            await msg.edit(embed=embed, view=view)
            await asyncio.sleep(10)
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Time's Up...",
                description="||```You didn't click the emoji in time.```||",
                color=primary_color()
            )
            await msg.edit(embed=timeout_embed, view=None)


async def setup(bot):
    await bot.add_cog(Games(bot))
