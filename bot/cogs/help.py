import os, json, aiohttp
from io import BytesIO
from PIL import Image
from data.local.const import *
from utils.cogs.help import *
from imports.log_imports import logger
from imports.discord_imports import *

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def help(self, ctx, command_name: str = None):
        # Fetch bot avatar & primary color
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(self.bot.user.avatar.with_size(128))) as resp:
                    if resp.status != 200:
                        return await ctx.reply("Failed to get bot avatar.")
                    data = await resp.read()
            os.makedirs("data/images", exist_ok=True)
            path = "data/images/bot_icon.png"
            with Image.open(BytesIO(data)) as avatar:
                avatar.save(path)
            color = primary_color(path)
        except Exception as e:
            logger.error(f"Error getting primary color: {e}")
            return await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Primary Color"))

        # Command-specific help
        if command_name:
            try:
                sub = Sub_Helper(self.bot, ctx.prefix)
                result = await sub.get_command_help_embed(ctx, command_name)
                if isinstance(result, tuple):
                    embed, view = result
                    return await ctx.reply(embed=embed, view=view, mention_author=False)
                else:
                    return await ctx.reply(result, mention_author=False)
            except Exception as e:
                logger.error(f"Error generating help for command {command_name}: {e}")
                return await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Command Help"))

        # Full HelpMenu
        try:
            # Prepare cog commands (ignore hidden commands)
            cog_commands = {
                cog_name: [cmd for cmd in cog.get_commands() if not cmd.hidden]
                for cog_name, cog in self.bot.cogs.items()
                if isinstance(cog, commands.Cog)
            }

            # Generate help image
            img = ImageGenerator(ctx=ctx)
            img_path = "data/commands/help/set_image/image.png"
            img.save_image(file_path=img_path)

            # Initialize view & select menu
            view = HelpMenu(self.bot, None, ctx, cog_commands, img_path, color)
            select_view = Select_Help(self.bot, ctx, help_view=view)
            view.select_view = select_view
            view.clear_items()
            view.add_item(select_view)
            view.add_item(view.prev_button)
            view.add_item(view.next_button)

            embed = view.build_embed()
            embed.set_image(url="attachment://image.png")

            with open(img_path, "rb") as f:
                await ctx.send(
                    embed=embed,
                    file=discord.File(f, "image.png"),
                    view=view,
                    reference=ctx.message,
                    allowed_mentions=discord.AllowedMentions.none()
                )

        except Exception as e:
            logger.error(f"Error sending HelpMenu: {e}")
            await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Help Menu"))

def setup(bot): bot.add_cog(Help(bot))
