import os, gc, time, random, logging, traceback, asyncio, weakref, requests
from pathlib import Path
from functools import partial, lru_cache
from collections import OrderedDict, deque
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

import aiohttp, aiofiles, orjson, cloudinary, cloudinary.uploader
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import redis
import hashlib

from imports.discord_imports import *
from bot.token import use_test_bot as ut
from bot.cogs.pokemon import PoketwoCommands
from utils.subcogs.pokemon import MongoHelper
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

class PoketwoSpawnDetector(commands.Cog):
    """
    A Discord Cog for detecting and processing Pokétwo spawns.
    Handles image prediction, caching, pinging, and image generation/uploading.
    """

    TARGET_BOT_ID = 716390085896962058
    MAX_DYNAMIC_CACHE_SIZE = 500
    MAX_SERVER_CACHE_SIZE = 200
    WORKER_COUNT = 4
    BATCH_SIZE = 5
    SPAM_WINDOW_SECONDS = 60
    SPAM_THRESHOLD = 100  # messages per window
    SPAWN_DIR = Path("data/events/poketwo_spawns/spawns")
    CONFIG_PATH = Path("data/events/poketwo_spawns/image/config.json")
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
    RAM_THRESHOLD_MB = 450  # Trigger GC below 512MB
    QUEUE_MAXSIZE = 20

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.predictor = Prediction()  # Preload model
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

        # Caches: Lightweight in-memory where appropriate
        self.base_cache = lru_cache(maxsize=self.MAX_DYNAMIC_CACHE_SIZE)(self._get_base_name)
        self.server_config_cache = OrderedDict()
        self.desc_cache = {}  # Static, preloaded
        self.type_cache = {}  # Static, preloaded
        self.alt_cache = {}  # Static, preloaded
        self.test_images = None
        self.channel_stats = {}  # Fallback if no Redis
        self.redis = None
        self.channel_locks = {}

        if os.getenv("REDIS_URL"):
            try:
                self.redis = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)
                logger.info("Connected to Redis for efficient state management")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}, falling back to in-memory")
                self.redis = None
        else:
            logger.warning("No REDIS_URL set, falling back to in-memory")

        self.default_ext = self._get_default_ext()
        self.queue = asyncio.Queue(maxsize=self.QUEUE_MAXSIZE)
        self.queue_semaphore = asyncio.Semaphore(self.WORKER_COUNT * 2)  # Limit concurrent processing
        self.thread_executor = ThreadPoolExecutor(max_workers=self.WORKER_COUNT)
        self.process_executor = ProcessPoolExecutor(max_workers=self.WORKER_COUNT)
        self.processed_count = 0
        self.dropped_count = 0

        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )

        self.testing = False
        self._preload_static_caches()
        self.SPAWN_DIR.mkdir(parents=True, exist_ok=True)

        # Start workers and ram monitor
        self.bot.loop.create_task(self._start_workers_and_saver())
        self.bot.loop.create_task(self._ram_monitor())

    def _get_channel_lock(self, cid_str: str) -> asyncio.Lock:
        if cid_str not in self.channel_locks:
            self.channel_locks[cid_str] = asyncio.Lock()
        return self.channel_locks[cid_str]

    def _serialize_for_json(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, dict):
            return {k: self._serialize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._serialize_for_json(i) for i in obj]
        return obj

    async def _start_workers_and_saver(self):
        for _ in range(self.WORKER_COUNT):
            self.bot.loop.create_task(self._worker())

    async def _ram_monitor(self):
        while True:
            await asyncio.sleep(30)  # Check every 30s
            try:
                import psutil
                process = psutil.Process()
                ram_mb = process.memory_info().rss / 1024 / 1024
                if ram_mb > self.RAM_THRESHOLD_MB:
                    gc.collect()
                    logger.warning(f"High RAM ({ram_mb:.2f} MB): Forced GC")
            except ImportError:
                pass  # Skip if psutil not available
            except Exception as e:
                logger.debug(f"RAM monitor error: {e}")

    def _get_default_ext(self) -> str:
        try:
            with open(self.CONFIG_PATH, "rb") as f:
                cfg = orjson.loads(f.read())
                url = (cfg.get(b"background_url", b"") or b"").decode().lower()
                return "gif" if url.endswith(".gif") else "png"
        except Exception:
            logger.warning("Failed to read config.json, defaulting to PNG")
            return "png"

    def _preload_static_caches(self) -> None:
        for name in self._pokemon_ids:
            name_lower = name.lower()
            desc_data = self.pokemon_utils.get_description(name_lower) or ("", "???")
            self.desc_cache[name_lower] = desc_data
            types = self.pokemon_utils.get_pokemon_types(name_lower)
            self.type_cache[name_lower] = types
            alt = self.pokemon_utils.get_best_normal_alt_name(name_lower) or ""
            self.alt_cache[name_lower] = alt

    async def _get_image_url(self, base_name: str) -> str | None:
        if not self.redis:
            return None  # Or fallback logic if needed
        loop = asyncio.get_event_loop()
        key = base_name.lower()
        url = await loop.run_in_executor(self.thread_executor, self.redis.hget, "image_urls", key)
        return url

    async def _add_image_url(self, base_name: str, url: str) -> None:
        if not self.redis:
            return
        loop = asyncio.get_event_loop()
        key = base_name.lower()
        await loop.run_in_executor(self.thread_executor, self.redis.hset, "image_urls", key, url)

    async def _worker(self) -> None:
        while True:
            try:
                async with self.queue_semaphore:
                    item = await self.queue.get()
                    message, image_url = item
                    await self._process_spawn(message, image_url)
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
                traceback.print_exc()
                await asyncio.sleep(0.1)

    async def _process_spawn(self, message: discord.Message, image_url: str) -> None:
        overall_start = time.time()
        try:
            # Run prediction in executor for non-blocking
            pred_start = time.time()
            loop = asyncio.get_event_loop()
            raw_name, conf = await loop.run_in_executor(
                self.thread_executor,
                partial(self._predict_pokemon, image_url)
            )
            pred_end = time.time()
            pred_time = pred_end - pred_start

            base = self.base_cache(raw_name)
            base_name = base.lower()
            conf_float = self._parse_confidence(conf)
            low_conf = conf_float < 30.0

            if message.guild is None:
                logger.warning("Spawn message without guild; skipping.")
                return

            sid = message.guild.id
            server_config = await self._get_server_config(sid)

            desc_data = self.desc_cache.get(base_name, ("", "???"))
            desc, dex = desc_data[:2]
            dex = self._pokemon_ids.get(base_name, dex)

            # Live MongoDB queries for pings - awaited every time per spawn
            shiny_collect, type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_ping_users(message.guild, base_name),
                self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
            )

            shiny_pings, collect_pings = shiny_collect

            rare, regional = getattr(self.pokemon_utils, "_special_names", ([], []))
            special_roles = self._get_special_roles(server_config, base_name, rare, regional)

            ping_msg, _ = await self.pokemon_utils.format_messages(
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
            url = await self._handle_image_upload(base_name)
            image_end = time.time()
            image_time = image_end - image_start

            process_end = time.time()

            if not self.testing:
                embed = discord.Embed()
                footer_parts = [f"{process_end - overall_start:.2f}s"]
                if low_conf:
                    footer_parts.insert(0, "Low confidence prediction")
                embed.set_footer(text=" | ".join(footer_parts))
                if url:
                    embed.set_image(url=url)
                await message.channel.send(
                    content=ping_msg,
                    embed=embed,
                    reference=message,
                    view=view
                )
            else:
                logger.info(f"Test spawn processed: {base_name} (skipped send)")

            self.processed_count += 1

            overall_end = time.time()
            overall_time = overall_end - overall_start

            # RAM check
            try:
                import psutil
                process = psutil.Process()
                ram_mb = process.memory_info().rss / 1024 / 1024
            except:
                ram_mb = 0
            logger.info(
                f"Spawn Processing - Pred: {pred_time:.3f}s | Img: {image_time:.3f}s | Total: {overall_time:.3f}s | RAM: {ram_mb:.1f}MB"
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
        return (
            [f"<@&{server_config['rare_role']}>" for r in rare if r in base_name and server_config.get("rare_role")]
            + [f"<@&{server_config['regional_role']}>" for r in regional if r in base_name and server_config.get("regional_role")]
        )

    def _handle_memory_error(self, message: discord.Message) -> None:
        logger.error("MemoryError: Aggressive cleanup")
        self.base_cache.cache_clear()
        self.server_config_cache.clear()
        gc.collect(generation=2)
        try:
            asyncio.create_task(message.channel.send(f"{self.ERROR_EMOJI} Memory issue, cleared caches", reference=message))
        except Exception:
            logger.exception("Failed to notify about memory error.")

    def _handle_processing_error(self, message: discord.Message, e: Exception) -> None:
        logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
        traceback.print_exc()
        try:
            asyncio.create_task(message.channel.send(f"{self.ERROR_EMOJI} Failed to process spawn", reference=message))
        except Exception:
            logger.exception("Failed to notify about spawn processing error.")

    def _predict_pokemon(self, image_url: str) -> tuple[str, str]:
        hash_url = hashlib.md5(image_url.encode()).hexdigest()
        pred_key = f"pred:{hash_url}"
        if self.redis:
            cached = self.redis.get(pred_key)
            if cached:
                data = orjson.loads(cached)
                return data[0], data[1]

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
                pred = self.predictor.predict(image_url)
            finally:
                requests.get = original_get
        else:
            pred = self.predictor.predict(image_url)

        if self.redis:
            self.redis.setex(pred_key, 86400, orjson.dumps([pred[0], pred[1]]))

        return pred

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

        loop = asyncio.get_event_loop()
        config = None
        if self.redis:
            config_json = await loop.run_in_executor(
                self.thread_executor, self.redis.get, f"server_config:{sid}"
            )
            if config_json:
                try:
                    config = orjson.loads(config_json)
                except:
                    config = None

        if not config:
            config = await self.pokemon_utils.get_server_config(sid)
            if config:
                config = self._serialize_for_json(config)
            if config and self.redis:
                await loop.run_in_executor(
                    self.thread_executor,
                    self.redis.setex,
                    f"server_config:{sid}",
                    3600,
                    orjson.dumps(config)
                )

        self.server_config_cache[sid] = config or {}
        if len(self.server_config_cache) > self.MAX_SERVER_CACHE_SIZE:
            self.server_config_cache.popitem(last=False)
        return self.server_config_cache[sid]

    async def _handle_image_upload(self, base_name: str) -> str | None:
        ext = self.default_ext
        local_path = self.SPAWN_DIR / f"{base_name}.{ext}"
        if local_path.exists():
            url = await self._upload_local_image(local_path, base_name)
            if url:
                return url

        # Generate and upload new image
        return await self._generate_and_upload_image(base_name, ext)

    async def _upload_local_image(self, local_path: Path, base_name: str) -> str | None:
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                self.thread_executor,
                partial(
                    cloudinary.uploader.upload,
                    str(local_path),
                    folder="poketwo_spawns",
                    public_id=base_name,
                    overwrite=True
                )
            )
            url = resp.get("secure_url")
            if url:
                await self._add_image_url(base_name, url)
            return url
        except Exception as e:
            logger.error(f"Local upload failed for {base_name}: {e}")
            return None

    async def _generate_and_upload_image(self, base_name: str, ext: str) -> str | None:
        temp_path = self._get_temp_path(base_name, ext)
        alt = self.alt_cache.get(base_name.lower()) or ""
        types = self.type_cache.get(base_name.lower()) or []
        name = self.pokemon_utils.format_name(base_name).replace("_", " ").title()

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.process_executor,
                self.image_builder.create_image,
                base_name, name, alt, types, None, temp_path, ext.upper()
            )
            resp = await loop.run_in_executor(
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
                await self._add_image_url(base_name, url)
            self._cleanup_temp_file(temp_path)
            return url
        except Exception as e:
            logger.error(f"Image create/upload failed for {base_name}: {e}")
            self._cleanup_temp_file(temp_path)
            return None

    def _get_temp_path(self, base_name: str, ext: str) -> str:
        temp_dir = Path("/tmp") if os.name != "nt" else Path.cwd()
        return str(temp_dir / f"{base_name}.{ext}")

    def _cleanup_temp_file(self, temp_path: str) -> None:
        temp_p = Path(temp_path)
        if temp_p.exists():
            try:
                temp_p.unlink()
            except Exception:
                logger.debug("Failed to remove temp image", exc_info=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        try:
            cid = message.channel.id
            cid_str = str(cid)
            now = time.time()
            stats_key = f"channel_stats:{cid_str}"
            loop = asyncio.get_event_loop()

            async with self._get_channel_lock(cid_str):
                if self.redis:
                    stats = await loop.run_in_executor(
                        self.thread_executor, self.redis.hgetall, stats_key
                    )
                else:
                    stats = self.channel_stats.get(cid_str, {})

                if not stats:
                    stats = {'count': '0', 'window_start': str(now), 'ignored': 'False'}

                count = int(stats.get('count', '0'))
                window_start_str = stats.get('window_start', str(now))
                window_start = float(window_start_str)
                ignored_str = stats.get('ignored', 'False')
                ignored = ignored_str == 'True'

                if now - window_start > self.SPAM_WINDOW_SECONDS:
                    count = 1
                    window_start = now
                else:
                    count += 1

                if not ignored and count > self.SPAM_THRESHOLD:
                    ignored = True
                    channel_name = message.channel.name if hasattr(message.channel, 'name') else 'Unknown'
                    logger.warning(f"Marked high-volume channel {cid} ({channel_name}) as spam (rate: {count} msg/{self.SPAM_WINDOW_SECONDS}s), ignoring future messages.")

                new_stats = {
                    'count': str(count),
                    'window_start': str(window_start),
                    'ignored': 'True' if ignored else 'False'
                }

                if self.redis:
                    await loop.run_in_executor(
                        self.thread_executor,
                        partial(self.redis.hset, stats_key, mapping=new_stats)
                    )
                    await loop.run_in_executor(
                        self.thread_executor,
                        self.redis.expire,
                        stats_key,
                        1800
                    )
                else:
                    self.channel_stats[cid_str] = new_stats

                if ignored:
                    return

            if message.author.id != self.TARGET_BOT_ID or ut:
                return
            for embed in message.embeds:
                title = embed.title
                if title and "pokémon has appeared!" in title.lower() and embed.image:
                    img_url = embed.image.url
                    if img_url:
                        try:
                            self.queue.put_nowait((message, img_url))
                        except asyncio.QueueFull:
                            self.dropped_count += 1
                            logger.warning(f"Dropped spawn due to overflow (total dropped: {self.dropped_count})")
        except Exception as e:
            logger.error(f"Error in on_message: {e}")

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
            slugs = []
            for row in reader:
                slug = (row.get("slug") or row.get("name") or "").strip().lower()
                if slug:
                    slugs.append(slug)
            if not regenerate:
                check_tasks = [self._get_image_url(slug) for slug in slugs]
                urls = await asyncio.gather(*check_tasks, return_exceptions=True)
                work_items = [(slug, True) for slug, url in zip(slugs, urls) if isinstance(url, Exception) or not url]
            else:
                work_items = [(slug, True) for slug in slugs]

            if not work_items:
                msg = "❌ No spawn items found." if regenerate else "✅ All spawn images already cached."
                return await ctx.send(msg)

            success_count = 0
            error_count = 0
            async def process_slug(slug: str):
                url = await self._handle_image_upload(slug)
                return bool(url)

            semaphore = asyncio.Semaphore(self.BATCH_SIZE)
            async def limited_process(slug):
                async with semaphore:
                    return await process_slug(slug)

            for start in range(0, len(work_items), self.BATCH_SIZE):
                batch = [slug for slug, needs_process in work_items[start:start + self.BATCH_SIZE] if needs_process]
                results = await asyncio.gather(*(limited_process(slug) for slug in batch), return_exceptions=True)
                success_count += sum(1 for r in results if isinstance(r, bool) and r)
                error_count += sum(1 for r in results if isinstance(r, Exception) or (isinstance(r, bool) and not r))

            action = "Regenerated" if regenerate else "Generated"
            await ctx.send(f"✅ {action} {success_count} spawn images. ❌ {error_count} failed.")
        except Exception as e:
            logger.error(f"Spawn image handler failure: {type(e).__name__}: {e}")
            await ctx.send(f"{self.ERROR_EMOJI} Error: {e}")

    async def _pressure_loop(self, ctx: commands.Context, period: int) -> None:
        def get_ram():
            try:
                import resource
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # in MB
            except:
                return 0

        initial_ram = get_ram()
        logger.info(f"Initial RAM: {initial_ram} MB")

        i = 0
        delay_max = 1.0
        start_time = time.time()

        while self.testing:
            url = random.choice(self.test_images)
            message = ctx.message  # Simulate using the command's message
            try:
                self.queue.put_nowait((message, url))
            except asyncio.QueueFull:
                self.dropped_count += 1
                await asyncio.sleep(0.01)
                continue

            await asyncio.sleep(random.uniform(0, delay_max))

            i += 1

            if i % 10 == 0:
                delay_max = max(0.01, delay_max * 0.9)  # Reduce delay to make it faster over time

            if i % period == 0:
                current_ram = get_ram()
                increase = current_ram - initial_ram
                elapsed = time.time() - start_time
                print(f"After {i} simulated spawns (elapsed {elapsed:.2f} seconds), RAM: {current_ram} MB, increase: {increase} MB, current delay max: {delay_max:.2f} seconds")

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
                                path = Path(f"/tmp/spawn_test_{i}.jpg")
                                async with aiofiles.open(path, 'wb') as f:
                                    await f.write(content)
                                self.test_images.append(str(path))
                    logger.info(f"Downloaded test image {i}")
                except Exception as e:
                    logger.error(f"Failed to download {url}: {e}")
        
        if not self.test_images:
            return await ctx.send("Failed to prepare test images.")
        
        self.testing = True
        await ctx.send(f"Pressure test started. Use {ctx.prefix}stop_pressure to stop. Check logs for RAM usage and processing times.")
        self.pressure_task = self.bot.loop.create_task(self._pressure_loop(ctx, period))

    @commands.command(name="stop_pressure", hidden=True)
    @commands.is_owner()
    async def stop_pressure(self, ctx: commands.Context) -> None:
        if not self.testing:
            return await ctx.send("No pressure test running.")
        
        self.testing = False
        if hasattr(self, 'pressure_task') and self.pressure_task:
            await self.pressure_task
            await asyncio.sleep(0.1)  # Allow workers to finish
        
        def get_ram():
            try:
                import resource
                return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # in MB
            except:
                return 0

        final_ram = get_ram()
        print(f"Pressure test stopped. Final RAM: {final_ram} MB | Processed: {self.processed_count} | Dropped: {self.dropped_count}")
        await ctx.send("Pressure test stopped. Check logs for final RAM usage and processing times.")

    def cog_unload(self) -> None:
        self.testing = False
        if self.test_images:
            for path_str in self.test_images:
                path = Path(path_str)
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        pass
        self.thread_executor.shutdown(wait=False, cancel_futures=True)
        self.process_executor.shutdown(wait=False, cancel_futures=True)
        if self.redis:
            self.redis.close()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PoketwoSpawnDetector(bot))
