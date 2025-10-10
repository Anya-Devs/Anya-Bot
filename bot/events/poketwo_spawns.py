import os
import asyncio
import logging
import json
import traceback
from functools import partial

import aiofiles
import aiohttp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

import cloudinary
import cloudinary.uploader
import discord
from discord.ext import commands

from bot.token import use_test_bot as ut
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import MongoHelper
from bot.cogs.pokemon import PoketwoCommands
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)


class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot, worker_count=None):
        self.bot = bot
        self.target_id = 716390085896962058

        self.predictor = None
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

        # Updated caches with locking for thread safety
        self.pred_cache = {}
        self.base_cache = {}
        self.server_cache = {}
        self.desc_cache = {}
        self.type_cache = {}
        self.alt_cache = {}

        self.spawn_dir = "data/events/poketwo_spawns/spawns"
        self.image_urls = self._load_image_urls()
        self.default_ext = self._get_default_ext()

        self.queue = asyncio.Queue()
        self.worker_count = 2

        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

        # Executors for concurrency
        max_thread_workers = 4
        self.thread_executor = ThreadPoolExecutor(max_workers=max_thread_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=2)

        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET"),
            secure=True
        )

        # Start worker tasks
        for _ in range(self.worker_count):
            self.bot.loop.create_task(self._worker())

        # Preload caches async
        asyncio.create_task(self._preload_caches())

    def _load_image_urls(self):
        path = "data/events/poketwo_spawns/image_urls.json"
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load image URLs: {e}")
        return {}

    def _get_default_ext(self):
        try:
            with open("data/events/poketwo_spawns/image/config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                url = cfg.get("background_url", "").lower()
                if url.endswith(".gif"):
                    return "gif"
                return "png"
        except Exception:
            logger.warning("Failed to read config.json, defaulting to PNG")
            return "png"

    async def upload_all_existing(self):
        if not os.path.exists(self.spawn_dir):
            logger.warning(f"Spawn directory missing: {self.spawn_dir}")
            return

        files = [f for f in os.listdir(self.spawn_dir) if f.lower().endswith(('.gif', '.png'))]
        if not files:
            logger.info("No existing spawn images to upload")
            return

        # Use aiohttp for async uploads to avoid blocking threads
        async with aiohttp.ClientSession() as session:
            async def upload_file(file):
                base_name, _ = os.path.splitext(file)
                base_name = base_name.lower()
                if base_name in self.image_urls:
                    return True
                full_path = os.path.join(self.spawn_dir, file)
                try:
                    # Cloudinary python API does not support async natively, so keep thread offload
                    resp = await asyncio.get_running_loop().run_in_executor(
                        self.thread_executor,
                        partial(cloudinary.uploader.upload, full_path,
                                folder="poketwo_spawns", public_id=base_name, overwrite=True)
                    )
                    self.image_urls[base_name] = resp['secure_url']
                    return True
                except Exception as e:
                    logger.error(f"Upload failed for {file}: {e}")
                    return False

            successes = 0
            batch_size = 10
            for i in range(0, len(files), batch_size):
                batch = files[i:i+batch_size]
                results = await asyncio.gather(*[upload_file(f) for f in batch])
                successes += sum(results)
            logger.info(f"Uploaded {successes} spawn images to Cloudinary")

        try:
            os.makedirs("data/events/poketwo_spawns", exist_ok=True)
            async with aiofiles.open("data/events/poketwo_spawns/image_urls.json", 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.image_urls, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save image URLs: {e}")

    async def _worker(self):
        while True:
            message, image_url = await self.queue.get()
            try:
                await self.process_spawn(message, image_url)
            except Exception as e:
                logger.error(f"Worker error: {type(e).__name__}: {e}")
                traceback.print_exc()
            finally:
                self.queue.task_done()

    async def _preload_caches(self):
        tasks = []
        for slug in self._pokemon_ids:
            tasks.append(self._load_cache_for_slug(slug))
        await asyncio.gather(*tasks)

    async def _load_cache_for_slug(self, slug):
        base_name = self.pokemon_utils.get_base_pokemon_name(slug)
        self.base_cache[slug] = base_name
        desc_data = self.pokemon_utils.get_description(slug)
        self.desc_cache[slug] = desc_data[:2] if desc_data else ("", "???")
        self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
        self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""

    async def process_spawn(self, message, image_url):
        try:
            if self.predictor is None:
                self.predictor = Prediction()

            loop = asyncio.get_running_loop()

            # Predict asynchronously with caching
            if (pred := self.pred_cache.get(image_url)):
                raw_name, conf = pred
            else:
                raw_name, conf = await loop.run_in_executor(self.thread_executor, self.predictor.predict, image_url)
                self.pred_cache[image_url] = (raw_name, conf)

            base_name = self.base_cache.get(raw_name) or self.pokemon_utils.get_base_pokemon_name(raw_name)
            if base_name not in self._pokemon_ids:
                base_name = self.pokemon_utils.find_full_name_for_slug(raw_name).lower().replace("_", "-")
            self.base_cache[raw_name] = base_name

            conf_float = float(str(conf).strip().rstrip("%"))
            low_conf = conf_float < 30

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
            special_roles = []
            if server_config:
                special_roles = [
                    f"<@&{server_config['rare_role']}>" for r in rare if r in base_name
                ] + [
                    f"<@&{server_config['regional_role']}>" for r in regional if r in base_name
                ]

            desc, dex = self.desc_cache.get(base_name, ("", "???"))
            dex = self._pokemon_ids.get(base_name, dex)

            ping_msg, _ = await self.pokemon_utils.format_messages(
                raw_name, type_pings, quest_pings, shiny_pings, collect_pings,
                " ".join(special_roles), f"{conf_float:.2f}%", dex, desc,
                image_url, low_conf
            )

            view = PokemonSpawnView(slug=base_name, pokemon_data=self.full_pokemon_data, pokemon_utils=self.pokemon_utils)

            url = self.image_urls.get(base_name)
            if not url:
                url = await self._handle_image_upload(base_name)

            embed = discord.Embed()
            embed.set_image(url=url)

            await message.channel.send(content=ping_msg, embed=embed, reference=message, view=view)

        except Exception as e:
            logger.error(f"Spawn processing error: {type(e).__name__}: {e}")
            traceback.print_exc()
            await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)

    async def _handle_image_upload(self, base_name):
        # Attempt to upload local files or generate image and upload
        loop = asyncio.get_running_loop()
        for ext in ['.gif', '.png']:
            local_path = os.path.join(self.spawn_dir, f"{base_name}{ext}")
            if os.path.exists(local_path):
                try:
                    resp = await loop.run_in_executor(
                        self.thread_executor,
                        partial(cloudinary.uploader.upload, local_path,
                                folder="poketwo_spawns", public_id=base_name, overwrite=True)
                    )
                    url = resp['secure_url']
                    self.image_urls[base_name] = url
                    await self._save_image_urls()
                    return url
                except Exception as e:
                    logger.error(f"Local upload failed for {base_name}: {e}")
                    traceback.print_exc()

        # If local image not found, generate and upload
        ext = self.default_ext
        temp_path = f"/tmp/{base_name}.{ext}"
        name = self.pokemon_utils.format_name(base_name).replace("_", " ").title()
        alt = self.alt_cache.get(base_name, "")
        types = self.type_cache.get(base_name, [])
        try:
            await loop.run_in_executor(
                self.process_executor,
                self.image_builder.create_image,
                base_name, name, alt, types, None, temp_path, ext.upper()
            )
            resp = await loop.run_in_executor(
                self.thread_executor,
                partial(cloudinary.uploader.upload, temp_path,
                        folder="poketwo_spawns", public_id=base_name, overwrite=True)
            )
            url = resp['secure_url']
            self.image_urls[base_name] = url
            await self._save_image_urls()
            os.remove(temp_path)
            return url
        except Exception as e:
            logger.error(f"Create/upload failed for {base_name}: {e}")
            traceback.print_exc()
            return None

    async def _save_image_urls(self):
        try:
            os.makedirs("data/events/poketwo_spawns", exist_ok=True)
            async with aiofiles.open("data/events/poketwo_spawns/image_urls.json", 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.image_urls, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save image URLs JSON: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.target_id or ut:
            return
        for embed in message.embeds:
            title = embed.title
            if title and "pokémon has appeared!" in title.lower() and embed.image:
                await self.queue.put((message, embed.image.url))

    @commands.command(name="ps", hidden=True)
    @commands.is_owner()
    async def predict_spawn(self, ctx, image_url=None):
        try:
            def extract_image(msg: discord.Message):
                if msg.attachments:
                    return msg.attachments[0].url
                if msg.embeds:
                    emb = msg.embeds[0]
                    if emb.image and emb.image.url:
                        return emb.image.url
                    if emb.thumbnail and emb.thumbnail.url:
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
                    traceback.print_exc()

            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")

            await self.process_spawn(message, image_url)

        except Exception as e:
            logger.error(f"Prediction command error: {type(e).__name__}: {e}")
            traceback.print_exc()
            await ctx.send(f"{self.error_emoji} Failed to process prediction.")

    @commands.command(name="generate_spawns", hidden=True)
    @commands.is_owner()
    async def generate_spawns(self, ctx):
        await self._spawn_images_handler(ctx, regenerate=False)

    @commands.command(name="regenerate_spawns", hidden=True)
    @commands.is_owner()
    async def regenerate_spawns(self, ctx):
        await self._spawn_images_handler(ctx, regenerate=True)

    async def _spawn_images_handler(self, ctx, regenerate=False):
        try:
            await ctx.defer()
            loop = asyncio.get_running_loop()

            import csv
            async with aiofiles.open(self.pokemon_utils.pokemon_description_file, "r", encoding="utf-8") as f:
                data = await f.read()
            reader = list(csv.DictReader(data.splitlines()))

            file_ext = self.default_ext
            work_items = []
            for row in reader:
                slug = (row.get("slug") or row.get("name") or "").strip().lower()
                if slug and (regenerate or slug not in self.image_urls):
                    name = self.pokemon_utils.format_name(slug).replace("_", " ").title()
                    alt = self.alt_cache.get(slug, "")
                    types = self.type_cache.get(slug, [])
                    work_items.append((slug, name, alt, types))

            if not work_items:
                msg = "❌ No spawn items found." if regenerate else "✅ All spawn images already in database."
                return await ctx.send(msg)

            batch_size = 20
            success_count = 0
            error_count = 0

            # Create executors only once at init, reuse here
            pe = self.process_executor
            te = self.thread_executor

            async def generate_one(item):
                s, n, a, t = item
                temp_path = f"/tmp/{s}.{file_ext}"
                try:
                    await loop.run_in_executor(pe, self.image_builder.create_image, s, n, a, t, None, temp_path, file_ext.upper())
                    return s, temp_path
                except Exception as e:
                    logger.error(f"Generation failed for {s}: {e}")
                    return s, e

            async def upload_one(s, temp_path):
                try:
                    resp = await loop.run_in_executor(te, partial(cloudinary.uploader.upload, temp_path,
                                                                folder="poketwo_spawns", public_id=s, overwrite=True))
                    self.image_urls[s] = resp['secure_url']
                    os.remove(temp_path)
                    return s, resp['secure_url']
                except Exception as e:
                    logger.error(f"Upload failed for {s}: {e}")
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except Exception:
                        pass
                    return s, e

            for start in range(0, len(work_items), batch_size):
                batch = work_items[start:start + batch_size]
                gen_results = await asyncio.gather(*[generate_one(i) for i in batch])
                temp_paths = {s: p for s, p in gen_results if not isinstance(p, Exception)}

                upload_tasks = [upload_one(s, tp) for s, tp in temp_paths.items()]
                upload_results = await asyncio.gather(*upload_tasks)

                batch_success = sum(1 for _, r in upload_results if not isinstance(r, Exception))
                success_count += batch_success
                error_count += len(batch) - batch_success

                # Clean up any remaining temp files (though upload_one should handle it)
                for s, tp in temp_paths.items():
                    if os.path.exists(tp):
                        try:
                            os.remove(tp)
                        except Exception:
                            pass

            try:
                await self._save_image_urls()
            except Exception as e:
                logger.warning(f"Failed to save image URLs JSON: {e}")
                await ctx.send(f"⚠️ Updated {success_count} images but failed to save JSON locally: {e}")

            await ctx.send(f"✅ {'Regenerated' if regenerate else 'Generated'} and uploaded {success_count} spawn images. ❌ {error_count} failed. Total URLs cached: {len(self.image_urls)}")

        except Exception as e:
            logger.error(f"Spawn image handler failure: {type(e).__name__}: {e}")
            traceback.print_exc()
            await ctx.send(f"{self.error_emoji} Error during spawn images operation: {e}")


def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))