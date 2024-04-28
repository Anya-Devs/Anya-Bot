# Cogs/ping.py

import discord
from discord.ext import commands
import platform
import psutil
import const

class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        # System information
        system_info = f"**System**: {const.PingConstants.system_info['Operating System']}\n"
        system_info += f"**Processor**: {const.PingConstants.system_info['Processor']}\n"
        system_info += f"**Python Version**: {const.PingConstants.system_info['Python Version']}\n"
        
        # Gateway latency
        gateway_latency = f"**Gateway Latency**: {round(self.bot.latency * 1000)}ms\n"

        # Discord API latency
        api_latency = f"**Discord API Latency**: {round(self.bot.latency * 1000)}ms\n"

        # CPU and memory usage
        cpu_usage = f"**CPU Usage**: {psutil.cpu_percent()}%\n"
        mem_usage = f"**Memory Usage**: {psutil.virtual_memory().percent}%\n"

        # Language and libraries used
        language_info = f"**Language**: {const.PingConstants.language_info['Language']}\n"
        language_info += f"**Discord Library**: {const.PingConstants.language_info['Discord Library']}\n"

        # Create embed
        embed = discord.Embed(title="Ping Command", color=const.PingConstants.embed_color)
        embed.add_field(name="System Information", value=system_info, inline=True)
        embed.add_field(name="Gateway Latency", value=gateway_latency, inline=True)
        embed.add_field(name="Discord API Latency", value=api_latency, inline=True)
        embed.add_field(name="CPU Usage", value=cpu_usage, inline=True)
        embed.add_field(name="Memory Usage", value=mem_usage, inline=True)
        embed.add_field(name="Language Information", value=language_info, inline=True)

        # Set thumbnail URL
        embed.set_thumbnail(url=const.PingConstants.thumbnail_url)

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(System(bot))
