import aiofiles, aiohttp, asyncio, cloudinary, cloudinary.uploader, gc, io, json, logging, os, psutil, random, resource, tempfile, time, traceback, weakref
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache, partial
from motor.motor_asyncio import AsyncIOMotorClient
from bot.cogs.pokemon import PoketwoCommands
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from submodules.poketwo_autonamer.predict import Prediction
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonSpawnView, PokemonUtils
from utils.subcogs.pokemon import MongoHelper


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

class PoketwoSpawnDetector(commands.Cog):

    TARGET_BOT_ID = 716390085896962058
    MAX_DYNAMIC_CACHE_SIZE = 50  # Reduced for lighter memory footprint
    MAX_STATIC_CACHE_SIZE = 5000  # Reduced but still sufficient for common pokemons
    MAX_PING_CACHE_SIZE = 25  # Reduced
    WORKER_COUNT = 1
    BATCH_SIZE = 1
    PERIODIC_SAVE_INTERVAL = 60  # Slightly increased to reduce I/O frequency
    SPAM_WINDOW_SECONDS = 60
    SPAM_THRESHOLD = 50
    SPAWN_DIR = "data/events/poketwo_spawns/spawns"
    IMAGE_URLS_PATH = "data/events/poketwo_spawns/image_urls.json"
    CONFIG_PATH = "data/events/poketwo_spawns/image/config.json"
    SUCCESS_EMOJI = "<:green:1261639410181476443>"
    ERROR_EMOJI = "<:red:1261639413943762944>"
    CROSS_EMOJI = "❌"
    RAM_THRESHOLD_MB = 450  # Adjusted closer to 512MB limit
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
        self.predictor = None
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
        self.full_pokemon_data = None
        self.image_builder = PokemonImageBuilder()
        self._pokemon_ids = None

        self.pred_cache = lru_cache(maxsize=self.MAX_DYNAMIC_CACHE_SIZE)(self._predict_pokemon)
        self.base_cache = lru_cache(maxsize=self.MAX_DYNAMIC_CACHE_SIZE)(self._get_base_name)
        self.server_config_cache = OrderedDict()
        self.ping_cache = OrderedDict()
        self.desc_cache = weakref.WeakKeyDictionary()  # Use weakref for auto-cleanup
        self.type_cache = weakref.WeakKeyDictionary()
        self.alt_cache = weakref.WeakKeyDictionary()
        self.image_url_cache = OrderedDict()
        self.test_images = None
        self.channel_stats = weakref.WeakKeyDictionary()  # Use weakref for channels

        self.default_ext = self._get_default_ext()
        self.queue = asyncio.Queue(maxsize=1)
        self.thread_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="spawn_worker")
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

        self.bot.loop.create_task(self._start_workers_and_saver())
        self.bot.loop.create_task(self._periodic_cleanup())
        self.bot.loop.create_task(self._gentle_ram_monitor())

    def _get_ram_mb(self) -> float:
        try:
            return psutil.Process().memory_info().rss / 1024 / 1024
        except:
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    async def _gentle_ram_monitor(self):
        while True:
            await asyncio.sleep(60)  # Less frequent checks
            ram = self._get_ram_mb()
            if ram > self.RAM_THRESHOLD_MB:
                logger.warning(f"Moderate RAM usage ({ram:.1f} MB): Gentle cleanup")
                self._gentle_cleanup()
                gc.collect()

    def _gentle_cleanup(self):
        # Trim caches gently instead of full clear
        if len(self.server_config_cache) > self.MAX_DYNAMIC_CACHE_SIZE // 2:
            self.server_config_cache.clear()  # Configs are lightweight, safe to clear
        if len(self.ping_cache) > self.MAX_PING_CACHE_SIZE // 2:
            self.ping_cache.clear()
        # Weakref dicts auto-clean, no need to touch
        # LRU caches auto-evict

    async def _start_workers_and_saver(self):
        self.bot.loop.create_task(self._worker())
        self.bot.loop.create_task(self._periodic_save())

    async def _periodic_cleanup(self):
        while True:
            await asyncio.sleep(900)  # Increased interval for less overhead
            # Weakref handles most cleanup; just trim OrderedDicts if oversized
            while len(self.image_url_cache) > self.MAX_STATIC_CACHE_SIZE:
                self.image_url_cache.popitem(last=False)
            logger.debug(f"Trimmed image cache to {len(self.image_url_cache)} items")

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
                        while len(self.image_url_cache) > self.MAX_STATIC_CACHE_SIZE:
                            self.image_url_cache.popitem(last=False)
            except Exception as e:
                logger.error(f"Failed to load image URLs: {e}")

    def _get_image_url(self, base_name: str) -> str | None:
        return self.image_url_cache.get(base_name.lower())

    def _add_image_url(self, base_name: str, url: str) -> None:
        base_name_lower = base_name.lower()
        self.image_url_cache[base_name_lower] = url
        while len(self.image_url_cache) > self.MAX_STATIC_CACHE_SIZE:  # Use while for safety
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
            # Limit data size by sampling if too large (rare)
            data_dict = dict(self.image_url_cache)
            if len(json.dumps(data_dict, ensure_ascii=False)) > 1_000_000:  # ~1MB limit
                data_dict = dict(list(data_dict.items())[-self.MAX_STATIC_CACHE_SIZE:])
            data = json.dumps(data_dict, indent=2, ensure_ascii=False)
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
                    del message, image_url  # Explicit del for locals
                    if gc.is_tracked(self):  # Gentle GC trigger
                        gc.collect(1)  # Generation 1 only, lighter
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue get error: {type(e).__name__}: {e}")
                traceback.print_exc()
                await asyncio.sleep(1)
                gc.collect(1)

    async def _process_spawn(self, msg: discord.Message, img_url: str):
        try:
            if self._get_ram_mb() > self.RAM_THRESHOLD_MB * .75: 
                self._gentle_cleanup(); gc.collect(1)
            s = time.time(); rn, cf = self.pred_cache(img_url); del img_url
            bn = self.base_cache(rn).lower(); cfv = self._parse_confidence(cf); low = cfv < 30.0; del rn, cf
            if not msg.guild: logger.warning("No guild; skip."); return
            sid = msg.guild.id; sc = await self._get_server_config(sid); self._lazy_load_pokemon_data()
            d, dx = self._get_description(bn)[:2]; dx = self._pokemon_ids.get(bn, dx); k = (sid, bn)
            if k not in self.ping_cache:
                scoll, tp, qp = await asyncio.gather(
                    self.pokemon_utils.get_ping_users(msg.guild, bn),
                    self.pokemon_utils.get_type_ping_users(msg.guild, bn),
                    self.pokemon_utils.get_quest_ping_users(msg.guild, bn))
                self.ping_cache[k] = (scoll, tp, qp)
                while len(self.ping_cache) > self.MAX_PING_CACHE_SIZE: 
                    self.ping_cache.popitem(last=False)
            else: scoll, tp, qp = self.ping_cache[k]
            sp, cp = scoll; r, reg = getattr(self.pokemon_utils, "_special_names", ([], []))
            roles = self._get_special_roles(sc, bn, r, reg)
            pmsg, _ = await self.pokemon_utils.format_messages(
                bn.title(), tp, qp, sp, cp, " ".join(roles), f"{cfv:.2f}%", dx, d, "", low)
            view = PokemonSpawnView(slug=bn, pokemon_data=self.full_pokemon_data, pokemon_utils=self.pokemon_utils)
            url = self._get_image_url(bn) or await self._handle_image_upload(bn)
            if not self.testing:
                if url:
                    try:
                        # Use temp file instead of BytesIO to avoid full load in memory
                        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                            temp_path = tmp.name
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url) as resp:
                                if resp.status == 200:
                                    async with aiofiles.open(temp_path, 'wb') as f:
                                        async for chunk in resp.content.iter_chunked(8192):  # Chunked read
                                            await f.write(chunk)
                                    f = discord.File(temp_path, "prediction.png")
                                    await msg.channel.send(content=pmsg, file=f, reference=msg, view=view)
                                    os.unlink(temp_path)  # Immediate cleanup
                                else:
                                    logger.warning(f"Failed to fetch image from {url}: status {resp.status}")
                                    await msg.channel.send(content=pmsg, reference=msg, view=view)
                    except Exception as e:
                        logger.error(f"Error fetching/sending image from {url}: {e}")
                        await msg.channel.send(content=pmsg, reference=msg, view=view)
                else:
                    await msg.channel.send(content=pmsg, reference=msg, view=view)
                await asyncio.sleep(0.05)
            else:
                logger.info(f"Test spawn {bn}")
            self.processed_count += 1; logger.info(f"Done {bn} | RAM {self._get_ram_mb():.1f}MB | {time.time() - s:.2f}s")
        except MemoryError: self._handle_memory_error(msg)
        except Exception as e: self._handle_processing_error(msg, e)
        finally: gc.collect(1)

    def _get_description(self, base_name: str):
        if base_name not in self.desc_cache:
            self._lazy_load_pokemon_data()
            desc_data = self.pokemon_utils.get_description(base_name) or ("", "???")
            self.desc_cache[base_name] = desc_data
        return self.desc_cache[base_name]

    def _get_types(self, base_name: str):
        if base_name not in self.type_cache:
            self._lazy_load_pokemon_data()
            types = self.pokemon_utils.get_pokemon_types(base_name)
            self.type_cache[base_name] = types
        return self.type_cache[base_name]

    def _get_alt(self, base_name: str):
        if base_name not in self.alt_cache:
            self._lazy_load_pokemon_data()
            alt = self.pokemon_utils.get_best_normal_alt_name(base_name) or ""
            self.alt_cache[base_name] = alt
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
        logger.error("MemoryError: Gentle cleanup")
        self._gentle_cleanup()
        gc.collect(1)
        try:
            asyncio.create_task(message.channel.send(f"{self.ERROR_EMOJI} Memory issue, cleared caches", reference=message))
        except Exception:
            logger.exception("Failed to notify about memory error.")

    def _handle_processing_error(self, message: discord.Message, e: Exception) -> None:
        logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
        traceback.print_exc()
        self._gentle_cleanup()
        gc.collect(1)
        try:
            asyncio.create_task(message.channel.send(f"{self.ERROR_EMOJI} Failed to process spawn", reference=message))
        except Exception:
            logger.exception("Failed to notify about spawn processing error.")

    def _predict_pokemon(self, image_url: str) -> tuple[str, str]:
        if self.predictor is None:
            self.predictor = Prediction()
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
                del content  # Explicit del if exists
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
        while len(self.server_config_cache) > self.MAX_DYNAMIC_CACHE_SIZE:
            self.server_config_cache.popitem(last=False)
        return self.server_config_cache[sid]

    async def _handle_image_upload(self, base_name: str) -> str | None:
        if self._get_ram_mb() > self.RAM_THRESHOLD_MB * 0.6:  # Earlier but gentler
            self._gentle_cleanup()
            gc.collect(1)
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
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            temp_path = tmp.name
        alt = self._get_alt(base_name)
        types = self._get_types(base_name)
        name = self.pokemon_utils.format_name(base_name).replace("_", " ").title()

        try:
            await self.bot.loop.run_in_executor(
                self.thread_executor,
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
            return url
        except Exception as e:
            logger.error(f"Image create/upload failed for {base_name}: {e}")
            return None
        finally:
            self._cleanup_temp_file(temp_path)
            gc.collect(1)

    def _get_temp_path(self, base_name: str, ext: str) -> str:
        return os.path.join(tempfile.gettempdir(), f"{base_name}.{ext}")

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

    @commands.command(name="list_spawn_images", hidden=True)
    @commands.is_owner()
    async def list_spawn_images(self, ctx: commands.Context) -> None:
        await ctx.defer()
        if not self.image_url_cache:
            return await ctx.send("❌ No spawn images cached yet. Run `generate_spawns` first.")
        
        table_lines = ["| Pokémon Slug | Image URL |", "|-------------|-----------|"]
        for slug, url in list(self.image_url_cache.items())[:50]:
            table_lines.append(f"| `{slug}` | {url} |")
        table = "\n".join(table_lines)
        
        if len(table) > 1900:
            parts = [table[:1900], table[1900:]]
            for part in parts:
                await ctx.send(f"```{part}```")
        else:
            await ctx.send(f"**Current Spawn Image Mapping** (showing first 50):\n```{table}```")
        await ctx.send(f"Total cached: {len(self.image_url_cache)} images.")

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
            success_urls = {}
            async def process_slug(slug: str):
                self._gentle_cleanup()
                gc.collect(1)
                url = await self._handle_image_upload(slug)
                gc.collect(1)
                if url:
                    success_urls[slug] = url
                return bool(url)

            await ctx.send(f"Starting {'regeneration' if regenerate else 'generation'} of {len(work_items)} images...")

            for i, item in enumerate(work_items):
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
                    if (i + 1) % 10 == 0:
                        await ctx.send(f"Progress: {i + 1}/{len(work_items)} (Success: {success_count}, Errors: {error_count})")
                    await asyncio.sleep(0.2)  # Slightly longer sleep for stability

            action = "Regenerated" if regenerate else "Generated"
            await ctx.send(f"✅ {action} {success_count} spawn images. ❌ {error_count} failed.")

            if success_urls:
                table_lines = ["| Pokémon Slug | Image URL |", "|-------------|-----------|"]
                for slug, url in list(success_urls.items())[:20]:
                    table_lines.append(f"| `{slug}` | {url} |")
                table = "\n".join(table_lines)
                await ctx.send(f"**Newly {action.lower()} Mapping** (first 20):\n```{table}```")
                if len(success_urls) > 20:
                    await ctx.send(f"... and {len(success_urls) - 20} more. Use `list_spawn_images` for full list.")
        except Exception as e:
            logger.error(f"Spawn image handler failure: {type(e).__name__}: {e}")
            await ctx.send(f"{self.ERROR_EMOJI} Error: {e}")

    async def _pressure_loop(self, ctx: commands.Context, period: int) -> None:
        def get_ram():
            return self._get_ram_mb()

        initial_ram = get_ram()
        logger.info(f"Initial RAM: {initial_ram} MB")

        i = 0
        delay = 2.0
        start_time = time.time()

        while self.testing:
            if self.queue.full():
                await asyncio.sleep(0.5)
                continue
            url = random.choice(self.test_images)
            message = ctx.message
            try:
                self.queue.put_nowait((message, url))
            except asyncio.QueueFull:
                await asyncio.sleep(0.1)
                continue

            await asyncio.sleep(delay)

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
        
        if self.test_images is None:
            self.test_images = []
            for i, url in enumerate(self.TEST_SPAWN_URLS):
                try:
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        path = tmp.name
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                async with aiofiles.open(path, 'wb') as f:
                                    async for chunk in resp.content.iter_chunked(8192):
                                        await f.write(chunk)
                                self.test_images.append(path)
                    logger.info(f"Downloaded test image {i}")
                except Exception as e:
                    logger.error(f"Failed to download {url}: {e}")
                    if 'path' in locals():
                        try:
                            os.unlink(path)
                        except:
                            pass
        
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
            await asyncio.sleep(0.1)
        
        final_ram = self._get_ram_mb()
        print(f"Pressure test stopped. Final RAM: {final_ram} MB")
        await ctx.send("Pressure test stopped. Check logs for final RAM usage and processing times.")

    def cog_unload(self) -> None:
        self.testing = False
        self._gentle_cleanup()
        gc.collect(1)
        if self.test_images:
            for path in self.test_images:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass
            self.test_images = None
        self.thread_executor.shutdown(wait=False, cancel_futures=True)
        if hasattr(self, 'predictor'):
            self.predictor = None  # Allow model to be GC'd
        self.full_pokemon_data = None
        self._pokemon_ids = None
        self.bot.loop.run_until_complete(self._save_image_urls())
        gc.collect(2)  # Final full GC on unload

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PoketwoSpawnDetector(bot))