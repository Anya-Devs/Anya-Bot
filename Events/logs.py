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
