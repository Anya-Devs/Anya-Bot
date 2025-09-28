import os, sys, gc, asyncio, importlib, pkgutil, threading, signal, multiprocessing
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

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv(dotenv_path=os.path.join(".github", ".env"))

def patch_discord_gateway(env_gateway: str = "wss://gateway.discord.gg/") -> None:
    class CustomHTTP(discord.http.HTTPClient):
        async def get_gateway(self, **_) -> str:
            return f"{env_gateway}?encoding=json&v=10"
        async def get_bot_gateway(self, **_) -> tuple:
            data = await self.request(discord.http.Route("GET", "/gateway/bot"))
            return data["shards"], f"{env_gateway}?encoding=json&v=10", data.get("session_start_limit", {})
    class CustomWebSocket(discord.gateway.DiscordWebSocket):
        DEFAULT_GATEWAY = yarl.URL(env_gateway)
        def is_ratelimited(self) -> bool:
            return False
    discord.http.HTTPClient.get_gateway = CustomHTTP.get_gateway
    discord.http.HTTPClient.get_bot_gateway = CustomHTTP.get_bot_gateway
    discord.gateway.DiscordWebSocket.DEFAULT_GATEWAY = CustomWebSocket.DEFAULT_GATEWAY
    discord.gateway.DiscordWebSocket.is_ratelimited = CustomWebSocket.is_ratelimited

patch_discord_gateway()

class Config:
    PORT: int = int(os.environ.get("PORT", 8081 if not get_bot_token else 0))
    USE_PRESENCE: bool = os.environ.get("USE_PRESENCE_INTENTS", "0").strip().lower() not in ("0", "false", "no")
    COOLDOWN: list = [
        'rate_limit_count', 1,
        'per_seconds', 5,
        'type', commands.BucketType.user
    ]
    TOTAL_SHARDS: int = int(os.environ.get("TOTAL_SHARDS", 0))
    CLUSTERS: int = int(os.environ.get("CLUSTERS", multiprocessing.cpu_count()))
    HEARTBEAT_TIMEOUT: float = 90.0
    GUILD_READY_TIMEOUT: float = 5.0

rate = Config.COOLDOWN[1]
per = Config.COOLDOWN[3]
bucket_type = Config.COOLDOWN[5]

def cooldown_decorator(rate: int, per: float, type: commands.BucketType) -> callable:
    def decorator(func: callable) -> callable:
        func._buckets = commands.CooldownMapping.from_cooldown(rate, per, type)
        return func
    return decorator

class FlaskServer:
    def __init__(self, port: int = Config.PORT):
        self.app = Flask(__name__, static_folder="html")
        self.port = port
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.app.route("/")
        def index():
            p = os.path.join(self.app.static_folder, "index.html")
            return send_from_directory(self.app.static_folder, "index.html") if os.path.exists(p) else ("⚠️ index.html not found.", 404)

        @self.app.route("/html/<path:filename>")
        def serve_static(filename):
            return send_from_directory(self.app.static_folder, filename)

    def run(self) -> None:
        self.app.run(host="0.0.0.0", port=self.port, threaded=True)

class ClusteredBot(commands.Bot):
    def __init__(self, shard_ids: list[int] | int, shard_count: int):
        if isinstance(shard_ids, int):
            shard_ids = [shard_ids]
        self.shard_ids = shard_ids
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=commands.when_mentioned_or(prefix),
            intents=intents,
            help_command=None,
            shard_ids=self.shard_ids,
            shard_count=shard_count,
            heartbeat_timeout=Config.HEARTBEAT_TIMEOUT,
            chunk_guilds_at_startup=False,
            guild_ready_timeout=Config.GUILD_READY_TIMEOUT,
        )
        self.cog_dirs = ['bot.cogs', 'bot.events']
        self.console = Console()
        self.http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self) -> None:
        await self._import_cogs()
        self.http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        logger.info(f"🧩 Shards {self.shard_ids}: Initializing.")

    async def on_ready(self) -> None:
        term = __import__('shutil').get_terminal_size().columns
        art_str = ""
        try:
            art = AvatarToTextArt(getattr(self.user, "avatar", None))
            await asyncio.wait_for(asyncio.to_thread(art.create_art), timeout=3)
            art_str = art.get_colored_ascii_art()
        except Exception as e:
            logger.error(f"Error generating ASCII art: {e}")
        banner = "\n\n\n" + (art_str + "\n" if art_str else "")
        banner += "\033[38;2;88;101;242m" + f"Shards {self.shard_ids} Ready!".center(term) + "\033[0m\n\033[92m"
        banner += "\n".join(line.center(term) for line in text2art(self.user.name[:11], 'sub-zero').splitlines())
        banner += f"🌐 Shards {self.shard_ids} Connected: {len(self.guilds)} servers".center(term)
        print(banner)
        await setup_persistent_views_fun(self)
        await setup_persistent_views(self)

    async def on_disconnect(self) -> None:
        logger.warning(f"⚠️ Shards {self.shard_ids} disconnected.")

    async def on_resumed(self) -> None:
        logger.info(f"🔄 Shards {self.shard_ids} resumed.")

    async def close(self) -> None:
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    async def _import_cogs(self) -> None:
        tree = Tree(f"[bold cyan]◇ Loading Cogs for Shards {self.shard_ids}[/bold cyan]")
        for dir_name in self.cog_dirs:
            await self._import_cogs_from_dir(tree, dir_name)
        self.console.print(Align(tree, align='center', width=self.console.width))

    async def _import_cogs_from_dir(self, tree: Tree, dir_name: str) -> None:
        branch = tree.add(f"[bold magenta]□ {dir_name}[/bold magenta]")
        try:
            package = importlib.import_module(dir_name)
        except ModuleNotFoundError as e:
            branch.add(f"[red]Could not import {dir_name}: {e}[/red]")
            logger.error(f"Failed to import package {dir_name}", exc_info=True)
            return

        for _, mod_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if is_pkg:
                continue
            leaf = branch.add(mod_name + ".py")
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
                            leaf.label = f"[green]□ {mod_name}.py[/green]"
                            leaf.add(f"[cyan]→[/cyan] [bold white]{obj.__name__}[/bold white]")
                            for cmd in cog_instance.get_commands():
                                cooldown_decorator(rate, per, bucket_type)(cmd)
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

