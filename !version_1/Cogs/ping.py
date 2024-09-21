import os
import gc
import pip
import json
import logging
import aiohttp
import requests
import platform
import psutil
import colorama
from Imports.discord_imports import *
from Imports.log_imports import *
from colorama import Fore, Style
import Data.const as const  # Importing the const module
from Data.const import primary_color
from datetime import datetime
import sys
import subprocess

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

    @commands.command(name='ping')
    async def ping(self, ctx):
        try:
            emojis_data = await self.load_and_get_emojis(ctx.bot, ctx)

            cpu_emoji = emojis_data.get("cpu_emoji")
            memory_emoji = emojis_data.get("memory_emoji")
            python_emoji = emojis_data.get("python_emoji")

            python_version = platform.python_version()
            python_version_info = f"{python_version} {'Up to Date' if python_version >= await self.get_latest_python_version() else 'Outdated'}"

            system_info = f"{platform.system()} {platform.processor()}"
            
            threshold = 200
            lag = self.bot.latency * 1000
            gateway_latency = f"{'+' if lag < threshold else '-'} {round(lag)}ms"
            
            cpu_usage_value = psutil.cpu_percent()
            mem_usage_value = psutil.virtual_memory().percent

            cpu_status = "Good" if cpu_usage_value < 80 else "Bad"
            mem_status = "Good" if mem_usage_value < 80 else "Bad"
            
            color =  discord.Color.green() if lag < threshold else discord.Color.red()

            embed = discord.Embed(title='Pong', description=f"```diff\n{gateway_latency}```", color=color, timestamp=datetime.now())

            # embed.add_field(name="\u200b", value=f"```diff\nCPU: {cpu_usage_value}% {cpu_status}\n```", inline=True)
            # embed.add_field(name="\u200b", value=f"```diff\nMemory: {mem_usage_value}% {mem_status}\n```", inline=True)
            # embed.add_field(name="\u200b", value=f"```diff\nSystem: {system_info}\n```", inline=True)
            # embed.add_field(name="\u200b", value=f"```diff\nPython: {python_version_info}\n```", inline=True)
            # embed.add_field(name="\u200b", value=f"```diff\nDiscord Library: {const.PingConstants.language_info['Discord Library']}\n```", inline=True)

            # embed.set_thumbnail(url=ctx.author.avatar.url)
            await ctx.reply(embed=embed)

        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping")
            logger.error(f"[System cog] Error occurred while sending ping embed: {e}")

    def cog_unload(self):
        logger.info(f"{Fore.RED}[System cog] Unloaded{Style.RESET_ALL}")


def setup(bot):
    bot.add_cog(System(bot))
