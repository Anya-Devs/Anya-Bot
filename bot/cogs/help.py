
import os
import json
 
import aiohttp
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


from data.local.const import *
from utils.cogs.help import *

from imports.log_imports import logger
from imports.discord_imports import *




class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _get_cog_command_mapping(self):
        mapping = {}
        for cog_name, cog in self.bot.cogs.items():
            if isinstance(cog, commands.Cog):
                visible_commands = {
                    cmd.name: " " for cmd in cog.get_commands() if not cmd.hidden
                }
                if visible_commands:
                    mapping[cog_name] = visible_commands
        return mapping

    @commands.command(hidden=True)
    async def help(self, ctx, command_name: str = None):
        try:
            bot_avatar_url = str(self.bot.user.avatar.with_size(128))
            async with aiohttp.ClientSession() as session:
                async with session.get(bot_avatar_url) as resp:
                    if resp.status != 200:
                        return await ctx.reply("Failed to get bot avatar.")
                    data = await resp.read()

            temp_image_dir = "data/images"
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
                sub_helper = Sub_Helper(self.bot, ctx.prefix)
                markdown_help = sub_helper.get_command_help_string(ctx, command_name)
                await ctx.reply(markdown_help)
            except Exception as e:
                logger.error(f"Error generating help for command {command_name}: {e}")
                await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Command Help"))
            return

        try:
            # Generate mapping dynamically in memory
            self.cog_commands = {
                cog_name: [
                    cmd for cmd in cog.get_commands() if not cmd.hidden
                ]
                for cog_name, cog in self.bot.cogs.items()
                if isinstance(cog, commands.Cog)
            }

            sub_helper = Sub_Helper(self.bot, ctx.prefix)
            sub_helper.create_command_help_json()

            image_generator = ImageGenerator(ctx=ctx)
            image_file_path = "data/commands/help/set_image/image.png"
            image_generator.save_image(file_path=image_file_path)

            with open(image_file_path, "rb") as file:
                help_embed = discord.Embed(
                    color=primary_color_value,
                    description=(
                        f"Use `{ctx.prefix}help <command>` to get more information about a specific command.\n\n"
                        f"- For more help, visit the [support server](https://discord.gg/9QTMkjsteF)."
                    ),
                )
                select_view = Select_Help(self.bot, ctx)
                options = HelpMenu(self.bot, select_view)
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

def setup(bot):
    bot.add_cog(Help(bot))
