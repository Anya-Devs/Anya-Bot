import os
import logging
from datetime import datetime
from difflib import get_close_matches
import traceback

import Data.const as const
from Data.const import error_custom_embed
from Imports.log_imports import logger
from Imports.discord_imports import *


class LogColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    ENDC = '\033[0m'


class EmojiIndicator:
    INFO = "🩶"
    WARNING = "⚠️"
    ERROR = "❌"
    DEBUG = "🔍"


class CustomFormatter(logging.Formatter):
    def format(self, record):
        time_now = datetime.now().strftime("%I:%M:%S %p")
        filename = os.path.basename(record.pathname)
        level_emoji = {
            logging.DEBUG: EmojiIndicator.DEBUG,
            logging.INFO: EmojiIndicator.INFO,
            logging.WARNING: EmojiIndicator.WARNING,
            logging.ERROR: EmojiIndicator.ERROR,
        }.get(record.levelno, "📋")

        color = {
            logging.DEBUG: LogColors.OKBLUE,
            logging.INFO: LogColors.OKGREEN,
            logging.WARNING: LogColors.WARNING,
            logging.ERROR: LogColors.ERROR,
        }.get(record.levelno, LogColors.HEADER)

        message = f"{level_emoji} | {filename} | {time_now} | {record.getMessage()}"
        return f"{color}{message}{LogColors.ENDC}"


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
for handler in logging.getLogger().handlers:
    handler.setFormatter(CustomFormatter())


class Permission(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logger
        self.error_custom_embed = error_custom_embed

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        try:
            if isinstance(error, commands.MissingPermissions):
                await self.notify_missing_permissions(ctx, error)
            elif isinstance(error, commands.BotMissingPermissions):
                await self.notify_bot_missing_permissions(ctx, error)
            elif isinstance(error, commands.CommandNotFound):
                await self.suggest_command(ctx, error)
            else:
                raise error
        except Exception as e:
            await self.notify_error(ctx, e)
            self.logger.exception(f"Exception caught in on_command_error: {e}")
            traceback.print_exc()

    async def notify_missing_permissions(self, ctx, error):
        missing_perms = ', '.join(error.missing_perms)
        await ctx.send(f"{ctx.author.mention}, you lack: {missing_perms}")
        self.logger.info(f"User {ctx.author} missing permissions: {missing_perms} in {ctx.guild.name}")

        user_perms = ctx.channel.permissions_for(ctx.author)
        perms_list = [perm for perm, value in user_perms if value]
        await ctx.send(f"Your current permissions: {', '.join(perms_list)}")

    async def notify_bot_missing_permissions(self, ctx, error):
        missing_perms = ', '.join(error.missing_perms)
        invite_link = self.generate_invite_link(error.missing_perms)
        await ctx.send(f"I lack: {missing_perms}. [Fix with invite]({invite_link})")
        self.logger.warning(f"Bot missing permissions: {missing_perms} in {ctx.guild.name}")

        bot_perms = ctx.channel.permissions_for(ctx.guild.me)
        perms_list = [perm for perm, value in bot_perms if value]
        await ctx.send(f"My permissions: {', '.join(perms_list)}")

    async def notify_forbidden_error(self, ctx, error):
        await ctx.send("Forbidden action. Check role/channel settings.")
        self.logger.warning(f"Forbidden error in command {ctx.command}: {error}")

        bot_perms = ctx.channel.permissions_for(ctx.guild.me)
        perms_list = [perm for perm, value in bot_perms if value]
        await ctx.send(f"My permissions: {', '.join(perms_list)}")

    async def notify_error(self, ctx, error):
        await self.error_custom_embed(self.bot, ctx, error)
        self.logger.error(f"Unexpected error in command {ctx.command}: {error}")

    def generate_invite_link(self, missing_perms):
        permissions = discord.Permissions()
        for perm in missing_perms:
            setattr(permissions, perm, True)
        return discord.utils.oauth_url(self.bot.user.id, permissions=permissions)

    async def suggest_command(self, ctx, error):
        all_commands = [command.name for command in self.bot.commands]
        closest_matches = get_close_matches(ctx.invoked_with, all_commands, n=3, cutoff=0.5)
        suggestion = f"Did you mean: `{', '.join(closest_matches)}`?" if closest_matches else "No similar commands found."
        await ctx.reply(embed=discord.Embed(description=f"Command `{ctx.invoked_with}` not found. {suggestion}"), mention_author=False)


def setup(bot):
    bot.add_cog(Permission(bot))
