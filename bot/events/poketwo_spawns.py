import os
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from collections import OrderedDict
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import MongoHelper
from bot.cogs.pokemon import PoketwoCommands
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

MAX_IMG_BYTES_CACHE = 8
MAX_PRED_CACHE = 256
WORKER_COUNT = min(4, (os.cpu_count() or 4))
CPU_POOL_SIZE = max(1, (os.cpu_count() or 4) // 2)
THREAD_POOL_SIZE = min(8, (os.cpu_count() or 4) * 2)
QUEUE_MAXSIZE = 256
PRELOAD_SPAWNS = os.getenv("PRELOAD_POKEMON_IMAGES") == "1"

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
        if key in self:
            super().__setitem__(key, value)
            self.move_to_end(key)
            return
        super().__setitem__(key, value)
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
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.file_cache = {}
        self.img_bytes_cache = LRUCache(maxsize=MAX_IMG_BYTES_CACHE)
        self.pred_cache = LRUCache(maxsize=MAX_PRED_CACHE)
        self.base_cache = {}
        self.desc_cache = {}
        self.type_cache = {}
        self.alt_cache = {}
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path):
                self.file_cache[slug] = path
        self.queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self.worker_count = worker_count or WORKER_COUNT
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"
        for _ in range(self.worker_count):
            self.bot.loop.create_task(self._worker())
        asyncio.create_task(self._prepare_metadata_and_optional_images())
        self._full_pokemon_data = None

    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn(message, image_url)
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
            finally:
                self.queue.task_done()

    async def _prepare_metadata_and_optional_images(self):
        loop = asyncio.get_running_loop()
        slugs = list(self._pokemon_ids.keys())
        for slug in slugs:
            self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)
            desc, dex = "", self._pokemon_ids.get(slug, "???")
            desc_data = self.pokemon_utils.get_description(slug)
            if desc_data:
                desc, dex = desc_data[:2]
            self.desc_cache[slug] = (desc, dex)
            self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
            self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if slug not in self.file_cache and os.path.exists(path):
                self.file_cache[slug] = path
        if not PRELOAD_SPAWNS:
            return
        batch_size = max(2, CPU_POOL_SIZE)
        tasks = []
        for slug in slugs:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if slug in self.file_cache and os.path.exists(path):
                continue
            tasks.append(loop.run_in_executor(
                CPU_EXECUTOR,
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
            if len(tasks) >= batch_size:
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks = []
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _ensure_predictor(self):
        loop = asyncio.get_running_loop()
        if self.predictor is None:
            self.predictor = await loop.run_in_executor(THREAD_EXECUTOR, Prediction)
        return self.predictor

    async def process_spawn(self, message, image_url):
        try:
            loop = asyncio.get_running_loop()
            cached = self.pred_cache.get(image_url)
            if cached:
                raw_name, conf = cached
            else:
                predictor = await self._ensure_predictor()
                raw_name, conf = await loop.run_in_executor(
                    THREAD_EXECUTOR, lambda: predictor.predict(image_url)
                )
                self.pred_cache[image_url] = (raw_name, conf)
            base_name = self.base_cache.get(raw_name)
            if not base_name:
                base_name = self.pokemon_utils.get_base_pokemon_name(raw_name)
                if base_name not in self._pokemon_ids:
                    base_name = (
                        self.pokemon_utils.find_full_name_for_slug(raw_name)
                        .lower()
                        .replace("_", "-")
                    )
                self.base_cache[raw_name] = base_name
            conf_float = float(str(conf).strip().rstrip("%"))
            low_conf = conf_float < 30
            desc, dex = self.desc_cache.get(base_name, ("", "???"))
            dex = self._pokemon_ids.get(base_name, dex)
            ping_msg = f"**{base_name.title()}** | Confidence: {conf_float:.2f}% | Dex: {dex}\n{desc}"
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
                    "PNG",
                )
                self.file_cache[base_name] = path
            try:
                f = open(path, "rb")
            except Exception as e:
                logger.error(f"Failed to open spawn image {path}: {e}")
                return await message.channel.send(
                    f"{self.cross_emoji} Missing image for {base_name}",
                    reference=message,
                )
            if self._full_pokemon_data is None:
                try:
                    self._full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()
                except Exception:
                    self._full_pokemon_data = {}
            view = PokemonSpawnView(
                slug=base_name,
                pokemon_data=self._full_pokemon_data,
                pokemon_utils=self.pokemon_utils
            )
            try:
                await message.channel.send(
                    content=ping_msg,
                    file=discord.File(fp=f, filename=f"{base_name}.png"),
                    reference=message,
                    view=view
                )
            finally:
                try:
                    f.close()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
            try:
                await message.channel.send(
                    f"{self.error_emoji} Failed to process spawn", reference=message
                )
            except Exception:
                pass

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

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        try:
            def extract_image_from_message(msg: discord.Message):
                if msg.attachments:
                    return msg.attachments[0].url
                if msg.embeds:
                    embed = msg.embeds[0]
                    if embed.image and embed.image.url:
                        return embed.image.url
                    if embed.thumbnail and embed.thumbnail.url:
                        return embed.thumbnail.url
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
            await self.process_spawn(message, image_url)
        except Exception as e:
            logger.error(f"Prediction error: {type(e).__name__}: {e}")
            await ctx.send(f"{self.error_emoji} Failed to process prediction.")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
