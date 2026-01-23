
"""
═════════════════════════════════════════════════════════════════════════════════════════════════════
🎮 GAME IMAGE GENERATION - ANYA BOT
═════════════════════════════════════════════════════════════════════════════════════════════════════

This module provides comprehensive image generation functions for all game systems.
Creates professional, emoji-compatible visuals for Discord embeds and interactions.

🎨 FEATURES:
    • Emoji-compatible font rendering with fallback support
    • Professional UI design with consistent styling
    • Avatar integration with circular masking
    • Animated GIF generation for dynamic games
    • Multiplayer game visualizations

📦 DEPENDENCIES:
    - PIL (Pillow): Image processing and font rendering
    • Crime Games - Scene visualization with overlays
    • Profile Cards - User statistics and achievements

📁 DEPENDENCIES:
    - io: BytesIO for image buffer management
    - pathlib.Path: Cross-platform file path handling
    - PIL: Image processing (Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter)
    - aiohttp: Async HTTP requests for avatar fetching
    - .fonts: Emoji-compatible font loading

🎯 DESIGN PRINCIPLES:
    • Consistent color schemes across all games
    • Emoji support for enhanced visual appeal
    • Graceful fallbacks for missing assets
    • Performance-optimized image generation
    • Discord-friendly dimensions and formats

═════════════════════════════════════════════════════════════════════════════════════════════════════
"""

import io
import random
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import aiohttp
from .fonts import _load_emoji_font
from typing import Literal, Optional, List, Dict, Union
import asyncio
import time

logger = logging.getLogger(__name__)

# Font assets
FONT_DIR = Path(__file__).resolve().parents[3] / "data" / "assets" / "fonts"
POPPINS_SEMIBOLD_PATH = FONT_DIR / "Poppins-SemiBold.ttf"
POPPINS_REGULAR_PATH = FONT_DIR / "Poppins-Regular.ttf"
INTER_REGULAR_PATH = FONT_DIR / "Inter.ttf"
SEGUIEMJ_PATH = FONT_DIR / "seguiemj.ttf"

def _load_font_from_assets(font_path: Path, size: int):
    """Load a custom font from assets with emoji fallback."""
    try:
        if font_path.is_file():
            return ImageFont.truetype(str(font_path), size)
    except Exception as exc:
        logger.debug(f"Failed to load font {font_path}: {exc}")
    return _load_emoji_font(size)

