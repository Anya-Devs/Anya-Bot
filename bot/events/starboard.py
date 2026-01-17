import os
import re
import csv
import traceback
from pathlib import Path
from discord.ext import commands
import discord
from motor.motor_asyncio import AsyncIOMotorClient

from imports.discord_imports import *
from bot.utils.subcogs.utils.mongo import MongoHelper


class StarboardConfig:
    """Constants, regex patterns, and embed templates for starboard logic."""

    patterns = {
        "shiny_indicator": r"These colors seem unusual\.{3} ✨",
        "unknown_emoji": r"<:unknown:\d+>|:unknown:",
        "congrats_message": re.compile(
            r"Congratulations\s+"
            r"(?:<@!?(\d+)>|@([\w_]+))\s*!"
            r"\s*You caught a Level\s+(\d+)\s+"
            r"([A-Za-z0-9\s\-\'\.:]+?)"
            r"(?::[a-zA-Z0-9_]+:|<:[a-zA-Z0-9_]+:\d+>)"
            r"(?:\s*\([\d\.]+%\))?",
            re.IGNORECASE,
        ),
        "spawn_message_title": r"pokémon has appeared",
    }

    colors = {
        "shiny": 0x131416,
        "rare": 0x131416,
        "regional": 0x131416,
        "default": 0x131416,
    }

    congrats_thumbnail = "attachment://congrats_thumbnail.png"

    embed_layout = {
        "congrats": {
            "title": "<a:tada:1401401635439251587> Congrats!",
            "description_template": (
                "{mention}, you've caught a {type_label} {shiny} **{pokemon_name}**!"
               
            ),
            "show_thumbnail": True,
            "show_timestamp": True,
            "thumbnail_url": congrats_thumbnail,
        },
        "starboard": {
            "title_template": "{sparkle_emoji} {pokemon_name}",
            "description_template": "Catcher: {mention}\n> [Go to spawn]({spawn_location})",
        },
    }

    target_ids = [716390085896962058, 1124389055598170182]
    ignore_channels = [1278580578593148978]
    special_names_file = Path("data/commands/pokemon/pokemon_special_names.csv")

    rare_names: set[str] = set()
    regional_names: set[str] = set()
    # Mapping from variant names to base names
    variant_to_base: dict[str, str] = {}

    @classmethod
    def load_special_names(cls):
        try:
            with cls.special_names_file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rare_name = row.get("Rare Pokémon", "").strip()
                    regional_name = row.get("Regional Pokémon", "").strip()
                    
                    if rare_name:
                        cls.rare_names.add(rare_name.lower())
                    
                    if regional_name:
                        cls.regional_names.add(regional_name.lower())
                        # Create mapping from variant to base name
                        base_name = cls._extract_base_name(regional_name)
                        if base_name != regional_name.lower():
                            cls.variant_to_base[regional_name.lower()] = base_name
                            
        except Exception as e:
            print(f"[ERROR] Failed loading special names CSV: {e}")
            cls.rare_names, cls.regional_names = set(), set()

    @classmethod
    def _extract_base_name(cls, pokemon_name: str) -> str:
        """Extract base Pokémon name from variant forms."""
        name = pokemon_name.lower().strip()
        
        # Regional/form prefixes and suffixes to remove
        prefixes = [
            "alolan", "galarian", "hisuian", "paldean", 
            "fire", "water", "grass", "electric", "ice", "fighting", "poison", 
            "ground", "flying", "psychic", "bug", "rock", "ghost", "dragon", 
            "dark", "steel", "fairy", "normal"
        ]
        
        suffixes = [
            "alola", "galar", "hisui", "paldea", "totem", "standard", "zen",
            "cap", "original-cap", "hoenn-cap", "sinnoh-cap", "unova-cap",
            "kalos-cap", "alola-cap", "partner-cap", "world-cap",
            "busted", "disguised", "aqua-breed", "blaze-breed", "combat-breed"
        ]
        
        # Remove prefixes
        for prefix in prefixes:
            if name.startswith(prefix + " "):
                name = name[len(prefix) + 1:].strip()
                break
        
        # Remove suffixes (connected with hyphens)
        for suffix in suffixes:
            if name.endswith("-" + suffix):
                name = name[:-len(suffix)-1].strip()
                break
        
        return name

    @classmethod
    def normalize_pokemon_name(cls, pokemon_name: str) -> str:
        """Convert variant Pokémon names to their base forms for rarity checking."""
        name_lower = pokemon_name.lower().strip()
        
        # Check if we have a direct mapping
        if name_lower in cls.variant_to_base:
            return cls.variant_to_base[name_lower]
        
        # Extract base name using our extraction logic
        return cls._extract_base_name(name_lower)


