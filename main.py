#import asyncio;from data.setup import SetupManager;asyncio.run(SetupManager().run_setup())  
import os, sys, gc, importlib, pkgutil, threading, signal, traceback, asyncio, shutil, glob
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

# Check and install FFmpeg on startup
#from utils.ffmpeg_installer import install_ffmpeg
#install_ffmpeg()



# Disk cleanup functionality
class DiskCleanup:
    """Handles disk cleanup for temporary files and cache"""
    
    @staticmethod
    def cleanup_temp_files():
        """Clean up temporary audio files, cache, and other temporary data"""
        cleaned_files = 0
        cleaned_size = 0
        
        try:
            # Clean yt-dlp cache
            import tempfile
            temp_dir = tempfile.gettempdir()
            
            # Clean yt-dlp temporary files
            yt_patterns = [
                os.path.join(temp_dir, "yt-dlp-*"),
                os.path.join(temp_dir, "youtube-dl-*"),
                "*.part",
                "*.ytdl",
                "*.f4m",
                "*.f4f"
            ]
            
            for pattern in yt_patterns:
                for file_path in glob.glob(pattern):
                    try:
                        if os.path.isfile(file_path):
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_files += 1
                            cleaned_size += size
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Could not remove {file_path}: {e}")
            
            # Clean project-specific temp files
            project_temp_patterns = [
                "youtube-search-server-*.db",
                "*.tmp",
                "*.temp",
                "cache_*.json",
                "*.pyc",
                "__pycache__",
            ]
            
            for pattern in project_temp_patterns:
                for file_path in glob.glob(pattern):
                    try:
                        if os.path.isfile(file_path):
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_files += 1
                            cleaned_size += size
                        elif os.path.isdir(file_path) and file_path.endswith("__pycache__"):
                            shutil.rmtree(file_path, ignore_errors=True)
                            cleaned_files += 1
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Could not remove {file_path}: {e}")
            
            # Clean .pyc files recursively
            for root, dirs, files in os.walk("."):
                for file in files:
                    if file.endswith(".pyc"):
                        file_path = os.path.join(root, file)
                        try:
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_files += 1
                            cleaned_size += size
                        except (OSError, PermissionError):
                            pass
                
                # Remove empty __pycache__ directories
                dirs[:] = [d for d in dirs if not d.startswith("__pycache__") or 
                          (any(os.scandir(os.path.join(root, d))) if os.path.exists(os.path.join(root, d)) else False)]
            
            if cleaned_files > 0:
                size_mb = cleaned_size / (1024 * 1024)
                logger.info(f"Disk cleanup: Removed {cleaned_files} files ({size_mb:.2f} MB)")
            
        except Exception as e:
            logger.error(f"Disk cleanup error: {e}")
    
    @staticmethod
    async def periodic_cleanup():
        """Run periodic disk cleanup every 2 hours"""
        while True:
            await asyncio.sleep(7200)  # 2 hours
            DiskCleanup.cleanup_temp_files()
    
    @staticmethod
    def startup_cleanup():
        """Run cleanup on startup"""
        logger.info("Running startup disk cleanup...")
        DiskCleanup.cleanup_temp_files()
        logger.info("Startup disk cleanup completed")

# Run startup cleanup
DiskCleanup.startup_cleanup()

def patch_discord_gateway(env_gateway="wss://gateway.discord.gg/"):  
    class CustomHTTP(discord.http.HTTPClient):  
        async def get_gateway(self, **_):  
            return f"{env_gateway}?encoding=json&v=10"  
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
    PORT = int(os.environ.get("PORT", 5000))  
    USE_PRESENCE = os.environ.get("USE_PRESENCE_INTENTS", "0").strip().lower() not in ("0", "false", "no")  
    COOLDOWN = [  
        'rate_limit_count', 1,  
        'per_seconds', 5,  
        'type', commands.BucketType.user  
    ]  
    SERVER_SHARD_MAPPING = {}  
    SHARD_POOL_SIZE = 100  
discord.Client.MAX_MESSAGES = 800 # limit message cache size  
discord.Client.member_cache_flags = discord.MemberCacheFlags.none() # minimal member caching  
gc.enable()  
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
        logger.info(f"Starting Flask server on port {self.port}")  
        self.app.run(host="0.0.0.0", port=self.port, threaded=True)  
