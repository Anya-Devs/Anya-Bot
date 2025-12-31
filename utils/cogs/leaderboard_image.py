import io
import os
import math
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class LeaderboardImageGenerator:
    """Generate modern leaderboard images with Spy x Family inspired theme."""

    def __init__(self):
        self.width = 700  # Wider for better podium spacing
        self.header_height = 60
        self.row_height = 65
        self.row_spacing = 8
        self.avatar_size = 44
        self.padding = 25
        
        # Spy x Family inspired color scheme
        # Dark teal/green spy theme with Anya's pink accents
        self.bg_gradient_top = (15, 22, 28)       # Dark teal-black top
        self.bg_gradient_mid = (20, 32, 38)       # Dark teal middle
        self.bg_gradient_bottom = (12, 18, 22)   # Dark bottom
        self.row_bg = (25, 40, 48, 200)           # Teal-tinted row
        self.accent_pink = (255, 145, 175)        # Anya's soft pink
        self.accent_gold = (255, 210, 100)        # Stella star gold
        self.text_color = (255, 255, 255)
        self.text_muted = (150, 170, 180)
        self.stella_color = (255, 220, 120)       # Stella points color
        
        # Medal colors (main, glow) - gold, silver, bronze
        self.medal_colors = {
            1: ((255, 215, 0), (255, 200, 80)),    # Gold
            2: ((210, 215, 225), (190, 195, 210)), # Silver
            3: ((210, 140, 70), (190, 120, 60)),   # Bronze
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

    def _create_static_background(self, width: int, height: int) -> Image.Image:
        """Create Spy x Family inspired dark teal gradient with pink accent glow."""
        bg = Image.new("RGBA", (width, height))
        
        # Three-point gradient: top -> mid -> bottom (spy aesthetic)
        mid_point = height // 3
        for y in range(height):
            if y < mid_point:
                # Top to mid gradient
                ratio = y / max(1, mid_point)
                r = int(self.bg_gradient_top[0] * (1 - ratio) + self.bg_gradient_mid[0] * ratio)
                g = int(self.bg_gradient_top[1] * (1 - ratio) + self.bg_gradient_mid[1] * ratio)
                b = int(self.bg_gradient_top[2] * (1 - ratio) + self.bg_gradient_mid[2] * ratio)
            else:
                # Mid to bottom gradient
                ratio = (y - mid_point) / max(1, height - mid_point - 1)
                r = int(self.bg_gradient_mid[0] * (1 - ratio) + self.bg_gradient_bottom[0] * ratio)
                g = int(self.bg_gradient_mid[1] * (1 - ratio) + self.bg_gradient_bottom[1] * ratio)
                b = int(self.bg_gradient_mid[2] * (1 - ratio) + self.bg_gradient_bottom[2] * ratio)
            for x in range(width):
                bg.putpixel((x, y), (r, g, b, 255))
        
        # Add subtle pink glow at top (Anya's presence)
        glow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        
        center_x = width // 2
        center_y = 30
        for i in range(5):
            glow_size = 100 + i * 60
            alpha = max(0, 25 - i * 5)
            gd.ellipse(
                [center_x - glow_size, center_y - glow_size // 3,
                 center_x + glow_size, center_y + glow_size // 2],
                fill=(self.accent_pink[0], self.accent_pink[1], self.accent_pink[2], alpha)
            )
        
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=50))
        bg = Image.alpha_composite(bg, glow_layer)
        
        # Add subtle teal accent at bottom corners
        corner_glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        cgd = ImageDraw.Draw(corner_glow)
        for i in range(3):
            size = 80 + i * 40
            alpha = max(0, 15 - i * 5)
            # Bottom left
            cgd.ellipse([-size//2, height - size//2, size, height + size//2], 
                       fill=(40, 80, 90, alpha))
            # Bottom right
            cgd.ellipse([width - size, height - size//2, width + size//2, height + size//2], 
                       fill=(40, 80, 90, alpha))
        corner_glow = corner_glow.filter(ImageFilter.GaussianBlur(radius=30))
        bg = Image.alpha_composite(bg, corner_glow)
        
        return bg

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

    def _draw_podium_member(self, img: Image.Image, entry: dict, center_x: int, base_y: int, 
                             pedestal_height: int, avatar_size: int, rank: int) -> tuple:
        """Draw a podium member with avatar, name, stella points, and pedestal."""
        draw = ImageDraw.Draw(img)
        username = entry["username"]
        points = entry["points"]
        is_first = rank == 1
        
        # Pedestal styling
        pedestal_width = 160 if is_first else 140
        pedestal_x = center_x - pedestal_width // 2
        pedestal_top = base_y - pedestal_height
        
        # Draw pedestal background with gradient effect
        pedestal_bg = (30, 45, 55, 220) if is_first else (25, 38, 48, 200)
        self._draw_rounded_rect(draw, 
            (pedestal_x, pedestal_top, pedestal_x + pedestal_width, base_y),
            10, pedestal_bg)
        
        # Pedestal top accent line (rank color)
        accent_color = self.medal_colors[rank][0]
        draw.line([(pedestal_x + 10, pedestal_top + 2), (pedestal_x + pedestal_width - 10, pedestal_top + 2)],
                  fill=(*accent_color, 180), width=3)
        
        # Avatar position (centered above pedestal)
        avatar_y = pedestal_top - avatar_size - 15
        avatar_x = center_x - avatar_size // 2
        
        # Add glow behind avatar for 1st place
        if is_first:
            img = self._add_glow(img, center_x, avatar_y + avatar_size // 2, 
                                avatar_size // 2 + 8, self.accent_gold, intensity=14)
            draw = ImageDraw.Draw(img)
        
        # Avatar border ring
        ring_width = 4 if is_first else 3
        ring_color = self.medal_colors[rank][0]
        draw.ellipse(
            [avatar_x - ring_width, avatar_y - ring_width,
             avatar_x + avatar_size + ring_width, avatar_y + avatar_size + ring_width],
            outline=ring_color, width=ring_width
        )
        
        # Rank badge (bottom-right of avatar)
        badge_size = 24 if is_first else 20
        badge_x = avatar_x + avatar_size - badge_size // 2 - 2
        badge_y = avatar_y + avatar_size - badge_size // 2 - 2
        badge_color = self.medal_colors[rank][0]
        
        # Badge background
        draw.ellipse([badge_x, badge_y, badge_x + badge_size, badge_y + badge_size],
                     fill=badge_color, outline=(255, 255, 255), width=2)
        
        # Rank number in badge
        font_badge = self._get_font(12 if is_first else 10, bold=True)
        rank_str = str(rank)
        bbox = draw.textbbox((0, 0), rank_str, font=font_badge)
        rank_w = bbox[2] - bbox[0]
        rank_h = bbox[3] - bbox[1]
        draw.text((badge_x + badge_size // 2 - rank_w // 2, 
                   badge_y + badge_size // 2 - rank_h // 2 - 1),
                  rank_str, fill=(30, 20, 10), font=font_badge)
        
        # Username (centered on pedestal)
        font_name = self._get_font(16 if is_first else 14, bold=True)
        display_name = username[:11] + "…" if len(username) > 11 else username
        bbox = draw.textbbox((0, 0), display_name, font=font_name)
        name_w = bbox[2] - bbox[0]
        name_x = center_x - name_w // 2
        name_y = pedestal_top + 15
        draw.text((name_x, name_y), display_name, fill=self.text_color, font=font_name)
        
        # Stella points below username
        font_pts = self._get_font(18 if is_first else 15, bold=True)
        pts_text = f"{points:,}"
        bbox = draw.textbbox((0, 0), pts_text, font=font_pts)
        pts_w = bbox[2] - bbox[0]
        pts_x = center_x - pts_w // 2
        pts_y = name_y + 20 if is_first else name_y + 18
        pts_color = self.stella_color if is_first else self.medal_colors[rank][0]
        draw.text((pts_x, pts_y), pts_text, fill=pts_color, font=font_pts)
        
        # Quest count below points (in a small box)
        quests_done = entry.get("quests_done", 0)
        font_quests = self._get_font(12)
        quests_text = f"{quests_done} quests"
        bbox = draw.textbbox((0, 0), quests_text, font=font_quests)
        quests_w = bbox[2] - bbox[0]
        quests_h = bbox[3] - bbox[1]
        
        # Quest box dimensions
        box_padding = 6
        box_w = quests_w + (box_padding * 2)
        box_h = quests_h + (box_padding * 2)
        box_x = center_x - box_w // 2
        box_y = pts_y + 26 if is_first else pts_y + 24  # More spacing from points
        
        # Draw quest count box
        self._draw_rounded_rect(draw, 
            (box_x, box_y, box_x + box_w, box_y + box_h),
            4, (20, 30, 35, 180))
        
        # Quest count text centered in box
        quests_x = center_x - quests_w // 2
        quests_y = box_y + box_padding
        draw.text((quests_x, quests_y), quests_text, fill=self.text_muted, font=font_quests)
        
        return img, avatar_x, avatar_y, avatar_size

    async def generate(self, entries: list, title: str = "STELLA LEADERBOARD") -> io.BytesIO:
        """Generate a static leaderboard with podium display for top 3."""
        # Separate top 3 from rest
        top3 = [e for e in entries if e["rank"] <= 3]
        rest = [e for e in entries if e["rank"] > 3]
        
        # Calculate dimensions
        podium_section_height = 240 if top3 else 0
        num_rows = len(rest)
        height = self.header_height + podium_section_height + (self.row_height + self.row_spacing) * num_rows + self.padding + 30

        # Create foreground layer
        fg = Image.new("RGBA", (self.width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(fg)

        # Title with decorative elements
        font_title = self._get_font(22, bold=True)
        bbox = draw.textbbox((0, 0), title, font=font_title)
        title_w = bbox[2] - bbox[0]
        title_x = (self.width - title_w) // 2
        draw.text((title_x, 18), title, fill=self.accent_pink, font=font_title)

        # Decorative lines under title
        line_y = self.header_height - 8
        line_width = 120
        center = self.width // 2
        # Left line with fade
        for i in range(line_width):
            alpha = int(80 * (i / line_width))
            draw.point((center - line_width + i - 20, line_y), fill=(*self.accent_pink[:3], alpha))
        # Right line with fade
        for i in range(line_width):
            alpha = int(80 * (1 - i / line_width))
            draw.point((center + 20 + i, line_y), fill=(*self.accent_pink[:3], alpha))

        # Draw podium for top 3
        avatar_positions = []
        if top3:
            podium_base_y = self.header_height + 195  # Bottom line for pedestals
            
            # Pedestal heights and avatar sizes (taller to fit text properly)
            heights = {1: 105, 2: 85, 3: 80}
            avatar_sizes = {1: 72, 2: 58, 3: 58}
            
            # Positions: 2nd on left, 1st in center, 3rd on right (wider spacing)
            positions = {
                2: int(self.width * 0.22),
                1: self.width // 2,
                3: int(self.width * 0.78),
            }
            
            for entry in sorted(top3, key=lambda x: x["rank"]):
                rank = entry["rank"]
                if rank in positions:
                    center_x = positions[rank]
                    ped_height = heights[rank]
                    av_size = avatar_sizes[rank]
                    
                    fg, av_x, av_y, av_sz = self._draw_podium_member(
                        fg, entry, center_x, podium_base_y, ped_height, av_size, rank
                    )
                    avatar_positions.append((entry, av_x, av_y, av_sz))
            
            # Draw connecting base line between pedestals
            draw = ImageDraw.Draw(fg)
            draw.line([(positions[2] - 70, podium_base_y), (positions[3] + 70, podium_base_y)],
                     fill=(40, 55, 65, 150), width=2)

        # Draw regular rows for rank 4+
        font_name = self._get_font(13, bold=True)
        font_stats = self._get_font(10)
        font_points = self._get_font(14, bold=True)
        font_rank = self._get_font(15, bold=True)

        y = self.header_height + podium_section_height + 20
        row_x = self.padding
        row_width = self.width - 2 * self.padding

        row_avatar_positions = []
        for entry in rest:
            rank = entry["rank"]
            username = entry["username"]
            points = entry["points"]
            quests_done = entry.get("quests_done", 0)

            # Row background
            row_layer = Image.new("RGBA", fg.size, (0, 0, 0, 0))
            row_draw = ImageDraw.Draw(row_layer)
            self._draw_rounded_rect(row_draw, (row_x, y, row_x + row_width, y + self.row_height), 12, self.row_bg)
            fg = Image.alpha_composite(fg, row_layer)
            draw = ImageDraw.Draw(fg)

            # Rank number with circle background
            rank_text = str(rank)
            bbox = draw.textbbox((0, 0), rank_text, font=font_rank)
            rank_w = bbox[2] - bbox[0]
            rank_center_x = row_x + 30
            rank_center_y = y + self.row_height // 2
            draw.ellipse([rank_center_x - 14, rank_center_y - 14, rank_center_x + 14, rank_center_y + 14],
                        fill=(35, 50, 60, 200))
            draw.text((rank_center_x - rank_w // 2, rank_center_y - 9), 
                      rank_text, fill=self.text_muted, font=font_rank)

            # Avatar position
            avatar_x = row_x + 60
            avatar_y = y + (self.row_height - self.avatar_size) // 2
            draw.ellipse(
                [avatar_x - 2, avatar_y - 2, avatar_x + self.avatar_size + 2, avatar_y + self.avatar_size + 2],
                outline=(60, 80, 95), width=2
            )
            row_avatar_positions.append((entry, avatar_x, avatar_y, self.avatar_size))

            # Username and quests
            name_x = avatar_x + self.avatar_size + 14
            display_name = username[:18] + "…" if len(username) > 18 else username
            draw.text((name_x, y + 15), display_name, fill=self.text_color, font=font_name)
            draw.text((name_x, y + 36), f"{quests_done} quests", fill=self.text_muted, font=font_stats)

            # Stella points
            pts_text = f"{points:,}"
            pts_bbox = draw.textbbox((0, 0), pts_text, font=font_points)
            pts_w = pts_bbox[2] - pts_bbox[0]
            pts_x = row_x + row_width - pts_w - 20
            draw.text((pts_x, y + self.row_height // 2 - 8), pts_text, fill=self.stella_color, font=font_points)

            y += self.row_height + self.row_spacing

        # Fetch and paste avatars
        for entry, av_x, av_y, av_sz in avatar_positions + row_avatar_positions:
            avatar_url = entry.get("avatar_url")
            if avatar_url:
                avatar = await self.fetch_avatar(avatar_url, av_sz)
                fg.paste(avatar, (av_x, av_y), avatar)

        # Create background and composite
        bg = self._create_static_background(self.width, height)
        
        final = Image.alpha_composite(bg, fg)
        
        # Save as PNG
        buffer = io.BytesIO()
        final.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer
