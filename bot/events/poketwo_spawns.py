import os, asyncio, logging, gc, json, heapq, itertools
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from collections import OrderedDict
from io import BytesIO
import aiofiles
from bot.token import use_test_bot as ut
from imports.discord_imports import *
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils, PokemonSpawnView
from submodules.poketwo_autonamer.predict import Prediction
from utils.subcogs.pokemon import MongoHelper
from bot.cogs.pokemon import PoketwoCommands
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)
LOW_MEMORY = os.getenv("LOW_MEMORY_MODE") == "1"

CPU_EXECUTOR = ProcessPoolExecutor(max_workers=1 if LOW_MEMORY else max(2, os.cpu_count() - 2))
THREAD_EXECUTOR = ThreadPoolExecutor(max_workers=1 if LOW_MEMORY else min(16, (os.cpu_count() or 4) * 2))

class LRUCache(OrderedDict):
    def __init__(self, maxsize=128):
        super().__init__()
        self.maxsize = maxsize
    def __getitem__(self, key):
        v = super().__getitem__(key)
        self.move_to_end(key)
        return v
    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
        if self.maxsize and len(self) > self.maxsize:
            self.popitem(last=False)

class BoundedPriorityQueue:
    def __init__(self, maxsize=256):
        self.maxsize = maxsize
        self._heap = []
        self._counter = itertools.count()
        self._cond = asyncio.Condition()

    def qsize(self): return len(self._heap)

    async def put(self, item, priority: int):
        async with self._cond:
            if len(self._heap) < self.maxsize:
                heapq.heappush(self._heap, (priority, next(self._counter), item))
                self._cond.notify()
                return True
            min_priority, idx = max((p, i) for i, (p, _, _) in enumerate(self._heap))
            if priority < min_priority:
                self._heap[idx] = (priority, next(self._counter), item)
                heapq.heapify(self._heap)
                self._cond.notify()
                return True
            return False

    def put_nowait(self, item, priority: int):
        loop = None
        try: loop = asyncio.get_running_loop()
        except RuntimeError: pass
        if len(self._heap) < self.maxsize:
            heapq.heappush(self._heap, (priority, next(self._counter), item))
            if loop: loop.call_soon_threadsafe(self._notify)
            return True
        min_priority, idx = max((p, i) for i, (p, _, _) in enumerate(self._heap))
        if priority < min_priority:
            self._heap[idx] = (priority, next(self._counter), item)
            heapq.heapify(self._heap)
            if loop: loop.call_soon_threadsafe(self._notify)
            return True
        return False

    async def get(self):
        async with self._cond:
            while not self._heap: await self._cond.wait()
            return heapq.heappop(self._heap)[2]

    def empty(self): return not self._heap

    def _notify(self):
        async def _n():
            async with self._cond: self._cond.notify_all()
        try: asyncio.create_task(_n())
        except RuntimeError: pass

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot, worker_count=None):
        self.bot = bot
        self.target_id = 716390085896962058
        self.predictor = None
        self._predictor_lock = asyncio.Lock()
        self.predictor_last_used = 0.0
        self.pp = PoketwoCommands(bot)

        mongo_uri = os.getenv("MONGO_URI")
        self.mongo = MongoHelper(AsyncIOMotorClient(mongo_uri)["Commands"]["pokemon"]) if mongo_uri else None

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

        self.image_builder = PokemonImageBuilder()
        self.spawn_dir = "data/events/poketwo_spawns/spawns"
        os.makedirs(self.spawn_dir, exist_ok=True)
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.index_path = os.path.join(self.spawn_dir, "index.json")

        # Caches
        self.file_cache = {}
        self.img_bytes_cache = LRUCache(maxsize=256)
        self.pred_cache = LRUCache(maxsize=1024)
        self.base_cache = LRUCache(maxsize=1024)
        self.desc_cache = {}
        self.type_cache = {}
        self.alt_cache = {}
        self.server_cache = LRUCache(maxsize=2048)

        self.server_speed = {}  # guild_id: delay per spawn in seconds
        self.queue = BoundedPriorityQueue(maxsize=1024 if not LOW_MEMORY else 128)
        self.worker_count = worker_count or (4 if not LOW_MEMORY else 2)
        self.success_emoji, self.error_emoji, self.cross_emoji = "<:green:1261639410181476443>", "<:red:1261639413943762944>", "❌"
        self.metrics = {"received":0,"dropped":0,"processed":0}

        self._load_index()
        for slug in self._pokemon_ids:
            path = os.path.join(self.spawn_dir, f"{slug}.png")
            if os.path.exists(path): self.file_cache[slug] = path

        loop = asyncio.get_event_loop()
        loop.create_task(self._prepare_metadata())
        loop.create_task(self._ensure_predictor(warm=True))
        for _ in range(self.worker_count): loop.create_task(self._worker())
        loop.create_task(self._periodic_persist())
        loop.create_task(self._predictor_idle_cleaner())
        self._full_pokemon_data = None

    # --- Index ---
    def _load_index(self):
        try:
            if os.path.exists(self.index_path):
                with open(self.index_path,"r",encoding="utf-8") as f:
                    self.file_cache.update(json.load(f).get("file_cache",{}))
            else: self._persist_index_blocking()
        except Exception as e: logger.debug("Index load failed: %s",e)

    def _persist_index_blocking(self):
        try:
            tmp = self.index_path+".tmp"
            with open(tmp,"w",encoding="utf-8") as f: json.dump({"file_cache":self.file_cache},f)
            os.replace(tmp,self.index_path)
        except Exception as e: logger.debug("Index persist failed: %s",e)

    async def _periodic_persist(self):
        while True:
            await asyncio.sleep(30)
            try:
                await asyncio.get_running_loop().run_in_executor(THREAD_EXECUTOR,self._persist_index_blocking)
            except Exception as e: logger.debug("Periodic persist error: %s",e)

    # --- Predictor ---
    async def _ensure_predictor(self, warm=False):
        async with self._predictor_lock:
            if not self.predictor:
                try: self.predictor = await asyncio.get_running_loop().run_in_executor(THREAD_EXECUTOR, Prediction)
                except Exception as e: logger.error("Predictor init fail: %s", e); self.predictor=None; return None
            self.predictor_last_used = asyncio.get_running_loop().time()
            if warm:
                try: await asyncio.get_running_loop().run_in_executor(THREAD_EXECUTOR,getattr(self.predictor,"warm",lambda:None))
                except Exception: pass
            return self.predictor

    async def _predictor_idle_cleaner(self):
        while True:
            await asyncio.sleep(60)
            if self.predictor and (asyncio.get_running_loop().time()-self.predictor_last_used)>300:
                self.predictor=None
                self._clear_memory_caches()
                gc.collect()

    # --- Metadata ---
    async def _prepare_metadata(self):
        tasks = []
        loop = asyncio.get_running_loop()
        for slug in list(self._pokemon_ids):
            tasks.append(loop.run_in_executor(THREAD_EXECUTOR, self._prepare_metadata_single, slug))
        await asyncio.gather(*tasks)

    def _prepare_metadata_single(self, slug):
        try:
            self.base_cache[slug] = self.pokemon_utils.get_base_pokemon_name(slug)
            d = self.pokemon_utils.get_description(slug)
            self.desc_cache[slug] = (d[0], d[1]) if d else ("",self._pokemon_ids.get(slug,"???"))
            self.type_cache[slug] = self.pokemon_utils.get_pokemon_types(slug)
            self.alt_cache[slug] = self.pokemon_utils.get_best_normal_alt_name(slug) or ""
        except Exception: pass

    # --- Worker ---
    async def _worker(self):
        while True:
            try:
                message,image_url = await self.queue.get()
                speed = self.server_speed.get(getattr(message.guild,"id",None),0)
                if speed: await asyncio.sleep(speed)
                await self._process_spawn_safe(message,image_url)
            except MemoryError: self._clear_memory_caches(); gc.collect()
            except Exception as e: logger.exception("Worker error: %s",e)

    # --- Spawn processing ---
    async def process_spawn(self,message,image_url):
        loop = asyncio.get_running_loop()
        pred = self.pred_cache.get(image_url)
        if not pred:
            predictor = await self._ensure_predictor()
            if predictor:
                raw_name,conf = await loop.run_in_executor(THREAD_EXECUTOR,predictor.predict,image_url)
            else:
                try: raw_name,conf = await loop.run_in_executor(THREAD_EXECUTOR,Prediction().predict,image_url)
                except Exception: raw_name,conf = "unknown","0"
            self.pred_cache[image_url]=(raw_name,conf)
        else: raw_name,conf = pred

        base_name = self.base_cache.get(raw_name)
        if not base_name:
            base_name = await loop.run_in_executor(THREAD_EXECUTOR,self.pokemon_utils.get_base_pokemon_name,raw_name)
            self.base_cache[raw_name]=base_name

        try: conf_float = float(str(conf).strip().rstrip("%") or 0)
        except: conf_float=0.0

        guild_obj = getattr(message,"guild",None)
        server_cfg = None
        if guild_obj and isinstance(guild_obj,discord.Guild):
            sid = guild_obj.id
            server_cfg=self.server_cache.get(sid)
            if not server_cfg:
                try: server_cfg = await self.pokemon_utils.get_server_config(guild_obj)
                except: server_cfg={}
                self.server_cache[sid]=server_cfg

        ping_tasks=[
            asyncio.create_task(self.pokemon_utils.get_ping_users(guild_obj,base_name)),
            asyncio.create_task(self.pokemon_utils.get_type_ping_users(guild_obj,base_name)),
            asyncio.create_task(self.pokemon_utils.get_quest_ping_users(guild_obj,base_name))
        ]
        shiny_collect,type_pings,quest_pings = await asyncio.gather(*ping_tasks)
        shiny_pings,collect_pings=shiny_collect

        desc,dex=self.desc_cache.get(base_name,("","???"))
        dex=self._pokemon_ids.get(base_name,dex)

        ping_msg,_ = await self.pokemon_utils.format_messages(
            raw_name,type_pings,quest_pings,shiny_pings,collect_pings,
            "",f"{conf_float:.2f}%",dex,desc,image_url,conf_float<30
        )

        path = self.file_cache.get(base_name) or os.path.join(self.spawn_dir,f"{base_name}.png")
        if not os.path.exists(path):
            try:
                await loop.run_in_executor(
                    CPU_EXECUTOR,
                    self.image_builder.create_image,
                    base_name,
                    self.pokemon_utils.format_name(base_name).title(),
                    self.alt_cache.get(base_name,""),
                    self.type_cache.get(base_name,[]),
                    None,
                    path,
                    "PNG"
                )
                self.file_cache[base_name]=path
            except Exception: logger.exception("Image create failed for %s",base_name)

        img_bytes=self.img_bytes_cache.get(base_name)
        if img_bytes is None:
            try:
                async with aiofiles.open(path,"rb") as f: img_bytes=await f.read()
                self.img_bytes_cache[base_name]=img_bytes
            except Exception: img_bytes=b""; logger.exception("Failed to read image bytes for %s",base_name)

        if not self._full_pokemon_data:
            try: self._full_pokemon_data=await loop.run_in_executor(THREAD_EXECUTOR,self.pokemon_utils.load_full_pokemon_data)
            except: self._full_pokemon_data={}

        view=PokemonSpawnView(slug=base_name,pokemon_data=self._full_pokemon_data,pokemon_utils=self.pokemon_utils)
        try:
            await message.channel.send(
                content=ping_msg,
                file=discord.File(fp=BytesIO(img_bytes),filename=f"{base_name}.png"),
                reference=message,
                view=view
            )
        except:
            try: await message.channel.send(content=ping_msg,reference=message)
            except: logger.exception("Failed to send ping for %s",base_name)

    async def _process_spawn_safe(self,message,image_url):
        self.metrics["processed"]+=1
        try: await self.process_spawn(message,image_url)
        except Exception as e:
            logger.exception("Spawn processing error: %s",e)
            try: await message.channel.send(f"{self.error_emoji} Failed to process spawn",reference=message)
            except: pass

    def _clear_memory_caches(self):
        try: self.pred_cache.clear(); self.img_bytes_cache.clear(); gc.collect()
        except: pass

    # --- Listeners / commands ---
    @commands.Cog.listener()
    async def on_message(self,message):
        if message.author.id != self.target_id or ut: return
        for e in message.embeds:
            try:
                if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                    self.metrics["received"]+=1
                    if not self.queue.put_nowait((message,e.image.url),priority=0):
                        self.metrics["dropped"]+=1
            except: continue

    @commands.command(name="generate_spawns",hidden=True)
    async def generate_all_spawn_images(self,ctx):
        missing=[s for s in self._pokemon_ids if not os.path.exists(os.path.join(self.spawn_dir,f"{s}.png"))]
        if not missing: return await ctx.send("✅ All spawn images ready!")
        await ctx.send(f"⚠️ Generating {len(missing)} images...")
        loop=asyncio.get_running_loop()
        tasks=[loop.run_in_executor(
            CPU_EXECUTOR,
            self.image_builder.create_image,
            slug,
            self.pokemon_utils.format_name(slug).title(),
            self.alt_cache.get(slug,""),
            self.type_cache.get(slug,[]),
            None,
            os.path.join(self.spawn_dir,f"{slug}.png"),
            "PNG"
        ) for slug in missing]
        try:
            await asyncio.gather(*tasks)
            for slug in missing: self.file_cache[slug]=os.path.join(self.spawn_dir,f"{slug}.png")
            await ctx.send("✅ Done!")
        except Exception as e:
            logger.exception("Batch generate failed: %s",e)
            await ctx.send(f"{self.error_emoji} Generation failed.")

    @commands.command(name="ps",hidden=True)
    async def predict_spawn(self,ctx,image_url=None):
        try:
            def extract_image(msg):
                if msg.attachments: return msg.attachments[0].url
                if msg.embeds: return getattr(msg.embeds[0].image or msg.embeds[0].thumbnail,"url",None)
                return None
            msg=ctx.message
            if not image_url:
                image_url=extract_image(msg)
                if not image_url and msg.reference:
                    ref=await ctx.channel.fetch_message(msg.reference.message_id)
                    image_url=extract_image(ref)
                    if not image_url and ref.reference:
                        ref2=await ctx.channel.fetch_message(ref.reference.message_id)
                        image_url=extract_image(ref2)
            if not image_url: return await ctx.send(f"{self.cross_emoji} No image URL found.")
            accepted=self.queue.put_nowait((msg,image_url),priority=1)
            if not accepted:
                put_ok=await self.queue.put((msg,image_url),priority=1)
                if not put_ok: self.metrics["dropped"]+=1; return await ctx.send(f"{self.error_emoji} Queue full; try again.")
        except Exception as e: logger.exception("Prediction error: %s",e); await ctx.send(f"{self.error_emoji} Failed to queue prediction.")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
