import asyncio
import os
import traceback
import ssl
from colorama import Fore, Style

import pymongo # import database api
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConfigurationError

from Imports.log_imports import logger
import Imports.depend_imports as depend_imports
from Imports.depend_imports import *
from Imports.discord_imports import *

class BotSetup(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=commands.when_mentioned_or('...'), intents=intents, help_command=None)
        self.mongoConnect = None  # Initialize the MongoDB connection attribute

    async def start_bot(self):
        await self.setup()
        token = os.getenv('TOKEN')

        if not token:
            logger.error("No token found. Please set the TOKEN environment variable.")
            return

        try:
            await self.start(token)
        except KeyboardInterrupt:
            await self.close()
        except Exception as e:
            traceback_string = traceback.format_exc()
            logger.error(f"An error occurred while logging in: {e}\n{traceback_string}")
            await self.close()

    async def setup(self):
        print("\n")
        print(Fore.BLUE + " /" + Style.RESET_ALL)
        print(Fore.BLUE + "├── Cogs/" + Style.RESET_ALL)
        await self.import_cogs("Cogs")
        print(Fore.BLUE + "│" + Style.RESET_ALL)
        print(Fore.BLUE + "└── Events/" + Style.RESET_ALL)
        await self.import_cogs("Events")

        print("\n")
        print(Fore.BLUE + "===== Setup Completed =====" + Style.RESET_ALL)

      
    async def import_cogs(self, dir_name):
        files_dir = os.listdir(dir_name)
        for i, filename in enumerate(files_dir):
            if filename.endswith(".py"):
                if i < len(files_dir) - 1:
                    print(Fore.BLUE + f"│    ├── {filename}" + Style.RESET_ALL)
                else:
                    print(Fore.BLUE + f"│    └── {filename}" + Style.RESET_ALL)

                module = __import__(f"{dir_name}.{filename[:-3]}", fromlist=[""])
                for obj_name in dir(module):
                    obj = getattr(module, obj_name)
                    if isinstance(obj, commands.CogMeta):
                        if not self.get_cog(obj_name):  # Check if cog already added
                            await self.add_cog(obj(self))
                            print(Fore.GREEN + f"│    └── {obj_name}" + Style.RESET_ALL)

async def main():
    bot = BotSetup()

    try:
        await bot.start_bot()
    except Exception as e:
        traceback_string = traceback.format_exc()
        logger.error(f"An error occurred: {e}\n{traceback_string}")
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
