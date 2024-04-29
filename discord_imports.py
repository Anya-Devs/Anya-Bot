# Discord
import discord
from discord import File, Reaction, User, FFmpegPCMAudio, Activity, ActivityType
from discord.ext import commands, tasks
from discord.ui import Select, View
from discord.ext.commands import BucketType, Greedy, Context
from discord.ui.button import Button
from discord import app_commands

# Discord Slash Commands
from typing import Literal, Optional