class ClusteredBot(commands.AutoShardedBot):  
    def __init__(self):  
        intents = discord.Intents.default()
        intents.members = True 
        intents.presences = True 
        intents.message_content = True 
        super().__init__(  
            command_prefix=commands.when_mentioned_or(prefix),  
            intents=intents,  
            help_command=None,  
            shard_ids=None,  
            shard_count=None,  
            shard_reconnect_interval=15,  
            heartbeat_timeout=90,  
            chunk_guilds_at_startup=False,  
            guild_ready_timeout=5.0,  
            max_concurrency=Config.SHARD_POOL_SIZE,  
            max_messages=800,  
        )  
        self.cog_dirs = ['bot.cogs', 'bot.events']  
        self.console = Console()  
        self.http_session: aiohttp.ClientSession | None = None  
        self.cog_cache = {}  
        self.server_shards = {}  
        self._gc_task = None  
    async def setup_hook(self):  
        await self._import_cogs()  
        # Enhanced connector settings for better stability  
        connector = aiohttp.TCPConnector(  
            limit=Config.SHARD_POOL_SIZE,  
            ttl_dns_cache=300,  
            use_dns_cache=True,  
            keepalive_timeout=60,  
            enable_cleanup_closed=True,  
            force_close=False  
        )  
        # Enhanced timeout settings  
        timeout = aiohttp.ClientTimeout(  
            total=30,  
            connect=10,  
            sock_read=15  
        )  
        self.http_session = aiohttp.ClientSession(  
            timeout=timeout,  
            connector=connector,  
            headers={  
                'User-Agent': 'Discord Bot (https://github.com/discord/discord-api-docs, 1.0)'  
            }  
        )  
        self._gc_task = asyncio.create_task(self._run_periodic_gc())  
        # Start periodic disk cleanup task
        self._cleanup_task = asyncio.create_task(DiskCleanup.periodic_cleanup())
    async def _run_periodic_gc(self):  
        while True:  
            gc.collect()  
            await asyncio.sleep(600)  
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
        for guild in self.guilds:  
            await self._configure_server_shards(guild)  
    async def _configure_server_shards(self, guild):  
        guild_id = guild.id  
        if guild_id not in Config.SERVER_SHARD_MAPPING:  
            member_count = guild.member_count or 100  
            shard_count = max(1, min(10, member_count // 1000))  
            Config.SERVER_SHARD_MAPPING[guild_id] = {  
                'shard_count': shard_count,  
                'priority': member_count / 1000,  
            }  
            self.server_shards[guild_id] = shard_count  
            logger.info(f"Configured {shard_count} shards for guild {guild_id}")  
    async def _remove_server_shards(self, guild):  
        guild_id = guild.id  
        if guild_id in Config.SERVER_SHARD_MAPPING:  
            del Config.SERVER_SHARD_MAPPING[guild_id]  
            if guild_id in self.server_shards:  
                del self.server_shards[guild_id]  
            logger.info(f"Removed shard configuration for guild {guild_id}")  
            await self._rebalance_shards()  
    async def _rebalance_shards(self):  
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
        if self._gc_task:  
            self._gc_task.cancel()  
            try:  
                await self._gc_task  
            except asyncio.CancelledError:  
                pass  
        if hasattr(self, '_cleanup_task') and self._cleanup_task:  
            self._cleanup_task.cancel()  
            try:  
                await self._cleanup_task  
            except asyncio.CancelledError:  
                pass  
        # Run final disk cleanup on shutdown
        DiskCleanup.cleanup_temp_files()
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
        try:  
            await bot.start(token, reconnect=True)  
        except Exception as e:  
            logger.error(f"Bot startup failed: {type(e).__name__}: {e}")  
            traceback.print_exc()  
        finally:  
            if not bot.is_closed():  
                await bot.close()  
    @staticmethod  
    def _install_signal_handlers(loop):  
        def _graceful(*_):  
            logger.info("Received shutdown signal, gracefully shutting down...")  
            for task in asyncio.all_tasks(loop):  
                task.cancel()  
        for sig in (signal.SIGINT, signal.SIGTERM):  
            try:  
                loop.add_signal_handler(sig, _graceful)  
            except NotImplementedError:  
                signal.signal(sig, lambda *_: _graceful())  
    @classmethod  
    def main(cls):  
        gc.collect()  
        threading.Thread(target=FlaskServer().run, daemon=True).start()  
        loop = asyncio.new_event_loop()  
        asyncio.set_event_loop(loop)  
        cls._install_signal_handlers(loop)  
        try:  
            loop.run_until_complete(cls._run_bot())  
        except KeyboardInterrupt:  
            logger.info("Received keyboard interrupt")  
        except Exception as e:  
            logger.error(f"Unexpected error in main loop: {e}")  
            traceback.print_exc()  
        finally:  
            try:  
                # Cancel all remaining tasks  
                pending = asyncio.all_tasks(loop)  
                for task in pending:  
                    task.cancel()  
                if pending:  
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))  
                loop.run_until_complete(loop.shutdown_asyncgens())  
            except Exception as e:  
                logger.error(f"Error during cleanup: {e}")  
            finally:  
                loop.close()  
if __name__ == "__main__":  
    BotRunner.main()