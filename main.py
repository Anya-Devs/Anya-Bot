from Data.setup import start  # Set everything up first
start()

import os
import gc
import asyncio
import aiohttp
import traceback
import uvicorn
from aiohttp import web
from motor.motor_asyncio import AsyncIOMotorClient
from Data.const import AvatarToTextArt
from Data.utils.token_utils import get_bot_token, prefix
from Imports.log_imports import logger
from Imports.discord_imports import *
from Imports.depend_imports import *
from dotenv import load_dotenv

if __name__ == "__main__":
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
        avatar_url = self.user.avatar
        art_generator = AvatarToTextArt(avatar_url, new_size=75)
        art_generator.create_art()
        print(art_generator.get_colored_ascii_art())
        print("\033[38;2;88;101;242mWelcome to Discord!\033[0m")

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
        for filename in os.listdir(dir_name):
            if filename.endswith(".py"):
                module_name = os.path.splitext(filename)[0]
                module = __import__(f"{dir_name}.{module_name}", fromlist=[""])
                for obj_name in dir(module):
                    obj = getattr(module, obj_name)
                    if isinstance(obj, commands.CogMeta):
                        if not self.get_cog(obj_name):
                            await self.add_cog(obj(self))

async def check_rate_limit():
    url = "https://discord.com/api/v10/users/@me"
    token = await get_bot_token()
    headers = {"Authorization": f"Bot {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
                reset_after = float(response.headers.get("X-RateLimit-Reset-After", 0))
                if remaining <= 0:
                    await asyncio.sleep(reset_after)

async def periodic_ping():
    """Periodically pings the server to ensure it's up."""
    retries = 5  # Maximum number of retries
    while retries > 0:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8080"):
                    print("Ping successful!")
                    return  # Exit once the ping is successful
        except Exception as e:
            logger.error(f"Ping failed: {e}")
            retries -= 1
            await asyncio.sleep(5)  # Wait 5 seconds before retrying

    # If we exhausted all retries and still couldn't ping the server
    logger.error("Failed to ping server after multiple attempts.")

# === Uvicorn Compatible HTTP Server ===
async def handle_index(request):
    return web.Response(text="✅ Bot is running", content_type="text/html")

def create_app():
    """Returns an ASGI app instance for Uvicorn."""
    app = web.Application()
    app.router.add_get("/", handle_index)
    return app  # Directly return the app

async def start_services():
    """Starts both the bot and HTTP server tasks."""
    gc.collect()
    try:
        bot_setup = BotSetup()
        bot_task = asyncio.create_task(bot_setup.start_bot())  # Start bot
       
        # Start Uvicorn and wait until it's fully ready
        uvicorn_task = asyncio.create_task(start_uvicorn())  # Start Uvicorn server
        await asyncio.gather(bot_task, uvicorn_task)  # Wait for both tasks to complete
       
        # Start the periodic ping task after Uvicorn is ready
        ping_task = asyncio.create_task(periodic_ping())
        await ping_task  # Let it run
    except Exception as e:
        logger.error(f"🔥 Fatal error in main loop: {e}\n{traceback.format_exc()}")
        await asyncio.sleep(10)

async def start_uvicorn():
    """Run the Uvicorn ASGI server."""
    config = uvicorn.Config(create_app(), host="0.0.0.0", port=8080, loop="asyncio")
    server = uvicorn.Server(config)
    print("Starting Uvicorn server...")
    await server.serve()
    print("Uvicorn server started.")

if __name__ == "__main__":
    asyncio.run(start_services())  # Use asyncio.run instead of get_event_loop
    asyncio.run(start_uvicorn())  # Runs Uvicorn