class StarboardProcessor:
    """Handles starboard logic, embed generation, and message parsing."""

    def __init__(self, db_helper: MongoHelper):
        self.config_db = db_helper
        StarboardConfig.load_special_names()

    def is_rare_name(self, name: str) -> bool:
        """Check if a Pokémon name is rare, including variant forms."""
        name_lower = name.lower().strip()
        # Check exact match first
        if name_lower in StarboardConfig.rare_names:
            return True
        # Check normalized base name
        base_name = StarboardConfig.normalize_pokemon_name(name)
        return base_name in StarboardConfig.rare_names

    def is_regional_name(self, name: str) -> bool:
        """Check if a Pokémon name is regional, including variant forms."""
        name_lower = name.lower().strip()
        # Check exact match first
        if name_lower in StarboardConfig.regional_names:
            return True
        # Check normalized base name
        base_name = StarboardConfig.normalize_pokemon_name(name)
        return base_name in StarboardConfig.regional_names

    def determine_color(self, shiny: bool, name: str) -> int:
        return StarboardConfig.colors["default"]

    async def process_message(self, bot, message: discord.Message):
        try:
            shiny = bool(
                re.search(StarboardConfig.patterns["shiny_indicator"], message.content)
            )

            # Process all catch messages in the content
            matches = list(StarboardConfig.patterns["congrats_message"].finditer(message.content))
            if not matches and not shiny:
                return
            
            # Fetch spawn message once for all catches
            spawn_msg, spawn_color = await self.find_spawn_message(bot, message)
            
            # Process each catch
            for match in matches:
                await self._process_single_catch(bot, message, match, shiny, spawn_msg, spawn_color)

        except Exception as e:
            print(f"[ERROR] Exception in process_message: {e}")
            traceback.print_exc()

    async def _process_single_catch(self, bot, message: discord.Message, match, shiny: bool, spawn_msg, spawn_color):
        try:
            sparkle_emoji = "✨"
            
            catcher_id = self._extract_catcher_id(message, match)
            if catcher_id is None:
                return

            pokemon_name_display = match.group(4).strip()

            # Check if this Pokémon is rare or regional using our improved name matching
            # The normalize_pokemon_name function handles variant forms automatically
            is_rare = self.is_rare_name(pokemon_name_display)
            is_regional = self.is_regional_name(pokemon_name_display)
            
            # Only add to starboard if it's shiny, rare, or regional
            if not (shiny or is_rare or is_regional):
                return

            catcher_user = await bot.fetch_user(catcher_id)
            catcher_avatar_url = catcher_user.display_avatar.url if catcher_user else None
            spawn_image_url, spawn_jump_url = self._extract_spawn_info(spawn_msg)

            await self._send_starboard_embed(
                bot, message.guild.id, catcher_id, pokemon_name_display,
                sparkle_emoji if shiny else "", catcher_avatar_url,
                spawn_image_url, shiny, spawn_color, spawn_jump_url
            )
            await self._send_congrats_embed(
                message, catcher_id, pokemon_name_display, shiny, is_rare, is_regional,
                spawn_color, spawn_msg
            )

        except Exception as e:
            print(f"[ERROR] Exception in _process_single_catch: {e}")
            traceback.print_exc()

    def _extract_catcher_id(self, message, match):
        if not match:
            return None
        # Group 1 is user ID from <@!?(\d+)> format
        user_id = match.group(1)
        if user_id:
            return int(user_id)
        # Group 2 is username from @([\w_]+) format
        username = match.group(2)
        if username:
            username_lower = username.lower()
            user = discord.utils.find(
                lambda m: m.name.lower() == username_lower or m.display_name.lower() == username_lower,
                message.guild.members,
            )
            return user.id if user else None
        return None

    def _extract_spawn_info(self, spawn_msg):
        if spawn_msg and spawn_msg.embeds:
            first_embed = spawn_msg.embeds[0]
            return (
                first_embed.image.url if first_embed.image else None,
                spawn_msg.jump_url,
            )
        return None, None

    async def _send_starboard_embed(
        self, bot, guild_id, catcher_id, pokemon_name,
        sparkle_emoji, catcher_avatar_url, spawn_image_url,
        shiny, spawn_color, spawn_jump_url
    ):
        cfg = StarboardConfig.embed_layout["starboard"]
        if sparkle_emoji:
            title = f"✨ {pokemon_name.title()}"
        else:
            title = pokemon_name.title()
        
        # Ensure we have a valid spawn jump URL
        if not spawn_jump_url or spawn_jump_url == "N/A":
            spawn_jump_url = "N/A"
        
        embed = discord.Embed(
            title=title,
            description=cfg["description_template"].format(
                mention=f"<@{catcher_id}>",
                pokemon_name=pokemon_name.title(),
                spawn_location=spawn_jump_url
            ),
            color=StarboardConfig.colors["default"],
        )
        
        # Set the spawn image from the Pokétwo spawn embed
        if spawn_image_url:
            embed.set_image(url=spawn_image_url)
        
        await self.send_to_starboard(bot, embed, guild_id)

    async def _send_congrats_embed(
     self, message, catcher_id, pokemon_name, shiny, is_rare, is_regional,
     spawn_color, spawn_msg  # now a Message object
     ):
     cfg = StarboardConfig.embed_layout["congrats"]

     # Use channel mention from spawn message
     spawn_channel_mention = f"<#{spawn_msg.channel.id}>" if spawn_msg else "N/A"

     mention = f"<@{catcher_id}>"
     shiny_label = " shiny" if shiny else ""
     type_label = "rare" if is_rare else ("regional" if is_regional else "")

     starboard_channel_id = await self.config_db.get_starboard_channel(message.guild.id)
     starboard_mention = f"<#{starboard_channel_id}>" if starboard_channel_id else "N/A"

     embed = discord.Embed(
        title=cfg["title"],
        description=f"{mention}, you've caught a{' ' + type_label if type_label else ''}{shiny_label} **{pokemon_name.title()}**!\n> Posted momment to {starboard_mention}",
        color=StarboardConfig.colors["default"],
        #timestamp=message.created_at if cfg.get("show_timestamp") else None,
    )
     if cfg.get("show_thumbnail") and cfg["thumbnail_url"].startswith(('http://', 'https://', 'attachment://')):
        embed.set_thumbnail(url=cfg["thumbnail_url"])
    
     thumbnail_path = "data/events/starboard/images/congrats_thumbnail.png"
     if os.path.exists(thumbnail_path):
         file = discord.File(thumbnail_path, filename="congrats_thumbnail.png")
         await message.channel.send(embed=embed, file=file, allowed_mentions=discord.AllowedMentions.none())
     else:
         await message.channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none()) 

    async def find_spawn_message(self, bot, message: discord.Message):
        try:
            async for msg in message.channel.history(limit=50, before=message):
                if msg.author.id in StarboardConfig.target_ids:
                    for e in msg.embeds:
                        if e.title and re.search(StarboardConfig.patterns["spawn_message_title"], e.title, re.IGNORECASE):
                            return msg, (e.color.value if e.color else None)
            return None, None
        except Exception as e:
            print(f"[ERROR] find_spawn_message: {e}")
            traceback.print_exc()
            return None, None

    async def send_to_starboard(self, bot, embed: discord.Embed, guild_id: int):
        try:
            channel_id = await self.config_db.get_starboard_channel(guild_id)
            if not channel_id:
                return
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except Exception as e:
            print(f"[ERROR] send_to_starboard: {e}")
            traceback.print_exc()


class StarboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.processor = StarboardProcessor(
            MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id in StarboardConfig.target_ids and message.channel.id not in StarboardConfig.ignore_channels:
            await self.processor.process_message(self.bot, message)


async def setup(bot: commands.Bot):
    await bot.add_cog(StarboardCog(bot))
