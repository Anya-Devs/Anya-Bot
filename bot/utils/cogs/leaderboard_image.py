import io
import os
import aiohttp
from PIL import Image, ImageDraw, ImageFont


class LeaderboardImageGenerator:
    """Clean, readable leaderboard image generator."""

    # ═══════════════════════════════════════════════════════════════
    # CONFIGURATION - Modify all settings here
    # ═══════════════════════════════════════════════════════════════

    # Image dimensions
    WIDTH = 800  # Image width in pixels
    PADDING = 30  # Space around edges

    # Layout spacing
    HEADER_HEIGHT = 120  # Height of header section
    ROW_HEIGHT = 90  # Height of each leaderboard row
    ROW_GAP = 10  # Space between rows
    FOOTER_HEIGHT = 70  # Height of footer section

    # Font sizes (in pixels)
    TITLE_FONT_SIZE = 60  # Main title
    USERNAME_FONT_SIZE = 22  # User names
    RANK_FONT_SIZE = 32  # Rank numbers
    POINTS_FONT_SIZE = 18  # Point values
    STATS_FONT_SIZE = 13  # Stats text
    LABEL_FONT_SIZE = 11  # Small labels

    # Avatar settings
    AVATAR_SIZE = 56  # Avatar image size in pixels

    # Username truncation
    MAX_USERNAME_LENGTH = 18  # Max characters before truncation

    # Positioning (X, Y coordinates)
    TITLE_Y = 30  # Title vertical position
    RANK_X_OFFSET = 35  # Rank horizontal offset from left (centered)
    AVATAR_X_OFFSET = 85  # Avatar horizontal offset from left
    USERNAME_X_OFFSET = 18  # Username horizontal offset from avatar
    USERNAME_Y_OFFSET = 17  # Username vertical offset from row top
    STATS_Y_OFFSET = 32  # Stats vertical offset from username
    POINTS_X_OFFSET = 25  # Points horizontal offset from right
    POINTS_Y_OFFSET = -12  # Points vertical offset from center
    LABEL_Y_OFFSET = 4  # Label vertical offset from points
    PAGE_Y_OFFSET = 30  # Page text vertical offset from footer top

    # Colors (RGB tuples)
    BG_COLOR = (24, 24, 32)  # Main background
    CARD_BG = (32, 32, 42)  # Card background
    CARD_BORDER = (50, 50, 65)  # Card border

    # Accent colors
    GOLD = (255, 200, 80)  # 1st place
    SILVER = (200, 200, 210)  # 2nd place
    BRONZE = (205, 140, 80)  # 3rd place

    # Text colors
    TEXT_WHITE = (255, 255, 255)  # Primary text
    TEXT_MUTED = (150, 150, 165)  # Secondary text

    # ═══════════════════════════════════════════════════════════════
    # END CONFIGURATION - Don't modify below this line
    # ═══════════════════════════════════════════════════════════════

    def __init__(self):
        # Apply configuration
        self.width = self.WIDTH
        self.padding = self.PADDING

        # Colors
        self.bg_color = self.BG_COLOR
        self.card_bg = self.CARD_BG
        self.card_border = self.CARD_BORDER

        # Accent colors
        self.gold = self.GOLD
        self.silver = self.SILVER
        self.bronze = self.BRONZE

        # Text colors
        self.text_white = self.TEXT_WHITE
        self.text_muted = self.TEXT_MUTED

        # Rank colors mapping
        self.rank_colors = {1: self.gold, 2: self.silver, 3: self.bronze}

        # Fonts - fix path resolution
        # This file is at: bot/utils/cogs/leaderboard_image.py
        # We need to go up to project root, then to data/assets/fonts
        current_file = os.path.abspath(__file__)
        # Go up: leaderboard_image.py -> cogs -> utils -> bot -> project_root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        fonts_dir = os.path.join(project_root, "data", "assets", "fonts")
        
        self.font_regular = os.path.join(fonts_dir, "Poppins-Regular.ttf")
        self.font_bold = os.path.join(fonts_dir, "Poppins-SemiBold.ttf")
        
        if not os.path.exists(self.font_regular):
            self.font_regular = self.font_bold = None

    def _font(self, size, bold=False):
        """Load font with fallback."""
        path = self.font_bold if bold else self.font_regular
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                return ImageFont.load_default()
        return ImageFont.load_default()

    async def fetch_avatar(self, url: str, size: int) -> Image.Image:
        """Fetch and return circular avatar."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(url), timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        img = Image.open(io.BytesIO(data)).convert("RGBA")
                        img = img.resize((size, size), Image.LANCZOS)
                        
                        # Create circular mask
                        mask = Image.new("L", (size, size), 0)
                        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
                        
                        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                        output.paste(img, (0, 0), mask)
                        return output
        except:
            pass
        
        # Placeholder avatar
        placeholder = Image.new("RGBA", (size, size), (60, 60, 70, 255))
        draw = ImageDraw.Draw(placeholder)
        draw.ellipse([size//4, size//4, size*3//4, size*3//4], fill=(100, 100, 120))
        
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(placeholder, (0, 0), mask)
        return output

    async def generate(self, entries: list, title: str = "LEADERBOARD", page: int = 1, total_pages: int = 1) -> io.BytesIO:
        """Generate a modern UI/UX leaderboard with proper visual hierarchy."""
        
        # Layout constants - use configuration
        header_h = self.HEADER_HEIGHT
        row_h = self.ROW_HEIGHT
        row_gap = self.ROW_GAP
        footer_h = self.FOOTER_HEIGHT
        
        # Calculate total height
        num_entries = len(entries)
        content_h = num_entries * (row_h + row_gap)
        total_h = header_h + content_h + footer_h + self.padding * 2
        total_h = max(total_h, 500)
        
        # Create image with solid background
        img = Image.new("RGB", (self.width, total_h), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # ═══════════════════════════════════════════════════════════════
        # HEADER - Large, bold title
        # ═══════════════════════════════════════════════════════════════
        
        # Main title - very large and bold
        title_font = self._font(self.TITLE_FONT_SIZE, bold=True)
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = title_bbox[2] - title_bbox[0]
        title_x = (self.width - title_w) // 2
        title_y = self.TITLE_Y
        draw.text((title_x, title_y), title, fill=self.text_white, font=title_font)
        
        # Minimal separator
        line_y = header_h - 15
        draw.line([(self.padding * 2, line_y), (self.width - self.padding * 2, line_y)], 
                  fill=self.card_border, width=1)
        
        # ═══════════════════════════════════════════════════════════════
        # ENTRIES - Card-based layout with clear information hierarchy
        # ═══════════════════════════════════════════════════════════════
        
        y = header_h + 15
        row_x = self.padding
        row_w = self.width - self.padding * 2
        
        for entry in entries:
            rank = entry["rank"]
            
            # Card background with subtle elevation
            draw.rounded_rectangle(
                [row_x, y, row_x + row_w, y + row_h],
                radius=14,
                fill=self.card_bg,
                outline=self.card_border,
                width=1
            )
            
            # === RANK - Prominent badge ===
            rank_color = self.rank_colors.get(rank, self.text_muted)
            rank_font = self._font(self.RANK_FONT_SIZE, bold=True)
            rank_text = f"{rank}"
            rank_bbox = draw.textbbox((0, 0), rank_text, font=rank_font)
            rank_w = rank_bbox[2] - rank_bbox[0]
            rank_h = rank_bbox[3] - rank_bbox[1]
            rank_x = row_x + self.RANK_X_OFFSET
            rank_y = y + (row_h - rank_h) // 2
            draw.text((rank_x, rank_y), rank_text, fill=rank_color, font=rank_font)
            
            # === AVATAR ===
            av_size = self.AVATAR_SIZE
            av_x = row_x + self.AVATAR_X_OFFSET
            av_y = y + (row_h - av_size) // 2
            
            # Highlight border for top 3
            if rank <= 3:
                draw.ellipse([av_x - 3, av_y - 3, av_x + av_size + 3, av_y + av_size + 3], 
                            outline=rank_color, width=3)
            
            avatar_url = entry.get("avatar_url")
            if avatar_url:
                avatar = await self.fetch_avatar(avatar_url, av_size)
                img.paste(avatar, (av_x, av_y), avatar)
            
            # === USER INFO SECTION ===
            info_x = av_x + av_size + self.USERNAME_X_OFFSET
            
            # Username - much larger and bold
            name_font = self._font(self.USERNAME_FONT_SIZE, bold=True)
            username = entry.get("username", "Unknown")
            if len(username) > self.MAX_USERNAME_LENGTH:
                username = username[:self.MAX_USERNAME_LENGTH-2] + "..."
            
            name_bbox = draw.textbbox((0, 0), username, font=name_font)
            name_h = name_bbox[3] - name_bbox[1]
            name_y = y + self.USERNAME_Y_OFFSET
            draw.text((info_x, name_y), username, fill=self.text_white, font=name_font)
            
            # Stats - secondary information with labels
            stat_font = self._font(self.STATS_FONT_SIZE)
            stat_y = name_y + self.STATS_Y_OFFSET
            
            cards = entry.get("cards", 0)
            quests = entry.get("quests_done", 0)
            reviews = entry.get("reviews", 0)
            
            # Format rating (out of 5) - no rounding
            rating = f"{reviews}/5" if isinstance(reviews, (int, float)) else f"{reviews}/5"
            
            # Structured stats display
            stats_text = f"Cards {cards}  |  Quests {quests}  |  Rating {rating}"
            draw.text((info_x, stat_y), stats_text, fill=self.text_muted, font=stat_font)
            
            # === POINTS - Most prominent metric ===
            # Large, bold number for visual impact
            pts_font = self._font(self.POINTS_FONT_SIZE, bold=True)
            pts_text = f"{entry['points']:,}"
            pts_bbox = draw.textbbox((0, 0), pts_text, font=pts_font)
            pts_w = pts_bbox[2] - pts_bbox[0]
            pts_h = pts_bbox[3] - pts_bbox[1]
            pts_x = row_x + row_w - pts_w - self.POINTS_X_OFFSET
            pts_y = y + (row_h - pts_h) // 2 + self.POINTS_Y_OFFSET
            draw.text((pts_x, pts_y), pts_text, fill=self.gold, font=pts_font)
            
            # Label below points
            label_font = self._font(self.LABEL_FONT_SIZE)
            label_text = ""
            label_bbox = draw.textbbox((0, 0), label_text, font=label_font)
            label_w = label_bbox[2] - label_bbox[0]
            label_x = pts_x + (pts_w - label_w) // 2
            draw.text((label_x, pts_y + pts_h + self.LABEL_Y_OFFSET), label_text, fill=self.text_muted, font=label_font)
            
            y += row_h + row_gap
        
        # ═══════════════════════════════════════════════════════════════
        # FOOTER - Pagination info
        # ═══════════════════════════════════════════════════════════════
        
        footer_y = total_h - footer_h
        
        # Separator
        draw.line([(self.padding * 2, footer_y + 10), (self.width - self.padding * 2, footer_y + 10)], 
                  fill=self.card_border, width=1)
        
        # Page indicator
        page_font = self._font(self.STATS_FONT_SIZE)
        page_text = f"Page {page} of {total_pages}"
        page_bbox = draw.textbbox((0, 0), page_text, font=page_font)
        page_w = page_bbox[2] - page_bbox[0]
        draw.text(((self.width - page_w) // 2, footer_y + self.PAGE_Y_OFFSET), page_text, fill=self.text_muted, font=page_font)
        
        # Save to buffer
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer
