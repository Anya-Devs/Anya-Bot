import os
import sys
import subprocess
import traceback
import asyncio

"""
   : Run This if any installation problems occur

"""

""" 
def run_package_installer():
    try:
        subprocess.check_call([sys.executable, "Imports/depend_imports.py"])
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running the package installer: {e}")
        
run_package_installer()
"""

from Imports.depend_imports import *
import Imports.depend_imports as depend_imports
from Imports.discord_imports import *
from Imports.log_imports import logger

from colorama import Fore, Style  # Import Fore and Style explicitly
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

import pymongo  # Import database API
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConfigurationError



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
        print(Fore.BLUE + "── Cogs/" + Style.RESET_ALL)
        await self.import_cogs("Cogs")
        print("\n")
        print(Fore.BLUE + "── Events/" + Style.RESET_ALL)
        await self.import_cogs("Events")

        print("\n")
        print(Fore.BLUE + "===== Setup Completed =====" + Style.RESET_ALL)

    async def import_cogs(self, dir_name):
        files_dir = os.listdir(dir_name)
        for filename in files_dir:
            if filename.endswith(".py"):
                print(Fore.BLUE + f"│   ├── {filename}" + Style.RESET_ALL)

                module = __import__(f"{dir_name}.{os.path.splitext(filename)[0]}", fromlist=[""])
                for obj_name in dir(module):
                    obj = getattr(module, obj_name)
                    if isinstance(obj, commands.CogMeta):
                        if obj_name == "PokemonPredictor":
                            # Remove the cog if detected
                            existing_cog = self.get_cog("PokemonPredictor")
                            if existing_cog:
                                await self.remove_cog("PokemonPredictor")
                                print(Fore.RED + f"│   │   Removed {obj_name} cog" + Style.RESET_ALL)
                        else:
                            # Add other cogs
                            if not self.get_cog(obj_name):  # Check if cog already added
                                await self.add_cog(obj(self))
                                print(Fore.GREEN + f"│   │   └── {obj_name}" + Style.RESET_ALL)

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

