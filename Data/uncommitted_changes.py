

----------------------------------------------------------------------------
File: Cogs/ping.py
Location: /workspaces/Anya-Bot/Cogs/ping.py
----------------------------------------------------------------------------

import os
import pip
import json
import logging
import aiohttp
import requests
import platform
import psutil
import colorama
from discord_imports import *
from colorama import Fore, Style
import const  # Importing the const module
from datetime import datetime
import sys
import subprocess

colorama.init()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)


async def get_emoji(name, ctx):
    logger.info(f"{Fore.CYAN}[get_emoji] Attempting to get emoji: {name}{Style.RESET_ALL}")
    with open('Data/emoji.json', 'r') as f:
        emoji_data = json.load(f)

    if name in emoji_data:
        emoji_info = emoji_data[name]
        emoji_id = emoji_info['emoji_id']
        emoji_name = emoji_info['emoji_name']
        formatted_emoji = f"<:{emoji_name}:{emoji_id}>"
        logger.info(f"{Fore.GREEN}[get_emoji] Found emoji: {formatted_emoji}{Style.RESET_ALL}")
        return formatted_emoji
    else:
        logger.warning(f"{Fore.YELLOW}[get_emoji] Emoji not found for name: {name}. Attempting to create.{Style.RESET_ALL}")
        emoji = await const.Emojis.create_emoji(ctx, const.Emojis.emoji_paths[name], name)  # Updated line
        return emoji


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # logger.info(f"{Fore.GREEN}[System cog] Initialized{Style.RESET_ALL}")

    async def load_and_get_emojis(self, bot, ctx):
        return {
            "cpu_emoji": await get_emoji("cpu_emoji", ctx),
            "memory_emoji": await get_emoji("memory_emoji", ctx),
            "python_emoji": await get_emoji("python_emoji", ctx)
        }

    async def get_latest_python_version(self):
        latest_version = subprocess.check_output(['python', '-c', 'import sys; print("{}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro))']).decode().strip()
        return latest_version

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{Fore.YELLOW}[System cog] Bot is ready.{Style.RESET_ALL}")

    @commands.command()
    async def ping(self, ctx):
        try:
            emojis_data = await self.load_and_get_emojis(ctx.bot, ctx)

            cpu_emoji = emojis_data.get("cpu_emoji")
            memory_emoji = emojis_data.get("memory_emoji")
            python_emoji = emojis_data.get("python_emoji")

            python_version = platform.python_version()
            if python_version is not None:
                python_version_diff = const.PingConstants.format_diff(python_version)
                python_version_info = f"**Python Version**: ```diff\n{python_version_diff}"

                latest_python_version = await self.get_latest_python_version()
                if latest_python_version and python_version < latest_python_version:
                    i = '-'
                    python_version_info += "└── Outdated```"
                else:
                    i = '-'
                    python_version_info += "└── Up to Date```"
            else:
                python_version_info = "**Python Version**: ```diff\nVersion information not available\n```"

            system_info = f"**System**: ```diff\n{const.PingConstants.format_diff(platform.system())}\n```" \
                          f"**Processor**: ```diff\n{const.PingConstants.format_diff(platform.processor())}\n```" \
                          f"{python_version_info}"
            gateway_latency = f"```diff\n+ {round(self.bot.latency * 1000)}ms\n```"

            cpu_usage_value = psutil.cpu_percent()
            mem_usage_value = psutil.virtual_memory().percent

            cpu_usage_diff = const.PingConstants.format_diff(cpu_usage_value)
            mem_usage_diff = const.PingConstants.format_diff(mem_usage_value)

            cpu_usage_tree = "└── Good " if cpu_usage_value < 80 else "└── Bad | My head hurts!"
            mem_usage_tree = "└── Good" if mem_usage_value < 80 else "└── Bad | Wh-my brains all clumpy~"

            cpu_usage = f"**CPU Usage**: ```diff\n{cpu_usage_diff}{cpu_usage_tree}```"
            mem_usage = f"**Memory Usage**: ```diff\n{mem_usage_diff}{mem_usage_tree}```"

            language_info = f"**Language**: ```diff\n{const.PingConstants.language_info['Language']}\n```" \
                            f"**Discord Library**: ```diff\n{const.PingConstants.language_info['Discord Library']}\n```"

            embed = discord.Embed(title="Pong 🏓", description=f"{gateway_latency}",color=const.PingConstants.embed_color,timestamp=datetime.now())
            embed.add_field(name="", value=f"{cpu_usage}{mem_usage}", inline=True)
            embed.add_field(name="", value=f"{system_info}", inline=True)
            embed.add_field(name="", value=f"{language_info}", inline=True)
            embed.set_thumbnail(url=const.PingConstants.thumbnail_url)
            embed.set_image(url=const.PingConstants.image_url)
            embed.set_footer(text=f"Ping Request: {ctx.author.display_name}", icon_url=self.bot.user.avatar)

            await ctx.reply(embed=embed)

        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping Error")
            logger.error(f"{Fore.RED}[System cog] Error occurred while sending ping embed: {e}{Style.RESET_ALL}")

    def cog_unload(self):
        logger.info(f"{Fore.RED}[System cog] Unloaded{Style.RESET_ALL}")


