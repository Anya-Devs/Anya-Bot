import asyncio; from data.setup import SetupManager; asyncio.run(SetupManager().run_setup())
 
import os, sys, gc, asyncio, traceback, importlib, pkgutil, threading
from dotenv import load_dotenv
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

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv(dotenv_path=os.path.join(".github", ".env"))

# === Web Server ===
app = Flask(__name__, static_folder="html")

@app.route("/")
def index():
    index_path = os.path.join(app.static_folder, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(app.static_folder, "index.html")
    return "⚠️ index.html not found.", 404

@app.route("/html/<path:filename>")
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

def run_flask():
    port = int(os.environ.get("PORT", 10000  if not ut else 0))
    print(f"🌐 Hosting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port)

# === Discord Bot Setup ===
class BotSetup(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.members = True
        self.shard_count = 5 if not ut else None
        super().__init__(
            command_prefix=commands.when_mentioned_or(prefix),
            intents=intents,
            help_command=None,
            shard_count=self.shard_count,
            shard_reconnect_interval=20,
            heartbeat_timeout=120,
        )
        self.cog_dirs = ['bot.cogs', 'bot.events']

    async def on_ready(self):
        try:
            art = AvatarToTextArt(self.user.avatar)
            art.create_art()
            g = self.guilds
            term = __import__('shutil').get_terminal_size().columns
            msg = (
                f"\n\n\n{art.get_colored_ascii_art()}\n"
                f"\033[38;2;88;101;242m{'Welcome to Discord!'.center(term)}\033[0m\n\033[92m"
                + "\n".join(line.center(term) for line in text2art(self.user.name.title()[:11], 'sub-zero').splitlines())
            )
            msg += f"🌐  Connected: {len(g)} server{'s'*(len(g)!=1)}  |  Users served: ~{sum(m.member_count or 0 for m in g)}".center(term)
            print(msg)
            try:
                await setup_persistent_views(self)
            except Exception as e:
                logger.error(f"Persistent views error: {e}\n{traceback.format_exc()}")
        except Exception as e:
            logger.error(f"Error in on_ready: {e}\n{traceback.format_exc()}")

    async def on_disconnect(self):
        print("⚠️ Bot disconnected! Attempting to reconnect...")

    async def on_resumed(self):
        print("✅ Bot session successfully resumed.")

    async def start_bot(self):
        await self.setup()
        try:
            token = await get_bot_token()
            if not token:
                logger.error("No token found. Check database.")
                return
            await self.start(token)
        except Exception as e:
            logger.error(f"Error during bot start: {e}\n{traceback.format_exc()}")
        finally:
            await self.close()

    async def setup(self):
        print("\033[94m" + " Loading Cogs ".center(__import__('shutil').get_terminal_size().columns, "=") + "\033[0m")
        for d in self.cog_dirs:
            await self.import_cogs(d)
        print("\033[94m" + " Setup Completed ".center(__import__('shutil').get_terminal_size().columns, "=") + "\033[0m")

    async def import_cogs(self, dir_name):
        console = Console()
        tree = Tree(f"[bold cyan]◇ {dir_name}[/bold cyan]")
        print('\n\n')
        try:
            package = importlib.import_module(dir_name)
        except ModuleNotFoundError as e:
            tree.add(f"[red]Could not import {dir_name}: {e}[/red]")
            console.print(tree)
            return

        for _, mod_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if is_pkg:
                continue
            branch = tree.add(f"[red]{mod_name}.py[/red]")
            try:
                mod = importlib.import_module(f"{dir_name}.{mod_name}")
                found = False
                for obj in vars(mod).values():
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, commands.Cog)
                        and obj is not commands.Cog
                        and not self.get_cog(obj.__name__)
                    ):
                        await self.add_cog(obj(self))
                        if not found:
                            branch.label = f"[green]□ {mod_name}.py[/green]"
                            found = True
                        branch.add(f"[cyan]→[/cyan] [bold white]{obj.__name__}[/bold white]")
            except Exception as e:
                branch.add(f"[red]Error: {type(e).__name__}: {e}[/red]")
                logger.error(f"Error loading cog {mod_name}: {e}\n{traceback.format_exc()}")
        console.print(Align(tree, align='center', width=console.width))


def main():
    gc.collect()
    threading.Thread(target=run_flask, daemon=True).start()
    bot = BotSetup()
    asyncio.run(bot.start_bot())


if __name__ == "__main__":
    main()
