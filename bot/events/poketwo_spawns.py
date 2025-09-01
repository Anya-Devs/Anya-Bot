import os
import time
import asyncio
import logging
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import aiofiles
from motor.motor_asyncio import AsyncIOMotorClient

from bot.token import use_test_bot as ut
from imports.discord_imports import *  # noqa: F401,F403
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import PoketwoCommands, MongoHelper

logger = logging.getLogger(__name__)

# -----------------------
# Memory-safe cache utils
# -----------------------
class TTLCache:
    """Simple TTL + LRU (count-based) cache with O(1) get/set and periodic eviction."""
    def __init__(self, maxsize: int = 2048, ttl: float = 3600.0):
        self._store = OrderedDict()  # key -> (value, expires_at)
        self.maxsize = maxsize
        self.ttl = ttl

    def _evict(self):
        # Remove expired
        now = time.time()
        expired = [k for k, (_, exp) in self._store.items() if exp < now]
        for k in expired:
            self._store.pop(k, None)
        # Enforce LRU size bound
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def get(self, key, default=None):
        item = self._store.get(key)
        if not item:
            self._evict()
            return default
        value, exp = item
        if exp < time.time():
            self._store.pop(key, None)
            self._evict()
            return default
        # move to end (recently used)
        self._store.move_to_end(key, last=True)
        return value

    def set(self, key, value):
        self._store[key] = (value, time.time() + self.ttl)
        self._store.move_to_end(key, last=True)
        self._evict()

    def pop(self, key, default=None):
        item = self._store.pop(key, None)
        return item[0] if item else default

    def clear(self):
        self._store.clear()

    def __len__(self):
        self._evict()
        return len(self._store)


class SizedLRUCache:
    """LRU cache bounded by total byte size (good for image bytes)."""
    def __init__(self, max_bytes: int = 256 * 1024 * 1024):
        self._store = OrderedDict()  # key -> (value, size)
        self._bytes = 0
        self.max_bytes = max_bytes

    def _evict(self):
        while self._bytes > self.max_bytes and self._store:
            _, (v, sz) = self._store.popitem(last=False)
            self._bytes -= sz

    def get(self, key, default=None):
        item = self._store.get(key)
        if not item:
            return default
        v, sz = item
        self._store.move_to_end(key, last=True)
        return v

    def set(self, key, value: bytes):
        sz = len(value) if hasattr(value, "__len__") else 1
        old = self._store.pop(key, None)
        if old:
            self._bytes -= old[1]
        self._store[key] = (value, sz)
        self._store.move_to_end(key, last=True)
        self._bytes += sz
        self._evict()

    def pop(self, key, default=None):
        item = self._store.pop(key, None)
        if not item:
            return default
        v, sz = item
        self._bytes -= sz
        return v

    def clear(self):
        self._store.clear()
        self._bytes = 0

    @property
    def current_bytes(self) -> int:
        return self._bytes


# -----------------------
# Config (env-tunable)
# -----------------------
IMG_CACHE_MAX_MB = int(os.getenv("POKETWO_IMG_CACHE_MB", "256"))
PRED_CACHE_MAX = int(os.getenv("POKETWO_PRED_CACHE_MAX", "5000"))
PRED_CACHE_TTL = float(os.getenv("POKETWO_PRED_CACHE_TTL", "3600"))  # seconds
PING_CACHE_MAX = int(os.getenv("POKETWO_PING_CACHE_MAX", "5000"))
PING_CACHE_TTL = float(os.getenv("POKETWO_PING_CACHE_TTL", "3600"))
SERVER_CACHE_MAX = int(os.getenv("POKETWO_SERVER_CACHE_MAX", "2000"))
SERVER_CACHE_TTL = float(os.getenv("POKETWO_SERVER_CACHE_TTL", "1800"))
QUEUE_MAXSIZE = int(os.getenv("POKETWO_QUEUE_MAX", "300"))
CREATE_CONCURRENCY = int(os.getenv("POKETWO_CREATE_CONCURRENCY", "32"))