async def run_single_shard(shard_id: int, shard_count: int, token: str) -> None:
    bot = ClusteredBot(shard_id, shard_count)
    try:
        await bot.start(token)
    except asyncio.CancelledError:
        logger.info(f"Shard {shard_id} cancelled, shutting down.")
    finally:
        await bot.close()

def run_cluster_processes(cluster_shards: list[int], shard_count: int, token: str) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    gather_tasks = [run_single_shard(shard_id, shard_count, token) for shard_id in cluster_shards]
    try:
        loop.run_until_complete(asyncio.gather(*gather_tasks, return_exceptions=True))
    except KeyboardInterrupt:
        logger.info("Cluster process interrupted, shutting down.")
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

class BotRunner:
    @staticmethod
    async def _get_shard_count(token: str) -> int:
        try:
            loop = asyncio.get_running_loop()
            http = discord.http.HTTPClient(loop=loop)
            await http.static_login(token)
            data = await http.get_bot_gateway()
            await http.close()
            return Config.TOTAL_SHARDS or data[0]
        except Exception as e:
            logger.error(f"Failed to get shard count: {e}")
            raise

    @staticmethod
    async def _run_single_cluster(shard_count: int, token: str) -> None:
        bot = ClusteredBot(list(range(shard_count)), shard_count)
        try:
            await bot.start(token)
        except asyncio.CancelledError:
            logger.info("Single cluster cancelled, shutting down.")
        finally:
            await bot.close()

    @staticmethod
    async def _run_multi_cluster(shard_count: int, token: str) -> None:
        shards_per_cluster = shard_count // Config.CLUSTERS
        extra = shard_count % Config.CLUSTERS
        processes = []
        start_id = 0
        for c in range(Config.CLUSTERS):
            end_id = start_id + shards_per_cluster + (1 if c < extra else 0)
            cluster_shards = list(range(start_id, end_id))
            if cluster_shards:
                p = multiprocessing.Process(target=run_cluster_processes, args=(cluster_shards, shard_count, token))
                p.start()
                processes.append(p)
            start_id = end_id
        for p in processes:
            p.join()

    @staticmethod
    async def _run_bot(flask_server: FlaskServer) -> None:
        token = await get_bot_token()
        if not token:
            logger.error("No token found.")
            return
        shard_count = await BotRunner._get_shard_count(token)
        try:
            if Config.CLUSTERS == 1:
                await BotRunner._run_single_cluster(shard_count, token)
            else:
                await BotRunner._run_multi_cluster(shard_count, token)
        except Exception as e:
            logger.error(f"Error running bot: {e}", exc_info=True)
        finally:
            # Signal Flask server to stop
            flask_server.app.config['RUNNING'] = False

    @staticmethod
    def _install_signal_handlers() -> None:
        def _graceful_shutdown(*_) -> None:
            logger.info("Received shutdown signal, stopping bot and Flask server.")
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for t in tasks:
                t.cancel()
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _graceful_shutdown)

    @staticmethod
    def main() -> None:
        if Config.CLUSTERS > 1:
            multiprocessing.set_start_method('spawn', force=True)
        flask_server = FlaskServer()
        flask_server.app.config['RUNNING'] = True
        flask_thread = threading.Thread(target=flask_server.run, daemon=False)
        flask_thread.start()
        BotRunner._install_signal_handlers()
        try:
            asyncio.run(BotRunner._run_bot(flask_server))
        except KeyboardInterrupt:
            logger.info("Main process interrupted, shutting down.")
        finally:
            flask_server.app.config['RUNNING'] = False
            flask_thread.join()

if __name__ == "__main__":
    BotRunner.main()