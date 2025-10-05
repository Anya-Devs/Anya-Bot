import os, asyncio, logging, json, traceback, csv
from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
from io import BytesIO
import aiofiles
from tqdm.asyncio import tqdm_asyncio
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import MongoHelper
from bot.cogs.pokemon import PoketwoCommands
from motor.motor_asyncio import AsyncIOMotorClient

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
                "alola": "Alolan", "galar": "Galarian", "hisui": "Hisuian",
                "paldea": "Paldean", "unova": "Unovan",
            },
            lang_flags={"ja": "🇯🇵", "de": "🇩🇪", "fr": "🇫🇷", "en": "🇺🇸"},
            bot=bot,
            pp=self.pp,
        )
        self.full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()
        self.image_builder = PokemonImageBuilder()
        self.spawn_dir = "data/events/poketwo_spawns/spawns"
        os.makedirs(self.spawn_dir, exist_ok=True)

        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.file_cache = {}
        self.pred_cache, self.base_cache = {}, {}
        self.server_cache, self.desc_cache, self.type_cache, self.alt_cache = {}, {}, {}, {}
        self.ext_cache = {}  # Stores file extensions for speed

        # Cache existing files and their extensions
        for slug in self._pokemon_ids:
            for ext in ("png", "gif"):
                path = os.path.join(self.spawn_dir, f"{slug}.{ext}")
                if os.path.exists(path):
                    self.file_cache[slug] = path
                    self.ext_cache[slug] = ext
                    break

        self.queue = asyncio.Queue()
        self.worker_count = worker_count or min((os.cpu_count() or 4) * 4, 64)
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

        for _ in range(self.worker_count):
            self.bot.loop.create_task(self._worker())

        asyncio.create_task(self._pickellize_all())

        # Load config for default GIF/PNG
        try:
            with open("data/events/poketwo_spawns/image/config.json", "r", encoding="utf-8") as f:
                self.config_data = json.load(f)
            bg_url = self.config_data.get("background_url")
            self.default_ext = "gif" if bg_url and bg_url.lower().endswith(".gif") else "png"
        except Exception:
            self.default_ext = "png"
            print("[WARN] Failed to read config.json, defaulting to PNG.")

    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn(message, image_url)
            except Exception as e:
                print(f"[ERROR] Worker error: {type(e).__name__}: {e}")
                traceback.print_exc()
            finally:
                self.queue.task_done()

    async def _pickellize_all(self):
        loop = asyncio.get_running_loop()
        tasks = []

        # Precompute all caches
        for slug in self._pokemon_ids:
            self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)
            desc, dex = "", self._pokemon_ids.get(slug, "???")
            desc_data = self.pokemon_utils.get_description(slug)
            if desc_data:
                desc, dex = desc_data[:2]
            self.desc_cache[slug] = (desc, dex)
            self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
            self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""

            # Only generate missing images
            if slug not in self.file_cache:
                path = os.path.join(self.spawn_dir, f"{slug}.{self.default_ext}")
                tasks.append(loop.run_in_executor(
                    _thread_executor,
                    self.image_builder.create_image,
                    slug,
                    self.pokemon_utils.format_name(slug).replace("_", " ").title(),
                    self.alt_cache[slug],
                    self.type_cache[slug],
                    None,
                    path,
                    self.default_ext.upper()
                ))
                self.file_cache[slug] = path
                self.ext_cache[slug] = self.default_ext

        # Run all image generation concurrently
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


    async def process_spawn(self, message, image_url):
        try:
            loop = asyncio.get_running_loop()

            # Predict name and confidence
            if (pred := self.pred_cache.get(image_url)):
                raw_name, conf = pred
            else:
                raw_name, conf = await loop.run_in_executor(_thread_executor, self.predictor.predict, image_url)
                self.pred_cache[image_url] = (raw_name, conf)

            # Base name lookup
            base_name = self.base_cache.get(raw_name)
            if not base_name:
                base_name = self.pokemon_utils.get_base_pokemon_name(raw_name)
                if base_name not in self._pokemon_ids:
                    base_name = self.pokemon_utils.find_full_name_for_slug(raw_name).lower().replace("_", "-")
                self.base_cache[raw_name] = base_name

            conf_float = float(str(conf).strip().rstrip("%"))
            low_conf = conf_float < 30

            # Server config
            sid = message.guild.id
            if (server_config := self.server_cache.get(sid)) is None:
                server_config = await self.pokemon_utils.get_server_config(sid)
                self.server_cache[sid] = server_config

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

            # Get or generate image path
            path = self.file_cache.get(base_name)
            ext = self.ext_cache.get(base_name, self.default_ext)
            view = PokemonSpawnView(slug=base_name, pokemon_data=self.full_pokemon_data, pokemon_utils=self.pokemon_utils)

            if not path:
                path = os.path.join(self.spawn_dir, f"{base_name}.{ext}")
                if base_name not in self.file_cache:
                    try:
                        await loop.run_in_executor(
                            _thread_executor,
                            self.image_builder.create_image,
                            base_name,
                            self.pokemon_utils.format_name(base_name).replace("_", " ").title(),
                            self.alt_cache.get(base_name, ""),
                            self.type_cache.get(base_name, []),
                            None,
                            path,
                            ext.upper()
                        )
                        self.file_cache[base_name] = path
                        self.ext_cache[base_name] = ext
                    except Exception as e:
                        print(f"[ERROR] Failed to create image for {base_name}: {e}")
                        traceback.print_exc()
                        return await message.channel.send(content=ping_msg, reference=message, view=view)

            await message.channel.send(
                content=ping_msg,
                file=discord.File(path, filename=f"{base_name}.{ext}"),
                reference=message,
                view=view
            )
        except Exception as e:
            print(f"[ERROR] Spawn processing error: {type(e).__name__}: {e}")
            traceback.print_exc()
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
                    logger.error("Failed to fetch referenced messages")
                    traceback.print_exception(type(e), e, e.__traceback__)

            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")

            await self.process_spawn(message, image_url)

        except Exception as e:
            logger.error(f"Prediction error: {type(e).__name__}: {e}")
            traceback.print_exception(type(e), e, e.__traceback__)
            await ctx.send(f"{self.error_emoji} Failed to process prediction.\n```\n{e}\n```")

            
    # ------------------------------------------------------------------
    # NEW COMMAND: generate_spawns
    # ------------------------------------------------------------------
    @commands.command(name="generate_spawns", hidden=True)
    async def generate_spawns(self, ctx):
     try:
        await ctx.defer()
        SPAWN_DIR = "data/events/poketwo_spawns/spawns"
        os.makedirs(SPAWN_DIR, exist_ok=True)
        loop = asyncio.get_running_loop()
        try:
            async with aiofiles.open(self.pokemon_utils.pokemon_description_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader((await f.read()).splitlines())
        except Exception as e:
            traceback.print_exception(type(e), e, e.__traceback__)
            return await ctx.send(f"{self.error_emoji} Failed to read CSV: {e}")
        if not reader:
            return await ctx.send("⚠️ CSV empty.")
        file_ext = "gif" if getattr(self.image_builder.config, "get", lambda k: None)("background_url") and getattr(self.image_builder.config, "get", lambda k: None)("background_url").lower().endswith(".gif") else "png"
        work_items = []
        for row in reader:
            slug = (row.get("slug") or row.get("name") or "").strip()
            if slug:
                path = os.path.join(SPAWN_DIR, f"{slug}.{file_ext}")
                if os.path.exists(path):
                    self.file_cache[slug] = path
                else:
                    name = self.pokemon_utils.format_name(slug).replace("_", " ").title()
                    alt = self.alt_cache.get(slug, "")
                    types = self.type_cache.get(slug, [])
                    work_items.append((slug, name, alt, types, path))
        if not work_items:
            return await ctx.send("⚠️ No new spawn images to generate.")
        # Increase workers for potentially more parallelism, assuming mixed CPU/IO load
        pe = ProcessPoolExecutor(max_workers=(os.cpu_count() or 4) * 2)
        async def build_one(item):
            s, n, a, t, p = item
            try:
                await loop.run_in_executor(pe, self.image_builder.create_image, s, n, a, t, None, p, file_ext.upper())
                self.file_cache[s] = p
                return p
            except Exception as e:
                return e
        results = []
        for r in tqdm_asyncio.as_completed([build_one(i) for i in work_items], total=len(work_items), desc="Generating spawns"):
            res = await r
            print(f"[ERROR] {res}" if isinstance(res, Exception) else f"[FILE CREATED] {res}")
            results.append(res)
        await ctx.send(f"✅ Generated {sum(1 for r in results if not isinstance(r, Exception))} spawn images. ❌ {sum(1 for r in results if isinstance(r, Exception))} failed.")
     except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