# One shared executor (ok to reuse across cogs)
_thread_executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)


class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot, worker_count=None):
        self.bot = bot
        self.target_id = 716390085896962058
        self.predictor = Prediction()
        self.pp = PoketwoCommands(bot)
        self.mongo = MongoHelper(
            AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"]
        )
        self.pokemon_utils = PokemonUtils(
            self.mongo,
            type_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_types.json",
            quest_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_quest.json",
            description_file="data/commands/pokemon/pokemon_description.csv",
            id_file="data/commands/pokemon/pokemon_names.csv",
            regional_forms={
                "alola": "Alolan",
                "galar": "Galarian",
                "hisui": "Hisuian",
                "paldea": "Paldean",
                "unova": "Unovan",
            },
            lang_flags={"ja": "🇯🇵", "de": "🇩🇪", "fr": "🇫🇷", "en": "🇺🇸"},
            bot=bot,
            pp=self.pp,
        )
        self.image_builder = PokemonImageBuilder()
        self.spawn_dir = "data/events/poketwo_spawns/spawns"
        os.makedirs(self.spawn_dir, exist_ok=True)

        # ===== Static data =====
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()

        # ===== Caches (memory-safe) =====
        self.file_cache = {}  # slug -> path (tiny)
        # Bounded by bytes (default 256MB)
        self.img_bytes_cache = SizedLRUCache(max_bytes=IMG_CACHE_MAX_MB * 1024 * 1024)

        # TTL + LRU (count-bounded)
        self.pred_cache = TTLCache(maxsize=PRED_CACHE_MAX, ttl=PRED_CACHE_TTL)          # image_url -> (name, conf)
        self.server_cache = TTLCache(maxsize=SERVER_CACHE_MAX, ttl=SERVER_CACHE_TTL)    # guild_id -> config
        self.ping_cache = TTLCache(maxsize=PING_CACHE_MAX, ttl=PING_CACHE_TTL)          # (guild_id, base_name) -> pings

        # Small, bounded dicts (<= ~2k entries) — safe to keep
        self.base_cache, self.desc_cache = {}, {}
        self.type_cache, self.alt_cache = {}, {}

        # Preload existing image paths only (not bytes)
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path):
                self.file_cache[slug] = path

        # Work queue with backpressure to avoid RAM growth
        self.queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self.worker_count = worker_count or min((os.cpu_count() or 4) * 2, 32)
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

        # Task management
        self._worker_tasks: list[asyncio.Task] = []
        for _ in range(self.worker_count):
            t = self.bot.loop.create_task(self._worker())
            self._worker_tasks.append(t)
        self._precache_task = asyncio.create_task(self._precache_metadata())

        # Lazy full dataset (avoid reloading repeatedly)
        self._full_pokemon_data = None

    # -----------------
    # Lifecycle cleanup
    # -----------------
    def cog_unload(self):
        # Cancel workers & precache task
        for t in self._worker_tasks:
            t.cancel()
        if self._precache_task:
            self._precache_task.cancel()

    # ---------------
    # Helper methods
    # ---------------
    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn(message, image_url)
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
            finally:
                self.queue.task_done()

    async def _precache_metadata(self):
        """Pre-cache lightweight metadata and generate missing images to disk.
        Avoid loading image BYTES into RAM (paths only)."""
        try:
            loop = asyncio.get_running_loop()
            tasks = []

            for slug in self._pokemon_ids:
                # base name
                self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)

                # description + dex
                desc, dex = "", self._pokemon_ids.get(slug, "???")
                desc_data = self.pokemon_utils.get_description(slug)
                if desc_data:
                    desc, dex = desc_data[:2]
                self.desc_cache[slug] = (desc, dex)

                # types + alt
                self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
                self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""

                # ensure image exists on disk; do NOT read bytes into memory here
                path = os.path.join(self.spawn_dir, f"{slug}.png")
                self.file_cache[slug] = path
                if not os.path.exists(path) or os.path.getsize(path) == 0:
                    tasks.append(loop.run_in_executor(
                        _thread_executor,
                        self.image_builder.create_image,
                        slug,
                        self.pokemon_utils.format_name(slug).replace("_", " ").title(),
                        self.alt_cache[slug],
                        self.type_cache[slug],
                        None,
                        path,
                        "PNG",
                    ))

            # Chunk to cap concurrency and memory footprint
            if tasks:
                for i in range(0, len(tasks), CREATE_CONCURRENCY):
                    await asyncio.gather(*tasks[i:i + CREATE_CONCURRENCY], return_exceptions=True)

            logger.info("Preloaded Pokémon metadata and ensured images on disk (no byte preloads).")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Precache error: {type(e).__name__}: {e}")

    def _get_full_pokemon_data(self):
        if self._full_pokemon_data is None:
            self._full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()
        return self._full_pokemon_data

    # ---------------
    # Core processing
    # ---------------
    async def process_spawn(self, message, image_url):
        try:
            loop = asyncio.get_running_loop()

            # Prediction (TTL + LRU cache)
            cached_pred = self.pred_cache.get(image_url)
            if cached_pred:
                raw_name, conf = cached_pred
            else:
                raw_name, conf = await loop.run_in_executor(
                    _thread_executor, self.predictor.predict, image_url
                )
                self.pred_cache.set(image_url, (raw_name, conf))

            # Base name (normalize + fallback)
            base_name = self.base_cache.get(raw_name)
            if not base_name:
                base_name = self.pokemon_utils.get_base_pokemon_name(raw_name)
                if base_name not in self._pokemon_ids:
                    base_name = (
                        self.pokemon_utils.find_full_name_for_slug(raw_name)
                        .lower()
                        .replace("_", "-")
                    )
                self.base_cache[raw_name] = base_name

            # Confidence
            conf_float = float(str(conf).strip().rstrip("%"))
            low_conf = conf_float < 30

            # Server config (TTL cache)
            sid = message.guild.id
            server_config = self.server_cache.get(sid)
            if not server_config:
                server_config = await self.pokemon_utils.get_server_config(sid)
                self.server_cache.set(sid, server_config)

            # Pings (TTL cache)
            ping_key = (sid, base_name)
            cached_pings = self.ping_cache.get(ping_key)
            if cached_pings:
                type_pings, quest_pings, shiny_pings, collect_pings = cached_pings
            else:
                shiny_collect, type_pings, quest_pings = await asyncio.gather(
                    self.pokemon_utils.get_ping_users(message.guild, base_name),
                    self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                    self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
                )
                shiny_pings, collect_pings = shiny_collect
                self.ping_cache.set(ping_key, (type_pings, quest_pings, shiny_pings, collect_pings))

            # Special roles
            rare, regional = self.pokemon_utils._special_names
            special_roles = []
            if server_config.get("rare_role"):
                special_roles += [
                    f"<@&{server_config['rare_role']}>" for r in rare if r in base_name
                ]
            if server_config.get("regional_role"):
                special_roles += [
                    f"<@&{server_config['regional_role']}>" for r in regional if r in base_name
                ]

            # Description + dex
            desc, dex = self.desc_cache.get(base_name, ("", "???"))
            dex = self._pokemon_ids.get(base_name, dex)

            # Format ping message
            ping_msg, _ = await self.pokemon_utils.format_messages(
                raw_name,
                type_pings,
                quest_pings,
                shiny_pings,
                collect_pings,
                " ".join(special_roles),
                f"{conf_float:.2f}%",
                dex,
                desc,
                image_url,
                low_conf,
            )

            # Image bytes (size-bounded LRU)
            img_bytes = self.img_bytes_cache.get(base_name)
            if not img_bytes:
                path = self.file_cache.get(base_name) or os.path.join(self.spawn_dir, f"{base_name}.png")
                if not os.path.exists(path) or os.path.getsize(path) == 0:
                    # Generate file on disk if missing
                    await loop.run_in_executor(
                        _thread_executor,
                        self.image_builder.create_image,
                        base_name,
                        self.pokemon_utils.format_name(base_name).replace("_", " ").title(),
                        self.alt_cache.get(base_name, ""),
                        self.type_cache.get(base_name, []),
                        None,
                        path,
                        "PNG",
                    )
                self.file_cache[base_name] = path

                # Read bytes on demand, then insert into the bounded cache
                try:
                    async with aiofiles.open(path, "rb") as f:
                        img_bytes = await f.read()
                    self.img_bytes_cache.set(base_name, img_bytes)
                except Exception:
                    return await message.channel.send(
                        f"{self.cross_emoji} Missing image for {base_name}",
                        reference=message,
                    )

            # ===== Final send with buttons =====
            view = PokemonSpawnView(
                slug=base_name,
                pokemon_data=self._get_full_pokemon_data(),
                pokemon_utils=self.pokemon_utils
            )
            await message.channel.send(
                content=ping_msg,
                file=discord.File(fp=BytesIO(img_bytes), filename=f"{base_name}.png"),
                reference=message,
                view=view
            )

        except Exception as e:
            logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
            await message.channel.send(
                f"{self.error_emoji} Failed to process spawn", reference=message
            )

    # ---------------
    # Commands
    # ---------------
    @commands.command(name="generate_spawns", hidden=True)
    async def generate_all_spawn_images(self, ctx):
        """Generate missing images to disk ONLY (no byte preloading)."""
        os.makedirs(self.spawn_dir, exist_ok=True)

        missing_or_empty = []
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                missing_or_empty.append(slug)

        if not missing_or_empty:
            return await ctx.send("✅ All spawn images present on disk!")

        await ctx.send(f"⚠️ Generating {len(missing_or_empty)} Pokémon images to disk...")

        loop = asyncio.get_running_loop()
        tasks = []
        for slug in missing_or_empty:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            tasks.append(loop.run_in_executor(
                _thread_executor,
                self.image_builder.create_image,
                slug,
                self.pokemon_utils.format_name(slug).replace("_", " ").title(),
                self.alt_cache.get(slug, ""),
                self.type_cache.get(slug, []),
                None,
                path,
                "PNG",
            ))
            self.file_cache[slug] = path

        # Chunk execution to avoid spikes
        for i in range(0, len(tasks), CREATE_CONCURRENCY):
            await asyncio.gather(*tasks[i:i + CREATE_CONCURRENCY], return_exceptions=True)

        await ctx.send("✅ All spawn images generated to disk (memory-safe).")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Keep original logic; memory-safe queue will apply backpressure if busy
        if message.author.id != self.target_id or ut:
            return
        for e in message.embeds:
            if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                await self.queue.put((message, e.image.url))

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        try:
            def extract_image_from_message(msg: discord.Message):
                if msg.attachments:
                    return msg.attachments[0].url
                if msg.embeds:
                    embed = msg.embeds[0]
                    if embed.image and embed.image.url:
                        return embed.image.url
                    if embed.thumbnail and embed.thumbnail.url:
                        return embed.thumbnail.url
                return None

            message = ctx.message
            if not image_url:
                image_url = extract_image_from_message(message)
                if not image_url and message.reference:
                    ref = await ctx.channel.fetch_message(message.reference.message_id)
                    image_url = extract_image_from_message(ref)
                    if not image_url and ref.reference:
                        ref2 = await ctx.channel.fetch_message(ref.reference.message_id)
                        image_url = extract_image_from_message(ref2)
            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")
            await self.process_spawn(message, image_url)
        except Exception as e:
            logger.error(f"Prediction error: {type(e).__name__}: {e}")
            await ctx.send(f"{self.error_emoji} Failed to process prediction.")


def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
