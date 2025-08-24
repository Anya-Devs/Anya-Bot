import os
import asyncio
import logging
import time
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

import redis.asyncio as redis
import aiofiles
import aiofiles.ospath
from imports.discord_imports import *
from motor.motor_asyncio import AsyncIOMotorClient

from bot.token import use_test_bot as ut
from utils.events.poketwo_spawns import PokemonUtils
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import PoketwoCommands, MongoHelper

logger = logging.getLogger(__name__)
_thread_executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot, worker_count=None):
        self.bot = bot
        self.target_id = 716390085896962058

        # Predictor + utilities preloaded
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
                "paldea": "Paldean", "unova": "Unovan"
            },
            lang_flags={"ja": "🇯🇵", "de": "🇩🇪", "fr": "🇫🇷", "en": "🇺🇸"},
            bot=bot, pp=self.pp
        )

        self.redis = None
        self.image_cache_prefix = "poketwo:images:"
        self.config_cache_prefix = "poketwo:server_config:"
        self.desc_cache_prefix = "poketwo:desc:"

        # Load Pokemon IDs and slug mapping
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.slug_map = {k.lower(): k for k in self._pokemon_ids.keys()}

        # Preload spawn images
        self.spawn_output_dir = "data/events/poketwo_spawns/spawns"
        os.makedirs(self.spawn_output_dir, exist_ok=True)
        self.file_cache = {slug: os.path.join(self.spawn_output_dir, f"{slug}.png")
                           for slug in self._pokemon_ids if os.path.exists(os.path.join(self.spawn_output_dir, f"{slug}.png"))}

        # Concurrency controls
        self.worker_count = worker_count or max((os.cpu_count() or 4) * 2, 50)
        self.queue = asyncio.Queue(maxsize=10000)
        self.semaphore = asyncio.Semaphore(self.worker_count)
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

        # Start worker tasks
        for _ in range(self.worker_count):
            self.bot.loop.create_task(self._worker())

    async def setup_redis(self):
        self.redis = redis.from_url(REDIS_URL, decode_responses=True)

    async def _redis_get(self, key):
        if self.redis:
            return await self.redis.get(key)

    async def _redis_set(self, key, value):
        if self.redis:
            await self.redis.set(key, value)

    async def _redis_hgetall(self, key):
        if self.redis:
            return await self.redis.hgetall(key)
        return {}

    async def _redis_hset(self, key, mapping):
        if self.redis:
            await self.redis.hset(key, mapping)

    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            async with self.semaphore:
                try:
                    await self.process_spawn(message, image_url)
                except Exception as e:
                    logger.error(f"Worker error: {type(e).__name__}: {e}")
                finally:
                    self.queue.task_done()

    async def process_spawn(self, message, image_url):
        total_start = time.time()
        try:
            # Prediction offloaded to thread
            slug_raw, conf = await asyncio.to_thread(self.predictor.predict, image_url)
            slug = self.slug_map.get(slug_raw.lower(), slug_raw.lower())
            file_path = self.file_cache.get(slug)
            if not file_path:
                return await message.channel.send(f"{self.cross_emoji} Spawn image not found for {slug}.", reference=message)

            # Load file once
            async with aiofiles.open(file_path, "rb") as f:
                file_bytes = await f.read()
            file = discord.File(fp=BytesIO(file_bytes), filename=f"{slug}.png")

            # Server config cache
            config_key = f"{self.config_cache_prefix}{message.guild.id}"
            server_config = await self._redis_hgetall(config_key)
            if not server_config:
                server_config = await self.pokemon_utils.get_server_config(message.guild.id)
                await self._redis_hset(config_key, server_config)

            # Description cache
            desc_key = f"{self.desc_cache_prefix}{slug}"
            cached_desc = await self._redis_hgetall(desc_key)
            if cached_desc:
                description, dex = cached_desc["description"], cached_desc["dex"]
            else:
                description, dex, _ = self.pokemon_utils.get_description(slug)
                dex = dex if dex and dex != "???" else self._pokemon_ids.get(slug, "???")
                await self._redis_hset(desc_key, {"description": description, "dex": dex})

            # Gather all pings concurrently
            shiny_collect, type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_ping_users(message.guild, slug),
                self.pokemon_utils.get_type_ping_users(message.guild, slug),
                self.pokemon_utils.get_quest_ping_users(message.guild, slug)
            )
            shiny_pings, collect_pings = shiny_collect

            # Special roles
            rare, regional = self.pokemon_utils._special_names
            special_roles = []
            if server_config.get("rare_role"):
                special_roles += [f"<@&{server_config['rare_role']}>" for r in rare if r in slug]
            if server_config.get("regional_role"):
                special_roles += [f"<@&{server_config['regional_role']}>" for r in regional if r in slug]

            conf_float = float(str(conf).strip().rstrip("%"))
            low_conf = conf_float < 30

            ping_msg, _ = await self.pokemon_utils.format_messages(
                slug, type_pings, quest_pings, shiny_pings, collect_pings,
                " ".join(special_roles), f"{conf_float:.2f}%", dex, description, image_url, low_conf
            )
            await message.channel.send(content=ping_msg, file=file, reference=message)
            logger.info(f"Processed {slug} in {time.time() - total_start:.3f}s")

        except Exception as e:
            logger.error(f"Error in process_spawn: {type(e).__name__}: {e}")
            await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.target_id or ut:
            return
        embed = next((e for e in message.embeds if e.title and "pokémon has appeared!" in e.title.lower() and e.image), None)
        if embed:
            asyncio.create_task(self.queue.put((message, embed.image.url)))

    @commands.command(name="generate_spawns", hidden=True)
    async def generate_all_spawn_images(self, ctx):
        missing = [slug for slug in self._pokemon_ids
                   if slug not in self.file_cache]
        if not missing:
            await ctx.send("✅ All spawn images are preloaded!")
        else:
            await ctx.send(f"⚠️ Missing preloaded spawn images for {len(missing)} Pokémon: {', '.join(missing)}")


def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
