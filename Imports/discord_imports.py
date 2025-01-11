# Discord Imports
import discord
from discord import Embed
from discord.ext import tasks, commands
from discord.ext.commands import (
    BucketType,
    Context,
    Greedy,
    bot_has_permissions,
    check,
    cooldown,
    group,
    has_permissions,
    has_role,
)
from discord.enums import ChannelType, Status
from discord.errors import Forbidden, HTTPException, NotFound

from discord.ext.commands import (
    BadArgument,
    BotMissingPermissions,
    BotMissingRole,
    CheckFailure,
    CommandError,
    CommandInvokeError,
    CommandNotFound,
    CommandOnCooldown,
    ExtensionError,
    ExtensionFailed,
    ExtensionNotFound,
    MaxConcurrencyReached,
    MissingPermissions,
    MissingRole,
    NoPrivateMessage,
    NotOwner,
    UserInputError,
)
from discord.ext.commands.converter import (
    ColorConverter,
    EmojiConverter,
    MemberConverter,
    RoleConverter,
    TextChannelConverter,
)

from discord.ui import Select, View, Button
from discord.utils import get


# Discord Slash Commands
from discord import app_commands, TextChannel, Thread
from typing import Literal, Optional, List, Dict, Union
