import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from io import BytesIO
import aiofiles
import numpy as np
from collections import OrderedDict
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import MongoHelper
from bot.cogs.pokemon import PoketwoCommands
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# ------------ TUNABLES (reduce memory here) ------------
MAX_IMG_BYTES_CACHE = 8            # keep only a few images in memory (optional)
MAX_PRED_CACHE = 256               # limit predictions cached
WORKER_COUNT = min(4, (os.cpu_count() or 4))     # reduce workers
CPU_POOL_SIZE = max(1, (os.cpu_count() or 4) // 2)  # fewer processes
THREAD_POOL_SIZE = min(8, (os.cpu_count() or 4) * 2)  # capped threads
QUEUE_MAXSIZE = 256                # bounded queue, prevents unbounded growth
PRELOAD_SPAWNS = os.getenv("PRELOAD_POKEMON_IMAGES") == "1"  # default: off
# -------------------------------------------------------

# executors (smaller)
CPU_EXECUTOR = ProcessPoolExecutor(max_workers=CPU_POOL_SIZE)
THREAD_EXECUTOR = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)

# tiny LRU cache implementation
class LRUCache(OrderedDict):
    def __init__(self, maxsize=128):
        super().__init__()
        self.maxsize = maxsize

    def __getitem__(self, key):
        value = super().__getitem__(key)
        # move to end to mark as recently used
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        if key in self:
            super().__setitem__(key, value)
            self.move_to_end(key)
            return
        super().__setitem__(key, value)
        if self.maxsize and len(self) > self.maxsize:
            # pop oldest
            self.popitem(last=False)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

