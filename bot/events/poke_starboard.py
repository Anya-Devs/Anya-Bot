import os
import re
import csv
from pathlib import Path
from datetime import datetime

from imports.discord_imports import *
from utils.subcogs.pokemon import *

SPECIAL_NAMES_CSV = Path("data/commands/pokemon/pokemon_special_names.csv")


class PokemonSpecialNames:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rare = set()
            cls._instance.regional = set()
            cls._instance._load()
        return cls._instance

    @classmethod
    def _load(cls):
        if not SPECIAL_NAMES_CSV.exists():
            print(f"CSV not found: {SPECIAL_NAMES_CSV}")
            return
        with open(SPECIAL_NAMES_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if rare := row.get("Rare Pokémon", "").strip().lower():
                    cls._instance.rare.add(rare)
                if regional := row.get("Regional Pokémon", "").strip().lower():
                    cls._instance.regional.add(regional)

    def is_rare(self, name: str) -> bool:
        return name.lower() in self.rare

    def is_regional(self, name: str) -> bool:
        return name.lower() in self.regional


def has_manager_role_or_manage_channel(ctx):
    return "anya Manager" in [r.name for r in ctx.author.roles] or ctx.author.guild_permissions.manage_channels


class StarboardScanner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_db = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.target_id = 716390085896962058
        self.handled_congrats = set()
        self.pokemon_specials = PokemonSpecialNames()

        self.dic = {
            "patterns": {
                "shiny_indicator": r"These colors seem unusual\.{3} ✨",
                "congrats_message": r"Congratulations\s+<@!?(\d+)> \| (SH )?(.*?)! You caught a Level \d+ (.+?):",
                "spawn_message_title": r"pokémon has appeared",
            },
            "colors": {
                "shiny": 0xFFD700,
                "rare": 0xFF4500,
                "regional": 0xADD8E6,
                "default": 0x00BFFF,
            },
        }

    async def get_starboard_channel(self, guild_id):
        return await self.config_db.get_starboard_channel(guild_id)

    async def set_starboard_channel(self, guild_id, channel_id):
        await self.config_db.set_starboard_channel(guild_id, channel_id)

    def transform_name(self, name):
        variants = {
            "alolan": "-alola", "galarian": "-galar", "hisuian": "-hisui",
            "paldean": "-paldea", "mega": "-mega"
        }
        name_clean = re.sub(r"[^a-zA-Z\s]", "", name)
        lower = name_clean.lower()
        for key, suffix in variants.items():
            if key in lower:
                parts = name_clean.split()
                base = parts[1] if len(parts) > 1 else parts[0]
                return base.lower() + suffix, key
        return name_clean.lower(), None

    def extract_data(self, content):
        match = re.match(self.dic["patterns"]["congrats_message"], content)
        if not match:
            return None, False, None
        user_id = int(match.group(1))
        shiny = bool(match.group(2) or re.search(self.dic["patterns"]["shiny_indicator"], content))
        name = match.group(3) or match.group(4)
        name_transformed, _ = self.transform_name(name)
        return user_id, shiny, name_transformed

    async def find_spawn_message(self, message):
        async for msg in message.channel.history(limit=50, before=message):
            if msg.author.id == self.target_id:
                for e in msg.embeds:
                    if e.title and re.search(self.dic["patterns"]["spawn_message_title"], e.title, re.IGNORECASE):
                        return msg
        return None

    def determine_color(self, shiny, name):
        if shiny:
            return self.dic["colors"]["shiny"]
        if self.pokemon_specials.is_rare(name):
            return self.dic["colors"]["rare"]
        if self.pokemon_specials.is_regional(name):
            return self.dic["colors"]["regional"]
        return self.dic["colors"]["default"]

    async def get_user_display(self, guild, user_id):
        try:
            member = await guild.fetch_member(user_id)
            return member.display_name
        except:
            return f"<@{user_id}>"

    async def create_embed(self, original_message, caught_name, shiny, catcher_id):
        color = self.determine_color(shiny, caught_name)
        embed = Embed(
            title=original_message.embeds[0].title if original_message.embeds else "Pokémon Caught!",
            color=color
        )

        catcher_name = await self.get_user_display(original_message.guild, catcher_id)
        embed.description = (
            f"Caught Pokémon: **{caught_name}**\n"
            f"Shiny: {'Yes ✨' if shiny else 'No'}\n"
            f"Caught by: {catcher_name}\n"
            f"[View spawn message]({original_message.jump_url})"
        )

        try:
            user = await self.bot.fetch_user(catcher_id)
            embed.set_thumbnail(url=user.display_avatar.url)
        except:
            pass

        if original_message.embeds and original_message.embeds[0].image:
            embed.set_image(url=original_message.embeds[0].image.url)

        embed.set_footer(text=f"Caught at: {datetime.now().strftime('%I:%M %p | %b %d, %Y')} | Type: Unknown")
        return embed

    async def send_congrats_embed(self, channel, user, pokemon_name, shiny):
        embed = Embed(
            title="🎉 Congrats! Your catch was sent to the Starboard!",
            description=(
                f"**{user.mention}**, your catch of **{'Shiny ' if shiny else ''}{pokemon_name.title()}** "
                "has been stored in the starboard for everyone to admire!\n\n"
                "Keep hunting rare and shiny Pokémon!"
            ),
        
        )
        embed.set_thumbnail(url="https://media.discordapp.net/attachments/1279353553110040596/1400548137139179720/eskXPvubXzzyyHtVnk99TPURB9aicET47kEpgAAAABJRU5ErkJggg.png?ex=688d0998&is=688bb818&hm=92c59fe7fb495bc881bff57ab9e5ce67151be35683286e80dec7fa7647dd5f06&=&format=webp&quality=lossless&width=457&height=457")
        embed.set_footer(text=f"Stored at: {datetime.now().strftime('%I:%M %p | %b %d, %Y')}")
        await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.id != self.target_id or message.id in self.handled_congrats:
            return
        self.handled_congrats.add(message.id)

        if "Congratulations" in message.content and "caught a Level" in message.content:
            catcher_id, shiny, caught_name = self.extract_data(message.content)
            if not caught_name:
                return

            spawn_msg = await self.find_spawn_message(message)
            if not spawn_msg:
                return

            await self.config_db.add_star(
                message_id=str(message.id),
                user_id=catcher_id,
                pokemon=caught_name,
                level=None,
                shiny=shiny,
                rare=self.pokemon_specials.is_rare(caught_name),
                regional=self.pokemon_specials.is_regional(caught_name),
                timestamp=datetime.now().isoformat(),
                jump_url=spawn_msg.jump_url
            )

            channel_id = await self.get_starboard_channel(message.guild.id)
            if channel := self.bot.get_channel(channel_id):
                embed = await self.create_embed(spawn_msg, caught_name, shiny, catcher_id)
                await channel.send(embed=embed, reference=message)

                # 🔔 Send confirmation/congrats message
                try:
                    member = await message.guild.fetch_member(catcher_id)
                    await self.send_congrats_embed(message.channel, member, caught_name, shiny)
                except:
                    pass

    @commands.command(name="set_starboard")
    @commands.check(has_manager_role_or_manage_channel)
    async def set_starboard(self, ctx, channel: TextChannel):
        await self.set_starboard_channel(ctx.guild.id, channel.id)
        await ctx.send(f"✅ Starboard channel set to {channel.mention}")

    @set_starboard.error
    async def set_starboard_error(self, ctx, error):
        if isinstance(error, CheckFailure):
            await ctx.send(embed=Embed(
                title="Permission Denied",
                description="You need the **Anya Manager** role or **Manage Channels** permission.",
                color=0xFF0000
            ))
        else:
            await ctx.send(f"Error: {str(error)}")

    @commands.command(name="testb")
    async def test_starboard(self, ctx, *, pokemon_name: str = "Alolan Vulpix"):
        if not ctx.message.reference:
            return await ctx.send("❌ Reply to a message with a spawn embed to test.")

        replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        if not replied_msg.embeds or not replied_msg.embeds[0].image:
            return await ctx.send("❌ The replied message does not contain an embed with an image.")

        caught_name, _ = self.transform_name(pokemon_name)
        fake = type("FakeMsg", (), {
            "embeds": replied_msg.embeds,
            "jump_url": replied_msg.jump_url,
            "created_at": replied_msg.created_at,
            "guild": ctx.guild
        })()

        embed = await self.create_embed(fake, caught_name, False, ctx.author.id)

        channel_id = await self.get_starboard_channel(ctx.guild.id)
        channel = self.bot.get_channel(channel_id) or ctx.channel

        await channel.send(f"🧪 Test Starboard Embed for **{caught_name}** (Shiny: False) by {ctx.author.mention}")
        await channel.send(embed=embed)

        # 🔔 Also send confirmation/congrats message for testing
        await self.send_congrats_embed(ctx.channel, ctx.author, caught_name, False)


def setup(bot):
    bot.add_cog(StarboardScanner(bot))
