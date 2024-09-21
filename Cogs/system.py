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



class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # logger.info(f"{Fore.GREEN}[System cog] Initialized{Style.RESET_ALL}")

    async def get_latest_python_version(self):
        latest_version = subprocess.check_output(['python', '-c', 'import sys; print("{}.{}.{}".format(sys.version_info.major, sys.version_info.minor, sys.version_info.micro))']).decode().strip()
        return latest_version

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{Fore.YELLOW}[System cog] Bot is ready.{Style.RESET_ALL}")

    @commands.command(name='ping')
    async def ping(self, ctx):
        try:
            python_version = platform.python_version()
            python_version_info = f"{python_version} {'Up to Date' if python_version >= await self.get_latest_python_version() else 'Outdated'}"

            system_info = f"{platform.system()} {platform.processor()}"
            
            threshold = 200
            lag = self.bot.latency * 1000
            pos_neg = f"{'+' if lag < threshold else '-'}"
            gateway_latency = f"{round(lag)}ms"
            
            cpu_usage_value = psutil.cpu_percent()
            mem_usage_value = psutil.virtual_memory().percent

            cpu_status = "Good" if cpu_usage_value < 80 else "Bad"
            mem_status = "Good" if mem_usage_value < 80 else "Bad"
            
            color =  discord.Color.green() if lag < threshold else discord.Color.red()

            embed = discord.Embed(title='', description=f"```diff\n{pos_neg} Pong: {gateway_latency}```", color=color, timestamp=datetime.now())
            embed.set_footer(text=f'Requested by {ctx.author}', icon_url=ctx.author.avatar)

            # embed.add_field(name="\u200b", value=f"```diff\nCPU: {cpu_usage_value}% {cpu_status}\n```", inline=True)
            # embed.add_field(name="\u200b", value=f"```diff\nMemory: {mem_usage_value}% {mem_status}\n```", inline=True)
            # embed.add_field(name="\u200b", value=f"```diff\nSystem: {system_info}\n```", inline=True)
            # embed.add_field(name="\u200b", value=f"```diff\nPython: {python_version_info}\n```", inline=True)
            # embed.add_field(name="\u200b", value=f"```diff\nDiscord Library: {const.PingConstants.language_info['Discord Library']}\n```", inline=True)

            # embed.set_thumbnail(url=ctx.author.avatar.url)
            await ctx.reply(f"{ctx.message.author.mention}",embed=embed, mention_author=False)

        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping")
            logger.error(f"[System cog] Error occurred while sending ping embed: {e}")

    def cog_unload(self):
        logger.info(f"{Fore.RED}[System cog] Unloaded{Style.RESET_ALL}")
        
        
        
        
    @commands.command(name='credit')
    async def credit(self, ctx):
        try:
            # Load the JSON file
            with open('Data/commands/system/credits.json', 'r') as f:
                credit_data = json.load(f)

            # Create the embed using the JSON data
            embed = discord.Embed(
                title=f'{credit_data["title"]}',
                timestamp=datetime.now(),
                color=primary_color()
            )

            # Add developer fields
            emoji = '<:ty:1285850367065587762>'
            reply = '<:reply:1285852466704809984>'
            image_url = 'https://static1.cbrimages.com/wordpress/wp-content/uploads/2022/11/Spy-x-family-ep-18-Loid-and-Anya-studying.jpg?q=50&fit=crop&w=1100&h=618&dpr=1.5'
            for developer in credit_data["developers"]:
                embed.add_field(name='', value=f'**{emoji} | {developer["name"]}**\n{reply} {developer["role"]}', inline=False)
                
            embed.set_image(url=image_url)
              
            # Add footer
            embed.set_footer(text='- w - thanks for using our bot')

            # Send the embed
            await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
            # Handle any errors and send a message to the user
            await ctx.send(f"An error occurred while trying to load the credits: {e}")


def setup(bot):
    bot.add_cog(System(bot))