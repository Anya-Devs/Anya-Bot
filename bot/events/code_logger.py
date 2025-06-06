# ─── Imports ────────────────────────────────────────────────────────────────
import os
import sys
import logging
import traceback
from datetime import datetime
from difflib import get_close_matches

import data.local.const as const
from data.local.const import error_custom_embed
from imports.log_imports import logger
from imports.discord_imports import *

# ─── Suppress Third-Party Logs ──────────────────────────────────────────────
def suppress_import_logs():
    for name in logging.root.manager.loggerDict:
        if name != 'root':
            logging.getLogger(name).setLevel(logging.WARNING)

suppress_import_logs()

# ─── Logging Format Setup ───────────────────────────────────────────────────
class LogColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    ENDC = '\033[0m'

class EmojiIndicator:
    INFO = "🩶 "
    WARNING = "⚠️ "
    ERROR = "❌ "
    DEBUG = "🔍 "

class CustomFormatter(logging.Formatter):
    def format(self, record):
        now = datetime.now().strftime("%I:%M:%S %p")
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
        return f"{color}{level_emoji} | {now} | {filename} | {record.getMessage()}{LogColors.ENDC}"

logging.basicConfig(level=logging.DEBUG)
for handler in logging.getLogger().handlers:
    handler.setFormatter(CustomFormatter())

# ─── Permission Cog ─────────────────────────────────────────────────────────
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
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            self.logger.error(f"Exception in on_command_error:\n{tb}")

    async def notify_missing_permissions(self, ctx, error):
        missing = ', '.join(error.missing_perms)
        await ctx.send(f"{ctx.author.mention}, you lack: {missing}")
        self.logger.info(f"User {ctx.author} missing permissions: {missing} in {ctx.guild.name}")
        perms = ctx.channel.permissions_for(ctx.author)
        current = [perm for perm, val in perms if val]
        await ctx.send(f"Your current permissions: {', '.join(current)}")

    async def notify_bot_missing_permissions(self, ctx, error):
        missing = ', '.join(error.missing_perms)
        invite = self.generate_invite_link(error.missing_perms)
        await ctx.send(f"I lack: {missing}. [Fix with invite]({invite})")
        self.logger.warning(f"Bot missing permissions: {missing} in {ctx.guild.name}")
        perms = ctx.channel.permissions_for(ctx.guild.me)
        current = [perm for perm, val in perms if val]
        await ctx.send(f"My permissions: {', '.join(current)}")

    async def notify_forbidden_error(self, ctx, error):
        await ctx.send("Forbidden action. Check role/channel settings.")
        self.logger.warning(f"Forbidden error in command {ctx.command}: {error}")
        perms = ctx.channel.permissions_for(ctx.guild.me)
        current = [perm for perm, val in perms if val]
        await ctx.send(f"My permissions: {', '.join(current)}")

    async def notify_error(self, ctx, error):
     if isinstance(error, commands.MissingRequiredArgument) and error.param.name == "action":
        return
     await self.error_custom_embed(self.bot, ctx, error)
     self.logger.error(f"Unexpected error in command {ctx.command}: {error}")
     
    def generate_invite_link(self, missing_perms):
        permissions = discord.Permissions()
        for perm in missing_perms:
            setattr(permissions, perm, True)
        return discord.utils.oauth_url(self.bot.user.id, permissions=permissions)

    async def suggest_command(self, ctx, error):
        commands_list = [cmd.name for cmd in self.bot.commands]
        matches = get_close_matches(ctx.invoked_with, commands_list, n=3, cutoff=0.5)
        suggestion = f"Did you mean: `{', '.join(matches)}`?" if matches else "No similar commands found."
        await ctx.reply(embed=discord.Embed(
            description=f"Command `{ctx.invoked_with}` not found. {suggestion}"
        ), mention_author=False)

# ─── Cog Setup ──────────────────────────────────────────────────────────────
def setup(bot):
    bot.add_cog(Permission(bot))
