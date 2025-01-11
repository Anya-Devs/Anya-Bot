from Imports.log_imports import logger
from Imports.discord_imports import *
from Imports.depend_imports import *
import os
import sys
import subprocess
import traceback
import asyncio
import requests
from aiohttp import web

import pymongo
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConfigurationError

from dotenv import load_dotenv


# Load environment variables (still necessary for other environment-related settings)
load_dotenv()

# Print loaded environment variables
print("\033[93mLoaded Environment Variables:\033[0m")

for key, value in os.environ.items():
    if (
        key.startswith("TOKEN")
        or key.startswith("PASSWORD")
        or key.startswith("SECRET")
    ):
        print(f"{key} = [REDACTED]")
    else:
        print(f"{key} = {value}")

# Custom Imports


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
        self.mongoConnect = None
        self.DB_NAME = "Bot"
        self.COLLECTION_NAME = "information"
        self.token_type = "Token"

    async def on_ready(self):
        print(f"\033[92mLogged in as {self.user} (ID: {self.user.id})\033[0m")

    async def get_token_from_db(self):
        mongo_url = os.getenv("MONGO_URI")
        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")

        client = AsyncIOMotorClient(mongo_url)
        db = client[self.DB_NAME]
        collection = db[self.COLLECTION_NAME]

        token_data = await collection.find_one({self.token_type: {"$exists": True}})

        if token_data:
            return token_data.get(self.token_type)
        else:
            raise ValueError("No token found in the database")

    async def start_bot(self):
        await self.setup()
        token = await self.get_token_from_db()

        if not token:
            logger.error("No token found. Please check the database.")
            return

        # Set the token in the environment for use
        # Correct way to set an environment variable
        os.environ["TOKEN"] = token
        try:
            await self.start(token)
        except KeyboardInterrupt:
            await self.close()
        except Exception as e:
            logger.error(
                f"An error occurred while logging in: {e}\n{traceback.format_exc()}"
            )
            await self.close()
        finally:
            if self.is_closed():
                print("Bot is closed, cleaning up.")
            else:
                print("Bot is still running.")
            await self.close()

    async def setup(self):
        print("\n\033[94m• —— Cogs/\033[0m")
        await self.import_cogs("Cogs")
        print("\n\033[94m• —— Events/\033[0m")
        await self.import_cogs("Events")
        print("\n\033[94m===== Setup Completed =====\033[0m")

    async def import_cogs(self, dir_name):
        for filename in os.listdir(dir_name):
            if filename.endswith(".py"):
                print(f"\033[94m|   ├── {filename}\033[0m")
                module = __import__(
                    f"{dir_name}.{os.path.splitext(filename)[0]}", fromlist=[""]
                )
                for obj_name in dir(module):
                    obj = getattr(module, obj_name)
                    if isinstance(obj, commands.CogMeta):
                        if not self.get_cog(obj_name):
                            await self.add_cog(obj(self))
                            print(f"\033[92m|   |   └── {obj_name}\033[0m")


async def check_rate_limit():
    url = "https://discord.com/api/v10/users/@me"
    token = await BotSetup().get_token_from_db()  # Get token from DB
    headers = {"Authorization": f"Bot {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        remaining_requests = int(
            response.headers.get("X-RateLimit-Remaining", 1))
        rate_limit_reset_after = float(
            response.headers.get("X-RateLimit-Reset-After", 0)
        )
        if remaining_requests <= 0:
            logger.error(
                f"Rate limit exceeded. Retry after {rate_limit_reset_after} seconds."
            )
            print(
                f"Rate limit exceeded. Please wait for {rate_limit_reset_after} seconds before retrying."
            )
            await asyncio.sleep(rate_limit_reset_after)
    else:
        logger.error(
            f"Failed to check rate limit. Status code: {response.status_code}")


async def start_http_server():
    try:
        app = web.Application()
        app.router.add_get(
            "/", lambda request: web.Response(text="Bot is running"))
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.getenv("PORT", 8080))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"HTTP server started on port {port}")
    except Exception as e:
        logger.error(f"Failed to start HTTP server: {e}")
        print("Failed to start HTTP server.")


async def main():
    bot = BotSetup()
    try:
        await check_rate_limit()
        await bot.start_bot()
    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = int(e.response.headers.get("Retry-After", 0))
            logger.error(
                f"Rate limit exceeded. Retry after {retry_after} seconds.")
            print(
                f"Rate limit exceeded. Please wait for {retry_after} seconds before retrying."
            )
            await asyncio.sleep(retry_after)
        else:
            logger.error(f"An error occurred: {e}\n{traceback.format_exc()}")
    except Exception as e:
        logger.error(f"An error occurred: {e}\n{traceback.format_exc()}")
    finally:
        await bot.close()


if __name__ == "__main__":
    load_dotenv(dotenv_path=os.path.join(".github", ".env"))
    asyncio.run(start_http_server())
    asyncio.run(main())
