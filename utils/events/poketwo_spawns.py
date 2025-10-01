import os, io, re, json, csv, logging, requests, asyncio, uuid
from pathlib import Path
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import aiohttp, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageSequence
from pilmoji import Pilmoji
from bot.cogs.pokemon import PoketwoCommands
from fuzzywuzzy import fuzz
from imports.discord_imports import *
from bot.token import use_test_bot as ut, prefix
from utils.subcogs.pokemon import *

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
        self._full_pokemon_data = {}  

        self.load_emojis()
        self.alt_names_map = self.load_alt_names("data/commands/pokemon/alt_names.csv")
        self._image_color_cache = {}
        self._special_names = self._load_special_names_sync()
        self._pokemon_name_map = self._load_pokemon_names("data/commands/pokemon/pokemon_names.csv")
        self.flag_map = self.load_flag_map("data/commands/pokemon/flag_map.json")

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

    def load_quest_regions(self):
        regions = set()
        try:
            with open(self.pokemon_description_file, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    if region := row.get('region', '').strip().lower():
                        regions.add(region)
        except FileNotFoundError:
            pass
        return regions

    def load_pokemon_ids(self):
        id_map = {}
        try:
            with open(self.pokemon_id_file, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    id_map[row['name'].lower()] = row['id']
        except Exception as e:
            logger.warning(f"Failed to load Pokémon IDs: {e}")
        return id_map

    @staticmethod
    def _load_pokemon_names(path) -> dict:
        if not Path(path).exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return {row['name'].replace('-', '_'): row['id']
                    for row in csv.DictReader(f) if 'name' in row and 'id' in row}

    def get_base_pokemon_name(self, raw) -> str:
        name_map, norm = self._pokemon_name_map, raw.replace('-', '_')
        if norm in name_map:
            return norm.replace('_', '-')
        parts = norm.split('_')
        for i in range(len(parts)):
            if (c := '_'.join(parts[i:])) in name_map:
                return c.replace('_', '-')
        for p in reversed(parts):
            if p in name_map:
                return p.replace('_', '-')
        return norm.replace('_', '-')

    @staticmethod
    @lru_cache(maxsize=None)
    def load_flag_map(path):
        return json.load(open(path, encoding="utf-8")) if Path(path).exists() else {}

    def _load_special_names_sync(self):
        rare, regional = [], []
        try:
            with open('data/commands/pokemon/pokemon_special_names.csv', encoding='utf-8') as f:
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
            if (
                n.lower() != sl
                and n.lower() not in s
                and p.fullmatch(n)
                and len(n) < len(sl)
            ):
                s.add(n.lower())
                v.append((self.flag_map.get(lang, ''), n))
        if not v:
            return None
        m = min(len(n) for _, n in v)
        f, n = min(
            ((f, n) for f, n in v if len(n) == m),
            key=lambda x: x[1].lower()
        )
        return f"{f} {n}" if f else n
     except Exception as e:
        logger.error(f"get_best_normal_alt_name('{slug}') failed: {e}")
        return None

    async def _get_image_color_cached(self, url):
        if url in self._image_color_cache:
            return self._image_color_cache[url]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return 0xFFFFFF
                    data = await response.read()
            img_array = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img is None:
                return 0xFFFFFF
            small_img = cv2.resize(img, (50, 50), interpolation=cv2.INTER_AREA)
            small_img = cv2.cvtColor(small_img, cv2.COLOR_BGR2RGB)
            pixels = small_img.reshape((-1, 3)).astype(np.float32)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
            _, labels, centers = cv2.kmeans(pixels, 1, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            dominant_color = centers[0].astype(int)
            rgb = (dominant_color[0] << 16) + (dominant_color[1] << 8) + dominant_color[2]
            self._image_color_cache[url] = rgb
            return rgb
        except Exception:
            return 0xFFFFFF
        
    def load_full_pokemon_data(self):
     """Load and cache all Pokémon data from the description CSV, unpacking every column."""
     if self._full_pokemon_data:
        return self._full_pokemon_data

     data = {}
     try:
        with open(self.pokemon_description_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                slug = row.get("slug", "").lower()
                if not slug:
                    continue
                # Keep all CSV values as-is
                data[slug] = {key: value.strip() if isinstance(value, str) else value
                              for key, value in row.items()}
        self._full_pokemon_data = data
     except FileNotFoundError:
        logger.warning(f"Pokemon description file not found: {self.pokemon_description_file}")
        self._full_pokemon_data = {}
     return self._full_pokemon_data

    
    async def format_messages(self, slug, type_pings, quest_pings, shiny_pings, collection_pings,
                              special_roles, pred_text, dex_number, description, image_url,
                              low_confidence=True):
        try:
            formatted_name = self.format_name(slug.replace('_', ' ')).title()
            if low_confidence:
                unsure_msg = "Anya is unsure about this guess, but here is her best effort."
                return f"{unsure_msg}\n**{formatted_name}**: {pred_text}", None
            has_pings = any([type_pings, quest_pings, shiny_pings, collection_pings])
            header_line = f"{'' if has_pings else ''}**{formatted_name}**: {pred_text}"
            quote_lines = []
            if special_roles:
                quote_lines.append(special_roles)
            if shiny_pings:
                quote_lines.append(f"**Shinyhunt:**")
                quote_lines.append(" ".join(shiny_pings))
            if collection_pings:
                quote_lines.append(f"**Collectors:**")
                quote_lines.append("".join(collection_pings))
            if quest_pings:
                region_name = self.get_pokemon_region(slug) or "Region"
                region_emoji = self._quest_emojis.get(region_name.lower(), "")
                quote_lines.append(f"**{region_name} Ping:**")
                quote_lines.append("".join(quest_pings))
            if type_pings:
                type_parts = [
                    f"**{label}:**\n{''.join(users)}"
                    for label, users in type_pings.items() if users
                ]
                if type_parts:
                    quote_lines.append("\n".join(type_parts))
            quoted_content = "\n".join(quote_lines)
            blockquote = "\n".join("> " + line for line in quoted_content.splitlines())
            message = f"{header_line}\n{blockquote}"
            actual_types = self.get_pokemon_types(slug)
            actual_region = self.get_pokemon_region(slug)
            region_emoji = self._quest_emojis.get(actual_region.lower(), "") if actual_region else ""
            emoji_types = [
                f"{self._type_emojis.get(f'{t.lower()}_type','')} {t.title()}"
                for t in actual_types if t
            ]
            alt_names_field = []
            alt_names_list = self.alt_names_map.get(slug.lower(), {})
            if isinstance(alt_names_list, dict):
                alt_names_field.extend(name for name in alt_names_list.values())
            thumb_url = (
                f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{dex_number}.png"
                if slug and slug.lower() not in ("", "???") else image_url
            )
            embed = None
            return message, embed
        except Exception as e:
            logger.error(f"Error in format_messages: {type(e).__name__}: {e}")
            fallback = f"**{slug}**\nFailed to format spawn info."
            embed = discord.Embed(color=0xFF0000, description="An error occurred generating this embed.")
            return fallback, embed

    def format_name(self, name):
        return name.replace('-',' ').title()

    def get_pokemon_row(self, slug):
        try:
            with open(self.pokemon_description_file, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    if row.get("slug", "").lower() == slug.lower():
                        return row
        except FileNotFoundError:
            pass
        return None

    def get_description(self, slug):
        row = self.get_pokemon_row(slug)
        if row:
            return row.get("description", ""), row.get("dex_number", "???"), row
        fallback_id = self.load_pokemon_ids().get(slug.lower(), "???")
        return "", fallback_id, {}

    def get_pokemon_types(self, slug):
        row = self.get_pokemon_row(slug)
        if not row:
            return []
        types = []
        if row.get("type.0"):
            types.append(row["type.0"].strip().lower())
        if row.get("type.1") and row["type.1"].strip():
            types.append(row["type.1"].strip().lower())
        return types

    def get_pokemon_region(self, slug):
        row = self.get_pokemon_row(slug)
        if not row:
            return ""
        return row.get("region", "").capitalize()

    async def get_server_config(self, guild_id):
        return await self.mongo.db["server_config"].find_one({"guild_id": guild_id}) or {}

    async def get_type_ping_users(self, guild, pokemon_name):
        try:
            if not self._type_emojis:
                self.load_emojis()
            if not self.bot:
                logger.warning("Bot instance not set in PokemonUtils; cannot fetch pokemon_types")
                return {}
            pokemon_types_data = await self.pp.data_manager.pokemon_types
            pokemon_types = pokemon_types_data.get(pokemon_name.lower(), [])
            if not pokemon_types:
                pokemon_types = self.get_pokemon_types(pokemon_name)
            if not pokemon_types:
                return {}
            type_pings = {}
            for ptype in pokemon_types:
                ptype_lower = ptype.lower()
                emoji = self._type_emojis.get(f"{ptype_lower}_type", "")
                users = await self.mongo.db["type_ping_types"].find({"type": ptype_lower}).to_list(None)
                mentions = {
                    f"<@{user['user_id']}>"
                    for user in users
                    if user.get("user_id") and guild.get_member(user["user_id"])
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
            with open(self.pokemon_description_file, 'r', encoding='utf-8') as f:
                region = next((row['region'].lower() for row in csv.DictReader(f) if row.get("slug", "").lower() == pokemon_name.lower()), None)
            if not region:
                return []
            users = await self.mongo.db["quest_ping"].find({}).to_list(None)
            return [f"<@{u['user_id']}>" for u in users if guild.get_member(u["user_id"]) and region in [r.lower() for r in u.get("regions", [])]]
        except Exception as e:
            logger.warning(f"Error in get_quest_ping_users: {e}")
            return []

    async def get_ping_users(self, guild, pokemon_name):
        def fuzzy(t, n): return t == n or fuzz.ratio(t, n) > 85
        try:
            shiny = await self.mongo.db["shiny_hunt"].find({}).to_list(None)
            collect = await self.mongo.db["collection"].find({}).to_list(None)
            shiny_mentions = [f"<@{u['user_id']}>" for u in shiny if any(fuzzy(pokemon_name.lower(), p.lower()) for p in u.get("pokemon", [])) and guild.get_member(u["user_id"])]
            collect_mentions = [f"<@{u['user_id']}>" for u in collect if any(fuzzy(pokemon_name.lower(), p.lower()) for p in u.get("pokemon", [])) and guild.get_member(u["user_id"])]
            return shiny_mentions, collect_mentions
        except Exception as e:
            logger.warning(f"Error in get_ping_users: {e}")
            return [], []

    async def get_image_color(self, url):
        fallback = 0x3498db
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return fallback
                    data = await resp.read()
            with io.BytesIO(data) as img_bytes:
                img_bytes.seek(0)
                arr = np.frombuffer(img_bytes.read(), np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    return fallback
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                pixels = img.reshape((-1, 3))
                pixels = np.float32(pixels)
                criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
                K = 3
                _, labels, centers = cv2.kmeans(pixels, K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
                counts = np.bincount(labels.flatten())
                dominant = centers[np.argmax(counts)]
                r, g, b = map(int, dominant)
                return (r << 16) + (g << 8) + b
        except Exception as e:
            logger.warning(f"Failed to get image color: {e}")
            return fallback

    def find_full_name_for_slug(self, slug_raw: str) -> str:
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



class PokemonSpawnView(View):
    DEFAULT_LANG_FLAGS = {
        "de":"🇩🇪","en":"🇬🇧","es":"🇪🇸","fr":"🇫🇷","it":"🇮🇹",
        "ja":"🇯🇵","ja-Hrkt":"🇯🇵","ko":"🇰🇷","roomaji":"🇯🇵",
        "zh-Hans":"🇨🇳","zh-Hant":"🇹🇼"
    }

    CSV_PATH = "data/commands/pokemon/pokemon_full_data.csv"

    def __init__(self, slug, pokemon_utils, pokemon_data=None):
        super().__init__(timeout=None)
        self.slug = slug
        self.prefix = prefix
        self.pokemon_utils = pokemon_utils

        with open("data/commands/pokemon/pokemon_emojis/_pokemon_types.json", "r", encoding="utf-8") as f:
            self.type_emojis = json.load(f)

        # Only add the Pokédex button if Pokémon data exists
        if self.get_pokemon_info():
            self.add_item(discord.ui.Button(
                label="Pokédex",
                style=discord.ButtonStyle.secondary,
                emoji="<:pokedex:1411058742241529877>",
                custom_id="dex_button"
            ))

    # ===== Helpers =====
    def get_pokemon_info(self):
        try:
            with open(self.CSV_PATH, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if row.get("slug") == self.slug:
                        for stat in ["base.hp","base.atk","base.def","base.satk","base.sdef","base.spd",
                                     "height","weight","gender_rate"]:
                            if stat in row and row[stat]:
                                try: row[stat] = float(row[stat]) if "." in row[stat] else int(row[stat])
                                except: pass
                        return row
        except Exception as e:
            print(f"[get_pokemon_info] CSV read error: {e}")
        return None

    def format_type_field(self, data):
        types = []
        for i in (0, 1):
            t = data.get(f"type.{i}")
            if not t: continue
            emoji = self.type_emojis.get(f"{t.lower()}_type", "")
            types.append(f"{emoji} {t.capitalize()}")
        return "\n".join(types) if types else "N/A"

    def make_bar(self, value, length=10):
        filled = int((value / 255) * length)
        return "▰" * filled + "▱" * (length - filled)

    def extract_color(self, file_path):
        try:
            img = Image.open(file_path).convert("RGB")
            dominant_color = img.resize((1,1)).getpixel((0,0))
            return discord.Color.from_rgb(*dominant_color)
        except Exception as e:
            print(f"[extract_color] Error: {e}")
            return discord.Color.blurple()

    # ===== Gender Helper =====
    def format_gender(self, gender_rate):
        if gender_rate == -1:
            return "Genderless"
        elif gender_rate == 0:
            return "♂️ Male only"
        else:
            female_ratio = (8 - gender_rate) / 8
            male_ratio = gender_rate / 8
            male_percentage = int(female_ratio * 100)
            female_percentage = int(male_ratio * 100)
            if female_percentage == 100:
                return "♀️ Female only"
            elif male_percentage == 100:
                return "♂️ Male only"
            return f"♂ {male_percentage}% - ♀ {female_percentage}%"

    # ===== Embed Formatting =====
    def format_embed(self, data):
        try:
            embed_title = f"#{data['dex_number']} — {data['slug'].capitalize()}"
            file_path = f"data/commands/pokemon/pokemon_images/{self.slug}.png"

            stats_block = "\n".join([
                f"HP   {data['base.hp']:>3} {self.make_bar(int(data['base.hp']))}",
                f"Atk  {data['base.atk']:>3} {self.make_bar(int(data['base.atk']))}",
                f"Def  {data['base.def']:>3} {self.make_bar(int(data['base.def']))}",
                f"SpA  {data['base.satk']:>3} {self.make_bar(int(data['base.satk']))}",
                f"SpD  {data['base.sdef']:>3} {self.make_bar(int(data['base.sdef']))}",
                f"Spe  {data['base.spd']:>3} {self.make_bar(int(data['base.spd']))}",
            ])

            # ===== Alt names =====
            alt_name_lines = []
            alt_name_history = set()
            for lang in ["de","en","es","fr","it","ja","ja-Hrkt","ko","roomaji","zh-Hans","zh-Hant"]:
                name_col = f"name.{lang}"
                if not data.get(name_col): continue
                name = data[name_col].strip()
                lower_name = name.lower()
                if lower_name in alt_name_history or lower_name == data["slug"].lower(): continue
                alt_name_history.add(lower_name)
                flag = self.DEFAULT_LANG_FLAGS.get(lang, "🏴")
                alt_name_lines.append(f"{flag} {name}")
            alt_names = "\n".join(alt_name_lines) if alt_name_lines else "N/A"

            rarity = ("Mythical" if data.get("mythical") == "True"
                      else "Legendary" if data.get("legendary") == "True"
                      else "Normal")

            gender_text = self.format_gender(data.get("gender_rate", -1))
            description = (f"{data['description']}")

            embed = discord.Embed(title=embed_title, description=description,
                                  color=self.extract_color(file_path))
            embed.add_field(name="Region", value=data['region'].capitalize(), inline=True)
            embed.add_field(name="Types", value=self.format_type_field(data), inline=True)
            embed.add_field(name="Names", value=f"{alt_names}", inline=True)
            embed.add_field(name="Base Stats", value=f"```{stats_block}```", inline=False)

            embed.set_image(url=f"attachment://{self.slug}.png")
            embed.set_footer(
                icon_url='https://discords.com/_next/image?url=https%3A%2F%2Fcdn.discordapp.com%2Femojis%2F808909357240025099.png%3Fv%3D1&w=128&q=75',
                text=f"Height: {float(data['height']):.2f} m\nWeight: {float(data['weight']):.2f} kg    Gender: {gender_text}" +
                     (f"\nRarity: {rarity}" if rarity != 'Normal' else "")
            )

            return embed
        except Exception as e:
            print(f"[format_embed] Error: {e}")
            return discord.Embed(title="Error", description=str(e), color=discord.Color.red())

    # ===== Handle dynamic button interaction =====
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data.get("custom_id") == "dex_button":
            data = self.get_pokemon_info()
            if not data:
                await interaction.response.send_message("❌ Pokémon data not found.", ephemeral=True)
                return False
            embed = self.format_embed(data)
            file_path = f"data/commands/pokemon/pokemon_images/{self.slug}.png"
            await interaction.response.send_message(
                embed=embed,
                file=discord.File(file_path, filename=f"{self.slug}.png"),
                ephemeral=True
            )
            return False
        return True










# Cache fallbacks
try:
    from cachetools import LRUCache, TTLCache
except Exception:
    from collections import OrderedDict
    import time

    class LRUCache:
        def __init__(self, maxsize=1024):
            self.maxsize = maxsize
            self._od = OrderedDict()

        def get(self, k, default=None):
            if k in self._od:
                self._od.move_to_end(k)
                return self._od[k]
            return default

        def __setitem__(self, k, v):
            self._od[k] = v
            self._od.move_to_end(k)
            if len(self._od) > self.maxsize:
                self._od.popitem(last=False)

        def __contains__(self, k):
            return k in self._od

        def clear(self):
            self._od.clear()

    class TTLCache:
        def __init__(self, maxsize=1024, ttl=600):
            self.maxsize = maxsize
            self.ttl = ttl
            self._data = {}
            self._order = OrderedDict()

        def get(self, k, default=None):
            item = self._data.get(k)
            if not item:
                return default

            val, exp = item
            if exp and exp < time.time():
                self._data.pop(k, None)
                self._order.pop(k, None)
                return default

            self._order.move_to_end(k, last=True)
            return val

        def __setitem__(self, k, v):
            exp = time.time() + self.ttl if self.ttl else None
            self._data[k] = (v, exp)
            self._order[k] = None

            if len(self._data) > self.maxsize:
                old = next(iter(self._order))
                self._order.pop(old, None)
                self._data.pop(old, None)




         
            
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






