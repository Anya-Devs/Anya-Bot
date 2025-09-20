import os
import random
from imports.discord_imports import *
from utils.cogs.halloween import Config, DatabaseManager, EventManager, PaginationView
from datetime import datetime, timedelta
import asyncio
import re

POKETWO_ID = 716390085896962058
class CelestialTribute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config()
        self.db = DatabaseManager()
        self.event_manager = EventManager(self.config, self.db)

    # ---------------- Helpers ----------------
    def parse_time_arg(self, arg: str) -> datetime:
        now = datetime.utcnow()
        arg = arg.lower()
        if arg == "now":
            return now
        if arg[-1] in ["d", "h", "m", "s"] and arg[:-1].isdigit():
            value = int(arg[:-1])
            unit = arg[-1]
            units = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}
            return now + timedelta(**{units[unit]: value})
        try:
            if len(arg.split("-")) == 3:
                return datetime.strptime(arg, "%Y-%m-%d")
            else:
                return datetime.strptime(arg, "%Y-%m-%d-%H:%M")
        except ValueError:
            raise ValueError("Invalid time format. Use `now`, `2d`, `7h`, `30m`, `YYYY-MM-DD`, or `YYYY-MM-DD-HH:MM`.")

    async def cog_check(self, ctx):
        if not ctx.guild or str(ctx.guild.id) != self.config.server_id:
            await ctx.send("⚠️ This command can only be used in the configured server.")
            return False
        return True

    # ---------------- Listeners ----------------
    @commands.Cog.listener()
    async def on_message(self, message):
     if not message.guild or str(message.guild.id) != self.config.server_id:
        return

     # --- Regular contributions from any message ---
     if not message.author.bot:
        user_data = await self.db._get_user_async(message.author.id)
        user_data['contribution'] = min(100.0, user_data.get('contribution', 0) + 0.5)
        user_data['total_messages'] = user_data.get('total_messages', 0) + 1
        user_data['last_message_time'] = datetime.utcnow()
        if random.random() < 0.05:
            user_data['shards'] = user_data.get('shards', 0) + 1
        await self.db._update_user_async(user_data)

     # --- Poketwo activity detection ---
     if message.author.id == POKETWO_ID:

        # Detect a user catch message
        match = re.search(r"Congratulations <@!?(\d+)>! You caught a Level \d+ \w+", message.content)
        if match:
            user_id = int(match.group(1))
            user_data = await self.db._get_user_async(user_id)
            user_data['shards'] = user_data.get('shards', 0) + 1  # reward 1 shard per catch
            await self.db._update_user_async(user_data)

        # Optional: Detect shiny chain messages for bonus
        shiny_match = re.search(r"\+1 Shiny chain! \(\*\*(\d+)\*\*\)", message.content)
        if shiny_match:
            user_id = int(match.group(1))  # might want to track last catcher differently
            user_data = await self.db._get_user_async(user_id)
            user_data['shards'] = user_data.get('shards', 0) + 1
            await self.db._update_user_async(user_data)

    # ---------------- Main Command Group ----------------
    @commands.group(name="celestial", invoke_without_command=True, hidden=True)
    async def celestial(self, ctx):
        embed = discord.Embed(
            title="🌟 Celestial Tribute Commands",
            description=(
                "Subcommands:\n"
                "`inventory`, `about`, `tribute`, `leaderboard`, `set_time` (Admin)"
            ),
            color=0x9932CC
        )
        await ctx.reply(embed=embed, mention_author=False)

    # ---------- User Subcommands ----------
    @celestial.command()
    async def inventory(self, ctx):
     if not await self.event_manager.is_event_active():
        await ctx.send("⚠️ Event not active.")
        return

     user_data = await self.db._get_user_async(ctx.author.id)
     next_cost = 10 + 5 * user_data.get('offerings', 0)

     description = (
        f"**Celestial Shards:** {user_data.get('shards',0)}\n"
        f"**Contribution:** {user_data.get('contribution',0.0):.1f}/100.0\n"
        f"**Offerings Made:** {user_data.get('offerings',0)}\n"
        f"**Next Offering Cost:** {next_cost} shards\n"
        f"**Total Messages:** {user_data.get('total_messages',0)}"
     )

     embed = discord.Embed(title="🌟 Stellar Inventory", description=description)
     await ctx.reply(embed=embed, mention_author=False)

    @celestial.command()
    async def about(self, ctx):
     try:
        stage = await self.event_manager.get_corruption_stage()
        time_remaining = await self.event_manager.get_time_remaining()

        story_block = f"\n{self.config.story[:500]}{'...' if len(self.config.story) > 500 else ''}\n"

        description = (
            f"{story_block}\n\n"
            "How to Participate:\n"
            "• Be Active: Send messages to earn contribution points\n"
            "• Poketwo Activities: Earn celestial shards\n"
            "• Make Offerings: `celestial tribute`\n\n"
            "Rewards:\n"
            "• Pokecoins (scales with offerings)\n"
            "• Rare/Shiny Pokémon (better odds with more offerings)\n"
            "• Shiny Event Arceus (special reward after 20+ offerings)"
        )

        embed = discord.Embed(
            title="CELESTIAL TRIBUTE",
            description=description,
        )

        embed.set_image(url=self.config.banner_url)

        # Duration and Time Remaining as fields
        embed.add_field(name="Duration", value=f"{self.config.duration_days} Days", inline=True)
        embed.add_field(name="Time Remaining", value=str(time_remaining), inline=True)

        # Stage info as fields
        embed.add_field(name="Current Stage", value=stage['name'], inline=True)
        embed.add_field(name="Stage Description", value=stage['description'], inline=False)

        await ctx.reply(embed=embed, mention_author=False)

     except Exception as e:
        await ctx.reply(f"⚠️ Failed to load Celestial Tribute info: {e}", mention_author=False)

    @celestial.command()
    async def tribute(self, ctx):
        if not await self.event_manager.is_event_active():
            await ctx.send("⚠️ Event not active.")
            return
        user_data = await self.db._get_user_async(ctx.author.id)
        cost = 10 + 5 * user_data.get('offerings', 0)
        if user_data.get('shards', 0) < cost:
            await ctx.reply(f"⚠️ You need **{cost} shards**. You have **{user_data.get('shards',0)}**.", mention_author=False )
            return
        user_data['shards'] -= cost
        user_data['offerings'] = user_data.get('offerings', 0) + 1
        contrib_mult = 1 + (user_data.get('contribution',0)/100)
        rewards = []
        coins = int(random.randint(1000,5000)*(1.2**(user_data['offerings']-1))*contrib_mult)
        rewards.append(f"💰 **{coins:,}** Pokecoins")
        if random.random() < 0.7:
            shiny_chance = min(0.05+0.02*(user_data['offerings']-1),0.3)
            is_shiny = random.random() < shiny_chance
            shiny_text = "✨ **SHINY** " if is_shiny else ""
            rarity = random.choice(["Common","Uncommon","Rare"]) if not is_shiny else "Rare"
            rewards.append(f"🎯 {shiny_text}{rarity} Pokémon")
        if user_data['offerings'] >= 20 and random.random()<0.01:
            rewards.append("🌟 **SHINY EVENT ARCEUS** 🌟")
        await self.db._update_user_async(user_data)
        await self.db.increment_offerings()
        embed = discord.Embed(
            title="🌟 The Stellar Apostle of Aeons Responds",
            description=f"**{ctx.author.mention}** made offering **{user_data['offerings']}**!\n*{cost} shards consumed*",
            color=0x00FF00
        )
        embed.set_image(url=self.config.apostle_banner_url)
        embed.add_field(name="🎁 Rewards", value="\n".join(rewards), inline=False)
        stage = await self.event_manager.get_corruption_stage()
        total_off = (await self.db.get_event_stats()).get("total_offerings",0)
        embed.add_field(name=f"Cosmic Stage: {stage['name']}", value=f"*{stage['description']}*\nTotal Offerings: {total_off}", inline=False)
        await ctx.reply(embed=embed, mention_author=False)

    @celestial.command()
    async def leaderboard(self, ctx):
     try:
        top_users = await self.db._leaderboard_async(25)
        if not top_users:
            await ctx.reply("🏆 Stellar Champions\nNo champions yet!", mention_author=False)
            return

        text_pages = []
        users_per_page = 10
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}

        for i in range(0, len(top_users), users_per_page):
            page_users = top_users[i:i + users_per_page]
            lines = ["🏆 Stellar Champions Leaderboard\n"]
            # Adjusted column widths
            lines.append(f"{'Position':<10} {'Name':<17} {'Offerings':<9} {'Shards':<7} {'Contribution':<12}")
            lines.append("-" * 65)

            for j, user_info in enumerate(page_users):
                pos = i + j + 1
                pos_display = medals.get(pos, str(pos))
                user_obj = self.bot.get_user(user_info['user_id'])
                name = user_obj.display_name if user_obj else f"Unknown({user_info['user_id']})"
                offerings = user_info.get('offerings', 0)
                shards = user_info.get('shards', 0)
                contribution = user_info.get('contribution', 0.0)

                lines.append(f"{pos_display:<9} {name:<18} {offerings:<10} {shards:<8} {contribution:<12.1f}")

            text_pages.append("```\n" + "\n".join(lines) + "\n```")

        # Pagination
        if len(text_pages) > 1:
            view = PaginationView(text_pages)
            await ctx.reply(text_pages[0], view=view, mention_author=False)
        else:
            await ctx.reply(text_pages[0], mention_author=False)

     except Exception as e:
        await ctx.send(f"⚠️ Failed to load leaderboard: {e}")
        
    # ---------- Admin Subcommand ----------
    @celestial.command(name="set_time")
    #@commands.has_permissions(administrator=True)
    async def set_event_time(self, ctx, start: str, end: str):
    
     try:
        start_time = self.parse_time_arg(start)
        end_time = self.parse_time_arg(end)

        if start_time >= end_time:
            await ctx.send("❌ Start time must be before end time.")
            return

        await self.event_manager.set_event_time(start_time, end_time)

        # Discord timestamp format: <t:unix:format>, 'f' = short datetime
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())

        embed = discord.Embed(
            title="✅ Event Time Set",
            description=(
                f"**Start:** <t:{start_ts}:f>\n"
                f"**End:** <t:{end_ts}:f>\n\n"
                f"*You can use relative times like 'now', '2d', '7m', or full date 'YYYY-MM-DD-HH:MM'*"
            ),
            color=0x00FF00
        )
        await ctx.reply(embed=embed, mention_author=False)

     except ValueError as e:
        await ctx.send(f"❌ {e}")

    # ---------------- Setup ----------------
    async def cog_load(self):
        await self.db.connect()
        #print(f"{self.bot.user} has awakened to face the corruption!")
