import asyncio; from data.setup import SetupManager; asyncio.run(SetupManager().run_setup())
import os, sys, gc, asyncio, importlib, pkgutil, threading, signal, traceback
from dotenv import load_dotenv
import aiohttp, yarl, discord
from flask import Flask, send_from_directory
from rich.console import Console
from rich.align import Align
from rich.tree import Tree
from data.local.const import AvatarToTextArt
from bot.token import get_bot_token, prefix
from imports.log_imports import logger
from imports.discord_imports import *
from utils.cogs.ticket import setup_persistent_views
from utils.cogs.fun import setup_persistent_views_fun
from art import text2art
from bot.token import get_bot_token as ut 

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv(dotenv_path=os.path.join(".github", ".env"))

def patch_discord_gateway(env_gateway="wss://gateway.discord.gg/"):
    class CustomHTTP(discord.http.HTTPClient):
        async def get_gateway(self, **_): return f"{env_gateway}?encoding=json&v=10"
        async def get_bot_gateway(self, **_):
            data = await self.request(discord.http.Route("GET","/gateway/bot"))
            return data["shards"], f"{env_gateway}?encoding=json&v=10", data.get("session_start_limit", {})
    class CustomWebSocket(discord.gateway.DiscordWebSocket):
        DEFAULT_GATEWAY = yarl.URL(env_gateway)
        def is_ratelimited(self): return False
    discord.http.HTTPClient.get_gateway = CustomHTTP.get_gateway
    discord.http.HTTPClient.get_bot_gateway = CustomHTTP.get_bot_gateway
    discord.gateway.DiscordWebSocket.DEFAULT_GATEWAY = CustomWebSocket.DEFAULT_GATEWAY
    discord.gateway.DiscordWebSocket.is_ratelimited = CustomWebSocket.is_ratelimited

patch_discord_gateway()

class Config:
    PORT = int(os.environ.get("PORT", 8081 if not ut else 0))
    USE_PRESENCE = os.environ.get("USE_PRESENCE_INTENTS", "0").strip().lower() not in ("0", "false", "no")
    COOLDOWN = [
        'rate_limit_count', 1,
        'per_seconds', 5,
        'type', commands.BucketType.user
    ]
    # Per-server sharding configuration
    SERVER_SHARD_MAPPING = {}  # Maps guild_id to shard configuration
    SHARD_POOL_SIZE = 100  # Connection pool size for optimized connections

rate = Config.COOLDOWN[1]
per = Config.COOLDOWN[3]
bucket_type = Config.COOLDOWN[5]

class FlaskServer:
    def __init__(self, port=Config.PORT):
        self.app = Flask(__name__, static_folder="html")
        self.port = port
        self._setup_routes()
    def _setup_routes(self):
        @self.app.route("/")
        def index():
            p = os.path.join(self.app.static_folder, "index.html")
            return send_from_directory(self.app.static_folder, "index.html") if os.path.exists(p) else ("⚠️ index.html not found.", 404)
        @self.app.route("/html/<path:filename>")
        def serve_static(filename):
            return send_from_directory(self.app.static_folder, filename)
    def run(self):
        self.app.run(host="0.0.0.0", port=self.port, threaded=True)

