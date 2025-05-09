# Core Discord and Commands
import discord
from discord.ext import commands, tasks

# Discord Types and Interactions
from discord import (
    AllowedMentions,
    ButtonStyle,
    ChannelType,
    Client,
    Embed,
    Emoji,
    File,
    Guild,
    Interaction,
    Intents,
    Member,
    Message,
    PartialEmoji,
    Permissions,
    Role,
    SelectOption,
    StageChannel,
    Status,
    TextChannel,
    Thread,
    User,
    VoiceChannel,
    Activity,
    ActivityType,
    Reaction,
    FFmpegPCMAudio,
)

# Slash Commands and App Commands
from discord import app_commands
from discord.app_commands import (
    Command,
    Group,
    Choice,
    check,
    describe,
    guilds,
    default_permissions,
    CommandTree,
    Namespace,
)

# Components
from discord.ui import (
    Button,
    Modal,
    Select,
    TextInput,
    View,
)

# Typing Utilities
from typing import Literal, Optional, List, Dict, Union

# Constants and Utilities
from discord.utils import (
    get,
    find,
    escape_markdown,
    format_dt,
)

# Errors
from discord.errors import Forbidden, HTTPException, NotFound
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
    command,
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

# Converters
from discord.ext.commands.converter import (
    ColorConverter,
    EmojiConverter,
    MemberConverter,
    RoleConverter,
    TextChannelConverter,
)

# Help Command Utilities
from discord.ext.commands import (
    Paginator,
    HelpCommand,
    DefaultHelpCommand,
)

# Slash Commands, Additional Types
from discord.ext.commands import when_mentioned, when_mentioned_or, clean_content

from typing import Union, Literal
