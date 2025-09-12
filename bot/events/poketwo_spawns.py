import os
import asyncio
import logging
import gc
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from collections import OrderedDict
from io import BytesIO
import time
import aiofiles  # still used by other parts if needed
import numpy as np  # kept if other modules expect it
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import MongoHelper
from bot.cogs.pokemon import PoketwoCommands
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# --- Memory / concurrency tuning (safer defaults for <=512MB instances) ---
PRELOAD_SPAWNS = os.getenv("PRELOAD_POKEMON_IMAGES") == "1"  # keep opt-in
LOW_MEMORY = os.getenv("LOW_MEMORY_MODE") == "1"  # optional override for very small hosts

MAX_PRED_CACHE = int(os.getenv("MAX_PRED_CACHE", "64" if not LOW_MEMORY else "32"))
CPU_POOL_SIZE = int(os.getenv("CPU_POOL_SIZE", "1" if LOW_MEMORY else "1"))  # prefer single process on constrained hosts
THREAD_POOL_SIZE = int(os.getenv("THREAD_POOL_SIZE", "2" if not LOW_MEMORY else "1"))
QUEUE_MAXSIZE = int(os.getenv("QUEUE_MAXSIZE", "64" if not LOW_MEMORY else "16"))
WORKER_COUNT = int(os.getenv("WORKER_COUNT", "2" if not LOW_MEMORY else "1"))
PREDICTOR_IDLE_SECONDS = int(os.getenv("PREDICTOR_IDLE_SECONDS", "300"))  # drop predictor after idle

CPU_EXECUTOR = ProcessPoolExecutor(max_workers=CPU_POOL_SIZE)
THREAD_EXECUTOR = ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)


class LRUCache(OrderedDict):
    def __init__(self, maxsize=128):
        super().__init__()
        self.maxsize = maxsize

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
        if self.maxsize and len(self) > self.maxsize:
            self.popitem(last=False)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default


