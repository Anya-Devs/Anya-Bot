import os, asyncio, logging, uuid
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from motor.motor_asyncio import AsyncIOMotorClient
import numpy as np
from imports.discord_imports import *
from bot.token import use_test_bot as ut
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import PoketwoCommands, MongoHelper

logger = logging.getLogger(__name__)
_thread_executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)

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
        self.pokemon_image_builder = PokemonImageBuilder()

        # --- Cache setup ---
        self.image_cache_prefix = "poketwo:images:"
        self.config_cache_prefix = "poketwo:server_config:"
        self.desc_cache_prefix = "poketwo:desc:"

        # Load Pokémon IDs + slug map
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.slug_map = {k.lower(): k for k in self._pokemon_ids.keys()}

        # Preload spawn images dir + file cache
        self.spawn_output_dir = "data/events/poketwo_spawns/spawns"
        os.makedirs(self.spawn_output_dir, exist_ok=True)
        self.file_cache = {
            slug: os.path.join(self.spawn_output_dir, f"{slug}.png")
            for slug in self._pokemon_ids
            if os.path.exists(os.path.join(self.spawn_output_dir, f"{slug}.png"))
        }

        self.queue = asyncio.Queue()
        self.worker_count = worker_count or min((os.cpu_count() or 4) * 2, 32)
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
                logger.error(f"Worker error: {type(e).__name__}: {e}")
            finally:
                self.queue.task_done()

    async def process_spawn(self, message, image_url):
        try:
            loop = asyncio.get_running_loop()
            slug_raw, conf = await loop.run_in_executor(
                _thread_executor, self.predictor.predict, image_url
            )

            # ✅ Use base name logic
            slug = self.pokemon_utils.get_base_pokemon_name(slug_raw)
            if slug not in self._pokemon_ids:
                slug = (
                    self.pokemon_utils.find_full_name_for_slug(slug_raw)
                    .lower()
                    .replace("_", "-")
                )

            conf_float = np.array(
                [float(str(conf).strip().rstrip("%"))], dtype=np.float32
            )
            low_conf = conf_float < 30

            # Parallel fetch server + ping configs
            server_config, shiny_collect, type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_server_config(message.guild.id),
                self.pokemon_utils.get_ping_users(message.guild, slug),
                self.pokemon_utils.get_type_ping_users(message.guild, slug),
                self.pokemon_utils.get_quest_ping_users(message.guild, slug),
            )
            shiny_pings, collect_pings = shiny_collect

            # Rare / Regional role handling
            rare, regional = self.pokemon_utils._special_names
            special_roles = []
            if server_config.get("rare_role"):
                special_roles += [
                    f"<@&{server_config['rare_role']}>" for r in rare if r in slug
                ]
            if server_config.get("regional_role"):
                special_roles += [
                    f"<@&{server_config['regional_role']}>" for r in regional if r in slug
                ]

            # Dex + description
            description, dex, _ = self.pokemon_utils.get_description(slug)
            dex = dex if dex and dex != "???" else self._pokemon_ids.get(slug, "???")

            ping_msg, _ = await self.pokemon_utils.format_messages(
                slug,
                type_pings,
                quest_pings,
                shiny_pings,
                collect_pings,
                " ".join(special_roles),
                f"{conf_float[0]:.2f}%",
                dex,
                description,
                image_url,
                low_conf[0],
            )

            # ✅ Prefer pre-existing spawn image
            image_path = os.path.join(self.spawn_output_dir, f"{slug_raw}.png")
            if os.path.exists(image_path):
                file = discord.File(image_path, filename="pokemon_spawn.png")
            else:
                # Fallback → build new image
                image_bytes = BytesIO()
                await loop.run_in_executor(
                    _thread_executor,
                    self.pokemon_image_builder.create_image,
                    slug_raw,
                    self.pokemon_utils.format_name(slug).replace("_", " ").title(),
                    self.pokemon_utils.get_best_normal_alt_name(slug) or "",
                    self.pokemon_utils.get_pokemon_types(slug),
                    None,
                    image_bytes,
                    "PNG",
                )
                image_bytes.seek(0)
                file = discord.File(fp=image_bytes, filename="pokemon_spawn.png")

            await message.channel.send(content=ping_msg, file=file, reference=message)

        except Exception as e:
            logger.error(f"Error in process_spawn_tasks: {type(e).__name__}: {e}")
            await message.channel.send(
                f"{self.error_emoji} Failed to process spawn", reference=message
            )

    @commands.command(name="generate_spawns", hidden=True)
    async def generate_all_spawn_images(self, ctx):
        """Check which spawn images are missing from cache"""
        missing = [slug for slug in self._pokemon_ids if slug not in self.file_cache]
        if not missing:
            await ctx.send("✅ All spawn images are preloaded!")
        else:
            await ctx.send(
                f"⚠️ Missing preloaded spawn images for {len(missing)} Pokémon: {', '.join(missing)}"
            )

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
                return await ctx.send(f"{self.cross_emoji} No image URL found in message, reference, or embed.")

            await self.process_spawn(message, image_url)

        except Exception as e:
            logger.error(f"Prediction error: {type(e).__name__}: {e}")
            await ctx.send(f"{self.error_emoji} Failed to process prediction.")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
