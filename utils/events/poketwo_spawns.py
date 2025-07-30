import os, io, re, csv, json, logging, requests, aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageSequence
from colorthief import ColorThief
from pilmoji import Pilmoji
from fuzzywuzzy import fuzz



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
        self.bot = bot  # Pass bot here explicitly if needed for async data access
        self.pp = pp

        self._type_emojis = {}
        self._quest_emojis = {}
        self.load_emojis()

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

    def format_name(self, name):
     lens = {
        "iron-treads", "iron-bundle", "iron-hands", "iron-jugulis", "iron-moth", "iron-thorns",
        "great-tusk", "scream-tail", "brute-bonnet", "flutter-mane", "slither-wing", "sandy-shocks", "roaring-moon",
        "walking-wake", "raging-bolt", "gouging-fire", "iron-leaves", "iron-valiant", "iron-boulder", "iron-crown"
     }
     if name in lens or any(name.endswith(f"-{form}") for form in self.regional_forms):
        return name.replace('-', ' ').title()
     return name.split('-')[0].title()
 
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

            # Use self.bot passed in constructor instead of guild.bot
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
                    label = f"{ptype.capitalize()} Type".strip() # {emoji}
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
                color_thief = ColorThief(img_bytes)
                r, g, b = color_thief.get_color(quality=1)
                return (r << 16) + (g << 8) + b
        except Exception as e:
            logger.warning(f"Failed to get image color: {e}")
            return fallback


class PokemonImageBuilder:
    def __init__(self):
        self.config_path = "data/events/poketwo_spawns/image/config.json"
        self.type_emojis_file = "data/commands/pokemon/pokemon_emojis/_pokemon_types.json"
        self.emoji_icon_dir = "data/commands/pokemon/pokemon_emojis/icons/types"
        self.base_url = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/"
        os.makedirs(self.emoji_icon_dir, exist_ok=True)

        with open(self.config_path, 'r') as f:
            self.config = json.load(f)
        with open(self.type_emojis_file, 'r', encoding='utf-8') as f:
            self.type_emojis = json.load(f)

        self.font_header = ImageFont.truetype(self.config["font_path_header"], self.config["font_size_header"])
        self.font_base = ImageFont.truetype(self.config["font_path_base"], self.config["font_size_base"])
        self.output_dir = "data/events/poketwo_spawns/image"
        os.makedirs(self.output_dir, exist_ok=True)

    def fetch_pokemon_image(self, pokemon_id):
        url = f"{self.base_url}{pokemon_id}.png"
        response = requests.get(url)
        if response.status_code == 200:
            return Image.open(io.BytesIO(response.content)).convert("RGBA"), io.BytesIO(response.content)
        raise Exception(f"Failed to fetch image for ID {pokemon_id}")

    @staticmethod
    def country_code_to_flag_emoji(cc):
        OFFSET = 127397
        return "".join(chr(ord(c) + OFFSET) for c in cc.upper())

    def get_dominant_color(self, image_bytes_io):
        return ColorThief(image_bytes_io).get_color(quality=1)

    def extract_emoji_id(self, emoji_str):
        match = re.search(r"<:.+?:(\d+)>", emoji_str)
        return match.group(1) if match else None

    def get_or_download_emoji_image(self, emoji_str):
        emoji_id = self.extract_emoji_id(emoji_str)
        if not emoji_id:
            return None
        local_path = os.path.join(self.emoji_icon_dir, f"{emoji_id}.png")
        if not os.path.exists(local_path):
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
            r = requests.get(url)
            if r.status_code == 200:
                with open(local_path, 'wb') as f:
                    f.write(r.content)
            else:
                return None
        return Image.open(local_path).convert("RGBA")

    def draw_type_emojis(self, canvas, types, position):
        x, y = position
        spacing = self.config["type_spacing"]
        icon_size = self.config["type_icon_size"]

        if len(types) == 1:
            x += spacing

        for type_name in types:
            emoji_str = self.type_emojis.get(f"{type_name.lower()}_type", "")
            emoji_img = self.get_or_download_emoji_image(emoji_str)
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
            emoji_img = self.get_or_download_emoji_image(emoji_str)
            if emoji_img:
                with io.BytesIO() as buf:
                    emoji_img.save(buf, format="PNG")
                    buf.seek(0)
                    dom_color = ColorThief(buf).get_color(quality=1)
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
                response = requests.get(bg_url, timeout=5, allow_redirects=True)
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
                if not frames:
                    bg_image = bg_image.convert("RGBA")
                    bg_image = self.resize_and_crop(bg_image, (width, height))
                    if blur_enabled:
                        bg_image = bg_image.filter(ImageFilter.GaussianBlur(radius=8))
                    return [bg_image], [100]
                return frames, durations
            except (requests.RequestException, OSError) as e:
                print(f"[BG ERROR] Using color fallback. {e}")

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
            pilmoji.text(
                (x, offset_y),
                part,
                font=font,
                fill=fill,
                stroke_fill=stroke_fill,
                stroke_width=stroke_width
            )
            x += width

    def compose_frame(self, bg_frame, poke_img, pokemon_name, best_name, types):
        frame = bg_frame.copy()
        poke_img_resized = poke_img.resize(self.config["pokemon_image_size"])
        frame.paste(poke_img_resized, self.config["pokemon_image_position"], poke_img_resized)

        pilmoji = Pilmoji(frame)

        self.draw_text_with_flag_offset(
            pilmoji,
            self.config["pokemon_name_position"],
            pokemon_name,
            self.font_header,
            self.config["name_color"],
            stroke_fill=self.config.get("name_outline_color"),
            stroke_width=self.config.get("name_stroke_width", 0)
        )

        self.draw_text_with_flag_offset(
            pilmoji,
            self.config["alt_name_position"],
            best_name,
            self.font_base,
            self.config["alt_color"],
            stroke_fill=self.config.get("alt_outline_color"),
            stroke_width=self.config.get("alt_stroke_width", 0)
        )

        self.draw_type_emojis(frame, types, self.config["type_position"])
        return frame

    def create_image(self, pokemon_id, pokemon_name, best_name, types, bg_url=None, filename="test.png"):
        poke_img, img_bytes = self.fetch_pokemon_image(pokemon_id)
        type_colors = self.get_type_colors(types)
        bg_frames, durations = self.prepare_background_frames(type_colors, bg_url)
        frames = [self.compose_frame(bg_frame, poke_img, pokemon_name, best_name, types) for bg_frame in bg_frames]
        filepath = os.path.join(self.output_dir, filename)
        if len(frames) == 1:
            frames[0].save(filepath)
        else:
            frames[0].save(filepath, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2, transparency=0)






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







