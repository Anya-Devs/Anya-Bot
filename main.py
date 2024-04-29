import os
import asyncio

from colorama import Fore, Style
from discord_imports import *

class BotSetup(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or(','), intents=discord.Intents.all(), help_command=None)

    async def start_bot(self):
        await self.setup()
        token = os.getenv('TOKEN')
        await self.start(token)

    async def setup(self):
        print("\n")
        print(Fore.BLUE + " /" + Style.RESET_ALL)
        print(Fore.BLUE + "├── Cogs/" + Style.RESET_ALL)
        # Define the directory where your additional Cogs are located
        cog_dir = "Cogs"
        # Get the list of files in the cog directory
        cog_files = os.listdir(cog_dir)
        # Iterate through files in the cog directory
        for i, filename in enumerate(cog_files):
            if filename.endswith(".py"):  # Check if the file is a Python file
                cog_name = filename[:-3]  # Remove the ".py" extension
                cog_module = __import__(f"{cog_dir}.{cog_name}", fromlist=[""])
                num_commands = len([obj for obj in dir(cog_module) if isinstance(getattr(cog_module, obj), commands.Command)])
                if i < len(cog_files) - 1:
                    print(Fore.BLUE + f"│   ├── {filename}" + Style.RESET_ALL)
                else:
                    print(Fore.BLUE + f"│   └── {filename}" + Style.RESET_ALL)

                # Dynamically import the module
                cog_module = __import__(f"{cog_dir}.{cog_name}", fromlist=[""])

                # Iterate through objects in the module
                for obj_name in dir(cog_module):
                    # Get the object
                    obj = getattr(cog_module, obj_name)
                    # Check if the object is a subclass of commands.Cog
                    if isinstance(obj, commands.CogMeta):
                        # Add the Cog to the bot
                        await self.add_cog(obj(self))
                        print(Fore.GREEN + f"│   └── {obj_name}" + Style.RESET_ALL)

        print(Fore.BLUE + "│" + Style.RESET_ALL)
        print(Fore.BLUE + "└── Events/" + Style.RESET_ALL)
        # Define the directory where your additional Event handlers are located
        events_dir = "Events"
        # Get the list of files in the events directory
        events_files = os.listdir(events_dir)
        # Iterate through files in the events directory
        for i, filename in enumerate(events_files):
            if filename.endswith(".py"):  # Check if the file is a Python file
                if i < len(events_files) - 1:
                    print(Fore.BLUE + f"    ├── {filename}" + Style.RESET_ALL)
                else:
                    print(Fore.BLUE + f"    └── {filename}" + Style.RESET_ALL)

                # Dynamically import the module
                event_module = __import__(f"{events_dir}.{filename[:-3]}", fromlist=[""])

                # Iterate through objects in the module
                for obj_name in dir(event_module):
                    # Get the object
                    obj = getattr(event_module, obj_name)
                    # Check if the object is a subclass of commands.Cog
                    if isinstance(obj, commands.CogMeta):
                        # Add the Cog to the bot
                        await self.add_cog(obj(self))
                        print(Fore.GREEN + f"│   └── {obj_name}" + Style.RESET_ALL)

        print("\n")
        print(Fore.BLUE + "===== Setup Completed =====" + Style.RESET_ALL)

bot = BotSetup()

asyncio.get_event_loop().run_until_complete(bot.start_bot())
