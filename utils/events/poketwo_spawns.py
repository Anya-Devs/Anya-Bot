import os, io, re, json, csv, logging, requests, asyncio, uuid
from pathlib import Path
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import aiohttp, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageSequence
from pilmoji import Pilmoji
from fuzzywuzzy import fuzz
from imports.discord_imports import *
from bot.token import use_test_bot as ut
from utils.subcogs.pokemon import PoketwoCommands, MongoHelper



logger = logging.getLogger(__name__)

class PokemonUtils:
    def __init__(self, mongo, type_emojis_file, quest_emojis_file, description_file, id_file, regional_forms, lang_flags, bot=None, pp=None):
        self.mongo = mongo
        self.type_emojis_file = type_emojis_file
        self.quest_emojis_file = quest_emojis_file
        self.pokemon_description_file = description_file
        self.pokemon_id_file = id_file
        self.regional_forms = regional_forms
        self.lang_flags = lang_flags
        self.bot = bot
        self.pp = pp
        self._type_emojis = {}
        self._quest_emojis = {}
        self.load_emojis()
        self.alt_names_map = self.load_alt_names("data/commands/pokemon/alt_names.csv")
        self._image_color_cache = {}
        self._special_names = self._load_special_names_sync()
        self._pokemon_name_map = self._load_pokemon_names("data/commands/pokemon/pokemon_names.csv")
        self.flag_map = self.load_flag_map("data/commands/pokemon/flag_map.json")
        self._pokemon_rows = self._load_pokemon_rows(description_file)
        self._id_map = self._load_pokemon_ids_cached(id_file)
        self._server_config_cache = {}
        self._ping_cache = {}

    @staticmethod
    @lru_cache(maxsize=None)
    def load_alt_names(path):
        if not Path(path).exists():
            return {}
        with open(path, newline="", encoding="utf-8") as f:
            return {
                row["pokemon_species"].strip().lower(): {
                    lang: name.strip() for lang, name in row.items()
                    if lang != "pokemon_species" and name.strip()
                }
                for row in csv.DictReader(f)
            }

    def load_emojis(self):
        for file, attr in [(self.type_emojis_file, "_type_emojis"), (self.quest_emojis_file, "_quest_emojis")]:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    setattr(self, attr, json.load(f))
            except Exception:
                setattr(self, attr, {})

    @staticmethod
    def _load_pokemon_rows(path):
        if not Path(path).exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return {row["slug"].lower(): row for row in csv.DictReader(f)}

    @staticmethod
    def _load_pokemon_ids_cached(path):
        if not Path(path).exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return {row["name"].lower(): row["id"] for row in csv.DictReader(f)}

    @staticmethod
    def _load_pokemon_names(path):
        if not Path(path).exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return {row["name"].replace("-", "_"): row["id"]
                    for row in csv.DictReader(f) if "name" in row and "id" in row}

    def get_base_pokemon_name(self, raw):
        name_map, norm = self._pokemon_name_map, raw.replace("-", "_")
        if norm in name_map:
            return norm.replace("_", "-")
        parts = norm.split("_")
        for i in range(len(parts)):
            if (c := "_".join(parts[i:])) in name_map:
                return c.replace("_", "-")
        for p in reversed(parts):
            if p in name_map:
                return p.replace("_", "-")
        return norm.replace("_", "-")

    @staticmethod
    @lru_cache(maxsize=None)
    def load_flag_map(path):
        return json.load(open(path, encoding="utf-8")) if Path(path).exists() else {}

    def _load_special_names_sync(self):
        rare, regional = [], []
        try:
            with open("data/commands/pokemon/pokemon_special_names.csv", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row[0]:
                        rare.append(row[0].strip().lower())
                    if len(row) > 1 and row[1]:
                        regional.append(row[1].strip().lower())
        except FileNotFoundError:
            pass
        return rare, regional

    def get_best_normal_alt_name(self, slug):
        try:
            p = re.compile(r"[A-Za-z0-9\- ']+")
            s, v = set(), []
            sl = slug.lower()
            for lang, name in self.alt_names_map.get(sl, {}).items():
                n = name.strip()
                if n.lower() != sl and n.lower() not in s and p.fullmatch(n) and len(n) < len(sl):
                    s.add(n.lower())
                    v.append((self.flag_map.get(lang, ""), n))
            if not v:
                return None
            m = min(len(n) for _, n in v)
            f, n = min(((f, n) for f, n in v if len(n) == m), key=lambda x: x[1].lower())
            return f"{f} {n}" if f else n
        except Exception as e:
            logger.error(f"get_best_normal_alt_name('{slug}') failed: {e}")
            return None

    def get_pokemon_row(self, slug):
        return self._pokemon_rows.get(slug.lower())

    def get_description(self, slug):
        row = self.get_pokemon_row(slug)
        if row:
            return row.get("description", ""), row.get("dex_number", "???"), row
        return "", self._id_map.get(slug.lower(), "???"), {}

    def get_pokemon_types(self, slug):
        row = self.get_pokemon_row(slug)
        if not row:
            return []
        return [row.get("type.0", "").strip().lower(), row.get("type.1", "").strip().lower()] if row.get("type.0") else []

    def get_pokemon_region(self, slug):
        row = self.get_pokemon_row(slug)
        return row.get("region", "").capitalize() if row else ""

    async def get_server_config(self, guild_id):
        if guild_id in self._server_config_cache:
            return self._server_config_cache[guild_id]
        cfg = await self.mongo.db["server_config"].find_one({"guild_id": guild_id}) or {}
        self._server_config_cache[guild_id] = cfg
        return cfg

    async def get_type_ping_users(self, guild, pokemon_name):
        try:
            pokemon_types = self.get_pokemon_types(pokemon_name)
            if not pokemon_types:
                return {}
            type_pings = {}
            for ptype in pokemon_types:
                ptype_lower = ptype.lower()
                users = await self.mongo.db["type_ping_types"].find({"type": ptype_lower}).to_list(None)
                mentions = {
                    f"<@{u['user_id']}>" for u in users if u.get("user_id") and guild.get_member(u["user_id"])
                }
                if mentions:
                    label = f"{ptype.capitalize()} Type".strip()
                    type_pings[label] = "".join(sorted(mentions))
            return type_pings
        except Exception as e:
            logger.warning(f"Error in get_type_ping_users: {e}")
            return {}

    async def get_quest_ping_users(self, guild, pokemon_name):
        try:
            row = self.get_pokemon_row(pokemon_name)
            region = row.get("region", "").lower() if row else None
            if not region:
                return []
            users = await self.mongo.db["quest_ping"].find({}).to_list(None)
            return [f"<@{u['user_id']}>" for u in users if guild.get_member(u["user_id"]) and region in [r.lower() for r in u.get("regions", [])]]
        except Exception as e:
            logger.warning(f"Error in get_quest_ping_users: {e}")
            return []

    async def get_ping_users(self, guild, pokemon_name):
        try:
            shiny = await self.mongo.db["shiny_hunt"].find({}).to_list(None)
            collect = await self.mongo.db["collection"].find({}).to_list(None)
            shiny_mentions = [f"<@{u['user_id']}>" for u in shiny if pokemon_name.lower() in [p.lower() for p in u.get("pokemon", [])] and guild.get_member(u["user_id"])]
            collect_mentions = [f"<@{u['user_id']}>" for u in collect if pokemon_name.lower() in [p.lower() for p in u.get("pokemon", [])] and guild.get_member(u["user_id"])]
            return shiny_mentions, collect_mentions
        except Exception as e:
            logger.warning(f"Error in get_ping_users: {e}")
            return [], []

    def find_full_name_for_slug(self, slug_raw):
        slug_lower = slug_raw.lower()
        for name in self._pokemon_name_map.keys():
            if slug_lower in name.lower():
                return name
        return slug_raw

class PokemonImageBuilder:
    def __init__(self):
        self.config_path = "data/events/poketwo_spawns/image/config.json"
        self.type_emojis_file = "data/commands/pokemon/pokemon_emojis/_pokemon_types.json"
        self.emoji_icon_dir = "data/commands/pokemon/pokemon_emojis/icons/types"
        self.pokemon_image_dir = "data/commands/pokemon/pokemon_images"
        self.output_dir = "data/events/poketwo_spawns/image"

        os.makedirs(self.emoji_icon_dir, exist_ok=True)
        os.makedirs(self.pokemon_image_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        with open(self.type_emojis_file, 'r', encoding='utf-8') as f:
            self.type_emojis = json.load(f)

        self.font_header = ImageFont.truetype(self.config["font_path_header"], self.config["font_size_header"])
        self.font_base = ImageFont.truetype(self.config["font_path_base"], self.config["font_size_base"])

    def fetch_pokemon_image(self, pokemon_raw_name):
        local_path = os.path.join(self.pokemon_image_dir, f"{pokemon_raw_name}.png")
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Missing Pokémon image: {local_path}")
        img = Image.open(local_path).convert("RGBA")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return img, img_bytes

    @staticmethod
    def country_code_to_flag_emoji(cc):
        OFFSET = 127397
        return "".join(chr(ord(c) + OFFSET) for c in cc.upper())

    def get_dominant_color(self, image_bytes_io):
        pil_image = Image.open(image_bytes_io).convert('RGB')
        img = np.array(pil_image)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        pixels = img.reshape((-1, 3)).astype(np.float32)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        counts = np.bincount(labels.flatten())
        dominant = centers[np.argmax(counts)]
        return tuple(int(c) for c in dominant[::-1])

    def extract_emoji_id(self, emoji_str):
        match = re.search(r"<:.+?:(\d+)>", emoji_str)
        return match.group(1) if match else None

    def get_local_emoji_image(self, emoji_str):
        emoji_id = self.extract_emoji_id(emoji_str)
        if not emoji_id:
            return None
        local_path = os.path.join(self.emoji_icon_dir, f"{emoji_id}.png")
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Missing emoji icon: {local_path}")
        return Image.open(local_path).convert("RGBA")

    def draw_type_emojis(self, canvas, types, position):
        x, y = position
        spacing = self.config["type_spacing"]
        icon_size = self.config["type_icon_size"]
        if len(types) == 1:
            x += spacing
        for t in types:
            emoji_str = self.type_emojis.get(f"{t.lower()}_type", "")
            emoji_img = self.get_local_emoji_image(emoji_str)
            if emoji_img:
                emoji_img = emoji_img.resize(icon_size)
                canvas.paste(emoji_img, (x, y), emoji_img)
                x += spacing

    def resize_and_crop(self, img, target_size):
        width, height = target_size
        img_ratio = img.width / img.height
        target_ratio = width / height
        scale_factor = height / img.height if img_ratio > target_ratio else width / img.width
        new_size = (int(img.width * scale_factor), int(img.height * scale_factor))
        img = img.resize(new_size, Image.LANCZOS)
        left = (img.width - width) // 2
        top = (img.height - height) // 2
        return img.crop((left, top, left + width, top + height))

    def get_type_colors(self, types):
        def lighten_color(rgb, factor=0.45):
            return tuple(min(int(c + (255 - c) * factor), 255) for c in rgb)
        colors = []
        for t in types:
            emoji_str = self.type_emojis.get(f"{t.lower()}_type", "")
            emoji_img = self.get_local_emoji_image(emoji_str)
            if emoji_img:
                with io.BytesIO() as buf:
                    emoji_img.save(buf, format="PNG")
                    buf.seek(0)
                    dom_color = self.get_dominant_color(buf)
                    colors.append(lighten_color(dom_color))
        return colors or [(240, 240, 240)]

    def blend_colors(self, colors):
        r = sum(c[0] for c in colors) // len(colors)
        g = sum(c[1] for c in colors) // len(colors)
        b = sum(c[2] for c in colors) // len(colors)
        return (r, g, b)

    def prepare_background_frames(self, bg_colors, bg_url=None):
        width, height = self.config["canvas_size"]
        blur_enabled = self.config.get("background_blur", False)
        transparent = self.config.get("transparent_background", False)
        if transparent:
            canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            return [canvas], [100]
        if bg_url:
            try:
                response = requests.get(bg_url, timeout=5)
                response.raise_for_status()
                img_bytes = io.BytesIO(response.content)
                bg_image = Image.open(img_bytes)
                frames, durations = [], []
                for frame in ImageSequence.Iterator(bg_image):
                    frame = frame.convert("RGBA")
                    frame = self.resize_and_crop(frame, (width, height))
                    if blur_enabled:
                        frame = frame.filter(ImageFilter.GaussianBlur(radius=8))
                    frames.append(frame)
                    durations.append(frame.info.get('duration', 40))
                if frames:
                    return frames, durations
            except (requests.RequestException, OSError):
                pass
        solid_color = self.blend_colors(bg_colors) if len(bg_colors) > 1 else bg_colors[0]
        canvas = Image.new("RGBA", (width, height), solid_color + (255,))
        if blur_enabled:
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=8))
        return [canvas], [100]

    def replace_flag_emojis_with_displacement(self, text):
        parts, last_index = [], 0
        for match in re.finditer(r"\{flag_([a-z]{2})\}", text):
            start, end = match.span()
            if start > last_index:
                parts.append((text[last_index:start], False))
            parts.append((self.country_code_to_flag_emoji(match.group(1)), True))
            last_index = end
        if last_index < len(text):
            parts.append((text[last_index:], False))
        return parts

    def draw_text_with_flag_offset(self, pilmoji, position, text, font, fill, stroke_fill=None, stroke_width=0, flag_offset=4):
        x, y = position
        parts = self.replace_flag_emojis_with_displacement(text)
        for part, is_flag in parts:
            width, _ = pilmoji.getsize(part, font=font)
            offset_y = y + flag_offset if is_flag else y
            pilmoji.text((x, offset_y), part, font=font, fill=fill, stroke_fill=stroke_fill, stroke_width=stroke_width)
            x += width

    def get_scaled_font(self, base_font, text, step=12, shrink=8):
        base_size = base_font.size
        shrink_steps = len(text) // step
        new_size = max(10, base_size - shrink_steps * shrink)
        return ImageFont.truetype(base_font.path, new_size)

    def compose_frame(self, bg_frame, poke_img, pokemon_name, best_name, types):
        frame = bg_frame.copy()
        poke_img_resized = poke_img.resize(self.config["pokemon_image_size"])
        frame.paste(poke_img_resized, self.config["pokemon_image_position"], poke_img_resized)
        pilmoji = Pilmoji(frame)
        scaled_font = self.get_scaled_font(self.font_header, pokemon_name)
        self.draw_text_with_flag_offset(
            pilmoji, self.config["pokemon_name_position"], pokemon_name,
            scaled_font, self.config["name_color"],
            stroke_fill=self.config.get("name_outline_color"),
            stroke_width=self.config.get("name_stroke_width", 0)
        )
        self.draw_text_with_flag_offset(
            pilmoji, self.config["alt_name_position"], best_name,
            self.font_base, self.config["alt_color"],
            stroke_fill=self.config.get("alt_outline_color"),
            stroke_width=self.config.get("alt_stroke_width", 0)
        )
        self.draw_type_emojis(frame, types, self.config["type_position"])
        return frame

    def create_image(self, raw_slug, pokemon_name, best_name, types, bg_url=None, output_path=None, format="PNG"):
        """Create Pokémon image; output_path can be None to return BytesIO."""
        poke_img, img_bytes = self.fetch_pokemon_image(pokemon_name.lower().replace(" ", "-"))
        type_colors = self.get_type_colors(types)
        bg_frames, durations = self.prepare_background_frames(type_colors, bg_url)
        frames = [self.compose_frame(bg_frame, poke_img, pokemon_name, best_name, types) for bg_frame in bg_frames]

        if output_path is None:
            output_bytes = io.BytesIO()
            if len(frames) == 1:
                frames[0].save(output_bytes, format=format)
            else:
                frames[0].save(output_bytes, format=format, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2, transparency=0)
            output_bytes.seek(0)
            return output_bytes
        else:
            if len(frames) == 1:
                frames[0].save(output_path, format=format)
            else:
                frames[0].save(output_path, format=format, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2, transparency=0)
            return output_path
        
        
        
if __name__ == "__main__":
    builder = PokemonImageBuilder()
    builder.create_image(
        pokemon_id=943,
        pokemon_name="Mabosstiff",
        best_name="{flag_fr} Dogrino",
        types=["dark"],
        bg_url=None,
        filename="test.png"
    )
    print("✅ Image created at:", os.path.join(builder.output_dir, "test.png"))






