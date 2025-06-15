import os, json, aiohttp
from io import BytesIO
from PIL import Image
from data.local.const import *
from utils.cogs.help import *
from imports.log_imports import logger
from imports.discord_imports import *

class Help(commands.Cog):
    def __init__(self, bot): self.bot = bot

    def _get_cog_command_mapping(self):
        return {
            cog_name: {cmd.name: " " for cmd in cog.get_commands() if not cmd.hidden}
            for cog_name, cog in self.bot.cogs.items()
            if isinstance(cog, commands.Cog) and any(not cmd.hidden for cmd in cog.get_commands())
        }

    @commands.command(hidden=True)
    async def help(self, ctx, command_name: str = None):
        try:
            bot_avatar_url = str(self.bot.user.avatar.with_size(128))
            async with aiohttp.ClientSession() as session:
                async with session.get(bot_avatar_url) as resp:
                    if resp.status != 200: return await ctx.reply("Failed to get bot avatar.")
                    data = await resp.read()
            os.makedirs("data/images", exist_ok=True)
            path = "data/images/bot_icon.png"
            with Image.open(BytesIO(data)) as avatar: avatar.save(path)
            color = primary_color(path)
        except Exception as e:
            logger.error(f"Error getting primary color: {e}")
            return await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Primary Color"))

        if command_name:
            try:
                sub = Sub_Helper(self.bot, ctx.prefix)
                return await ctx.reply(sub.get_command_help_string(ctx, command_name))
            except Exception as e:
                logger.error(f"Error generating help for command {command_name}: {e}")
                return await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Command Help"))

        try:
            self.cog_commands = {
                cog_name: [cmd for cmd in cog.get_commands() if not cmd.hidden]
                for cog_name, cog in self.bot.cogs.items()
                if isinstance(cog, commands.Cog)
            }
            sub = Sub_Helper(self.bot, ctx.prefix)
            sub.create_command_help_json()
            img = ImageGenerator(ctx=ctx)
            img_path = "data/commands/help/set_image/image.png"
            img.save_image(file_path=img_path)
            with open(img_path, "rb") as f:
                embed = discord.Embed(
                    color=color,
                    description=f"Use `{ctx.prefix}help <command>` for more info.\n\n- For support, visit the [support server](https://discord.gg/9QTMkjsteF)."
                )
                embed.set_image(url="attachment://image.png")
                await ctx.send(
                    embed=embed,
                    file=discord.File(f, "image.png"),
                    view=HelpMenu(self.bot, Select_Help(self.bot, ctx)),
                    reference=ctx.message,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            if os.path.exists(img_path): os.remove(img_path)
        except Exception as e:
            logger.error(f"Error sending HelpMenu: {e}")
            await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Help Menu"))

def setup(bot): bot.add_cog(Help(bot))