def setup(bot):
    bot.add_cog(System(bot))



----------------------------------------------------------------------------
File: Events/bot-apperence.py
Location: /workspaces/Anya-Bot/Events/bot-apperence.py
----------------------------------------------------------------------------

import logging
import colorlog
from discord.ext import commands
import os
import asyncio
import random

# Set up logging with color
logger = colorlog.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }))
logger.addHandler(handler)

class AvatarChanger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.countdown = 200  # Initial countdown value in seconds
        self.emojis_folder = 'Emojis'  # Path to the folder containing PNG files
        self.png_files = [f for f in os.listdir(self.emojis_folder) if f.endswith('.png')]
        self.png_weights = [1] * len(self.png_files)  # Equal weights for each PNG file

    async def change_avatar(self):
        try:
            if self.png_files:
                random_png = random.choices(self.png_files, weights=self.png_weights)[0]
                with open(os.path.join(self.emojis_folder, random_png), 'rb') as f:
                    avatar_data = f.read()
                await self.bot.user.edit(avatar=avatar_data)
                logger.info(f"Changed avatar to {random_png} - Countdown: {self.countdown} seconds left")
            else:
                logger.info("No PNG files found in the Emojis folder.")
        except Exception as e:
            logger.error(f"An error occurred while changing avatar: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("AvatarChanger cog is ready. This cog periodically changes the bot's avatar.")
        await self.change_avatar_countdown()  # Start the countdown loop when bot is ready

    async def change_avatar_countdown(self):
        while True:
            await self.change_avatar()
            await asyncio.sleep(self.countdown)  # Wait for 60 seconds between avatar changes

def setup(bot):
    bot.add_cog(AvatarChanger(bot))



----------------------------------------------------------------------------
File: Events/logs.py
Location: /workspaces/Anya-Bot/Events/logs.py
----------------------------------------------------------------------------

# logs.py

import discord
from discord import Embed
from discord.ext import commands
from git import Repo
import const

class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_log_embed(self, message):
        channel = discord.utils.get(self.bot.guilds[0].channels, name="logs")
        if not channel:
            return

        embed = Embed(title="Bot Online", description="The bot is now online.", color=0x00ff00)
        embed.add_field(name="Updated Commands", value="Here are the commands that have been updated:", inline=False)
        embed.add_field(name="Uncommitted Changes", value="The following files have uncommitted changes:", inline=False)
        
        # Check for uncommitted changes in the Git repository
        repo = Repo('.')
        uncommitted_changes = [item.a_path for item in repo.index.diff(None)]
        if uncommitted_changes:
            # Highlight uncommitted files in red
            uncommitted_files = "```diff\n"
            for file in uncommitted_changes:
                uncommitted_files += f"- {file}\n"
            uncommitted_files += "```"
            embed.add_field(name="Uncommitted Files", value=uncommitted_files, inline=False)
            embed.set_footer(text=const.LogConstants.footer_text, icon_url=const.LogConstants.footer_icon)
        else:
            embed.add_field(name="Uncommitted Files", value="No uncommitted changes detected.", inline=False)

        # Set thumbnail URL
        thumbnail_url = const.LogConstants.start_log_thumbnail
        embed.set_thumbnail(url=thumbnail_url)
        
        # Set author details
        embed.set_author(name=const.LogConstants.author_name, icon_url=const.LogConstants.author_icon)

        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.send_log_embed("Bot is online")

def setup(bot):
    bot.add_cog(Logs(bot))



----------------------------------------------------------------------------
File: const.py
Location: /workspaces/Anya-Bot/const.py
----------------------------------------------------------------------------

# Imports
import os
import io
import json
import traceback
from datetime import datetime
from PIL import Image

import discord
from discord.ext import commands
import platform

# Constants
class AnyaImages:
    shocked_anya = "https://img-03.stickers.cloud/packs/20d46227-dcb0-4583-8d66-ee78d4743129/webp/a65e28be-a5fd-4654-8e7d-736dbd809df2.webp"
    awake_anya = 'https://media.tenor.com/9kLYJilshNMAAAAe/spy-x-family-anya.png'
    question_anya = 'https://i.pinimg.com/236x/b7/23/1f/b7231fbf87eee22b6d1f35f83e9a80bd.jpg'
    ping_banner_anya = 'https://i.redd.it/fvcg0u3kaiga1.jpg'

class LogConstants:
    start_log_thumbnail = "https://example.com/start_log_thumbnail.png"
    footer_text = "Please commit your changes to the repository."
    footer_icon = "https://example.com/footer_icon.png"
    author_name = "Your Bot Name"
    author_icon = "https://example.com/author_icon.png"

class PingConstants:
    thumbnail_url = 'https://example.com'
    image_url = AnyaImages.ping_banner_anya
    footer_icon = None
    embed_color = None

    current_time = datetime.now().strftime("%I:%M:%S %p")
    system_info = {
        "Operating System": f"{platform.system()} {platform.release()}\n└── {platform.version()} ",
        "System Time": current_time,
        "Processor": platform.processor(),
        "Python Version": platform.python_version(),
        "System Version": current_time
    }
    language_info = {
        "Language": "Python",
        "Discord Library": f"\ndiscord.py\n└── {discord.__version__}"
    }
    @staticmethod
    def format_diff(value):
        cpu_threshold = 80
        python_version_threshold = "3.10.13"
        if isinstance(value, str) and value < python_version_threshold:
            return f"- {value}\n"
        elif isinstance(value, (int, float)) and value > cpu_threshold:
            return f"- {value}\n"
        else:
            return f"+ {value}\n"

# Classes
class Emojis:
    emoji_paths = {
        "cpu_emoji": "Emojis/cpu.png",
        "memory_emoji": "Emojis/memory.png",
        "python_emoji": "Emojis/python.png"
    }

    @staticmethod
    async def load(bot, ctx):
        print('Loading emojis from local files')
        emojis = {}
        for emoji_name, file_path in Emojis.emoji_paths.items():
            emoji = await Emojis.create_emoji(ctx, file_path, emoji_name)
            emoji_id = emoji.split(":")[-1][:-1]
            emoji_format = f"<:_:{emoji_id}>"
            emojis[emoji_id] = emoji_format  # Store emoji format with emoji ID as key
            print(emoji_format)

        formatted_results = ""
        for emoji_id in emojis.keys():
            formatted_results += f"<:_:{emoji_id}>"

        return formatted_results

    @staticmethod
    async def create_emoji(ctx, file_path, emoji_name):
        # Check if emoji.json file exists, create if not
        if not os.path.exists("Data"):
            os.makedirs("Data")
        if not os.path.exists("Data/emoji.json"):
            with open("Data/emoji.json", "w") as f:
                json.dump({}, f)  # Empty json file

        # Load emoji data from emoji.json
        with open("Data/emoji.json", "r") as f:
            emoji_data = json.load(f)

        # Check if emoji exists in the json
        if emoji_name in emoji_data and "emoji_id" in emoji_data[emoji_name]:
            # Emoji ID exists in json, return the emoji format
            emoji_id = emoji_data[emoji_name]["emoji_id"]
            return f"<:_:{emoji_id}>"

        # Check if emoji exists in the guild
        existing_emoji = discord.utils.get(ctx.guild.emojis, name=emoji_name)
        if existing_emoji:
            # Delete existing emoji from the guild
            await existing_emoji.delete()
            print(f"Deleted existing emoji: {existing_emoji.name}")

        # Create new emoji
        with open(file_path, "rb") as f:
            image = Image.open(f)
            img_byte_array = io.BytesIO()
            image.save(img_byte_array, format=image.format)
            img_byte_array.seek(0)
            print(f"Creating emoji from file: {file_path}")
            new_emoji = await ctx.guild.create_custom_emoji(name=emoji_name, image=img_byte_array.read())
            print(f"Emoji created successfully: {new_emoji.name}")

            # Update emoji data
            emoji_data[emoji_name] = {"emoji_id": new_emoji.id, "emoji_name": "_"}
            with open("Data/emoji.json", "w") as f:
                json.dump(emoji_data, f, indent=4)  # Save updated json with indentation

        # Return the emoji format
        return f"<:_:{new_emoji.id}>"

# Functions
async def error_custom_embed(bot, ctx, e, title="Custom Error", thumbnail_url=AnyaImages.question_anya):
    error_embed = discord.Embed(
        description=f'```bash\n{e}```',
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    error_embed.set_author(name=f'{bot.user.display_name.title()} - {title}', icon_url=bot.user.avatar)
    line_number = traceback.extract_tb(e.__traceback__)[-1].lineno
    tb_frame = traceback.extract_tb(e.__traceback__)[-1]
    file_location = tb_frame.filename
    error_embed.add_field(
        name=" ",
        value=f"**Potential issue found:**\n- **File:** `{file_location}`\n- **Line:** `{line_number}`",
        inline=False
    )
    error_embed.set_footer(text='Error Found')
    error_embed.set_thumbnail(url=thumbnail_url)
    await ctx.reply(embed=error_embed)



----------------------------------------------------------------------------
File: depend.py
Location: /workspaces/Anya-Bot/depend.py
----------------------------------------------------------------------------

import os
import asyncio
os.system("pip install -r requirements.txt")
os.system("pip install --upgrade pip")

from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()


----------------------------------------------------------------------------
File: discord_imports.py
Location: /workspaces/Anya-Bot/discord_imports.py
----------------------------------------------------------------------------

# Discord Imports
import discord
from discord import File, Reaction, User, FFmpegPCMAudio, Activity, ActivityType
from discord.ext import commands, tasks
from discord.ui import Select, View, button
from discord.ext.commands import BucketType, Greedy, Context, check, cooldown
from discord import app_commands
from discord.ext.commands import Bot, Cog, command, group, has_permissions, has_role
from discord.enums import Status, ChannelType
from discord.errors import NotFound, HTTPException, Forbidden
from discord.ext.commands import BadArgument, CommandError, CommandNotFound
from discord.ext.commands import MemberConverter, RoleConverter, TextChannelConverter
from discord.ext.commands import EmojiConverter, ColorConverter
from discord.ext.commands import Paginator, HelpCommand, DefaultHelpCommand
from discord.ext.commands import NoPrivateMessage, NotOwner, MissingPermissions
from discord.ext.commands import BotMissingPermissions, MissingRole, BotMissingRole
from discord.ext.commands import UserInputError, CommandInvokeError, CheckFailure
from discord.ext.commands import ExtensionError, ExtensionNotFound, ExtensionFailed
from discord.ext.commands import CommandOnCooldown, MaxConcurrencyReached
from discord.ext.commands import when_mentioned, when_mentioned_or
from discord.ext.commands import clean_content
from discord.ext.commands import Group, Context
from discord.ext.commands import command, group, check, cooldown, bot_has_permissions

# Discord Slash Commands
from typing import Literal, Optional



----------------------------------------------------------------------------
File: main.py
Location: /workspaces/Anya-Bot/main.py
----------------------------------------------------------------------------


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