class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot, worker_count=None):
        self.bot = bot
        self.target_id = 716390085896962058
        self.predictor = None
        self._predictor_lock = asyncio.Lock()
        self.predictor_last_used = 0.0

        self.pp = PoketwoCommands(bot)
        mongo_uri = os.getenv("MONGO_URI")
        self.mongo = MongoHelper(AsyncIOMotorClient(mongo_uri)["Commands"]["pokemon"]) if mongo_uri else None

        self.pokemon_utils = PokemonUtils(
            self.mongo,
            type_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_types.json",
            quest_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_quest.json",
            description_file="data/commands/pokemon/pokemon_description.csv",
            id_file="data/commands/pokemon/pokemon_names.csv",
            regional_forms={"alola": "Alolan", "galar": "Galarian", "hisui": "Hisuian", "paldea": "Paldean", "unova": "Unovan"},
            lang_flags={"ja": "🇯🇵", "de": "🇩🇪", "fr": "🇫🇷", "en": "🇺🇸"},
            bot=bot, pp=self.pp,
        )

        self.image_builder = PokemonImageBuilder()
        self.spawn_dir = "data/events/poketwo_spawns/spawns"
        os.makedirs(self.spawn_dir, exist_ok=True)
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()

        # caches: keep small and memory-friendly (store paths / lightweight metadata only)
        self.file_cache = {}                     # slug -> filepath (no bytes)
        self.pred_cache = LRUCache(MAX_PRED_CACHE)
        self.base_cache = {}
        self.desc_cache = {}
        self.type_cache = {}
        self.alt_cache = {}

        self.queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self.worker_count = worker_count or WORKER_COUNT
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

        # prime file_cache with existing files (doesn't load them)
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path):
                self.file_cache[slug] = path

        # start workers and background preparers/cleanup tasks on the bot loop
        for _ in range(self.worker_count):
            self.bot.loop.create_task(self._worker())
        self.bot.loop.create_task(self._prepare_metadata_and_optional_images())
        self.bot.loop.create_task(self._predictor_idle_cleaner())

        self._full_pokemon_data = None

    # --- worker loop ---
    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn(message, image_url)
            except MemoryError:
                logger.error("MemoryError in worker — clearing caches & forcing GC.")
                self._clear_memory_caches()
                gc.collect()
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
            finally:
                try:
                    self.queue.task_done()
                except Exception:
                    pass

    # --- metadata (lightweight) and optional image preloading (batched if requested) ---
    async def _prepare_metadata_and_optional_images(self):
        loop = asyncio.get_running_loop()
        slugs = list(self._pokemon_ids.keys())
        batch = []
        for slug in slugs:
            try:
                self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)
                desc_data = self.pokemon_utils.get_description(slug)
                self.desc_cache[slug] = (desc_data[0], desc_data[1]) if desc_data else ("", self._pokemon_ids.get(slug, "???"))
                self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
                self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""
                path = os.path.join(self.spawn_dir, f"{slug}.png")
                if slug not in self.file_cache and os.path.exists(path):
                    self.file_cache[slug] = path

                # optional preload (very conservative batching)
                if PRELOAD_SPAWNS and slug not in self.file_cache:
                    batch.append((slug, path))
                    if len(batch) >= max(1, CPU_POOL_SIZE):
                        await self._batch_create_images(batch, executor=CPU_EXECUTOR)
                        batch.clear()

                # yield occasionally so the loop can breathe on small hosts
                if len(self.base_cache) % 100 == 0:
                    await asyncio.sleep(0)
            except Exception as e:
                logger.debug(f"Metadata prepare error for {slug}: {e}")
        if batch:
            await self._batch_create_images(batch, executor=CPU_EXECUTOR)

    async def _batch_create_images(self, items, executor):
        loop = asyncio.get_running_loop()
        futures = []
        for slug, path in items:
            futures.append(loop.run_in_executor(
                executor,
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
        if futures:
            # run in small batches to avoid bursts
            for i in range(0, len(futures), 4):
                subset = futures[i:i + 4]
                await asyncio.gather(*subset, return_exceptions=True)
                await asyncio.sleep(0)

    # --- predictor lifecycle (lazy + cleanup) ---
    async def _ensure_predictor(self):
        async with self._predictor_lock:
            if self.predictor is None:
                loop = asyncio.get_running_loop()
                # instantiate predictor in thread to avoid blocking event loop
                try:
                    self.predictor = await loop.run_in_executor(THREAD_EXECUTOR, Prediction)
                except Exception as e:
                    logger.error(f"Failed to initialize predictor: {e}")
                    self.predictor = None
            self.predictor_last_used = time.time()
            return self.predictor

    async def _predictor_idle_cleaner(self):
        # background task to free predictor after idle to save memory
        while True:
            await asyncio.sleep(60)
            try:
                if self.predictor and (time.time() - self.predictor_last_used) > PREDICTOR_IDLE_SECONDS:
                    logger.info("Predictor idle for too long — freeing memory.")
                    async with self._predictor_lock:
                        try:
                            # attempt graceful teardown if predictor exposes it
                            teardown = getattr(self.predictor, "close", None) or getattr(self.predictor, "shutdown", None)
                            if teardown:
                                try:
                                    res = teardown()
                                    if asyncio.iscoroutine(res):
                                        await res
                                except Exception:
                                    pass
                        finally:
                            self.predictor = None
                            gc.collect()
            except Exception as e:
                logger.debug(f"Predictor cleaner error: {e}")

    # --- processing a spawn (memory-friendly) ---
    async def process_spawn(self, message, image_url):
        try:
            loop = asyncio.get_running_loop()

            cached = self.pred_cache.get(image_url)
            if cached:
                raw_name, conf = cached
            else:
                predictor = await self._ensure_predictor()
                if predictor is None:
                    raise RuntimeError("Predictor unavailable")
                # run prediction in thread executor (predict should be CPU/lightweight)
                raw_name, conf = await loop.run_in_executor(THREAD_EXECUTOR, lambda: predictor.predict(image_url))
                self.pred_cache[image_url] = (raw_name, conf)

            base_name = self.base_cache.get(raw_name) or self.pokemon_utils.get_base_pokemon_name(raw_name)
            if base_name not in self._pokemon_ids:
                base_name = self.pokemon_utils.find_full_name_for_slug(raw_name).lower().replace("_", "-")
            self.base_cache[raw_name] = base_name

            # parse confidence robustly
            try:
                conf_float = float(str(conf).strip().rstrip("%"))
            except Exception:
                conf_float = 0.0

            desc, dex = self.desc_cache.get(base_name, ("", "???"))
            dex = self._pokemon_ids.get(base_name, dex)
            ping_msg = f"**{base_name.title()}** {conf_float:.2f}%"

            # ensure image exists (create on demand). create_image should write to disk.
            path = os.path.join(self.spawn_dir, f"{base_name}.png")
            if base_name not in self.file_cache or not os.path.exists(path):
                await loop.run_in_executor(
                    CPU_EXECUTOR,
                    self.image_builder.create_image,
                    base_name,
                    self.pokemon_utils.format_name(base_name).replace("_", " ").title(),
                    self.alt_cache.get(base_name, ""),
                    self.type_cache.get(base_name, []),
                    None,
                    path,
                    "PNG"
                )
                self.file_cache[base_name] = path

            # load full pokemon data lazily (may be heavy)
            if self._full_pokemon_data is None:
                try:
                    self._full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()
                except Exception:
                    self._full_pokemon_data = {}

            # memory-friendly send: pass file path to discord.File so we don't hold bytes in memory
            try:
                file_obj = discord.File(path, filename=f"{base_name}.png")
                view = PokemonSpawnView(slug=base_name, pokemon_data=self._full_pokemon_data, pokemon_utils=self.pokemon_utils)
                await message.channel.send(content=ping_msg, file=file_obj, reference=message, view=view)
            except Exception as send_exc:
                # fallback: attempt smaller payload or simple message
                logger.error(f"Failed to send spawn message with file: {send_exc}")
                try:
                    await message.channel.send(content=ping_msg, reference=message)
                except Exception:
                    pass

        except MemoryError:
            logger.error("MemoryError during spawn processing — clearing caches & GC.")
            self._clear_memory_caches()
            gc.collect()
            try:
                await message.channel.send(f"{self.error_emoji} Failed to process spawn (memory).", reference=message)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
            try:
                await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)
            except Exception:
                pass

    # --- helper to clear in-memory caches (paths-only caches are safe) ---
    def _clear_memory_caches(self):
        try:
            self.pred_cache.clear()
            # keep base/desc/type/alt caches (they are small text metadata)
        except Exception:
            pass

    # --- message listener (only process target author and when not in test mode) ---
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.target_id or ut:
            return
        for e in message.embeds:
            if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                try:
                    self.queue.put_nowait((message, e.image.url))
                except asyncio.QueueFull:
                    logger.warning("Spawn queue full; dropping incoming spawn.")
                return

    # --- manual command to predict from a message / URL ---
    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        try:
            def extract_image(msg):
                if msg.attachments:
                    return msg.attachments[0].url
                if msg.embeds:
                    e = msg.embeds[0]
                    return getattr(e.image or e.thumbnail, "url", None)
                return None

            msg = ctx.message
            if not image_url:
                image_url = extract_image(msg)
                if not image_url and msg.reference:
                    ref = await ctx.channel.fetch_message(msg.reference.message_id)
                    image_url = extract_image(ref)
                    if not image_url and ref.reference:
                        ref2 = await ctx.channel.fetch_message(ref.reference.message_id)
                        image_url = extract_image(ref2)
            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")
            await self.process_spawn(msg, image_url)
        except Exception as e:
            logger.error(f"Prediction error: {type(e).__name__}: {e}")
            await ctx.send(f"{self.error_emoji} Failed to process prediction.")

    # --- command to generate all missing spawn images (conservative, sequential by default) ---
    @commands.command(name="generate_spawns", hidden=True)
    async def generate_all_spawn_images(self, ctx):
        os.makedirs(self.spawn_dir, exist_ok=True)
        missing = [slug for slug in self._pokemon_ids if not os.path.exists(os.path.join(self.spawn_dir, f"{slug}.png"))]
        if not missing:
            return await ctx.send("✅ All spawn images preloaded!")
        await ctx.send(f"⚠️ Preloading {len(missing)} Pokémon images...")

        loop = asyncio.get_running_loop()
        # conservative sequential generation to avoid bursts
        for slug in missing:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            try:
                await loop.run_in_executor(
                    THREAD_EXECUTOR,
                    self.image_builder.create_image,
                    slug,
                    self.pokemon_utils.format_name(slug).replace("_", " ").title(),
                    self.alt_cache.get(slug, ""),
                    self.type_cache.get(slug, []),
                    None,
                    path,
                    "PNG"
                )
                self.file_cache[slug] = path
            except Exception as e:
                logger.error(f"Failed generating {slug}: {e}")
            # yield to event loop to avoid hogging memory/CPU
            await asyncio.sleep(0)
        await ctx.send("✅ All spawn images generated, cached, and verified!")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
