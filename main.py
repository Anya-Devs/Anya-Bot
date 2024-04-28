# Standard Library Imports
import os
import sys
import json
import uuid
import logging
import threading
import subprocess
import traceback
import cProfile
import pstats
import time

from datetime import datetime, timezone, timedelta
from io import BytesIO
from urllib.parse import quote_plus
from random import choice
from difflib import SequenceMatcher
import string
import random
import math
import re

# Third-Party Imports
from colorama import Fore, Style

# Files
import depend

# Package Management
os.system("pip install -r requirements.txt")
os.system("pip install --upgrade pip")

# Discord Imports
import discord
from discord import app_commands
from discord import File, Reaction, User, FFmpegPCMAudio, Activity, ActivityType , 
from discord.ext import commands, tasks
from discord.ui import Select, View
from discord.ext.commands import BucketType, Greedy, Context
from discord.ui.button import Button

# Discord Bot Define
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=commands.when_mentioned_or(','), intents=intents, help_command=None)

# Bot Token
token = os.environ.get('TOKEN')


# Log Console                           
logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s [%(levelname)s]: %(message)s')
logger = logging.getLogger(__name__)


@bot.event
async def setup(bot):
    print("\n")
    print(Fore.BLUE + "===== Setting up Cogs =====" + Style.RESET_ALL)
    print("\n")
    # Define the directory where your additional Cogs are located
    cog_dir = "Cogs"
    print("\n")
    print(Fore.BLUE + "===== Additional Cogs =====" + Style.RESET_ALL)
    print("\n")
    # Iterate through files in the cog directory
    additional_cogs = []
    for filename in os.listdir(cog_dir):
        if filename.endswith(".py"):  # Check if the file is a Python file
            cog_name = filename[:-3]  # Remove the ".py" extension
            cog_module = __import__(f"{cog_dir}.{cog_name}", fromlist=[""])
            num_commands = len([obj for obj in dir(cog_module) if isinstance(getattr(cog_module, obj), commands.Command)])
            additional_cogs.append(Fore.GREEN + f"{cog_name.ljust(20)} | ✅" + Style.RESET_ALL)

            # Dynamically import the module
            cog_module = __import__(f"{cog_dir}.{cog_name}", fromlist=[""])

            # Iterate through objects in the module
            for obj_name in dir(cog_module):
                # Get the object
                obj = getattr(cog_module, obj_name)
                # Check if the object is a subclass of commands.Cog
                if isinstance(obj, commands.CogMeta):
                    # Add the Cog to the bot
                    await bot.add_cog(obj(bot))
                    additional_cogs.append(Fore.YELLOW + f"🛠️  {obj.qualified_name} Cog setup completed." + Style.RESET_ALL)

    # Print additional cogs
    for cog in additional_cogs:
        print(cog)

    print("\n")
    print(Fore.BLUE + "===== Setup Completed =====" + Style.RESET_ALL)
    print("\n")




  
asyncio.get_event_loop().run_until_complete(setup(bot))

async def main():
    await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except discord.errors.HTTPException as e:
        print(e)
        print("\n\n\nBLOCKED BY RATE LIMITS\nRESTARTING NOW\n\n\n")
        os.system('kill 1')

