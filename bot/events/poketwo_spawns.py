import os, asyncio, logging, json, traceback, csv
import cloudinary
import cloudinary.uploader
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import aiofiles
from tqdm.asyncio import tqdm_asyncio
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import MongoHelper
from bot.cogs.pokemon import PoketwoCommands
from motor.motor_asyncio import AsyncIOMotorClient
from functools import partial
from collections import OrderedDict

logger = logging.getLogger(__name__)
_thread_executor = ThreadPoolExecutor(max_workers=32)  # Increased for IO
_process_executor = ProcessPoolExecutor(max_workers=(os.cpu_count() or 4) * 2)  # Increased for CPU

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
        self.pred_cache = OrderedDict()
        self.base_cache = {}
        self.server_cache = OrderedDict()
        self.desc_cache = {}
        self.type_cache = {}
        self.alt_cache = {}
        self.queue = asyncio.Queue()  # Unbounded for reliability
        self.worker_count = worker_count or min((os.cpu_count() or 4) * 16, 256)  # Higher for speed
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"
        self.max_cache_size = 20000  # Increased

        # Configure Cloudinary
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )

        self.spawn_dir = "data/events/poketwo_spawns/spawns"

        # Load image URLs
        self.image_urls = {}
        url_file = "data/events/poketwo_spawns/image_urls.json"
        if os.path.exists(url_file):
            try:
                with open(url_file, 'r', encoding='utf-8') as f:
                    self.image_urls = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load image_urls.json: {e}")

        # Auto-upload existing and generate missing on init

        # Load config for default GIF/PNG
        try:
            with open("data/events/poketwo_spawns/image/config.json", "r", encoding="utf-8") as f:
                self.config_data = json.load(f)
            bg_url = self.config_data.get("background_url")
            self.default_ext = "gif" if bg_url and bg_url.lower().endswith(".gif") else "png"
        except Exception:
            self.default_ext = "png"
            logger.warning("Failed to read config.json, defaulting to PNG.")

        for _ in range(self.worker_count):
            self.bot.loop.create_task(self._worker())

        asyncio.create_task(self._pickellize_all())
        asyncio.create_task(self._monitor_queue())  # New: Monitor queue size
        self.bot.loop.create_task(self.auto_prepare_images())

    async def auto_prepare_images(self):
        await self.upload_all_existing()
        if len(self.image_urls) < len(self._pokemon_ids):
            await self.generate_spawns_internal()

    async def _monitor_queue(self):
        while True:
            size = self.queue.qsize()
            if size > 5000:
                logger.warning(f"Queue size high: {size} - Consider more workers or optimizations.")
            await asyncio.sleep(60)  # Check every minute

    def _evict_oldest(self, cache):
        if len(cache) > self.max_cache_size:
            cache.popitem(last=False)

    async def upload_all_existing(self):
        if not os.path.exists(self.spawn_dir):
            logger.warning(f"Spawn directory does not exist: {self.spawn_dir}")
            return

        files = [f for f in os.listdir(self.spawn_dir) if f.lower().endswith(('.gif', '.png'))]
        if not files:
            logger.info("No existing spawn images to upload.")
            return

        loop = asyncio.get_running_loop()

        async def upload_one(file):
            base_name, _ = os.path.splitext(file)
            base_name = base_name.lower()
            if base_name in self.image_urls:
                return True  # Already exists, skip
            full_path = os.path.join(self.spawn_dir, file)
            try:
                response = await loop.run_in_executor(
                    _thread_executor,  # I/O bound, use threads
                    partial(cloudinary.uploader.upload, full_path, **{"folder": "poketwo_spawns", "public_id": base_name, "overwrite": True})
                )
                url = response['secure_url']
                self.image_urls[base_name] = url
                return True
            except Exception as e:
                logger.error(f"Failed to upload existing image {file}: {e}")
                return False

        results = await tqdm_asyncio.gather(*[upload_one(f) for f in files], desc="Uploading existing spawn images")
        success_count = sum(results)
        logger.info(f"Uploaded {success_count} existing spawn images to Cloudinary.")

        # Save updated JSON
        try:
            os.makedirs("data/events/poketwo_spawns", exist_ok=True)
            async with aiofiles.open("data/events/poketwo_spawns/image_urls.json", 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.image_urls, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save image_urls.json after uploading existing: {e}")

    async def _worker(self):
        while True:
            try:
                message, image_url = await self.queue.get()
                await self.process_spawn(message, image_url)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
                traceback.print_exc()
            finally:
                self.queue.task_done()

    async def _pickellize_all(self):
        for slug in self._pokemon_ids:
            self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)
            desc, dex = "", self._pokemon_ids.get(slug, "???")
            desc_data = self.pokemon_utils.get_description(slug)
            if desc_data:
                desc, dex = desc_data[:2]
            self.desc_cache[slug] = (desc, dex)
            self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
            self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""

    async def process_spawn(self, message, image_url):
        try:
            loop = asyncio.get_running_loop()

            # Predict name and confidence (CPU-bound, use process)
            if (pred := self.pred_cache.get(image_url)):
                raw_name, conf = pred
            else:
                raw_name, conf = await loop.run_in_executor(_process_executor, self.predictor.predict, image_url)
                self.pred_cache[image_url] = (raw_name, conf)
                self.pred_cache.move_to_end(image_url)
                self._evict_oldest(self.pred_cache)

            # Base name lookup
            base_name = self.base_cache.get(raw_name)
            if not base_name:
                base_name = self.pokemon_utils.get_base_pokemon_name(raw_name)
                if base_name not in self._pokemon_ids:
                    base_name = self.pokemon_utils.find_full_name_for_slug(raw_name).lower().replace("_", "-")
                self.base_cache[raw_name] = base_name

            conf_float = float(str(conf).strip().rstrip("%"))
            low_conf = conf_float < 30

            # Server config with LRU
            sid = message.guild.id
            server_config = self.server_cache.get(sid)
            if server_config is None:
                server_config = await self.pokemon_utils.get_server_config(sid)
                self.server_cache[sid] = server_config
                self.server_cache.move_to_end(sid)
                self._evict_oldest(self.server_cache)

            shiny_collect, type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_ping_users(message.guild, base_name),
                self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
            )
            shiny_pings, collect_pings = shiny_collect

            rare, regional = self.pokemon_utils._special_names
            special_roles = [
                f"<@&{server_config['rare_role']}>" for r in rare if r in base_name
            ] + [
                f"<@&{server_config['regional_role']}>" for r in regional if r in base_name
            ] if server_config else []

            desc, dex = self.desc_cache.get(base_name, ("", "???"))
            dex = self._pokemon_ids.get(base_name, dex)

            ping_msg, _ = await self.pokemon_utils.format_messages(
                raw_name, type_pings, quest_pings, shiny_pings, collect_pings,
                " ".join(special_roles), f"{conf_float:.2f}%", dex, desc,
                image_url, low_conf
            )

            view = PokemonSpawnView(slug=base_name, pokemon_data=self.full_pokemon_data, pokemon_utils=self.pokemon_utils)

            # Get image URL from cache or generate/upload
            url = self.image_urls.get(base_name)
            if not url:
                logger.warning(f"Missing URL for {base_name} - Fallback to generation")
                # Check if existing file in spawn_dir
                for ext in ['.gif', '.png']:
                    local_path = os.path.join(self.spawn_dir, f"{base_name}{ext}")
                    if os.path.exists(local_path):
                        try:
                            response = await loop.run_in_executor(
                                _thread_executor,  # I/O bound
                                partial(cloudinary.uploader.upload, local_path, **{"folder": "poketwo_spawns", "public_id": base_name, "overwrite": True})
                            )
                            url = response['secure_url']
                            self.image_urls[base_name] = url
                            break
                        except Exception as e:
                            logger.error(f"Failed to upload existing image for {base_name}: {e}")
                            traceback.print_exc()

                if not url:
                    # Generate new if no existing (CPU-bound, use process)
                    ext = self.default_ext
                    temp_path = f"/tmp/{base_name}.{ext}"
                    name = self.pokemon_utils.format_name(base_name).replace("_", " ").title()
                    alt = self.alt_cache.get(base_name, "")
                    types = self.type_cache.get(base_name, [])
                    try:
                        await loop.run_in_executor(
                            _process_executor,
                            self.image_builder.create_image,
                            base_name, name, alt, types, None, temp_path, ext.upper()
                        )
                        response = await loop.run_in_executor(
                            _thread_executor,  # I/O bound
                            partial(cloudinary.uploader.upload, temp_path, **{"folder": "poketwo_spawns", "public_id": base_name, "overwrite": True})
                        )
                        url = response['secure_url']
                        self.image_urls[base_name] = url
                        os.remove(temp_path)
                    except Exception as e:
                        logger.error(f"Failed to create/upload image for {base_name}: {e}")
                        traceback.print_exc()
                        return await message.channel.send(content=ping_msg, reference=message, view=view)

                # Save updated JSON (ephemeral on Render; run locally to persist)
                try:
                    os.makedirs("data/events/poketwo_spawns", exist_ok=True)
                    async with aiofiles.open("data/events/poketwo_spawns/image_urls.json", 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(self.image_urls, indent=2))
                except Exception as e:
                    logger.warning(f"Failed to save image_urls.json: {e}")

            # Send with embed
            embed = discord.Embed()
            embed.set_image(url=url)
            await message.channel.send(
                content=ping_msg,
                embed=embed,
                reference=message,
                view=view
            )
        except Exception as e:
            logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
            traceback.print_exc()
            await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.target_id or ut:
            return
        for e in message.embeds:
            if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                await self.queue.put((message, e.image.url))  # No try/except, unbounded

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        try:
            def extract_image_from_message(msg: discord.Message):
                if msg.attachments: return msg.attachments[0].url
                if msg.embeds:
                    embed = msg.embeds[0]
                    if embed.image and embed.image.url: return embed.image.url
                    if embed.thumbnail and embed.thumbnail.url: return embed.thumbnail.url
                return None

            message = ctx.message

            if not image_url:
                image_url = extract_image_from_message(message)

            if not image_url and message.reference:
                try:
                    ref = await ctx.channel.fetch_message(message.reference.message_id)
                    image_url = extract_image_from_message(ref)
                    if not image_url and ref.reference:
                        ref2 = await ctx.channel.fetch_message(ref.reference.message_id)
                        image_url = extract_image_from_message(ref2)
                except Exception as e:
                    logger.error(f"Failed to fetch referenced messages: {e}")
                    traceback.print_exc()

            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")

            await self.process_spawn(message, image_url)

        except Exception as e:
            logger.error(f"Prediction error: {type(e).__name__}: {e}")
            traceback.print_exc()
            await ctx.send(f"{self.error_emoji} Failed to process prediction.\n```\n{e}\n```")

    # ------------------------------------------------------------------
    # COMMAND: generate_spawns
    # ------------------------------------------------------------------
    async def generate_spawns_internal(self):
        # Internal version of generate_spawns, no ctx
        try:
            loop = asyncio.get_running_loop()

            try:
                async with aiofiles.open(self.pokemon_utils.pokemon_description_file, "r", encoding="utf-8") as f:
                    reader = csv.DictReader((await f.read()).splitlines())
            except Exception as e:
                traceback.print_exc()
                logger.error(f"Failed to read CSV: {e}")
                return

            file_ext = self.default_ext

            # Collect missing items only
            work_items = []
            for row in reader:
                slug = (row.get("slug") or row.get("name") or "").strip().lower()
                if slug and slug not in self.image_urls:
                    name = self.pokemon_utils.format_name(slug).replace("_", " ").title()
                    alt = self.alt_cache.get(slug, "")
                    types = self.type_cache.get(slug, [])
                    work_items.append((slug, name, alt, types))

            if not work_items:
                logger.info("All spawn images pre-generated.")
                return

            # Increase workers for parallelism
            pe = ProcessPoolExecutor(max_workers=(os.cpu_count() or 4) * 4)

            async def build_and_upload_one(item):
                s, n, a, t = item
                temp_path = f"/tmp/{s}.{file_ext}"
                try:
                    # Generate image
                    await loop.run_in_executor(pe, self.image_builder.create_image, s, n, a, t, None, temp_path, file_ext.upper())
                    # Upload with overwrite
                    response = await loop.run_in_executor(
                        _thread_executor,
                        partial(cloudinary.uploader.upload, temp_path, **{"folder": "poketwo_spawns", "public_id": s, "overwrite": True})
                    )
                    url = response['secure_url']
                    self.image_urls[s] = url
                    os.remove(temp_path)
                    return url
                except Exception as e:
                    logger.error(f"Failed for {s}: {e}")
                    return e

            results = await tqdm_asyncio.gather(*[build_and_upload_one(i) for i in work_items], desc="Pre-generating spawns")
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            logger.info(f"Pre-generated {success_count} spawn images.")

            # Save updated JSON (ephemeral on Render; run locally to persist)
            try:
                os.makedirs("data/events/poketwo_spawns", exist_ok=True)
                async with aiofiles.open("data/events/poketwo_spawns/image_urls.json", 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(self.image_urls, indent=2))
            except Exception as e:
                logger.warning(f"Failed to save image_urls.json: {e}")

        except Exception as e:
            traceback.print_exc()
            logger.error(f"Pre-generation error: {e}")

    @commands.command(name="generate_spawns", hidden=True)
    async def generate_spawns(self, ctx):
        try:
            await ctx.defer()
            await self.generate_spawns_internal()
            await ctx.send("✅ Pre-generation complete.")
        except Exception as e:
            traceback.print_exc()
            await ctx.send(f"{self.error_emoji} Error during spawn generation: {e}")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
