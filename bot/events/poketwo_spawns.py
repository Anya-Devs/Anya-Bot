from functools import partial, lru_cache
from collections import OrderedDict
import os
import gc
import json
import asyncio
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import psutil  # For cross-platform RAM monitoring
import io

from motor.motor_asyncio import AsyncIOMotorClient
import aiohttp
import aiofiles
import cloudinary
import cloudinary.uploader
import requests

from imports.discord_imports import *
from bot.token import use_test_bot as ut
from bot.cogs.pokemon import PoketwoCommands
from utils.subcogs.pokemon import MongoHelper
from submodules.poketwo_autonamer.predict import Prediction
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView

import resource
import random
import time
import weakref

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

class PoketwoSpawnDetector(commands.Cog):
    """
    A Discord Cog for detecting and processing Pokétwo spawns.
    Handles image prediction, caching, pinging, and image generation/uploading.
    Optimized for low latency, minimal RAM footprint, and benchmark-grade performance.
    """

    TARGET_BOT_ID = 716390085896962058
    MAX_DYNAMIC_CACHE_SIZE = 200  # Further reduced for tighter RAM control
    MAX_STATIC_CACHE_SIZE = 2000  # Reduced to balance preload vs. RAM
    WORKER_COUNT = 1  # Reduced to minimize context switching overhead
    BATCH_SIZE = 3  # Smaller batches for lower latency
    PERIODIC_SAVE_INTERVAL = 120  # Less frequent saves to reduce I/O
    SPAM_WINDOW_SECONDS = 60
    SPAM_THRESHOLD = 50  # Lower threshold for quicker spam detection
    SPAWN_DIR = "data/events/poketwo_spawns/spawns"
    IMAGE_URLS_PATH = "data/events/poketwo_spawns/image_urls.json"
    CONFIG_PATH = "data/events/poketwo_spawns/image/config.json"
    SUCCESS_EMOJI = "<:green:1261639410181476443>"
    ERROR_EMOJI = "<:red:1261639413943762944>"
    CROSS_EMOJI = "❌"
    TEST_SPAWN_URLS = [
        "https://i.redd.it/4x0qmnu2y4571.png",
        "https://i.redd.it/pls6rcr2gb591.jpg",
        "https://i.redd.it/kutqoamhevl61.jpg",
        "https://pbs.twimg.com/media/Ep1myBdXMAEtOqJ.jpg",
        "https://i.redd.it/zeffm59rxqx51.jpg",
        "https://i.ytimg.com/vi/wHp2uMBgqx8/maxresdefault.jpg",
        "https://i.ytimg.com/vi/L2Bd0BGBkOw/maxresdefault.jpg",
    ]

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.predictor = None  # Lazy load with weakref for auto-unload
        self.predictor_ref = None
        self.pp = PoketwoCommands(bot)
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.pokemon_utils = PokemonUtils(
            self.mongo,
            type_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_types.json",
            quest_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_quest.json",
            description_file="data/commands/pokemon/pokemon_description.csv",
            id_file="data/commands/pokemon/pokemon_names.csv",
            regional_forms={
                "alola": "Alolan", "galar": "Galarian", "hisui": "Hisuian",
                "paldea": "Paldean", "unova": "Unovan",
            },
            lang_flags={"ja": "🇯🇵", "de": "🇩🇪", "fr": "🇫🇷", "en": "🇺🇸"},
            bot=bot,
            pp=self.pp,
        )
        self.full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()
        self.image_builder = PokemonImageBuilder()
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()

        # Optimized caches: Smaller LRU, weakref for static to allow GC
        self.pred_cache = lru_cache(maxsize=self.MAX_DYNAMIC_CACHE_SIZE)(self._predict_pokemon)
        self.base_cache = lru_cache(maxsize=self.MAX_DYNAMIC_CACHE_SIZE)(self._get_base_name)
        self.server_config_cache = OrderedDict()  # Manual LRU for configs
        self.desc_cache = weakref.WeakValueDictionary()  # Weak for auto-eviction
        self.type_cache = weakref.WeakValueDictionary()
        self.alt_cache = weakref.WeakValueDictionary()
        self.image_url_cache = OrderedDict()  # Manual with size limit
        self.test_images = None
        self.channel_stats = weakref.WeakValueDictionary()  # Weak for auto-cleanup

        # Benchmark metrics
        self.metrics = {
            'pred_times': [],
            'image_times': [],
            'overall_times': [],
            'ram_peaks': [],
            'processed_count': 0
        }
        self.metrics_lock = asyncio.Lock()

        self.default_ext = self._get_default_ext()
        self.queue = asyncio.Queue(maxsize=20)  # Smaller queue to prevent backlog
        self.thread_executor = ThreadPoolExecutor(max_workers=self.WORKER_COUNT, thread_name_prefix="spawn-thread")
        self.process_executor = ProcessPoolExecutor(max_workers=self.WORKER_COUNT, mp_context='forkserver')  # Forkserver for lower overhead
        self.last_gc = time.time()

        cloudinary.config(
            cloudinary_url=os.getenv("CLOUDINARY_URL")  # Use URL for faster config
        )

        self.dirty = False
        self.testing = False
        self._preload_static_caches()
        self._load_image_urls()

        # Start optimized workers and tasks
        self.bot.loop.create_task(self._start_workers_and_saver())
        self.bot.loop.create_task(self._periodic_cleanup())
        self.bot.loop.create_task(self._periodic_metrics_flush())

    def _get_ram_usage(self) -> float:
        """Cross-platform RAM in MB."""
        try:
            return psutil.Process().memory_info().rss / 1024 / 1024
        except:
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    async def _lazy_load_predictor(self):
        if self.predictor is None:
            start = time.time()
            self.predictor = Prediction()
            self.predictor_ref = weakref.ref(self.predictor)
            load_time = time.time() - start
            logger.info(f"Model loaded in {load_time:.2f}s")

    async def _start_workers_and_saver(self):
        for _ in range(self.WORKER_COUNT):
            self.bot.loop.create_task(self._worker())
        self.bot.loop.create_task(self._periodic_save())

    async def _periodic_cleanup(self):
        while True:
            await asyncio.sleep(180)  # 3 min for balanced cleanup
            now = time.time()
            # Manual cleanup for OrderedDicts
            while len(self.server_config_cache) > self.MAX_DYNAMIC_CACHE_SIZE:
                self.server_config_cache.popitem(last=False)
            while len(self.image_url_cache) > self.MAX_STATIC_CACHE_SIZE:
                self.image_url_cache.popitem(last=False)
            # Conditional GC: only if idle
            if time.time() - self.last_gc > 60:
                gc.collect(2)  # Generational GC
                self.last_gc = time.time()
            logger.debug("Periodic cleanup executed")

    async def _periodic_metrics_flush(self):
        """Flush metrics to log every 100 processes for benchmarking."""
        while True:
            await asyncio.sleep(60)
            async with self.metrics_lock:
                if self.metrics['processed_count'] > 0:
                    pred_avg = sum(self.metrics['pred_times']) / len(self.metrics['pred_times'])
                    image_avg = sum(self.metrics['image_times']) / len(self.metrics['image_times'])
                    overall_avg = sum(self.metrics['overall_times']) / len(self.metrics['overall_times'])
                    ram_avg = sum(self.metrics['ram_peaks']) / len(self.metrics['ram_peaks'])
                    logger.info(
                        f"Benchmark Flush: Processed {self.metrics['processed_count']} | "
                        f"Avg Pred: {pred_avg:.3f}s | Avg Image: {image_avg:.3f}s | "
                        f"Avg Overall: {overall_avg:.3f}s | Avg RAM Peak: {ram_avg:.1f}MB"
                    )
                    # Reset for next interval
                    self.metrics = {
                        'pred_times': [], 'image_times': [], 'overall_times': [], 'ram_peaks': [], 'processed_count': 0
                    }

    def _get_default_ext(self) -> str:
        try:
            with open(self.CONFIG_PATH, "rb") as f:  # Binary read for speed
                cfg = json.loads(f.read())
                url = (cfg.get("background_url", "") or "").lower()
                return "gif" if url.endswith(".gif") else "png"
        except Exception:
            return "png"

    def _preload_static_caches(self) -> None:
        """Preload with weakrefs for RAM efficiency."""
        for name in list(self._pokemon_ids.keys())[:self.MAX_STATIC_CACHE_SIZE]:  # Limit preload
            name_lower = name.lower()
            desc_data = self.pokemon_utils.get_description(name_lower) or ("", "???")
            self.desc_cache[name_lower] = desc_data
            types = self.pokemon_utils.get_pokemon_types(name_lower)
            self.type_cache[name_lower] = types
            alt = self.pokemon_utils.get_best_normal_alt_name(name_lower) or ""
            self.alt_cache[name_lower] = alt
        logger.info(f"Preloaded {len(self.desc_cache)} static cache entries")

    def _load_image_urls(self) -> None:
        if os.path.exists(self.IMAGE_URLS_PATH):
            try:
                with open(self.IMAGE_URLS_PATH, "rb") as f:
                    data = json.loads(f.read())
                    if isinstance(data, dict):
                        self.image_url_cache = OrderedDict((k.lower(), v) for k, v in list(data.items())[:self.MAX_STATIC_CACHE_SIZE])
            except Exception as e:
                logger.error(f"Failed to load image URLs: {e}")

    def _get_image_url(self, base_name: str) -> str | None:
        return self.image_url_cache.get(base_name.lower())

    def _add_image_url(self, base_name: str, url: str) -> None:
        base_name_lower = base_name.lower()
        self.image_url_cache[base_name_lower] = url
        if len(self.image_url_cache) > self.MAX_STATIC_CACHE_SIZE:
            self.image_url_cache.popitem(last=False)
        self.dirty = True

    async def _periodic_save(self) -> None:
        while True:
            await asyncio.sleep(self.PERIODIC_SAVE_INTERVAL)
            if self.dirty:
                await self._save_image_urls()
                self.dirty = False

    async def _save_image_urls(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.IMAGE_URLS_PATH), exist_ok=True)
            data = dict(list(self.image_url_cache.items())[:self.MAX_STATIC_CACHE_SIZE])
            async with aiofiles.open(self.IMAGE_URLS_PATH, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, separators=(',', ':'), ensure_ascii=False))  # Compact JSON for speed
        except Exception as e:
            logger.warning(f"Failed to save image URLs: {e}")

    async def _worker(self) -> None:
        while True:
            try:
                message, image_url = await self.queue.get()
                try:
                    await self._process_spawn(message, image_url)
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
                await asyncio.sleep(0.1)

    async def _process_spawn(self, message: discord.Message, image_url: str) -> None:
        overall_start = time.time()
        ram_start = self._get_ram_usage()
        try:
            await self._lazy_load_predictor()
            pred_start = time.time()
            raw_name, conf = self.pred_cache(image_url)
            pred_end = time.time()
            pred_time = pred_end - pred_start

            base = self.base_cache(raw_name)
            base_name = base.lower()
            conf_float = self._parse_confidence(conf)
            low_conf = conf_float < 30.0

            if message.guild is None:
                return

            sid = message.guild.id
            server_config = await self._get_server_config(sid)

            # Use get with default to avoid KeyError
            desc_data = self.desc_cache.get(base_name, ("", "???"))
            desc, dex = desc_data[:2]
            dex = self._pokemon_ids.get(base_name, dex)

            # Always fetch pings live
            shiny_collect, type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_ping_users(message.guild, base_name),
                self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
            )

            shiny_pings, collect_pings = shiny_collect

            rare, regional = getattr(self.pokemon_utils, "_special_names", ([], []))
            special_roles = self._get_special_roles(server_config, base_name, rare, regional)

            ping_msg, embed_data = await self.pokemon_utils.format_messages(
                raw_name, type_pings, quest_pings, shiny_pings, collect_pings,
                " ".join(special_roles), f"{conf_float:.2f}%", dex, desc,
                image_url, low_conf
            )

            view = PokemonSpawnView(
                slug=base_name,
                pokemon_data=self.full_pokemon_data,
                pokemon_utils=self.pokemon_utils
            )

            image_start = time.time()
            url = self._get_image_url(base_name) or await self._handle_image_upload(base_name)
            image_end = time.time()
            image_time = image_end - image_start

            if not self.testing:
                # Download and attach image as file instead of embed
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            img_data = await resp.read()
                            filename = f"prediction.{self.default_ext}"
                            file = discord.File(io.BytesIO(img_data), filename=filename)
                            await message.channel.send(
                                content=ping_msg,
                                file=file,
                                reference=message,
                                view=view
                            )
                        else:
                            # Fallback to no file if download fails
                            await message.channel.send(
                                content=ping_msg,
                                reference=message,
                                view=view
                            )
            else:
                logger.info(f"Test spawn: {base_name}")

            # Update metrics
            ram_peak = self._get_ram_usage()
            overall_end = time.time()
            overall_time = overall_end - overall_start
            async with self.metrics_lock:
                self.metrics['pred_times'].append(pred_time)
                self.metrics['image_times'].append(image_time)
                self.metrics['overall_times'].append(overall_time)
                self.metrics['ram_peaks'].append(ram_peak - ram_start)
                self.metrics['processed_count'] += 1

                # Trim metrics lists to prevent RAM bloat (keep last 100)
                for key in ['pred_times', 'image_times', 'overall_times', 'ram_peaks']:
                    if len(self.metrics[key]) > 100:
                        self.metrics[key] = self.metrics[key][-100:]

            # Log per-process benchmark
            logger.info(
                f"Spawn Benchmark - Pred: {pred_time:.3f}s | Image: {image_time:.3f}s | "
                f"Overall: {overall_time:.3f}s | RAM Δ: {ram_peak - ram_start:.1f}MB"
            )

        except MemoryError:
            self._handle_memory_error(message)
        except Exception as e:
            self._handle_processing_error(message, e)
        
    def _parse_confidence(self, conf: str) -> float:
        try:
            return float(str(conf).strip().rstrip("%"))
        except ValueError:
            return 0.0

    def _get_special_roles(self, server_config: dict, base_name: str, rare: list, regional: list) -> list:
        if not server_config:
            return []
        roles = []
        if server_config.get("rare_role"):
            for r in rare:
                if r in base_name:
                    roles.append(f"<@&{server_config['rare_role']}>")
                    break  # Only once per type
        if server_config.get("regional_role"):
            for r in regional:
                if r in base_name:
                    roles.append(f"<@&{server_config['regional_role']}>")
                    break
        return roles

    def _handle_memory_error(self, message: discord.Message) -> None:
        logger.error("MemoryError: Emergency cache clear")
        self.pred_cache.cache_clear()
        self.base_cache.cache_clear()
        if self.predictor_ref and self.predictor_ref() is not None:
            del self.predictor
            self.predictor = None
            self.predictor_ref = None
        # Clear OrderedDicts aggressively
        self.server_config_cache.clear()
        gc.collect(2)
        try:
            asyncio.create_task(message.channel.send(f"{self.ERROR_EMOJI} Memory cleared", reference=message))
        except:
            pass

    def _handle_processing_error(self, message: discord.Message, e: Exception) -> None:
        logger.error(f"Processing error: {type(e).__name__}: {e}")
        try:
            asyncio.create_task(message.channel.send(f"{self.ERROR_EMOJI} Processing failed", reference=message))
        except:
            pass

    def _predict_pokemon(self, image_url: str) -> tuple[str, str]:
        if not image_url.startswith(('http://', 'https://')):
            # Local mock for speed
            original_get = requests.get
            def mock_get(*args, **kwargs):
                with open(image_url, 'rb') as f:
                    content = f.read()
                class MockResponse:
                    status_code = 200
                    content = content
                    headers = {'Content-Type': 'image/jpeg'}
                return MockResponse()
            requests.get = mock_get
            try:
                return self.predictor.predict(image_url)
            finally:
                requests.get = original_get
        else:
            return self.predictor.predict(image_url)

    def _get_base_name(self, raw_name: str) -> str:
        base = self.pokemon_utils.get_base_pokemon_name(raw_name)
        if base not in self._pokemon_ids:
            full = self.pokemon_utils.find_full_name_for_slug(raw_name)
            if full:
                base = full.lower().replace("_", "-")
        return base

    async def _get_server_config(self, sid: int) -> dict:
        if sid in self.server_config_cache:
            self.server_config_cache.move_to_end(sid)
            return self.server_config_cache[sid]
        config = await self.pokemon_utils.get_server_config(sid)
        self.server_config_cache[sid] = config or {}
        if len(self.server_config_cache) > self.MAX_DYNAMIC_CACHE_SIZE:
            self.server_config_cache.popitem(last=False)
        return self.server_config_cache[sid]

    async def _handle_image_upload(self, base_name: str) -> str | None:
        ext = self.default_ext
        local_path = os.path.join(self.SPAWN_DIR, f"{base_name}.{ext}")
        if os.path.exists(local_path):
            url = await self._upload_local_image(local_path, base_name)
            if url:
                return url
        return await self._generate_and_upload_image(base_name, ext)

    async def _upload_local_image(self, local_path: str, base_name: str) -> str | None:
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                self.thread_executor,
                partial(
                    cloudinary.uploader.upload,
                    local_path,
                    folder="poketwo_spawns",
                    public_id=base_name,
                    overwrite=True,
                    resource_type="image"
                )
            )
            url = resp.get("secure_url")
            if url:
                self._add_image_url(base_name, url)
            return url
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return None

    async def _generate_and_upload_image(self, base_name: str, ext: str) -> str | None:
        temp_path = self._get_temp_path(base_name, ext)
        try:
            alt = self.alt_cache.get(base_name.lower())
            types = self.type_cache.get(base_name.lower())
            name = self.pokemon_utils.format_name(base_name).replace("_", " ").title()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.process_executor,
                partial(self.image_builder.create_image, base_name, name, alt or "", types or [], None, temp_path, ext.upper())
            )
            resp = await loop.run_in_executor(
                self.thread_executor,
                partial(
                    cloudinary.uploader.upload,
                    temp_path,
                    folder="poketwo_spawns",
                    public_id=base_name,
                    overwrite=True,
                    resource_type="image"
                )
            )
            url = resp.get("secure_url")
            if url:
                self._add_image_url(base_name, url)
            return url
        except Exception as e:
            logger.error(f"Generate/upload failed: {e}")
            return None
        finally:
            self._cleanup_temp_file(temp_path)

    @staticmethod
    def _get_temp_path(base_name: str, ext: str) -> str:
        tmp_dir = "/tmp" if os.name != "nt" else os.getcwd()
        return os.path.join(tmp_dir, f"{base_name}.{ext}")

    @staticmethod
    def _cleanup_temp_file(temp_path: str) -> None:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.id != self.TARGET_BOT_ID or ut:
            return

        # Optimized spam check with weakref
        cid = message.channel.id
        now = time.time()
        stats = self.channel_stats.get(cid)
        if stats is None:
            stats = {'count': 0, 'window_start': now, 'ignored': False}
            self.channel_stats[cid] = stats

        if now - stats['window_start'] > self.SPAM_WINDOW_SECONDS:
            stats['count'] = 1
            stats['window_start'] = now
        else:
            stats['count'] += 1

        if stats['count'] > self.SPAM_THRESHOLD:
            stats['ignored'] = True
            logger.warning(f"Spam channel {cid} ignored")
            return

        if stats['ignored']:
            return

        for embed in message.embeds:
            title = embed.title
            if title and "pokémon has appeared!" in title.lower() and embed.image:
                img_url = embed.image.url
                if img_url:
                    try:
                        await self.queue.put((message, img_url), timeout=0.1)
                    except asyncio.QueueFull:
                        logger.debug("Queue full, dropping")

    @commands.command(name="ps", hidden=True)
    @commands.is_owner()
    async def predict_spawn(self, ctx: commands.Context, image_url: str | None = None) -> None:
        image_url = image_url or await self._extract_image_url(ctx)
        if not image_url:
            return await ctx.send(f"{self.CROSS_EMOJI} No image.")
        await self._process_spawn(ctx.message, image_url)

    async def _extract_image_url(self, ctx: commands.Context) -> str | None:
        message = ctx.message
        url = self._extract_from_message(message)
        if url:
            return url
        if message.reference:
            try:
                ref = await ctx.fetch_message(message.reference.message_id)
                url = self._extract_from_message(ref)
                if url:
                    return url
                if ref.reference:
                    ref2 = await ctx.fetch_message(ref.reference.message_id)
                    return self._extract_from_message(ref2)
            except:
                pass
        return None

    @staticmethod
    def _extract_from_message(msg: discord.Message) -> str | None:
        if msg.attachments:
            return msg.attachments[0].url
        if msg.embeds:
            emb = msg.embeds[0]
            return emb.image.url if emb.image else (emb.thumbnail.url if emb.thumbnail else None)
        return None

    @commands.command(name="generate_spawns", hidden=True)
    @commands.is_owner()
    async def generate_spawns(self, ctx: commands.Context) -> None:
        await self._handle_spawn_images(ctx, regenerate=False)

    @commands.command(name="regenerate_spawns", hidden=True)
    @commands.is_owner()
    async def regenerate_spawns(self, ctx: commands.Context) -> None:
        await self._handle_spawn_images(ctx, regenerate=True)

    async def _handle_spawn_images(self, ctx: commands.Context, regenerate: bool = False) -> None:
        await ctx.defer()
        try:
            import csv
            async with aiofiles.open(self.pokemon_utils.description_file, "r", encoding="utf-8") as f:
                data = await f.read()
            reader = list(csv.DictReader(data.splitlines()))
            slugs_to_process = [
                slug.strip().lower()
                for row in reader
                if (slug := (row.get("slug") or row.get("name") or "")).strip().lower()
                and (regenerate or not self._get_image_url(slug))
            ][:self.MAX_STATIC_CACHE_SIZE]

            if not slugs_to_process:
                msg = "❌ No items." if regenerate else "✅ All cached."
                return await ctx.send(msg)

            success_count = error_count = 0
            sem = asyncio.Semaphore(self.BATCH_SIZE)  # Semaphore for concurrency limit

            async def process_slug(slug: str):
                async with sem:
                    url = await self._handle_image_upload(slug)
                    return bool(url)

            tasks = [process_slug(slug) for slug in slugs_to_process]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if isinstance(r, bool) and r)
            error_count = len(results) - success_count

            action = "Regenerated" if regenerate else "Generated"
            await ctx.send(f"✅ {action} {success_count}. ❌ {error_count} failed.")
        except Exception as e:
            await ctx.send(f"{self.ERROR_EMOJI} Error: {e}")

    async def _pressure_loop(self, ctx: commands.Context, period: int) -> None:
        initial_ram = self._get_ram_usage()
        logger.info(f"Pressure start RAM: {initial_ram:.1f}MB")
        i = 0
        delay_max = 0.5  # Start faster
        start_time = time.time()

        while self.testing:
            if not self.test_images:
                await asyncio.sleep(0.1)
                continue
            url = random.choice(self.test_images)
            message = ctx.message
            try:
                self.queue.put_nowait((message, url))
            except asyncio.QueueFull:
                await asyncio.sleep(0.01)
                continue

            await asyncio.sleep(random.uniform(0, delay_max))
            i += 1
            if i % 20 == 0:  # Faster ramp-up
                delay_max = max(0.005, delay_max * 0.95)

            if i % period == 0:
                current_ram = self._get_ram_usage()
                elapsed = time.time() - start_time
                logger.info(
                    f"After {i} spawns ({elapsed:.1f}s), RAM: {current_ram:.1f}MB (+{current_ram - initial_ram:.1f}MB), "
                    f"delay: {delay_max:.3f}s"
                )

    @commands.command(name="pressure_test", hidden=True)
    @commands.is_owner()
    async def pressure_test(self, ctx: commands.Context, period: int = 10) -> None:
        if self.testing:
            return await ctx.send("Already running.")
        
        # Prepare test images locally for zero-latency
        if self.test_images is None:
            self.test_images = []
            connector = aiohttp.TCPConnector(limit=5, limit_per_host=5)
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                for i, url in enumerate(self.TEST_SPAWN_URLS):
                    try:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                content = await resp.read()
                                path = f"/tmp/spawn_test_{i}.jpg" if os.name != "nt" else f"spawn_test_{i}.jpg"
                                async with aiofiles.open(path, 'wb') as f:
                                    await f.write(content)
                                self.test_images.append(path)
                    except:
                        pass
            logger.info(f"Prepared {len(self.test_images)} test images")
        
        if not self.test_images:
            return await ctx.send("Failed to prepare images.")
        
        self.testing = True
        await ctx.send(f"Pressure test: {ctx.prefix}stop_pressure to stop. Logs for benchmarks.")
        self.pressure_task = self.bot.loop.create_task(self._pressure_loop(ctx, period))

    @commands.command(name="stop_pressure", hidden=True)
    @commands.is_owner()
    async def stop_pressure(self, ctx: commands.Context) -> None:
        if not self.testing:
            return await ctx.send("Not running.")
        
        self.testing = False
        if hasattr(self, 'pressure_task'):
            await self.pressure_task
        final_ram = self._get_ram_usage()
        logger.info(f"Pressure end RAM: {final_ram:.1f}MB")
        await ctx.send("Stopped. Check logs.")

    def cog_unload(self) -> None:
        self.testing = False
        if self.test_images:
            for path in self.test_images:
                self._cleanup_temp_file(path)
        self.thread_executor.shutdown(wait=False, cancel_futures=True)
        self.process_executor.shutdown(wait=False, cancel_futures=True)
        if self.dirty:
            self.bot.loop.run_until_complete(self._save_image_urls())
        # Final metrics
        async def final_flush():
            async with self.metrics_lock:
                if self.metrics['processed_count'] > 0:
                    logger.info(f"Final Benchmark: {self.metrics['processed_count']} processed")
        self.bot.loop.run_until_complete(final_flush())

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PoketwoSpawnDetector(bot))
