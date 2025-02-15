import os
import gc
import json
import platform
import psutil
import time
import json
import subprocess
from datetime import datetime
from colorama import Fore, Style

import Data.const as const
from Imports.log_imports import *
from Imports.discord_imports import *
from Data.const import primary_color, timestamp_gen


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.image_file = "Data/commands/help/help_embed_images.json"


    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(
            f"{Fore.YELLOW}[System cog] Bot is ready.{Style.RESET_ALL}")

    @commands.command(name="ping")
    async def ping(self, ctx):
        try:
            python_version = platform.python_version()
            threshold = 200
            lag = self.bot.latency * 1000
            pos_neg = f"{'+' if lag < threshold else '-'}"
            gateway_latency = f"{round(lag)}ms"
            color = discord.Color.green() if lag < threshold else discord.Color.red()

            embed = discord.Embed(
                title="",
                description=f"```diff\n{pos_neg} Pong: {gateway_latency}```",
                color=color,
                timestamp=datetime.now(),
            )
            embed.set_thumbnail(url=self.bot.user.avatar)
            embed.set_footer(
                text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar
            )

            await ctx.reply(
                f"{ctx.message.author.mention}", embed=embed, mention_author=False
            )

        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping")
            logger.error(
                f"[System cog] Error occurred while sending ping embed: {e}")

    def cog_unload(self):
        logger.info(f"{Fore.RED}[System cog] Unloaded{Style.RESET_ALL}")

    @commands.command(name="uptime")
    async def uptime(self, ctx):
        bot_uptime = timestamp_gen(self.start_time)

        embed = discord.Embed(
            description=f"I been awake since {bot_uptime}",
            color=primary_color(),
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url=self.bot.user.avatar)
        embed.set_footer(text="Uptime", icon_url=self.bot.user.avatar)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="credit")
    async def credit(self, ctx):
        try:
            with open("Data/commands/system/credits.json", "r") as f:
                credit_data = json.load(f)

            embed = discord.Embed(
                title=f'{credit_data["title"]}',
                timestamp=datetime.now(),
                color=primary_color(),
            )

            emoji = "<:ty:1285850367065587762>"
            reply = "<:reply:1285852466704809984>"
            image_url = "https://static1.cbrimages.com/wordpress/wp-content/uploads/2022/11/Spy-x-family-ep-18-Loid-and-Anya-studying.jpg?q=50&fit=crop&w=1100&h=618&dpr=1.5"
            for developer in credit_data["developers"]:
                embed.add_field(
                    name="",
                    value=f'**{emoji} | {developer["name"]}**\n{reply} {developer["role"]}',
                    inline=False,
                )

            embed.set_image(url=image_url)

            embed.set_footer(text="- w - thanks for using our bot")

            await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
            await ctx.send(f"An error occurred while trying to load the credits: {e}")


def setup(bot):
    bot.add_cog(System(bot))
