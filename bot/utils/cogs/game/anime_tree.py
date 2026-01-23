"""
Anime Hierarchy Tree Generator for Gacha System
Creates visual family tree-style diagrams grouping characters by anime
"""

import io
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from difflib import SequenceMatcher
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

def fuzzy_match_anime(anime1: str, anime2: str, threshold: float = 0.75) -> bool:
    """
    Check if two anime names are similar using fuzzy matching.
    
    Args:
        anime1: First anime name
        anime2: Second anime name
        threshold: Similarity threshold (0-1)
    
    Returns:
        True if names are similar enough
    """
    if not anime1 or not anime2:
        return False
    
    # Normalize strings
    a1 = anime1.lower().strip()
    a2 = anime2.lower().strip()
    
    # Exact match
    if a1 == a2:
        return True
    
    # Check if one contains the other
    if a1 in a2 or a2 in a1:
        return True
    
    # Use SequenceMatcher for fuzzy comparison
    ratio = SequenceMatcher(None, a1, a2).ratio()
    return ratio >= threshold


def group_characters_by_anime(characters: list) -> dict:
    """
    Group characters by anime using fuzzy matching.
    
    Args:
        characters: List of character dictionaries
    
    Returns:
        Dictionary mapping anime names to character lists
    """
    anime_groups = {}
    anime_representatives = {}  # Maps normalized anime to canonical name
    
    for char in characters:
        anime = char.get("anime", "Unknown")
        if not anime:
            anime = "Unknown"
        
        # Find matching group
        matched = False
        for canonical_anime in anime_representatives.keys():
            if fuzzy_match_anime(anime, canonical_anime):
                # Add to existing group
                anime_groups[anime_representatives[canonical_anime]].append(char)
                matched = True
                break
        
        if not matched:
            # Create new group
            anime_representatives[anime] = anime
            anime_groups[anime] = [char]
    
    return anime_groups