def _dominant_color(image: Image.Image, default=(120, 170, 255)):
    """Return dominant/average color of an RGBA/RGB image."""
    try:
        small = image.convert("RGBA").resize((32, 32))
        data = small.getdata()
        r = g = b = count = 0
        for pr, pg, pb, pa in data:
            if pa == 0:
                continue
            r += pr
            g += pg
            b += pb
            count += 1
        if count:
            return (r // count, g // count, b // count)
    except Exception as exc:
        logger.debug(f"dominant color fallback: {exc}")
    return default

# ═══════════════════════════════════════════════════════════════
# 🎨 WORDLE GAME COLORS & CONSTANTS
# ═══════════════════════════════════════════════════════════════

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


async def fetch_anisearch_screenshot(session, character_name: str) -> Optional[str]:
    """Fetch anisearch screenshot for a character.
    
    Args:
        session: aiohttp ClientSession
        character_name: Name of the character to search for
        
    Returns:
        URL of the screenshot image or None if not found
    """
    try:
        # Search for character on anisearch
        search_url = f"https://anisearch.org/character/index.html?char={character_name}&q=character"
        async with session.get(search_url) as resp:
            if resp.status == 200:
                html = await resp.text()
                
                # Simple regex to find screenshot images
                import re
                # Look for image URLs that appear to be screenshots
                screenshot_pattern = r'<img[^>]+src="([^"]+)"[^>]+alt="[^"]*screenshot[^"]*"'
                matches = re.findall(screenshot_pattern, html, re.IGNORECASE)
                
                if matches:
                    # Return the first screenshot found
                    screenshot_url = matches[0]
                    # Make sure it's a full URL
                    if screenshot_url.startswith('//'):
                        screenshot_url = 'https:' + screenshot_url
                    elif screenshot_url.startswith('/'):
                        screenshot_url = 'https://anisearch.org' + screenshot_url
                    return screenshot_url
                    
                # Alternative: look for character images
                image_pattern = r'<img[^>]+src="([^"]+)"[^>]+class="[^"]*character[^"]*"'
                matches = re.findall(image_pattern, html, re.IGNORECASE)
                
                if matches:
                    image_url = matches[0]
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = 'https://anisearch.org' + image_url
                    return image_url
    except Exception as e:
        logger.error(f"Error fetching anisearch screenshot for {character_name}: {e}")
    
    return None


# ═══════════════════════════════════════════════════════════════
# 🎮 WORDLE GAME IMAGE GENERATION
# ═══════════════════════════════════════════════════════════════

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
    
    # Try to load emoji-compatible fonts, fallback to default
    try:
        font = _load_emoji_font(36)
        small_font = _load_emoji_font(20)
        name_font = _load_emoji_font(18)
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
    # Try to load emoji-compatible fonts
    try:
        title_font = _load_emoji_font(24)
        status_font = _load_emoji_font(12)
        name_font = _load_emoji_font(13)
        cell_font = _load_emoji_font(18)
        attempts_font = _load_emoji_font(10)
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
    
    # Try to load emoji-compatible fonts
    try:
        title_font = _load_emoji_font(28)
        subtitle_font = _load_emoji_font(14)
        name_font = _load_emoji_font(13)
        host_font = _load_emoji_font(11)
        countdown_font = _load_emoji_font(18)
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

# ═══════════════════════════════════════════════════════════════
# 🃏 GACHA & CARD SYSTEM IMAGE GENERATION
# ═══════════════════════════════════════════════════════════════

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
    
    # Try to load emoji-compatible fonts
    try:
        name_font = _load_emoji_font(16)
        sub_font = _load_emoji_font(12)
        star_font = _load_emoji_font(18)
        mult_font = _load_emoji_font(14)
    except:
        name_font = sub_font = star_font = mult_font = ImageFont.load_default()
    
    # Get texture frame data
    frame = RARITY_FRAMES.get(rarity, RARITY_FRAMES["common"])
    
    # Draw textured frame instead of basic border
    _draw_textured_card_frame(draw, card_width, card_height, frame)
    
    # Inner card background (adjusted for textured frame)
    inner_margin = 10
    draw.rounded_rectangle(
        [inner_margin, inner_margin, card_width - inner_margin - 1, card_height - inner_margin - 1],
        radius=8,
        fill=(30, 30, 35)
    )
    
    # Stars at top using frame highlight color
    star_text = "⭐" * stars
    star_bbox = draw.textbbox((0, 0), star_text, font=star_font)
    star_x = (card_width - (star_bbox[2] - star_bbox[0])) // 2
    draw.text((star_x, inner_margin + 8), star_text, fill=frame["highlight"], font=star_font)
    
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
# GACHA MULTI-CARD DRAW IMAGE - PREMIUM TRADING CARD DESIGN
# ═══════════════════════════════════════════════════════════════

# Standard trading card aspect ratio: 2.5:3.5 (63mm x 88mm)
# Scaled for display: 350 x 490 pixels
CARD_WIDTH = 350
CARD_HEIGHT = 490

# Premium trading card frame styles with realistic metallic finishes
# Rarities: Bronze (common) -> Silver (uncommon) -> Gold (rare) -> Platinum (epic) -> Obsidian (legendary)
RARITY_FRAMES = {
    # Bronze - Warm copper/bronze metallic finish
    "common": {
        "name": "Bronze",
        "outer_edge": (45, 30, 20),
        "border_dark": (120, 80, 50),
        "border_base": (180, 130, 80),
        "border_light": (220, 175, 120),
        "border_shine": (245, 210, 160),
        "inner_accent": (160, 110, 65),
        "card_bg": (25, 22, 20),
        "text_primary": (255, 255, 255),
        "text_secondary": (220, 175, 120),
        "texture_type": "brushed_bronze",
        "glow_color": (180, 130, 80, 60),
        # Legacy compatibility
        "outer_border": (45, 30, 20),
        "frame_base": (180, 130, 80),
        "frame_light": (220, 175, 120),
        "frame_dark": (120, 80, 50),
        "inner_border": (160, 110, 65),
        "corner_accent": (245, 210, 160),
        "title_bg": (25, 22, 20, 240),
        "title_border": (160, 110, 65),
        "texture": "brushed_bronze",
    },
    # Silver - Cool polished silver finish
    "uncommon": {
        "name": "Silver",
        "outer_edge": (50, 55, 60),
        "border_dark": (100, 110, 120),
        "border_base": (170, 180, 190),
        "border_light": (210, 220, 230),
        "border_shine": (245, 250, 255),
        "inner_accent": (140, 150, 165),
        "card_bg": (22, 24, 28),
        "text_primary": (255, 255, 255),
        "text_secondary": (200, 210, 225),
        "texture_type": "polished_silver",
        "glow_color": (180, 195, 220, 70),
        # Legacy compatibility
        "outer_border": (50, 55, 60),
        "frame_base": (170, 180, 190),
        "frame_light": (210, 220, 230),
        "frame_dark": (100, 110, 120),
        "inner_border": (140, 150, 165),
        "corner_accent": (245, 250, 255),
        "title_bg": (22, 24, 28, 240),
        "title_border": (140, 150, 165),
        "texture": "polished_silver",
    },
    # Gold - Rich luxurious gold finish
    "rare": {
        "name": "Gold",
        "outer_edge": (60, 45, 15),
        "border_dark": (150, 110, 30),
        "border_base": (210, 170, 50),
        "border_light": (245, 210, 90),
        "border_shine": (255, 240, 150),
        "inner_accent": (185, 145, 40),
        "card_bg": (28, 24, 18),
        "text_primary": (255, 255, 255),
        "text_secondary": (255, 220, 100),
        "texture_type": "gold_foil",
        "glow_color": (255, 200, 80, 80),
        # Legacy compatibility
        "outer_border": (60, 45, 15),
        "frame_base": (210, 170, 50),
        "frame_light": (245, 210, 90),
        "frame_dark": (150, 110, 30),
        "inner_border": (185, 145, 40),
        "corner_accent": (255, 240, 150),
        "title_bg": (28, 24, 18, 240),
        "title_border": (185, 145, 40),
        "texture": "gold_foil",
    },
    # Platinum - Premium iridescent platinum
    "epic": {
        "name": "Platinum",
        "outer_edge": (55, 50, 65),
        "border_dark": (130, 125, 150),
        "border_base": (195, 190, 210),
        "border_light": (230, 225, 245),
        "border_shine": (255, 250, 255),
        "inner_accent": (170, 165, 190),
        "card_bg": (24, 22, 30),
        "text_primary": (255, 255, 255),
        "text_secondary": (220, 210, 245),
        "texture_type": "platinum_holo",
        "glow_color": (200, 180, 255, 90),
        # Legacy compatibility
        "outer_border": (55, 50, 65),
        "frame_base": (195, 190, 210),
        "frame_light": (230, 225, 245),
        "frame_dark": (130, 125, 150),
        "inner_border": (170, 165, 190),
        "corner_accent": (255, 250, 255),
        "title_bg": (24, 22, 30, 240),
        "title_border": (170, 165, 190),
        "texture": "platinum_holo",
    },
    # Obsidian - Dark mysterious obsidian with crimson accents
    "legendary": {
        "name": "Obsidian",
        "outer_edge": (15, 10, 12),
        "border_dark": (35, 25, 30),
        "border_base": (55, 45, 50),
        "border_light": (85, 70, 78),
        "border_shine": (180, 50, 70),
        "inner_accent": (140, 40, 55),
        "card_bg": (12, 10, 12),
        "text_primary": (255, 255, 255),
        "text_secondary": (220, 70, 90),
        "texture_type": "obsidian_flame",
        "glow_color": (180, 40, 60, 100),
        # Legacy compatibility
        "outer_border": (15, 10, 12),
        "frame_base": (55, 45, 50),
        "frame_light": (85, 70, 78),
        "frame_dark": (35, 25, 30),
        "inner_border": (140, 40, 55),
        "corner_accent": (180, 50, 70),
        "title_bg": (12, 10, 12, 240),
        "title_border": (140, 40, 55),
        "texture": "obsidian_flame",
    },
}

def _draw_premium_card_frame(card_img: Image.Image, card_width: int, card_height: int, frame: dict, is_claimed: bool = False):
    """Draw a premium trading card frame with realistic metallic textures and polished finishes.
    
    Supports 5 rarity tiers:
    - Bronze (common): Warm brushed bronze metallic
    - Silver (uncommon): Cool polished silver  
    - Gold (rare): Rich luxurious gold foil
    - Platinum (epic): Iridescent platinum with subtle holo
    - Obsidian (legendary): Dark obsidian with crimson flame accents
    """
    draw = ImageDraw.Draw(card_img)
    border_width = 16  # Thick textured border like real cards
    corner_radius = 12
    
    if is_claimed:
        # Desaturated gray frame for claimed cards
        draw.rounded_rectangle([0, 0, card_width - 1, card_height - 1], corner_radius, 
                              fill=(45, 45, 50), outline=(65, 65, 70), width=3)
        draw.rounded_rectangle([border_width, border_width, card_width - border_width - 1, card_height - border_width - 1], 
                              8, fill=(30, 30, 35), outline=(55, 55, 60), width=2)
        return
    
    texture = frame.get("texture_type", frame.get("texture", "brushed_bronze"))
    
    # === LAYER 1: Outer dark edge (card edge shadow) ===
    outer_edge = frame.get("outer_edge", frame.get("outer_border", (40, 40, 45)))
    draw.rounded_rectangle([0, 0, card_width - 1, card_height - 1], corner_radius + 2, fill=outer_edge)
    
    # === LAYER 2: Main border base color ===
    border_base = frame.get("border_base", frame.get("frame_base", (150, 150, 150)))
    draw.rounded_rectangle([3, 3, card_width - 4, card_height - 4], corner_radius, fill=border_base)
    
    # === LAYER 3: Textured border based on rarity ===
    _draw_border_texture(draw, card_width, card_height, border_width, frame, texture)
    
    # === LAYER 4: Inner accent border (separates frame from card content) ===
    inner_accent = frame.get("inner_accent", frame.get("inner_border", (120, 120, 120)))
    draw.rounded_rectangle(
        [border_width - 2, border_width - 2, card_width - border_width + 1, card_height - border_width + 1],
        8, outline=inner_accent, width=3
    )
    
    # === LAYER 5: Card content background ===
    card_bg = frame.get("card_bg", (25, 25, 30))
    draw.rounded_rectangle(
        [border_width, border_width, card_width - border_width - 1, card_height - border_width - 1],
        6, fill=card_bg
    )
    
    # === LAYER 6: 3D beveled edge effect ===
    border_light = frame.get("border_light", frame.get("frame_light", (200, 200, 200)))
    border_dark = frame.get("border_dark", frame.get("frame_dark", (80, 80, 80)))
    
    # Top and left highlight
    draw.line([(5, 5), (card_width - 5, 5)], fill=border_light, width=2)
    draw.line([(5, 5), (5, card_height - 5)], fill=border_light, width=2)
    
    # Bottom and right shadow
    draw.line([(5, card_height - 5), (card_width - 5, card_height - 5)], fill=border_dark, width=2)
    draw.line([(card_width - 5, 5), (card_width - 5, card_height - 5)], fill=border_dark, width=2)
    
    # === LAYER 7: Corner shine accents ===
    border_shine = frame.get("border_shine", frame.get("corner_accent", (255, 255, 255)))
    _draw_corner_accents(draw, card_width, card_height, border_width, border_shine, texture)


def _draw_border_texture(draw, card_width: int, card_height: int, border_width: int, frame: dict, texture: str):
    """Draw the textured border pattern based on rarity type."""
    import random
    
    border_base = frame.get("border_base", frame.get("frame_base", (150, 150, 150)))
    border_light = frame.get("border_light", frame.get("frame_light", (200, 200, 200)))
    border_dark = frame.get("border_dark", frame.get("frame_dark", (100, 100, 100)))
    border_shine = frame.get("border_shine", frame.get("corner_accent", (255, 255, 255)))
    
    if texture == "brushed_bronze":
        # Horizontal brushed metal lines with warm bronze tones
        random.seed(101)
        for y in range(6, card_height - 6, 2):
            # Only draw in border area
            if y < border_width or y > card_height - border_width:
                variation = random.randint(-15, 15)
                color = tuple(max(0, min(255, c + variation)) for c in border_base[:3])
                # Left border
                draw.line([(6, y), (border_width - 2, y)], fill=color, width=1)
                # Right border
                draw.line([(card_width - border_width + 2, y), (card_width - 6, y)], fill=color, width=1)
        # Top and bottom borders
        for x in range(6, card_width - 6, 2):
            if x < border_width or x > card_width - border_width:
                continue
            variation = random.randint(-15, 15)
            color = tuple(max(0, min(255, c + variation)) for c in border_base[:3])
            draw.line([(x, 6), (x, border_width - 2)], fill=color, width=1)
            draw.line([(x, card_height - border_width + 2), (x, card_height - 6)], fill=color, width=1)
        random.seed()
        
    elif texture == "polished_silver":
        # Smooth gradient with reflective shine bands
        for y in range(6, border_width):
            progress = (y - 6) / (border_width - 6)
            if progress < 0.3:
                color = border_light
            elif progress < 0.6:
                color = border_base
            else:
                color = border_dark
            draw.line([(6, y), (card_width - 6, y)], fill=color, width=1)
        # Bottom border gradient (reversed)
        for y in range(card_height - border_width, card_height - 6):
            progress = (y - (card_height - border_width)) / (border_width - 6)
            if progress < 0.3:
                color = border_dark
            elif progress < 0.6:
                color = border_base
            else:
                color = border_light
            draw.line([(6, y), (card_width - 6, y)], fill=color, width=1)
        # Add shine streaks
        random.seed(202)
        for _ in range(8):
            sx = random.randint(20, card_width - 20)
            sy = random.randint(6, border_width - 2)
            draw.line([(sx, sy), (sx + random.randint(15, 40), sy)], fill=border_shine, width=1)
        random.seed()
        
    elif texture == "gold_foil":
        # Rich gold with foil shimmer effect
        random.seed(303)
        # Base gradient
        for y in range(6, border_width):
            progress = (y - 6) / (border_width - 6)
            r = int(border_dark[0] + (border_light[0] - border_dark[0]) * (1 - progress * 0.5))
            g = int(border_dark[1] + (border_light[1] - border_dark[1]) * (1 - progress * 0.5))
            b = int(border_dark[2] + (border_light[2] - border_dark[2]) * (1 - progress * 0.5))
            draw.line([(6, y), (card_width - 6, y)], fill=(r, g, b), width=1)
        # Foil shine spots
        for _ in range(20):
            sx = random.randint(10, card_width - 10)
            sy = random.randint(6, border_width - 2)
            size = random.randint(2, 5)
            draw.ellipse([sx - size, sy - size//2, sx + size, sy + size//2], fill=border_shine)
        # Bottom border
        for _ in range(20):
            sx = random.randint(10, card_width - 10)
            sy = random.randint(card_height - border_width + 2, card_height - 6)
            size = random.randint(2, 5)
            draw.ellipse([sx - size, sy - size//2, sx + size, sy + size//2], fill=border_shine)
        random.seed()
        
    elif texture == "platinum_holo":
        # Iridescent platinum with subtle rainbow shimmer
        random.seed(404)
        holo_colors = [
            (240, 220, 255),  # Light purple
            (220, 240, 255),  # Light blue
            (255, 240, 245),  # Light pink
            (240, 255, 245),  # Light mint
        ]
        # Base platinum gradient
        for y in range(6, border_width):
            progress = (y - 6) / (border_width - 6)
            color = border_light if progress < 0.4 else border_base
            draw.line([(6, y), (card_width - 6, y)], fill=color, width=1)
        # Holographic shimmer lines
        for _ in range(25):
            sx = random.randint(8, card_width - 8)
            sy = random.randint(6, border_width - 2)
            length = random.randint(20, 60)
            color = random.choice(holo_colors)
            draw.line([(sx, sy), (min(sx + length, card_width - 8), sy)], fill=color, width=1)
        # Bottom holo
        for _ in range(25):
            sx = random.randint(8, card_width - 8)
            sy = random.randint(card_height - border_width + 2, card_height - 6)
            length = random.randint(20, 60)
            color = random.choice(holo_colors)
            draw.line([(sx, sy), (min(sx + length, card_width - 8), sy)], fill=color, width=1)
        # Diamond sparkles
        for _ in range(8):
            sx = random.randint(15, card_width - 15)
            sy = random.choice([random.randint(8, border_width - 4), random.randint(card_height - border_width + 4, card_height - 8)])
            draw.polygon([(sx, sy-3), (sx+3, sy), (sx, sy+3), (sx-3, sy)], fill=(255, 255, 255))
        random.seed()
        
    elif texture == "obsidian_flame":
        # Dark obsidian with crimson flame/ember accents
        random.seed(505)
        # Dark obsidian base with subtle variation
        for y in range(6, border_width):
            variation = random.randint(-8, 8)
            color = tuple(max(0, min(255, c + variation)) for c in border_base[:3])
            draw.line([(6, y), (card_width - 6, y)], fill=color, width=1)
        for y in range(card_height - border_width, card_height - 6):
            variation = random.randint(-8, 8)
            color = tuple(max(0, min(255, c + variation)) for c in border_base[:3])
            draw.line([(6, y), (card_width - 6, y)], fill=color, width=1)
        
        # Crimson flame/ember accents
        flame_colors = [
            (180, 50, 70),   # Deep crimson
            (200, 60, 80),   # Crimson
            (220, 80, 90),   # Bright crimson
            (160, 40, 55),   # Dark crimson
        ]
        # Flame streaks on top border
        for _ in range(15):
            sx = random.randint(20, card_width - 20)
            sy = random.randint(7, border_width - 3)
            length = random.randint(10, 35)
            color = random.choice(flame_colors)
            draw.line([(sx, sy), (sx + length, sy - random.randint(0, 3))], fill=color, width=2)
        # Flame streaks on bottom border
        for _ in range(15):
            sx = random.randint(20, card_width - 20)
            sy = random.randint(card_height - border_width + 3, card_height - 7)
            length = random.randint(10, 35)
            color = random.choice(flame_colors)
            draw.line([(sx, sy), (sx + length, sy + random.randint(0, 3))], fill=color, width=2)
        # Ember particles
        for _ in range(12):
            ex = random.randint(15, card_width - 15)
            ey = random.choice([random.randint(8, border_width - 4), random.randint(card_height - border_width + 4, card_height - 8)])
            draw.ellipse([ex - 2, ey - 2, ex + 2, ey + 2], fill=border_shine)
        random.seed()


def _draw_corner_accents(draw, card_width: int, card_height: int, border_width: int, shine_color: tuple, texture: str):
    """Draw decorative corner accents based on card rarity."""
    corner_inset = 8
    accent_size = 10
    
    corners = [
        (corner_inset, corner_inset),  # Top-left
        (card_width - corner_inset - accent_size, corner_inset),  # Top-right
        (corner_inset, card_height - corner_inset - accent_size),  # Bottom-left
        (card_width - corner_inset - accent_size, card_height - corner_inset - accent_size),  # Bottom-right
    ]
    
    for cx, cy in corners:
        if texture == "obsidian_flame":
            # Crimson diamond accents for obsidian
            center_x = cx + accent_size // 2
            center_y = cy + accent_size // 2
            draw.polygon([
                (center_x, center_y - 5),
                (center_x + 5, center_y),
                (center_x, center_y + 5),
                (center_x - 5, center_y)
            ], fill=shine_color, outline=(100, 30, 40))
        elif texture == "platinum_holo":
            # Star sparkle for platinum
            center_x = cx + accent_size // 2
            center_y = cy + accent_size // 2
            draw.polygon([
                (center_x, center_y - 6),
                (center_x + 2, center_y - 2),
                (center_x + 6, center_y),
                (center_x + 2, center_y + 2),
                (center_x, center_y + 6),
                (center_x - 2, center_y + 2),
                (center_x - 6, center_y),
                (center_x - 2, center_y - 2),
            ], fill=(255, 255, 255))
        elif texture == "gold_foil":
            # Circular gold medallion accent
            draw.ellipse([cx, cy, cx + accent_size, cy + accent_size], fill=shine_color, outline=(150, 110, 30))
            draw.ellipse([cx + 2, cy + 2, cx + accent_size - 2, cy + accent_size - 2], outline=(200, 160, 60))
        else:
            # Simple corner squares for bronze/silver
            draw.rectangle([cx, cy, cx + accent_size, cy + accent_size], outline=shine_color, width=1)
            draw.ellipse([cx + 3, cy + 3, cx + accent_size - 3, cy + accent_size - 3], fill=shine_color)


def _draw_realistic_card_frame(card_img: Image.Image, card_width: int, card_height: int, frame: dict, is_claimed: bool = False):
    """Draw a realistic anime trading card frame - wrapper for premium frame."""
    _draw_premium_card_frame(card_img, card_width, card_height, frame, is_claimed)


def _draw_textured_card_frame(draw, card_width: int, card_height: int, frame: dict, is_claimed: bool = False, scale: int = 1):
    """Legacy wrapper - creates a temp image and draws realistic frame."""
    if is_claimed:
        draw.rounded_rectangle([0, 0, card_width - 1, card_height - 1], 12, 
                              fill=(50, 50, 55), outline=(70, 70, 75), width=3)
        draw.rounded_rectangle([6, 6, card_width - 7, card_height - 7], 8, 
                              outline=(60, 60, 65), width=2)
        return
    
    # Outer border
    draw.rounded_rectangle([0, 0, card_width - 1, card_height - 1], 14, 
                          fill=frame.get("outer_border", frame.get("shadow", (80, 80, 80))))
    
    # Main frame
    draw.rounded_rectangle([4, 4, card_width - 5, card_height - 5], 12, 
                          fill=frame.get("frame_base", frame.get("base", (150, 150, 150))))
    
    # Inner border
    draw.rounded_rectangle([8, 8, card_width - 9, card_height - 9], 10, 
                          outline=frame.get("inner_border", frame.get("accent", (120, 120, 120))), width=2)
    
    # Highlight edges
    light = frame.get("frame_light", frame.get("highlight", (200, 200, 200)))
    dark = frame.get("frame_dark", frame.get("shadow", (100, 100, 100)))
    draw.line([(6, 6), (card_width - 6, 6)], fill=light, width=1)
    draw.line([(6, 6), (6, card_height - 6)], fill=light, width=1)
    draw.line([(6, card_height - 6), (card_width - 6, card_height - 6)], fill=dark, width=1)
    draw.line([(card_width - 6, 6), (card_width - 6, card_height - 6)], fill=dark, width=1)


def _draw_individual_card(char: dict, char_img: Image.Image = None, is_claimed: bool = False, is_owned: bool = False, owner_data: dict = None, card_width: int = 280, card_height: int = 400) -> Image.Image:
    """Draw an individual card using the exact same logic as the draw system."""
    
    rarity = char.get("rarity", "common")
    frame = RARITY_FRAMES.get(rarity, RARITY_FRAMES["common"])
    
    card_bg = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card_bg)
    
    # Load fonts - scale with card size
    try:
        name_font = _load_emoji_font(int(16 * (card_width / 220)))  # Scale from original 220px width
        small_font = _load_emoji_font(int(12 * (card_width / 220)))
        tiny_font = _load_emoji_font(int(10 * (card_width / 220)))
    except:
        name_font = small_font = tiny_font = ImageFont.load_default()
    
    # Draw textured frame
    if is_claimed:
        _draw_textured_card_frame(card_draw, card_width, card_height, frame, is_claimed=True)
    else:
        _draw_textured_card_frame(card_draw, card_width, card_height, frame, is_claimed=False)
    
    # Draw banner - scale with card size
    banner_h = int(36 * (card_width / 220))
    banner_margin = int(12 * (card_width / 220))
    card_draw.rounded_rectangle(
        [banner_margin, banner_margin, card_width - banner_margin, banner_margin + banner_h],
        6,
        fill=(20, 20, 25, 240) if not is_claimed else (40, 40, 45, 240)
    )
    
    # Draw character name
    name = char.get("name", "Unknown")
    max_name_length = int(16 * (card_width / 220))
    if len(name) > max_name_length:
        name = name[:max_name_length-2] + "..."
    name_bbox = card_draw.textbbox((0, 0), name, font=name_font)
    name_x = (card_width - (name_bbox[2] - name_bbox[0])) // 2
    name_y_offset = int(10 * (card_width / 220))
    card_draw.text((name_x + 1, banner_margin + name_y_offset + 1), name, fill=(0, 0, 0, 180), font=name_font)
    card_draw.text((name_x, banner_margin + name_y_offset), name, fill=(255, 255, 255), font=name_font)
    
    # Draw UID and favorite indicator in top right
    uid = char.get("uid", "UNKNOWN")
    uid_text = uid[:6]  # Shorten UID for display
    uid_bbox = card_draw.textbbox((0, 0), uid_text, font=tiny_font)
    uid_x = card_width - banner_margin - (uid_bbox[2] - uid_bbox[0]) - 5
    uid_y = banner_margin + 5
    
    # Draw UID background
    uid_bg_margin = 2
    card_draw.rounded_rectangle(
        [uid_x - uid_bg_margin, uid_y - uid_bg_margin, 
         uid_x + (uid_bbox[2] - uid_bbox[0]) + uid_bg_margin, uid_y + (uid_bbox[3] - uid_bbox[1]) + uid_bg_margin],
        4,
        fill=(10, 10, 15, 200)
    )
    
    # Draw UID text
    card_draw.text((uid_x + 1, uid_y + 1), uid_text, fill=(0, 0, 0, 180), font=tiny_font)
    card_draw.text((uid_x, uid_y), uid_text, fill=(200, 200, 200), font=tiny_font)
    
    # Draw favorite star if favorited
    if char.get("favorite", False):
        star_text = "⭐"
        star_bbox = card_draw.textbbox((0, 0), star_text, font=tiny_font)
        star_x = uid_x - star_bbox[2] - 8
        star_y = uid_y
        
        # Draw star with slight shadow
        card_draw.text((star_x + 1, star_y + 1), star_text, fill=(0, 0, 0, 180), font=tiny_font)
        card_draw.text((star_x, star_y), star_text, fill=(255, 215, 0), font=tiny_font)  # Gold color
    
    # Draw character image area - scale with card size
    img_area_x = int(10 * (card_width / 220))
    img_area_y = banner_margin + banner_h + int(8 * (card_width / 220))
    img_area_w = card_width - int(20 * (card_width / 220))
    img_area_h = card_height - (banner_margin + banner_h) - int(68 * (card_width / 220))
    
    if char_img:
        if is_claimed:
            # Convert to grayscale for claimed cards
            char_img = char_img.convert('L').convert('RGBA')
            # Apply gray tint
            gray_overlay = Image.new('RGBA', char_img.size, (128, 128, 128, 100))
            char_img = Image.alpha_composite(char_img, gray_overlay)
        char_img = char_img.resize((img_area_w, img_area_h), Image.Resampling.LANCZOS)
        card_bg.paste(char_img, (img_area_x, img_area_y), char_img)
    else:
        # Draw placeholder - scale with card size
        placeholder_margin = int(20 * (card_width / 220))
        card_draw.ellipse([img_area_x + placeholder_margin, img_area_y + placeholder_margin, 
                          img_area_x + img_area_w - placeholder_margin, img_area_y + img_area_h - placeholder_margin],
                        fill=(50, 50, 55))
    
    # Draw claimed stamp if needed
    if is_claimed:
        try:
            stamp_font = _load_emoji_font(int(48 * (card_width / 220)))
        except:
            stamp_font = ImageFont.load_default()
        
        stamp_text = "CLAIMED"
        stamp_x = card_width // 2
        stamp_y = card_height // 2
        
        stamp_img = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
        stamp_draw = ImageDraw.Draw(stamp_img)
        
        text_bbox = stamp_draw.textbbox((0, 0), stamp_text, font=stamp_font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        text_x = (card_width - text_width) // 2
        text_y = (card_height - text_height) // 2
        
        shadow_offset = int(3 * (card_width / 220))
        stamp_draw.text((text_x + shadow_offset, text_y + shadow_offset), stamp_text, fill=(0, 0, 0, 180), font=stamp_font)
        stamp_draw.text((text_x, text_y), stamp_text, fill=(220, 20, 60, 230), font=stamp_font)
        
        rotated_stamp = stamp_img.rotate(-30, expand=False, fillcolor=(0, 0, 0, 0))
        card_bg.paste(rotated_stamp, (0, 0), rotated_stamp)
    
    # Draw owned banner if needed
    if is_owned and not is_claimed and owner_data:
        owner_banner_h = int(40 * (card_width / 220))
        owner_banner_y = img_area_y + img_area_h - owner_banner_h - int(4 * (card_width / 220))
        
        card_draw.rounded_rectangle(
            [img_area_x + int(6 * (card_width / 220)), owner_banner_y, 
             img_area_x + img_area_w - int(6 * (card_width / 220)), owner_banner_y + owner_banner_h],
            6,
            fill=(15, 15, 20, 235),
            outline=(255, 70, 70),
            width=int(3 * (card_width / 220))
        )
        
        # Draw owner avatar if available
        if owner_data.get("avatar_img"):
            avatar_img = owner_data["avatar_img"]
            card_bg.paste(avatar_img, (img_area_x + int(10 * (card_width / 220)), owner_banner_y - 8), avatar_img)
        
        # Draw owned text - scale positions
        owned_text_x = img_area_x + int(52 * (card_width / 220))
        card_draw.text((owned_text_x + 1, owner_banner_y + int(9 * (card_width / 220))), "OWNED", fill=(0, 0, 0, 200), font=small_font)
        card_draw.text((owned_text_x, owner_banner_y + int(8 * (card_width / 220))), "OWNED", fill=(255, 70, 70), font=small_font)
        
        owner_name = owner_data.get("username", "Someone")[:int(12 * (card_width / 220))]
        card_draw.text((owned_text_x + 1, owner_banner_y + int(26 * (card_width / 220))), f"by {owner_name}", fill=(0, 0, 0, 200), font=small_font)
        card_draw.text((owned_text_x, owner_banner_y + int(25 * (card_width / 220))), f"by {owner_name}", fill=(200, 200, 200), font=small_font)
    
    # Draw bottom banner with anime name - scale with card size
    bottom_banner_h = int(32 * (card_width / 220))
    bottom_banner_y = card_height - int(48 * (card_width / 220))
    card_draw.rounded_rectangle(
        [banner_margin, bottom_banner_y, card_width - banner_margin, bottom_banner_y + bottom_banner_h],
        6,
        fill=(20, 20, 25, 240)
    )
    
    anime = char.get("anime", "Unknown")
    max_anime_length = int(20 * (card_width / 220))
    if len(anime) > max_anime_length:
        anime = anime[:max_anime_length-2] + "..."
    anime_bbox = card_draw.textbbox((0, 0), anime, font=small_font)
    anime_x = (card_width - (anime_bbox[2] - anime_bbox[0])) // 2
    anime_y_offset = int(10 * (card_width / 220))
    card_draw.text((anime_x + 1, bottom_banner_y + anime_y_offset + 1), anime, fill=(0, 0, 0, 180), font=small_font)
    card_draw.text((anime_x, bottom_banner_y + anime_y_offset), anime, fill=(240, 240, 240), font=small_font)
    
    return card_bg





# Helper async function for image fetching
async def fetch_image(session, url, idx):
    try:
        async with session.get(url) as resp:
            if resp.status == 200:
                return idx, await resp.read()
    except Exception as e:
        logger.error(f"Error fetching image {url}: {e}")
    return None

async def generate_gacha_draw_image(characters: list, claimed_indices: list = None, ownership_info: dict = None) -> io.BytesIO:
    """Generate premium trading cards with realistic metallic finishes.
    
    Card rarities with unique visual styles:
    - Bronze (common): Warm brushed bronze metallic
    - Silver (uncommon): Cool polished silver
    - Gold (rare): Rich luxurious gold foil
    - Platinum (epic): Iridescent platinum with holo effects
    - Obsidian (legendary): Dark obsidian with crimson flame accents
    """
    if claimed_indices is None:
        claimed_indices = []
    if ownership_info is None:
        ownership_info = {}

    # Standard trading card aspect ratio 2.5:3.5 (like real cards)
    # 350x490 provides proper proportions for mobile display
    card_width = CARD_WIDTH   # 350
    card_height = CARD_HEIGHT  # 490
    card_spacing = 30
    num_cards = len(characters)

    content_width = (card_width * num_cards) + (card_spacing * (num_cards - 1))
    margin = 50
    total_width = content_width + (margin * 2)
    total_height = card_height + (margin * 2)

    img = Image.new('RGBA', (total_width, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        title_font = _load_emoji_font(24)
        name_font = _load_emoji_font(22)  # Increased from 16 for better visibility
        small_font = _load_emoji_font(16)  # Increased from 12 for anime name
        tiny_font = _load_emoji_font(12)  # Increased from 10
        number_font = _load_emoji_font(32)
    except:
        title_font = name_font = small_font = tiny_font = number_font = ImageFont.load_default()

    char_images = []
    owner_avatars = {}

    async with aiohttp.ClientSession() as session:
        for char in characters:
            char_img = None
            image_url = char.get("image_url")
            if image_url:
                try:
                    # Faster timeout for quicker draws (3s instead of 5s)
                    async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status == 200:
                            char_img = Image.open(io.BytesIO(await resp.read())).convert('RGBA')
                        else:
                            logger.warning(f"Draw card: Failed to fetch image from {image_url}, status: {resp.status}")
                except Exception as e:
                    logger.error(f"Draw card: Error fetching image from {image_url}: {e}")
            else:
                logger.debug(f"Draw card: No image URL for character {char.get('name', 'Unknown')}")
            char_images.append(char_img)

        for idx, owner_data in ownership_info.items():
            if owner_data.get("avatar_url"):
                try:
                    async with session.get(owner_data["avatar_url"]) as resp:
                        if resp.status == 200:
                            avatar = Image.open(io.BytesIO(await resp.read())).convert('RGBA')
                            avatar = avatar.resize((36, 36), Image.Resampling.LANCZOS)
                            mask = Image.new('L', (36, 36), 0)
                            ImageDraw.Draw(mask).ellipse([0, 0, 35, 35], fill=255)
                            avatar.putalpha(mask)
                            owner_avatars[idx] = avatar
                except Exception as e:
                    logger.error(f"Gallery: Error fetching owner avatar from {owner_data['avatar_url']}: {e}")
                    pass

    for i, char in enumerate(characters):
        card_x = margin + i * (card_width + card_spacing)
        card_y = margin

        rarity = char.get("rarity", "common")
        frame = RARITY_FRAMES.get(rarity, RARITY_FRAMES["common"])

        is_claimed = i in claimed_indices
        is_owned = i in ownership_info

        card_bg = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_bg)

        # Draw realistic trading card frame with textures
        _draw_realistic_card_frame(card_bg, card_width, card_height, frame, is_claimed=is_claimed)
        card_draw = ImageDraw.Draw(card_bg)  # Refresh draw object after frame

        # === TOP TITLE BANNER (professional trading card style) ===
        border_width = 16
        banner_margin = border_width + 2  # 18px from edge
        title_bg = frame.get("title_bg", frame.get("card_bg", (20, 20, 25)))
        title_border = frame.get("title_border", frame.get("inner_accent", (100, 100, 100)))
        
        # Calculate exact banner height based on text
        name = char.get("name", "Unknown")
        if len(name) > 20:
            name = name[:18] + "..."
        name_bbox = card_draw.textbbox((0, 0), name, font=name_font)
        text_height = name_bbox[3] - name_bbox[1]
        banner_h = text_height + 12  # 6px padding top and bottom
        
        # Draw decorative title banner with stronger border
        card_draw.rounded_rectangle(
            [banner_margin, banner_margin, card_width - banner_margin, banner_margin + banner_h],
            8,
            fill=title_bg if not is_claimed else (40, 40, 45, 240),
            outline=title_border if not is_claimed else (60, 60, 65),
            width=3
        )
        
        # Add subtle inner glow for depth
        if not is_claimed:
            card_draw.rounded_rectangle(
                [banner_margin + 2, banner_margin + 2, card_width - banner_margin - 2, banner_margin + banner_h - 2],
                7,
                outline=frame.get("frame_light", (150, 150, 150)),
                width=1
            )
        
        # Small decorative lines on title banner edges
        if not is_claimed:
            card_draw.line([(banner_margin + 8, banner_margin + 6), (banner_margin + 30, banner_margin + 6)], 
                          fill=frame["frame_light"], width=2)
            card_draw.line([(card_width - banner_margin - 30, banner_margin + 6), (card_width - banner_margin - 8, banner_margin + 6)], 
                          fill=frame["frame_light"], width=2)

        name_x = (card_width - (name_bbox[2] - name_bbox[0])) // 2
        name_y = banner_margin + 6  # Centered vertically in banner
        # Stronger shadow for better visibility
        card_draw.text((name_x + 2, name_y + 2), name, fill=(0, 0, 0, 220), font=name_font)
        card_draw.text((name_x + 1, name_y + 1), name, fill=(0, 0, 0, 180), font=name_font)
        card_draw.text((name_x, name_y), name, fill=(255, 255, 255), font=name_font)

        # === CHARACTER IMAGE AREA (with inner frame) - MAXIMIZED ===
        img_area_x = 14
        img_area_y = banner_margin + banner_h + 6
        img_area_w = card_width - 28
        # Calculate bottom banner height for anime title
        anime = char.get("anime", "Unknown")
        if len(anime) > 26:
            anime = anime[:24] + "..."
        anime_bbox = card_draw.textbbox((0, 0), anime, font=small_font)
        anime_text_height = anime_bbox[3] - anime_bbox[1]
        bottom_banner_h = anime_text_height + 10  # 5px padding top and bottom
        # Maximize image area
        img_area_h = card_height - (banner_margin + banner_h) - bottom_banner_h - 12
        
        # Draw inner image frame border (like real cards have)
        if not is_claimed:
            card_draw.rounded_rectangle(
                [img_area_x - 2, img_area_y - 2, img_area_x + img_area_w + 2, img_area_y + img_area_h + 2],
                4,
                outline=frame["inner_border"],
                width=2
            )

        char_img = char_images[i]
        if char_img:
            if is_claimed:
                # Convert to grayscale for claimed cards
                char_img = char_img.convert('L').convert('RGBA')
                # Apply gray tint
                gray_overlay = Image.new('RGBA', char_img.size, (128, 128, 128, 100))
                char_img = Image.alpha_composite(char_img, gray_overlay)
            
            # Smart crop/fit to prevent squishing - maintain aspect ratio
            img_aspect = char_img.width / char_img.height
            area_aspect = img_area_w / img_area_h
            
            if img_aspect > area_aspect:
                # Image is wider - fit height and crop width
                new_height = img_area_h
                new_width = int(new_height * img_aspect)
                char_img = char_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # Center crop
                crop_x = (new_width - img_area_w) // 2
                char_img = char_img.crop((crop_x, 0, crop_x + img_area_w, img_area_h))
            else:
                # Image is taller - fit width and crop height
                new_width = img_area_w
                new_height = int(new_width / img_aspect)
                char_img = char_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # Center crop from top (keep character's face visible)
                crop_y = max(0, (new_height - img_area_h) // 4)  # Crop from upper portion
                char_img = char_img.crop((0, crop_y, img_area_w, crop_y + img_area_h))
            
            card_bg.paste(char_img, (img_area_x, img_area_y), char_img)

        # ===== CLAIMED STAMP =====
        if is_claimed:
            # Create red stamp text
            try:
                stamp_font = _load_emoji_font(48)
            except:
                stamp_font = ImageFont.load_default()
            
            stamp_text = "CLAIMED"
            
            # Calculate stamp position and rotation (diagonal)
            stamp_x = card_width // 2
            stamp_y = card_height // 2
            
            # Create stamp overlay with rotation
            stamp_img = Image.new('RGBA', (card_width, card_height), (0, 0, 0, 0))
            stamp_draw = ImageDraw.Draw(stamp_img)
            
            # Draw text with shadow effect
            text_bbox = stamp_draw.textbbox((0, 0), stamp_text, font=stamp_font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            # Center the stamp
            text_x = (card_width - text_width) // 2
            text_y = (card_height - text_height) // 2
            
            # Draw shadow
            stamp_draw.text((text_x + 3, text_y + 3), stamp_text, fill=(0, 0, 0, 180), font=stamp_font)
            # Draw red text
            stamp_draw.text((text_x, text_y), stamp_text, fill=(220, 20, 60, 230), font=stamp_font)
            
            # Rotate the stamp
            rotated_stamp = stamp_img.rotate(-30, expand=False, fillcolor=(0, 0, 0, 0))
            
            # Paste rotated stamp onto card
            card_bg.paste(rotated_stamp, (0, 0), rotated_stamp)

        # ===== OWNED BANNER (TEXT MOVED DOWN 5PX) =====
        if is_owned and not is_claimed:
            owner = ownership_info[i]
            owner_banner_y = img_area_y + img_area_h - 44

            card_draw.rounded_rectangle(
                [img_area_x + 6, owner_banner_y, img_area_x + img_area_w - 6, owner_banner_y + 40],
                6,
                fill=(15, 15, 20, 235),
                outline=(255, 70, 70),
                width=3
            )

            if i in owner_avatars:
                card_bg.paste(owner_avatars[i], (img_area_x + 10, owner_banner_y + 2), owner_avatars[i])

            text_x = img_area_x + 52

            # OWNED (moved down 5px)
            card_draw.text((text_x + 1, owner_banner_y + 9), "OWNED", fill=(0, 0, 0, 200), font=small_font)
            card_draw.text((text_x,     owner_banner_y + 8), "OWNED", fill=(255, 70, 70), font=small_font)

            owner_name = owner.get("username", "Someone")[:12]

            # by username (moved down 5px)
            card_draw.text((text_x + 1, owner_banner_y + 26), f"by {owner_name}", fill=(0, 0, 0, 200), font=small_font)
            card_draw.text((text_x,     owner_banner_y + 25), f"by {owner_name}", fill=(200, 200, 200), font=small_font)

        # === BOTTOM BANNER (anime name only - perfectly fitted) ===
        bottom_banner_y = card_height - border_width - bottom_banner_h - 2
        
        card_draw.rounded_rectangle(
            [banner_margin, bottom_banner_y, card_width - banner_margin, bottom_banner_y + bottom_banner_h],
            8,
            fill=title_bg if not is_claimed else (40, 40, 45, 240),
            outline=title_border if not is_claimed else (60, 60, 65),
            width=2
        )

        # Draw anime name centered
        anime_x = (card_width - (anime_bbox[2] - anime_bbox[0])) // 2
        anime_y = bottom_banner_y + 5  # Centered vertically in banner
        card_draw.text((anime_x + 1, anime_y + 1), anime, fill=(0, 0, 0, 200), font=small_font)
        card_draw.text((anime_x, anime_y), anime, fill=(255, 255, 255), font=small_font)

        img.paste(card_bg, (card_x, card_y), card_bg)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", quality=95)
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# GUESS GAME THERMOMETER IMAGE
# ═══════════════════════════════════════════════════════════════

def _load_guess_fonts(size: int, small_size: int = 11):
    """
    Load fonts for guess game (emoji-compatible). Falls back to default if missing.
    """
    return _load_emoji_font(size), _load_emoji_font(small_size)


# ═══════════════════════════════════════════════════════════════
# 🎯 NUMBER GUESSING GAME IMAGE GENERATION
# ═══════════════════════════════════════════════════════════════

def generate_guess_thermometer(guesses: list, secret: int, attempts_left: int, total_attempts: int) -> io.BytesIO:
    """Generate a thermometer/gradient bar showing how close guesses are.
    
    Args:
        guesses: List of guess values
        secret: The secret number
        attempts_left: Remaining attempts
        total_attempts: Total attempts allowed
    
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
    
    font, small_font = _load_guess_fonts(14, 11)
    
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
    header_text = f"Attempts: {total_attempts - attempts_left}/{total_attempts}"
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
    
    # Try to load emoji-compatible fonts
    try:
        font = _load_emoji_font(16)
        big_font = _load_emoji_font(24)
        small_font = _load_emoji_font(11)
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
# PAYCHECK IMAGE GENERATOR
# ═══════════════════════════════════════════════════════════════

def generate_paycheck_image(
    job_title: str,
    job_emoji: str,
    base_pay: int,
    bonus: int = 0,
    overtime: bool = False,
    character_bonus: int = 0,
    pay_to: str = "",
    avatar_bytes: bytes = None,
) -> io.BytesIO:
    """Generate a paycheck image for the work command."""
    width = 350
    height = 180
    
    # Colors
    bg_color = (245, 245, 240)  # Off-white paper
    border_color = (180, 160, 140)
    text_color = (40, 40, 40)
    accent_color = (0, 100, 0) if not overtime else (180, 140, 0)  # Green or gold for overtime
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load emoji-compatible fonts
    try:
        title_font = _load_emoji_font(16)
        main_font = _load_emoji_font(14)
        small_font = _load_emoji_font(11)
        big_font = _load_emoji_font(22)
    except Exception:
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
    
    # Optional avatar + payee
    current_y = 45
    if avatar_bytes:
        try:
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGB").resize((48, 48))
            mask = Image.new("L", avatar_img.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, 48, 48], fill=255)
            img.paste(avatar_img, (16, current_y - 4), mask)
            name_x = 16 + 48 + 8
        except Exception:
            name_x = 16
    else:
        name_x = 16
    
    if pay_to:
        draw.text((name_x, current_y), f"Pay to: {pay_to}", fill=text_color, font=main_font)
        current_y += 22
    else:
        current_y = 45
    
    # Job info
    job_text = f"{job_emoji} {job_title}"
    job_bbox = draw.textbbox((0, 0), job_text, font=main_font)
    job_x = (width - (job_bbox[2] - job_bbox[0])) // 2
    draw.text((job_x, current_y), job_text, fill=text_color, font=main_font)
    
    # Pay breakdown
    y_pos = 75 if pay_to else 70
    
    draw.text((20, y_pos), "Base Pay:", fill=text_color, font=small_font)
    draw.text((width - 110, y_pos), f"{base_pay:,} pts", fill=text_color, font=small_font)
    y_pos += 18
    
    if bonus > 0:
        draw.text((20, y_pos), "Task Bonus:", fill=text_color, font=small_font)
        draw.text((width - 110, y_pos), f"+{bonus:,} pts", fill=(0, 128, 0), font=small_font)
        y_pos += 18
    
    if character_bonus > 0:
        draw.text((20, y_pos), "Character Bonus:", fill=text_color, font=small_font)
        draw.text((width - 110, y_pos), f"+{character_bonus:,} pts", fill=(0, 128, 0), font=small_font)
        y_pos += 18
    
    overtime_bonus = 0
    if overtime:
        overtime_bonus = base_pay  # Double pay for overtime
        draw.text((20, y_pos), "Overtime (2x):", fill=text_color, font=small_font)
        draw.text((width - 110, y_pos), f"+{overtime_bonus:,} pts", fill=(180, 140, 0), font=small_font)
        y_pos += 18
    
    # Total
    total = base_pay + bonus + character_bonus + overtime_bonus
    total_text = f"TOTAL: {total:,} pts"
    total_bbox = draw.textbbox((0, 0), total_text, font=big_font)
    total_x = (width - (total_bbox[2] - total_bbox[0])) // 2
    draw.text((total_x, height - 38), total_text, fill=accent_color, font=big_font)
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


# ═══════════════════════════════════════════════════════════════
# PROFILE CARD IMAGE GENERATOR
# ═══════════════════════════════════════════════════════════════

import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont

# Note: _load_emoji_font is assumed to be defined somewhere in your codebase
# If you don't have it, replace all font usages with ImageFont.load_default()

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
    width = 420
    height = 220
    
    # Colors
    bg_color = (24, 24, 28)
    card_bg = (35, 35, 40)
    accent = (88, 101, 242)  # Discord blurple
    gold = (255, 193, 7)
    text_color = (255, 255, 255)
    subtitle_color = (150, 150, 160)
    
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Try to load emoji-compatible fonts
    try:
        name_font = _load_emoji_font(18)
        stat_font = _load_emoji_font(14)
        small_font = _load_emoji_font(11)
        big_font = _load_emoji_font(22)
    except:
        name_font = stat_font = small_font = big_font = ImageFont.load_default()
    
    # Draw card background
    draw.rounded_rectangle([10, 10, width - 10, height - 10], radius=12, fill=card_bg)
    
    # Draw accent bar at top
    draw.rounded_rectangle([10, 10, width - 10, 60], radius=12, fill=accent)
    draw.rectangle([10, 50, width - 10, 60], fill=card_bg)
    
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
                    draw.ellipse(
                        [avatar_x - 3, avatar_y - 3, avatar_x + avatar_size + 3, avatar_y + avatar_size + 3],
                        outline=(255, 255, 255), width=3
                    )
                    
                    img.paste(output, (avatar_x, avatar_y), output)
    except Exception:
        draw.ellipse(
            [avatar_x, avatar_y, avatar_x + avatar_size, avatar_y + avatar_size],
            fill=(60, 60, 65)
        )
    
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
    
    # ─── Improved Stats Layout ──────────────────────────────────────────────────
    
    # Vertical positions - below avatar area
    balance_y = 110
    stats_row_y = 155
    label_offset_y = 20
    
    # Horizontal layout
    left_margin = 30
    right_margin = 30
    stat_width = (width - left_margin - right_margin) // 3
    
    # Balance (big & centered)
    balance_text = f"💰 {balance:,}"
    balance_bbox = draw.textbbox((0, 0), balance_text, font=big_font)
    balance_x = (width - (balance_bbox[2] - balance_bbox[0])) // 2
    
    draw.text((balance_x, balance_y), balance_text, fill=gold, font=big_font)
    
    # "Stella Points" subtitle under balance
    subtitle_text = "Stella Points"
    subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=small_font)
    subtitle_x = (width - (subtitle_bbox[2] - subtitle_bbox[0])) // 2
    draw.text((subtitle_x, balance_y + 28), subtitle_text, fill=subtitle_color, font=small_font)
    
    # Three stats row
    stats = [
        ("🔥", f"{daily_streak}", "Streak"),
        ("🎮", f"{total_games:,}", "Games"),
        ("📈", f"{total_earned:,}", "Earned"),
    ]
    
    for i, (emoji, value, label) in enumerate(stats):
        center_x = left_margin + i * stat_width + stat_width // 2
    
        # Value + emoji
        stat_text = f"{emoji} {value}"
        bbox = draw.textbbox((0, 0), stat_text, font=stat_font)
        text_w = bbox[2] - bbox[0]
        draw.text(
            (center_x - text_w // 2, stats_row_y),
            stat_text,
            fill=text_color,
            font=stat_font
        )
    
        # Label below
        label_bbox = draw.textbbox((0, 0), label, font=small_font)
        label_w = label_bbox[2] - label_bbox[0]
        draw.text(
            (center_x - label_w // 2, stats_row_y + label_offset_y),
            label,
            fill=subtitle_color,
            font=small_font
        )
    
    # Final output
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
    character_bonus: int = 0,
    pay_to: str = "Employee",
    avatar_bytes: bytes = None
) -> io.BytesIO:
    """Generate a 3D coin toss animation that lands and reveals paycheck details.
    
    Args:
        job_title: Job title
        job_emoji: Job emoji (rendered if emoji font available)
        base_pay: Base pay amount
        bonus: Any bonus amount
        overtime: Whether this was an overtime shift
        character_bonus: Character-specific bonus
        pay_to: Display name of the employee
        avatar_bytes: Optional avatar image bytes to display
    
    Returns:
        BytesIO buffer containing the animated GIF
    """
    import math
    
    # Animation settings with advanced physics
    width, height = 400, 400
    frames = []
    num_frames = 30  # Extended for better physics
    
    # Physics constants
    gravity = 0.8  # pixels per frame squared
    initial_velocity_y = -12  # upward toss velocity
    air_resistance = 0.99  # velocity damping
    bounce_damping = 0.6  # energy loss per bounce
    rotation_speed = 0.3  # radians per frame
    
    # Animation state
    coin_x, coin_y = width // 2, height - 50  # start on ground
    velocity_x, velocity_y = 0, initial_velocity_y
    rotation_pitch, rotation_yaw, rotation_roll = 0, 0, 0
    camera_x, camera_y = width // 2, height // 2
    camera_tilt = 0
    ground_y = height - 50
    
    # Particle system for impact
    particles = []  # list of (x, y, vx, vy, life, color)
    
    total = base_pay + bonus + character_bonus + (base_pay if overtime else 0)
    
    for frame_num in range(num_frames):
        # Create frame
        img = Image.new('RGB', (width, height), bg_top)
        draw = ImageDraw.Draw(img)
        
        progress = frame_num / num_frames
        
        # Phase 1: Falling with physics (frames 0-16)
        if frame_num < 17:
            # Apply gravity and air resistance
            velocity_y += gravity
            velocity_y *= air_resistance
            velocity_x *= air_resistance
            
            # Update position
            coin_x += velocity_x
            coin_y += velocity_y
            
            # Multi-axis rotation
            rotation_pitch += rotation_speed * 0.8
            rotation_yaw += rotation_speed * 1.2
            rotation_roll += rotation_speed * 0.6
            
            # Camera tracking with lag
            target_camera_x = coin_x
            target_camera_y = coin_y
            camera_lag = 0.1
            camera_x += (target_camera_x - camera_x) * camera_lag
            camera_y += (target_camera_y - camera_y) * camera_lag
            
            # Camera tilt based on coin velocity
            target_tilt = velocity_y * 0.02
            camera_tilt += (target_tilt - camera_tilt) * 0.15
            
            # Check ground collision
            if coin_y >= ground_y - 25:
                coin_y = ground_y - 25
                velocity_y *= -bounce_damping
                velocity_x *= 0.8
                
                # Add impact particles
                for i in range(8):
                    angle = random.uniform(0, 2 * math.pi)
                    speed = random.uniform(2, 8)
                    particles.append({
                        'x': coin_x,
                        'y': coin_y + 25,
                        'vx': math.cos(angle) * speed,
                        'vy': math.sin(angle) * speed - random.uniform(1, 3),
                        'life': 20,
                        'color': coin_shine if random.random() < 0.3 else (200, 170, 0)
                    })
        
        # Phase 2: Multiple bounces (frames 17-23)
        elif frame_num < 24:
            # Continue physics but with multiple bounces
            velocity_y += gravity * 0.5  # reduced gravity after impact
            velocity_y *= air_resistance
            velocity_x *= air_resistance
            
            coin_x += velocity_x
            coin_y += velocity_y
            
            # Ground collision with bounce
            if coin_y >= ground_y - 25:
                coin_y = ground_y - 25
                velocity_y *= -bounce_damping
                velocity_x *= 0.8
                
                # Add smaller impact particles
                for i in range(3):
                    angle = random.uniform(-math.pi/2, math.pi/2)
                    speed = random.uniform(1, 4)
                    particles.append({
                        'x': coin_x,
                        'y': coin_y + 25,
                        'vx': math.cos(angle) * speed,
                        'vy': math.sin(angle) * speed - random.uniform(0.5, 2),
                        'life': 15,
                        'color': (150, 120, 0)
                    })
            
            # Slow rotation after impact
            rotation_pitch += rotation_speed * 0.3
            rotation_yaw += rotation_speed * 0.4
            rotation_roll += rotation_speed * 0.2
        
        # Phase 3: Reveal (frames 24-29)
        else:
            reveal_frame = frame_num - 24
            alpha = reveal_frame / 5
            
            # Background transition
            bg_color = tuple(int(bg_floor[j] * (1 - alpha) + (250, 251, 253)[j] * alpha) for j in range(3))
            draw.rectangle([0, 0, width, height], fill=bg_color)
            
            # Coin settles
            coin_y = ground_y - 25 + reveal_frame * 2
            
            # Stop physics, show final position
            
        # Apply camera transform (simulate perspective)
        render_x = coin_x - camera_x + width // 2
        render_y = coin_y - camera_y + height // 2
        
        # Apply camera tilt (rotation)
        tilt_matrix = (1, math.sin(camera_tilt)*0.1, 0, 0,
                      -math.sin(camera_tilt)*0.1, 1, 0, 0,
                      0, 0, 1, 0,
                      0, 0, 0, 1)
        
        # Draw floor with perspective
        floor_y = height - 50
        for i in range(12):
            y = floor_y + i * 4
            alpha = 1 - (i / 12) * 0.6
            color = tuple(int(bg_floor[j] * alpha + bg_top[j] * (1 - alpha)) for j in range(3))
            draw.rectangle([0, y, width, y + 4], fill=color)
        
        # Update and draw particles
        new_particles = []
        for p in particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += gravity * 0.3  # particle gravity
            p['vx'] *= 0.98  # air resistance
            p['life'] -= 1
            
            if p['life'] > 0:
                size = max(1, int(p['life'] / 4))
                alpha = p['life'] / 20
                color = tuple(int(c * alpha) for c in p['color'])
                draw.ellipse([p['x'] - size, p['y'] - size, p['x'] + size, p['y'] + size], fill=color)
                new_particles.append(p)
        particles = new_particles
        
        # Calculate 3D rotation effects
        pitch_cos = math.cos(rotation_pitch)
        yaw_cos = math.cos(rotation_yaw)
        roll_cos = math.cos(rotation_roll)
        
        # Simulate 3D coin with elliptical projection
        coin_size = 45
        coin_width = abs(int(coin_size * pitch_cos))
        coin_height = abs(int(coin_size * yaw_cos))
        
        if coin_width > 2:
            # Draw coin shadow with motion blur if moving fast
            shadow_size = max(coin_width // 3, 4)
            if abs(velocity_y) > 5:
                # Motion blur for shadow
                for blur in range(3):
                    blur_x = render_x + blur * velocity_x * 0.1
                    blur_y = ground_y + blur * 2
                    alpha = 0.3 - blur * 0.1
                    color = tuple(int(20 * alpha) for _ in range(3))
                    draw.ellipse([blur_x - shadow_size, blur_y, blur_x + shadow_size, blur_y + 4], fill=color)
            
            draw.ellipse([render_x - shadow_size, ground_y, render_x + shadow_size, ground_y + 4], fill=(20, 20, 30))
            
            # Draw coin with 3D face
            if pitch_cos > 0:
                # Front face
                draw.ellipse([render_x - coin_width//2, render_y - coin_height//2, 
                            render_x + coin_width//2, render_y + coin_height//2], 
                            fill=coin_gold)
                
                # Metallic shine effect
                shine_x = render_x - coin_width//4
                shine_y = render_y - coin_height//4
                draw.ellipse([shine_x, shine_y, shine_x + coin_width//2, shine_y + coin_height//2], 
                            fill=coin_shine)
                
                # Amount text with motion blur if fast
                if coin_width > 25 and frame_num < 24:
                    amount_text = f"{total:,}"
                    text_bbox = draw.textbbox((0, 0), amount_text, font=coin_font)
                    text_x = render_x - (text_bbox[2] - text_bbox[0]) // 2
                    text_y = render_y - 7
                    
                    if abs(velocity_y) > 3:
                        # Add motion blur to text
                        for blur in range(2):
                            blur_x = text_x + blur * velocity_x * 0.05
                            alpha = 0.5 - blur * 0.2
                            text_color = tuple(int(50 * alpha) for _ in range(3))
                            draw.text((blur_x, text_y), amount_text, fill=text_color, font=coin_font)
                    
                    draw.text((text_x, text_y), amount_text, fill=(50, 50, 50), font=coin_font)
            else:
                # Back face with job emoji
                draw.ellipse([render_x - coin_width//2, render_y - coin_height//2, 
                            render_x + coin_width//2, render_y + coin_height//2], 
                            fill=(180, 150, 0))
                if coin_width > 20 and job_emoji:
                    emoji_bbox = draw.textbbox((0, 0), job_emoji, font=amount_font)
                    emoji_x = render_x - (emoji_bbox[2] - emoji_bbox[0]) // 2
                    emoji_y = render_y - 14
                    draw.text((emoji_x, emoji_y), job_emoji, fill=coin_gold, font=amount_font)
        
        # Reveal paycheck details in final phase
        if frame_num >= 24:
            reveal_frame = frame_num - 24
            detail_alpha = min(1, reveal_frame / 4)
            text_color = tuple(int(44 * detail_alpha) for _ in range(3))
            
            # Pay to
            pay_text = f"Paid to: {pay_to}"
            text_bbox = draw.textbbox((0, 0), pay_text, font=name_font)
            text_x = (width - (text_bbox[2] - text_bbox[0])) // 2
            draw.text((text_x, 150 + reveal_frame * 5), pay_text, fill=text_color, font=name_font)
            
            # Job title
            job_text = f"Role: {job_title}"
            text_bbox = draw.textbbox((0, 0), job_text, font=name_font)
            text_x = (width - (text_bbox[2] - text_bbox[0])) // 2
            draw.text((text_x, 170 + reveal_frame * 5), job_text, fill=text_color, font=name_font)
            
            # Date
            now = datetime.now(timezone.utc)
            date_text = now.strftime('%Y-%m-%d')
            text_bbox = draw.textbbox((0, 0), date_text, font=name_font)
            text_x = (width - (text_bbox[2] - text_bbox[0])) // 2
            draw.text((text_x, 190 + reveal_frame * 5), date_text, fill=text_color, font=name_font)
        
        frames.append(img)
    
    # Create animated GIF
    buffer = io.BytesIO()
    frames[0].save(
        buffer, 
        format='GIF', 
        save_all=True, 
        append_images=frames[1:], 
        duration=80,  # Faster for smoother physics
        loop=0,
        optimize=True,
        disposal=2
    )
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
    
    # Try to load emoji-compatible font
    try:
        font = _load_emoji_font(14)
        small_font = _load_emoji_font(11)
        big_font = _load_emoji_font(18)
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
        # Arrow showing money transfer
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
# ═══════════════════════════════════════════════════════════════
# 🎲 ANIMATED GAME GIF GENERATION
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

# 🖼️ GALLERY IMAGE GENERATION - OPTIMIZED & PROFESSIONAL
# ═══════════════════════════════════════════════════════════════

# Pre-cached gradient images for speed
_GALLERY_CACHE = {}

def _create_gradient_rect(width: int, height: int, color: tuple, direction: str = "vertical") -> Image.Image:
    """Create a cached gradient rectangle - much faster than line-by-line drawing."""
    cache_key = (width, height, color, direction)
    if cache_key in _GALLERY_CACHE:
        return _GALLERY_CACHE[cache_key].copy()
    
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    
    if direction == "vertical":
        for y in range(height):
            alpha = int(200 * (1 - y / height * 0.4))
            for x in range(width):
                img.putpixel((x, y), (*color[:3], alpha))
    
    # Cache it
    if len(_GALLERY_CACHE) < 50:  # Limit cache size
        _GALLERY_CACHE[cache_key] = img.copy()
    
    return img

async def generate_gallery_image(
    characters: list,
    page: int = 1,
    cards_per_page: int = 10,
    user_name: str = "User",
    user_avatar_bytes: bytes | None = None,
    filter_type: str = "all",
    search_query: str | None = None
) -> io.BytesIO:
    """
    Generate a FAST, professional gallery grid image for character collection.
    Optimized for speed with pre-cached fonts, parallel image loading, and efficient rendering.
    """
    start_total = time.perf_counter()

    # ── LAYOUT CONFIG ────────────────────────────────────────────────────────
    cards_per_row = 5
    rows_per_page = 2
    cards_per_page = cards_per_row * rows_per_page

    card_w, card_h = 480, 640  # Larger for better visibility
    spacing_x, spacing_y = 50, 60
    header_h = 180
    footer_h = 120
    margin_x, margin_y = 70, 50

    grid_w = (card_w * cards_per_row) + (spacing_x * (cards_per_row - 1))
    grid_h = (card_h * rows_per_page) + (spacing_y * (rows_per_page - 1))
    total_w = grid_w + (margin_x * 2)
    total_h = header_h + grid_h + footer_h + (margin_y * 2)

    # Colors
    bg_color = (15, 15, 20)
    accent_color = (100, 140, 255)
    gold_color = (255, 215, 0)  # For favorites
    text_color = (255, 255, 255)

    # ── PRE-LOAD ALL FONTS ONCE ──────────────────────────────────────────────
    title_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 52)
    name_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 26)
    info_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 18)
    fav_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 20)
    page_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 32)
    uid_font = _load_font_from_assets(INTER_REGULAR_PATH, 16)
    emoji_font = _load_emoji_font(22)  # Emoji-compatible font for hearts

    # ── CREATE BASE IMAGE ────────────────────────────────────────────────────
    img = Image.new("RGB", (total_w, total_h), bg_color)
    draw = ImageDraw.Draw(img)

    # Subtle background pattern (diagonal lines)
    for i in range(0, total_w + total_h, 40):
        draw.line([(i, 0), (0, i)], fill=(20, 20, 28), width=1)

    # ── HEADER (Simplified & Fast) ───────────────────────────────────────────
    # Header background gradient
    draw.rectangle([0, 0, total_w, header_h], fill=(20, 20, 30))
    draw.rectangle([0, header_h - 3, total_w, header_h], fill=accent_color)

    avatar_size = 100
    avatar_x = margin_x + 20
    avatar_y = (header_h - avatar_size) // 2

    if user_avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(user_avatar_bytes)).convert("RGBA")
            w, h = avatar.size
            size = min(w, h)
            avatar = avatar.crop(((w-size)//2, (h-size)//2, (w+size)//2, (h+size)//2))
            avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.BILINEAR)  # BILINEAR is faster
            
            # Simple circular mask
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)
            
            # Border glow
            draw.ellipse([avatar_x-4, avatar_y-4, avatar_x+avatar_size+4, avatar_y+avatar_size+4], 
                        fill=accent_color)
            
            img.paste(avatar, (avatar_x, avatar_y), mask)
        except:
            # Placeholder circle
            draw.ellipse([avatar_x, avatar_y, avatar_x+avatar_size, avatar_y+avatar_size], 
                        fill=(60, 60, 80))

    # Title
    title_x = avatar_x + avatar_size + 30
    title_y = avatar_y + 10
    draw.text((title_x, title_y), f"{user_name}'s Collection", fill=text_color, font=title_font)

    # Stats subtitle
    total_cards = len(characters)
    total_pages = max(1, (total_cards + cards_per_page - 1) // cards_per_page)
    fav_count = sum(1 for c in characters if c.get("favorite"))
    stats_text = f"{total_cards} Cards • {fav_count} Favorites • Page {page}/{total_pages}"
    draw.text((title_x, title_y + 55), stats_text, fill=(180, 180, 200), font=info_font)

    # ── PARALLEL IMAGE FETCHING (Fast with timeout) ──────────────────────────
    start_idx = (page - 1) * cards_per_page
    end_idx = min(start_idx + cards_per_page, total_cards)
    page_characters = characters[start_idx:end_idx]

    async def fetch_image_fast(session, url, idx):
        if not url:
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=3)  # Shorter timeout
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(io.BytesIO(data)).convert("RGB")  # RGB faster than RGBA
        except:
            pass
        return None

    char_images = []
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_image_fast(session, char.get("active_cover_url") or char.get("image_url"), i) 
                 for i, char in enumerate(page_characters)]
        char_images = await asyncio.gather(*tasks)

    # ── RARITY COLORS ────────────────────────────────────────────────────────
    rarity_colors = {
        "common": (120, 120, 130),
        "uncommon": (80, 180, 80),
        "rare": (80, 140, 255),
        "epic": (180, 80, 255),
        "legendary": (255, 180, 50)
    }

    # ── GRID DRAWING (High Quality) ──────────────────────────────────────────
    grid_y = header_h + margin_y

    for i, char in enumerate(page_characters):
        row, col = divmod(i, cards_per_row)
        x = margin_x + col * (card_w + spacing_x)
        y = grid_y + row * (card_h + spacing_y)

        char_img = char_images[i] if i < len(char_images) else None
        
        # Draw high-quality card using the shared renderer
        # We disable 'is_owned' banner since this is the inventory view
        card = _draw_individual_card(
            char, 
            char_img, 
            is_claimed=False, 
            is_owned=False, 
            card_width=card_w, 
            card_height=card_h
        )
        
        # Paste card with alpha channel
        img.paste(card, (x, y), card)

    # ── FOOTER ───────────────────────────────────────────────────────────────
    footer_y = header_h + margin_y + grid_h + margin_y
    draw.rectangle([0, footer_y, total_w, total_h], fill=(20, 20, 30))
    
    # Page indicator centered
    page_text = f"Page {page} of {total_pages}"
    page_bbox = draw.textbbox((0, 0), page_text, font=page_font)
    page_x = (total_w - (page_bbox[2] - page_bbox[0])) // 2
    draw.text((page_x, footer_y + 30), page_text, fill=text_color, font=page_font)

    # Legend with star symbol
    legend_y = footer_y + 75
    legend_font = _load_font_from_assets(INTER_REGULAR_PATH, 16)
    legend_star_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 20)
    draw.text((margin_x, legend_y - 2), "★", fill=gold_color, font=legend_star_font)
    draw.text((margin_x + 26, legend_y), "= Favorited", fill=gold_color, font=legend_font)
    
    # Filter info
    if filter_type != "all" or search_query:
        filter_text = f"Filter: {filter_type}" + (f" • Search: {search_query}" if search_query else "")
        draw.text((total_w - margin_x - 300, legend_y), filter_text, fill=(120, 120, 140), font=legend_font)

    # ── SAVE TO BUFFER (No optimization for speed) ───────────────────────────
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")  # No optimize=True for speed
    buffer.seek(0)

    logger.debug(f"Gallery generated in {time.perf_counter() - start_total:.2f}s")
    return buffer

CARD_SUITS = {
    "♠": {"color": (30, 30, 30), "name": "spades"},
    "♥": {"color": (220, 50, 50), "name": "hearts"},
    "♣": {"color": (30, 30, 30), "name": "clubs"},
    "♦": {"color": (220, 50, 50), "name": "diamonds"}
}

def generate_blackjack_image(player_hand: list, dealer_hand: list, player_value: int, dealer_value: int, 
                             hide_dealer: bool = True, result: str = None, bet: int = 0, 
                             winnings: int = 0, balance: int = 0) -> io.BytesIO:
    """Generate a clean blackjack game image with proper containers and layout."""
    
    # Canvas dimensions - wider for better spacing
    width, height = 700, 480
    
    # Colors
    bg_color = (15, 45, 30)  # Dark casino green
    felt_color = (25, 75, 50)  # Lighter felt
    container_color = (20, 55, 40)  # Container background
    container_border = (40, 100, 70)  # Container border
    card_back = (35, 50, 100)
    text_color = (255, 255, 255)
    gold_color = (255, 215, 0)
    muted_text = (180, 200, 180)
    
    # Create image
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Draw main felt area
    draw.rounded_rectangle([15, 15, width-15, height-15], radius=20, fill=felt_color)
    
    # Load fonts
    try:
        title_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 20)
        card_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 24)
        small_font = _load_font_from_assets(INTER_REGULAR_PATH, 14)
        value_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 18)
        result_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 22)
    except:
        title_font = _load_emoji_font(20)
        card_font = _load_emoji_font(24)
        small_font = _load_emoji_font(14)
        value_font = _load_emoji_font(18)
        result_font = _load_emoji_font(22)
    
    # Card dimensions
    card_w, card_h = 65, 90
    card_spacing = 12
    
    # ═══════════════════════════════════════════════════════════════
    # INFO PANEL (Top Right) - Contained box
    # ═══════════════════════════════════════════════════════════════
    info_box_w, info_box_h = 150, 100
    info_x = width - info_box_w - 35
    info_y = 35
    
    # Info container
    draw.rounded_rectangle(
        [info_x, info_y, info_x + info_box_w, info_y + info_box_h],
        radius=10, fill=container_color, outline=container_border, width=2
    )
    
    # Info content with padding
    info_padding = 12
    draw.text((info_x + info_padding, info_y + info_padding), 
              "Bet", fill=muted_text, font=small_font)
    draw.text((info_x + info_padding, info_y + info_padding + 16), 
              f"{bet:,} pts", fill=gold_color, font=value_font)
    
    draw.text((info_x + info_padding, info_y + info_padding + 50), 
              "Balance", fill=muted_text, font=small_font)
    draw.text((info_x + info_padding, info_y + info_padding + 66), 
              f"{balance:,} pts", fill=text_color, font=value_font)
    
    # ═══════════════════════════════════════════════════════════════
    # DEALER SECTION - Contained box
    # ═══════════════════════════════════════════════════════════════
    dealer_box_x = 35
    dealer_box_y = 35
    dealer_box_w = info_x - dealer_box_x - 20
    dealer_box_h = 130
    
    # Dealer container
    draw.rounded_rectangle(
        [dealer_box_x, dealer_box_y, dealer_box_x + dealer_box_w, dealer_box_y + dealer_box_h],
        radius=10, fill=container_color, outline=container_border, width=2
    )
    
    # Dealer label
    draw.text((dealer_box_x + 15, dealer_box_y + 10), "DEALER", fill=muted_text, font=title_font)
    
    # Dealer value in a pill
    if hide_dealer:
        dealer_display = f"{dealer_hand[0].value}+?"
    else:
        dealer_display = str(dealer_value)
    
    value_bbox = draw.textbbox((0, 0), dealer_display, font=value_font)
    value_w = value_bbox[2] - value_bbox[0] + 20
    value_pill_x = dealer_box_x + dealer_box_w - value_w - 15
    value_pill_y = dealer_box_y + 8
    
    draw.rounded_rectangle(
        [value_pill_x, value_pill_y, value_pill_x + value_w, value_pill_y + 26],
        radius=13, fill=(40, 80, 60)
    )
    draw.text((value_pill_x + 10, value_pill_y + 4), dealer_display, fill=gold_color, font=value_font)
    
    # Dealer cards - centered in container
    total_cards_w = len(dealer_hand) * card_w + (len(dealer_hand) - 1) * card_spacing
    dealer_cards_x = dealer_box_x + (dealer_box_w - total_cards_w) // 2
    dealer_cards_y = dealer_box_y + 38
    
    for i, card in enumerate(dealer_hand):
        x = dealer_cards_x + i * (card_w + card_spacing)
        y = dealer_cards_y
        
        if hide_dealer and i == 1:
            # Draw card back
            draw.rounded_rectangle([x, y, x + card_w, y + card_h], radius=6, fill=card_back)
            draw.rounded_rectangle([x+3, y+3, x + card_w-3, y + card_h-3], radius=4, outline=(55, 70, 130), width=1)
            # Diamond pattern
            for py in range(y+12, y+card_h-12, 10):
                for px in range(x+12, x+card_w-12, 10):
                    if (py + px) % 20 == 0:
                        draw.rectangle([px, py, px+3, py+3], fill=(45, 60, 120))
        else:
            _draw_card(draw, x, y, card_w, card_h, str(card), card_font, small_font)
    
    # ═══════════════════════════════════════════════════════════════
    # PLAYER SECTION - Contained box
    # ═══════════════════════════════════════════════════════════════
    player_box_x = 35
    player_box_y = 180
    player_box_w = width - 70
    player_box_h = 130
    
    # Player container
    draw.rounded_rectangle(
        [player_box_x, player_box_y, player_box_x + player_box_w, player_box_y + player_box_h],
        radius=10, fill=container_color, outline=container_border, width=2
    )
    
    # Player label
    draw.text((player_box_x + 15, player_box_y + 10), "YOUR HAND", fill=muted_text, font=title_font)
    
    # Player value in a pill
    player_display = str(player_value)
    if player_value == 21 and len(player_hand) == 2:
        player_display = "BJ!"
        pill_color = (180, 140, 40)
    elif player_value > 21:
        player_display = f"{player_value}"
        pill_color = (140, 50, 50)
    else:
        pill_color = (40, 80, 60)
    
    value_bbox = draw.textbbox((0, 0), player_display, font=value_font)
    value_w = value_bbox[2] - value_bbox[0] + 20
    value_pill_x = player_box_x + player_box_w - value_w - 15
    value_pill_y = player_box_y + 8
    
    draw.rounded_rectangle(
        [value_pill_x, value_pill_y, value_pill_x + value_w, value_pill_y + 26],
        radius=13, fill=pill_color
    )
    draw.text((value_pill_x + 10, value_pill_y + 4), player_display, fill=gold_color, font=value_font)
    
    # Player cards - centered in container
    total_cards_w = len(player_hand) * card_w + (len(player_hand) - 1) * card_spacing
    player_cards_x = player_box_x + (player_box_w - total_cards_w) // 2
    player_cards_y = player_box_y + 38
    
    for i, card in enumerate(player_hand):
        x = player_cards_x + i * (card_w + card_spacing)
        y = player_cards_y
        _draw_card(draw, x, y, card_w, card_h, str(card), card_font, small_font)
    
    # ═══════════════════════════════════════════════════════════════
    # RESULT BANNER (Bottom) - Only if game over
    # ═══════════════════════════════════════════════════════════════
    if result:
        result_box_x = 35
        result_box_y = 325
        result_box_w = width - 70
        result_box_h = 65
        
        # Determine colors based on result
        if "win" in result.lower() or "blackjack" in result.lower():
            banner_color = (35, 100, 50)
            banner_border = (60, 150, 80)
            emoji = "🎉"
        elif "push" in result.lower() or "tie" in result.lower():
            banner_color = (100, 90, 35)
            banner_border = (150, 140, 60)
            emoji = "🤝"
        else:
            banner_color = (100, 40, 40)
            banner_border = (150, 60, 60)
            emoji = "💔"
        
        # Result container
        draw.rounded_rectangle(
            [result_box_x, result_box_y, result_box_x + result_box_w, result_box_y + result_box_h],
            radius=10, fill=banner_color, outline=banner_border, width=2
        )
        
        # Result text - centered
        result_text = f"{emoji} {result}"
        result_bbox = draw.textbbox((0, 0), result_text, font=result_font)
        result_text_w = result_bbox[2] - result_bbox[0]
        result_x = result_box_x + (result_box_w - result_text_w) // 2
        draw.text((result_x, result_box_y + 12), result_text, fill=text_color, font=result_font)
        
        # Winnings info below result
        if winnings != 0:
            if winnings > 0:
                win_text = f"+{winnings:,} pts"
                win_color = (150, 255, 150)
            else:
                win_text = f"{winnings:,} pts"
                win_color = (255, 150, 150)
            
            win_bbox = draw.textbbox((0, 0), win_text, font=value_font)
            win_text_w = win_bbox[2] - win_bbox[0]
            win_x = result_box_x + (result_box_w - win_text_w) // 2
            draw.text((win_x, result_box_y + 38), win_text, fill=win_color, font=value_font)
    
    # ═══════════════════════════════════════════════════════════════
    # FOOTER - Instructions or status
    # ═══════════════════════════════════════════════════════════════
    footer_y = height - 45
    if not result:
        footer_text = "Hit to draw • Stand to hold • Double to double bet"
        footer_bbox = draw.textbbox((0, 0), footer_text, font=small_font)
        footer_x = (width - (footer_bbox[2] - footer_bbox[0])) // 2
        draw.text((footer_x, footer_y), footer_text, fill=muted_text, font=small_font)
    else:
        footer_text = f"Final Balance: {balance:,} pts"
        footer_bbox = draw.textbbox((0, 0), footer_text, font=small_font)
        footer_x = (width - (footer_bbox[2] - footer_bbox[0])) // 2
        draw.text((footer_x, footer_y), footer_text, fill=gold_color, font=small_font)
    
    # Save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _draw_card(draw, x: int, y: int, w: int, h: int, card_str: str, card_font, small_font):
    """Draw a single playing card."""
    # Card background
    draw.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=(255, 255, 255))
    draw.rounded_rectangle([x+2, y+2, x + w-2, y + h-2], radius=6, outline=(200, 200, 200), width=1)
    
    # Parse card string (e.g., "A♠", "10♥")
    if len(card_str) >= 2:
        if card_str[-1] in CARD_SUITS:
            suit = card_str[-1]
            rank = card_str[:-1]
        else:
            suit = "♠"
            rank = card_str
    else:
        suit = "♠"
        rank = card_str
    
    suit_color = CARD_SUITS.get(suit, {}).get("color", (30, 30, 30))
    
    # Draw rank in top-left
    draw.text((x + 8, y + 5), rank, fill=suit_color, font=card_font)
    
    # Draw suit in center
    suit_bbox = draw.textbbox((0, 0), suit, font=card_font)
    suit_w = suit_bbox[2] - suit_bbox[0]
    draw.text((x + (w - suit_w) // 2, y + h // 2 - 10), suit, fill=suit_color, font=card_font)
    
    # Draw rank in bottom-right (upside down effect - just smaller)
    draw.text((x + w - 25, y + h - 35), rank, fill=suit_color, font=small_font)


async def generate_gambling_stats_image(user_name: str, avatar_url: str, stats: dict) -> io.BytesIO:
    """Generate a gambling statistics card for a user."""
    
    width, height = 500, 350
    
    # Colors
    bg_gradient_top = (25, 25, 35)
    bg_gradient_bottom = (15, 15, 25)
    accent_color = (255, 180, 50)
    text_color = (255, 255, 255)
    subtext_color = (180, 180, 200)
    positive_color = (100, 255, 100)
    negative_color = (255, 100, 100)
    
    # Create image with gradient
    img = Image.new("RGB", (width, height), bg_gradient_top)
    draw = ImageDraw.Draw(img)
    
    # Simple gradient effect
    for y in range(height):
        ratio = y / height
        r = int(bg_gradient_top[0] * (1 - ratio) + bg_gradient_bottom[0] * ratio)
        g = int(bg_gradient_top[1] * (1 - ratio) + bg_gradient_bottom[1] * ratio)
        b = int(bg_gradient_top[2] * (1 - ratio) + bg_gradient_bottom[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Load fonts
    try:
        title_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 28)
        stat_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 22)
        label_font = _load_font_from_assets(INTER_REGULAR_PATH, 14)
        value_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 18)
    except:
        title_font = _load_emoji_font(28)
        stat_font = _load_emoji_font(22)
        label_font = _load_emoji_font(14)
        value_font = _load_emoji_font(18)
    
    # Draw border
    draw.rounded_rectangle([5, 5, width-5, height-5], radius=15, outline=accent_color, width=2)
    
    # Avatar
    avatar_size = 80
    avatar_x, avatar_y = 30, 30
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    avatar_data = await resp.read()
                    avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA")
                    avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
                    
                    # Circular mask
                    mask = Image.new("L", (avatar_size, avatar_size), 0)
                    mask_draw = ImageDraw.Draw(mask)
                    mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)
                    
                    # Border
                    draw.ellipse([avatar_x-3, avatar_y-3, avatar_x+avatar_size+3, avatar_y+avatar_size+3], 
                                fill=accent_color)
                    
                    img.paste(avatar, (avatar_x, avatar_y), mask)
    except:
        draw.ellipse([avatar_x, avatar_y, avatar_x+avatar_size, avatar_y+avatar_size], fill=(60, 60, 80))
    
    # Title
    draw.text((avatar_x + avatar_size + 20, avatar_y + 10), f"{user_name}", fill=text_color, font=title_font)
    draw.text((avatar_x + avatar_size + 20, avatar_y + 45), "Gambling Stats", fill=subtext_color, font=label_font)
    
    # Stats grid
    stats_y = 130
    col_width = (width - 60) // 3
    
    stat_items = [
        ("🎰 Games", stats.get("total_games", 0)),
        ("🏆 Wins", stats.get("wins", 0)),
        ("💔 Losses", stats.get("losses", 0)),
        ("💰 Total Bet", f"{stats.get('total_bet', 0):,}"),
        ("📈 Total Won", f"{stats.get('total_won', 0):,}"),
        ("📉 Net Profit", stats.get('net_profit', 0)),
    ]
    
    for i, (label, value) in enumerate(stat_items):
        row = i // 3
        col = i % 3
        x = 30 + col * col_width
        y = stats_y + row * 80
        
        # Draw stat box
        box_w, box_h = col_width - 20, 65
        draw.rounded_rectangle([x, y, x + box_w, y + box_h], radius=10, fill=(40, 40, 55))
        
        # Label
        draw.text((x + 10, y + 8), label, fill=subtext_color, font=label_font)
        
        # Value
        if isinstance(value, int) and "Profit" in label:
            value_color = positive_color if value >= 0 else negative_color
            value_text = f"+{value:,}" if value >= 0 else f"{value:,}"
        else:
            value_color = text_color
            value_text = str(value) if isinstance(value, str) else f"{value:,}"
        
        draw.text((x + 10, y + 32), value_text, fill=value_color, font=value_font)
    
    # Win rate bar
    bar_y = height - 60
    total_games = stats.get("total_games", 0)
    wins = stats.get("wins", 0)
    win_rate = (wins / total_games * 100) if total_games > 0 else 0
    
    draw.text((30, bar_y - 25), f"Win Rate: {win_rate:.1f}%", fill=text_color, font=label_font)
    
    # Progress bar background
    bar_x, bar_w, bar_h = 30, width - 60, 20
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=10, fill=(50, 50, 70))
    
    # Progress bar fill
    fill_w = int(bar_w * (win_rate / 100))
    if fill_w > 0:
        fill_color = positive_color if win_rate >= 50 else (255, 180, 50) if win_rate >= 30 else negative_color
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=10, fill=fill_color)
    
    # Save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def generate_coinflip_gif(result: str) -> io.BytesIO:
    pass