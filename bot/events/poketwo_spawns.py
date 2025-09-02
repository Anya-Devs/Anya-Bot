import os, asyncio, logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from collections import OrderedDict
import aiofiles
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import PoketwoCommands, MongoHelper
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)
_MAX_THREADS = os.cpu_count() or 2
_thread_executor = ThreadPoolExecutor(max_workers=_MAX_THREADS)

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
            regional_forms={"alola": "Alolan","galar": "Galarian","hisui": "Hisuian","paldea": "Paldean","unova": "Unovan"},
            lang_flags={"ja": "🇯🇵","de": "🇩🇪","fr": "🇫🇷","en": "🇺🇸"},
            bot=bot,
            pp=self.pp,
        )
        self.image_builder = PokemonImageBuilder()
        self.spawn_dir = "data/events/poketwo_spawns/spawns"
        os.makedirs(self.spawn_dir, exist_ok=True)
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.file_cache = {}
        self.pred_cache = OrderedDict()
        self.PRED_CACHE_MAX = 1000
        self.base_cache = {}
        self.formatted_name_cache = {}
        self.server_cache = {}
        self.ping_cache = {}
        self.desc_cache, self.type_cache, self.alt_cache = {}, {}, {}
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path):
                self.file_cache[slug] = path
        self._full_pokemon_data = None
        self._preload_task = asyncio.create_task(self._pickellize_all())
        self.queue = asyncio.Queue()
        self.worker_count = worker_count or (os.cpu_count() or 2)
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"
        for _ in range(self.worker_count):
            self.bot.loop.create_task(self._worker())

    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn(message, image_url)
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}", exc_info=True)
            finally:
                self.queue.task_done()

    async def _pickellize_all(self):
        loop = asyncio.get_running_loop()
        tasks = []
        for slug in self._pokemon_ids:
            try:
                base = self.pokemon_utils.get_base_pokemon_name(slug)
            except Exception:
                base = slug
            self.base_cache[slug] = base
            desc_data = self.pokemon_utils.get_description(slug) or ("", self._pokemon_ids.get(slug, "???"))
            self.desc_cache[slug] = desc_data[:2]
            self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
            self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""
            self.formatted_name_cache[slug] = self.pokemon_utils.format_name(slug).replace("_", " ").title()
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path):
                self.file_cache[slug] = path
            else:
                tasks.append(loop.run_in_executor(_thread_executor,self._generate_image_sync,slug,path))
                self.file_cache[slug] = path
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        try:
            self._full_pokemon_data = await loop.run_in_executor(_thread_executor, self.pokemon_utils.load_full_pokemon_data)
        except Exception:
            self._full_pokemon_data = {}

    def _generate_image_sync(self, slug, path):
        try:
            name_display = self.formatted_name_cache.get(slug) or self.pokemon_utils.format_name(slug).replace("_", " ").title()
            alt = self.alt_cache.get(slug, "")
            types = self.type_cache.get(slug, [])
            self.image_builder.create_image(slug, name_display, alt, types, None, path, "PNG")
        except Exception as e:
            logger.exception(f"Failed to generate image for {slug}: {e}")

    async def process_spawn(self, message, image_url):
        try:
            loop = asyncio.get_running_loop()
            pred = self.pred_cache.get(image_url)
            if pred is None:
                raw_name, conf = await loop.run_in_executor(_thread_executor, self.predictor.predict, image_url)
                self.pred_cache[image_url] = (raw_name, conf)
                while len(self.pred_cache) > self.PRED_CACHE_MAX:
                    self.pred_cache.popitem(last=False)
            else:
                raw_name, conf = pred
            base_name = self.base_cache.get(raw_name)
            if not base_name:
                base_name = self.pokemon_utils.get_base_pokemon_name(raw_name)
                if base_name not in self._pokemon_ids:
                    base_name = self.pokemon_utils.find_full_name_for_slug(raw_name).lower().replace("_", "-")
                self.base_cache[raw_name] = base_name
            try:
                conf_float = float(str(conf).strip().rstrip("%"))
            except Exception:
                conf_float = 0.0
            low_conf = conf_float < 30
            sid = getattr(message.guild, "id", None)
            server_config = None
            if sid is not None:
                server_config = self.server_cache.get(sid)
                if server_config is None:
                    server_config = await self.pokemon_utils.get_server_config(sid)
                    self.server_cache[sid] = server_config
            ping_key = (sid, base_name)
            cached_pings = self.ping_cache.get(ping_key)
            if cached_pings:
                type_pings, quest_pings, shiny_pings, collect_pings = cached_pings
            else:
                shiny_collect_task = self.pokemon_utils.get_ping_users(message.guild, base_name)
                type_task = self.pokemon_utils.get_type_ping_users(message.guild, base_name)
                quest_task = self.pokemon_utils.get_quest_ping_users(message.guild, base_name)
                shiny_collect, type_pings, quest_pings = await asyncio.gather(shiny_collect_task, type_task, quest_task)
                shiny_pings, collect_pings = shiny_collect
                self.ping_cache[ping_key] = (type_pings, quest_pings, shiny_pings, collect_pings)
            rare, regional = getattr(self.pokemon_utils, "_special_names", ([], []))
            special_roles = []
            if server_config:
                rare_role_id = server_config.get("rare_role")
                regional_role_id = server_config.get("regional_role")
                if rare_role_id:
                    special_roles += [f"<@&{rare_role_id}>" for r in rare if r in base_name]
                if regional_role_id:
                    special_roles += [f"<@&{regional_role_id}>" for r in regional if r in base_name]
            desc, dex = self.desc_cache.get(base_name, ("", "???"))
            dex = self._pokemon_ids.get(base_name, dex)
            ping_msg, _ = await self.pokemon_utils.format_messages(raw_name,type_pings,quest_pings,shiny_pings,collect_pings," ".join(special_roles),f"{conf_float:.2f}%",dex,desc,image_url,low_conf)
            path = self.file_cache.get(base_name) or os.path.join(self.spawn_dir, f"{base_name}.png")
            if not os.path.exists(path):
                await loop.run_in_executor(_thread_executor, self._generate_image_sync, base_name, path)
                self.file_cache[base_name] = path
            pokemon_data = self._full_pokemon_data or {}
            view = PokemonSpawnView(slug=base_name,pokemon_data=pokemon_data,pokemon_utils=self.pokemon_utils)
            try:
                await message.channel.send(content=ping_msg,file=discord.File(fp=path, filename=f"{base_name}.png"),reference=message,view=view)
            except Exception as send_err:
                logger.exception("Failed to send file directly; falling back to BytesIO", exc_info=send_err)
                try:
                    async with aiofiles.open(path, "rb") as f:
                        b = await f.read()
                    await message.channel.send(content=ping_msg,file=discord.File(fp=BytesIO(b), filename=f"{base_name}.png"),reference=message,view=view)
                except Exception:
                    logger.exception(f"Failed to fallback-send image {path}")
                    await message.channel.send(f"{self.cross_emoji} Missing image for {base_name}", reference=message)
        except Exception as e:
            logger.exception(f"Spawn processing error: {e}")
            try:
                await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)
            except Exception:
                logger.exception("Failed to notify channel about spawn processing error")

    @commands.command(name="generate_spawns", hidden=True)
    async def generate_all_spawn_images(self, ctx):
        os.makedirs(self.spawn_dir, exist_ok=True)
        missing_or_empty = []
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                missing_or_empty.append(slug)
                self.file_cache[slug] = path
        if not missing_or_empty:
            return await ctx.send("✅ All spawn images preloaded and valid!")
        await ctx.send(f"⚠️ Preloading {len(missing_or_empty)} Pokémon images...")
        loop = asyncio.get_running_loop()
        tasks = [loop.run_in_executor(_thread_executor, self._generate_image_sync, slug, self.file_cache[slug]) for slug in missing_or_empty]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await ctx.send("✅ All spawn images generated, cached (paths), and verified!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.target_id or ut:
            return
        for e in message.embeds:
            if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                await self.queue.put((message, e.image.url))

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
            logger.exception(f"Prediction error: {e}")
            await ctx.send(f"{self.error_emoji} Failed to process prediction.")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
