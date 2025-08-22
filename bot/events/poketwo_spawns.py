import os, asyncio, logging
from concurrent.futures import ThreadPoolExecutor
from motor.motor_asyncio import AsyncIOMotorClient
import numpy as np
from aiocache import Cache  # <- Better async-native cache

from imports.discord_imports import *
from bot.token import use_test_bot as ut
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import PoketwoCommands, MongoHelper

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)

# Configure aiocache in-memory
cache = Cache(Cache.MEMORY, ttl=3600)  # cache expires in 1 hour

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot, worker_count=8):
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
            regional_forms={"alola": "Alolan", "galar": "Galarian", "hisui": "Hisuian",
                            "paldea": "Paldean", "unova": "Unovan"},
            lang_flags={"ja": "🇯🇵", "de": "🇩🇪", "fr": "🇫🇷", "en": "🇺🇸"},
            bot=bot, pp=self.pp
        )
        self.pokemon_image_builder = PokemonImageBuilder()
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.queue = asyncio.Queue()
        self.worker_count = worker_count
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"
        self.emojis = {"shiny": "<:shiny_sparkle:1394386258406412380>", "collection": "<:collection_ball:1394386212961124504>"}

        for _ in range(worker_count):
            self.bot.loop.create_task(self._worker())

    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn_tasks(message, image_url)
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
            finally:
                self.queue.task_done()

    async def process_spawn_tasks(self, message, image_url):
        """Centralized processor function for spawn prediction and message handling."""
        try:
            # Async cache check
            cached = await cache.get(image_url)
            if cached:
                slug_raw, conf = cached
            else:
                slug_raw, conf = await asyncio.to_thread(self.predictor.predict, image_url)
                await cache.set(image_url, (slug_raw, conf))

            slug = self.pokemon_utils.get_base_pokemon_name(slug_raw)
            if slug not in self._pokemon_ids:
                slug = self.pokemon_utils.find_full_name_for_slug(slug_raw).lower().replace("_","-")

            conf_float = np.array([float(str(conf).strip().rstrip("%"))], dtype=np.float32)
            low_conf = conf_float < 30

            server_config = await self.pokemon_utils.get_server_config(message.guild.id)
            shiny_pings, collect_pings = await self.pokemon_utils.get_ping_users(message.guild, slug)
            type_pings = await self.pokemon_utils.get_type_ping_users(message.guild, slug)
            quest_pings = await self.pokemon_utils.get_quest_ping_users(message.guild, slug)
            rare, regional = self.pokemon_utils._special_names
            special_roles = [f"<@&{server_config['rare_role']}>" for r in rare if r in slug and server_config.get("rare_role")]
            special_roles += [f"<@&{server_config['regional_role']}>" for r in regional if r in slug and server_config.get("regional_role")]

            description, dex, _ = self.pokemon_utils.get_description(slug)
            if not dex or dex == "???": dex = self._pokemon_ids.get(slug, "???")

            ping_msg, _ = await self.pokemon_utils.format_messages(
                slug, type_pings, quest_pings, shiny_pings, collect_pings,
                " ".join(special_roles), f"{conf_float[0]:.2f}%", dex, description, image_url, low_conf[0]
            )

            await asyncio.to_thread(
                self.pokemon_image_builder.create_image,
                raw_slug=slug_raw,
                pokemon_name=self.pokemon_utils.format_name(slug).replace("_"," ").title(),
                best_name=self.pokemon_utils.get_best_normal_alt_name(slug) or "",
                types=self.pokemon_utils.get_pokemon_types(slug),
                bg_url=None
            )

            file = discord.File("data/events/poketwo_spawns/image/test.png", filename="pokemon_spawn.png")
            await message.channel.send(content=ping_msg, file=file, reference=message)

        except Exception as e:
            logger.error(f"Error in process_spawn_tasks: {type(e).__name__}: {e}")
            await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)

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
            await self.process_spawn_tasks(message, image_url)
        except Exception as e:
            await ctx.send(f"{self.cross_emoji} Prediction error: {type(e).__name__}: {e}")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
