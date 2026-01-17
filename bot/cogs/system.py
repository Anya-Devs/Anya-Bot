from imports.discord_imports import *
from imports.log_imports import *
from bot.utils.cogs.ticket import *
import data.local.const as const
from data.local.const import primary_color, timestamp_gen
import os, psutil, platform, time, json, socket, random
from datetime import datetime
from colorama import Fore, Style


class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.now()           # kept in case you need a human-readable start later
        self.start_monotonic = time.monotonic()    # use this for uptime calculations
        self.image_file = "data/commands/help/help_embed_images.json"
        self.ticket_system = TicketSystem(bot)
        self.host_address = socket.gethostbyname(socket.gethostname())

    def format_uptime(self, total_seconds: int) -> str:
        # Monotonic-based elapsed seconds -> human string
        seconds = int(max(0, total_seconds))
        years, rem = divmod(seconds, 365 * 24 * 3600)
        days, rem = divmod(rem, 24 * 3600)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)

        parts = []
        if years: parts.append(f"{years} year{'s' if years != 1 else ''}")
        if days: parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes: parts.append(f"{minutes} min{'s' if minutes != 1 else ''}")
        if seconds or not parts: parts.append(f"{seconds} sec")
        return " ".join(parts)

    def has_manage_role_or_perms(self, member):
        role = discord.utils.find(lambda r: r.name.lower() == "anya manager", member.roles)
        return role is not None or member.guild_permissions.manage_guild

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
        embed = discord.Embed(
            title="Memory Usage", 
            description=f"```{memory_str}```",
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_footer(
            text=f"Memory | Requested by {ctx.author}",
            icon_url=self.bot.user.avatar.url
            )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="ping")
    async def ping(self, ctx):
        try:
            lag = self.bot.latency * 1000
            pos_neg = f"{'+' if lag < 200 else '-'}"
            embed = discord.Embed(
                title="Ping",
                description=f"```diff\n{pos_neg} 🏓 Pong! : {round(lag)}ms```",
                color=discord.Color.green() if lag < 200 else discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.set_footer(
                text=f" Ping | Requested by {ctx.author}",
                icon_url=self.bot.user.avatar.url
            )
            await ctx.reply(f"{ctx.author.mention}", embed=embed, mention_author=False)
        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping")
            logger.error(f"[System cog] Error in ping: {e}")

    @commands.command(name="uptime")
    async def uptime(self, ctx):
        elapsed = time.monotonic() - self.start_monotonic
        uptime = self.format_uptime(int(elapsed))
        latency = self.bot.latency * 1000

        embed = discord.Embed(
            title="Uptime",
            color=primary_color(),
            timestamp=datetime.now(),
            description=f'```{uptime}```'
        )
        
        embed.set_footer(
            text=f"Uptime | Requested by {ctx.author}",
            icon_url=self.bot.user.avatar.url 
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="credit")
    async def credit(self, ctx):
        try:
            with open("data/commands/system/credits.json") as f:
                data = json.load(f)
            embed = discord.Embed(
                title=data["title"],
                timestamp=datetime.now(),
                color=primary_color()
            )
            for dev in data["developers"]:
                embed.add_field(
                    name="",
                    value=f'**{dev["name"]}**\n> {dev["role"]}',
                    inline=False
                )
            embed.set_image(
                url="https://static1.cbrimages.com/wordpress/wp-content/uploads/2022/11/Spy-x-family-ep-18-Loid-and-Anya-studying.jpg?q=50&fit=crop&w=1100&h=618&dpr=1.5"
            )
            embed.set_footer(text=data["footer"]['text'], icon_url=self.bot.user.avatar.url)
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.send(f"An error occurred loading the credits: {e}")

    @commands.group(name="ticket", invoke_without_command=True)
    async def ticket(self, ctx):
        embed = discord.Embed(color=primary_color())
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
        await ctx.reply(embed=embed, mention_author=False)

    # Subcommands
    @ticket.command(name="create")
    async def ticket_create(self, ctx, channel: discord.TextChannel):
        await self.ticket_system.ticket_command(ctx, "create", str(channel.id))

    @ticket.command(name="activate")
    async def ticket_activate(self, ctx):
        await self.ticket_system.ticket_command(ctx, "activate")

    @ticket.command(name="delete")
    async def ticket_delete(self, ctx):
        await self.ticket_system.ticket_command(ctx, "delete")

    @ticket.command(name="edit")
    async def ticket_edit(self, ctx, message_link: str):
        await self.ticket_system.ticket_command(ctx, "edit", message_link)

    @ticket.error
    async def ticket_error(self, ctx, error):
        if isinstance(error, commands.MissingAnyRole):
            return await ctx.reply("You need the `Anya Manager` role to use this command.", mention_author=False)
        embed = discord.Embed(color=discord.Color.red())
        embed.add_field(
            name="Error",
            value=f"```{str(error)}```",
            inline=False
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(System(bot))
