# ─── Imports ────────────────────────────────────────────────────────────────
import os
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
        embed = None
        try:
            if isinstance(error, commands.MissingPermissions):
                missing = ', '.join(error.missing_perms)
                embed = Embed(
                    title="Missing Permissions",
                    description=f"{ctx.author.mention}, you lack the following permissions:\n`{missing}`",
                    color=0xFF0000
                )
                self.logger.info(f"User {ctx.author} missing permissions: {missing} in {ctx.guild.name}")

            elif isinstance(error, commands.BotMissingPermissions):
                missing = ', '.join(error.missing_perms)
                invite = self.generate_invite_link(error.missing_perms)
                embed = Embed(
                    title="Bot Missing Permissions",
                    description=f"I lack the following permissions:\n`{missing}`\n[Fix with invite]({invite})",
                    color=0xFF0000
                )
                self.logger.warning(f"Bot missing permissions: {missing} in {ctx.guild.name}")

            elif isinstance(error, commands.MissingRequiredArgument):
                embed = Embed(
                    title="Missing Required Argument",
                    description=f"You must specify: `{ctx.prefix}{ctx.command} <{error.param.name}>`",
                    color=0xFF0000
                )

            elif isinstance(error, commands.CommandOnCooldown):
                try:
                    await ctx.message.add_reaction("⏱️")
                except Exception:
                    pass

            elif isinstance(error, commands.CommandNotFound):
                commands_list = [cmd.name for cmd in self.bot.commands]
                matches = get_close_matches(ctx.invoked_with, commands_list, n=3, cutoff=0.5)
                suggestion = f"Did you mean: `{', '.join(matches)}`?" if matches else "No similar commands found."
                embed = Embed(
                    description=f"Command `{ctx.invoked_with}` not found. {suggestion}"
                )

            else:
                raise error

        except Exception as e:
            await self.error_custom_embed(self.bot, ctx, e)
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            self.logger.error(f"Exception in on_command_error:\n{tb}")
            return

        if embed:
            await ctx.reply(embed=embed, mention_author=False)

    def generate_invite_link(self, missing_perms):
        permissions = discord.Permissions()
        for perm in missing_perms:
            setattr(permissions, perm, True)
        return discord.utils.oauth_url(self.bot.user.id, permissions=permissions)

# ─── Cog Setup ──────────────────────────────────────────────────────────────
def setup(bot):
    bot.add_cog(Permission(bot))
