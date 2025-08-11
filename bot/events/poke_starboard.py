import os
import re
import csv
from pathlib import Path
from datetime import datetime
import traceback

from imports.discord_imports import *
from utils.subcogs.pokemon import *
from utils.events.starboard import *
from bot.token import use_test_bot as ut


class StarboardConfig:
    patterns = {
        "shiny_indicator": r"These colors seem unusual\.{3} ✨",
        "congrats_message": re.compile(
            r"Congratulations\s+"
            r"(?:<@!?(\d+)>|@([\w_]+))\s*"
            r"!\s*You caught a Level\s+(\d+)\s+"
            r"([A-Za-z\s\-]+)"
            r"(?:" 
            r"(?::[a-z]+:|<:[a-z]+:\d+>)"
            r")?"
            r"(?:\s*\([\d\.]+%\))?"
            r"!?",
            re.IGNORECASE
        ),
        "spawn_message_title": r"pokémon has appeared",
    }

    colors = {
        "shiny": 0xFFD700,
        "rare": 0xFF4500,
        "regional": 0xADD8E6,
        "default": 0x00BFFF,
    }

    congrats_thumbnail = (
        "https://media.discordapp.net/attachments/1279353553110040596/"
        "1400548137139179720/eskXPvubXzzyyHtVnk99TPURB9aicET47kEpgAAAABJRU5ErkJggg.png"
        "?ex=688d0998&is=688bb818&hm=92c59fe7fb495bc881bff57ab9e5ce67151be35683286e80"
        "dec7fa7647dd5f06&=&format=webp&quality=lossless&width=457&height=457"
    )

    embed_layout = {
        "congrats": {
            "title": "<a:tada:1401401635439251587> Congrats!",
            "description_template": (
                "{mention}, you’ve caught a {type_label} **{shiny}{pokemon_name}**! "
                "It’s now proudly displayed in <#{starboard_channel_id}> for everyone to admire!"
            ),
            "show_thumbnail": True,
            "show_image": True,
            "show_timestamp": True,
            "thumbnail_url": congrats_thumbnail,
        },
        "starboard": {
            "title_template": "{shiny_emoji} {pokemon_name}",
            "description_template": "Caught by {mention}\nLocation: {spawn_location}",
        }
    }

    target_ids = [716390085896962058, 1124389055598170182]
    ignore_channels = [1278580578593148978]

    special_names_file = Path("data/commands/pokemon/pokemon_special_names.csv")

    @classmethod
    def load_special_names(cls):
        cls.rare_names = set()
        cls.regional_names = set()
        try:
            with cls.special_names_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rare = row.get("Rare Pokémon", "").strip().lower()
                    regional = row.get("Regional Pokémon", "").strip().lower()
                    if rare:
                        cls.rare_names.add(rare)
                    if regional:
                        cls.regional_names.add(regional)
        except Exception as e:
            print(f"[ERROR] loading special names CSV: {e}")
            cls.rare_names = set()
            cls.regional_names = set()


