from imports.discord_imports import *
from imports.log_imports import *
from utils.cogs.ticket import *
import data.local.const as const
from data.local.const import primary_color, timestamp_gen
import os, psutil, platform, time, json, socket, random
from datetime import datetime
from colorama import Fore, Style

class Config:
    COLOR = 0x00ff88
    VERSION = "v2.1.0"
    COMMANDS = {"uptime": "uptime"}
    BAR_LENGTH = 20
    DISCORDPY_VERSION = discord.__version__

    @staticmethod
    def primary_color(): return Config.COLOR

    @staticmethod
    def health_bar(percentage, inverse=False):
        filled = int(percentage / 100 * Config.BAR_LENGTH)
        empty = Config.BAR_LENGTH - filled
        bar = "█" * filled + "░" * empty
        if inverse:
            if percentage <= 20: color = "\u001b[1;32m"
            elif percentage <= 40: color = "\u001b[1;33m"
            elif percentage <= 60: color = "\u001b[1;33m"
            else: color = "\u001b[1;31m"
        else:
            if percentage >= 80: color = "\u001b[1;31m"
            elif percentage >= 60: color = "\u001b[1;33m"
            else: color = "\u001b[1;32m"
        return f"{color}{bar} {percentage:.1f}%\u001b[0m"

class System(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.now()
        self.image_file = "data/commands/help/help_embed_images.json"
        self.ticket_system = TicketSystem(bot)
        self.host_address = socket.gethostbyname(socket.gethostname())

    def format_uptime(self, start_time: datetime) -> str:
        now = datetime.utcnow()
        delta = now - start_time
        seconds = int(delta.total_seconds())
        years, rem = divmod(seconds, 365*24*3600)
        days, rem = divmod(rem, 24*3600)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        parts = []
        if years: parts.append(f"{years} year{'s' if years>1 else ''}")
        if days: parts.append(f"{days} day{'s' if days>1 else ''}")
        if hours: parts.append(f"{hours} hour{'s' if hours>1 else ''}")
        if minutes: parts.append(f"{minutes} min{'s' if minutes>1 else ''}")
        if seconds or not parts: parts.append(f"{seconds} sec")
        return " ".join(parts)

    def has_manage_role_or_perms(self, member):
        role = discord.utils.find(lambda r: r.name.lower() == "anya manager", member.roles)
        return role is not None or member.guild_permissions.manage_guild

    def get_system_info(self):
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return {
            'cpu': psutil.cpu_percent(interval=1),
            'memory': mem.percent,
            'memory_total': mem.total / (1024**3),
            'memory_used': mem.used / (1024**3),
            'disk': (disk.used / disk.total) * 100
        }

    def get_shard_health(self):
        data = []
        if hasattr(self.bot, 'shards'):
            for sid, shard in self.bot.shards.items():
                latency = shard.latency * 1000
                health = random.randint(85, 100) if latency < 100 else random.randint(70, 85) if latency < 200 else random.randint(50, 70)
                data.append({'id': sid, 'latency': latency, 'health': health, 'guilds': len([g for g in self.bot.guilds if g.shard_id == sid])})
        else:
            data.append({'id': 0, 'latency': self.bot.latency * 1000, 'health': random.randint(85, 100), 'guilds': len(self.bot.guilds)})
        return data

    def predict_downtime(self):
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        risks = []
        if cpu > 80: risks.append("High CPU usage")
        if mem > 85: risks.append("High memory usage")
        if not risks:
            return "Low Risk - No downtime expected", "Next 24-48h: Stable"
        elif len(risks) == 1:
            return "Medium Risk - Monitor", f"Next 6-12h: {risks[0]}"
        return "High Risk - Maintenance advised", "Next 2-4h: Optimization needed"

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
            embed = discord.Embed(description=f"```diff\n{pos_neg} Pong: {round(lag)}ms```",
                                  color=discord.Color.green() if lag < 200 else discord.Color.red(),
                                  timestamp=datetime.now())
            embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            await ctx.reply(f"{ctx.author.mention}", embed=embed, mention_author=False)
        except Exception as e:
            await const.error_custom_embed(self.bot, ctx, e, title="Ping")
            logger.error(f"[System cog] Error in ping: {e}")

    @commands.command(name=Config.COMMANDS["uptime"])
    async def uptime(self, ctx):
        uptime = str(datetime.now() - self.start_time).split('.')[0]
        sys_info = self.get_system_info()
        shards = self.get_shard_health()
        downtime_risk, prediction = self.predict_downtime()
        latency = self.bot.latency * 1000

        embed = discord.Embed(title=" ", color=primary_color(), timestamp=datetime.now())

        embed.add_field(name="Main Overview", value=(
            "```ansi\n"
            f"\u001b[1;32mOnline:\u001b[0m {self.format_uptime(self.start_time)}\n"
            f"\u001b[1;36mUptime:\u001b[0m {uptime}\n"
            f"\u001b[1;35mHost:\u001b[0m {self.host_address}\n"
            "```"), inline=False)

        embed.add_field(name="System Health", value=(
            "```ansi\n"
            f"\u001b[1;33m□ CPU:\u001b[0m {Config.health_bar(100 - sys_info['cpu'], inverse=True)}\n"
            f"\u001b[1;33m□ Memory:\u001b[0m {Config.health_bar(sys_info['memory'])}\n"
            f"\u001b[1;37m└── {sys_info['memory_used']:.1f}GB / {sys_info['memory_total']:.1f}GB\n"
            f"\u001b[1;33m□ Disk:\u001b[0m {Config.health_bar(sys_info['disk'])}\n"
            "```"), inline=False)

        shard_output = "```ansi\n"
        for s in shards:
            color = "\u001b[1;32m" if s['health'] >= 80 else "\u001b[1;33m" if s['health'] >= 60 else "\u001b[1;31m"
            shard_output += (
                f"{color}Shard {s['id']}:\u001b[0m\n"
                f"  Health: {Config.health_bar(s['health'])}\n"
                f"  \u001b[1;36mLatency:\u001b[0m {s['latency']:.0f}ms\n"
                f"  \u001b[1;35mGuilds:\u001b[0m {s['guilds']}\n\n"
            )
        shard_output += "```"

        embed.add_field(name="Shard Collections", value=shard_output, inline=False)

        embed.add_field(name="Downtime Predictions", value=(
            "```ansi\n"
            f"\u001b[1;37mRisk:\u001b[0m {downtime_risk}\n"
            f"\u001b[1;37mPrediction:\u001b[0m {prediction}\n"
            "```"), inline=False)

        embed.add_field(name="Network Performance", value=(
            "```ansi\n"
            f"\u001b[1;32mDiscord Latency:\u001b[0m {latency:.0f}ms\n"
            f"\u001b[1;36mTotal Guilds:\u001b[0m {len(self.bot.guilds)}\n"
            f"\u001b[1;35mTotal Users:\u001b[0m {len(self.bot.users)}\n"
            f"\u001b[1;37mCommands Loaded:\u001b[0m {len(self.bot.commands)}\n"
            "```"), inline=True)

        avg = (sys_info['cpu'] + sys_info['memory'] + sys_info['disk']) / 3
        health = "EXCELLENT" if avg < 60 else "MODERATE" if avg < 80 else "CRITICAL"

        embed.add_field(name="Overall Status", value=(
            "```ansi\n"
            f"\u001b[1;32mSystem:\u001b[0m {health}\n"
            f"\u001b[1;36mVersion:\u001b[0m {Config.VERSION}\n"
            f"\u001b[1;35mDiscord.py:\u001b[0m {Config.DISCORDPY_VERSION}\n"
            "```"), inline=True)

        embed.set_footer(text=f"Last Updated • Hosted on {self.host_address}",
                         icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="credit")
    async def credit(self, ctx):
        try:
            with open("data/commands/system/credits.json") as f:
                data = json.load(f)
            embed = discord.Embed(title=data["title"], timestamp=datetime.now(), color=Config.primary_color())
            for dev in data["developers"]:
                embed.add_field(name="", value=f'**{dev["name"]}**\n{dev["role"]}', inline=False)
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
        embed = discord.Embed(color=discord.Color.blue())
        embed.add_field(name="Usage", value=(
            f"`{ctx.prefix}ticket create #channel`\n"
            f"`{ctx.prefix}ticket activate`\n"
            f"`{ctx.prefix}ticket delete`\n"
            f"`{ctx.prefix}ticket edit <message link>`"
        ), inline=False)
        embed.set_footer(text="Tip: Each subcommand has its own required inputs.")
        await ctx.send(embed=embed, mention_author=False)

    def cog_unload(self):
        logger.info(f"[System cog] Unloaded")

async def setup(bot):
    await bot.add_cog(System(bot))
