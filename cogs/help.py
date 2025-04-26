
import os
import traceback
import json

import cv2
import numpy as np
import aiohttp
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


from Imports.discord_imports import *
from Data.const import *
from Imports.log_imports import logger
from utils.cogs.help import *



class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cog_commands = {}
        self.command_mapping_file = "Data/commands/help/command_map.json"

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.command_mapping_file), exist_ok=True)
        if not os.path.exists(self.command_mapping_file):
            with open(self.command_mapping_file, "w") as f:
                json.dump({}, f, indent=4)

    def _load_command_mapping(self):
        self._ensure_file_exists()
        with open(self.command_mapping_file, "r") as f:
            return json.load(f)

    def _save_command_mapping(self, mapping):
        with open(self.command_mapping_file, "w") as f:
            json.dump(mapping, f, indent=4)

    def _update_command_mapping(self):
        mapping = self._load_command_mapping()
        for cog_name in self.cog_commands.keys():
            if cog_name not in mapping:
                mapping[cog_name] = {}
            cog = self.bot.get_cog(cog_name)
            if cog:
                for cmd in cog.get_commands():
                    if not cmd.hidden:
                        if cmd.name not in mapping[cog_name]:
                            mapping[cog_name][cmd.name] = " "
        self._save_command_mapping(mapping)

    @commands.command(hidden=True)
    async def help(self, ctx, command_name: str = None):
        try:
            bot_avatar_url = str(self.bot.user.avatar.with_size(128))

            async with aiohttp.ClientSession() as session:
                async with session.get(bot_avatar_url) as resp:
                    if resp.status != 200:
                        return await ctx.reply("Failed to get bot avatar.")
                    data = await resp.read()

            temp_image_dir = "Data/images"
            os.makedirs(temp_image_dir, exist_ok=True)
            temp_image_path = os.path.join(temp_image_dir, "bot_icon.png")

            with Image.open(BytesIO(data)) as avatar_image:
                avatar_image.save(temp_image_path)

            primary_color_value = primary_color(temp_image_path)

        except Exception as e:
            logger.error(f"Error getting primary color: {e}")
            await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Primary Color"))
            return

        if command_name:
            try:
                sub_helper = Sub_Helper(self.bot)
                markdown_help = sub_helper.get_command_help_string(ctx, command_name)
                await ctx.reply(markdown_help)
            except Exception as e:
                logger.error(f"Error generating help for command {command_name}: {e}")
                await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Command Help"))
            return

        try:
            cog_commands = {}
            for cog_name, cog_object in self.bot.cogs.items():
                if isinstance(cog_object, commands.Cog):
                    commands_in_cog = [
                        cmd for cmd in cog_object.get_commands() if not cmd.hidden
                    ]
                    if commands_in_cog:
                        cog_commands[cog_name] = commands_in_cog

            self.cog_commands = cog_commands
            self._update_command_mapping()

            sub_helper = Sub_Helper(self.bot)
            sub_helper.create_command_help_json()

            image_generator = ImageGenerator(ctx=ctx)
            image_file_path = "Data/commands/help/set_image/image.png"
            image_generator.save_image(file_path=image_file_path)

            with open(image_file_path, "rb") as file:
                help_embed = discord.Embed(
                    color=primary_color_value,
                    description=(
                        f"Use `{ctx.prefix}help <command>` to get more information about a specific command.\n\n"
                        f"- For more help, visit the [support server](https://discord.gg/9QTMkjsteF)."
                    ),
                )

                select_view = Select(self.bot, primary_color_value, ctx)
                options = HelpMenu(self.bot, primary_color_value, select_view)

                help_embed.set_image(url="attachment://image.png")
                await ctx.send(
                    embed=help_embed,
                    file=discord.File(file, "image.png"),
                    view=options,
                    reference=ctx.message,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

            if os.path.exists(image_file_path):
                os.remove(image_file_path)

        except Exception as e:
            logger.error(f"Error sending HelpMenu: {e}")
            await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Help Menu"))
            return


def setup(bot):
    bot.add_cog(Help(bot))