class StarboardScanner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_db = MongoHelper(
            AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"]
        )
        StarboardConfig.load_special_names()

    def is_rare_name(self, name):
        return name.lower() in StarboardConfig.rare_names

    def is_regional_name(self, name):
        return name.lower() in StarboardConfig.regional_names

    @commands.command(name="set_starboard")
    @commands.check(has_manager_role_or_manage_channel)
    async def set_starboard(self, ctx, channel: TextChannel):
        try:
            await self.config_db.set_starboard_channel(ctx.guild.id, channel.id)
            await ctx.send(f"✅ Starboard channel set to {channel.mention}")
        except Exception as e:
            print(f"[ERROR] set_starboard: {e}")
            traceback.print_exc()
            await ctx.send(f"⚠️ Error setting starboard: {e}")

    @set_starboard.error
    async def set_starboard_error(self, ctx, error):
        if isinstance(error, CheckFailure):
            await ctx.send(embed=Embed(
                title="Permission Denied",
                description="You need the **Anya Manager** role or **Manage Channels** permission.",
                color=0xFF0000
            ))
        else:
            print(f"[ERROR] set_starboard_error: {error}")
            traceback.print_exc()
            await ctx.send(f"Error: {str(error)}")

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if message.author.id in StarboardConfig.target_ids:
                if message.channel.id not in StarboardConfig.ignore_channels:
                    await self.process_message(message)
                    
        except Exception as e:
            print(f"[ERROR] on_message: {e}")
            traceback.print_exc()

    async def process_message(self, message):
        try:
            shiny = bool(re.search(StarboardConfig.patterns["shiny_indicator"], message.content))
            sparkle_emoji = "✨"

            first_line = message.content.split('\n', 1)[0]
            match = StarboardConfig.patterns["congrats_message"].search(first_line)
            if not match and not shiny:
                return

            catcher_id = None
            if message.mentions:
                catcher_id = message.mentions[0].id
            else:
                if match:
                    username = match.group(2)
                    if username:
                        username_lower = username.lower()
                        user = discord.utils.find(
                            lambda m: m.name.lower() == username_lower or m.display_name.lower() == username_lower,
                            message.guild.members
                        )
                        if user:
                            catcher_id = user.id

            if catcher_id is None:
                return

            level = int(match.group(3)) if match else 0
            pokemon_name = match.group(4).strip() if match else "Unknown"

            # Check if Pokémon is rare or regional by exact name match in CSV
            is_rare = self.is_rare_name(pokemon_name)
            is_regional = self.is_regional_name(pokemon_name)

            # Only proceed if shiny, rare, or regional
            if not (shiny or is_rare or is_regional):
                return

            spawn_msg, spawn_color = await self.find_spawn_message(message)

            catcher_user = await self.bot.fetch_user(catcher_id)
            catcher_avatar_url = catcher_user.display_avatar.url if catcher_user else None

            spawn_image_url = None
            spawn_location_text = "Spawn location unknown"
            if spawn_msg and spawn_msg.embeds:
                first_embed = spawn_msg.embeds[0]
                spawn_image_url = first_embed.image.url if first_embed.image else None
                spawn_location_text = spawn_msg.jump_url or spawn_location_text

            starboard_cfg = StarboardConfig.embed_layout["starboard"]
            starboard_title = starboard_cfg["title_template"].format(pokemon_name=pokemon_name)

            starboard_embed = Embed(
                title=starboard_title,
                description=starboard_cfg["description_template"].format(
                    mention=f"<@{catcher_id}>",
                    spawn_location=spawn_location_text,
                    shiny_emoji=sparkle_emoji if shiny else "",
                ),
                color=spawn_color or self.determine_color(shiny, pokemon_name)
            )
            if catcher_avatar_url:
                starboard_embed.set_thumbnail(url=catcher_avatar_url)
            if spawn_image_url:
                starboard_embed.set_image(url=spawn_image_url)

            await self.send_to_starboard(starboard_embed, message.guild.id)

            starboard_channel_id = await self.config_db.get_starboard_channel(message.guild.id) or 0
            congrats_cfg = StarboardConfig.embed_layout["congrats"]
            congrats_embed = Embed(
                title=congrats_cfg["title"],
                description=congrats_cfg["description_template"].format(
                    mention=f"<@{catcher_id}>",
                    type_label="rare" if is_rare else "regional" if is_regional else "regional",
                    shiny="Shiny " if shiny else "",
                    pokemon_name=pokemon_name,
                    starboard_channel_id=starboard_channel_id,
                ),
                color=spawn_color or self.determine_color(shiny, pokemon_name),
                timestamp=message.created_at if congrats_cfg.get("show_timestamp") else None
            )
            if congrats_cfg.get("show_thumbnail"):
                congrats_embed.set_thumbnail(url=congrats_cfg["thumbnail_url"])

            await message.channel.send(embed=congrats_embed)

        except Exception as e:
            print(f"[ERROR] Exception in process_message: {e}")
            traceback.print_exc()

    async def find_spawn_message(self, message):
        try:
            async for msg in message.channel.history(limit=50, before=message):
                if msg.author.id in StarboardConfig.target_ids:
                    for e in msg.embeds:
                        if e.title and re.search(StarboardConfig.patterns["spawn_message_title"], e.title, re.IGNORECASE):
                            embed_color = e.color.value if e.color else None
                            return msg, embed_color
            return None, None
        except Exception as e:
            print(f"[ERROR] find_spawn_message: {e}")
            traceback.print_exc()
            return None, None

    def determine_color(self, shiny, name):
        if shiny:
            return StarboardConfig.colors["shiny"]
        if self.is_rare_name(name):
            return StarboardConfig.colors["rare"]
        if self.is_regional_name(name):
            return StarboardConfig.colors["regional"]
        return StarboardConfig.colors["default"]

    async def get_user_display(self, guild, user_id):
        try:
            member = await guild.fetch_member(user_id)
            return member.display_name
        except:
            try:
                user = await self.bot.fetch_user(user_id)
                return user.name
            except Exception as e:
                print(f"[ERROR] get_user_display: {e}")
                traceback.print_exc()
                return "Unknown User"

    async def send_to_starboard(self, embed, guild_id):
        try:
            if not embed:
                return
            channel_id = await self.config_db.get_starboard_channel(guild_id)
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"[ERROR] send_to_starboard: {e}")
            traceback.print_exc()


async def setup(bot):
    await bot.add_cog(StarboardScanner(bot))
