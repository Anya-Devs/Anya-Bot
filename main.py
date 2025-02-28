"""-----------------------""" 

from Data.setup import start  # Set everything up first
start()

"""-----------------------"""

import os
import gc
import shutil
import asyncio
import aiohttp
import traceback
from aiohttp import web
from art import *
from rich.tree import Tree
from rich.console import Console
from motor.motor_asyncio import AsyncIOMotorClient
from Data.const import AvatarToTextArt
from Imports.log_imports import logger
from Imports.discord_imports import *
from Imports.depend_imports import *
from dotenv import load_dotenv
import socket  

# Load environment variables from the .env file inside the ".github" directory.
if __name__ == "__main__":
    load_dotenv(dotenv_path=os.path.join(".github", ".env"))

#print("\033[93mLoaded Environment Variables:\033[0m")
#for key, value in os.environ.items():
#    if key.startswith(("TOKEN", "PASSWORD", "SECRET")):
#        print(f"{key} = [REDACTED]")
#    else:
#        print(f"{key} = {value}")


class BotSetup(commands.AutoShardedBot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.members = True
        self.prefix = "..."
        super().__init__(
            command_prefix=commands.when_mentioned_or(self.prefix),
            intents=intents,
            help_command=None,
            shard_count=5,
            shard_reconnect_interval=10,
            heartbeat_timeout=120,
        )
        self.mongo_client = None
        self.DB_NAME = "Bot"
        self.COLLECTION_NAME = "information"
        self.token_field = "Token"

   

    async def on_ready(self):
        avatar_url = self.user.avatar
        art_generator =  AvatarToTextArt(avatar_url, new_width=25)
        art_generator.create_art()
        print(art_generator.get_colored_ascii_art())
        print("\033[38;2;88;101;242mWelcome to Discord!\033[0m")
        Login_Text=text2art(f"{self.user.name.title()[:10]}", "sub-zero")
        print(f"\033[92m{Login_Text}\033[0m")



    async def get_token_from_db(self):
        mongo_url = os.getenv("MONGO_URI")
        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")
        self.mongo_client = AsyncIOMotorClient(mongo_url)
        db = self.mongo_client[self.DB_NAME]
        collection = db[self.COLLECTION_NAME]
        token_data = await collection.find_one({self.token_field: {"$exists": True}})
        if token_data:
            return token_data.get(self.token_field)
        raise ValueError("No token found in the database")

    async def start_bot(self):
        await self.setup()
        token = await self.get_token_from_db()
        if not token:
            logger.error("No token found. Check database.")
            return
        try:
            await self.start(token)
        except KeyboardInterrupt:
            await self.close()
        except Exception as e:
            logger.error(f"Error during bot start: {e}\n{traceback.format_exc()}")
        finally:
            if self.is_closed():
                print("Bot is closed, cleaning up.")
            else:
                print("Bot is still running.")
            await self.close()

    async def setup(self):
        await self.import_cogs("Cogs")
        await self.import_cogs("Events")
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

async def check_rate_limit():
    url = "https://discord.com/api/v10/users/@me"
    bot_instance = BotSetup()
    token = await bot_instance.get_token_from_db()
    headers = {"Authorization": f"Bot {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
                reset_after = float(response.headers.get("X-RateLimit-Reset-After", 0))
                if remaining <= 0:
                    logger.error(f"Rate limit exceeded. Retry after {reset_after} seconds.")
                    print(f"Rate limit exceeded. Waiting {reset_after} seconds.")
                    await asyncio.sleep(reset_after)
            else:
                logger.error(f"Failed to check rate limit. Status code: {response.status}")

async def start_http_server():
    app = web.Application()

    async def handle_index(request):
        return web.Response(text="Bot is running", content_type="text/html")

    app.router.add_get("/", handle_index)
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 8080))

    if not is_port_available(port):
        print(f"Port {port} is already in use. Please free up the port or specify another one.")
        return

    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"HTTP server started on port {port}")

def is_port_available(port):
    """Checks if a port is available by attempting to bind to it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except socket.error:
            return False


async def run_bot():
    while True:
        bot = BotSetup()
        try:
            await check_rate_limit()
            await bot.start_bot()
        except Exception as e:
            logger.error(f"Bot crashed: {e}\n{traceback.format_exc()}")
            print("Bot crashed, restarting in 10 seconds.")
            await asyncio.sleep(10)

async def start_server():
    gc.collect() 
    await asyncio.gather(
        start_http_server(),
        run_bot(),
    )

if __name__ == "__main__":
    asyncio.run(start_server())
