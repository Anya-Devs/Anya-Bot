from Data.setup import start  # Set everything up first
start()

import os
import gc
import asyncio
import aiohttp
import traceback
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
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8080"):
                    pass
        except Exception as e:
            logger.error(f"Ping failed: {e}")
        await asyncio.sleep(300)

async def start_http_server():
    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="✅ Bot is running"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    asyncio.create_task(periodic_ping())
    print("🌍 HTTP server started on port 8080")

async def run_bot():
    while True:
        bot = BotSetup()
        try:
            await check_rate_limit()
            await bot.start_bot()
        except Exception as e:
            logger.error(f"❌ Bot crashed: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)

async def start_server():
    while True:
        gc.collect()
        try:
            http_task = asyncio.create_task(start_http_server())
            bot_task = asyncio.create_task(run_bot())
            await asyncio.gather(http_task, bot_task)
        except Exception as e:
            logger.error(f"🔥 Fatal error in main loop: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(start_server())
