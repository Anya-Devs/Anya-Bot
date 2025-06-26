from imports.discord_imports import *
from imports.log_imports import *
from utils.cogs.ticket import *
import data.local.const as const
from data.local.const import primary_color, timestamp_gen
import os, psutil, platform, time, json
from datetime import datetime
from colorama import Fore, Style

class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = time.time()
        self.image_file = "data/commands/help/help_embed_images.json"
        self.ticket_system = TicketSystem(bot)

    def has_manage_role_or_perms(self, member):
        role = discord.utils.find(lambda r: r.name.lower() == "anya manager", member.roles)
        return role is not None or member.guild_permissions.manage_guild


    def cog_unload(self):
        logger.info(f"{Fore.RED}[System cog] Unloaded{Style.RESET_ALL}")

    @commands.command(name='memory')
    async def memory(self, ctx):
        memory_bytes = psutil.Process(os.getpid()).memory_info().rss
        if memory_bytes < 1024:
            memory_str = f"{memory_bytes} B"
        elif memory_bytes < 1024**2:
            memory_str = f"{memory_bytes / 1024:.2f} KB"
        elif memory_bytes < 1024**3:
            memory_str = f"{memory_bytes / 1024**2:.2f} MB"
        else:
            memory_str = f"{memory_bytes / 1024**3:.2f} GB"
        await ctx.send(f"Memory Usage: {memory_str}")

    @commands.command(name="ping")
    async def ping(self, ctx):
        try:
            lag = self.bot.latency * 1000
            pos_neg = f"{'+' if lag < 200 else '-'}"
            embed = discord.Embed(
                description=f"```diff\n{pos_neg} Pong: {round(lag)}ms```",
                color=discord.Color.green() if lag < 200 else discord.Color.red(),
                timestamp=datetime.now(),
            )
            embed.set_thumbnail(url=self.bot.user.avatar)
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar)
            await ctx.reply(f"{ctx.author.mention}", embed=embed, mention_author=False)
        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping")
            logger.error(f"[System cog] Error in ping: {e}")

    @commands.command(name="uptime")
    async def uptime(self, ctx):
        up = timestamp_gen(self.start_time)
        embed = discord.Embed(
            description=f"I been awake since {up}",
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=self.bot.user.avatar)
        embed.set_footer(text="Uptime", icon_url=self.bot.user.avatar)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="credit")
    async def credit(self, ctx):
        try:
            with open("data/commands/system/credits.json") as f:
                data = json.load(f)
            embed = discord.Embed(title=data["title"], timestamp=datetime.now(), color=primary_color())
            emoji, reply = "<:ty:1285850367065587762>", "<:reply:1285852466704809984>"
            for dev in data["developers"]:
                embed.add_field(name="", value=f'**{emoji} | {dev["name"]}**\n{reply} {dev["role"]}', inline=False)
            embed.set_image(url="https://static1.cbrimages.com/wordpress/wp-content/uploads/2022/11/Spy-x-family-ep-18-Loid-and-Anya-studying.jpg?q=50&fit=crop&w=1100&h=618&dpr=1.5")
            embed.set_footer(text="- w - thanks for using our bot")
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.send(f"An error occurred loading the credits: {e}")

    @commands.command(name="ticket")
    async def ticket_command(self, ctx, action: Literal["create", "activate", "delete", "edit"], param: str = None):
     await self.ticket_system.ticket_command(ctx, action, param)


    @ticket_command.error
    async def ticket_error(self, ctx, error):
     if isinstance(error, commands.MissingAnyRole):
        return await ctx.send("You need the `Anya Manager` role to use this command.")

     embed = discord.Embed(
        color=discord.Color.blue()
     )
     embed.add_field(
        name="Usage",
        value=(
            f"`{ctx.prefix}ticket create #channel`\n"
            f"`{ctx.prefix}ticket activate`\n"
            f"`{ctx.prefix}ticket delete`\n"
            f"`{ctx.prefix}ticket edit <message link>`"
        ),
        inline=False
     )
     embed.set_footer(text="Tip: Each subcommand has its own required inputs.")
     await ctx.send(embed=embed, mention_author=False)

def setup(bot):
    bot.add_cog(System(bot))
