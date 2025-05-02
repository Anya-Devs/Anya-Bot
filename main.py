from Data.setup import start
start()

import os
import gc
import asyncio
import requests
import traceback

import aiohttp
from aiohttp import web
import shutil
from art import *
from rich.tree import Tree
from rich.panel import Panel
from rich.align import Align
from rich.console import Console
from dotenv import load_dotenv
from Data.const import AvatarToTextArt
from utils.token import get_bot_token, prefix, use_test_bot as ut
from Imports.log_imports import logger
from Imports.discord_imports import *



load_dotenv(dotenv_path=os.path.join(".github", ".env"))  

class BotSetup(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.members = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(prefix),
            intents=intents,
            help_command=None,
            shard_count=5,
            shard_reconnect_interval=10,
            heartbeat_timeout=120,
        )

    async def on_ready(self):
        avatar_url = self.user.avatar
        art_generator = AvatarToTextArt(avatar_url)
        art_generator.create_art()
        guild_count = len(self.guilds)
        user_count = sum(guild.member_count for guild in self.guilds if guild.member_count)
        print('\n\n\n')
        print(art_generator.get_colored_ascii_art())
        print(f"\033[38;2;88;101;242m{'Welcome to Discord!'.center(__import__('shutil').get_terminal_size().columns)}\033[0m")
        print("\033[92m" + "\n".join(line.center(__import__('shutil').get_terminal_size().columns) for line in text2art(self.user.name.title()[:11], 'sub-zero').splitlines()) + "\033[0m")
        print("\033[96m" + f"🌐  Connected: {guild_count} server{'s' if guild_count != 1 else ''}  |  Users served: ~{user_count}".center(__import__('shutil').get_terminal_size().columns) + "\033[0m")

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
        await self.import_cogs("cogs")
        await self.import_cogs("events")
        print("\033[94m" + " Setup Completed ".center(__import__('shutil').get_terminal_size().columns, "=") + "\033[0m")


    async def import_cogs(self, dir_name):
        print('\n\n\n')

        self.ALIGNMENT = 'center'  

        console = Console()
        tree = Tree(f"[bold cyan]◇ {dir_name}[/bold cyan]")

        for filename in os.listdir(dir_name):
            if filename.endswith(".py"):
                module_name = os.path.splitext(filename)[0]
                file_branch = tree.add(f"[red]{filename}[/red]")
                found = False

                try:
                    module = __import__(f"{dir_name}.{module_name}", fromlist=[""])
                    for obj_name in dir(module):
                        obj = getattr(module, obj_name)
                        if isinstance(obj, commands.CogMeta):
                            if not self.get_cog(obj_name):
                                await self.add_cog(obj(self))
                                if not found:
                                    file_branch.label = f"[green]□ {filename}[/green]"
                                    found = True
                                file_branch.add(f"[cyan]→[/cyan] [bold white]{obj_name}[/bold white]")
                except Exception as e:
                    file_branch.add(f"[red]Error: {type(e).__name__}: {e}[/red]")

        aligned_output = Align(tree, align=self.ALIGNMENT, width=console.width)
        console.print(aligned_output)



async def handle_index(request):
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
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://{host}:{port}") as r:
                    if r.status == 200:
                        return
        except:
            pass
        await asyncio.sleep(60)

async def start_all_services():
    gc.collect()
    runner = site = None
    try:
        bot_setup = BotSetup()
        runner, site = await start_web_server()
        port = site._server.sockets[0].getsockname()[1]
        await asyncio.gather(
            bot_setup.start_bot(),
            periodic_ping("localhost", port)
        )
    except Exception:
        traceback.print_exc()
    finally:
        if runner:
            await runner.cleanup()
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(start_all_services())