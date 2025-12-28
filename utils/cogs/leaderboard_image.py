import io
import os
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class LeaderboardImageGenerator:
    """Generate modern leaderboard images with pink theme and glass effect."""

    def __init__(self):
        self.width = 580
        self.header_height = 70
        self.row_height = 70
        self.row_spacing = 10
        self.avatar_size = 48
        self.padding = 20
        
        # Pink/purple color scheme
        self.bg_gradient_top = (50, 30, 65)
        self.bg_gradient_bottom = (30, 18, 45)
        self.row_bg = (80, 50, 95, 160)
        self.row_bg_top3 = (100, 60, 120, 180)
        self.accent_pink = (255, 105, 180)
        self.text_color = (255, 255, 255)
        self.text_muted = (200, 180, 210)
        self.points_color = (255, 200, 220)
        
        # Medal colors (main, glow)
        self.medal_colors = {
            1: ((255, 215, 0), (255, 200, 100)),
            2: ((200, 200, 215), (180, 180, 200)),
            3: ((205, 127, 50), (180, 120, 80)),
        }
        
        # Local font paths
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        fonts_dir = os.path.join(base_path, "data", "assets", "fonts")
        
        self.font_path = os.path.join(fonts_dir, "Poppins-Regular.ttf")
        self.font_bold_path = os.path.join(fonts_dir, "Poppins-SemiBold.ttf")
        
        # Verify fonts exist, fallback to system if not
        if not os.path.exists(self.font_path):
            self.font_path = None
            for path in ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]:
                try:
                    ImageFont.truetype(path, 20)
                    self.font_path = path
                    break
                except:
                    continue
        if not os.path.exists(self.font_bold_path):
            self.font_bold_path = self.font_path

    def _get_font(self, size: int, bold: bool = False):
        path = self.font_bold_path if bold and self.font_bold_path else self.font_path
        if path:
            return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    def _create_gradient_bg(self, width: int, height: int) -> Image.Image:
        """Create vertical gradient background."""
        img = Image.new("RGBA", (width, height))
        for y in range(height):
            ratio = y / height
            r = int(self.bg_gradient_top[0] * (1 - ratio) + self.bg_gradient_bottom[0] * ratio)
            g = int(self.bg_gradient_top[1] * (1 - ratio) + self.bg_gradient_bottom[1] * ratio)
            b = int(self.bg_gradient_top[2] * (1 - ratio) + self.bg_gradient_bottom[2] * ratio)
            for x in range(width):
                img.putpixel((x, y), (r, g, b, 255))
        return img

    def _draw_rounded_rect(self, draw: ImageDraw.Draw, xy: tuple, radius: int, fill: tuple):
        """Draw rounded rectangle."""
        x1, y1, x2, y2 = xy
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
        draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
        draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
        draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill)

    def _add_glow(self, img: Image.Image, x: int, y: int, size: int, color: tuple, intensity: int = 12) -> Image.Image:
        """Add soft glow effect."""
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        for i in range(intensity, 0, -2):
            alpha = int(60 * (i / intensity))
            offset = (intensity - i) * 2
            glow_draw.ellipse([
                x - size - offset, y - size - offset,
                x + size + offset, y + size + offset
            ], fill=(*color[:3], alpha))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=6))
        return Image.alpha_composite(img, glow)

    async def fetch_avatar(self, url: str, size: int = None) -> Image.Image:
        """Fetch and return circular avatar."""
        size = size or self.avatar_size
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(url)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        img = Image.open(io.BytesIO(data)).convert("RGBA")
                        img = img.resize((size, size), Image.LANCZOS)
                        mask = Image.new("L", (size * 4, size * 4), 0)
                        ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
                        mask = mask.resize((size, size), Image.LANCZOS)
                        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                        output.paste(img, (0, 0), mask)
                        return output
        except:
            pass
        # Placeholder
        placeholder = Image.new("RGBA", (size, size), (90, 60, 100, 255))
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
        mask = mask.resize((size, size), Image.LANCZOS)
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(placeholder, (0, 0), mask)
        return output

    def _draw_medal(self, img: Image.Image, x: int, y: int, rank: int) -> Image.Image:
        """Draw medal with glow for top 3."""
        if rank not in self.medal_colors:
            return img
        color, glow = self.medal_colors[rank]
        img = self._add_glow(img, x, y, 14, glow, intensity=10)
        draw = ImageDraw.Draw(img)
        draw.ellipse([x - 14, y - 14, x + 14, y + 14], fill=color, outline=(255, 255, 255, 200), width=2)
        font = self._get_font(13, bold=True)
        text = str(rank)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x - tw // 2, y - 8), text, fill=(40, 25, 15), font=font)
        return img

    async def generate(self, entries: list, title: str = "LEADERBOARD") -> io.BytesIO:
        """
        Generate leaderboard image.
        
        entries: list of dicts with:
            - rank: int
            - username: str
            - points: int
            - quests_done: int (optional)
            - avatar_url: str (optional)
        """
        num_rows = len(entries)
        total_height = self.header_height + (self.row_height + self.row_spacing) * num_rows + self.padding
        
        img = self._create_gradient_bg(self.width, total_height)
        
        # Title
        font_title = self._get_font(26, bold=True)
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), title, font=font_title)
        title_w = bbox[2] - bbox[0]
        title_x = (self.width - title_w) // 2
        
        # Add glow behind title
        img = self._add_glow(img, self.width // 2, 32, 50, self.accent_pink, intensity=8)
        draw = ImageDraw.Draw(img)
        draw.text((title_x, 18), title, fill=self.accent_pink, font=font_title)
        
        # Decorative line
        draw.line([(60, self.header_height - 12), (self.width - 60, self.header_height - 12)],
                  fill=(*self.accent_pink, 80), width=2)
        
        font_name = self._get_font(15, bold=True)
        font_stats = self._get_font(12)
        font_points = self._get_font(16, bold=True)
        
        y = self.header_height
        row_x = self.padding
        row_width = self.width - 2 * self.padding
        
        for entry in entries:
            rank = entry["rank"]
            username = entry["username"]
            points = entry["points"]
            quests_done = entry.get("quests_done", 0)
            avatar_url = entry.get("avatar_url")
            is_top3 = rank <= 3
            
            # Row background
            row_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            row_draw = ImageDraw.Draw(row_layer)
            bg_color = self.row_bg_top3 if is_top3 else self.row_bg
            self._draw_rounded_rect(row_draw, (row_x, y, row_x + row_width, y + self.row_height), 12, bg_color)
            img = Image.alpha_composite(img, row_layer)
            
            # Glow for top 3
            if is_top3:
                img = self._add_glow(img, row_x + 35, y + self.row_height // 2, 18, self.medal_colors[rank][1], 8)
            
            draw = ImageDraw.Draw(img)
            
            # Medal or rank
            medal_x = row_x + 35
            medal_y = y + self.row_height // 2
            if is_top3:
                img = self._draw_medal(img, medal_x, medal_y, rank)
                draw = ImageDraw.Draw(img)
            else:
                font_rank = self._get_font(18, bold=True)
                draw.text((medal_x - 8, medal_y - 10), str(rank), fill=self.text_muted, font=font_rank)
            
            # Avatar
            avatar_x = row_x + 70
            avatar_y = y + (self.row_height - self.avatar_size) // 2
            draw.ellipse([avatar_x - 2, avatar_y - 2, avatar_x + self.avatar_size + 2, avatar_y + self.avatar_size + 2],
                         outline=self.accent_pink if is_top3 else (150, 120, 160), width=2)
            if avatar_url:
                avatar = await self.fetch_avatar(avatar_url)
                img.paste(avatar, (avatar_x, avatar_y), avatar)
                draw = ImageDraw.Draw(img)
            
            # Username and quests
            name_x = avatar_x + self.avatar_size + 14
            display_name = username[:15] + "…" if len(username) > 15 else username
            draw.text((name_x, y + 18), display_name, fill=self.text_color, font=font_name)
            draw.text((name_x, y + 40), f"{quests_done} quests", fill=self.text_muted, font=font_stats)
            
            # Points
            pts_text = f"{points:,}"
            pts_bbox = draw.textbbox((0, 0), pts_text, font=font_points)
            pts_w = pts_bbox[2] - pts_bbox[0]
            pts_x = row_x + row_width - pts_w - 45
            draw.text((pts_x, y + 20), pts_text, fill=self.points_color if is_top3 else self.text_color, font=font_points)
            draw.text((pts_x + pts_w + 4, y + 23), "pts", fill=self.text_muted, font=font_stats)
            
            y += self.row_height + self.row_spacing
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer
