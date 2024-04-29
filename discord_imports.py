# Discord Imports
from discord import File, Reaction, User, FFmpegPCMAudio, Activity, ActivityType
from discord.ext import commands, tasks
from discord.ui import Select, View, button
from discord.ext.commands import BucketType, Greedy, Context, check, cooldown
from discord import app_commands
from discord.ext.commands import Bot, Cog, command, group, has_permissions, has_role
from discord.enums import Status, ChannelType
from discord.errors import NotFound, HTTPException, Forbidden
from discord.ext.commands import BadArgument, CommandError, CommandNotFound
from discord.ext.commands import MemberConverter, RoleConverter, TextChannelConverter
from discord.ext.commands import EmojiConverter, ColorConverter
from discord.ext.commands import Paginator, HelpCommand, DefaultHelpCommand
from discord.ext.commands import NoPrivateMessage, NotOwner, MissingPermissions
from discord.ext.commands import BotMissingPermissions, MissingRole, BotMissingRole
from discord.ext.commands import UserInputError, CommandInvokeError, CheckFailure
from discord.ext.commands import ExtensionError, ExtensionNotFound, ExtensionFailed
from discord.ext.commands import CommandOnCooldown, MaxConcurrencyReached
from discord.ext.commands import when_mentioned, when_mentioned_or
from discord.ext.commands import clean_content, escape_markdown
from discord.ext.commands import Group, Context, NoExit
from discord.ext.commands import slash_command, SlashContext, Option
from discord.ext.commands import command, command_group, group, check, cooldown, bot_has_permissions, bot_missing_permissions

# Discord Slash Commands
from typing import Literal, Optional
