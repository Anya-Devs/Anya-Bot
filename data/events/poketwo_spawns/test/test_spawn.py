import os, io, re, json, requests
from pathlib import Path
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageSequence
from pilmoji import Pilmoji


class PokemonImageBuilder:
    def __init__(self):
        self.config_path = "data/events/poketwo_spawns/image/config.json"
        self.type_emojis_file = "data/commands/pokemon/pokemon_emojis/_pokemon_types.json"
        self.emoji_icon_dir = "data/commands/pokemon/pokemon_emojis/icons/types"
        self.pokemon_image_dir = "data/commands/pokemon/pokemon_images"
        self.output_dir = "data/events/poketwo_spawns/test/spawns"
        os.makedirs(self.emoji_icon_dir, exist_ok=True)
        os.makedirs(self.pokemon_image_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        self.config = self.load_json(self.config_path, default=dict())
        self.type_emojis = self.load_json(self.type_emojis_file, default=dict())
        self.font_header = self.safe_font(self.config.get("font_path_header", "arial.ttf"), self.config.get("font_size_header", 24))
        self.font_base = self.safe_font(self.config.get("font_path_base", "arial.ttf"), self.config.get("font_size_base", 16))
        self.default_bg_url = self.config.get("background_url", None)

        shader_opacity = self.config.get("shader_opacity", "80%")
        if isinstance(shader_opacity, str) and shader_opacity.endswith("%"):
            shader_opacity = float(shader_opacity.strip("%"))
        self.shader_opacity = max(0.0, min(1.0, shader_opacity / 100.0))

    def load_json(self, path, default=None):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Can't load {path}: {e}")
            return default if default is not None else {}

    def safe_font(self, path, size):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            print(f"Warning: Could not load font '{path}'. Using default.")
            return ImageFont.load_default()

    def create_shader_layer(self, size):
        w, h = size
        alpha = int(255 * self.shader_opacity)
        return Image.new("RGBA", (w, h), (0, 0, 0, alpha))

    def fetch_pokemon_image(self, pokemon_raw_name):
        path = os.path.join(self.pokemon_image_dir, f"{pokemon_raw_name}.png")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing Pokémon image: {path}")
        img = Image.open(path).convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return img, buf

    @staticmethod
    def country_code_to_flag_emoji(cc):
        return "".join(chr(ord(c) + 127397) for c in cc.upper())

    def get_dominant_color(self, image_bytes_io):
        pil_img = Image.open(image_bytes_io).convert("RGB")
        arr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        pixels = arr.reshape((-1, 3)).astype(np.float32)
        _, labels, centers = cv2.kmeans(
            pixels, 3, None,
            (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0),
            10, cv2.KMEANS_RANDOM_CENTERS)
        counts = np.bincount(labels.flatten())
        dom = centers[np.argmax(counts)]
        return tuple(int(c) for c in dom[::-1])

    def extract_emoji_id(self, emoji_str):
        m = re.search(r"<:.+?:(\d+)>", emoji_str)
        return m.group(1) if m else None

    def get_local_emoji_image(self, emoji_str):
        eid = self.extract_emoji_id(emoji_str)
        if not eid:
            return None
        path = os.path.join(self.emoji_icon_dir, f"{eid}.png")
        if not os.path.exists(path):
            return None
        return Image.open(path).convert("RGBA")

    def draw_type_emojis(self, canvas, types, pos=None):
        if not types: return
        spacing = self.config.get("type_spacing", 40)
        icon_size = self.config.get("type_icon_size", 32)
        if isinstance(icon_size, int):
            w, h = icon_size, icon_size
        else:
            w, h = icon_size
        x = canvas.width - (len(types) * spacing)
        y = canvas.height - h
        for t in types:
            emoji_img = self.get_local_emoji_image(self.type_emojis.get(f"{t.lower()}_type", ""))
            if emoji_img:
                emoji_img = emoji_img.resize((w, h))
                canvas.paste(emoji_img, (x, y), emoji_img)
                x += spacing

    def contain_image(self, img, target_size, bg_color=(0,0,0,0)):
        tw, th = target_size
        iw, ih = img.size
        scale = min(tw / iw, th / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGBA", target_size, bg_color)
        x = (tw - nw) // 2
        y = (th - nh) // 2
        canvas.paste(img, (x, y), img)
        return canvas

    def get_type_colors(self, types):
        def lighten(rgb, f=0.45): return tuple(min(int(c + (255 - c) * f), 255) for c in rgb)
        colors = []
        for t in types:
            emoji_img = self.get_local_emoji_image(self.type_emojis.get(f"{t.lower()}_type", ""))
            if emoji_img:
                with io.BytesIO() as buf:
                    emoji_img.save(buf, format="PNG"); buf.seek(0)
                    colors.append(lighten(self.get_dominant_color(buf)))
        return colors or [(240, 240, 240)]

    def blend_colors(self, colors):
        return tuple(sum(c[i] for c in colors) // len(colors) for i in range(3))

    def prepare_background_frames(self, bg_colors, bg_url=None):
        w, h = self.config.get("canvas_size", (512, 512))
        blur = self.config.get("background_blur", False)
        transparent = self.config.get("transparent_background", False)
        url = bg_url if bg_url else self.default_bg_url
        frames, durations, is_gif = [], [], False
        if transparent:
            return [Image.new("RGBA", (w, h), (0, 0, 0, 0))], [100], False
        if url:
            try:
                if os.path.isfile(url):
                    bg_img = Image.open(url)
                else:
                    headers = {"User-Agent": "Mozilla/5.0"}
                    resp = requests.get(url, headers=headers, timeout=10)
                    resp.raise_for_status()
                    bg_img = Image.open(io.BytesIO(resp.content))
                is_gif = getattr(bg_img, "is_animated", False)
                dom_color = (0, 0, 0, 255)
                if is_gif:
                    bg_img.seek(0)
                    for frame in ImageSequence.Iterator(bg_img):
                        duration = frame.info.get("duration", 40)
                        frame = frame.convert("RGBA")
                        frame = self.contain_image(frame, (w, h), dom_color)
                        if blur:
                            frame = frame.filter(ImageFilter.GaussianBlur(8))
                        shader = self.create_shader_layer(frame.size)
                        frame = Image.alpha_composite(frame, shader)
                        frames.append(frame.convert("RGBA"))
                        durations.append(duration)
                    return frames, durations, True
                else:
                    buf = io.BytesIO()
                    bg_img.save(buf, format="PNG")
                    buf.seek(0)
                    dom_color = self.get_dominant_color(buf) + (255,)
                    frame = bg_img.convert("RGBA")
                    frame = self.contain_image(frame, (w, h), dom_color)
                    if blur:
                        frame = frame.filter(ImageFilter.GaussianBlur(8))
                    shader = self.create_shader_layer(frame.size)
                    frame = Image.alpha_composite(frame, shader)
                    return [frame], [100], False
            except Exception as e:
                print("Background fetch error:", e)
        color = self.blend_colors(bg_colors) if len(bg_colors) > 1 else bg_colors[0]
        canvas = Image.new("RGBA", (w, h), color + (255,))
        shader = self.create_shader_layer(canvas.size)
        canvas = Image.alpha_composite(canvas, shader)
        if blur:
            canvas = canvas.filter(ImageFilter.GaussianBlur(8))
        return [canvas], [100], False

    def replace_flag_emojis_with_displacement(self, text):
        parts, last = [], 0
        for m in re.finditer(r"\{flag_([a-z]{2})\}", text):
            s, e = m.span()
            if s > last:
                parts.append((text[last:s], False))
            parts.append((self.country_code_to_flag_emoji(m.group(1)), True))
            last = e
        if last < len(text):
            parts.append((text[last:], False))
        return parts

    def draw_text_with_flag_offset(self, pilmoji, pos, text, font, fill, stroke_fill=None, stroke_width=0, flag_offset=4):
        x, y = pos
        for part, is_flag in self.replace_flag_emojis_with_displacement(text):
            width, _ = pilmoji.getsize(part, font=font)
            off_y = y + flag_offset if is_flag else y
            pilmoji.text((x, off_y), part, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
            x += width

    def compose_frame(self, bg_frame, poke_img, pokemon_name, best_name, types):
        frame = bg_frame.copy()
        poke_img_size = self.config.get("pokemon_image_size", (128, 128))
        contained_poke = self.contain_image(poke_img, poke_img_size, (0,0,0,0))
        poke_pos = self.config.get("pokemon_image_position", (50, 50))
        frame.paste(contained_poke, poke_pos, contained_poke)
        pilmoji = Pilmoji(frame)

        # Always use fixed font for header
        self.draw_text_with_flag_offset(
            pilmoji, self.config.get("pokemon_name_position", (50, 10)),
            pokemon_name, self.font_header, self.config.get("name_color", (0, 0, 0)),
            stroke_fill=self.config.get("name_outline_color"),
            stroke_width=self.config.get("name_stroke_width", 0))

        self.draw_text_with_flag_offset(
            pilmoji, self.config.get("alt_name_position", (50, 40)),
            best_name, self.font_base, self.config.get("alt_color", (0, 0, 0)),
            stroke_fill=self.config.get("alt_outline_color"),
            stroke_width=self.config.get("alt_stroke_width", 0))

        self.draw_type_emojis(frame, types)
        return frame

    def create_image(self, raw_slug, pokemon_name, best_name, types, bg_url=None, filename=None, format="PNG"):
        try:
            poke_img, _ = self.fetch_pokemon_image(pokemon_name.lower().replace(" ", "-"))
        except FileNotFoundError:
            return None

        base_width=256; increment_per_char=10; max_width=512
        self.config["canvas_size"]=(min(base_width+increment_per_char*len(pokemon_name),max_width) + 20,self.config.get("canvas_size",(512,512))[1])
        type_colors = self.get_type_colors(types)
        bg_frames, durations, is_gif = self.prepare_background_frames(type_colors, bg_url)
        frames = [self.compose_frame(f, poke_img, pokemon_name, best_name, types) for f in bg_frames]

        out_format = "GIF" if is_gif else format.upper()
        path = os.path.join(self.output_dir, f"{raw_slug}.{out_format.lower()}")
        if filename:
            path = os.path.join(self.output_dir, filename)

        if len(frames) == 1:
            frames[0].save(path, format=out_format)
        else:
            frames[0].save(path, format=out_format, save_all=True,
                           append_images=frames[1:], duration=durations, loop=0)
        return path

if __name__ == "__main__":
    builder = PokemonImageBuilder()
    try:
        path = builder.create_image(
            raw_slug="Maushold Family Of Three",
            pokemon_name="Maushold Family Of Three",
            best_name="{flag_fr} Purmel",
            types=["dark","ice"],
            bg_url=None,
            filename="test.png"
        )
        if path:
            print("✅ Image created at:", path)
        else:
            print("❌ Failed to create image. Check for missing images or font files.")
    except Exception as ex:
        print(f"Image creation failed: {ex}")
