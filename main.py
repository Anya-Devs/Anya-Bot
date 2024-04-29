
import depend 
from depend import *

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
                    print(Fore.BLUE + f"    ├── {filename}" + Style.RESET_ALL)
                else:
                    print(Fore.BLUE + f"    └── {filename}" + Style.RESET_ALL)

                module = __import__(f"{dir_name}.{filename[:-3]}", fromlist=[""])
                for obj_name in dir(module):
                    obj = getattr(module, obj_name)
                    if isinstance(obj, commands.CogMeta):
                        await self.add_cog(obj(self))
                        print(Fore.GREEN + f"│   └── {obj_name}" + Style.RESET_ALL)

bot = BotSetup()

asyncio.get_event_loop().run_until_complete(bot.start_bot())
