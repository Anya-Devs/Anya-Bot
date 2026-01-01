
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
    • Real-time leaderboard updates
    • Achievement and statistics cards

🎮 SUPPORTED GAMES:
    • Wordle - Word guessing with visual boards and multiplayer leaderboards
    • Hangman - Letter guessing with hangman ASCII art
    • Gacha System - Character cards with rarity frames
    • Slot Machine - Animated reels with symbol rendering
    • Number Guessing - Thermometer visualizations
    • Coin Flip - Animated coin toss GIFs
    • Dice Rolling - Animated dice with various sides
    • Work/Jobs - Professional paycheck generation
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
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import aiohttp
from .fonts import _load_emoji_font

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
    
    # Try to load emoji-compatible fonts
    try:
        title_font = _load_emoji_font(22)
        name_font = _load_emoji_font(14)
        small_font = _load_emoji_font(11)
        number_font = _load_emoji_font(28)
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
    
    # Try to load emoji-compatible fonts
    try:
        name_font = _load_emoji_font(20)
        stat_font = _load_emoji_font(14)
        small_font = _load_emoji_font(11)
        big_font = _load_emoji_font(24)
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
    
    # Try to load emoji-compatible font
    try:
        font = _load_emoji_font(28)
        small_font = _load_emoji_font(14)
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
