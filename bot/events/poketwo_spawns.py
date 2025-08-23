import os, asyncio, logging, time
from io import BytesIO
from multiprocessing import Process, Queue
from motor.motor_asyncio import AsyncIOMotorClient
import discord
from discord.ext import commands

from imports.discord_imports import *
from bot.token import use_test_bot as ut
from utils.events.poketwo_spawns import *
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import PoketwoCommands, MongoHelper

logger = logging.getLogger(__name__)


class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058
        self.predict_in = Queue()
        self.predict_out = Queue()
        self.predict_worker = PredictorWorker(self.predict_in, self.predict_out)
        self.predict_worker.start()
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
            bot=bot, pp=self.pp
        )
        self.pokemon_image_builder = PokemonImageBuilder()
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self._server_config_cache = {}
        self._image_cache = TTLCache(ttl=120, maxsize=256)
        self._ping_msg_cache = TTLCache(ttl=10, maxsize=512)
        self._buffer = BytesIO()
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

    async def cog_unload(self):
        try:
            self.predict_in.put_nowait(None)
        except Exception:
            pass

    async def get_cached_server_config(self, guild_id):
        cached = self._server_config_cache.get(guild_id)
        if cached:
            return cached
        cfg = await self.pokemon_utils.get_server_config(guild_id)
        self._server_config_cache[guild_id] = cfg
        return cfg

    async def predict_slug(self, image_url: str, timeout: float = 3.0):
        task_id = os.urandom(8).hex()
        self.predict_in.put((task_id, image_url))
        loop = asyncio.get_running_loop()
        start = loop.time()
        while loop.time() - start < timeout:
            await asyncio.sleep(0)
            try:
                got_id, payload = self.predict_out.get_nowait()
            except Exception:
                await asyncio.sleep(0.002)
                continue
            if got_id != task_id:
                continue
            status, *rest = payload
            if status == "ok":
                slug_raw, conf = rest
                return slug_raw, conf
            raise RuntimeError(rest[0])
        raise TimeoutError("Prediction timed out")

    async def build_or_get_image(self, guild_id: int, slug_raw: str, slug: str) -> bytes:
        key = (guild_id, slug)
        cached = self._image_cache.get(key)
        if cached:
            return cached
        self._buffer.seek(0)
        self._buffer.truncate(0)
        self.pokemon_image_builder.create_image(
            slug_raw,
            self.pokemon_utils.format_name(slug).replace("_", " ").title(),
            self.pokemon_utils.get_best_normal_alt_name(slug) or "",
            self.pokemon_utils.get_pokemon_types(slug),
            None,
            self._buffer,
            "JPEG",
        )
        data = self._buffer.getvalue()
        self._image_cache.set(key, data)
        return data

    async def build_or_get_ping_msg(
        self, guild: discord.Guild, slug: str, conf_float: float, dex: str, description: str, image_url: str, low_conf: bool
    ) -> str:
        key = (guild.id, slug, low_conf)
        cached = self._ping_msg_cache.get(key)
        if cached:
            return cached
        server_config = await self.get_cached_server_config(guild.id)
        shiny_collect, type_pings, quest_pings = await asyncio.gather(
            self.pokemon_utils.get_ping_users(guild, slug),
            self.pokemon_utils.get_type_ping_users(guild, slug),
            self.pokemon_utils.get_quest_ping_users(guild, slug),
        )
        shiny_pings, collect_pings = shiny_collect
        rare, regional = self.pokemon_utils._special_names
        special_roles = []
        if server_config.get("rare_role"):
            if any(r in slug for r in rare):
                special_roles.append(f"<@&{server_config['rare_role']}>")
        if server_config.get("regional_role"):
            if any(r in slug for r in regional):
                special_roles.append(f"<@&{server_config['regional_role']}>")
        ping_msg, _ = await self.pokemon_utils.format_messages(
            slug,
            type_pings,
            quest_pings,
            shiny_pings,
            collect_pings,
            " ".join(special_roles),
            f"{conf_float:.2f}%",
            dex,
            description,
            image_url,
            low_conf,
        )
        self._ping_msg_cache.set(key, ping_msg)
        return ping_msg

    async def process_spawn(self, message: discord.Message, image_url: str):
        try:
            slug_raw, conf = await self.predict_slug(image_url)
            slug = self.pokemon_utils.get_base_pokemon_name(slug_raw)
            if slug not in self._pokemon_ids:
                slug = self.pokemon_utils.find_full_name_for_slug(slug_raw).lower().replace("_", "-")
            conf_float = float(str(conf).strip().rstrip("%"))
            low_conf = conf_float < 30
            description, dex, _ = self.pokemon_utils.get_description(slug)
            dex = dex if dex and dex != "???" else self._pokemon_ids.get(slug, "???")
            ping_msg = await self.build_or_get_ping_msg(
                message.guild, slug, conf_float, dex, description, image_url, low_conf
            )
            img_bytes = await self.build_or_get_image(message.guild.id, slug_raw, slug)
            file = discord.File(fp=BytesIO(img_bytes), filename="pokemon_spawn.jpg")
            await message.channel.send(content=ping_msg, file=file, reference=message)
        except Exception as e:
            logger.error(f"Error in process_spawn: {type(e).__name__}: {e}")
            try:
                await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id != self.target_id and ut:
            return
        for e in message.embeds:
            if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                await self.process_spawn(message, e.image.url)
                break

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        try:
            message = ctx.message
            if not image_url:
                ref = message.reference
                if ref:
                    message = await ctx.channel.fetch_message(ref.message_id)
                if message.attachments:
                    image_url = message.attachments[0].url
                elif message.embeds and message.embeds[0].image:
                    image_url = message.embeds[0].image.url
            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")
            await self.process_spawn(message, image_url)
        except Exception as e:
            logger.error(f"Prediction error: {type(e).__name__}: {e}")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
