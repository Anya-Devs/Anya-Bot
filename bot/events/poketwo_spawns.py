from functools import partial, lru_cache
from collections import OrderedDict
import os
import gc
import json
import asyncio
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor

from motor.motor_asyncio import AsyncIOMotorClient
import aiohttp
import aiofiles
import cloudinary
import cloudinary.uploader
import requests
import psutil  # For accurate RAM monitoring; assume installed or add if needed

from imports.discord_imports import *
from bot.token import use_test_bot as ut
from bot.cogs.pokemon import PoketwoCommands
from utils.subcogs.pokemon import MongoHelper
from submodules.poketwo_autonamer.predict import Prediction
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView

import resource
import random
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

class PoketwoSpawnDetector(commands.Cog):
    """
    A Discord Cog for detecting and processing Pokétwo spawns.
    Handles image prediction, caching, pinging, and image generation/uploading.
    Optimized for extreme memory efficiency: sequential processing, lazy loading,
    no in-memory attachments, aggressive GC, and RAM monitoring.
    """

    TARGET_BOT_ID = 716390085896962058
    MAX_DYNAMIC_CACHE_SIZE = 100  # Drastically reduced for safety
    MAX_STATIC_CACHE_SIZE = 10000
    MAX_PING_CACHE_SIZE = 50  # Smaller to limit user list bloat
    WORKER_COUNT = 1  # Sequential: only one worker
    BATCH_SIZE = 1  # Sequential generation
    PERIODIC_SAVE_INTERVAL = 30  # seconds
    SPAM_WINDOW_SECONDS = 60
    SPAM_THRESHOLD = 50  # messages per window
    SPAWN_DIR = "data/events/poketwo_spawns/spawns"
    IMAGE_URLS_PATH = "data/events/poketwo_spawns/image_urls.json"
    CONFIG_PATH = "data/events/poketwo_spawns/image/config.json"
    SUCCESS_EMOJI = "<:green:1261639410181476443>"
    ERROR_EMOJI = "<:red:1261639413943762944>"
    CROSS_EMOJI = "❌"
    RAM_THRESHOLD_MB = 400  # Alert/GC if approaching 512 MB limit
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
        self.predictor = None  # Lazy load heavy model
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
        self.full_pokemon_data = None  # Lazy load
        self.image_builder = PokemonImageBuilder()
        self._pokemon_ids = None  # Lazy load

        # Caches: Smaller LRU, manual eviction where possible
        self.pred_cache = lru_cache(maxsize=self.MAX_DYNAMIC_CACHE_SIZE)(self._predict_pokemon)
        self.base_cache = lru_cache(maxsize=self.MAX_DYNAMIC_CACHE_SIZE)(self._get_base_name)
        self.server_config_cache = OrderedDict()
        self.ping_cache = OrderedDict()  # (guild_id, base_name): (shiny_collect, type_pings, quest_pings)
        self.desc_cache = {}  # Compute on fly, small cache
        self.type_cache = {}
        self.alt_cache = {}
        self.image_url_cache = OrderedDict()  # URLs are lightweight
        self.test_images = None
        self.channel_stats = {}  # channel_id: {'count': int, 'window_start': float, 'ignored': bool}

        self.default_ext = self._get_default_ext()
        self.queue = asyncio.Queue(maxsize=1)  # Only one at a time
        self.thread_executor = ThreadPoolExecutor(max_workers=1)  # Sequential even for threads
        self.processed_count = 0

        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )

        self.dirty = False
        self.testing = False
        self._load_image_urls()

        # Start single worker, saver, cleanup, and RAM monitor
        self.bot.loop.create_task(self._start_workers_and_saver())
        self.bot.loop.create_task(self._periodic_cleanup())
        self.bot.loop.create_task(self._ram_monitor())

    def _get_ram_mb(self) -> float:
        """Get current RAM usage in MB."""
        try:
            return psutil.Process().memory_info().rss / 1024 / 1024
        except:
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    async def _ram_monitor(self):
        """Periodic RAM check: GC and clear caches if high."""
        while True:
            await asyncio.sleep(30)  # Every 30s
            ram = self._get_ram_mb()
            if ram > self.RAM_THRESHOLD_MB:
                logger.warning(f"High RAM usage ({ram:.1f} MB): Aggressive cleanup")
                self._aggressive_cleanup()
                gc.collect()

    def _aggressive_cleanup(self):
        """Clear all dynamic caches and force GC."""
        self.pred_cache.cache_clear()
        self.base_cache.cache_clear()
        self.server_config_cache.clear()
        self.ping_cache.clear()
        # Keep static caches small
        if len(self.desc_cache) > 50:
            self.desc_cache.clear()
        if len(self.type_cache) > 50:
            self.type_cache.clear()
        if len(self.alt_cache) > 50:
            self.alt_cache.clear()

    async def _start_workers_and_saver(self):
        self.bot.loop.create_task(self._worker())  # Only one
        self.bot.loop.create_task(self._periodic_save())

    async def _periodic_cleanup(self):
        while True:
            await asyncio.sleep(600)  # Every 10 minutes
            now = time.time()
            to_remove = [cid for cid, stats in self.channel_stats.items() if now - stats['window_start'] > 1800]  # 30 min inactive
            for cid in to_remove:
                del self.channel_stats[cid]
            # Also trim channel_stats if too many
            if len(self.channel_stats) > 100:
                # Keep recent/active
                recent = {cid: stats for cid, stats in self.channel_stats.items() if now - stats['window_start'] < 3600}
                self.channel_stats.clear()
                self.channel_stats.update(recent)
            logger.debug(f"Cleaned up {len(to_remove)} inactive channel stats; total now {len(self.channel_stats)}")

    def _get_default_ext(self) -> str:
        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                url = (cfg.get("background_url", "") or "").lower()
                return "gif" if url.endswith(".gif") else "png"
        except Exception:
            logger.warning("Failed to read config.json, defaulting to PNG")
            return "png"

    def _lazy_load_pokemon_data(self):
        if self._pokemon_ids is None:
            self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        if self.full_pokemon_data is None:
            self.full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()

    def _load_image_urls(self) -> None:
        if os.path.exists(self.IMAGE_URLS_PATH):
            try:
                with open(self.IMAGE_URLS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.image_url_cache = OrderedDict((k.lower(), v) for k, v in data.items())
                        # Trim if too large (though URLs are cheap)
                        while len(self.image_url_cache) > self.MAX_STATIC_CACHE_SIZE:
                            self.image_url_cache.popitem(last=False)
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
            if self.dirty:
                await self._save_image_urls()
                self.dirty = False
            await asyncio.sleep(self.PERIODIC_SAVE_INTERVAL)

    async def _save_image_urls(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.IMAGE_URLS_PATH), exist_ok=True)
            data = json.dumps(dict(self.image_url_cache), indent=2, ensure_ascii=False)
            async with aiofiles.open(self.IMAGE_URLS_PATH, "w", encoding="utf-8") as f:
                await f.write(data)
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
                    # Immediate GC after each process
                    gc.collect()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue get error: {type(e).__name__}: {e}")
                traceback.print_exc()
                await asyncio.sleep(1)
                gc.collect()

    async def _process_spawn(self, message: discord.Message, image_url: str) -> None:
        overall_start = time.time()
        try:
            # RAM check before heavy ops
            if self._get_ram_mb() > self.RAM_THRESHOLD_MB * 0.8:
                self._aggressive_cleanup()
                gc.collect()

            pred_start = time.time()
            raw_name, conf = self.pred_cache(image_url)
            pred_end = time.time()
            pred_time = pred_end - pred_start
            del image_url  # Free early

            base = self.base_cache(raw_name)
            base_name = base.lower()
            conf_float = self._parse_confidence(conf)
            low_conf = conf_float < 30.0
            del raw_name, conf  # Free

            if message.guild is None:
                logger.warning("Spawn message without guild; skipping.")
                return

            sid = message.guild.id
            server_config = await self.server_cache(sid)

            self._lazy_load_pokemon_data()
            desc_data = self._get_description(base_name)
            desc, dex = desc_data[:2]
            dex = self._pokemon_ids.get(base_name, dex)

            key = (sid, base_name)
            if key not in self.ping_cache:
                shiny_collect, type_pings, quest_pings = await asyncio.gather(
                    self.pokemon_utils.get_ping_users(message.guild, base_name),
                    self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                    self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
                )
                self.ping_cache[key] = (shiny_collect, type_pings, quest_pings)
                if len(self.ping_cache) > self.MAX_PING_CACHE_SIZE:
                    self.ping_cache.popitem(last=False)
                # Free large lists early if possible, but needed below
            else:
                shiny_collect, type_pings, quest_pings = self.ping_cache[key]

            shiny_pings, collect_pings = shiny_collect

            rare, regional = getattr(self.pokemon_utils, "_special_names", ([], []))
            special_roles = self._get_special_roles(server_config, base_name, rare, regional)

            ping_msg, _ = await self.pokemon_utils.format_messages(
                base_name.title(), type_pings, quest_pings, shiny_pings, collect_pings,  # Use base_name
                " ".join(special_roles), f"{conf_float:.2f}%", dex, desc,
                "", low_conf  # No spawn image_url needed
            )
            # Free pings after formatting
            del type_pings, quest_pings, shiny_pings, collect_pings, shiny_collect

            view = PokemonSpawnView(
                slug=base_name,
                pokemon_data=self.full_pokemon_data,  # Reference only
                pokemon_utils=self.pokemon_utils
            )

            image_start = time.time()
            url = self._get_image_url(base_name) or await self._handle_image_upload(base_name)
            image_end = time.time()
            image_time = image_end - image_start

            if not self.testing:
                if url:
                    # Send as embed image URL: NO DOWNLOAD, NO BYTESIO
                    embed = discord.Embed()
                    embed.set_image(url=url)
                    embed.description = ping_msg  # Or title/color as needed
                    await message.channel.send(embed=embed, reference=message, view=view)
                else:
                    await message.channel.send(content=ping_msg, reference=message, view=view)
            else:
                logger.info(f"Test spawn processed: {base_name} (skipped send)")

            self.processed_count += 1
            logger.debug(f"GC after {self.processed_count} processes")

            overall_end = time.time()
            overall_time = overall_end - overall_start

            logger.info(
                f"Spawn Processing Times - Prediction: {pred_time:.2f} seconds | "
                f"Image Preparation: {image_time:.2f} seconds | "
                f"Overall Response: {overall_time:.2f} seconds | RAM: {self._get_ram_mb():.1f} MB"
            )
        except MemoryError:
            self._handle_memory_error(message)
        except Exception as e:
            self._handle_processing_error(message, e)
        finally:
            # Final cleanup
            gc.collect()

    def _get_description(self, base_name: str):
        """Lazy compute description with small cache."""
        if base_name not in self.desc_cache:
            self._lazy_load_pokemon_data()
            desc_data = self.pokemon_utils.get_description(base_name) or ("", "???")
            self.desc_cache[base_name] = desc_data
            if len(self.desc_cache) > 50:  # Tiny cache
                # Evict oldest
                oldest = next(iter(self.desc_cache))
                del self.desc_cache[oldest]
        return self.desc_cache[base_name]

    def _get_types(self, base_name: str):
        """Lazy compute types with small cache."""
        if base_name not in self.type_cache:
            self._lazy_load_pokemon_data()
            types = self.pokemon_utils.get_pokemon_types(base_name)
            self.type_cache[base_name] = types
            if len(self.type_cache) > 50:
                oldest = next(iter(self.type_cache))
                del self.type_cache[oldest]
        return self.type_cache[base_name]

    def _get_alt(self, base_name: str):
        """Lazy compute alt with small cache."""
        if base_name not in self.alt_cache:
            self._lazy_load_pokemon_data()
            alt = self.pokemon_utils.get_best_normal_alt_name(base_name) or ""
            self.alt_cache[base_name] = alt
            if len(self.alt_cache) > 50:
                oldest = next(iter(self.alt_cache))
                del self.alt_cache[oldest]
        return self.alt_cache[base_name]

    def _parse_confidence(self, conf: str) -> float:
        try:
            return float(str(conf).strip().rstrip("%"))
        except ValueError:
            return 0.0

    def _get_special_roles(self, server_config: dict, base_name: str, rare: list, regional: list) -> list:
        if not server_config:
            return []
        return (
            [f"<@&{server_config['rare_role']}>" for r in rare if r in base_name and server_config.get("rare_role")]
            + [f"<@&{server_config['regional_role']}>" for r in regional if r in base_name and server_config.get("regional_role")]
        )

    def _handle_memory_error(self, message: discord.Message) -> None:
        logger.error("MemoryError: Aggressive cleanup")
        self._aggressive_cleanup()
        gc.collect()
        try:
            asyncio.create_task(message.channel.send(f"{self.ERROR_EMOJI} Memory issue, cleared caches", reference=message))
        except Exception:
            logger.exception("Failed to notify about memory error.")

    def _handle_processing_error(self, message: discord.Message, e: Exception) -> None:
        logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
        traceback.print_exc()
        self._aggressive_cleanup()
        gc.collect()
        try:
            asyncio.create_task(message.channel.send(f"{self.ERROR_EMOJI} Failed to process spawn", reference=message))
        except Exception:
            logger.exception("Failed to notify about spawn processing error.")

    def _predict_pokemon(self, image_url: str) -> tuple[str, str]:
        if self.predictor is None:
            self.predictor = Prediction()  # Lazy load once
        if not image_url.startswith(('http://', 'https://')):
            # Local file path
            original_get = requests.get
            def mock_get(url, *args, **kwargs):
                with open(image_url, 'rb') as f:
                    content = f.read()
                class MockResponse:
                    def __init__(self, content):
                        self.content = content
                return MockResponse(content)
            requests.get = mock_get
            try:
                return self.predictor.predict(image_url)
            finally:
                requests.get = original_get
        else:
            return self.predictor.predict(image_url)

    def _get_base_name(self, raw_name: str) -> str:
        self._lazy_load_pokemon_data()
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
        # RAM check before gen
        if self._get_ram_mb() > self.RAM_THRESHOLD_MB * 0.7:
            self._aggressive_cleanup()
            gc.collect()
        ext = self.default_ext
        local_path = os.path.join(self.SPAWN_DIR, f"{base_name}.{ext}")
        if os.path.exists(local_path):
            url = await self._upload_local_image(local_path, base_name)
            if url:
                return url
        # Generate and upload new image
        return await self._generate_and_upload_image(base_name, ext)

    async def _upload_local_image(self, local_path: str, base_name: str) -> str | None:
        try:
            resp = await self.bot.loop.run_in_executor(
                self.thread_executor,
                partial(
                    cloudinary.uploader.upload,
                    local_path,
                    folder="poketwo_spawns",
                    public_id=base_name,
                    overwrite=True
                )
            )
            url = resp.get("secure_url")
            if url:
                self._add_image_url(base_name, url)
            return url
        except Exception as e:
            logger.error(f"Local upload failed for {base_name}: {e}")
            return None

    async def _generate_and_upload_image(self, base_name: str, ext: str) -> str | None:
        temp_path = self._get_temp_path(base_name, ext)
        alt = self._get_alt(base_name)
        types = self._get_types(base_name)
        name = self.pokemon_utils.format_name(base_name).replace("_", " ").title()

        try:
            await self.bot.loop.run_in_executor(
                self.thread_executor,  # Single thread, no pool explosion
                self.image_builder.create_image,
                base_name, name, alt, types, None, temp_path, ext.upper()
            )
            resp = await self.bot.loop.run_in_executor(
                self.thread_executor,
                partial(
                    cloudinary.uploader.upload,
                    temp_path,
                    folder="poketwo_spawns",
                    public_id=base_name,
                    overwrite=True
                )
            )
            url = resp.get("secure_url")
            if url:
                self._add_image_url(base_name, url)
            self._cleanup_temp_file(temp_path)
            return url
        except Exception as e:
            logger.error(f"Image create/upload failed for {base_name}: {e}")
            self._cleanup_temp_file(temp_path)
            return None
        finally:
            gc.collect()  # After gen

    def _get_temp_path(self, base_name: str, ext: str) -> str:
        return os.path.join("/tmp" if os.name != "nt" else os.getcwd(), f"{base_name}.{ext}")

    def _cleanup_temp_file(self, temp_path: str) -> None:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                logger.debug("Failed to remove temp image", exc_info=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        cid = message.channel.id
        now = time.time()
        if cid not in self.channel_stats:
            self.channel_stats[cid] = {'count': 0, 'window_start': now, 'ignored': False}
        stats = self.channel_stats[cid]
        if now - stats['window_start'] > self.SPAM_WINDOW_SECONDS:
            stats['count'] = 1
            stats['window_start'] = now
        else:
            stats['count'] += 1
        if not stats['ignored'] and stats['count'] > self.SPAM_THRESHOLD:
            stats['ignored'] = True
            channel_name = message.channel.name if hasattr(message.channel, 'name') else 'Unknown'
            print(f"Marked high-volume channel {cid} ({channel_name}) as spam (rate: {stats['count']} msg/{self.SPAM_WINDOW_SECONDS}s), ignoring future messages.")
        if stats['ignored']:
            return

        if message.author.id != self.TARGET_BOT_ID or ut:
            return
        for embed in message.embeds:
            title = embed.title
            if title and "pokémon has appeared!" in title.lower() and embed.image:
                img_url = embed.image.url
                if img_url:
                    try:
                        await self.queue.put((message, img_url))
                    except asyncio.QueueFull:
                        logger.warning("Queue full, dropping spawn message")

    @commands.command(name="ps", hidden=True)
    @commands.is_owner()
    async def predict_spawn(self, ctx: commands.Context, image_url: str | None = None) -> None:
        image_url = image_url or await self._extract_image_url(ctx)
        if not image_url:
            return await ctx.send(f"{self.CROSS_EMOJI} No image URL found.")
        await self._process_spawn(ctx.message, image_url)

    async def _extract_image_url(self, ctx: commands.Context) -> str | None:
        message = ctx.message
        url = self._extract_from_message(message)
        if url:
            return url
        if message.reference:
            try:
                ref = await ctx.channel.fetch_message(message.reference.message_id)
                url = self._extract_from_message(ref)
                if url:
                    return url
                if ref.reference:
                    ref2 = await ctx.channel.fetch_message(ref.reference.message_id)
                    url = self._extract_from_message(ref2)
                    if url:
                        return url
            except Exception as e:
                logger.error(f"Failed fetching referenced message: {e}")
        return None

    def _extract_from_message(self, msg: discord.Message) -> str | None:
        if msg.attachments:
            return msg.attachments[0].url
        if msg.embeds:
            emb = msg.embeds[0]
            if emb.image and emb.image.url:
                return emb.image.url
            if emb.thumbnail and emb.thumbnail.url:
                return emb.thumbnail.url
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
            work_items = [
                (row["slug"].strip().lower(), regenerate or not self._get_image_url(row["slug"].strip().lower()))
                for row in reader if (slug := row.get("slug") or row.get("name") or "").strip().lower() and (regenerate or not self._get_image_url(slug))
            ]

            if not work_items:
                msg = "❌ No spawn items found." if regenerate else "✅ All spawn images already cached."
                return await ctx.send(msg)

            success_count = 0
            error_count = 0
            async def process_slug(slug: str):
                self._aggressive_cleanup()  # Clean before each
                gc.collect()
                url = await self._handle_image_upload(slug)
                gc.collect()  # After
                return bool(url)

            for item in work_items:  # Sequential, no batches
                slug, needs_process = item
                if needs_process:
                    result = await process_slug(slug)
                    if isinstance(result, bool):
                        if result:
                            success_count += 1
                        else:
                            error_count += 1
                    else:
                        error_count += 1
                    await asyncio.sleep(0.1)  # Tiny pause for stability

            action = "Regenerated" if regenerate else "Generated"
            await ctx.send(f"✅ {action} {success_count} spawn images. ❌ {error_count} failed.")
        except Exception as e:
            logger.error(f"Spawn image handler failure: {type(e).__name__}: {e}")
            await ctx.send(f"{self.ERROR_EMOJI} Error: {e}")

    async def _pressure_loop(self, ctx: commands.Context, period: int) -> None:
        def get_ram():
            return self._get_ram_mb()

        initial_ram = get_ram()
        logger.info(f"Initial RAM: {initial_ram} MB")

        i = 0
        delay = 2.0  # Fixed longer delay for sequential sim
        start_time = time.time()

        while self.testing:
            if self.queue.full():
                await asyncio.sleep(0.5)
                continue
            url = random.choice(self.test_images)
            message = ctx.message  # Simulate using the command's message
            try:
                self.queue.put_nowait((message, url))
            except asyncio.QueueFull:
                await asyncio.sleep(0.1)
                continue

            await asyncio.sleep(delay)  # Slow to mimic real, prevent queue buildup

            i += 1

            if i % period == 0:
                current_ram = get_ram()
                increase = current_ram - initial_ram
                elapsed = time.time() - start_time
                print(f"After {i} simulated spawns (elapsed {elapsed:.2f} seconds), RAM: {current_ram} MB, increase: {increase} MB")

    @commands.command(name="pressure_test", hidden=True)
    @commands.is_owner()
    async def pressure_test(self, ctx: commands.Context, period: int = 10) -> None:
        if self.testing:
            return await ctx.send("Pressure test already running.")
        
        # Download test images locally if not done
        if self.test_images is None:
            self.test_images = []
            for i, url in enumerate(self.TEST_SPAWN_URLS):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                content = await resp.read()
                                path = f"/tmp/spawn_test_{i}.jpg"
                                async with aiofiles.open(path, 'wb') as f:
                                    await f.write(content)
                                self.test_images.append(path)
                    logger.info(f"Downloaded test image {i}")
                except Exception as e:
                    logger.error(f"Failed to download {url}: {e}")
        
        if not self.test_images:
            return await ctx.send("Failed to prepare test images.")
        
        self.testing = True
        await ctx.send(f"Pressure test started (sequential). Use {ctx.prefix}stop_pressure to stop. Check logs for RAM usage and processing times.")
        self.pressure_task = self.bot.loop.create_task(self._pressure_loop(ctx, period))

    @commands.command(name="stop_pressure", hidden=True)
    @commands.is_owner()
    async def stop_pressure(self, ctx: commands.Context) -> None:
        if not self.testing:
            return await ctx.send("No pressure test running.")
        
        self.testing = False
        if self.pressure_task:
            await self.pressure_task
            await asyncio.sleep(0.1)  # Allow worker to finish
        
        final_ram = self._get_ram_mb()
        print(f"Pressure test stopped. Final RAM: {final_ram} MB")
        await ctx.send("Pressure test stopped. Check logs for final RAM usage and processing times.")

    def cog_unload(self) -> None:
        self.testing = False
        self._aggressive_cleanup()
        gc.collect()
        if self.test_images:
            for path in self.test_images:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
        self.thread_executor.shutdown(wait=False, cancel_futures=True)
        if hasattr(self, 'predictor'):
            self.predictor = None  # Hint GC
        self.full_pokemon_data = None
        self._pokemon_ids = None
        self.bot.loop.run_until_complete(self._save_image_urls())

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PoketwoSpawnDetector(bot))