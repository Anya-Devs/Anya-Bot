import discord
from discord.ext import commands
import platform
import psutil
import const
import logging
import colorama
from colorama import Fore, Style

# Initialize colorama
colorama.init()

# Setup logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info(f"{Fore.GREEN}[System cog] Initialized{Style.RESET_ALL}")

    @commands.Cog.listener()
    async def on_ready(self):
        # Load emojis when the bot is ready
        logger.info(f"{Fore.YELLOW}[System cog] Bot is ready. Loading emojis...{Style.RESET_ALL}")
        await self.load_emojis()
        logger.info(f"{Fore.YELLOW}[System cog] Emojis loaded.{Style.RESET_ALL}")

    async def load_emojis(self):
        # Pass bot instance and guild to load emojis
        await const.Emojis.load(self.bot, self.bot.guild)

    @commands.command()
    async def ping(self, ctx):
        try:
            # Load emojis
            cpu_emoji, memory_emoji, python_emoji = await const.Emojis.load(ctx.bot)

            # System information
            system_info = f"**System**: ```diff\n{const.PingConstants.format_diff(const.PingConstants.system_info['Operating System'])}\n```" \
                          f"**Processor**: ```diff\n{const.PingConstants.format_diff(const.PingConstants.system_info['Processor'])}\n```" \
                          f"**Python Version**: {python_emoji} ```diff\n{const.PingConstants.format_diff(const.PingConstants.system_info['Python Version'])}\n```"

            # Gateway latency
            gateway_latency = f"**Gateway Latency**: {cpu_emoji} ```diff\n+ {round(self.bot.latency * 1000)}ms\n```"

            # Discord API latency
            api_latency = f"**Discord API Latency**: {cpu_emoji} ```diff\n+ {round(self.bot.latency * 1000)}ms\n```"

            # CPU and memory usage
            cpu_usage = f"**CPU Usage**: {cpu_emoji} ```diff\n{const.PingConstants.format_diff(psutil.cpu_percent())}%```"
            mem_usage = f"**Memory Usage**: {memory_emoji} ```diff\n{const.PingConstants.format_diff(psutil.virtual_memory().percent)}%```"

            # Language and libraries used
            language_info = f"**Language**: ```diff\n{const.PingConstants.language_info['Language']}\n```" \
                            f"**Discord Library**: ```diff\n{const.PingConstants.language_info['Discord Library']}\n```"

            # Create embed
            embed = discord.Embed(title="", color=const.PingConstants.embed_color)
            embed.set_author(name='Anya - Pong 🏓', icon_url=self.bot.user.avatar)

            # Add latency information
            embed.add_field(name="Latency Information", value=f"{gateway_latency}{api_latency}", inline=True)

            # Add resource usage information
            embed.add_field(name="Resource Usage", value=f"{cpu_usage}{mem_usage}", inline=True)

            # Add system information
            embed.add_field(name="System Information", value=f"{system_info}", inline=False)

            # Add language and libraries information
            embed.add_field(name="Language & Libraries", value=f"{language_info}", inline=False)

            # Set thumbnail URL
            embed.set_thumbnail(url=const.PingConstants.thumbnail_url)

            # Set Image
            embed.set_image(url=const.PingConstants.image_url)

            # Set footer
            embed.set_footer(text=f"Ping Request: {ctx.author.display_name}", icon_url=const.LogConstants.footer_icon)

            # Send embed
            await ctx.send(embed=embed)

        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping Error")

            logger.error(f"{Fore.RED}[System cog] Error occurred while sending ping embed: {e}{Style.RESET_ALL}")

    def cog_unload(self):
        logger.info(f"{Fore.RED}[System cog] Unloaded{Style.RESET_ALL}")

def setup(bot):
    bot.add_cog(System(bot))
