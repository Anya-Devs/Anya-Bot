from functools import partial
from collections import OrderedDict
import os, gc, json, asyncio, logging, traceback
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from motor.motor_asyncio import AsyncIOMotorClient
import aiohttp, aiofiles, cloudinary, cloudinary.uploader

from imports.discord_imports import *
from bot.token import use_test_bot as ut
from bot.cogs.pokemon import PoketwoCommands
from utils.subcogs.pokemon import MongoHelper
from submodules.poketwo_autonamer.predict import Prediction
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView


logger = logging.getLogger(__name__)


class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.target_id = 716390085896962058
        self.predictor: Prediction | None = None
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
                "paldea": "Paldean", "unova": "Unovan",
            },
            lang_flags={"ja": "🇯🇵", "de": "🇩🇪", "fr": "🇫🇷", "en": "🇺🇸"},
            bot=bot,
            pp=self.pp,
        )
        self.full_pokemon_data = self.pokemon_utils.load_full_pokemon_data()
        self.image_builder = PokemonImageBuilder()
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.pred_cache: OrderedDict[str, tuple[str, str]] = OrderedDict()
        self.base_cache: OrderedDict[str, str] = OrderedDict()
        self.server_cache: OrderedDict[int, dict] = OrderedDict()
        self.desc_cache: OrderedDict[str, tuple[str, str]] = OrderedDict()
        self.type_cache: OrderedDict[str, list[str]] = OrderedDict()
        self.alt_cache: OrderedDict[str, str] = OrderedDict()
        self.image_url_cache: OrderedDict[str, str] = OrderedDict()
        self.max_dynamic_cache_size = 2000
        self.max_static_cache_size = 10000
        self.spawn_dir = "data/events/poketwo_spawns/spawns"
        self.default_ext = self._get_default_ext()
        self.queue: asyncio.Queue[tuple[discord.Message, str]] = asyncio.Queue(maxsize=100)
        self.worker_count = 1
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"
        self.thread_executor = ThreadPoolExecutor(max_workers=2)
        self.process_executor = ProcessPoolExecutor(max_workers=1)
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )
        self._load_image_urls()
        try:
            loop = getattr(self.bot, "loop", asyncio.get_event_loop())
            loop.create_task(self._worker())
        except Exception:
            asyncio.create_task(self._worker())

    def _get_default_ext(self) -> str:
        try:
            with open("data/events/poketwo_spawns/image/config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                url = (cfg.get("background_url", "") or "").lower()
                return "gif" if url.endswith(".gif") else "png"
        except Exception:
            logger.warning("Failed to read config.json, defaulting to PNG")
            return "png"

    def _load_image_urls(self) -> None:
        path = "data/events/poketwo_spawns/image_urls.json"
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.image_url_cache = OrderedDict((k.lower(), v) for k, v in data.items())
            except Exception as e:
                logger.error(f"Failed to load image URLs: {e}")

    def _get_image_url(self, base_name: str) -> str | None:
        return self.image_url_cache.get(base_name.lower())

    def _add_image_url(self, base_name: str, url: str) -> None:
        base_name = base_name.lower()
        self.image_url_cache[base_name] = url
        if len(self.image_url_cache) > self.max_static_cache_size:
            self.image_url_cache.popitem(last=False)
        self._save_image_urls()

    def _save_image_urls(self) -> None:
        path = "data/events/poketwo_spawns/image_urls.json"
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dict(self.image_url_cache), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save image URLs: {e}")

    async def _worker(self) -> None:
        while True:
            try:
                message, image_url = await self.queue.get()
                try:
                    await self.process_spawn(message, image_url)
                except Exception as e:
                    logger.error(f"Worker error: {type(e).__name__}: {e}")
                    traceback.print_exc()
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue get error: {type(e).__name__}: {e}")
                traceback.print_exc()
                await asyncio.sleep(1)

    async def process_spawn(self, message: discord.Message, image_url: str) -> None:
        try:
            if self.predictor is None:
                self.predictor = Prediction()
            loop = asyncio.get_running_loop()
            pred = self.pred_cache.get(image_url)
            if pred is None:
                raw_name, conf = await loop.run_in_executor(
                    self.thread_executor, self.predictor.predict, image_url
                )
                self.pred_cache[image_url] = (raw_name, conf)
                if len(self.pred_cache) > self.max_dynamic_cache_size:
                    self.pred_cache.popitem(last=False)
            else:
                raw_name, conf = pred
            base = self.base_cache.get(raw_name)
            if base is None:
                base = self.pokemon_utils.get_base_pokemon_name(raw_name)
                if base not in self._pokemon_ids:
                    full = self.pokemon_utils.find_full_name_for_slug(raw_name)
                    if full:
                        base = full.lower().replace("_", "-")
                self.base_cache[raw_name] = base
                if len(self.base_cache) > self.max_dynamic_cache_size:
                    self.base_cache.popitem(last=False)
            base_name = base
            try:
                conf_float = float(str(conf).strip().rstrip("%"))
            except Exception:
                conf_float = 0.0
            low_conf = conf_float < 30.0
            if message.guild is None:
                logger.warning("Received spawn from DM or message without guild; skipping.")
                return
            sid = message.guild.id
            server_config = self.server_cache.get(sid)
            if server_config is None:
                server_config = await self.pokemon_utils.get_server_config(sid)
                self.server_cache[sid] = server_config or {}
                if len(self.server_cache) > self.max_dynamic_cache_size:
                    self.server_cache.popitem(last=False)
            desc_data = self.desc_cache.get(base_name)
            if desc_data is None:
                desc_data = self.pokemon_utils.get_description(base_name) or ("", "???")
                self.desc_cache[base_name] = desc_data
                if len(self.desc_cache) > self.max_static_cache_size:
                    self.desc_cache.popitem(last=False)
            desc, dex = desc_data[:2]
            dex = self._pokemon_ids.get(base_name, dex)
            shiny_collect, type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_ping_users(message.guild, base_name),
                self.pokemon_utils.get_type_ping_users(message.guild, base_name),
                self.pokemon_utils.get_quest_ping_users(message.guild, base_name),
            )
            shiny_pings, collect_pings = shiny_collect
            rare, regional = getattr(self.pokemon_utils, "_special_names", ([], []))
            special_roles = []
            if server_config:
                special_roles = [
                    f"<@&{server_config['rare_role']}>" for r in rare if r in base_name and server_config.get("rare_role")
                ] + [
                    f"<@&{server_config['regional_role']}>" for r in regional if r in base_name and server_config.get("regional_role")
                ]
            ping_msg, _ = await self.pokemon_utils.format_messages(
                raw_name, type_pings, quest_pings, shiny_pings, collect_pings,
                " ".join(special_roles), f"{conf_float:.2f}%", dex, desc,
                image_url, low_conf
            )
            view = PokemonSpawnView(
                slug=base_name,
                pokemon_data=self.full_pokemon_data,
                pokemon_utils=self.pokemon_utils
            )
            url = self._get_image_url(base_name)
            if not url:
                url = await self._handle_image_upload(base_name)
            embed = discord.Embed()
            if url:
                embed.set_image(url=url)
            await message.channel.send(
                content=ping_msg,
                embed=embed if url else None,
                reference=message,
                view=view
            )
        except MemoryError:
            logger.error("MemoryError: Clearing dynamic caches")
            self.pred_cache.clear()
            self.base_cache.clear()
            self.server_cache.clear()
            gc.collect()
            try:
                await message.channel.send(f"{self.error_emoji} Memory issue, cleared caches", reference=message)
            except Exception:
                logger.exception("Failed to notify about memory error.")
        except Exception as e:
            logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
            traceback.print_exc()
            try:
                await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)
            except Exception:
                logger.exception("Failed to notify about spawn processing error.")

    async def _handle_image_upload(self, base_name: str) -> str | None:
        loop = asyncio.get_running_loop()
        ext = self.default_ext
        temp_path = os.path.join("/tmp", f"{base_name}.{ext}") if os.name != "nt" else os.path.join(os.getcwd(), f"{base_name}.{ext}")
        local_path = os.path.join(self.spawn_dir, f"{base_name}.{ext}")
        if os.path.exists(local_path):
            try:
                resp = await loop.run_in_executor(
                    self.thread_executor,
                    partial(
                        cloudinary.uploader.upload,
                        local_path,
                        folder="poketwo_spawns",
                        public_id=base_name,
                        overwrite=True
                    )
                )
                url = resp.get("secure_url")
                if url:
                    self._add_image_url(base_name, url)
                    return url
            except Exception as e:
                logger.error(f"Local upload failed for {base_name}: {e}")
        alt = self.alt_cache.get(base_name)
        if alt is None:
            alt = self.pokemon_utils.get_best_normal_alt_name(base_name) or ""
            self.alt_cache[base_name] = alt
            if len(self.alt_cache) > self.max_static_cache_size:
                self.alt_cache.popitem(last=False)
        types = self.type_cache.get(base_name)
        if types is None:
            types = self.pokemon_utils.get_pokemon_types(base_name)
            self.type_cache[base_name] = types
            if len(self.type_cache) > self.max_static_cache_size:
                self.type_cache.popitem(last=False)
        name = self.pokemon_utils.format_name(base_name).replace("_", " ").title()
        try:
            await loop.run_in_executor(
                self.process_executor,
                self.image_builder.create_image,
                base_name, name, alt, types, None, temp_path, ext.upper()
            )
            resp = await loop.run_in_executor(
                self.thread_executor,
                partial(
                    cloudinary.uploader.upload,
                    temp_path,
                    folder="poketwo_spawns",
                    public_id=base_name,
                    overwrite=True
                )
            )
            url = resp.get("secure_url")
            if url:
                self._add_image_url(base_name, url)
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    logger.debug("Failed to remove temp image", exc_info=True)
            return url
        except Exception as e:
            logger.error(f"Image create/upload failed for {base_name}: {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    logger.debug("Failed to remove temp image after error", exc_info=True)
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.id != self.target_id or ut:
            return
        for embed in message.embeds:
            title = embed.title
            if title and "pokémon has appeared!" in title.lower() and getattr(embed, "image", None):
                try:
                    img_url = embed.image.url if embed.image and getattr(embed.image, "url", None) else None
                    if img_url:
                        try:
                            self.queue.put_nowait((message, img_url))
                        except asyncio.QueueFull:
                            logger.warning("Queue full, dropping spawn message")
                except Exception:
                    logger.exception("Failed to queue spawn message")

    @commands.command(name="ps", hidden=True)
    @commands.is_owner()
    async def predict_spawn(self, ctx: commands.Context, image_url: str | None = None) -> None:
        try:
            def extract_image(msg: discord.Message) -> str | None:
                if msg.attachments:
                    return msg.attachments[0].url
                if msg.embeds:
                    emb = msg.embeds[0]
                    if emb.image and getattr(emb.image, "url", None):
                        return emb.image.url
                    if emb.thumbnail and getattr(emb.thumbnail, "url", None):
                        return emb.thumbnail.url
                return None
            message = ctx.message
            if not image_url:
                image_url = extract_image(message)
            if not image_url and message.reference:
                try:
                    ref = await ctx.channel.fetch_message(message.reference.message_id)
                    image_url = extract_image(ref)
                    if not image_url and ref.reference:
                        ref2 = await ctx.channel.fetch_message(ref.reference.message_id)
                        image_url = extract_image(ref2)
                except Exception as e:
                    logger.error(f"Failed fetching referenced message: {e}")
            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")
            await self.process_spawn(ctx.message, image_url)
        except Exception as e:
            logger.error(f"Prediction command error: {type(e).__name__}: {e}")
            await ctx.send(f"{self.error_emoji} Failed to process prediction.")

    @commands.command(name="generate_spawns", hidden=True)
    @commands.is_owner()
    async def generate_spawns(self, ctx: commands.Context) -> None:
        await self._spawn_images_handler(ctx, regenerate=False)

    @commands.command(name="regenerate_spawns", hidden=True)
    @commands.is_owner()
    async def regenerate_spawns(self, ctx: commands.Context) -> None:
        await self._spawn_images_handler(ctx, regenerate=True)

    async def _spawn_images_handler(self, ctx: commands.Context, regenerate: bool = False) -> None:
        try:
            await ctx.defer()
            loop = asyncio.get_running_loop()
            import csv
            async with aiofiles.open(self.pokemon_utils.pokemon_description_file, "r", encoding="utf-8") as f:
                data = await f.read()
            reader = list(csv.DictReader(data.splitlines()))
            work_items: list[tuple[str, str, str, list[str]]] = []
            for row in reader:
                slug = (row.get("slug") or row.get("name") or "").strip().lower()
                if slug and (regenerate or not self._get_image_url(slug)):
                    name = self.pokemon_utils.format_name(slug).replace("_", " ").title()
                    alt = self.alt_cache.get(slug) or self.pokemon_utils.get_best_normal_alt_name(slug) or ""
                    self.alt_cache[slug] = alt
                    types = self.type_cache.get(slug) or self.pokemon_utils.get_pokemon_types(slug)
                    self.type_cache[slug] = types
                    work_items.append((slug, name, alt, types))
            if not work_items:
                msg = "❌ No spawn items found." if regenerate else "✅ All spawn images already cached."
                return await ctx.send(msg)
            batch_size = 3
            success_count = 0
            error_count = 0
            async def process_item(item: tuple[str, str, str, list[str]]) -> bool:
                slug, _, _, _ = item
                url = await self._handle_image_upload(slug)
                return bool(url)
            for start in range(0, len(work_items), batch_size):
                batch = work_items[start:start + batch_size]
                results = await asyncio.gather(*[process_item(i) for i in batch])
                success_count += sum(results)
                error_count += len(batch) - sum(results)
                gc.collect()
            action = "Regenerated" if regenerate else "Generated"
            await ctx.send(f"✅ {action} {success_count} spawn images. ❌ {error_count} failed.")
        except Exception as e:
            logger.error(f"Spawn image handler failure: {type(e).__name__}: {e}")
            await ctx.send(f"{self.error_emoji} Error: {e}")

    def cog_unload(self) -> None:
        try:
            self.thread_executor.shutdown(wait=False)
        except Exception:
            logger.exception("Failed to shutdown thread executor")
        try:
            self.process_executor.shutdown(wait=False)
        except Exception:
            logger.exception("Failed to shutdown process executor")
        self._save_image_urls()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PoketwoSpawnDetector(bot))
