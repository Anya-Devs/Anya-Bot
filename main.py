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
import asyncio

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
import discord
from discord.ext import commands

# Package Management
os.system("pip install -r requirements.txt")
os.system("pip install --upgrade pip")


class BotSetup:
    def __init__(self, bot):
        self.bot = bot

    async def setup(self):
        print("\n")
        print(Fore.BLUE + " /" + Style.RESET_ALL)
        print(Fore.BLUE + "├── Cogs/" + Style.RESET_ALL)
        # Define the directory where your additional Cogs are located
        cog_dir = "Cogs"
        # Iterate through files in the cog directory
        for filename in os.listdir(cog_dir):
            if filename.endswith(".py"):  # Check if the file is a Python file
                cog_name = filename[:-3]  # Remove the ".py" extension
                cog_module = __import__(f"{cog_dir}.{cog_name}", fromlist=[""])
                num_commands = len([obj for obj in dir(cog_module) if isinstance(getattr(cog_module, obj), commands.Command)])
                print(Fore.BLUE + f"│   ├── {filename}" + Style.RESET_ALL)

                # Dynamically import the module
                cog_module = __import__(f"{cog_dir}.{cog_name}", fromlist=[""])

                # Iterate through objects in the module
                for obj_name in dir(cog_module):
                    # Get the object
                    obj = getattr(cog_module, obj_name)
                    # Check if the object is a subclass of commands.Cog
                    if isinstance(obj, commands.CogMeta):
                        # Add the Cog to the bot
                        await self.bot.add_cog(obj(self.bot))
                        print(Fore.GREEN + f"│   │       ├── {obj_name}" + Style.RESET_ALL)

        print(Fore.BLUE + "│" + Style.RESET_ALL)
        print(Fore.BLUE + "└── Events/" + Style.RESET_ALL)
        # Define the directory where your additional Event handlers are located
        events_dir = "Events"
        # Iterate through files in the events directory
        for filename in os.listdir(events_dir):
            if filename.endswith(".py"):  # Check if the file is a Python file
                print(Fore.BLUE + f"    ├── {filename}" + Style.RESET_ALL)

        print("\n")
        print(Fore.BLUE + "===== Setup Completed =====" + Style.RESET_ALL)


async def main():
    bot = BotSetup(commands.Bot(command_prefix=commands.when_mentioned_or(','), intents=discord.Intents.all(), help_command=None))
    await bot.setup().bot.start(os.environ.get('TOKEN'))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except discord.errors.HTTPException as e:
        print(e)
        print("\n\n\nBLOCKED BY RATE LIMITS\nRESTARTING NOW\n\n\n")
        os.system('kill 1')