async def generate_anime_hierarchy_tree(
    characters: list,
    user_name: str = "User",
    user_avatar_bytes: bytes = None
) -> io.BytesIO:
    """
    Generate a large hierarchy tree diagram showing characters grouped by anime.
    
    Args:
        characters: List of character dictionaries with 'anime', 'name', 'image_url', etc.
        user_name: Username for header
        user_avatar_bytes: Optional avatar bytes for header
    
    Returns:
        BytesIO buffer containing the PNG image
    """
    from bot.utils.cogs.game.images import _draw_individual_card, _load_font_from_assets, _load_emoji_font
    from bot.utils.cogs.game.const import POPPINS_SEMIBOLD_PATH, INTER_REGULAR_PATH
    
    # Group characters by anime
    anime_groups = group_characters_by_anime(characters)
    
    # Sort groups by size (largest first) and limit to prevent huge images
    sorted_groups = sorted(anime_groups.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    
    # Card dimensions
    card_w, card_h = 320, 440  # Larger cards for better visibility
    
    # Layout configuration
    header_h = 200
    footer_h = 100
    margin_x, margin_y = 80, 60
    anime_title_h = 80
    vertical_spacing = 100  # Space between anime groups
    horizontal_spacing = 60  # Space between cards
    
    # Calculate dimensions
    max_cards_per_row = 6  # Maximum cards per anime row
    
    # Calculate total height needed
    total_height = header_h + margin_y
    for anime, chars in sorted_groups:
        rows_needed = (len(chars) + max_cards_per_row - 1) // max_cards_per_row
        total_height += anime_title_h + (card_h * rows_needed) + ((rows_needed - 1) * horizontal_spacing) + vertical_spacing
    total_height += footer_h
    
    # Calculate width (use max cards per row)
    total_width = margin_x * 2 + (card_w * max_cards_per_row) + (horizontal_spacing * (max_cards_per_row - 1))
    
    # Ensure minimum dimensions
    total_width = max(total_width, 2400)
    total_height = max(total_height, 1200)
    
    # Colors
    bg_color = (12, 12, 18)
    accent_color = (100, 140, 255)
    text_color = (255, 255, 255)
    anime_bg_color = (25, 25, 35)
    
    # Create base image
    img = Image.new("RGB", (total_width, total_height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # Load fonts
    try:
        title_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 56)
        anime_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 42)
        info_font = _load_font_from_assets(POPPINS_SEMIBOLD_PATH, 22)
        count_font = _load_font_from_assets(INTER_REGULAR_PATH, 18)
    except:
        title_font = anime_font = info_font = count_font = ImageFont.load_default()
    
    # ═══════════════════════════════════════════════════════════════
    # HEADER
    # ═══════════════════════════════════════════════════════════════
    
    # Header background with gradient effect
    for y in range(header_h):
        alpha = int(255 * (1 - y / header_h))
        color = (20 + alpha // 12, 20 + alpha // 12, 30 + alpha // 8)
        draw.line([(0, y), (total_width, y)], fill=color)
    
    # Accent line
    draw.rectangle([0, header_h - 4, total_width, header_h], fill=accent_color)
    
    # Avatar
    avatar_size = 120
    avatar_x = margin_x + 30
    avatar_y = (header_h - avatar_size) // 2 - 10
    
    if user_avatar_bytes:
        try:
            avatar = Image.open(io.BytesIO(user_avatar_bytes)).convert("RGBA")
            w, h = avatar.size
            size = min(w, h)
            avatar = avatar.crop(((w-size)//2, (h-size)//2, (w+size)//2, (h+size)//2))
            avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
            
            # Circular mask
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)
            
            # Glow border
            draw.ellipse([avatar_x-5, avatar_y-5, avatar_x+avatar_size+5, avatar_y+avatar_size+5], 
                        fill=accent_color)
            
            img.paste(avatar, (avatar_x, avatar_y), mask)
        except:
            draw.ellipse([avatar_x, avatar_y, avatar_x+avatar_size, avatar_y+avatar_size], 
                        fill=(60, 60, 80))
    
    # Title
    title_x = avatar_x + avatar_size + 40
    title_y = avatar_y + 15
    draw.text((title_x, title_y), f"{user_name}'s Anime Collection", fill=text_color, font=title_font)
    
    # Stats
    total_chars = len(characters)
    total_anime = len(anime_groups)
    stats_text = f"{total_chars} Characters • {total_anime} Anime Series"
    draw.text((title_x, title_y + 65), stats_text, fill=(180, 180, 200), font=info_font)
    
    # ═══════════════════════════════════════════════════════════════
    # FETCH ALL CHARACTER IMAGES IN PARALLEL
    # ═══════════════════════════════════════════════════════════════
    
    async def fetch_char_image(session, char):
        url = char.get("active_cover_url") or char.get("image_url")
        if not url:
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(io.BytesIO(data)).convert("RGB")
        except:
            pass
        return None
    
    # Fetch all images
    char_images = {}
    async with aiohttp.ClientSession() as session:
        tasks = []
        for anime, chars in sorted_groups:
            for char in chars:
                tasks.append((char.get("uid"), fetch_char_image(session, char)))
        
        results = await asyncio.gather(*[task[1] for task in tasks])
        for (uid, _), img in zip(tasks, results):
            if uid:
                char_images[uid] = img
    
    # ═══════════════════════════════════════════════════════════════
    # DRAW ANIME GROUPS
    # ═══════════════════════════════════════════════════════════════
    
    current_y = header_h + margin_y
    
    for anime, chars in sorted_groups:
        # Draw anime title banner
        banner_x = margin_x
        banner_y = current_y
        banner_w = total_width - margin_x * 2
        
        # Banner background with rounded corners
        draw.rounded_rectangle(
            [banner_x, banner_y, banner_x + banner_w, banner_y + anime_title_h],
            radius=12,
            fill=anime_bg_color,
            outline=accent_color,
            width=3
        )
        
        # Anime title
        anime_text = anime[:50]  # Truncate if too long
        anime_bbox = draw.textbbox((0, 0), anime_text, font=anime_font)
        anime_x = banner_x + 30
        anime_y = banner_y + (anime_title_h - (anime_bbox[3] - anime_bbox[1])) // 2
        
        # Shadow
        draw.text((anime_x + 2, anime_y + 2), anime_text, fill=(0, 0, 0, 180), font=anime_font)
        # Main text
        draw.text((anime_x, anime_y), anime_text, fill=text_color, font=anime_font)
        
        # Character count badge
        count_text = f"{len(chars)} character{'s' if len(chars) != 1 else ''}"
        count_bbox = draw.textbbox((0, 0), count_text, font=count_font)
        count_x = banner_x + banner_w - (count_bbox[2] - count_bbox[0]) - 30
        count_y = banner_y + (anime_title_h - (count_bbox[3] - count_bbox[1])) // 2
        
        # Count badge background
        badge_padding = 12
        draw.rounded_rectangle(
            [count_x - badge_padding, count_y - badge_padding,
             count_x + (count_bbox[2] - count_bbox[0]) + badge_padding, 
             count_y + (count_bbox[3] - count_bbox[1]) + badge_padding],
            radius=8,
            fill=accent_color
        )
        draw.text((count_x, count_y), count_text, fill=(255, 255, 255), font=count_font)
        
        # Draw character cards in a grid
        current_y += anime_title_h + 40
        
        for i, char in enumerate(chars):
            row = i // max_cards_per_row
            col = i % max_cards_per_row
            
            # Calculate card position
            card_x = margin_x + col * (card_w + horizontal_spacing)
            card_y = current_y + row * (card_h + horizontal_spacing)
            
            # Get character image
            char_img = char_images.get(char.get("uid"))
            
            # Draw card using the same style as .draw command
            card = _draw_individual_card(
                char,
                char_img,
                is_claimed=False,
                is_owned=False,
                card_width=card_w,
                card_height=card_h
            )
            
            # Draw connecting line from banner to first row
            if row == 0:
                line_start_x = banner_x + banner_w // 2
                line_start_y = banner_y + anime_title_h
                line_end_x = card_x + card_w // 2
                line_end_y = card_y
                
                # Draw vertical line from banner
                draw.line([(line_start_x, line_start_y), (line_start_x, line_start_y + 20)], 
                         fill=accent_color, width=3)
                
                # Draw horizontal line to cards
                if col == 0:
                    # First card - direct connection
                    draw.line([(line_start_x, line_start_y + 20), (line_end_x, line_start_y + 20)], 
                             fill=accent_color, width=3)
                    draw.line([(line_end_x, line_start_y + 20), (line_end_x, line_end_y)], 
                             fill=accent_color, width=3)
                elif col < len(chars):
                    # Horizontal line across all cards in first row
                    first_card_x = margin_x + card_w // 2
                    last_card_x = margin_x + min(len(chars) - 1, max_cards_per_row - 1) * (card_w + horizontal_spacing) + card_w // 2
                    
                    if col == 0:
                        draw.line([(line_start_x, line_start_y + 20), (last_card_x, line_start_y + 20)], 
                                 fill=accent_color, width=3)
                    
                    # Vertical line to each card
                    draw.line([(line_end_x, line_start_y + 20), (line_end_x, line_end_y)], 
                             fill=accent_color, width=3)
            
            # Paste card
            img.paste(card, (card_x, card_y), card)
        
        # Update Y position for next anime group
        rows_used = (len(chars) + max_cards_per_row - 1) // max_cards_per_row
        current_y += rows_used * (card_h + horizontal_spacing) + vertical_spacing
    
    # ═══════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════
    
    footer_y = total_height - footer_h
    draw.rectangle([0, footer_y, total_width, total_height], fill=(20, 20, 30))
    
    footer_text = "Anime Hierarchy Tree • Characters grouped by series"
    footer_bbox = draw.textbbox((0, 0), footer_text, font=info_font)
    footer_x = (total_width - (footer_bbox[2] - footer_bbox[0])) // 2
    draw.text((footer_x, footer_y + 35), footer_text, fill=(150, 150, 170), font=info_font)
    
    # Save to buffer
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=False)
    buffer.seek(0)
    
    logger.info(f"Generated anime hierarchy tree: {total_anime} anime, {total_chars} characters")
    return buffer