class ClusteredBot(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=commands.when_mentioned_or(prefix),
            intents=intents,
            help_command=None,
            shard_ids=None,
            shard_count=None,
            shard_reconnect_interval=15,  # Maintained wait time
            heartbeat_timeout=90,        # Maintained wait time
            chunk_guilds_at_startup=False,
            guild_ready_timeout=5.0,     # Maintained wait time
            max_concurrency=Config.SHARD_POOL_SIZE,  # Optimized connection pool
        )
        self.cog_dirs = ['bot.cogs', 'bot.events']
        self.console = Console()
        self.http_session: aiohttp.ClientSession | None = None
        self.cog_cache = {}  # Cache for loaded cogs
        self.server_shards = {}  # Per-server shard tracking

    async def setup_hook(self):
        await self._import_cogs()
        # Optimized HTTP session with connection pooling
        connector = aiohttp.TCPConnector(limit=Config.SHARD_POOL_SIZE, ttl_dns_cache=300)
        self.http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15), connector=connector)
        try:
            shards = list(self.shards.keys())
            shard_count = self.shard_count
            logger.info("🧩 The cluster has the initializing shards and no we don't need to wait for all 1 trillion shards")
        except Exception as e:
            logger.warning(f"Shard initialization failed: {e}")

    async def on_ready(self):
        term = __import__('shutil').get_terminal_size().columns
        art_str = ""
        try:
            art = AvatarToTextArt(getattr(self.user, "avatar", None))
            await asyncio.wait_for(asyncio.to_thread(art.create_art), timeout=3)
            art_str = art.get_colored_ascii_art()
        except: pass
        banner = "\n\n\n" + (art_str + "\n" if art_str else "")
        banner += "\033[38;2;88;101;242m" + "Welcome to Discord!".center(term) + "\033[0m\n\033[92m"
        banner += "\n".join(line.center(term) for line in text2art(self.user.name[:11], 'sub-zero').splitlines())
        banner += f"🌐 Connected: {len(self.guilds)} servers | Users ~{sum(g.member_count or 0 for g in self.guilds)}".center(term)
        print(banner)
        await self.change_presence(
            status=discord.Status.idle,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"@{self.user.name} help"
            ))
        await setup_persistent_views_fun(self)
        await setup_persistent_views(self)
        # Initialize per-server shard configurations
        for guild in self.guilds:
            await self._configure_server_shards(guild)

    async def _configure_server_shards(self, guild):
        """Configure unique shard allocation for each server"""
        guild_id = guild.id
        if guild_id not in Config.SERVER_SHARD_MAPPING:
            # Dynamically assign shards based on server size
            member_count = guild.member_count or 100
            shard_count = max(1, min(10, member_count // 1000))  # Example scaling
            Config.SERVER_SHARD_MAPPING[guild_id] = {
                'shard_count': shard_count,
                'priority': member_count / 1000,  # Prioritize larger servers
            }
            self.server_shards[guild_id] = shard_count
            logger.info(f"Configured {shard_count} shards for guild {guild_id}")

    async def _remove_server_shards(self, guild):
        """Remove shard configuration for a server"""
        guild_id = guild.id
        if guild_id in Config.SERVER_SHARD_MAPPING:
            del Config.SERVER_SHARD_MAPPING[guild_id]
            if guild_id in self.server_shards:
                del self.server_shards[guild_id]
            logger.info(f"Removed shard configuration for guild {guild_id}")
            # Optional: Trigger shard rebalance if needed
            await self._rebalance_shards()

    async def _rebalance_shards(self):
        """Rebalance shards across servers (placeholder for advanced logic)"""
        total_shards = sum(config['shard_count'] for config in Config.SERVER_SHARD_MAPPING.values())
        logger.info(f"Rebalanced shards: Total allocated shards now {total_shards}")

    async def on_guild_join(self, guild):
        logger.info(f"Bot added to guild: {guild.name} (ID: {guild.id})")
        await self._configure_server_shards(guild)

    async def on_guild_remove(self, guild):
        logger.info(f"Bot removed from guild: {guild.name} (ID: {guild.id})")
        await self._remove_server_shards(guild)

    async def on_shard_ready(self, shard_id: int):
        logger.info(f"✅ Shard {shard_id} is ready.")

    async def on_shard_disconnect(self, shard_id: int):
        logger.warning(f"⚠️ Shard {shard_id} disconnected. Reconnecting...")

    async def on_shard_resumed(self, shard_id: int):
        logger.info(f"🔄 Shard {shard_id} resumed.")

    async def close(self):
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    async def _import_cogs(self):
        tree = Tree("[bold cyan]◇ Loading Cogs[/bold cyan]")
        for dir_name in self.cog_dirs:
            branch = tree.add(f"[bold magenta]□ {dir_name}[/bold magenta]")
            try:
                package = importlib.import_module(dir_name)
            except ModuleNotFoundError as e:
                branch.add(f"[red]Could not import {dir_name}: {e}[/red]")
                logger.error(f"Failed to import package {dir_name}", exc_info=True)
                continue

            for _, mod_name, is_pkg in pkgutil.iter_modules(package.__path__):
                if is_pkg: 
                    continue
                leaf = branch.add(mod_name + ".py")
                cache_key = f"{dir_name}.{mod_name}"
                if cache_key in self.cog_cache:
                    leaf.label = f"[green]□ {mod_name}.py (cached)[/green]"
                    continue
                try:
                    mod = importlib.import_module(f"{dir_name}.{mod_name}")
                    cog_found = False
                    for obj in vars(mod).values():
                        if (isinstance(obj, type) and issubclass(obj, commands.Cog) 
                                and obj is not commands.Cog and not self.get_cog(obj.__name__)):
                            cog_found = True
                            try:
                                cog_instance = obj(self)
                                await self.add_cog(cog_instance)
                                self.cog_cache[cache_key] = cog_instance
                                leaf.label = f"[green]□ {mod_name}.py[/green]"
                                leaf.add(f"[cyan]→[/cyan] [bold white]{obj.__name__}[/bold white]")
                                for cmd in cog_instance.get_commands():
                                    cmd._buckets = commands.CooldownMapping.from_cooldown(rate, per, commands.BucketType.user)
                            except Exception as e:
                                leaf.label = f"[red]□ {mod_name}.py[/red]"
                                leaf.add(f"[red]Instantiation Error: {type(e).__name__}: {e}[/red]")
                                logger.error(f"Error instantiating cog {mod_name}.{obj.__name__}", exc_info=True)
                    if not cog_found:
                        leaf.label = f"[yellow]□ {mod_name}.py[/yellow]"
                except Exception as e:
                    leaf.label = f"[red]□ {mod_name}.py[/red]"
                    leaf.add(f"[red]Import Error: {type(e).__name__}: {e}[/red]")
                    logger.error(f"Error importing cog {dir_name}.{mod_name}", exc_info=True)

        self.console.print(Align(tree, align='center', width=self.console.width))

class BotRunner:
    @staticmethod
    async def _run_bot():
        bot = ClusteredBot()
        token = await get_bot_token()
        if not token:
            logger.error("No token found.")
            return
        await bot.start(token, reconnect=True)

    @staticmethod
    def _install_signal_handlers(loop):
        def _graceful(*_): [t.cancel() for t in asyncio.all_tasks(loop)]
        for sig in (signal.SIGINT, signal.SIGTERM):
            try: loop.add_signal_handler(sig, _graceful)
            except NotImplementedError: signal.signal(sig, lambda *_: _graceful())

    @classmethod
    def main(cls):
        gc.collect()
        threading.Thread(target=FlaskServer().run, daemon=True).start()
        loop = asyncio.new_event_loop()
        cls._install_signal_handlers(loop)
        loop.run_until_complete(cls._run_bot())
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

if __name__ == "__main__":
    BotRunner.main()