# installs stuff
import asyncio; from data.setup import SetupManager; asyncio.run(SetupManager().run_setup())


import os, sys, gc, asyncio, importlib, pkgutil, threading, signal
from urllib.parse import quote_plus
from collections import namedtuple
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(".github", ".env"))

import aiohttp, yarl, discord
from flask import Flask, send_from_directory
from art import text2art
from rich.tree import Tree
from rich.align import Align
from rich.console import Console
from data.local.const import AvatarToTextArt
from bot.token import get_bot_token, prefix, use_test_bot as ut
from imports.log_imports import logger
from imports.discord_imports import *
from utils.cogs.ticket import setup_persistent_views

def patch_discord_gateway(env_gateway: str = "wss://gateway.discord.gg/"):
    class CustomHTTP(discord.http.HTTPClient):
        async def get_gateway(self, **_):
            return f"{env_gateway}?encoding=json&v=10"

        async def get_bot_gateway(self, **_):
            data = await self.request(discord.http.Route("GET", "/gateway/bot"))
            return data["shards"], f"{env_gateway}?encoding=json&v=10", data.get("session_start_limit", {})

    class CustomWebSocket(discord.gateway.DiscordWebSocket):
        DEFAULT_GATEWAY = yarl.URL(env_gateway)
        def is_ratelimited(self):
            return False

    discord.http.HTTPClient.get_gateway = CustomHTTP.get_gateway
    discord.http.HTTPClient.get_bot_gateway = CustomHTTP.get_bot_gateway
    discord.gateway.DiscordWebSocket.DEFAULT_GATEWAY = CustomWebSocket.DEFAULT_GATEWAY
    discord.gateway.DiscordWebSocket.is_ratelimited = CustomWebSocket.is_ratelimited

patch_discord_gateway()

class Config:
    PORT = int(os.environ.get("PORT", 8081))
    SHARD_IDS = os.environ.get("SHARD_IDS", "").strip()
    SHARD_COUNT = os.environ.get("SHARD_COUNT", "auto").strip().lower()
    USE_PRESENCE = os.environ.get("USE_PRESENCE_INTENTS", "0").strip() not in ("0","false","no")

    @staticmethod
    def parse_shard_ids():
        raw = Config.SHARD_IDS
        if not raw: return None
        ids = []
        for part in raw.split(","):
            part = part.strip()
            if not part: continue
            if "-" in part:
                a, b = map(int, part.split("-", 1))
                ids.extend(range(a, b + 1))
            else:
                ids.append(int(part))
        return sorted(set(ids))

    @staticmethod
    def shard_count():
        val = Config.SHARD_COUNT
        if not val or val == "auto": return None
        try: return int(val)
        except: return None

app = Flask(__name__, static_folder="html")

@app.route("/")
def index():
    p = os.path.join(app.static_folder, "index.html")
    return send_from_directory(app.static_folder, "index.html") if os.path.exists(p) else ("⚠️ index.html not found.", 404)

@app.route("/html/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

def run_flask():
    print(f"🌐 Hosting Flask server on port {Config.PORT}")
    app.run(host="0.0.0.0", port=Config.PORT, threaded=True)

class BotSetup(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        intents.members = False
        intents.presences = bool(Config.USE_PRESENCE)

        member_cache_flags = discord.MemberCacheFlags.none()
        allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True, replied_user=False)

        shard_count = Config.shard_count() if not ut else None
        shard_ids = Config.parse_shard_ids() if not ut else None

        super().__init__(
            command_prefix=commands.when_mentioned_or(prefix),
            intents=intents,
            help_command=None,
            shard_count=shard_count,
            shard_ids=shard_ids,
            shard_reconnect_interval=15,
            heartbeat_timeout=90,
            chunk_guilds_at_startup=False,
            guild_ready_timeout=5.0,
            max_messages=1000,
            allowed_mentions=allowed_mentions,
            member_cache_flags=member_cache_flags
        )

        self.cog_dirs = ['bot.cogs', 'bot.events']
        self.console = Console()
        self.http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        await self._import_cogs()
        try:
            self.http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        except Exception as e:
            logger.warning(f"aiohttp session init failed: {e}")

    async def on_ready(self):
        try:
            term = __import__('shutil').get_terminal_size().columns
            name = (self.user.name if self.user else "Bot")[:11].title()
            art_str = ""
            g = self.guilds
            try:
                art = AvatarToTextArt(getattr(self.user, "avatar", None))
                await asyncio.wait_for(asyncio.to_thread(art.create_art), timeout=3.0)
                art_str = art.get_colored_ascii_art()
            except Exception: pass
            banner = "\n\n\n" + (art_str + "\n" if art_str else "")
            banner += f"\033[38;2;88;101;242m{'Welcome to Discord!'.center(term)}\033[0m\n\033[92m"
            banner += "\n".join(line.center(term) for line in text2art(name, 'sub-zero').splitlines())
            banner +=  f"🌐 Connected: {len(g)} server{'s'*(len(g)!=1)}  |  Users served: ~{sum(m.member_count or 0 for m in g)}".center(term)
            print(banner)
            try: await setup_persistent_views(self)
            except Exception as e: logger.error(f"Persistent views error: {e}")
        except Exception as e:
            logger.error(f"on_ready error: {e}")

    async def close(self):
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        await super().close()

    async def _import_cogs(self):
        console, tree = self.console, Tree(f"[bold cyan]◇ Loading Cogs[/bold cyan]")
        for dir_name in self.cog_dirs:
            branch_dir = tree.add(f"[bold magenta]□ {dir_name}[/bold magenta]")
            try: package = importlib.import_module(dir_name)
            except ModuleNotFoundError as e:
                branch_dir.add(f"[red]Could not import {dir_name}: {e}[/red]"); continue
            for _, mod_name, is_pkg in pkgutil.iter_modules(package.__path__):
                if is_pkg: continue
                leaf = branch_dir.add(f"[yellow]{mod_name}.py[/yellow]")
                try:
                    mod = importlib.import_module(f"{dir_name}.{mod_name}")
                    for obj in vars(mod).values():
                        if isinstance(obj, type) and issubclass(obj, commands.Cog) and obj is not commands.Cog and not self.get_cog(obj.__name__):
                            await self.add_cog(obj(self))
                            leaf.label = f"[green]□ {mod_name}.py[/green]"
                            leaf.add(f"[cyan]→[/cyan] [bold white]{obj.__name__}[/bold white]")
                except Exception as e:
                    leaf.add(f"[red]Error: {type(e).__name__}: {e}[/red]")
                    logger.error(f"Error loading cog {mod_name}: {e}")
        console.print(Align(tree, align='center', width=console.width))

async def _run_bot():
    bot = BotSetup()
    try:
        token = await get_bot_token()
        if not token: logger.error("No token found."); return
        await bot.start(token, reconnect=True)
    except (KeyboardInterrupt, SystemExit): pass
    except Exception as e: logger.error(f"Error during bot start: {e}")
    finally: await bot.close()

def _install_signal_handlers(loop):
    def _graceful(*_): [task.cancel() for task in asyncio.all_tasks(loop)]
    for sig in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(sig, _graceful)
        except NotImplementedError: signal.signal(sig, lambda *_: _graceful())

def main():
    gc.collect()
    threading.Thread(target=run_flask, daemon=True).start()
    loop = asyncio.new_event_loop()
    _install_signal_handlers(loop)
    try: loop.run_until_complete(_run_bot())
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

if __name__ == "__main__":
    main()