# ---------------- Cog ----------------
class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot, worker_count=None):
        self.bot = bot
        self.target_id = 716390085896962058

        # predictor lazy: don't instantiate heavy model in main thread until needed
        self.predictor = None

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

        # caches - bounded to prevent runaway memory usage
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.file_cache = {}                           # slug -> path (on-disk)
        # small optional img-bytes LRU cache (mostly disabled/limited)
        self.img_bytes_cache = LRUCache(maxsize=MAX_IMG_BYTES_CACHE)
        self.pred_cache = LRUCache(maxsize=MAX_PRED_CACHE)
        self.base_cache = {}
        self.server_cache = {}
        self.ping_cache = {}
        self.desc_cache = {}
        self.type_cache = {}
        self.alt_cache = {}

        # pre-populate file_cache with already-created files (don't read bytes)
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path):
                self.file_cache[slug] = path

        # bounded queue prevents memory blow-up if spawns flood in
        self.queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self.worker_count = worker_count or WORKER_COUNT
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

        # start workers (fewer than before)
        for _ in range(self.worker_count):
            self.bot.loop.create_task(self._worker())

        # preload metadata (lightweight) and optionally generate image files in controlled batches
        asyncio.create_task(self._prepare_metadata_and_optional_images())

        # lazy store of full data used by views (load once, on demand)
        self._full_pokemon_data = None

    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn(message, image_url)
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
            finally:
                self.queue.task_done()

    async def _prepare_metadata_and_optional_images(self):
        """
        Preloads lightweight metadata (names, types, descriptions), but
        DOES NOT read all image bytes into memory. If PRELOAD_SPAWNS is enabled,
        it will generate missing image files in small batches so it doesn't
        flood the process pool with thousands of simultaneous tasks.
        """
        loop = asyncio.get_running_loop()
        slugs = list(self._pokemon_ids.keys())
        for slug in slugs:
            # light metadata
            self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)
            desc, dex = "", self._pokemon_ids.get(slug, "???")
            desc_data = self.pokemon_utils.get_description(slug)
            if desc_data:
                desc, dex = desc_data[:2]
            self.desc_cache[slug] = (desc, dex)

            self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
            self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""

            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if slug not in self.file_cache and os.path.exists(path):
                self.file_cache[slug] = path

        if not PRELOAD_SPAWNS:
            logger.info("Skipped heavy spawn-image preloading (PRELOAD_POKEMON_IMAGES not set).")
            return

        # If enabled, generate images in small batches to avoid memory spike
        batch_size = max(2, CPU_POOL_SIZE)  # small
        tasks = []
        for i, slug in enumerate(slugs):
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if slug in self.file_cache and os.path.exists(path):
                continue
            # schedule image creation in CPU executor - batched
            tasks.append(loop.run_in_executor(
                CPU_EXECUTOR,
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

            # every batch_size tasks, await them (keeps concurrency small)
            if len(tasks) >= batch_size:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Prepared spawn images on disk (preload finished).")

    async def _ensure_predictor(self):
        """
        Lazy init of the predictor inside the THREAD_EXECUTOR to avoid
        loading heavy models in the main event loop memory.
        """
        loop = asyncio.get_running_loop()
        if self.predictor is None:
            # create in threadpool (so model memory is allocated on worker thread/process)
            self.predictor = await loop.run_in_executor(THREAD_EXECUTOR, Prediction)
        return self.predictor

    async def process_spawn(self, message, image_url):
        try:
            loop = asyncio.get_running_loop()

            # prediction: use LRU pred_cache to bound memory
            cached = self.pred_cache.get(image_url)
            if cached:
                raw_name, conf = cached
            else:
                predictor = await self._ensure_predictor()
                # run prediction in thread pool (predictor is thread-safe for this code)
                raw_name, conf = await loop.run_in_executor(
                    THREAD_EXECUTOR, lambda: predictor.predict(image_url)
                )
                self.pred_cache[image_url] = (raw_name, conf)

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

            conf_float = float(str(conf).strip().rstrip("%"))
            low_conf = conf_float < 30

            sid = message.guild.id
            if sid not in self.server_cache:
                self.server_cache[sid] = await self.pokemon_utils.get_server_config(sid)
            server_config = self.server_cache[sid]

            shiny_collect, type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_ping_users(message.guild, base_name),
                self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
            )
            shiny_pings, collect_pings = shiny_collect
            self.ping_cache[(sid, base_name)] = (type_pings, quest_pings, shiny_pings, collect_pings)

            rare, regional = self.pokemon_utils._special_names
            special_roles = []
            if server_config.get("rare_role"):
                special_roles += [f"<@&{server_config['rare_role']}>" for r in rare if r in base_name]
            if server_config.get("regional_role"):
                special_roles += [f"<@&{server_config['regional_role']}>" for r in regional if r in base_name]

            desc, dex = self.desc_cache.get(base_name, ("", "???"))
            dex = self._pokemon_ids.get(base_name, dex)

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

            # Obtain image file path; if missing, generate it (on disk) but DO NOT load all bytes to memory
            path = os.path.join(self.spawn_dir, f"{base_name}.png")
            if base_name not in self.file_cache or not os.path.exists(path):
                # create image on-disk (use CPU pool)
                await loop.run_in_executor(
                    CPU_EXECUTOR,
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

            # Option A (preferred): stream file to discord without reading bytes into memory
            # open file and pass to discord.File; ensure file is closed after send
            try:
                f = open(path, "rb")
            except Exception as e:
                logger.error(f"Failed to open spawn image {path}: {e}")
                return await message.channel.send(
                    f"{self.cross_emoji} Missing image for {base_name}",
                    reference=message,
                )

            # prepare view: use cached full data loaded once (lazy)
            if self._full_pokemon_data is None:
                # load once (may be somewhat heavy; still better than reloading every time)
                try:
                    self._full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()
                except Exception:
                    self._full_pokemon_data = {}

            view = PokemonSpawnView(
                slug=base_name,
                pokemon_data=self._full_pokemon_data,
                pokemon_utils=self.pokemon_utils
            )

            try:
                # send with open file (no BytesIO copy)
                await message.channel.send(
                    content=ping_msg,
                    file=discord.File(fp=f, filename=f"{base_name}.png"),
                    reference=message,
                    view=view
                )
            finally:
                try:
                    f.close()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
            try:
                await message.channel.send(
                    f"{self.error_emoji} Failed to process spawn", reference=message
                )
            except Exception:
                pass

    @commands.command(name="generate_spawns", hidden=True)
    async def generate_all_spawn_images(self, ctx):
        """
        Generate missing spawn image files on disk in small batches.
        This command still avoids loading many images into memory.
        """
        os.makedirs(self.spawn_dir, exist_ok=True)
        missing_or_empty = [
            slug for slug in self._pokemon_ids
            if not os.path.exists(os.path.join(self.spawn_dir, f"{slug}.png"))
            or os.path.getsize(os.path.join(self.spawn_dir, f"{slug}.png")) == 0
        ]

        if not missing_or_empty:
            return await ctx.send("✅ All spawn images preloaded and valid!")

        await ctx.send(f"⚠️ Preloading {len(missing_or_empty)} Pokémon images... (batched)")

        loop = asyncio.get_running_loop()
        tasks = []
        batch_size = max(2, CPU_POOL_SIZE)
        for slug in missing_or_empty:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            tasks.append(loop.run_in_executor(
                CPU_EXECUTOR,
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
            if len(tasks) >= batch_size:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        await ctx.send("✅ All spawn images generated on disk (cached paths).")

    @commands.Cog.listener()
    async def on_message(self, message):
        # ignore non-poketwo and test bot flag
        if message.author.id != self.target_id or ut:
            return
        for e in message.embeds:
            if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                try:
                    # don't block: drop spawn if queue full to avoid memory blowup
                    self.queue.put_nowait((message, e.image.url))
                except asyncio.QueueFull:
                    logger.warning("Spawn queue full; dropping incoming spawn to protect memory.")
                return  # only process first matching embed

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
