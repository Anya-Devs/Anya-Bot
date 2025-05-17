from data.setup  import start
start()


import os
import sys
import gc
import asyncio
import traceback
import importlib
import pkgutil
import aiohttp
from aiohttp import web
from art import text2art
from rich.tree import Tree
from rich.align import Align
from rich.console import Console
from dotenv import load_dotenv
from data.const import AvatarToTextArt
from bot.token import get_bot_token, prefix, use_test_bot as ut
from imports.log_imports import logger
from imports.discord_imports import *
from utils.cogs.ticket import setup_persistent_views

# Add the current directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
load_dotenv(dotenv_path=os.path.join(".github", ".env"))

class BotSetup(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.members = True
        super().__init__(
            command_prefix=commands.when_mentioned_or(prefix),
            intents=intents,
            help_command=None,
            shard_count=100,
            shard_reconnect_interval=20,
            heartbeat_timeout=120
        )
        self.cog_dirs = ['bot.cogs', 'bot.events']

    async def on_ready(self):
        try:
            avatar = self.user.avatar
            art = AvatarToTextArt(avatar)
            art.create_art()
            
            guilds = len(self.guilds)
            users = sum(g.member_count or 0 for g in self.guilds)
            term = __import__('shutil').get_terminal_size().columns

            msg2 = "🌐  Connected: {} server{}  |  Users served: ~{}".format(guilds, 's'*(guilds!=1), users)

            msg = f"\n\n\n{art.get_colored_ascii_art()}\n\033[38;2;88;101;242m{'Welcome to Discord!'.center(term)}\033[0m\n\033[92m" + "\n".join(line.center(term) for line in text2art(self.user.name.title()[:11], 'sub-zero').splitlines()) + msg2
            print(msg)

            # Setup persistent ticket views with proper error handling
            try:
                await setup_persistent_views(self)
                print("✅ Persistent ticket views restored.")
            except Exception as e:
                print(f"❌ Failed to restore persistent ticket views: {str(e)}")
                logger.error(f"Persistent views error: {str(e)}\n{traceback.format_exc()}")
        except Exception as e:
            logger.error(f"Error in on_ready: {str(e)}\n{traceback.format_exc()}")

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
                    if isinstance(obj, type) and issubclass(obj, commands.Cog) and obj is not commands.Cog:
                        if self.get_cog(obj.__name__):
                            continue
                        await self.add_cog(obj(self))
                        if not found:
                            branch.label = f"[green]□ {mod_name}.py[/green]"
                            found = True
                        branch.add(f"[cyan]→[/cyan] [bold white]{obj.__name__}[/bold white]")
            except Exception as e:
                branch.add(f"[red]Error: {type(e).__name__}: {e}[/red]")
                logger.error(f"Error loading cog {mod_name}: {str(e)}\n{traceback.format_exc()}")
                
        console.print(Align(tree, align='center', width=console.width))

async def handle_index(_):
    return web.Response(text="✅ Bot is running", content_type="text/html")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_index)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 0 if ut else 8080)
    await site.start()
    return runner, site

async def periodic_ping(host, port):
    while True:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"http://{host}:{port}") as r:
                    if r.status == 200:
                        logger.debug("Ping successful!")
        except Exception as e:
            logger.debug(f"Ping failed: {str(e)}")
        await asyncio.sleep(60)

async def start_all_services():
    gc.collect()
    runner = site = None
    try:
        bot = BotSetup()
        runner, site = await start_web_server()
        port = site._server.sockets[0].getsockname()[1]
        
        print(f"Web server started on port {port}")
        
        await asyncio.gather(
            bot.start_bot(),
            periodic_ping("localhost", port)
        )
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Fatal error: {str(e)}\n{traceback.format_exc()}")
    finally:
        if runner:
            await runner.cleanup()
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(start_all_services())
