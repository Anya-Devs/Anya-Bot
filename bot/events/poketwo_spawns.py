import os, asyncio, logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import aiofiles
from cachetools import LRUCache
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from bot.cogs.pokemon import PoketwoCommands, MongoHelper
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)
_thread_executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot, worker_count=None):
        self.bot = bot
        self.target_id = 716390085896962058
        self.predictor = Prediction()
        self.pp = PoketwoCommands(bot)
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.pokemon_utils = PokemonUtils(
            self.mongo,
            type_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_types.json",
            quest_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_quest.json",
            description_file="data/commands/pokemon/pokemon_description.csv",
            id_file="data/commands/pokemon/pokemon_names.csv",
            regional_forms={"alola":"Alolan","galar":"Galarian","hisui":"Hisuian","paldea":"Paldean","unova":"Unovan"},
            lang_flags={"ja":"🇯🇵","de":"🇩🇪","fr":"🇫🇷","en":"🇺🇸"},
            bot=bot,
            pp=self.pp,
        )
        self.image_builder = PokemonImageBuilder()
        self.spawn_dir = "data/events/poketwo_spawns/spawns"
        os.makedirs(self.spawn_dir, exist_ok=True)

        # ===== Bounded caches =====
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.file_cache = LRUCache(maxsize=2000)        # paths only
        self.pred_cache = LRUCache(maxsize=5000)        # prediction results
        self.base_cache = LRUCache(maxsize=1000)
        self.server_cache = LRUCache(maxsize=5000)
        self.ping_cache = LRUCache(maxsize=5000)
        self.desc_cache, self.type_cache, self.alt_cache = {}, {}, {}

        # preload image paths (no bytes)
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path):
                self.file_cache[slug] = path

        # ===== Worker queue =====
        self.queue = asyncio.Queue(maxsize=1024)
        self.worker_count = worker_count or min((os.cpu_count() or 4) * 2, 16)
        for _ in range(self.worker_count):
            self.bot.loop.create_task(self._worker())

        # ===== Metadata pre-cache =====
        asyncio.create_task(self._precache_metadata())
        asyncio.create_task(self._periodic_cache_cleanup())

        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

    # ===== Worker =====
    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn(message, image_url)
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
            finally:
                self.queue.task_done()

    # ===== Preload metadata =====
    async def _precache_metadata(self):
        loop = asyncio.get_running_loop()
        for slug in self._pokemon_ids:
            self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)
            desc_data = self.pokemon_utils.get_description(slug)
            self.desc_cache[slug] = (desc_data[0], desc_data[1]) if desc_data else ("", "???")
            self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
            self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""
        logger.info("Preloaded Pokémon metadata (no images).")

    # ===== Periodic cleanup =====
    async def _periodic_cache_cleanup(self):
        while True:
            await asyncio.sleep(600)  # every 10 minutes
            self.pred_cache.clear()
            self.server_cache.clear()
            self.ping_cache.clear()
            logger.info("Caches cleaned to reduce memory usage.")

    # ===== Process a spawn =====
    async def process_spawn(self, message, image_url):
        loop = asyncio.get_running_loop()

        # ===== Prediction =====
        raw_name, conf = self.pred_cache.get(image_url) or await loop.run_in_executor(
            _thread_executor, self.predictor.predict, image_url
        )
        self.pred_cache[image_url] = (raw_name, conf)

        base_name = self.base_cache.get(raw_name) or self.pokemon_utils.get_base_pokemon_name(raw_name)
        self.base_cache[raw_name] = base_name

        conf_float = float(str(conf).strip().rstrip("%"))
        low_conf = conf_float < 30

        # ===== Server config =====
        sid = message.guild.id
        server_config = self.server_cache.get(sid) or await self.pokemon_utils.get_server_config(sid)
        self.server_cache[sid] = server_config

        # ===== Pings =====
        ping_key = (sid, base_name)
        if ping_key in self.ping_cache:
            type_pings, quest_pings, shiny_pings, collect_pings = self.ping_cache[ping_key]
        else:
            shiny_collect, type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_ping_users(message.guild, base_name),
                self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
            )
            shiny_pings, collect_pings = shiny_collect
            self.ping_cache[ping_key] = (type_pings, quest_pings, shiny_pings, collect_pings)

        # ===== Special roles =====
        rare, regional = self.pokemon_utils._special_names
        special_roles = []
        if server_config.get("rare_role"):
            special_roles += [f"<@&{server_config['rare_role']}>" for r in rare if r in base_name]
        if server_config.get("regional_role"):
            special_roles += [f"<@&{server_config['regional_role']}>" for r in regional if r in base_name]

        desc, dex = self.desc_cache.get(base_name, ("", "???"))
        dex = self._pokemon_ids.get(base_name, dex)

        ping_msg, _ = await self.pokemon_utils.format_messages(
            raw_name, type_pings, quest_pings, shiny_pings, collect_pings,
            " ".join(special_roles), f"{conf_float:.2f}%", dex, desc, image_url, low_conf
        )

        # ===== Image handling (stream from disk) =====
        path = self.file_cache.get(base_name) or os.path.join(self.spawn_dir, f"{base_name}.png")
        if not os.path.exists(path) or os.path.getsize(path) == 0:
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
                img_bytes = BytesIO(await f.read())  # use BytesIO for discord.File
            view = PokemonSpawnView(slug=base_name, pokemon_data=self.pokemon_utils.load_full_pokemon_data(), pokemon_utils=self.pokemon_utils)
            await message.channel.send(content=ping_msg, file=discord.File(fp=img_bytes, filename=f"{base_name}.png"), reference=message, view=view)
        finally:
            img_bytes.close()  # free memory immediately

    # ===== Event listener =====
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.target_id or ut:
            return
        for e in message.embeds:
            if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                try:
                    self.queue.put_nowait((message, e.image.url))
                except asyncio.QueueFull:
                    logger.warning("Queue full, spawn skipped")

    # ===== Commands =====
    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        message = ctx.message
        def extract_image(msg):
            if msg.attachments: return msg.attachments[0].url
            if msg.embeds:
                embed = msg.embeds[0]
                return embed.image.url or embed.thumbnail.url
            return None

        if not image_url:
            image_url = extract_image(message)
            if not image_url and message.reference:
                ref = await ctx.channel.fetch_message(message.reference.message_id)
                image_url = extract_image(ref)
        if not image_url:
            return await ctx.send(f"{self.cross_emoji} No image URL found.")
        await self.process_spawn(message, image_url)

    @commands.command(name="generate_spawns", hidden=True)
    async def generate_all_spawn_images(self, ctx):
        os.makedirs(self.spawn_dir, exist_ok=True)
        loop = asyncio.get_running_loop()
        tasks = []
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                tasks.append(loop.run_in_executor(
                    _thread_executor,
                    self.image_builder.create_image,
                    slug,
                    self.pokemon_utils.format_name(slug).replace("_", " ").title(),
                    self.alt_cache.get(slug, ""),
                    self.type_cache.get(slug, []),
                    None,
                    path,
                    "PNG"
                ))
                self.file_cache[slug] = path
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await ctx.send("✅ All spawn images generated and cached!")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
