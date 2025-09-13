# Updated PoketwoSpawnDetector with performance and stability improvements for 24/7 running.
# Key changes:
# - Bounded asyncio.Queue to apply backpressure
# - ThreadPoolExecutor sized & shared
# - LRU and TTL caches (with fallbacks if cachetools not installed)
# - Preload guard and single-load full_pokemon_data
# - Limited worker_count and message-send semaphore to avoid rate / resource spikes
# - Safer predictor caching & exception handling
# - Reduced repeated DB/load calls (server config cached with TTL)
# - Use img bytes LRU cache to avoid repeated disk reads while bounding memory

import os
import time
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from collections import OrderedDict
import aiofiles
import numpy as np
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import MongoHelper
from bot.cogs.pokemon import PoketwoCommands
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# Shared thread pool (bounded)
_THREAD_POOL_MAX = min(32, max(4, (os.cpu_count() or 4) * 2))
_thread_executor = ThreadPoolExecutor(max_workers=_THREAD_POOL_MAX)


# Try to use cachetools; if unavailable, provide lightweight fallbacks
try:
    from cachetools import LRUCache, TTLCache
except Exception:
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
        def pop(self, k, default=None):
            return self._od.pop(k, default)
        def items(self):
            return self._od.items()
        def keys(self):
            return self._od.keys()
        def clear(self):
            self._od.clear()

    class TTLCache:
        def __init__(self, maxsize=1024, ttl=600):
            self.maxsize = maxsize
            self.ttl = ttl
            self._data = {}  # k -> (value, expiry_ts)
            self._order = OrderedDict()
        def _evict_if_needed(self):
            while len(self._data) > self.maxsize:
                # pop oldest
                k, _ = self._order.popitem(last=False)
                self._data.pop(k, None)
        def get(self, k, default=None):
            item = self._data.get(k)
            if not item:
                return default
            val, exp = item
            if exp and exp < time.time():
                self._data.pop(k, None)
                try: self._order.pop(k, None)
                except: pass
                return default
            # refresh order
            try:
                self._order.move_to_end(k)
            except:
                pass
            return val
        def __setitem__(self, k, v):
            exp = time.time() + self.ttl if self.ttl else None
            if k not in self._data:
                self._order[k] = None
            self._data[k] = (v, exp)
            try:
                self._order.move_to_end(k)
            except:
                pass
            self._evict_if_needed()
        def pop(self, k, default=None):
            self._order.pop(k, None)
            return self._data.pop(k, (default, None))[0]
        def clear(self):
            self._data.clear()
            self._order.clear()


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

        # Pokemon ids & derived caches
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids() or {}
        # keep file paths for existing spawn images (persisted)
        self.file_cache = {}  # slug -> path (persisted on disk)
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path):
                self.file_cache[slug] = path

        # Caches (LRU / TTL) to bound memory usage on a long-running process
        # sizes chosen conservatively; tune if needed
        self.pred_cache = LRUCache(maxsize=5000)            # image_url -> (raw_name, conf)
        self.img_bytes_cache = LRUCache(maxsize=max(2000, len(self._pokemon_ids) + 50))  # slug -> bytes
        self.ping_cache = LRUCache(maxsize=10000)           # (sid, base_name) -> pings tuple
        self.base_cache = {}                                # raw_name -> base_name (small)
        self.desc_cache = {}                                # base_name -> (desc, dex)
        self.type_cache = {}                                # base_name -> types
        self.alt_cache = {}                                 # base_name -> alt name
        self.server_cache = TTLCache(maxsize=2000, ttl=600) # sid -> server config (10 min TTL)

        # Backpressure queue to avoid memory blow-up under spikes
        self.queue = asyncio.Queue(maxsize=256)

        # Worker count: keep modest for 24/7 stability (avoid huge concurrency)
        default_workers = min(16, max(4, (os.cpu_count() or 4)))
        self.worker_count = worker_count or default_workers

        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

        # semaphore to limit concurrent message sends (helps avoid rate limits / bursts)
        self._send_semaphore = asyncio.Semaphore(8)

        # Preload guard & place to cache full_pokemon_data
        self._preloaded = False
        self.full_pokemon_data = None

        # spawn image metadata preload is started on bot loop
        for _ in range(self.worker_count):
            try:
                self.bot.loop.create_task(self._worker())
            except Exception:
                # fallback to asyncio.create_task if loop unavailable at instantiation
                asyncio.create_task(self._worker())

        # schedule pickellize/preload using bot loop if possible
        try:
            self.bot.loop.create_task(self._pickellize_all())
        except Exception:
            asyncio.create_task(self._pickellize_all())

    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn(message, image_url)
            except Exception:
                logger.exception("Worker error while processing spawn")
            finally:
                try:
                    self.queue.task_done()
                except Exception:
                    pass

    async def _pickellize_all(self):
        # Preload metadata + generate missing images and cache bytes.
        if getattr(self, "_preloaded", False):
            return
        self._preloaded = True

        loop = asyncio.get_running_loop()
        tasks = []

        # fill metadata caches and queue image generation for missing files
        for slug in self._pokemon_ids:
            try:
                self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)
            except Exception:
                self.base_cache[slug] = slug

            desc, dex = "", self._pokemon_ids.get(slug, "???")
            try:
                desc_data = self.pokemon_utils.get_description(slug)
                if desc_data:
                    desc, dex = desc_data[:2]
            except Exception:
                pass
            self.desc_cache[slug] = (desc, dex)

            try:
                self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
            except Exception:
                self.type_cache[slug] = []

            try:
                self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""
            except Exception:
                self.alt_cache[slug] = ""

            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if slug not in self.file_cache or not os.path.exists(self.file_cache[slug]):
                # generate on thread pool; ThreadPoolExecutor bounded by _THREAD_POOL_MAX
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

        if tasks:
            # run generators (exceptions returned but we continue)
            await asyncio.gather(*tasks, return_exceptions=True)

        # read all existing files into img_bytes_cache (bounded by LRU size)
        read_tasks = []
        for slug, path in list(self.file_cache.items()):
            read_tasks.append(self._read_and_cache_bytes(slug, path))
        if read_tasks:
            await asyncio.gather(*read_tasks, return_exceptions=True)

        # cache full pokemon data once
        try:
            self.full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()
        except Exception:
            self.full_pokemon_data = None

        logger.info("Preloaded Pokémon metadata and images.")

    async def _read_and_cache_bytes(self, slug, path):
        try:
            async with aiofiles.open(path, "rb") as f:
                data = await f.read()
            if data:
                self.img_bytes_cache[slug] = data
        except Exception:
            # fail silently—image might be missing or corrupt
            pass

    async def process_spawn(self, message, image_url):
        """Process single spawn: prediction -> get metadata -> send message."""
        try:
            loop = asyncio.get_running_loop()

            # 1) Prediction (cached, LRU)
            pred = self.pred_cache.get(image_url)
            if pred is None:
                try:
                    raw_name, conf = await loop.run_in_executor(
                        _thread_executor, self.predictor.predict, image_url
                    )
                except Exception:
                    logger.exception("Predictor failed for %s", image_url)
                    raw_name, conf = ("unknown", "0%")
                try:
                    self.pred_cache[image_url] = (raw_name, conf)
                except Exception:
                    # in case our cache impl doesn't support item assignment pattern
                    pass
            else:
                raw_name, conf = pred

            # 2) Resolve base name -> cache
            base_name = self.base_cache.get(raw_name)
            if not base_name:
                try:
                    base_name = self.pokemon_utils.get_base_pokemon_name(raw_name)
                except Exception:
                    base_name = None
                if not base_name or base_name not in self._pokemon_ids:
                    try:
                        base_name = (
                            self.pokemon_utils.find_full_name_for_slug(raw_name)
                            .lower()
                            .replace("_", "-")
                        )
                    except Exception:
                        base_name = raw_name.lower().replace("_", "-")
                self.base_cache[raw_name] = base_name

            # 3) Confidence handling
            try:
                conf_float = float(str(conf).strip().rstrip("%"))
            except Exception:
                conf_float = 0.0
            low_conf = conf_float < 30

            # 4) Server config (cached with TTL)
            sid = None
            try:
                sid = message.guild.id
            except Exception:
                sid = None

            server_config = None
            if sid is not None:
                server_config = self.server_cache.get(sid)
                if server_config is None:
                    try:
                        server_config = await self.pokemon_utils.get_server_config(sid)
                    except Exception:
                        server_config = {}
                    try:
                        self.server_cache[sid] = server_config
                    except Exception:
                        pass

            # 5) ping users (concurrent)
            try:
                shiny_collect, type_pings, quest_pings = await asyncio.gather(
                    self.pokemon_utils.get_ping_users(message.guild, base_name),
                    self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                    self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
                )
                shiny_pings, collect_pings = shiny_collect
            except Exception:
                # if any ping fetch fails, fall back to empty lists
                logger.exception("Failed to fetch pings for %s", base_name)
                type_pings = []
                quest_pings = []
                shiny_pings = []
                collect_pings = []

            try:
                self.ping_cache[(sid, base_name)] = (type_pings, quest_pings, shiny_pings, collect_pings)
            except Exception:
                pass

            # 6) special roles
            try:
                rare, regional = self.pokemon_utils._special_names
            except Exception:
                rare, regional = ([], [])
            special_roles = []
            if server_config and server_config.get("rare_role"):
                special_roles += [f"<@&{server_config['rare_role']}>" for r in rare if r in (base_name or "")]
            if server_config and server_config.get("regional_role"):
                special_roles += [f"<@&{server_config['regional_role']}>" for r in regional if r in (base_name or "")]

            # 7) desc/dex
            desc, dex = self.desc_cache.get(base_name, ("", "???"))
            dex = self._pokemon_ids.get(base_name, dex)

            # 8) format the ping message
            try:
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
            except Exception:
                logger.exception("format_messages failed for %s", base_name)
                ping_msg = f"{self.cross_emoji} {base_name}"

            # 9) image bytes (LRU cache)
            img_bytes = self.img_bytes_cache.get(base_name)
            if not img_bytes:
                path = os.path.join(self.spawn_dir, f"{base_name}.png")
                if base_name not in self.file_cache:
                    # generate missing image on thread-pool
                    try:
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
                    except Exception:
                        logger.exception("Failed to generate image for %s", base_name)

                # read file bytes if possible
                try:
                    async with aiofiles.open(path, "rb") as f:
                        img_bytes = await f.read()
                    if img_bytes:
                        try:
                            self.img_bytes_cache[base_name] = img_bytes
                        except Exception:
                            pass
                except Exception:
                    # if missing, notify channel
                    try:
                        await message.channel.send(f"{self.cross_emoji} Missing image for {base_name}", reference=message)
                    except Exception:
                        logger.exception("Failed to notify missing image for %s", base_name)
                    return

            # 10) build view (use preloaded full data when possible)
            pokemon_data = self.full_pokemon_data
            if pokemon_data is None:
                try:
                    pokemon_data = self.pokemon_utils.load_full_pokemon_data()
                    self.full_pokemon_data = pokemon_data
                except Exception:
                    pokemon_data = None

            view = PokemonSpawnView(
                slug=base_name,
                pokemon_data=pokemon_data,
                pokemon_utils=self.pokemon_utils
            )

            # 11) Send message with send semaphore to limit concurrent send operations
            await self._acquire_send_and_send(message, ping_msg, img_bytes, base_name, view)

        except Exception:
            logger.exception("Spawn processing error")
            try:
                await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)
            except Exception:
                logger.exception("Failed to send failure message")

    async def _acquire_send_and_send(self, message, ping_msg, img_bytes, base_name, view):
        await self._send_semaphore.acquire()
        try:
            # create a fresh BytesIO for each send (pointer starts at 0)
            file_obj = discord.File(fp=BytesIO(img_bytes), filename=f"{base_name}.png")
            await message.channel.send(content=ping_msg, file=file_obj, reference=message, view=view)
        except Exception:
            logger.exception("Failed to send spawn message for %s", base_name)
        finally:
            try:
                self._send_semaphore.release()
            except Exception:
                pass

    @commands.command(name="generate_spawns", hidden=True)
    async def generate_all_spawn_images(self, ctx):
        os.makedirs(self.spawn_dir, exist_ok=True)
        missing_or_empty = []
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                missing_or_empty.append(slug)

        if not missing_or_empty:
            return await ctx.send("✅ All spawn images preloaded and valid!")

        await ctx.send(f"⚠️ Preloading {len(missing_or_empty)} Pokémon images...")

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

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # read cached bytes
        read_tasks = []
        for slug in missing_or_empty:
            path = self.file_cache.get(slug)
            if path:
                read_tasks.append(self._read_and_cache_bytes(slug, path))
        if read_tasks:
            await asyncio.gather(*read_tasks, return_exceptions=True)

        await ctx.send("✅ All spawn images generated, cached, and verified!")

    @commands.Cog.listener()
    async def on_message(self, message):
        # NOTE: keep original guard semantics (unchanged from supplied code)
        if message.author.id != self.target_id or ut:
            return
        for e in message.embeds:
            if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                # put will block if queue is full (backpressure)
                try:
                    await self.queue.put((message, e.image.url))
                except Exception:
                    logger.exception("Failed to enqueue spawn")

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
        except Exception:
            logger.exception("Prediction command error")
            await ctx.send(f"{self.error_emoji} Failed to process prediction.")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
