from Data.setup import start
start()

# Standard Library
import os
import gc
import asyncio
import traceback

import aiohttp
from aiohttp import web

from art import *
from rich.tree import Tree
from rich.console import Console
from dotenv import load_dotenv
from Data.const import AvatarToTextArt
from Data.utils.token_utils import get_bot_token, prefix
from Imports.log_imports import logger
from Imports.discord_imports import *
from Imports.depend_imports import *

load_dotenv(dotenv_path=os.path.join(".github", ".env"))  

class BotSetup(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.members = True
        self.prefix = prefix
        super().__init__(
            command_prefix=commands.when_mentioned_or(self.prefix),
            intents=intents,
            help_command=None,
            shard_count=5,
            shard_reconnect_interval=10,
            heartbeat_timeout=120,
        )

    async def on_ready(self):
        """Triggered when the bot successfully connects to Discord."""
        avatar_url = self.user.avatar
        art_generator = AvatarToTextArt(avatar_url)
        art_generator.create_art()
        print(art_generator.get_colored_ascii_art())
        print(f"\n\033[38;2;88;101;242m{'Welcome to Discord!':^80}\033[0m\n\033[92m{''.join([f'{line:^80}\n' for line in text2art(self.user.name.title()[:11], 'sub-zero').splitlines()])}\033[0m")



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
        await self.import_cogs("cogs")
        await self.import_cogs("events")
        print("\033[94m===== Setup Completed =====\033[0m")

    async def import_cogs(self, dir_name):
        console = Console()
        tree = Tree(f"[bold blue]{dir_name}[/bold blue]")

        for filename in os.listdir(dir_name):
            if filename.endswith(".py"):
                file_branch = tree.add(f"[cyan]{filename}[/cyan]")
                module_name = os.path.splitext(filename)[0]
                module = __import__(f"{dir_name}.{module_name}", fromlist=[""])

                for obj_name in dir(module):
                    obj = getattr(module, obj_name)
                    if isinstance(obj, commands.CogMeta):
                        if not self.get_cog(obj_name):
                            await self.add_cog(obj(self))
                            file_branch.add(f"[green]{obj_name}[/green]")

        console.print(tree)

async def periodic_ping():
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8080") as response:
                    if response.status == 200:
                        return
        except Exception as e:
            logger.error(f"Ping failed: {e}")
        await asyncio.sleep(60) 
        
async def handle_index(request):
    return web.Response(text="✅ Bot is running", content_type="text/html")

def create_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    return app

async def start_web_server():
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("Web server started on http://0.0.0.0:8080")
    return runner  

async def cleanup(runner):
    await runner.cleanup()

async def start_all_services():
    gc.collect()
    runner = None
    try:
        bot_setup = BotSetup()
        runner = await start_web_server()
        
        await asyncio.gather(
            bot_setup.start_bot(),
            periodic_ping()
        )
    except Exception as e:
        logger.error(f"🔥 Fatal error in main loop: {e}\n{traceback.format_exc()}")
    finally:
        if runner:
            await cleanup(runner)
        await asyncio.sleep(1)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_all_services())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
