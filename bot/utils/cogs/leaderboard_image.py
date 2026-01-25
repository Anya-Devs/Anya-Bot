import io
import os
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class LeaderboardImageGenerator:
    """Generate clean, modern leaderboard images."""

    def __init__(self):
        self.width = 800
        self.padding = 24
        
        # Colors - Enhanced for better contrast
        self.bg = (10, 12, 18)
        self.card_bg = (22, 25, 35)
        self.card_bg_light = (32, 36, 48)
        self.card_border = (55, 60, 75)
        self.gold = (255, 215, 0)
        self.gold_glow = (255, 235, 100)
        self.silver = (192, 192, 192)
        self.silver_glow = (220, 220, 220)
        self.bronze = (205, 127, 50)
        self.bronze_glow = (235, 157, 80)
        self.accent = (139, 92, 246)  # Purple accent
        self.accent_glow = (169, 132, 255)
        self.text_white = (255, 255, 255)
        self.text_gray = (180, 185, 195)
        self.text_dim = (120, 125, 135)
        self.shadow = (0, 0, 0, 180)
        
        self.rank_colors = {1: self.gold, 2: self.silver, 3: self.bronze}
        self.rank_emojis = {1: "1st", 2: "2nd", 3: "3rd"}
        
        # Fonts
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        fonts = os.path.join(base, "data", "assets", "fonts")
        self.font_regular = os.path.join(fonts, "Poppins-Regular.ttf")
        self.font_bold = os.path.join(fonts, "Poppins-SemiBold.ttf")
        self.font_emoji = os.path.join(fonts, "NotoColorEmoji.ttf")
        
        if not os.path.exists(self.font_regular):
            self.font_regular = self.font_bold = None
        if not os.path.exists(self.font_emoji):
            self.font_emoji = None

    def _font(self, size, bold=False):
        path = self.font_bold if bold else self.font_regular
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
        return ImageFont.load_default()
    
    def _draw_text_with_emoji(self, draw, pos, text, font, fill, emoji_font=None):
        """Draw text with emoji support by using fallback font for emojis"""
        x, y = pos
        for char in text:
            # Check if character is emoji (simplified check)
            if ord(char) > 0x1F300 or char in ['🃏', '📋', '⭐', '|']:
                # Use emoji font if available, otherwise skip
                if emoji_font:
                    draw.text((x, y), char, font=emoji_font, fill=fill)
                else:
                    draw.text((x, y), char, font=font, fill=fill)
            else:
                draw.text((x, y), char, font=font, fill=fill)
            
            # Get character width for positioning
            bbox = draw.textbbox((0, 0), char, font=font)
            x += bbox[2] - bbox[0]

    async def fetch_avatar(self, url: str, size: int) -> Image.Image:
        """Fetch circular avatar."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(url), timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        img = Image.open(io.BytesIO(data)).convert("RGBA")
                        img = img.resize((size, size), Image.LANCZOS)
                        
                        # Circular mask
                        mask = Image.new("L", (size * 4, size * 4), 0)
                        ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
                        mask = mask.resize((size, size), Image.LANCZOS)
                        
                        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                        output.paste(img, (0, 0), mask)
                        return output
        except:
            pass
        
        # Placeholder
        placeholder = Image.new("RGBA", (size, size), (60, 65, 80, 255))
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
        mask = mask.resize((size, size), Image.LANCZOS)
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(placeholder, (0, 0), mask)
        return output

    async def generate(self, entries: list, title: str = "LEADERBOARD") -> io.BytesIO:
        """Generate a clean, modern leaderboard image."""
        
        # Layout calculations
        header_h = 80
        top3_h = 200
        row_h = 72
        row_gap = 8
        
        rest = [e for e in entries if e["rank"] > 3]
        list_h = len(rest) * (row_h + row_gap) if rest else 0
        total_h = header_h + top3_h + list_h + self.padding * 2 + 20
        
        # Create image
        img = Image.new("RGBA", (self.width, total_h), self.bg)
        draw = ImageDraw.Draw(img)
        
        # === HEADER ===
        title_font = self._font(32, bold=True)
        sub_font = self._font(13)
        
        # Title centered
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = bbox[2] - bbox[0]
        draw.text(((self.width - title_w) // 2, 20), title, fill=self.accent, font=title_font)
        
        # Subtitle
        subtitle = "Ranked by Stella Points"
        bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
        sub_w = bbox[2] - bbox[0]
        draw.text(((self.width - sub_w) // 2, 58), subtitle, fill=self.text_dim, font=sub_font)
        
        # === TOP 3 PODIUM ===
        top3 = sorted([e for e in entries if e["rank"] <= 3], key=lambda x: x["rank"])
        
        # Positions: 2nd on left, 1st in center (higher), 3rd on right
        positions = {
            2: (self.width // 4, header_h + 50),
            1: (self.width // 2, header_h + 20),
            3: (3 * self.width // 4, header_h + 50),
        }
        avatar_sizes = {1: 80, 2: 65, 3: 65}
        
        avatar_tasks = []
        for entry in top3:
            rank = entry["rank"]
            cx, cy = positions[rank]
            av_size = avatar_sizes[rank]
            avatar_tasks.append((entry, cx, cy, av_size))
        
        # Draw top 3 cards first (without avatars)
        for entry, cx, cy, av_size in avatar_tasks:
            rank = entry["rank"]
            color = self.rank_colors[rank]
            
            # Card dimensions
            card_w, card_h = 180 if rank == 1 else 160, 130 if rank == 1 else 115
            card_x = cx - card_w // 2
            card_y = cy + av_size // 2 + 5
            
            # Draw card shadow for depth
            shadow_offset = 4
            draw.rounded_rectangle(
                [card_x + shadow_offset, card_y + shadow_offset, card_x + card_w + shadow_offset, card_y + card_h + shadow_offset],
                radius=12, fill=(0, 0, 0, 100)
            )
            
            # Draw card background with gradient effect
            draw.rounded_rectangle(
                [card_x, card_y, card_x + card_w, card_y + card_h],
                radius=12, fill=self.card_bg, outline=color, width=3
            )
            
            # Inner glow
            draw.rounded_rectangle(
                [card_x + 2, card_y + 2, card_x + card_w - 2, card_y + card_h - 2],
                radius=10, outline=self.card_bg_light, width=1
            )
            
            # Rank badge with shadow and glow
            badge_size = 32 if rank == 1 else 28
            badge_x = cx - badge_size // 2
            badge_y = card_y - badge_size // 2
            
            # Badge shadow
            draw.ellipse([badge_x + 2, badge_y + 2, badge_x + badge_size + 2, badge_y + badge_size + 2], fill=(0, 0, 0, 150))
            
            # Badge outer glow
            glow_color = self.gold_glow if rank == 1 else (self.silver_glow if rank == 2 else self.bronze_glow)
            for i in range(3):
                offset = i * 2
                alpha = 100 - (i * 30)
                draw.ellipse([badge_x - offset, badge_y - offset, badge_x + badge_size + offset, badge_y + badge_size + offset], 
                           outline=(*glow_color, alpha), width=2)
            
            # Badge fill
            draw.ellipse([badge_x, badge_y, badge_x + badge_size, badge_y + badge_size], fill=color)
            
            # Badge inner highlight
            draw.ellipse([badge_x + 3, badge_y + 3, badge_x + badge_size - 3, badge_y + badge_size - 3], 
                        outline=(255, 255, 255, 80), width=2)
            
            # Rank text with shadow
            rank_font = self._font(16 if rank == 1 else 14, bold=True)
            rank_text = str(rank)
            bbox = draw.textbbox((0, 0), rank_text, font=rank_font)
            rw = bbox[2] - bbox[0]
            # Text shadow
            draw.text((cx - rw // 2 + 1, badge_y + 7), rank_text, fill=(0, 0, 0, 200), font=rank_font)
            # Text
            draw.text((cx - rw // 2, badge_y + 6), rank_text, fill=(0, 0, 0), font=rank_font)
            
            # Username with text shadow for depth
            name_font = self._font(16 if rank == 1 else 14, bold=True)
            username = entry.get("username", "Unknown")
            display = username[:14] + "…" if len(username) > 14 else username
            bbox = draw.textbbox((0, 0), display, font=name_font)
            nw = bbox[2] - bbox[0]
            # Text shadow
            draw.text((cx - nw // 2 + 1, card_y + 21), display, fill=(0, 0, 0, 200), font=name_font)
            # Text with white color
            draw.text((cx - nw // 2, card_y + 20), display, fill=self.text_white, font=name_font)
            
            # Points with glow effect
            pts_font = self._font(24 if rank == 1 else 20, bold=True)
            pts_text = f"{entry['points']:,}"
            bbox = draw.textbbox((0, 0), pts_text, font=pts_font)
            pw = bbox[2] - bbox[0]
            # Glow effect
            for offset in [(0, 1), (1, 0), (-1, 0), (0, -1)]:
                draw.text((cx - pw // 2 + offset[0], card_y + 45 + offset[1]), pts_text, fill=glow_color, font=pts_font)
            # Main text
            draw.text((cx - pw // 2, card_y + 45), pts_text, fill=color, font=pts_font)
            
            # Stats row
            stat_font = self._font(10)
            cards = entry.get("cards", 0)
            quests = entry.get("quests_done", 0)
            stats = f"{cards} cards  |  {quests} quests"
            bbox = draw.textbbox((0, 0), stats, font=stat_font)
            sw = bbox[2] - bbox[0]
            draw.text((cx - sw // 2, card_y + card_h - 28), stats, fill=self.text_gray, font=stat_font)
            
            # Avatar ring with glow
            ring_x = cx - av_size // 2 - 4
            ring_y = cy - 4
            # Outer glow
            for i in range(3):
                offset = i * 2
                alpha = 120 - (i * 40)
                draw.ellipse([ring_x - offset, ring_y - offset, ring_x + av_size + 8 + offset, ring_y + av_size + 8 + offset], 
                           outline=(*glow_color, alpha), width=2)
            # Main ring
            draw.ellipse([ring_x, ring_y, ring_x + av_size + 8, ring_y + av_size + 8], outline=color, width=4)
            # Inner highlight
            draw.ellipse([ring_x + 2, ring_y + 2, ring_x + av_size + 6, ring_y + av_size + 6], 
                        outline=(255, 255, 255, 60), width=2)
        
        # Fetch and paste avatars for top 3
        for entry, cx, cy, av_size in avatar_tasks:
            avatar_url = entry.get("avatar_url")
            if avatar_url:
                avatar = await self.fetch_avatar(avatar_url, av_size)
                img.paste(avatar, (cx - av_size // 2, cy), avatar)
        
        # === LIST ENTRIES (Rank 4+) ===
        y = header_h + top3_h + 20
        row_x = self.padding
        row_w = self.width - self.padding * 2
        
        for entry in rest:
            rank = entry["rank"]
            
            # Row shadow
            draw.rounded_rectangle(
                [row_x + 2, y + 2, row_x + row_w + 2, y + row_h + 2],
                radius=10, fill=(0, 0, 0, 80)
            )
            
            # Row background with border
            draw.rounded_rectangle(
                [row_x, y, row_x + row_w, y + row_h],
                radius=10, fill=self.card_bg, outline=self.card_border, width=2
            )
            
            # Inner highlight
            draw.rounded_rectangle(
                [row_x + 2, y + 2, row_x + row_w - 2, y + row_h - 2],
                radius=8, outline=self.card_bg_light, width=1
            )
            
            # Rank number
            rank_font = self._font(18, bold=True)
            rank_text = str(rank)
            draw.text((row_x + 24, y + row_h // 2 - 12), rank_text, fill=self.text_dim, font=rank_font)
            
            # Avatar placeholder position
            av_x = row_x + 65
            av_y = y + (row_h - 48) // 2
            
            # Avatar border with glow
            draw.ellipse([av_x - 3, av_y - 3, av_x + 51, av_y + 51], outline=(0, 0, 0, 100), width=2)
            draw.ellipse([av_x - 2, av_y - 2, av_x + 50, av_y + 50], outline=self.accent, width=3)
            draw.ellipse([av_x, av_y, av_x + 48, av_y + 48], outline=(255, 255, 255, 40), width=1)
            
            # Fetch avatar
            avatar_url = entry.get("avatar_url")
            if avatar_url:
                avatar = await self.fetch_avatar(avatar_url, 48)
                img.paste(avatar, (av_x, av_y), avatar)
            
            # Username with shadow
            name_font = self._font(16, bold=True)
            username = entry["username"]
            display = username[:22] + "…" if len(username) > 22 else username
            # Shadow
            draw.text((av_x + 61, y + 17), display, fill=(0, 0, 0, 180), font=name_font)
            # Text
            draw.text((av_x + 60, y + 16), display, fill=self.text_white, font=name_font)
            
            # Stats
            stat_font = self._font(11)
            cards = entry.get("cards", 0)
            quests = entry.get("quests_done", 0)
            reviews = entry.get("reviews", 0)
            stats = f"{cards} cards  |  {quests} quests  |  {reviews} reviews"
            draw.text((av_x + 60, y + 40), stats, fill=self.text_gray, font=stat_font)
            
            # Points on right with glow
            pts_font = self._font(22, bold=True)
            pts_text = f"{entry['points']:,}"
            bbox = draw.textbbox((0, 0), pts_text, font=pts_font)
            pw = bbox[2] - bbox[0]
            pts_x = row_x + row_w - pw - 24
            pts_y = y + row_h // 2 - 12
            # Glow
            for offset in [(0, 1), (1, 0), (-1, 0), (0, -1)]:
                draw.text((pts_x + offset[0], pts_y + offset[1]), pts_text, fill=self.gold_glow, font=pts_font)
            # Main text
            draw.text((pts_x, pts_y), pts_text, fill=self.gold, font=pts_font)
            
            y += row_h + row_gap
        
        # Save
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer
