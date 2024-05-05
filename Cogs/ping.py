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
            if python_version is not None:
                python_version_diff = const.PingConstants.format_diff(python_version)
                python_version_info = python_version_diff

                latest_python_version = await self.get_latest_python_version()
                if latest_python_version and python_version < latest_python_version:
                    i = '-'
                    python_version_info += "└── Outdated"
                else:
                    i = '-'
                    python_version_info += "└── Up to Date"
            else:
                python_version_info = "**Python Version**: ```diff\nVersion information not available\n```"

            system_info = f"**System**: ```diff\n{const.PingConstants.format_diff(platform.system())}\n```" \
                          f"**Processor**: ```diff\n{const.PingConstants.format_diff(platform.processor())}\n```" 
            gateway_latency = f"```diff\n+ {round(self.bot.latency * 1000)}ms\n```"

            cpu_usage_value = psutil.cpu_percent()
            mem_usage_value = psutil.virtual_memory().percent

            cpu_usage_diff = const.PingConstants.format_diff(cpu_usage_value)
            mem_usage_diff = const.PingConstants.format_diff(mem_usage_value)

            cpu_usage_tree = "└── Good" if cpu_usage_value < 80 else "└── Bad"
            mem_usage_tree = "└── Good" if mem_usage_value < 80 else "└── Bad"

            cpu_usage = f"**CPU Usage**: ```diff\n{cpu_usage_diff}{cpu_usage_tree}```"
            mem_usage = f"**Memory Usage**: ```diff\n{mem_usage_diff}{mem_usage_tree}```"
            
            x = f"{const.PingConstants.language_info['Language']} : {python_version_info}"
            y = x.replace('-','').replace('+','')
            x = y.split(" ")
            lang = ""
            if len(x) > 1:
                if x[0] == const.PingConstants.language_info['Language']:
                    result = f"{x[0]} : {x[1]}"
                else:
                    result = f"+ {x[0]} : {x[1]}"
                    if len(x) > 2:
                        lang += " " + " ".join(x[2:])
                    else:
                        lang = x[0]
            
            
            
            language_info = f"**Language**: ```diff\n+ {y}```" \
                            f"**Discord Library**: ```diff\n{const.PingConstants.language_info['Discord Library']}\n```" \
                         

            embed = discord.Embed(title="Pong 🏓", description=f"{gateway_latency}", color=const.PingConstants.embed_color,timestamp=datetime.now())
            embed.add_field(name="", value=f"{cpu_usage}{mem_usage}", inline=True)
            embed.add_field(name="", value=f"{system_info}", inline=True)
            embed.add_field(name="", value=f"{language_info}", inline=False)
            embed.set_thumbnail(url=const.PingConstants.thumbnail_url)
            embed.set_image(url=const.PingConstants.image_url)
            embed.set_footer(text=f"Ping Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar)
            await ctx.reply(embed=embed)

        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping")
            logger.error(f"{Fore.RED}[System cog] Error occurred while sending ping embed: {e}{Style.RESET_ALL}")

    def cog_unload(self):
        logger.info(f"{Fore.RED}[System cog] Unloaded{Style.RESET_ALL}")


def setup(bot):
    bot.add_cog(System(bot))
