import io
import os
import math
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance


class LeaderboardImageGenerator:
    """Generate stunning 3D leaderboard images with detailed statistics."""

    def __init__(self):
        # Larger dimensions for more detailed display
        self.width = 1200
        self.header_height = 140
        self.podium_height = 420
        self.row_height = 85
        self.row_spacing = 10
        self.avatar_size = 60
        self.podium_avatar_sizes = {1: 120, 2: 100, 3: 100}
        self.padding = 40
        
        # Premium dark theme color palette
        self.bg_dark = (8, 12, 18)
        self.bg_mid = (14, 20, 28)
        self.bg_light = (22, 30, 42)
        self.card_bg = (18, 25, 35, 230)
        self.card_border = (40, 55, 75, 180)
        
        # Accent colors
        self.accent_gold = (255, 200, 80)
        self.accent_silver = (200, 210, 225)
        self.accent_bronze = (205, 140, 85)
        self.accent_pink = (255, 120, 170)
        self.accent_teal = (80, 200, 200)
        self.accent_green = (80, 200, 120)
        
        # Text colors
        self.text_white = (255, 255, 255)
        self.text_light = (220, 225, 235)
        self.text_muted = (140, 150, 170)
        self.text_dim = (100, 110, 130)
        
        # Medal/Rank colors with gradients
        self.rank_colors = {
            1: {"main": (255, 200, 80), "glow": (255, 180, 50, 100), "label": "#1"},
            2: {"main": (200, 210, 225), "glow": (180, 190, 210, 80), "label": "#2"},
            3: {"main": (205, 140, 85), "glow": (180, 120, 70, 80), "label": "#3"},
        }
        
        # Load fonts
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        fonts_dir = os.path.join(base_path, "data", "assets", "fonts")
        
        self.font_path = os.path.join(fonts_dir, "Poppins-Regular.ttf")
        self.font_bold_path = os.path.join(fonts_dir, "Poppins-SemiBold.ttf")
        self.font_black_path = os.path.join(fonts_dir, "Poppins-Bold.ttf")
        
        # Fallback fonts
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
        if not os.path.exists(self.font_black_path):
            self.font_black_path = self.font_bold_path

    def _get_font(self, size: int, bold: bool = False, black: bool = False):
        """Get font with specified size and weight."""
        if black and self.font_black_path:
            path = self.font_black_path
        elif bold and self.font_bold_path:
            path = self.font_bold_path
        else:
            path = self.font_path
        if path:
            return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    def _draw_rounded_rect(self, draw: ImageDraw.Draw, xy: tuple, radius: int, 
                           fill: tuple, outline: tuple = None, outline_width: int = 1):
        """Draw a rounded rectangle with optional outline."""
        x1, y1, x2, y2 = xy
        
        # Draw filled rounded rect
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        draw.ellipse([x1, y1, x1 + 2*radius, y1 + 2*radius], fill=fill)
        draw.ellipse([x2 - 2*radius, y1, x2, y1 + 2*radius], fill=fill)
        draw.ellipse([x1, y2 - 2*radius, x1 + 2*radius, y2], fill=fill)
        draw.ellipse([x2 - 2*radius, y2 - 2*radius, x2, y2], fill=fill)
        
        # Draw outline if specified
        if outline:
            draw.arc([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=outline, width=outline_width)
            draw.arc([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=outline, width=outline_width)
            draw.arc([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=outline, width=outline_width)
            draw.arc([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=outline, width=outline_width)
            draw.line([(x1 + radius, y1), (x2 - radius, y1)], fill=outline, width=outline_width)
            draw.line([(x1 + radius, y2), (x2 - radius, y2)], fill=outline, width=outline_width)
            draw.line([(x1, y1 + radius), (x1, y2 - radius)], fill=outline, width=outline_width)
            draw.line([(x2, y1 + radius), (x2, y2 - radius)], fill=outline, width=outline_width)

    def _create_gradient_background(self, width: int, height: int) -> Image.Image:
        """Create a premium dark gradient background with subtle effects."""
        bg = Image.new("RGBA", (width, height))
        
        # Multi-point vertical gradient
        for y in range(height):
            ratio = y / height
            if ratio < 0.3:
                # Top section - lighter
                t = ratio / 0.3
                r = int(self.bg_light[0] * (1 - t) + self.bg_mid[0] * t)
                g = int(self.bg_light[1] * (1 - t) + self.bg_mid[1] * t)
                b = int(self.bg_light[2] * (1 - t) + self.bg_mid[2] * t)
            else:
                # Bottom section - darker
                t = (ratio - 0.3) / 0.7
                r = int(self.bg_mid[0] * (1 - t) + self.bg_dark[0] * t)
                g = int(self.bg_mid[1] * (1 - t) + self.bg_dark[1] * t)
                b = int(self.bg_mid[2] * (1 - t) + self.bg_dark[2] * t)
            for x in range(width):
                bg.putpixel((x, y), (r, g, b, 255))
        
        # Add grid pattern for depth
        grid_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        grid_draw = ImageDraw.Draw(grid_layer)
        
        grid_spacing = 60
        grid_color = (255, 255, 255, 8)
        
        # Horizontal lines with perspective effect
        for y in range(0, height, grid_spacing):
            fade = max(0, 15 - int(15 * (y / height)))
            grid_draw.line([(0, y), (width, y)], fill=(*grid_color[:3], fade), width=1)
        
        # Vertical scanlines
        for x in range(0, width, grid_spacing):
            grid_draw.line([(x, 0), (x, height)], fill=(*grid_color[:3], 5), width=1)
        
        bg = Image.alpha_composite(bg, grid_layer)
        
        # Add ambient glow spots
        glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        
        # Top center pink glow
        for i in range(8):
            size = 200 + i * 80
            alpha = max(0, 18 - i * 2)
            glow_draw.ellipse([
                width // 2 - size, -size // 2,
                width // 2 + size, size
            ], fill=(*self.accent_pink[:3], alpha))
        
        # Bottom corners teal glow
        for i in range(5):
            size = 150 + i * 60
            alpha = max(0, 12 - i * 2)
            glow_draw.ellipse([-size // 2, height - size // 2, size, height + size // 2], 
                             fill=(*self.accent_teal[:3], alpha))
            glow_draw.ellipse([width - size, height - size // 2, width + size // 2, height + size // 2], 
                             fill=(*self.accent_teal[:3], alpha))
        
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=50))
        bg = Image.alpha_composite(bg, glow_layer)
        
        return bg

    def _draw_3d_podium(self, img: Image.Image, width: int, base_y: int) -> Image.Image:
        """Draw a 3D podium with perspective effect inspired by reference images."""
        draw = ImageDraw.Draw(img)
        
        # Podium dimensions with 3D perspective
        podium_configs = {
            1: {"x": width // 2, "height": 140, "width": 200, "depth": 35},
            2: {"x": int(width * 0.25), "height": 100, "width": 180, "depth": 30},
            3: {"x": int(width * 0.75), "height": 85, "width": 180, "depth": 30},
        }
        
        # Draw podiums from back to front (3rd, 2nd, 1st)
        for rank in [3, 2, 1]:
            config = podium_configs[rank]
            cx = config["x"]
            ph = config["height"]
            pw = config["width"]
            depth = config["depth"]
            
            # Calculate podium vertices
            top_y = base_y - ph
            bottom_y = base_y
            left_x = cx - pw // 2
            right_x = cx + pw // 2
            
            # 3D effect colors
            rank_color = self.rank_colors[rank]["main"]
            dark_color = tuple(max(0, c - 60) for c in rank_color)
            darker_color = tuple(max(0, c - 100) for c in rank_color)
            
            # Draw back face (darker)
            back_points = [
                (left_x + depth, top_y - depth),
                (right_x + depth, top_y - depth),
                (right_x + depth, bottom_y - depth),
                (left_x + depth, bottom_y - depth)
            ]
            draw.polygon(back_points, fill=darker_color)
            
            # Draw right side face
            right_points = [
                (right_x, top_y),
                (right_x + depth, top_y - depth),
                (right_x + depth, bottom_y - depth),
                (right_x, bottom_y)
            ]
            draw.polygon(right_points, fill=dark_color)
            
            # Draw top face with gradient effect
            top_points = [
                (left_x, top_y),
                (left_x + depth, top_y - depth),
                (right_x + depth, top_y - depth),
                (right_x, top_y)
            ]
            draw.polygon(top_points, fill=rank_color)
            
            # Draw front face (main)
            front_points = [
                (left_x, top_y),
                (right_x, top_y),
                (right_x, bottom_y),
                (left_x, bottom_y)
            ]
            
            # Create gradient effect on front face
            for i in range(ph):
                ratio = i / ph
                fade_color = tuple(int(rank_color[j] * (1 - ratio * 0.3)) for j in range(3))
                draw.line([(left_x, top_y + i), (right_x, top_y + i)], fill=fade_color, width=1)
            
            # Add highlight line at top
            draw.line([(left_x + 5, top_y + 2), (right_x - 5, top_y + 2)], 
                     fill=(255, 255, 255, 100), width=2)
            
            # Add rank number on podium
            font_rank = self._get_font(42 if rank == 1 else 36, black=True)
            rank_text = f"#{rank}"
            bbox = draw.textbbox((0, 0), rank_text, font=font_rank)
            text_w = bbox[2] - bbox[0]
            text_x = cx - text_w // 2
            text_y = top_y + ph // 2 - 20
            
            # Draw rank with shadow
            draw.text((text_x + 2, text_y + 2), rank_text, fill=(0, 0, 0, 150), font=font_rank)
            draw.text((text_x, text_y), rank_text, fill=self.text_white, font=font_rank)
        
        return img

    def _draw_stat_box(self, draw: ImageDraw.Draw, x: int, y: int, width: int, 
                       label: str, value: str, color: tuple, font_label, font_value):
        """Draw a stat box with label and value."""
        box_height = 50
        self._draw_rounded_rect(draw, (x, y, x + width, y + box_height), 8, 
                               (25, 35, 50, 200), outline=(50, 65, 85, 150), outline_width=1)
        
        # Label (top)
        bbox = draw.textbbox((0, 0), label, font=font_label)
        label_w = bbox[2] - bbox[0]
        draw.text((x + (width - label_w) // 2, y + 6), label, fill=self.text_muted, font=font_label)
        
        # Value (bottom)
        bbox = draw.textbbox((0, 0), value, font=font_value)
        value_w = bbox[2] - bbox[0]
        draw.text((x + (width - value_w) // 2, y + 25), value, fill=color, font=font_value)

    async def fetch_avatar(self, url: str, size: int = None) -> Image.Image:
        """Fetch and return circular avatar with border."""
        size = size or self.avatar_size
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(url)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        img = Image.open(io.BytesIO(data)).convert("RGBA")
                        img = img.resize((size, size), Image.LANCZOS)
                        
                        # Create circular mask with anti-aliasing
                        mask = Image.new("L", (size * 4, size * 4), 0)
                        ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
                        mask = mask.resize((size, size), Image.LANCZOS)
                        
                        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                        output.paste(img, (0, 0), mask)
                        return output
        except:
            pass
        
        # Placeholder avatar
        placeholder = Image.new("RGBA", (size, size), (60, 70, 90, 255))
        mask = Image.new("L", (size * 4, size * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size * 4, size * 4), fill=255)
        mask = mask.resize((size, size), Image.LANCZOS)
        output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        output.paste(placeholder, (0, 0), mask)
        return output

    def _draw_podium_entry(self, img: Image.Image, entry: dict, cx: int, 
                           avatar_y: int, rank: int) -> tuple:
        """Draw a podium entry with avatar, name, and stats."""
        draw = ImageDraw.Draw(img)
        
        rank_config = self.rank_colors[rank]
        main_color = rank_config["main"]
        avatar_size = self.podium_avatar_sizes[rank]
        is_first = rank == 1
        
        # Position avatar
        avatar_x = cx - avatar_size // 2
        
        # Draw glow behind avatar
        glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_radius = avatar_size // 2 + (15 if is_first else 10)
        for i in range(12 if is_first else 8):
            alpha = max(0, 40 - i * 4)
            offset = i * 3
            glow_draw.ellipse([
                cx - glow_radius - offset, avatar_y + avatar_size // 2 - glow_radius - offset,
                cx + glow_radius + offset, avatar_y + avatar_size // 2 + glow_radius + offset
            ], fill=(*main_color[:3], alpha))
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=8))
        img = Image.alpha_composite(img, glow_layer)
        draw = ImageDraw.Draw(img)
        
        # Draw avatar ring
        ring_width = 5 if is_first else 4
        ring_offset = ring_width + 2
        draw.ellipse([
            avatar_x - ring_offset, avatar_y - ring_offset,
            avatar_x + avatar_size + ring_offset, avatar_y + avatar_size + ring_offset
        ], outline=main_color, width=ring_width)
        
        # Info card below avatar
        card_width = 200 if is_first else 180
        card_height = 130 if is_first else 115
        card_x = cx - card_width // 2
        card_y = avatar_y + avatar_size + 15
        
        self._draw_rounded_rect(draw, 
            (card_x, card_y, card_x + card_width, card_y + card_height), 
            12, self.card_bg, outline=main_color + (100,), outline_width=2)
        
        # Username
        font_name = self._get_font(18 if is_first else 16, bold=True)
        username = entry["username"]
        display_name = username[:14] + "…" if len(username) > 14 else username
        bbox = draw.textbbox((0, 0), display_name, font=font_name)
        name_w = bbox[2] - bbox[0]
        name_x = cx - name_w // 2
        draw.text((name_x, card_y + 10), display_name, fill=self.text_white, font=font_name)
        
        # Points (main stat)
        font_points = self._get_font(24 if is_first else 20, black=True)
        points = entry["points"]
        points_text = f"{points:,}"
        bbox = draw.textbbox((0, 0), points_text, font=font_points)
        pts_w = bbox[2] - bbox[0]
        pts_x = cx - pts_w // 2
        draw.text((pts_x, card_y + 35), points_text, fill=main_color, font=font_points)
        
        # Stats row
        font_stat_label = self._get_font(10)
        font_stat_value = self._get_font(13, bold=True)
        
        stat_y = card_y + 70
        stat_width = (card_width - 30) // 3
        
        # Cards
        cards = entry.get("cards", 0)
        self._draw_mini_stat(draw, card_x + 10, stat_y, stat_width, "CARDS", 
                            str(cards), self.accent_teal, font_stat_label, font_stat_value)
        
        # Quests
        quests = entry.get("quests_done", 0)
        self._draw_mini_stat(draw, card_x + 10 + stat_width, stat_y, stat_width, "QUESTS", 
                            str(quests), self.accent_green, font_stat_label, font_stat_value)
        
        # Reviews
        reviews = entry.get("reviews", 0)
        self._draw_mini_stat(draw, card_x + 10 + stat_width * 2, stat_y, stat_width, "REVIEWS", 
                            str(reviews), self.accent_pink, font_stat_label, font_stat_value)
        
        return img, avatar_x, avatar_y, avatar_size

    def _draw_mini_stat(self, draw, x, y, width, label, value, color, font_label, font_value):
        """Draw a mini stat indicator."""
        # Label
        bbox = draw.textbbox((0, 0), label, font=font_label)
        label_w = bbox[2] - bbox[0]
        draw.text((x + (width - label_w) // 2, y), label, fill=self.text_dim, font=font_label)
        
        # Value
        bbox = draw.textbbox((0, 0), value, font=font_value)
        value_w = bbox[2] - bbox[0]
        draw.text((x + (width - value_w) // 2, y + 15), value, fill=color, font=font_value)

    def _draw_list_entry(self, img: Image.Image, entry: dict, y: int, 
                         row_width: int, row_x: int) -> tuple:
        """Draw a list entry row for ranks 4+."""
        draw = ImageDraw.Draw(img)
        
        # Row background card
        row_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        row_draw = ImageDraw.Draw(row_layer)
        self._draw_rounded_rect(row_draw, 
            (row_x, y, row_x + row_width, y + self.row_height), 
            14, self.card_bg, outline=self.card_border, outline_width=1)
        img = Image.alpha_composite(img, row_layer)
        draw = ImageDraw.Draw(img)
        
        rank = entry["rank"]
        
        # Rank circle
        rank_font = self._get_font(18, bold=True)
        rank_text = str(rank)
        rank_cx = row_x + 45
        rank_cy = y + self.row_height // 2
        
        # Rank circle background
        draw.ellipse([rank_cx - 20, rank_cy - 20, rank_cx + 20, rank_cy + 20], 
                    fill=(30, 40, 55, 220))
        
        bbox = draw.textbbox((0, 0), rank_text, font=rank_font)
        rank_w = bbox[2] - bbox[0]
        draw.text((rank_cx - rank_w // 2, rank_cy - 11), rank_text, 
                 fill=self.text_muted, font=rank_font)
        
        # Avatar position
        avatar_x = row_x + 85
        avatar_y = y + (self.row_height - self.avatar_size) // 2
        
        # Avatar border
        draw.ellipse([
            avatar_x - 3, avatar_y - 3,
            avatar_x + self.avatar_size + 3, avatar_y + self.avatar_size + 3
        ], outline=(60, 80, 100), width=2)
        
        # Username and stats
        name_x = avatar_x + self.avatar_size + 18
        
        font_name = self._get_font(16, bold=True)
        font_stats = self._get_font(12)
        
        username = entry["username"]
        display_name = username[:20] + "…" if len(username) > 20 else username
        draw.text((name_x, y + 18), display_name, fill=self.text_white, font=font_name)
        
        # Inline stats
        quests = entry.get("quests_done", 0)
        cards = entry.get("cards", 0)
        reviews = entry.get("reviews", 0)
        
        stats_text = f"📋 {quests} quests  •  🃏 {cards} cards  •  ⭐ {reviews} reviews"
        draw.text((name_x, y + 45), stats_text, fill=self.text_muted, font=font_stats)
        
        # Points on the right
        font_points = self._get_font(22, bold=True)
        points = entry["points"]
        points_text = f"{points:,}"
        bbox = draw.textbbox((0, 0), points_text, font=font_points)
        pts_w = bbox[2] - bbox[0]
        pts_x = row_x + row_width - pts_w - 30
        draw.text((pts_x, y + self.row_height // 2 - 12), points_text, 
                 fill=self.accent_gold, font=font_points)
        
        # Points label
        font_label = self._get_font(10)
        label_text = "STELLA"
        bbox = draw.textbbox((0, 0), label_text, font=font_label)
        label_w = bbox[2] - bbox[0]
        draw.text((pts_x + (pts_w - label_w) // 2, y + self.row_height // 2 + 14), 
                 label_text, fill=self.text_dim, font=font_label)
        
        return img, avatar_x, avatar_y

    async def generate(self, entries: list, title: str = "LEADERBOARD") -> io.BytesIO:
        """Generate a premium 3D leaderboard image."""
        # Separate top 3 from rest
        top3 = [e for e in entries if e["rank"] <= 3]
        rest = [e for e in entries if e["rank"] > 3]
        
        # Calculate dimensions
        num_rows = len(rest)
        list_section_height = (self.row_height + self.row_spacing) * num_rows + 30 if num_rows > 0 else 0
        height = self.header_height + self.podium_height + list_section_height + self.padding * 2
        
        # Create background
        bg = self._create_gradient_background(self.width, height)
        fg = Image.new("RGBA", (self.width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(fg)
        
        # Draw header
        font_title = self._get_font(42, black=True)
        bbox = draw.textbbox((0, 0), title, font=font_title)
        title_w = bbox[2] - bbox[0]
        title_x = (self.width - title_w) // 2
        
        # Title with glow effect
        for offset in range(3, 0, -1):
            alpha = 30 - offset * 8
            draw.text((title_x, 35 + offset), title, fill=(255, 120, 170, alpha), font=font_title)
        draw.text((title_x, 35), title, fill=self.accent_pink, font=font_title)
        
        # Subtitle
        font_sub = self._get_font(14)
        subtitle = "Top players ranked by Stella Points, Cards, and Reviews"
        bbox = draw.textbbox((0, 0), subtitle, font=font_sub)
        sub_w = bbox[2] - bbox[0]
        draw.text(((self.width - sub_w) // 2, 90), subtitle, fill=self.text_muted, font=font_sub)
        
        # Decorative line
        line_y = 115
        line_width = 300
        center = self.width // 2
        for i in range(line_width):
            alpha = int(60 * (1 - abs(i - line_width // 2) / (line_width // 2)))
            draw.point((center - line_width // 2 + i, line_y), fill=(*self.accent_pink[:3], alpha))
        
        # Draw 3D podium
        podium_base_y = self.header_height + self.podium_height - 50
        fg = self._draw_3d_podium(fg, self.width, podium_base_y)
        draw = ImageDraw.Draw(fg)
        
        # Draw podium entries
        avatar_positions = []
        if top3:
            # Avatar Y positions (above podiums)
            avatar_y_positions = {
                1: podium_base_y - 140 - 155,  # Above tallest podium
                2: podium_base_y - 100 - 135,  # Above 2nd podium
                3: podium_base_y - 85 - 135,   # Above 3rd podium
            }
            
            # X positions
            x_positions = {
                1: self.width // 2,
                2: int(self.width * 0.25),
                3: int(self.width * 0.75),
            }
            
            for entry in sorted(top3, key=lambda x: x["rank"]):
                rank = entry["rank"]
                cx = x_positions[rank]
                avatar_y = avatar_y_positions[rank]
                avatar_size = self.podium_avatar_sizes[rank]
                
                fg, av_x, av_y, av_sz = self._draw_podium_entry(
                    fg, entry, cx, avatar_y, rank
                )
                avatar_positions.append((entry, av_x, av_y, av_sz))
        
        # Draw list entries for rank 4+
        row_x = self.padding
        row_width = self.width - 2 * self.padding
        y = self.header_height + self.podium_height + 20
        
        row_avatar_positions = []
        for entry in rest:
            fg, av_x, av_y = self._draw_list_entry(fg, entry, y, row_width, row_x)
            row_avatar_positions.append((entry, av_x, av_y))
            y += self.row_height + self.row_spacing
        
        # Fetch and paste avatars
        for entry, av_x, av_y, av_sz in avatar_positions:
            avatar_url = entry.get("avatar_url")
            if avatar_url:
                avatar = await self.fetch_avatar(avatar_url, av_sz)
                fg.paste(avatar, (av_x, av_y), avatar)
        
        for entry, av_x, av_y in row_avatar_positions:
            avatar_url = entry.get("avatar_url")
            if avatar_url:
                avatar = await self.fetch_avatar(avatar_url, self.avatar_size)
                fg.paste(avatar, (av_x, av_y), avatar)
        
        # Composite final image
        final = Image.alpha_composite(bg, fg)
        
        # Save as PNG
        buffer = io.BytesIO()
        final.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer
