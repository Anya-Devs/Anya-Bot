import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import aiofiles
import aiohttp
from cachetools import LRUCache
from discord.ext import commands
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import MongoHelper
from bot.cogs.pokemon import PoketwoCommands
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)
_thread_executor = ThreadPoolExecutor(max_workers=max(os.cpu_count() or 4, 8))

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

        # Caches with size limits
        self.file_cache = LRUCache(maxsize=1000)
        self.img_bytes_cache = LRUCache(maxsize=1000)
        self.pred_cache = LRUCache(maxsize=5000)
        self.base_cache = LRUCache(maxsize=1000)
        self.server_cache = LRUCache(maxsize=100)
        self.ping_cache = LRUCache(maxsize=500)
        self.desc_cache = LRUCache(maxsize=1000)
        self.type_cache = LRUCache(maxsize=1000)
        self.alt_cache = LRUCache(maxsize=1000)

        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.server_queues = {}  # Per-server queues
        self.worker_count = worker_count or max((os.cpu_count() or 4) * 2, 16)
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

        # Preload existing images
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path) and os.path.getsize(path) > 0:
                self.file_cache[slug] = path

        # Start workers for each server queue
        self.bot.loop.create_task(self._start_workers())
        asyncio.create_task(self._preload_data())

    async def _start_workers(self):
        """Start workers for each server queue."""
        while True:
            for guild_id in list(self.server_queues.keys()):
                queue = self.server_queues[guild_id]
                for _ in range(self.worker_count):
                    self.bot.loop.create_task(self._worker(guild_id, queue))
            await asyncio.sleep(60)  # Periodically check for new queues

    async def _worker(self, guild_id, queue):
        """Process tasks from a server-specific queue."""
        while True:
            try:
                message, image_url = await asyncio.wait_for(queue.get(), timeout=30.0)
                async with aiohttp.ClientSession() as session:
                    await self._process_spawn_with_retry(message, image_url, session)
            except asyncio.TimeoutError:
                continue  # Continue checking queue
            except Exception as e:
                logger.error(f"Worker error for guild {guild_id}: {type(e).__name__}: {e}")
            finally:
                queue.task_done()

    async def _preload_data(self):
        """Preload Pokémon data and images."""
        loop = asyncio.get_running_loop()
        tasks = []

        for slug in self._pokemon_ids:
            self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)
            desc, dex = self.pokemon_utils.get_description(slug) or ("", "???")
            self.desc_cache[slug] = (desc, dex)
            self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
            self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""

            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if slug not in self.file_cache:
                tasks.append(loop.run_in_executor(
                    _thread_executor,
                    self.image_builder.create_image,
                    slug,
                    self.pokemon_utils.format_name(slug).replace("_", " ").title(),
                    self.alt_cache[slug],
                    self.type_cache[slug],
                    None,
                    path,
                    "PNG",
                ))
                self.file_cache[slug] = path

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        read_tasks = []
        for slug, path in self.file_cache.items():
            read_tasks.append(self._read_file(path, slug))

        if read_tasks:
            await asyncio.gather(*read_tasks, return_exceptions=True)

        logger.info("Preloaded all Pokémon data and images.")

    async def _read_file(self, path, slug):
        """Read image file asynchronously."""
        try:
            async with aiofiles.open(path, "rb") as f:
                self.img_bytes_cache[slug] = await f.read()
        except Exception as e:
            logger.warning(f"Failed to read image {path}: {e}")

    async def _download_image(self, url, session, retries=3):
        """Download image with retry logic."""
        for attempt in range(retries):
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return await response.read()
                    logger.warning(f"Failed to download {url}: Status {response.status}")
            except Exception as e:
                logger.warning(f"Download attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return None

    async def _process_spawn_with_retry(self, message, image_url, session, retries=3):
        """Process a spawn with retry logic."""
        for attempt in range(retries):
            try:
                await self.process_spawn(message, image_url, session)
                return
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for spawn {image_url}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        await message.channel.send(
            f"{self.error_emoji} Failed to process spawn after {retries} attempts",
            reference=message
        )

    async def process_spawn(self, message, image_url, session):
        """Process a Pokémon spawn."""
        loop = asyncio.get_running_loop()

        # Prediction
        pred = self.pred_cache.get(image_url)
        if not pred:
            raw_name, conf = await loop.run_in_executor(
                _thread_executor, self.predictor.predict, image_url
            )
            self.pred_cache[image_url] = (raw_name, float(str(conf).strip().rstrip("%")))

        raw_name, conf_float = self.pred_cache[image_url]
        low_conf = conf_float < 30

        # Base name lookup
        base_name = self.base_cache.get(raw_name)
        if not base_name:
            base_name = self.pokemon_utils.get_base_pokemon_name(raw_name)
            if base_name not in self._pokemon_ids:
                base_name = self.pokemon_utils.find_full_name_for_slug(raw_name).lower().replace("_", "-")
            self.base_cache[raw_name] = base_name

        # Server config
        sid = message.guild.id
        server_config = self.server_cache.get(sid)
        if not server_config:
            server_config = await self.pokemon_utils.get_server_config(sid)
            self.server_cache[sid] = server_config

        # Pings
        pings = self.ping_cache.get((sid, base_name))
        if not pings:
            shiny_collect, type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_ping_users(message.guild, base_name),
                self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
            )
            shiny_pings, collect_pings = shiny_collect
            pings = (type_pings, quest_pings, shiny_pings, collect_pings)
            self.ping_cache[(sid, base_name)] = pings

        type_pings, quest_pings, shiny_pings, collect_pings = pings

        # Special roles
        rare, regional = self.pokemon_utils._special_names
        special_roles = []
        if server_config.get("rare_role"):
            special_roles += [f"<@&{server_config['rare_role']}>" for r in rare if r in base_name]
        if server_config.get("regional_role"):
            special_roles += [f"<@&{server_config['regional_role']}>" for r in regional if r in base_name]

        # Description and dex
        desc, dex = self.desc_cache.get(base_name, ("", "???"))
        dex = self._pokemon_ids.get(base_name, dex)

        # Format message
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

        # Image handling
        img_bytes = self.img_bytes_cache.get(base_name)
        view = PokemonSpawnView(
            slug=base_name,
            pokemon_data=self.pokemon_utils.load_full_pokemon_data(),
            pokemon_utils=self.pokemon_utils
        )

        if not img_bytes:
            path = os.path.join(self.spawn_dir, f"{base_name}.png")
            if base_name not in self.file_cache:
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

            try:
                async with aiofiles.open(path, "rb") as f:
                    img_bytes = await f.read()
                self.img_bytes_cache[base_name] = img_bytes
            except:
                img_bytes = await self._download_image(image_url, session)
                if img_bytes:
                    async with aiofiles.open(path, "wb") as f:
                        await f.write(img_bytes)
                    self.img_bytes_cache[base_name] = img_bytes
                else:
                    return await message.channel.send(
                        content=ping_msg,
                        reference=message,
                        view=view
                    )

        # Send response
        try:
            await message.channel.send(
                content=ping_msg,
                file=discord.File(fp=BytesIO(img_bytes), filename=f"{base_name}.png"),
                reference=message,
                view=view
            )
        except discord.errors.HTTPException as e:
            logger.error(f"Discord send error: {e}")
            await asyncio.sleep(1)  # Respect rate limits
            await message.channel.send(
                content=ping_msg,
                reference=message,
                view=view
            )

    @commands.command(name="generate_spawns", hidden=True)
    async def generate_all_spawn_images(self, ctx):
        """Generate all missing or invalid spawn images."""
        os.makedirs(self.spawn_dir, exist_ok=True)
        missing_or_empty = [
            slug for slug in self._pokemon_ids
            if slug not in self.file_cache or not os.path.exists(self.file_cache[slug]) or os.path.getsize(self.file_cache[slug]) == 0
        ]

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

        read_tasks = []
        for slug in missing_or_empty:
            read_tasks.append(self._read_file(self.file_cache[slug], slug))

        if read_tasks:
            await asyncio.gather(*read_tasks, return_exceptions=True)

        await ctx.send("✅ All spawn images generated and cached!")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle incoming messages for Pokémon spawns."""
        if message.author.id != self.target_id or ut:
            return
        guild_id = message.guild.id
        if guild_id not in self.server_queues:
            self.server_queues[guild_id] = asyncio.Queue()
        for e in message.embeds:
            if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                await self.server_queues[guild_id].put((message, e.image.url))

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        """Manually predict a spawn from an image URL or message."""
        try:
            def extract_image_from_message(msg: discord.Message):
                if msg.attachments:
                    return msg.attachments[0].url
                if msg.embeds and msg.embeds[0].image:
                    return msg.embeds[0].image.url
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

            guild_id = ctx.guild.id
            if guild_id not in self.server_queues:
                self.server_queues[guild_id] = asyncio.Queue()
            await self.server_queues[guild_id].put((message, image_url))
        except Exception as e:
            logger.error(f"Prediction error: {type(e).__name__}: {e}")
            await ctx.send(f"{self.error_emoji} Failed to process prediction.")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))