# Imports
import os
import logging
from datetime import datetime
from git import Repo

import discord
from discord.ext import commands, tasks

import Data.const as const
from Imports.log_imports import logger

# Define the Logs cog
class Logs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Method to send a log embed message
    async def send_log_embed(self, message):
        try:
            channel = discord.utils.get(self.bot.guilds[0].channels, name="anya-logs")
            if not channel:
                return

            # Get updated commands
            updated_commands = await self.get_updated_commands()
            if updated_commands:
                commands_str = "\n".join(updated_commands)
                if len(commands_str) <= 2000:  # Check if content fits in embed
                    await self.send_embed(channel, "Updated Files", commands_str)
                else:
                    await self.send_file(channel, "Data/uncommitted_changes.py", "Updated Files", commands_str)

        except Exception as e:
            logger.exception("An error occurred while sending log embed:")
            await const.error_custom_embed(self.bot, None, e, title="Log Embed Error")

    # Method to send an embed message
    async def send_embed(self, channel, title, description):
        embed = discord.Embed(
            title=title,
            description=description,
            color=const.LogConstants.embed_color
        )
        embed.set_thumbnail(url=const.LogConstants.start_log_thumbnail)
        embed.set_footer(text=const.LogConstants.footer_text, icon_url=const.LogConstants.footer_icon)
        embed.set_author(name=const.LogConstants.author_name, icon_url=const.LogConstants.author_icon)
        embed.timestamp = datetime.now()  # Set current timestamp
        await channel.send(embed=embed)

    # Method to send a file
    async def send_file(self, channel, file_path, title, description):
        with open(file_path, "w") as file:
            file.write(description)
        await channel.send(file=discord.File(file_path), content=f"**{title}**")

    # Method to get updated commands
    async def get_updated_commands(self):
        root_dir = os.getcwd()
        repo = Repo(root_dir)
        diff = repo.head.commit.diff(None)
        updated_commands = []

        for d in diff:
            if d.a_path.endswith('.py') and '__pycache__' not in d.a_path:
                content = d.a_blob.data_stream.read().decode('utf-8')
                x = '----------------------------------------------------------------------------'
                entry = f"\n\n{x}\nFile: {d.a_path}\nLocation: {os.path.abspath(d.a_path)}\n{x}\n\n{content}"
                updated_commands.append(entry)

        return updated_commands

    # Listener for when the bot is ready
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Log cog is ready. This cog tells the server what updates are in the code.")
        await self.send_log_embed("Bot is online")

# Setup function to add the Logs cog to the bot
def setup(bot):
    bot.add_cog(Logs(bot))
