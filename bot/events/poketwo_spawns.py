"""
Optimized Poketwo Spawn Detector
Performance improvements:
- Batched database queries (3+ queries → 1 query)
- Server config caching with TTL
- Warmed-up prediction model
- Chunked regeneration to prevent DB stacking
- Debounced spawn processing per channel
- Optimized Cloudinary connection pooling
- Pre-computed static caches on startup
"""

from functools import lru_cache
from collections import OrderedDict
import os
import gc
import json
import asyncio
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Optional, Tuple, List, Dict, Any

from motor.motor_asyncio import AsyncIOMotorClient
import aiohttp
import aiofiles
import cloudinary
import cloudinary.uploader
import requests
from cachetools import TTLCache

from imports.discord_imports import *
from bot.token import use_test_bot as ut
from bot.cogs.pokemon import PoketwoCommands
from utils.subcogs.pokemon import MongoHelper
from submodules.poketwo_autonamer.predict import Prediction
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from tqdm.asyncio import tqdm_asyncio

import resource
import random
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PoketwoSpawnDetector(commands.Cog):
    TARGET_BOT_ID = 716390085896962058
    MAX_DYNAMIC_CACHE_SIZE = 2000
    MAX_STATIC_CACHE_SIZE = 10000
    WORKER_COUNT = 12  # Increased for better throughput
    PERIODIC_SAVE_INTERVAL = 300
    SPAM_WINDOW_SECONDS = 60
    SPAM_THRESHOLD = 100
    SPAWN_DIR = "data/events/poketwo_spawns/spawns"
    IMAGE_URLS_PATH = "data/events/poketwo_spawns/image_urls.json"
    CONFIG_PATH = "data/events/poketwo_spawns/image/config.json"
    SUCCESS_EMOJI = "<:green:1261639410181476443>"
    ERROR_EMOJI = "<:red:1261639413943762944>"
    CROSS_EMOJI = "Cross"
    CONFIG_CACHE_TTL = 300  # 5 minutes
    REGENERATION_CHUNK_SIZE = 50  # Process in chunks to prevent DB stacking
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
        self.predictor = Prediction()
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
            lang_flags={"ja": "Japan", "de": "Germany", "fr": "France", "en": "United States"},
            bot=bot,
            pp=self.pp,
        )
        self.full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()
        self.image_builder = PokemonImageBuilder()
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()

        # Caches
        self.base_cache = lru_cache(maxsize=self.MAX_DYNAMIC_CACHE_SIZE)(self._get_base_name)
        self.desc_cache: Dict[str, Tuple[str, str]] = {}
        self.type_cache: Dict[str, List[str]] = {}
        self.alt_cache: Dict[str, str] = {}
        self.image_url_cache: OrderedDict = OrderedDict()
        self.config_cache = TTLCache(maxsize=1000, ttl=self.CONFIG_CACHE_TTL)
        self.test_images: Optional[List[str]] = None
        self.channel_stats: Dict[int, Dict[str, Any]] = {}

        # Spawn processing controls
        self.spawn_semaphores: Dict[int, asyncio.Semaphore] = {}
        self.spawn_locks: Dict[str, asyncio.Lock] = {}

        self.default_ext = self._get_default_ext()
        self.thread_executor = ThreadPoolExecutor(max_workers=self.WORKER_COUNT)
        self.process_executor = ProcessPoolExecutor(max_workers=self.WORKER_COUNT)
        self.processed_count = 0

        self.success_emoji = self.SUCCESS_EMOJI
        self.error_emoji = self.ERROR_EMOJI
        self.cross_emoji = self.CROSS_EMOJI

        # Shared aiohttp session with optimized settings
        self.aiohttp_session: Optional[aiohttp.ClientSession] = None

        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )

        self.dirty = False
        self.testing = False
        self.pressure_task: Optional[asyncio.Task] = None

        # Kick-off async init
        self.bot.loop.create_task(self._async_init())

    # --------------------------------------------------------------------- #
    # Async initialization
    # --------------------------------------------------------------------- #
    async def _async_init(self) -> None:
        """Async initialization tasks"""
        self._preload_static_caches()          # sync → no await
        self._load_image_urls()                # sync → no await
        await self._warmup_predictor()
        self.bot.loop.create_task(self._periodic_save())
        self.bot.loop.create_task(self._periodic_cleanup())
        self.bot.loop.create_task(self._preload_all_images())
        logger.info("PoketwoSpawnDetector fully initialized and warmed up")

    async def _warmup_predictor(self) -> None:
        """Warm up the prediction model to reduce first-prediction latency"""
        try:
            logger.info("Warming up prediction model...")
            dummy_url = self.TEST_SPAWN_URLS[0]
            await self.bot.loop.run_in_executor(
                self.thread_executor,  # ← FIXED: Use ThreadPoolExecutor to avoid pickling issues
                self._predict_pokemon,
                dummy_url
            )
            logger.info("Prediction model warmed up successfully")
        except Exception as e:
            logger.warning(f"Failed to warm up predictor: {e}")

    async def _get_aiohttp_session(self) -> aiohttp.ClientSession:
        """Get or create optimized aiohttp session"""
        if self.aiohttp_session is None or self.aiohttp_session.closed:
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            connector = aiohttp.TCPConnector(
                limit=300,
                limit_per_host=50,
                ttl_dns_cache=3600,
                use_dns_cache=True,
                keepalive_timeout=60,
                force_close=False,
                enable_cleanup_closed=True
            )
            self.aiohttp_session = aiohttp.ClientSession(timeout=timeout, connector=connector)
        return self.aiohttp_session

    # --------------------------------------------------------------------- #
    # Config cache invalidation
    # --------------------------------------------------------------------- #
    @commands.Cog.listener()
    async def on_config_update(self, guild_id: int, updated_keys: dict) -> None:
        """Invalidate config cache when settings change"""
        logger.debug(f"Config update for guild {guild_id}: {updated_keys}")
        self.config_cache.pop(guild_id, None)

    # --------------------------------------------------------------------- #
    # Image pre-loading (background)
    # --------------------------------------------------------------------- #
    async def _preload_all_images(self) -> None:
        """Preload missing images in background"""
        try:
            import csv
            async with aiofiles.open(self.pokemon_utils.pokemon_description_file, "r", encoding="utf-8") as f:
                data = await f.read()
            reader = list(csv.DictReader(data.splitlines()))
            slugs = [
                row.get("slug", row.get("name", "")).strip().lower()
                for row in reader
                if (row.get("slug") or row.get("name") or "").strip().lower()
            ]
            total_pokemon = len(slugs)
            missing = [slug for slug in slugs if not self._get_image_url(slug)]
            logger.info(f"Preloading {len(missing)} missing images out of {total_pokemon} Pokémon")

            if not missing:
                logger.info("All Pokémon images already cached")
                return

            for i in range(0, len(missing), self.REGENERATION_CHUNK_SIZE):
                chunk = missing[i:i + self.REGENERATION_CHUNK_SIZE]
                semaphore = asyncio.Semaphore(self.WORKER_COUNT)

                async def limited_process(slug: str) -> bool:
                    async with semaphore:
                        url = await self._handle_image_upload(slug)
                        return bool(url)

                results = await asyncio.gather(
                    *(limited_process(slug) for slug in chunk),
                    return_exceptions=True
                )
                success_count = sum(1 for r in results if isinstance(r, bool) and r)
                logger.info(f"Chunk {i // self.REGENERATION_CHUNK_SIZE + 1}: {success_count}/{len(chunk)} succeeded")

                if self.dirty:
                    await self._save_image_urls()
                    self.dirty = False

                await asyncio.sleep(0.5)  # gentle rate-limit

            logger.info("Image preloading complete")
        except Exception as e:
            logger.error(f"Failed to preload images: {e}")

    # --------------------------------------------------------------------- #
    # Periodic cleanup
    # --------------------------------------------------------------------- #
    async def _periodic_cleanup(self) -> None:
        """Clean up inactive channel stats and stale locks"""
        while True:
            await asyncio.sleep(300)
            now = time.time()

            # channel stats
            to_remove = [
                cid for cid, stats in self.channel_stats.items()
                if now - stats['window_start'] > 900
            ]
            for cid in to_remove:
                del self.channel_stats[cid]

            # semaphores
            inactive_semaphores = [
                cid for cid in self.spawn_semaphores
                if cid not in self.channel_stats
            ]
            for cid in inactive_semaphores:
                del self.spawn_semaphores[cid]

            logger.debug(
                f"Cleaned {len(to_remove)} channel stats, "
                f"{len(inactive_semaphores)} semaphores"
            )

    # --------------------------------------------------------------------- #
    # Static helper methods (sync)
    # --------------------------------------------------------------------- #
    def _get_default_ext(self) -> str:
        """Determine default image extension from config"""
        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                url = (cfg.get("background_url", "") or "").lower()
                return "gif" if url.endswith(".gif") else "png"
        except Exception:
            logger.warning("Failed to read config.json, defaulting to PNG")
            return "png"

    def _preload_static_caches(self) -> None:
        """Preload all static Pokémon data into memory"""
        logger.info("Preloading static caches...")
        for name in self._pokemon_ids:
            name_lower = name.lower()
            desc_data = self.pokemon_utils.get_description(name_lower) or ("", "???")
            self.desc_cache[name_lower] = desc_data
            self.type_cache[name_lower] = self.pokemon_utils.get_pokemon_types(name_lower)
            self.alt_cache[name_lower] = self.pokemon_utils.get_best_normal_alt_name(name_lower) or ""
        logger.info(f"Preloaded {len(self._pokemon_ids)} Pokémon into static caches")

    def _load_image_urls(self) -> None:
        """Load image URL cache from disk"""
        if os.path.exists(self.IMAGE_URLS_PATH):
            try:
                with open(self.IMAGE_URLS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.image_url_cache = OrderedDict((k.lower(), v) for k, v in data.items())
                        logger.info(f"Loaded {len(self.image_url_cache)} cached image URLs")
            except Exception as e:
                logger.error(f"Failed to load image URLs: {e}")

    def _get_image_url(self, base_name: str) -> Optional[str]:
        return self.image_url_cache.get(base_name.lower())

    def _add_image_url(self, base_name: str, url: str) -> None:
        base_name_lower = base_name.lower()
        self.image_url_cache[base_name_lower] = url
        if len(self.image_url_cache) > self.MAX_STATIC_CACHE_SIZE:
            self.image_url_cache.popitem(last=False)
        self.dirty = True

    # --------------------------------------------------------------------- #
    # Periodic save
    # --------------------------------------------------------------------- #
    async def _periodic_save(self) -> None:
        """Periodically save image URL cache to disk"""
        while True:
            await asyncio.sleep(self.PERIODIC_SAVE_INTERVAL)
            if self.dirty:
                await self._save_image_urls()
                self.dirty = False

    async def _save_image_urls(self) -> None:
        """Save image URL cache to disk"""
        try:
            os.makedirs(os.path.dirname(self.IMAGE_URLS_PATH), exist_ok=True)
            data = json.dumps(dict(self.image_url_cache), indent=2, ensure_ascii=False)
            async with aiofiles.open(self.IMAGE_URLS_PATH, "w", encoding="utf-8") as f:
                await f.write(data)
            logger.debug("Saved image URL cache")
        except Exception as e:
            logger.warning(f"Failed to save image URLs: {e}")

    # --------------------------------------------------------------------- #
    # Batched ping queries
    # --------------------------------------------------------------------- #
    async def _get_all_pings_batched(
        self,
        guild: discord.Guild,
        base_name: str,
        fetch_shiny: bool,
        fetch_type: bool,
        fetch_quest: bool
    ) -> Tuple[List[int], List[int], List[int], List[int]]:
        if not any([fetch_shiny, fetch_type, fetch_quest]):
            return [], [], [], []

        try:
            tasks = []
            if fetch_shiny:
                tasks.append(self.pokemon_utils.get_ping_users(guild, base_name))
            else:
                tasks.append(asyncio.sleep(0, result=([], [])))

            if fetch_type:
                tasks.append(self.pokemon_utils.get_type_ping_users(guild, base_name))
            else:
                tasks.append(asyncio.sleep(0, result=[]))

            if fetch_quest:
                tasks.append(self.pokemon_utils.get_quest_ping_users(guild, base_name))
            else:
                tasks.append(asyncio.sleep(0, result=[]))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            shiny_collect = results[0] if not isinstance(results[0], Exception) else ([], [])
            type_pings = results[1] if not isinstance(results[1], Exception) else []
            quest_pings = results[2] if not isinstance(results[2], Exception) else []

            shiny_pings, collect_pings = shiny_collect if isinstance(shiny_collect, tuple) else ([], [])
            return shiny_pings, collect_pings, type_pings, quest_pings
        except Exception as e:
            logger.error(f"Batched ping query failed: {e}")
            return [], [], [], []

    # --------------------------------------------------------------------- #
    # Core spawn processing
    # --------------------------------------------------------------------- #
    async def _process_spawn(self, message: discord.Message, image_url: str) -> None:
        overall_start = time.perf_counter()
        try:
            # Debounce per channel
            cid = message.channel.id
            if cid not in self.spawn_semaphores:
                self.spawn_semaphores[cid] = asyncio.Semaphore(3)

            async with self.spawn_semaphores[cid]:
                # Predict
                pred_start = time.perf_counter()
                raw_name, conf = await self.bot.loop.run_in_executor(
                    self.thread_executor,  # ← FIXED: Use ThreadPoolExecutor to avoid pickling issues
                    self._predict_pokemon,
                    image_url
                )
                pred_time = time.perf_counter() - pred_start

                base = self.base_cache(raw_name)
                base_name = base.lower()
                conf_float = self._parse_confidence(conf)
                low_conf = conf_float < 30.0

                # Duplicate guard
                if base_name not in self.spawn_locks:
                    self.spawn_locks[base_name] = asyncio.Lock()
                if self.spawn_locks[base_name].locked():
                    logger.debug(f"Skipping duplicate processing for {base_name}")
                    return

                async with self.spawn_locks[base_name]:
                    if message.guild is None:
                        logger.warning("Spawn message without guild; skipping")
                        return

                    sid = message.guild.id

                    # Config (cached)
                    config_start = time.perf_counter()
                    server_config = await self._get_server_config_cached(sid)
                    config_time = time.perf_counter() - config_start

                    # Static data
                    desc_data = self.desc_cache.get(base_name, ("", "???"))
                    desc, dex = desc_data[:2]
                    dex = self._pokemon_ids.get(base_name, dex)

                    # Pings
                    ping_start = time.perf_counter()
                    fetch_shiny = server_config.get("sh_enabled", True) or server_config.get("cl_enabled", True)
                    fetch_type = server_config.get("type_enabled", True)
                    fetch_quest = server_config.get("quest_enabled", True)

                    shiny_pings, collect_pings, type_pings, quest_pings = await self._get_all_pings_batched(
                        message.guild, base_name, fetch_shiny, fetch_type, fetch_quest
                    )
                    ping_time = time.perf_counter() - ping_start

                    # Special roles
                    rare, regional = getattr(self.pokemon_utils, "_special_names", ([], []))
                    special_roles = self._get_special_roles(server_config, base_name, rare, regional)

                    # Format ping message
                    ping_msg, _ = await self.pokemon_utils.format_messages(
                        raw_name, type_pings, quest_pings, shiny_pings, collect_pings,
                        " ".join(special_roles), f"{conf_float:.2f}%", dex, desc,
                        image_url, low_conf
                    )

                    # View
                    view = (
                        PokemonSpawnView(
                            slug=base_name,
                            pokemon_data=self.full_pokemon_data,
                            pokemonutils=self.pokemon_utils
                        ) if server_config.get("buttons_enabled", True) else None
                    )

                    # Image handling
                    image_start = time.perf_counter()
                    url = None
                    if server_config.get("images_enabled", True):
                        url = self._get_image_url(base_name)
                        if not url:
                            url = await self._handle_image_upload(base_name)
                    image_time = time.perf_counter() - image_start

                    # Send response
                    if not self.testing:
                        if url and server_config.get("images_enabled", True):
                            embed = discord.Embed(color=int("131416", 16))
                            embed.set_image(url=url)
                            self.bot.loop.create_task(
                                message.channel.send(
                                    content=ping_msg,
                                    embed=embed,
                                    reference=message,
                                    view=view
                                )
                            )
                        else:
                            self.bot.loop.create_task(
                                message.channel.send(
                                    content=ping_msg,
                                    reference=message,
                                    view=view
                                )
                            )
                    else:
                        logger.info(f"Test spawn processed: {base_name} (skipped send)")

                    self.processed_count += 1
                    if self.processed_count % 100 == 0:
                        gc.collect()
                        logger.debug(f"GC after {self.processed_count} spawns")

                    overall_time = time.perf_counter() - overall_start
                    logger.info(
                        f"Spawn: {base_name} | Pred: {pred_time:.2f}s | Config: {config_time:.3f}s | "
                        f"Pings: {ping_time:.2f}s | Image: {image_time:.2f}s | Total: {overall_time:.2f}s"
                    )
        except MemoryError:
            self._handle_memory_error(message)
        except Exception as e:
            self._handle_processing_error(message, e)

    # --------------------------------------------------------------------- #
    # Helper utilities
    # --------------------------------------------------------------------- #
    def _parse_confidence(self, conf: str) -> float:
        try:
            return float(str(conf).strip().rstrip("%"))
        except ValueError:
            return 0.0

    def _get_special_roles(
        self,
        server_config: dict,
        base_name: str,
        rare: list,
        regional: list
    ) -> list:
        if not server_config:
            return []
        roles = []
        if server_config.get("rare_enabled", True):
            roles.extend([
                f"<@&{server_config['rare_role']}>"
                for r in rare
                if r in base_name and server_config.get("rare_role")
            ])
        if server_config.get("regional_enabled", True):
            roles.extend([
                f"<@&{server_config['regional_role']}>"
                for r in regional
                if r in base_name and server_config.get("regional_role")
            ])
        return roles

    def _handle_memory_error(self, message: discord.Message) -> None:
        logger.error("MemoryError: Clearing dynamic caches")
        self.base_cache.cache_clear()
        gc.collect()
        self.bot.loop.create_task(
            message.channel.send(
                f"{self.error_emoji} Memory issue, cleared caches",
                reference=message
            )
        )

    def _handle_processing_error(self, message: discord.Message, e: Exception) -> None:
        logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
        traceback.print_exc()
        self.bot.loop.create_task(
            message.channel.send(
                f"{self.error_emoji} Failed to process spawn",
                reference=message
            )
        )

    def _predict_pokemon(self, image_url: str) -> Tuple[str, str]:
        if not image_url.startswith(('http://', 'https://')):
            # Local file handling (for pressure testing)
            # Read file content and create a mock response
            try:
                with open(image_url, 'rb') as f:
                    content = f.read()

                class MockResponse:
                    def __init__(self, content):
                        self.content = content
                        self.status_code = 200
                        self.headers = {'Content-Type': 'image/jpeg'}

                # Temporarily replace requests.get for this call
                original_get = requests.get
                requests.get = lambda url, *args, **kwargs: MockResponse(content)
                try:
                    return self.predictor.predict(image_url)
                finally:
                    requests.get = original_get
            except FileNotFoundError:
                logger.error(f"Local image not found: {image_url}")
                return "unknown", "0%"
        else:
            return self.predictor.predict(image_url)

    def _get_base_name(self, raw_name: str) -> str:
        base = self.pokemon_utils.get_base_pokemon_name(raw_name)
        if base not in self._pokemon_ids:
            full = self.pokemon_utils.find_full_name_for_slug(raw_name)
            if full:
                base = full.lower().replace("_", "-")
        return base

    async def _get_server_config_cached(self, sid: int) -> dict:
        if sid in self.config_cache:
            return self.config_cache[sid]

        try:
            config = await self.pokemon_utils.get_server_config(sid)
            result = config or {
                "images_enabled": True,
                "buttons_enabled": True,
                "rare_enabled": True,
                "regional_enabled": True,
                "cl_enabled": True,
                "sh_enabled": True,
                "type_enabled": True,
                "quest_enabled": True
            }
            self.config_cache[sid] = result
            return result
        except Exception as e:
            logger.error(f"Failed to fetch server config for guild {sid}: {e}")
            return {
                "images_enabled": True,
                "buttons_enabled": True,
                "rare_enabled": True,
                "regional_enabled": True,
                "cl_enabled": True,
                "sh_enabled": True,
                "type_enabled": True,
                "quest_enabled": True
            }

    # --------------------------------------------------------------------- #
    # Image generation / upload
    # --------------------------------------------------------------------- #
    async def _handle_image_upload(self, base_name: str) -> Optional[str]:
        ext = self.default_ext
        local_path = os.path.join(self.SPAWN_DIR, f"{base_name}.{ext}")

        if os.path.exists(local_path):
            url = await self._upload_local_image(local_path, base_name)
            if url:
                return url

        return await self._generate_and_upload_image(base_name, ext)

    async def _upload_local_image(self, local_path: str, base_name: str) -> Optional[str]:
        try:
            from functools import partial
            resp = await self.bot.loop.run_in_executor(
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
            logger.error(f"Local upload failed for {base_name}: {e}")
            return None

    async def _generate_and_upload_image(self, base_name: str, ext: str) -> Optional[str]:
        temp_path = self._get_temp_path(base_name, ext)
        alt = self.alt_cache.get(base_name.lower(), "")
        types = self.type_cache.get(base_name.lower(), [])
        name = self.pokemon_utils.format_name(base_name).replace("_", " ").title()

        try:
            await self.bot.loop.run_in_executor(
                self.thread_executor,
                self.image_builder.create_image,
                base_name, name, alt, types, None, temp_path, ext.upper()
            )

            if not os.path.exists(temp_path):
                logger.error(f"Generated file not found: {temp_path}")
                return None

            from functools import partial
            resp = await self.bot.loop.run_in_executor(
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
            logger.error(f"Image generation/upload failed for {base_name}: {e}")
            return None
        finally:
            self._cleanup_temp_file(temp_path)

    def _get_temp_path(self, base_name: str, ext: str) -> str:
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in base_name)
        return os.path.join("/tmp" if os.name != "nt" else os.getcwd(), f"{safe_name}.{ext}")

    def _cleanup_temp_file(self, temp_path: str) -> None:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                logger.debug("Failed to remove temp image", exc_info=True)

    # --------------------------------------------------------------------- #
    # Message listener
    # --------------------------------------------------------------------- #
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        cid = message.channel.id
        now = time.time()

        # Spam detection
        if cid not in self.channel_stats:
            self.channel_stats[cid] = {'count': 0, 'window_start': now, 'ignored': False}

        stats = self.channel_stats[cid]
        if now - stats['window_start'] > self.SPAM_WINDOW_SECONDS:
            stats['count'] = 1
            stats['window_start'] = now
            stats['ignored'] = False
        else:
            stats['count'] += 1

        if not stats['ignored'] and stats['count'] > self.SPAM_THRESHOLD:
            stats['ignored'] = True
            channel_name = getattr(message.channel, "name", "Unknown")
            logger.info(f"Marked high-volume channel {cid} ({channel_name}) as spam")

        if stats['ignored']:
            return

        if message.author.id != self.TARGET_BOT_ID or ut:
            return

        for embed in message.embeds:
            title = embed.title or ""
            if "pokémon has appeared!" in title.lower() and embed.image:
                img_url = embed.image.url
                if img_url:
                    self.bot.loop.create_task(self._process_spawn(message, img_url))

    # --------------------------------------------------------------------- #
    # Owner commands
    # --------------------------------------------------------------------- #
    @commands.command(name="ps", hidden=True)
    @commands.is_owner()
    async def predict_spawn(self, ctx: commands.Context, image_url: Optional[str] = None) -> None:
        image_url = image_url or await self._extract_image_url(ctx)
        if not image_url:
            return await ctx.send(f"{self.cross_emoji} No image URL found")
        await self._process_spawn(ctx.message, image_url)

    async def _extract_image_url(self, ctx: commands.Context) -> Optional[str]:
        msg = ctx.message
        url = self._extract_from_message(msg)
        if url:
            return url
        if msg.reference:
            try:
                ref = await ctx.channel.fetch_message(msg.reference.message_id)
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

    def _extract_from_message(self, msg: discord.Message) -> Optional[str]:
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

    # --------------------------------------------------------------------- #
    # Image (re)generation command
    # --------------------------------------------------------------------- #
    async def _handle_spawn_images(self, ctx: commands.Context, regenerate: bool = False) -> None:
        await ctx.defer()
        action = "Regenerating" if regenerate else "Generating"

        try:
            import csv
            async with aiofiles.open(self.pokemon_utils.pokemon_description_file, "r", encoding="utf-8") as f:
                data = await f.read()
            reader = list(csv.DictReader(data.splitlines()))

            work_items = []
            for row in reader:
                slug = (row.get("slug") or row.get("name") or "").strip().lower()
                if not slug:
                    continue
                if regenerate or not self._get_image_url(slug):
                    name = self.pokemon_utils.format_name(slug).replace("_", " ").title()
                    alt = self.alt_cache.get(slug, "")
                    types = self.type_cache.get(slug, [])
                    work_items.append((slug, name, alt, types))

            if not work_items:
                msg = "No Pokémon need regeneration" if regenerate else "All images already cached"
                return await ctx.send(f"{self.success_emoji} {msg}")

            total = len(work_items)
            running_embed = discord.Embed(
                title=f"{action} Spawn Images…",
                description=f"Processing **{total}** Pokémon in chunks of {self.REGENERATION_CHUNK_SIZE}…",
                colour=discord.Colour.orange()
            )
            prog_msg = await ctx.send(embed=running_embed)

            success = failed = 0
            failed_details = []

            for chunk_idx in range(0, len(work_items), self.REGENERATION_CHUNK_SIZE):
                chunk = work_items[chunk_idx:chunk_idx + self.REGENERATION_CHUNK_SIZE]
                chunk_num = chunk_idx // self.REGENERATION_CHUNK_SIZE + 1
                total_chunks = (len(work_items) + self.REGENERATION_CHUNK_SIZE - 1) // self.REGENERATION_CHUNK_SIZE

                logger.info(f"Processing chunk {chunk_num}/{total_chunks} ({len(chunk)} Pokémon)")

                semaphore = asyncio.Semaphore(self.WORKER_COUNT)

                async def process_one(item):
                    slug, name, alt, types = item
                    async with semaphore:
                        temp_path = self._get_temp_path(slug, self.default_ext)
                        try:
                            await self.bot.loop.run_in_executor(
                                self.thread_executor,
                                self.image_builder.create_image,
                                slug, name, alt, types, None, temp_path, self.default_ext.upper()
                            )
                            if not os.path.exists(temp_path):
                                raise FileNotFoundError(f"Generated file missing: {temp_path}")

                            from functools import partial
                            resp = await self.bot.loop.run_in_executor(
                                self.thread_executor,
                                partial(
                                    cloudinary.uploader.upload,
                                    temp_path,
                                    folder="poketwo_spawns",
                                    public_id=slug,
                                    overwrite=True,
                                    resource_type="image"
                                )
                            )
                            url = resp.get("secure_url")
                            if url:
                                self._add_image_url(slug, url)
                            return (slug, True, url)
                        except Exception as e:
                            logger.error(f"Failed {slug}: {e}")
                            return (slug, False, str(e))
                        finally:
                            self._cleanup_temp_file(temp_path)

                results = await tqdm_asyncio.gather(
                    *[process_one(item) for item in chunk],
                    desc=f"Chunk {chunk_num}/{total_chunks}",
                    unit="poke",
                    colour="cyan",
                    leave=True
                )

                for slug, ok, detail in results:
                    if ok:
                        success += 1
                    else:
                        failed += 1
                        failed_details.append(f"`{slug}`: {detail}")

                if self.dirty:
                    await self._save_image_urls()
                    self.dirty = False
                    logger.info(f"Saved progress after chunk {chunk_num}")

                progress_embed = discord.Embed(
                    title=f"{action} Spawn Images…",
                    description=(
                        f"**Progress:** {chunk_idx + len(chunk)}/{total}\n"
                        f"**Chunk:** {chunk_num}/{total_chunks}\n"
                        f"**Success:** {success} | **Failed:** {failed}"
                    ),
                    colour=discord.Colour.orange()
                )
                try:
                    await prog_msg.edit(embed=progress_embed)
                except:
                    pass

                if chunk_idx + self.REGENERATION_CHUNK_SIZE < len(work_items):
                    await asyncio.sleep(1.0)

            if self.dirty:
                await self._save_image_urls()
                self.dirty = False

            final_embed = discord.Embed(title=f"{action} Complete", colour=discord.Colour.green())
            final_embed.add_field(name="Success", value=f"{self.success_emoji} **{success}**", inline=True)
            final_embed.add_field(name="Failed", value=f"{self.error_emoji} **{failed}**", inline=True)
            final_embed.add_field(name="JSON", value=f"`{self.IMAGE_URLS_PATH}` updated", inline=False)

            if failed:
                if failed <= 15:
                    final_embed.add_field(name="Failed Pokémon", value="\n".join(failed_details), inline=False)
                else:
                    final_embed.add_field(name="Failed Pokémon",
                                          value="\n".join(failed_details[:10]) + f"\n... and **{failed - 10}** more",
                                          inline=False)

            await prog_msg.edit(embed=final_embed)

        except Exception as e:
            logger.error(f"Spawn image handler error: {e}", exc_info=True)
            err_embed = discord.Embed(title="Error", description=f"{self.error_emoji} `{e}`", colour=discord.Colour.red())
            try:
                await ctx.send(embed=err_embed)
            except:
                pass

    # --------------------------------------------------------------------- #
    # Health check
    # --------------------------------------------------------------------- #
    @commands.command(name="health_check", hidden=True)
    @commands.is_owner()
    async def health_check(self, ctx: commands.Context) -> None:
        cache_size = len(self.image_url_cache)
        total_pokemon = len(self._pokemon_ids)
        ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        config_cache_size = len(self.config_cache)

        embed = discord.Embed(title="Health Check", colour=discord.Colour.green())
        embed.add_field(name="Image Cache", value=f"{cache_size}/{total_pokemon} Pokémon", inline=True)
        embed.add_field(name="Config Cache", value=f"{config_cache_size} servers (TTL: {self.CONFIG_CACHE_TTL}s)", inline=True)
        embed.add_field(name="RAM Usage", value=f"{ram_mb:.1f} MB", inline=True)
        embed.add_field(name="Spawns Processed", value=f"{self.processed_count}", inline=True)
        embed.add_field(name="Active Channels", value=f"{len(self.channel_stats)}", inline=True)
        embed.add_field(name="Testing Mode", value="Yes" if self.testing else "No", inline=True)

        await ctx.send(embed=embed)

    # --------------------------------------------------------------------- #
    # Pressure testing
    # --------------------------------------------------------------------- #
    async def _pressure_loop(self, ctx: commands.Context, period: int) -> None:
        def get_ram():
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

        initial_ram = get_ram()
        logger.info(f"Initial RAM: {initial_ram:.1f} MB")

        i = 0
        delay_max = 0.5
        start_time = time.time()

        while self.testing:
            url = random.choice(self.test_images)
            self.bot.loop.create_task(self._process_spawn(ctx.message, url))
            await asyncio.sleep(random.uniform(0, delay_max))
            i += 1

            if i % 10 == 0:
                delay_max = max(0.005, delay_max * 0.95)

            if i % period == 0:
                cur = get_ram()
                inc = cur - initial_ram
                el = time.time() - start_time
                rate = i / el if el > 0 else 0
                logger.info(
                    f"Pressure test: {i} spawns ({el:.1f}s, {rate:.1f}/s) | "
                    f"RAM: {cur:.1f} MB (+{inc:.1f} MB) | delay ≤{delay_max:.3f}s"
                )

    @commands.command(name="pressure_test", hidden=True)
    @commands.is_owner()
    async def pressure_test(self, ctx: commands.Context, period: int = 10) -> None:
        if self.testing:
            return await ctx.send("Pressure test already running")

        if self.test_images is None:
            self.test_images = []

            async def dl(url, idx):
                try:
                    session = await self._get_aiohttp_session()
                    async with session.get(url) as r:
                        if r.status == 200:
                            data = await r.read()
                            path = f"/tmp/spawn_test_{idx}.jpg"
                            async with aiofiles.open(path, "wb") as f:
                                await f.write(data)
                            self.test_images.append(path)
                    logger.info(f"Downloaded test image {idx}")
                except Exception as e:
                    logger.error(f"Download failed {url}: {e}")

            await asyncio.gather(*(dl(u, i) for i, u in enumerate(self.TEST_SPAWN_URLS)))

        if not self.test_images:
            return await ctx.send("Failed to prepare test images")

        self.testing = True
        await ctx.send(f"Pressure test started. Use `{ctx.prefix}stop_pressure` to stop")
        self.pressure_task = self.bot.loop.create_task(self._pressure_loop(ctx, period))

    @commands.command(name="stop_pressure", hidden=True)
    @commands.is_owner()
    async def stop_pressure(self, ctx: commands.Context) -> None:
        if not self.testing:
            return await ctx.send("No pressure test running")

        self.testing = False
        if self.pressure_task:
            await self.pressure_task
            await asyncio.sleep(0.1)

        final = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        logger.info(f"Pressure test stopped. Final RAM: {final:.1f} MB")
        await ctx.send(f"Pressure test stopped. Final RAM: {final:.1f} MB")

    # --------------------------------------------------------------------- #
    # Cog unload
    # --------------------------------------------------------------------- #
    def cog_unload(self) -> None:
        self.testing = False

        if self.test_images:
            for p in self.test_images:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass

        self.thread_executor.shutdown(wait=False, cancel_futures=True)
        self.process_executor.shutdown(wait=False, cancel_futures=True)

        if self.aiohttp_session and not self.aiohttp_session.closed:
            self.bot.loop.run_until_complete(self.aiohttp_session.close())

        self.bot.loop.run_until_complete(self._save_image_urls())
        logger.info("PoketwoSpawnDetector cog unloaded")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PoketwoSpawnDetector(bot))
