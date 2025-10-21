from functools import partial, lru_cache
from collections import OrderedDict
import os
import gc
import json
import asyncio
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
 
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)


class PoketwoSpawnDetector(commands.Cog):
    TARGET_BOT_ID = 716390085896962058
    MAX_DYNAMIC_CACHE_SIZE = 2000
    MAX_STATIC_CACHE_SIZE = 10000
    WORKER_COUNT = 4
    BATCH_SIZE = 20
    PERIODIC_SAVE_INTERVAL = 300
    SPAM_WINDOW_SECONDS = 60
    SPAM_THRESHOLD = 100
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
        self.predictor = Prediction()
        self.pp = PoketwoCommands(bot)
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.pokemonutils = PokemonUtils(
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
        self.full_pokemon_data = self.pokemonutils.load_full_pokemon_data()
        self.image_builder = PokemonImageBuilder()
        self._pokemon_ids = self.pokemonutils.load_pokemon_ids()

        self.base_cache = lru_cache(maxsize=self.MAX_DYNAMIC_CACHE_SIZE)(self._get_base_name)
        self.server_cache = self._get_server_config
        self.server_config_cache = OrderedDict()
        self.desc_cache = {}
        self.type_cache = {}
        self.alt_cache = {}
        self.image_url_cache = OrderedDict()
        self.test_images = None
        self.channel_stats = {}

        self.default_ext = self._get_default_ext()
        self.thread_executor = ThreadPoolExecutor(max_workers=self.WORKER_COUNT)
        self.process_executor = ProcessPoolExecutor(max_workers=self.WORKER_COUNT)
        self.processed_count = 0

        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )

        self.dirty = False
        self.testing = False
        self._preload_static_caches()
        self._load_image_urls()

        self.bot.loop.create_task(self._periodic_save())
        self.bot.loop.create_task(self._periodic_cleanup())
        self.bot.loop.create_task(self._preload_all_images())

    async def _preload_all_images(self):
        try:
            import csv
            async with aiofiles.open(self.pokemonutils.pokemon_description_file, "r", encoding="utf-8") as f:
                data = await f.read()
            reader = list(csv.DictReader(data.splitlines()))
            slugs = [row.get("slug", row.get("name", "")).strip().lower() for row in reader if (slug := row.get("slug") or row.get("name") or "").strip().lower()]
            total_pokemon = len(slugs)
            missing = [slug for slug in slugs if not self._get_image_url(slug)]
            logger.info(f"Preloading {len(missing)} missing images out of {total_pokemon} Pokémon.")

            if not missing:
                logger.info("All Pokémon images already cached.")
                return

            semaphore = asyncio.Semaphore(self.WORKER_COUNT)
            async def limited_process(slug):
                async with semaphore:
                    url = await self._handle_image_upload(slug)
                    return bool(url)

            results = await asyncio.gather(*(limited_process(slug) for slug in missing), return_exceptions=True)
            success_count = sum(1 for r in results if isinstance(r, bool) and r)
            error_count = len(missing) - success_count
            logger.info(f"Preloaded {success_count} images successfully. {error_count} failed.")
        except Exception as e:
            logger.error(f"Failed to preload images: {e}")

    async def _periodic_cleanup(self):
        while True:
            await asyncio.sleep(300)
            now = time.time()
            to_remove = [cid for cid, stats in self.channel_stats.items() if now - stats['window_start'] > 900]
            for cid in to_remove:
                del self.channel_stats[cid]
            logger.debug(f"Cleaned up {len(to_remove)} inactive channel stats")

    def _get_default_ext(self) -> str:
        try:
            with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                url = (cfg.get("background_url", "") or "").lower()
                return "gif" if url.endswith(".gif") else "png"
        except Exception:
            logger.warning("Failed to read config.json, defaulting to PNG")
            return "png"

    def _preload_static_caches(self) -> None:
        for name in self._pokemon_ids:
            name_lower = name.lower()
            desc_data = self.pokemonutils.get_description(name_lower) or ("", "???")
            self.desc_cache[name_lower] = desc_data
            types = self.pokemonutils.get_pokemon_types(name_lower)
            self.type_cache[name_lower] = types
            alt = self.pokemonutils.get_best_normal_alt_name(name_lower) or ""
            self.alt_cache[name_lower] = alt

    def _load_image_urls(self) -> None:
        if os.path.exists(self.IMAGE_URLS_PATH):
            try:
                with open(self.IMAGE_URLS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.image_url_cache = OrderedDict((k.lower(), v) for k, v in data.items())
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

    async def _process_spawn(self, message: discord.Message, image_url: str) -> None:
        overall_start = time.perf_counter()
        try:
            pred_start = time.perf_counter()
            def predict_sync():
                return self._predict_pokemon(image_url)
            raw_name, conf = await self.bot.loop.run_in_executor(self.thread_executor, predict_sync)
            pred_end = time.perf_counter()
            pred_time = pred_end - pred_start

            base = self.base_cache(raw_name)
            base_name = base.lower()
            conf_float = self._parse_confidence(conf)
            low_conf = conf_float < 30.0

            if message.guild is None:
                logger.warning("Spawn message without guild; skipping.")
                return

            sid = message.guild.id
            server_config = await self.server_cache(sid)

            fetch_shiny = server_config.get("sh_enabled", True) or server_config.get("cl_enabled", True)
            fetch_type = server_config.get("type_enabled", True)
            fetch_quest = server_config.get("quest_enabled", True)

            desc_data = self.desc_cache.get(base_name, ("", "???"))
            desc, dex = desc_data[:2]
            dex = self._pokemon_ids.get(base_name, dex)

            ping_start = time.perf_counter()
            shiny_collect = (
                await self.pokemonutils.get_ping_users(message.guild, base_name)
                if fetch_shiny else ([], [])
            )
            type_pings = (
                await self.pokemonutils.get_type_ping_users(message.guild, base_name)
                if fetch_type else []
            )
            quest_pings = (
                await self.pokemonutils.get_quest_ping_users(message.guild, base_name)
                if fetch_quest else []
            )
            ping_end = time.perf_counter()
            ping_time = ping_end - ping_start

            shiny_pings, collect_pings = shiny_collect

            rare, regional = getattr(self.pokemonutils, "_special_names", ([], []))
            special_roles = self._get_special_roles(server_config, base_name, rare, regional)

            ping_msg, _ = await self.pokemonutils.format_messages(
                raw_name, type_pings, quest_pings, shiny_pings, collect_pings,
                " ".join(special_roles), f"{conf_float:.2f}%", dex, desc,
                image_url, low_conf
            )

            view = (
                PokemonSpawnView(
                    slug=base_name,
                    pokemon_data=self.full_pokemon_data,
                    pokemonutils=self.pokemonutils
                ) if server_config.get("buttons_enabled", True) else None
            )

            image_start = time.perf_counter()
            url = (
                self._get_image_url(base_name) or await self._handle_image_upload(base_name)
                if server_config.get("images_enabled", True) else None
            )
            image_end = time.perf_counter()
            image_time = image_end - image_start

            if not self.testing:
                if url and server_config.get("images_enabled", True):
                    embed = discord.Embed()
                    embed.set_image(url=url)
                    embed.set_footer(text="Predicted in {:.2f}s".format(pred_time + image_time))
                    await message.channel.send(
                        content=ping_msg,
                        embed=embed,
                        reference=message,
                        view=view
                    )
                else:
                    await message.channel.send(
                        content=ping_msg,
                        reference=message,
                        view=view
                    )
            else:
                logger.info(f"Test spawn processed: {base_name} (skipped send)")

            self.processed_count += 1
            if self.processed_count % 100 == 0:
                gc.collect()
                logger.debug(f"GC collected after {self.processed_count} processes")

            overall_end = time.perf_counter()
            overall_time = overall_end - overall_start

            logger.info(
                f"Spawn Processing Times - Prediction: {pred_time:.2f}s | "
                f"Pings: {ping_time:.2f}s | "
                f"Image Preparation: {image_time:.2f}s | "
                f"Overall Response: {overall_time:.2f}s"
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
        if server_config.get("rare_enabled", True):
            roles.extend(
                [f"<@&{server_config['rare_role']}>" for r in rare if r in base_name and server_config.get("rare_role")]
            )
        if server_config.get("regional_enabled", True):
            roles.extend(
                [f"<@&{server_config['regional_role']}>" for r in regional if r in base_name and server_config.get("regional_role")]
            )
        return roles

    def _handle_memory_error(self, message: discord.Message) -> None:
        logger.error("MemoryError: Clearing dynamic caches")
        self.base_cache.cache_clear()
        gc.collect()
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
        if not image_url.startswith(('http://', 'https://')):
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
        base = self.pokemonutils.get_base_pokemon_name(raw_name)
        if base not in self._pokemon_ids:
            full = self.pokemonutils.find_full_name_for_slug(raw_name)
            if full:
                base = full.lower().replace("_", "-")
        return base

    async def _get_server_config(self, sid: int) -> dict:
        if sid in self.server_config_cache:
            self.server_config_cache.move_to_end(sid)
            return self.server_config_cache[sid]
        config = await self.pokemonutils.get_server_config(sid)
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
        alt = self.alt_cache.get(base_name.lower()) or ""
        types = self.type_cache.get(base_name.lower()) or []
        name = self.pokemonutils.format_name(base_name).replace("_", " ").title()

        try:
            await self.bot.loop.run_in_executor(
                self.process_executor,
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
            self._cleanup_temp_file(temp_path)
            return None

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
                    self.bot.loop.create_task(self._process_spawn(message, img_url))

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
            async with aiofiles.open(self.pokemonutils.pokemon_description_file, "r", encoding="utf-8") as f:
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
                url = await self._handle_image_upload(slug)
                return bool(url)

            semaphore = asyncio.Semaphore(self.WORKER_COUNT)
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

    @commands.command(name="health_check", hidden=True)
    @commands.is_owner()
    async def health_check(self, ctx: commands.Context) -> None:
        cache_size = len(self.image_url_cache)
        total_pokemon = len(self._pokemon_ids)
        ram_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        await ctx.send(
            f"✅ Health Check:\n"
            f"• Image Cache: {cache_size}/{total_pokemon} Pokémon\n"
            f"• RAM Usage: {ram_mb:.1f} MB\n"
            f"• Processed: {self.processed_count} spawns\n"
            f"• Testing: {'Yes' if self.testing else 'No'}"
        )

    async def _pressure_loop(self, ctx: commands.Context, period: int) -> None:
        def get_ram():
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

        initial_ram = get_ram()
        logger.info(f"Initial RAM: {initial_ram} MB")

        i = 0
        delay_max = 0.5
        start_time = time.time()

        while self.testing:
            url = random.choice(self.test_images)
            message = ctx.message
            self.bot.loop.create_task(self._process_spawn(message, url))

            await asyncio.sleep(random.uniform(0, delay_max))

            i += 1

            if i % 10 == 0:
                delay_max = max(0.005, delay_max * 0.95)

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

        if self.test_images is None:
            self.test_images = []
            async def download_image(url, i):
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

            await asyncio.gather(*(download_image(url, i) for i, url in enumerate(self.TEST_SPAWN_URLS)))

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
        if self.pressure_task:
            await self.pressure_task
            await asyncio.sleep(0.05)

        def get_ram():
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

        final_ram = get_ram()
        print(f"Pressure test stopped. Final RAM: {final_ram} MB")
        await ctx.send("Pressure test stopped. Check logs for final RAM usage and processing times.")

    def cog_unload(self) -> None:
        self.testing = False
        if self.test_images:
            for path in self.test_images:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
        self.thread_executor.shutdown(wait=False, cancel_futures=True)
        self.process_executor.shutdown(wait=False, cancel_futures=True)
        self.bot.loop.run_until_complete(self._save_image_urls())

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PoketwoSpawnDetector(bot))