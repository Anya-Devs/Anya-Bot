"""-----------------------""" 

from Data.setup import start  # Set everything up first
start()

"""-----------------------"""

import os
import gc
import asyncio
import aiohttp
import traceback
from aiohttp import web
from dotenv import load_dotenv
from Data.utils.token_utils import get_bot_token, prefix
from Imports.log_imports import logger
from Imports.discord_imports import *
from Imports.depend_imports import *

# Load environment variables from .env file inside ".github" directory.
if __name__ == "__main__":
    load_dotenv(dotenv_path=os.path.join(".github", ".env"))


class BotSetup(commands.AutoShardedBot):
    """Main bot class handling setup, startup, and events."""

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
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")

    async def on_disconnect(self):
        """Triggered when the bot disconnects."""
        print("⚠️ Bot disconnected! Attempting to reconnect...")

    async def on_resumed(self):
        """Triggered when the bot resumes after a disconnection."""
        print("✅ Bot session successfully resumed.")

    async def start_bot(self):
        """Starts the bot, handling setup and login."""
        await self.setup()
        try:
            token = await get_bot_token()  # Fetch token securely
            if not token:
                logger.error("No token found. Check database.")
                return
            await self.start(token)
        except Exception as e:
            logger.error(f"Error during bot start: {e}\n{traceback.format_exc()}")
        finally:
            if self.is_closed():
                print("Bot is closed, cleaning up.")
            else:
                print("Bot is still running.")
            await self.close()

    async def setup(self):
        """Loads all cogs and event handlers."""
        await self.import_cogs("cogs")
        await self.import_cogs("events")
        print("\033[94m===== Setup Completed =====\033[0m")

    async def import_cogs(self, dir_name):
        """Dynamically loads all cogs from the specified directory."""
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
    """Checks Discord API rate limits and waits if necessary."""
    url = "https://discord.com/api/v10/users/@me"
    token = await get_bot_token()  # Fetch token securely
    headers = {"Authorization": f"Bot {token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
                reset_after = float(response.headers.get("X-RateLimit-Reset-After", 0))
                if remaining <= 0:
                    logger.error(f"Rate limit exceeded. Retry after {reset_after} seconds.")
                    print(f"⚠️ Rate limit exceeded. Waiting {reset_after} seconds.")
                    await asyncio.sleep(reset_after)
            else:
                logger.error(f"Failed to check rate limit. Status code: {response.status}")


async def start_http_server():
    """Starts a simple web server to keep Render.com service alive."""
    app = web.Application()

    async def handle_index(request):
        return web.Response(text="✅ Bot is running", content_type="text/html")

    app.router.add_get("/", handle_index)
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌍 HTTP server started on port {port}")


async def run_bot():
    """Runs the bot in a loop, restarting it if it crashes."""
    while True:
        bot = BotSetup()
        try:
            await check_rate_limit()
            await bot.start_bot()
        except Exception as e:
            logger.error(f"❌ Bot crashed: {e}\n{traceback.format_exc()}")
            print("⚠️ Bot crashed, restarting in 5 seconds.")
            await asyncio.sleep(5)  

async def start_server():
    """Starts both the bot and HTTP server for uptime monitoring."""
    gc.collect()
    while True:
        try:
            await asyncio.gather(
                start_http_server(),
                run_bot(),  
            )
        except Exception as e:
            logger.error(f"🔥 Fatal error in main loop: {e}\n{traceback.format_exc()}")
            print("⚠️ Critical error! Restarting in 10 seconds...")
            await asyncio.sleep(10)  


if __name__ == "__main__":
    asyncio.run(start_server())
