import discord
from discord.ext import commands
import random
import asyncio
import aiohttp
import logging
import json
import io
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from utils.cogs.game import *
from utils.cogs.game.view import *
from utils.cogs.game.const import *

logger = logging.getLogger(__name__)

class Games(commands.Cog):
    """🎮 Mini-games that use stella points - Gamble, Classic Games & Grounded Economy!"""
    
    def __init__(self, bot):
        self.bot = bot
        from utils.cogs.quest import Quest_Data
        self.quest_data = Quest_Data(bot)
        self.session: Optional[aiohttp.ClientSession] = None
        self.active_games: Dict[str, Dict] = {}  # Track active hangman/wordle games
        self.user_cooldowns: Dict[str, Dict[str, datetime]] = {}  # Track cooldowns
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self.session
    
    def cog_unload(self):
        """Cleanup when cog unloads."""
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())
    
    async def get_user_character(self, user_id: str, guild_id: str) -> Optional[str]:
        """Get the user's selected Spy x Family character if any."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.selected_character": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("inventory", {}).get("selected_character")
        except Exception as e:
            logger.error(f"Error getting character: {e}")
        return None
    
    async def check_cooldown(self, user_id: str, action: str, cooldown_seconds: int) -> Optional[timedelta]:
        """Check if user is on cooldown. Returns remaining time or None if ready."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            # Get last action time from DB
            result = await server_col.find_one(
                {"guild_id": "global_cooldowns"},
                {f"cooldowns.{user_id}.{action}": 1}
            )
            
            if result:
                last_time_str = result.get("cooldowns", {}).get(user_id, {}).get(action)
                if last_time_str:
                    last_time = datetime.fromisoformat(last_time_str)
                    elapsed = datetime.now(timezone.utc) - last_time
                    if elapsed.total_seconds() < cooldown_seconds:
                        return timedelta(seconds=cooldown_seconds) - elapsed
        except Exception as e:
            logger.error(f"Cooldown check error: {e}")
        return None
    
    async def set_cooldown(self, user_id: str, action: str):
        """Set cooldown timestamp for an action."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            await server_col.update_one(
                {"guild_id": "global_cooldowns"},
                {"$set": {f"cooldowns.{user_id}.{action}": datetime.now(timezone.utc).isoformat()}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Set cooldown error: {e}")
    
    async def check_timer(self, ctx, command: str) -> Optional[str]:
        """Check command cooldown and usage limits. Returns error message or None."""
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id)
        config = get_timer_config(command)
        
        # Always check command cooldown first (short delay between uses)
        command_cooldown = config.get("command_cooldown", 5)
        remaining = await self.check_cooldown(user_id, f"{command}_command", command_cooldown)
        if remaining:
            return format_cooldown_message(remaining, command)
        
        # For non-daily commands, check if user has reached usage limit
        if not uses_daily_reset(command):
            current_uses = await self.get_current_uses(user_id, guild_id, command)
            if current_uses >= config["max_uses"]:
                # Check if main cooldown is active
                main_remaining = await self.check_cooldown(user_id, f"{command}_main", config["cooldown"])
                if main_remaining:
                    return format_cooldown_message(main_remaining, command)
                else:
                    # User has reached limit but cooldown expired, reset uses
                    await self.reset_uses(user_id, guild_id, command)
                    return None
        else:
            # Only check daily limits for true daily commands (like claim)
            daily_plays = await self.get_daily_plays(user_id, guild_id, command)
            if daily_plays >= config["max_uses"]:
                return f"⏰ {command.replace('_', ' ').title()} is limited to {config['max_uses']} uses per day. You've used all {config['max_uses']} uses today."
        
        return None
    
    async def get_daily_streak(self, user_id: str, guild_id: str) -> int:
        """Get user's daily claim streak."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.daily_streak": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("daily_streak", 0)
        except Exception as e:
            logger.error(f"Error getting streak: {e}")
        return 0
    
    async def update_daily_streak(self, user_id: str, guild_id: str, streak: int):
        """Update user's daily claim streak."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.daily_streak": streak}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error updating streak: {e}")
    
    def format_time(self, td: timedelta) -> str:
        """Format timedelta to readable string."""
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    async def _get_daily_game_plays(self, user_id: str, guild_id: str, game: str) -> int:
        """Get how many times user played a game today."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]
            
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            result = await server_collection.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.games.{game}.{today}": 1}
            )
            
            if result:
                return result.get("members", {}).get(user_id, {}).get("games", {}).get(game, {}).get(today, 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting daily plays: {e}")
            return 0
    
    async def _increment_daily_game_plays(self, user_id: str, guild_id: str, game: str):
        """Increment the daily play count for a game."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]
            
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            await server_collection.update_one(
                {"guild_id": guild_id},
                {"$inc": {f"members.{user_id}.games.{game}.{today}": 1}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error incrementing daily plays: {e}")
    
    async def get_daily_plays(self, user_id: str, guild_id: str, game: str) -> int:
        """Get how many times user played a game today."""
        return await self._get_daily_game_plays(user_id, guild_id, game)
    
    async def increment_daily_plays(self, user_id: str, guild_id: str, game: str):
        """Increment the daily play count for a game."""
        await self._increment_daily_game_plays(user_id, guild_id, game)
    
    async def increment_plays(self, user_id: str, guild_id: str, command: str):
        """Unified function to increment play count for any command."""
        config = get_timer_config(command)
        
        # For daily commands, use daily tracking
        if uses_daily_reset(command):
            await self.increment_daily_plays(user_id, guild_id, command)
        else:
            # For usage-based commands, track current session uses
            await self.increment_current_uses(user_id, guild_id, command)
            current_uses = await self.get_current_uses(user_id, guild_id, command)
            
            # If reached max uses, set main cooldown
            if current_uses >= config["max_uses"]:
                await self.set_cooldown(user_id, f"{command}_main")
    
    async def get_current_uses(self, user_id: str, guild_id: str, command: str) -> int:
        """Get current usage count for a command in this session."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.game_uses.{command}": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("game_uses", {}).get(command, 0)
        except Exception as e:
            logger.error(f"Error getting current uses: {e}")
        return 0
    
    async def increment_current_uses(self, user_id: str, guild_id: str, command: str):
        """Increment current usage count for a command."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$inc": {f"members.{user_id}.game_uses.{command}": 1}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error incrementing current uses: {e}")
    
    async def reset_uses(self, user_id: str, guild_id: str, command: str):
        """Reset usage count for a command when cooldown expires."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.game_uses.{command}": 0}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error resetting uses: {e}")
    
    def get_random_rarity(self) -> str:
        """Get a random rarity based on chances (gacha-style)."""
        roll = random.random()
        cumulative = 0
        for rarity, data in RARITY_CONFIG.items():
            cumulative += data["chance"]
            if roll <= cumulative:
                return rarity
        return "common"
    
    def get_slot_symbol(self) -> str:
        """Get a weighted random slot symbol."""
        symbols = list(SLOT_SYMBOLS.keys())
        weights = [SLOT_SYMBOLS[s]["weight"] for s in symbols]
        return random.choices(symbols, weights=weights, k=1)[0]
    
    async def fetch_pokemon_info(self, pokemon_id: int) -> Optional[Dict[str, Any]]:
        """Fetch Pokemon info from API (just for display, not rarity)."""
        session = await self.get_session()
        
        try:
            async with session.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "name": data["name"].replace("-", " ").title(),
                        "id": data["id"],
                        "sprite": data["sprites"]["other"]["official-artwork"]["front_default"] 
                                  or data["sprites"]["front_default"],
                        "types": [t["type"]["name"].title() for t in data.get("types", [])],
                    }
        except Exception as e:
            logger.debug(f"Pokemon API error (using fallback): {e}")
        
        return None
    
    async def fetch_anime_character_info(self) -> Optional[Dict[str, Any]]:
        """Fetch random anime character info from API (just for display, not rarity)."""
        session = await self.get_session()
        
        try:
            # Random character ID (1-5000 for faster response)
            char_id = random.randint(1, 5000)
            
            async with session.get(f"https://api.jikan.moe/v4/characters/{char_id}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    char = data.get("data", {})
                    
                    if char:
                        # Get anime they're from
                        anime_name = "Unknown Anime"
                        if char.get("anime"):
                            anime_list = char.get("anime", [])
                            if anime_list:
                                anime_name = anime_list[0].get("anime", {}).get("title", "Unknown Anime")
                        
                        return {
                            "name": char.get("name", "Unknown"),
                            "anime": anime_name,
                            "image": char.get("images", {}).get("jpg", {}).get("image_url"),
                            "favorites": char.get("favorites", 0),
                        }
        except Exception as e:
            logger.debug(f"Jikan API error (using fallback): {e}")
        
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # GACHA SYSTEM METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def get_gacha_rarity(self, favorites: int = 0) -> str:
        """Determine rarity primarily from favorites/likes with light randomness.
        
        Tiered by favorites:
        - < 4,000: common
        - 4,000 - 9,999: uncommon
        - 10,000 - 24,999: rare
        - 25,000 - 49,999: epic
        - 50,000+: legendary
        
        A small random wiggle can bump up or down one tier to keep draws exciting,
        but high-favorite characters stay rare.
        """
        # Determine base tier from favorites
        if favorites >= 50000:
            base = "legendary"
        elif favorites >= 25000:
            base = "epic"
        elif favorites >= 10000:
            base = "rare"
        elif favorites >= 4000:
            base = "uncommon"
        else:
            base = "common"
        
        tiers = ["common", "uncommon", "rare", "epic", "legendary"]
        idx = tiers.index(base)
        
        # Light randomness (buffed ~10% overall): 12% chance to bump up, 8% to bump down (bounded)
        roll = random.random()
        if roll < 0.12 and idx < len(tiers) - 1:
            idx += 1
        elif roll > 0.92 and idx > 0:
            idx -= 1
        
        return tiers[idx]
    
    async def fetch_gacha_characters(self, count: int = 3, gender_filter: str = None) -> list:
        """Fetch multiple random anime characters FAST - parallel requests.
        Prioritizes characters with under 9k favorites (75% spawn rate).
        
        Args:
            count: Number of characters to fetch
            gender_filter: "Female" or "Male" to filter by gender, None for all
        """
        session = await self.get_session()
        
        # Fetch all characters in parallel for speed
        async def fetch_one_char(api_choice: str, force_low_favorites: bool = False):
            try:
                if api_choice == "jikan":
                    # Bias character ID selection based on force_low_favorites
                    if force_low_favorites:
                        # Lower IDs tend to have fewer favorites
                        char_id = random.randint(1, 5000)
                    else:
                        char_id = random.randint(1, 10000)
                    
                    # Use full endpoint to get anime info included
                    async with session.get(f"https://api.jikan.moe/v4/characters/{char_id}/full", timeout=aiohttp.ClientTimeout(total=4)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            char = data.get("data", {})
                            
                            if char and char.get("name"):
                                # Get anime from the full response
                                anime_name = "Original Character"
                                anime_list = char.get("anime", [])
                                if anime_list and len(anime_list) > 0:
                                    first_anime = anime_list[0].get("anime", {})
                                    anime_name = first_anime.get("title") or first_anime.get("name") or "Original Character"
                                
                                favorites = char.get("favorites", 0)
                                
                                # Quick gender check
                                about = (char.get("about", "") or "").lower()
                                gender = "Unknown"
                                if any(x in about for x in ["she ", "her ", "female", "woman", "girl"]):
                                    gender = "Female"
                                elif any(x in about for x in ["he ", "his ", "male", "man ", "boy"]):
                                    gender = "Male"
                                
                                if gender_filter and gender != gender_filter:
                                    return None
                                
                                images = char.get("images", {}).get("jpg", {})
                                image_url = images.get("large_image_url") or images.get("image_url")
                                
                                return {
                                    "id": char.get("mal_id"),
                                    "name": char.get("name", "Unknown"),
                                    "anime": anime_name,
                                    "image_url": image_url,
                                    "favorites": favorites,
                                    "rarity": self.get_gacha_rarity(favorites),
                                    "gender": gender,
                                }
                
                elif api_choice == "anilist":
                    query = '''
                    query ($page: Int) {
                        Page(page: $page, perPage: 1) {
                            characters(sort: FAVOURITES_DESC) {
                                id
                                name { full }
                                image { large }
                                favourites
                                gender
                                media(sort: POPULARITY_DESC, perPage: 1) {
                                    nodes { title { romaji } }
                                }
                            }
                        }
                    }
                    '''
                    
                    # Bias page selection for low favorites
                    if force_low_favorites:
                        # Higher page numbers tend to have lower favorites
                        variables = {"page": random.randint(300, 800)}
                    else:
                        variables = {"page": random.randint(1, 500)}
                    
                    async with session.post(
                        "https://graphql.anilist.co",
                        json={"query": query, "variables": variables},
                        timeout=aiohttp.ClientTimeout(total=3)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            chars = data.get("data", {}).get("Page", {}).get("characters", [])
                            
                            if chars:
                                char = chars[0]
                                gender = char.get("gender", "Unknown")
                                
                                if gender_filter and gender != gender_filter:
                                    return None
                                
                                anime_name = "Unlisted (AniList)"
                                media = char.get("media", {}).get("nodes", [])
                                if media:
                                    anime_name = media[0].get("title", {}).get("romaji", "Unknown Anime")
                                
                                return {
                                    "id": char.get("id"),
                                    "name": char.get("name", {}).get("full", "Unknown"),
                                    "anime": anime_name,
                                    "image_url": char.get("image", {}).get("large"),
                                    "favorites": char.get("favourites", 0),
                                    "rarity": self.get_gacha_rarity(char.get("favourites", 0)),
                                    "gender": gender,
                                }
                
                elif api_choice == "kitsu":
                    # Bias offset selection for low favorites
                    if force_low_favorites:
                        # Higher offsets tend to have lower favorites
                        offset = random.randint(3000, 8000)
                    else:
                        offset = random.randint(0, 5000)
                    
                    # Include media castings to get anime name
                    async with session.get(
                        f"https://kitsu.io/api/edge/characters?page[limit]=1&page[offset]={offset}&include=mediaCharacters.media",
                        timeout=aiohttp.ClientTimeout(total=4)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            chars = data.get("data", [])
                            
                            if chars:
                                char = chars[0]
                                attrs = char.get("attributes", {})
                                
                                name = attrs.get("canonicalName") or attrs.get("name", "Unknown")
                                image_url = None
                                if attrs.get("image"):
                                    image_url = attrs["image"].get("original") or attrs["image"].get("large")
                                
                                char_id = int(char.get("id", 0))
                                favorites = max(100, 10000 - (char_id % 9000))
                                
                                desc = (attrs.get("description") or "").lower()
                                gender = "Unknown"
                                if any(x in desc for x in ["she ", "her ", "female", "woman", "girl"]):
                                    gender = "Female"
                                elif any(x in desc for x in ["he ", "his ", "male", "man ", "boy"]):
                                    gender = "Male"
                                
                                if gender_filter and gender != gender_filter:
                                    return None
                                
                                # Get anime name from included media
                                anime_name = "Original Character"
                                included = data.get("included", [])
                                for inc in included:
                                    if inc.get("type") == "anime" or inc.get("type") == "manga":
                                        inc_attrs = inc.get("attributes", {})
                                        title = inc_attrs.get("canonicalTitle") or inc_attrs.get("titles", {}).get("en") or inc_attrs.get("titles", {}).get("en_jp")
                                        if title:
                                            anime_name = title
                                            break
                                
                                return {
                                    "id": char_id,
                                    "name": name,
                                    "anime": anime_name,
                                    "image_url": image_url,
                                    "favorites": favorites,
                                    "rarity": self.get_gacha_rarity(favorites),
                                    "gender": gender,
                                }
            except:
                return None
        
        # Determine how many characters should have under 9k favorites (75% chance)
        low_fav_count = sum(1 for _ in range(count) if random.random() < 0.75)
        high_fav_count = count - low_fav_count
        
        # Launch parallel requests with bias toward low favorites
        api_sources = ["jikan", "anilist", "kitsu"]
        tasks = []
        
        # Add tasks for low favorite characters (bias toward lower IDs/pages)
        for i in range(low_fav_count * 2):  # Fetch extra for filtering
            api = api_sources[i % 3]
            tasks.append(fetch_one_char(api, force_low_favorites=True))
        
        # Add tasks for regular characters
        for i in range(high_fav_count * 2):
            api = api_sources[i % 3]
            tasks.append(fetch_one_char(api, force_low_favorites=False))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter valid results and separate by favorites
        all_chars = [r for r in results if r and isinstance(r, dict)]
        low_fav_chars = [c for c in all_chars if c.get("favorites", 0) < 9000]
        high_fav_chars = [c for c in all_chars if c.get("favorites", 0) >= 9000]
        
        # Build final character list with 75% low favorites preference
        characters = []
        
        # Add low favorite characters first (up to low_fav_count)
        characters.extend(low_fav_chars[:low_fav_count])
        
        # Fill remaining slots with high favorite characters
        remaining_slots = count - len(characters)
        characters.extend(high_fav_chars[:remaining_slots])
        
        # If still need more characters, add any remaining
        if len(characters) < count:
            remaining_chars = [c for c in all_chars if c not in characters]
            characters.extend(remaining_chars[:count - len(characters)])
        
        # Fill with fallback characters if needed - with realistic rarity distribution
        fallback_pool = [
            # Common characters (50%)
            {"name": "Konohamaru", "anime": "Naruto", "gender": "Male", "favorites": 500},
            {"name": "Tenten", "anime": "Naruto", "gender": "Female", "favorites": 800},
            {"name": "Krillin", "anime": "Dragon Ball", "gender": "Male", "favorites": 600},
            {"name": "Usopp", "anime": "One Piece", "gender": "Male", "favorites": 700},
            {"name": "Mineta", "anime": "My Hero Academia", "gender": "Male", "favorites": 300},
            {"name": "Sakura Haruno", "anime": "Naruto", "gender": "Female", "favorites": 900},
            # Uncommon characters (25%)
            {"name": "Rock Lee", "anime": "Naruto", "gender": "Male", "favorites": 2000},
            {"name": "Shikamaru", "anime": "Naruto", "gender": "Male", "favorites": 3000},
            {"name": "Yamcha", "anime": "Dragon Ball", "gender": "Male", "favorites": 1500},
            {"name": "Nami", "anime": "One Piece", "gender": "Female", "favorites": 4000},
            # Rare characters (15%)
            {"name": "Kakashi", "anime": "Naruto", "gender": "Male", "favorites": 8000},
            {"name": "Vegeta", "anime": "Dragon Ball", "gender": "Male", "favorites": 12000},
            {"name": "Zoro", "anime": "One Piece", "gender": "Male", "favorites": 15000},
            {"name": "Hinata Hyuga", "anime": "Naruto", "gender": "Female", "favorites": 10000},
            # Epic characters (7%)
            {"name": "Levi Ackerman", "anime": "Attack on Titan", "gender": "Male", "favorites": 25000},
            {"name": "Yor Forger", "anime": "Spy x Family", "gender": "Female", "favorites": 30000},
            {"name": "Loid Forger", "anime": "Spy x Family", "gender": "Male", "favorites": 28000},
            # Legendary characters (3%) - rare to get!
            {"name": "Goku", "anime": "Dragon Ball", "gender": "Male", "favorites": 80000},
            {"name": "Naruto Uzumaki", "anime": "Naruto", "gender": "Male", "favorites": 90000},
            {"name": "Luffy", "anime": "One Piece", "gender": "Male", "favorites": 85000},
            {"name": "Anya Forger", "anime": "Spy x Family", "gender": "Female", "favorites": 100000},
            {"name": "Mikasa Ackerman", "anime": "Attack on Titan", "gender": "Female", "favorites": 75000},
        ]
        
        # Assign rarity using the realistic distribution
        fallback_chars = []
        for char in fallback_pool:
            char_copy = char.copy()
            char_copy["rarity"] = self.get_gacha_rarity(char.get("favorites", 0))
            fallback_chars.append(char_copy)
        
        # Filter fallbacks by gender if needed
        if gender_filter:
            fallback_chars = [c for c in fallback_chars if c["gender"] == gender_filter]
        
        while len(characters) < count:
            fallback = random.choice(fallback_chars).copy()
            fallback["id"] = random.randint(100000, 999999)
            characters.append(fallback)
        
        return characters[:count]
    
    def generate_uid(self) -> str:
        """Generate a unique ID for a character instance (like Pokétwo)."""
        import uuid
        # Format: 8 char hex string for readability
        return uuid.uuid4().hex[:8].upper()
    
    def calculate_release_value(self, favorites: int, rarity: str) -> int:
        """Calculate stella points for releasing a character based on rarity and favorites (likeness) with random seed."""
        import random
        
        # Enhanced base values for each rarity tier
        base_values = {
            "common": 50,      # Increased from 10
            "uncommon": 150,   # Increased from 25  
            "rare": 400,        # Increased from 75
            "epic": 1200,       # Increased from 200
            "legendary": 3000   # Increased from 500
        }
        base = base_values.get(rarity, 50)
        
        # Enhanced favorites bonus with exponential scaling
        # 1 point per 10 favorites (instead of 100), with higher multipliers for popular characters
        if favorites == 0:
            favorites_bonus = 0
        elif favorites <= 50:
            favorites_bonus = favorites * 1  # 1 point per favorite
        elif favorites <= 200:
            favorites_bonus = 50 + (favorites - 50) * 2  # 2 points per favorite after 50
        elif favorites <= 1000:
            favorites_bonus = 350 + (favorites - 200) * 3  # 3 points per favorite after 200
        elif favorites <= 5000:
            favorites_bonus = 2150 + (favorites - 1000) * 5  # 5 points per favorite after 1000
        else:
            # Ultra popular characters get massive bonuses
            favorites_bonus = 17150 + (favorites - 5000) * 10  # 10 points per favorite after 5000
        
        # Rarity multiplier on favorites bonus (rarer characters get more value from popularity)
        rarity_multipliers = {
            "common": 1.0,
            "uncommon": 1.2,
            "rare": 1.5,
            "epic": 2.0,
            "legendary": 3.0
        }
        rarity_mult = rarity_multipliers.get(rarity, 1.0)
        favorites_bonus = int(favorites_bonus * rarity_mult)
        
        # Add random seed factor for variability (±20% of base value)
        # Create a deterministic seed based on character properties for consistency per character
        seed_input = f"{rarity}_{favorites}_{base}"
        random.seed(hash(seed_input) % (2**32))  # Use hash to create seed
        
        random_factor = random.uniform(0.8, 1.2)  # ±20% variation
        random_bonus = int(base * (random_factor - 1.0))  # Convert to bonus/penalty
        
        # Reset random seed to avoid affecting other random operations
        random.seed()
        
        # Minimum and maximum caps
        min_value = max(base, 100)  # Minimum 100 points
        max_value = 50000  # Maximum 50,000 points
        
        total_value = base + favorites_bonus + random_bonus
        total_value = max(min_value, min(total_value, max_value))
        
        return total_value
    
    async def add_character_to_inventory(self, user_id: str, guild_id: str, character: dict) -> str:
        """Add a character to user's inventory in MongoDB. Returns the UID."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            uid = self.generate_uid()
            favorites = character.get("favorites", 0)
            
            char_data = {
                "uid": uid,
                "id": character.get("id", random.randint(1, 999999)),
                "name": character.get("name"),
                "anime": character.get("anime"),
                "image_url": character.get("image_url"),
                "rarity": character.get("rarity", "common"),
                "gender": character.get("gender", "Unknown"),
                "favorites": favorites,
                "claimed_at": datetime.now(timezone.utc).isoformat(),
                "cover_unlocked": False,  # Unlock with likes/interactions
                "cover_progress": 0,  # Progress toward unlocking cover art
            }
            
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$push": {f"members.{user_id}.gacha_inventory": char_data}},
                upsert=True
            )
            return uid
        except Exception as e:
            logger.error(f"Error adding character to inventory: {e}")
            return None
    
    async def is_character_owned_in_server(self, guild_id: str, char_name: str, char_id: int = None) -> tuple:
        """Check if a character is already owned by someone in the server.
        Returns (is_owned: bool, owner_id: str or None)
        """
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            server_data = await server_col.find_one({"guild_id": guild_id})
            if not server_data or "members" not in server_data:
                return (False, None)
            
            char_name_lower = char_name.lower() if char_name else ""
            
            for user_id, member_data in server_data.get("members", {}).items():
                inventory = member_data.get("gacha_inventory", [])
                for owned_char in inventory:
                    if (owned_char.get("id") == char_id or 
                        (owned_char.get("name", "").lower() == char_name_lower)):
                        return (True, user_id)
            
            return (False, None)
        except Exception as e:
            logger.error(f"Error checking character ownership: {e}")
            return (False, None)
    
    async def get_character_by_uid(self, guild_id: str, uid: str) -> tuple:
        """Get a character by UID. Returns (owner_id, character_data) or (None, None)."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            server_data = await server_col.find_one({"guild_id": guild_id})
            if not server_data or "members" not in server_data:
                return (None, None)
            
            for user_id, member_data in server_data.get("members", {}).items():
                inventory = member_data.get("gacha_inventory", [])
                for char in inventory:
                    if char.get("uid", "").upper() == uid.upper():
                        return (user_id, char)
            
            return (None, None)
        except Exception as e:
            logger.error(f"Error getting character by UID: {e}")
            return (None, None)
    
    async def remove_character_from_inventory(self, user_id: str, guild_id: str, uid: str) -> dict:
        """Remove a character from inventory by UID. Returns the removed character or None."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            # First get the character data
            server_data = await server_col.find_one({"guild_id": guild_id})
            if not server_data:
                return None
            
            member_data = server_data.get("members", {}).get(user_id, {})
            inventory = member_data.get("gacha_inventory", [])
            
            char_to_remove = None
            for char in inventory:
                if char.get("uid", "").upper() == uid.upper():
                    char_to_remove = char
                    break
            
            if not char_to_remove:
                return None
            
            # Remove from inventory
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$pull": {f"members.{user_id}.gacha_inventory": {"uid": char_to_remove["uid"]}}}
            )
            
            return char_to_remove
        except Exception as e:
            logger.error(f"Error removing character: {e}")
            return None
    
    async def get_user_inventory(self, user_id: str, guild_id: str) -> list:
        """Get user's character inventory from MongoDB."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            server_data = await server_col.find_one({"guild_id": guild_id})
            if server_data and "members" in server_data:
                member_data = server_data["members"].get(user_id, {})
                return member_data.get("gacha_inventory", [])
        except Exception as e:
            logger.error(f"Error fetching inventory: {e}")
        
        return []
    
    async def check_character_ownership(self, guild: discord.Guild, characters: list) -> dict:
        """Check if any characters are already owned by members in this server.
        
        Returns dict mapping character index to owner info (user_id, username, avatar_url)
        """
        ownership = {}
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            guild_id = str(guild.id)
            
            server_data = await server_col.find_one({"guild_id": guild_id})
            if not server_data or "members" not in server_data:
                return ownership
            
            # Check each character against all member inventories
            for i, char in enumerate(characters):
                char_name = char.get("name", "").lower()
                char_id = char.get("id")
                
                for user_id, member_data in server_data.get("members", {}).items():
                    inventory = member_data.get("gacha_inventory", [])
                    
                    for owned_char in inventory:
                        # Match by ID or name
                        if (owned_char.get("id") == char_id or 
                            owned_char.get("name", "").lower() == char_name):
                            
                            # Try to get the member info
                            try:
                                member = guild.get_member(int(user_id))
                                if member:
                                    ownership[i] = {
                                        "user_id": user_id,
                                        "username": member.display_name,
                                        "avatar_url": member.display_avatar.url if member.display_avatar else None
                                    }
                                    break
                            except:
                                pass
                    
                    if i in ownership:
                        break
                        
        except Exception as e:
            logger.debug(f"Error checking ownership: {e}")
        
        return ownership
    
    @commands.group(name="game", aliases=["games"], invoke_without_command=True)
    async def game(self, ctx):
        """🎮 Play mini-games to win stella points!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Get user character for bonus display
        character = await self.get_user_character(user_id, guild_id)
        balance = await self.quest_data.get_balance(user_id, guild_id)
        
        embed = discord.Embed(
            title="🎮 Anya's Game Corner",
            description=f"*Waku waku!* Play games to win stella points!\n\n"
                        f"💰 **Balance:** {balance:,} stella points",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        
        if character:
            embed.description += f"\n🌟 **Character:** {character}"
        
        # Gambling Games
        embed.add_field(
            name="🎰 **GAMBLING**",
            value=f"`{ctx.prefix}slots <bet>` - Slot Machine\n"
                  f"`{ctx.prefix}coinflip <bet> <h/t>` - Flip a Coin\n"
                  f"`{ctx.prefix}guess <bet>` - Number Guess",
            inline=False
        )
        
        # Card Games
        embed.add_field(
            name="🃏 **CARD DRAWS**",
            value=f"`{ctx.prefix}game pokemon` - 100 pts\n"
                  f"`{ctx.prefix}game anime` - 100 pts",
            inline=True
        )
        
        # Classic Games
        embed.add_field(
            name="**CLASSIC**",
            value=f"`{ctx.prefix}hangman` - Word Game\n"
                  f"`{ctx.prefix}wordle` - 5-Letter Puzzle",
            inline=True
        )
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        # Grounded/Economy Games
        embed.add_field(
            name="💼 **GROUNDED** (Spy x Family)",
            value=f"`{ctx.prefix}work` - Earn points\n"
                  f"`{ctx.prefix}job` - Risky mission\n"
                  f"`{ctx.prefix}rob @user` - Steal points\n"
                  f"`{ctx.prefix}claim` - Daily reward",
            inline=False
        )
        
        embed.set_footer(text="💡 Get a character from .shop for bonuses!")
        await ctx.reply(embed=embed, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # GAMBLING GAMES
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="slots", aliases=["slot", "spin"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def slots_command(self, ctx, bet: int = 50):
        """🎰 Spin the slot machine! Match symbols to win big."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check timer (cooldown + daily limit)
        timer_error = await self.check_timer(ctx, "slots")
        if timer_error:
            return await ctx.reply(timer_error, mention_author=False)
        
        # Validate bet
        if bet < 10:
            return await ctx.reply("❌ Minimum bet is **10** stella points!", mention_author=False)
        if bet > 10000:
            return await ctx.reply("❌ Maximum bet is **10,000** stella points!", mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ You need **{bet:,}** but only have **{balance:,}** stella points!", mention_author=False)
        
        # Set command cooldown and increment plays
        await self.set_cooldown(user_id, "slots_command")
        await self.increment_plays(user_id, guild_id, "slots")
        
        await self._run_slot_machine(ctx.channel, ctx.author, bet)
    
    def _generate_slot_gif(self, results: list) -> io.BytesIO:
        """Generate hyper-realistic slot machine GIF with physics-based animation"""
        import math
        
        frames = []
        durations = []
        all_symbols = list(SLOT_SYMBOLS.keys())
        num_symbols = len(all_symbols)
        
        # Determine result type for outline colors
        is_jackpot = results[0] == results[1] == results[2]
        is_two_match = (results[0] == results[1] or results[1] == results[2] or results[0] == results[2]) and not is_jackpot
        
        # Dimensions
        width, height = 360, 140
        reel_width = 80
        reel_height = 90
        symbol_height = 45  # Height per symbol in the reel strip
        reel_y = 25
        reel_positions = [40, 140, 240]
        
        # Colors
        bg_dark = (15, 12, 20)
        frame_gold = (200, 170, 60)
        frame_shadow = (90, 75, 35)
        reel_bg = (5, 5, 10)
        
        # Result colors
        if is_jackpot:
            result_color = (255, 215, 0)
            result_glow = (255, 255, 120)
        elif is_two_match:
            result_color = (50, 220, 50)
            result_glow = (120, 255, 120)
        else:
            result_color = (200, 50, 50)
            result_glow = (255, 100, 100)
        
        # Load font with emoji support
        try:
            font = _load_emoji_font(28)
        except:
            font = ImageFont.load_default()
        
        # Physics: each reel has its own spin state
        # Reel positions are in "symbol units" (0 = first symbol at center)
        # We'll track continuous position and velocity for each reel
        
        # Find the index of each result symbol
        result_indices = []
        for r in results:
            result_indices.append(all_symbols.index(r))
        
        # Animation parameters - smoother physics
        initial_velocity = 18.0  # symbols per second at start
        
        # Each reel stops at different times
        reel_stop_times = [1.6, 2.6, 3.8]  # seconds
        
        # Higher fps for smoother animation
        fps = 30
        total_duration = 5.0  # seconds
        total_frames = int(total_duration * fps)
        
        # Initialize reel states - track target position for smooth landing
        reel_positions_anim = [0.0, 0.0, 0.0]  # Current position in symbol units
        reel_velocities = [initial_velocity, initial_velocity, initial_velocity]
        reel_stopped = [False, False, False]
        reel_landing = [False, False, False]  # True when easing into final position
        
        for frame_idx in range(total_frames):
            current_time = frame_idx / fps
            
            img = Image.new('RGB', (width, height), bg_dark)
            draw = ImageDraw.Draw(img)
            
            # Draw machine frame with 3D effect
            # Outer shadow
            draw.rounded_rectangle([3, 3, width-1, height-1], radius=15, fill=frame_shadow)
            # Main frame
            draw.rounded_rectangle([0, 0, width-4, height-4], radius=15, fill=bg_dark, outline=frame_gold, width=4)
            # Inner highlight
            draw.rounded_rectangle([8, 8, width-12, height-12], radius=12, outline=(40, 35, 50), width=1)
            
            # Update physics for each reel
            for reel_idx in range(3):
                stop_time = reel_stop_times[reel_idx]
                target_pos = result_indices[reel_idx]
                
                if reel_stopped[reel_idx]:
                    # Already stopped - stay at target
                    reel_positions_anim[reel_idx] = target_pos
                    reel_velocities[reel_idx] = 0
                elif current_time >= stop_time - 0.4 and not reel_landing[reel_idx]:
                    # Start landing phase - smooth ease to target
                    reel_landing[reel_idx] = True
                
                if reel_landing[reel_idx] and not reel_stopped[reel_idx]:
                    # Smooth interpolation to target position
                    landing_progress = (current_time - (stop_time - 0.4)) / 0.4
                    landing_progress = min(1.0, max(0.0, landing_progress))
                    
                    # Smooth step function (ease in-out)
                    smooth = landing_progress * landing_progress * (3 - 2 * landing_progress)
                    
                    # Get current spinning position
                    spin_pos = reel_positions_anim[reel_idx]
                    
                    # Interpolate toward target
                    # Make sure we approach from the right direction (wrapping)
                    diff = target_pos - (spin_pos % num_symbols)
                    if diff < -num_symbols / 2:
                        diff += num_symbols
                    elif diff > num_symbols / 2:
                        diff -= num_symbols
                    
                    reel_positions_anim[reel_idx] = spin_pos + diff * smooth * 0.15
                    reel_velocities[reel_idx] = initial_velocity * (1 - smooth) * 0.3
                    
                    if landing_progress >= 1.0:
                        reel_stopped[reel_idx] = True
                        reel_positions_anim[reel_idx] = target_pos
                        reel_velocities[reel_idx] = 0
                        
                elif not reel_landing[reel_idx]:
                    # Normal spinning with gradual slowdown
                    time_to_landing = (stop_time - 0.4) - current_time
                    if time_to_landing < 0.8:
                        # Gradual slowdown before landing
                        ease = time_to_landing / 0.8
                        ease = 0.4 + ease * 0.6  # Never go below 40% speed
                        current_vel = initial_velocity * ease
                    else:
                        current_vel = initial_velocity
                    
                    reel_velocities[reel_idx] = current_vel
                    reel_positions_anim[reel_idx] += current_vel / fps
                    
                    # Wrap position
                    reel_positions_anim[reel_idx] = reel_positions_anim[reel_idx] % num_symbols
            
            # Draw each reel
            for reel_idx, x in enumerate(reel_positions):
                # Reel background with depth
                draw.rounded_rectangle([x-3, reel_y-3, x + reel_width+3, reel_y + reel_height+3], 
                                       radius=8, fill=(3, 3, 6))
                draw.rounded_rectangle([x, reel_y, x + reel_width, reel_y + reel_height], 
                                       radius=6, fill=reel_bg)
                
                # Create a clipping region for the reel
                reel_center_y = reel_y + reel_height // 2
                
                # Get current position
                pos = reel_positions_anim[reel_idx]
                is_stopped = reel_stopped[reel_idx]
                velocity = reel_velocities[reel_idx]
                
                # Draw 3 symbols: above, center, below
                for offset in [-1, 0, 1]:
                    symbol_idx = int(pos + offset) % num_symbols
                    symbol = all_symbols[symbol_idx]
                    
                    # Calculate y position based on fractional position
                    frac = pos - int(pos)
                    symbol_y = reel_center_y + (offset - frac) * symbol_height
                    
                    # Only draw if visible in reel window
                    if reel_y - symbol_height < symbol_y < reel_y + reel_height + symbol_height:
                        symbol_color = SLOT_SYMBOL_COLORS.get(symbol, (255, 255, 255))
                        
                        # Motion blur effect when spinning fast
                        if velocity > 5 and not is_stopped:
                            # Fade based on speed
                            fade = max(0.3, 1.0 - (velocity / initial_velocity) * 0.6)
                            symbol_color = tuple(int(c * fade) for c in symbol_color)
                        
                        # Center symbol in reel
                        bbox = draw.textbbox((0, 0), symbol, font=font)
                        text_w = bbox[2] - bbox[0]
                        text_x = x + (reel_width - text_w) // 2
                        text_y = int(symbol_y - symbol_height // 2 + 5)
                        
                        # Only draw center symbol with full opacity, others faded
                        if offset == 0 and is_stopped:
                            # Glow effect for stopped center symbol
                            glow = tuple(min(255, int(c * 0.4)) for c in symbol_color)
                            for glow_offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                draw.text((text_x + glow_offset[0], text_y + glow_offset[1]), 
                                         symbol, font=font, fill=glow)
                        
                        draw.text((text_x, text_y), symbol, font=font, fill=symbol_color)
                
                # Reel window overlay - gradient fade at top and bottom
                for i in range(12):
                    alpha = int((12 - i) / 12 * 200)
                    fade_color = (bg_dark[0], bg_dark[1], bg_dark[2])
                    # Top fade
                    draw.line([(x, reel_y + i), (x + reel_width, reel_y + i)], 
                             fill=tuple(int(c * (1 - i/12)) for c in fade_color), width=1)
                    # Bottom fade
                    draw.line([(x, reel_y + reel_height - i), (x + reel_width, reel_y + reel_height - i)], 
                             fill=tuple(int(c * (1 - i/12)) for c in fade_color), width=1)
                
                # Result highlight when stopped
                if is_stopped:
                    draw.rounded_rectangle([x-1, reel_y-1, x + reel_width+1, reel_y + reel_height+1], 
                                           radius=7, outline=result_color, width=2)
            
            # Center payline indicator
            line_y = reel_y + reel_height // 2
            # Left arrow
            draw.polygon([(32, line_y), (18, line_y - 10), (18, line_y + 10)], fill=frame_gold)
            # Right arrow
            draw.polygon([(width - 32, line_y), (width - 18, line_y - 10), (width - 18, line_y + 10)], fill=frame_gold)
            # Payline
            draw.line([(35, line_y), (width - 35, line_y)], fill=(frame_gold[0]//3, frame_gold[1]//3, frame_gold[2]//3), width=1)
            
            frames.append(img)
            
            # Consistent frame timing for smooth playback (33ms = ~30fps)
            durations.append(33)
        
        # Add final hold frames to show result
        for _ in range(12):
            frames.append(frames[-1])
            durations.append(120)
        
        # Save GIF
        gif_buffer = io.BytesIO()
        frames[0].save(
            gif_buffer,
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0  # Loop forever so user can watch again
        )
        gif_buffer.seek(0)
        return gif_buffer
    
    async def _run_slot_machine(self, channel, user, bet: int):
        """Run the slot machine game with anticipation-building progressive reveals"""
        guild_id = str(channel.guild.id)
        user_id = str(user.id)
        
        # Get balance before deducting
        balance = await self.quest_data.get_balance(user_id, guild_id)
        
        # Deduct bet
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Pre-generate final results
        results = [self.get_slot_symbol() for _ in range(3)]
        
        # Generate the GIF in background while spinning
        gif_task = asyncio.get_event_loop().run_in_executor(
            None, self._generate_slot_gif, results
        )
        
        # Simple spinning message
        spin_embed = discord.Embed(
            title="🎰 Slot Machine",
            description=f"**{user.display_name}** is spinning...\n💰 Bet: **{bet:,}** pts",
            color=discord.Color.blue()
        )
        spin_msg = await channel.send(embed=spin_embed)
        
        # Wait for gif to be ready
        gif_buffer = await gif_task
        
        # Determine outcome
        winnings = 0
        if results[0] == results[1] == results[2]:
            # JACKPOT!
            multiplier = SLOT_SYMBOLS[results[0]]["multiplier"]
            winnings = bet * multiplier
            final_title = "🎰 Jackpot!"
            final_color = discord.Color.gold()
        elif results[0] == results[1] or results[1] == results[2] or results[0] == results[2]:
            # Two match
            winnings = int(bet * 1.5)
            final_title = "🎰 Double Match!"
            final_color = discord.Color.green()
        else:
            final_title = "🎰 No Match"
            final_color = discord.Color.red()
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        # Create clean final embed with GIF
        final_embed = discord.Embed(
            title=final_title,
            #description=f"{results[0]} {results[1]} {results[2]}",
            color=final_color
        )
        
        if profit > 0:
            final_embed.add_field(name="Won", value=f"+{profit:,} pts", inline=True)
        else:
            final_embed.add_field(name="Lost", value=f"{abs(profit):,} pts", inline=True)
        
        final_embed.add_field(name="Balance", value=f"{new_balance:,} pts", inline=True)
        final_embed.set_image(url="attachment://slots.gif")
        
        # Create view with Play Again button
        view = SlotMachineView(self, user_id, guild_id, bet, results)
        
        file = discord.File(gif_buffer, filename="slots.gif")
        await spin_msg.edit(embed=final_embed, attachments=[file], view=view)
    
    def parse_bet(self, bet_str: str) -> int:
        """Parse a bet string that may contain commas (e.g., '5,000' -> 5000)."""
        if bet_str is None:
            return 50
        # Remove commas and convert to int
        cleaned = str(bet_str).replace(",", "").replace(" ", "")
        return int(cleaned)
    
    @commands.command(name="coinflip", aliases=["cf", "flip"])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def coinflip_command(self, ctx, bet: str = "50", choice: str = None):
        """🪙 Flip a coin! Call heads or tails to double your bet."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if choice is None:
            embed = discord.Embed(
                title="🪙 Coin Flip",
                description=f"**How to play:**\n"
                           f"`{ctx.prefix}coinflip <bet> <heads/tails>`\n\n"
                           f"Call it right and **double** your bet!\n\n"
                           f"**Example:** `{ctx.prefix}coinflip 100 heads`",
                color=discord.Color.gold()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Parse bet (handles commas like "5,000")
        try:
            bet = self.parse_bet(bet)
        except ValueError:
            return await ctx.reply("❌ Invalid bet amount! Use numbers like `100` or `5,000`", mention_author=False)
        
        # Normalize choice
        choice = choice.lower()
        if choice in ["h", "head", "heads"]:
            choice = "heads"
        elif choice in ["t", "tail", "tails"]:
            choice = "tails"
        else:
            return await ctx.reply("❌ Choose **heads** or **tails**!", mention_author=False)
        
        # Check timer (cooldown + daily limit)
        timer_error = await self.check_timer(ctx, "coinflip")
        if timer_error:
            return await ctx.reply(timer_error, mention_author=False)
        
        # Validate bet
        if bet < 10:
            return await ctx.reply("❌ Minimum bet is **10** stella points!", mention_author=False)
        if bet > 5000:
            return await ctx.reply("❌ Maximum bet is **5,000** stella points!", mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ You need **{bet:,}** but only have **{balance:,}** stella points!", mention_author=False)
        
        # Set command cooldown, deduct bet and increment plays
        await self.set_cooldown(user_id, "coinflip_command")
        await self.increment_plays(user_id, guild_id, "coinflip")
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Flip!
        result = random.choice(["heads", "tails"])
        won = result == choice
        
        # Send spinning message first (no GIF attachment to avoid lingering files)
        spin_embed = discord.Embed(
            title="🪙 Flipping...",
            description=f"You called **{choice.upper()}**!",
            color=discord.Color.gold()
        )
        msg = await ctx.reply(embed=spin_embed, mention_author=False)
        
        # Wait for animation
        await asyncio.sleep(1.2)
        
        if won:
            winnings = bet * 2
            await self.quest_data.add_balance(user_id, guild_id, winnings)
            profit = bet
            title = "🎉 You Won!"
            color = discord.Color.green()
            #result_emoji = "" if result == "heads" else "🦅"
        else:
            winnings = 0
            profit = -bet
            title = "💸 You Lost!"
            color = discord.Color.red()
            #result_emoji = "👑" if result == "heads" else "🦅"
        
        new_balance = balance - bet + winnings
        
        embed = discord.Embed(
            title=title,
            description=f"The coin landed on **{result.upper()}**!\n"
                       f"You called **{choice}**.",
            color=color
        )
        
        if profit > 0:
            embed.add_field(name="💰 Won", value=f"+**{profit:,}** pts", inline=True)
        else:
            embed.add_field(name="📉 Lost", value=f"**{profit:,}** pts", inline=True)
        
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        # Add Double or Nothing for winners
        if won:
            view = DoubleOrNothingView(self, user_id, guild_id, profit)
            embed.set_footer(text="Double your winnings or cash out!")
            await msg.edit(embed=embed, view=view, attachments=[])
        else:
            await msg.edit(embed=embed, attachments=[])
    
    @commands.command(name="dice", aliases=["roll", "d6"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def dice_command(self, ctx, bet: str = "50", guess: int = None):
        """🎲 Roll the dice! Guess 1-6 to win big."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if guess is None:
            embed = discord.Embed(
                title="🎲 Dice Game",
                description=f"**How to play:**\n"
                           f"`{ctx.prefix}dice <bet> <guess>`\n\n"
                           f"Guess the exact number for **5x** your bet!\n"
                           f"Off by 1 = **2x** your bet\n\n"
                           f"**Example:** `{ctx.prefix}dice 100 4`",
                color=discord.Color.blue()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Parse bet
        try:
            bet = self.parse_bet(bet)
        except ValueError:
            return await ctx.reply("❌ Invalid bet amount!", mention_author=False)
        
        if guess < 1 or guess > 6:
            return await ctx.reply("❌ Guess between **1** and **6**!", mention_author=False)
        if bet < 10 or bet > 5000:
            return await ctx.reply("❌ Bet between **10** and **5,000** pts!", mention_author=False)
        
        # Check timer (cooldown + daily limit)
        timer_error = await self.check_timer(ctx, "dice")
        if timer_error:
            return await ctx.reply(timer_error, mention_author=False)
        
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ Need **{bet:,}** but have **{balance:,}** pts!", mention_author=False)
        
        # Set command cooldown, deduct bet and increment plays
        await self.set_cooldown(user_id, "dice_command")
        await self.increment_plays(user_id, guild_id, "dice")
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Roll!
        roll = random.randint(1, 6)
        
        # Generate dice GIF
        gif_buffer = generate_dice_gif(roll)
        file = discord.File(gif_buffer, filename="dice.gif")
        
        # Send rolling message first
        roll_embed = discord.Embed(
            title="🎲 Rolling...",
            description=f"You guessed **{guess}**!",
            color=discord.Color.blue()
        )
        roll_embed.set_image(url="attachment://dice.gif")
        msg = await ctx.reply(embed=roll_embed, file=file, mention_author=False)
        
        # Wait for animation
        await asyncio.sleep(1.3)
        
        # Calculate winnings
        diff = abs(roll - guess)
        if diff == 0:
            winnings = bet * 5
            result = "🎯 **PERFECT!**"
            color = discord.Color.gold()
        elif diff == 1:
            winnings = bet * 2
            result = "✨ **Close!**"
            color = discord.Color.green()
        else:
            winnings = 0
            result = "💨 **Miss!**"
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        
        dice_faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
        
        embed = discord.Embed(
            title=result,
            description=f"{dice_faces[roll]} Rolled **{roll}** | You guessed **{guess}**",
            color=color
        )
        
        if winnings > 0:
            embed.add_field(name="Won", value=f"+**{winnings:,}** pts", inline=True)
        else:
            embed.add_field(name="Lost", value=f"**-{bet:,}** pts", inline=True)
        
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await msg.edit(embed=embed, attachments=[])
    
    @commands.command(name="guess", aliases=["number", "guessnumber"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def guess_command(self, ctx, bet: int = 50):
        """🔢 Guess a number 1-100! Closer guesses win more."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check timer (cooldown + daily limit)
        timer_error = await self.check_timer(ctx, "guess")
        if timer_error:
            return await ctx.reply(timer_error, mention_author=False)
        
        # Validate bet
        if bet < 20:
            return await ctx.reply("❌ Minimum bet is **20** stella points!", mention_author=False)
        if bet > 5000:
            return await ctx.reply("❌ Maximum bet is **5,000** stella points!", mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ You need **{bet:,}** but only have **{balance:,}** stella points!", mention_author=False)
        
        # Set command cooldown and increment plays
        await self.set_cooldown(user_id, "guess_command")
        await self.increment_plays(user_id, guild_id, "guess")
        
        # Deduct bet upfront - no refunds!
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Generate secret number
        secret = random.randint(1, 100)
        total_attempts = 5
        attempts_left = total_attempts
        guesses_list = []
        
        # Generate initial thermometer
        img_buffer = generate_guess_thermometer([], secret, attempts_left, total_attempts)
        file = discord.File(img_buffer, filename="guess.png")
        
        embed = discord.Embed(
            title="🔢 Number Guessing",
            description=f"Guess a number between **1-100**\nBet: **{bet:,}** pts\nAttempts: **{total_attempts}**",
            color=discord.Color.orange()
        )
        embed.set_image(url="attachment://guess.png")
        msg = await ctx.reply(embed=embed, file=file, mention_author=False)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
        
        perfect_win = False
        while attempts_left > 0:
            try:
                guess_msg = await self.bot.wait_for("message", timeout=45.0, check=check)
                guess = int(guess_msg.content)
                
                if guess < 1 or guess > 100:
                    await ctx.send("Please guess between 1-100!", delete_after=3)
                    continue
                
                guesses_list.append(guess)
                attempts_left -= 1
                diff = abs(secret - guess)
                
                if diff == 0:
                    # Perfect guess!
                    perfect_win = True
                    winnings = bet * 5
                    await self.quest_data.add_balance(user_id, guild_id, winnings)
                    new_balance = balance - bet + winnings
                    
                    # Generate result image
                    img_buffer = generate_guess_result_image(guesses_list, secret, True, winnings - bet)
                    file = discord.File(img_buffer, filename="guess_result.png")
                    
                    embed = discord.Embed(
                        title="🎯 PERFECT!",
                        description=f"You got it in **{len(guesses_list)}** {'guess' if len(guesses_list) == 1 else 'guesses'}!\n"
                                   f"💰 Won: **+{winnings - bet:,}** pts\n💳 Balance: **{new_balance:,}** pts",
                        color=discord.Color.gold()
                    )
                    embed.set_image(url="attachment://guess_result.png")
                    return await msg.edit(embed=embed, attachments=[file])
                
                # Update thermometer with guess
                img_buffer = generate_guess_thermometer(guesses_list, secret, attempts_left, total_attempts)
                file = discord.File(img_buffer, filename="guess.png")
                
                # Temperature hint
                if diff <= 5:
                    temp = "🔥 **HOT!**"
                elif diff <= 15:
                    temp = "🌡️ Warm"
                elif diff <= 30:
                    temp = "☀️ Getting there"
                else:
                    temp = "❄️ Cold"
                
                direction = "⬆️ Higher" if guess < secret else "⬇️ Lower"
                
                embed = discord.Embed(
                    title="🔢 Number Guessing",
                    description=f"Your guess: **{guess}** → {direction}\n{temp}\n\n"
                               f"Attempts left: **{attempts_left}**",
                    color=discord.Color.orange()
                )
                embed.set_image(url="attachment://guess.png")
                await msg.edit(embed=embed, attachments=[file])
                
            except asyncio.TimeoutError:
                break
        
        # Game over - much stricter partial winnings
        if guesses_list:
            closest = min(guesses_list, key=lambda x: abs(x - secret))
            diff = abs(closest - secret)
            
            # More reasonable near-miss rewards
            if diff == 0:
                winnings = bet * 5  # should be caught by perfect path, safe fallback
            elif diff <= 2:
                winnings = bet * 2
            elif diff <= 5:
                winnings = int(bet * 1.5)
            elif diff <= 10:
                winnings = int(bet * 1.25)
            elif diff <= 15:
                winnings = int(bet * 1.1)
            else:
                winnings = 0
        else:
            winnings = 0
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        # Generate result image
        img_buffer = generate_guess_result_image(guesses_list, secret, False, profit)
        file = discord.File(img_buffer, filename="guess_result.png")
        
        embed = discord.Embed(
            title="💀 Game Over" if profit <= 0 else "✅ Close!",
            description=f"The number was **{secret}**\n"
                       f"{'📉 Lost' if profit <= 0 else '💰 Won'}: **{profit:+,}** pts\n"
                       f"💳 Balance: **{new_balance:,}** pts",
            color=discord.Color.green() if profit > 0 else discord.Color.red()
        )
        embed.set_image(url="attachment://guess_result.png")
        await msg.edit(embed=embed, attachments=[file])
    
    # ═══════════════════════════════════════════════════════════════
    # CARD DRAW GAMES (kept from original)
    # ═══════════════════════════════════════════════════════════════
    
    @game.command(name="pokemon", aliases=["poke", "pkm"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pokemon_draw(self, ctx):
        """🃏 Draw a random Pokémon card for 100 points."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cost = 100
        
        # Check timer (cooldown + daily limit)
        timer_error = await self.check_timer(ctx, "pokemon")
        if timer_error:
            embed = discord.Embed(
                title="⏰ Daily Limit Reached!",
                description=timer_error,
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            embed = discord.Embed(
                title="❌ Not Enough Points!",
                description=f"You need **{cost}** stella points but only have **{balance:,}**.\n"
                           f"Complete quests to earn more!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Set command cooldown, deduct cost and increment plays
        await self.set_cooldown(user_id, "pokemon_command")
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        await self.increment_plays(user_id, guild_id, "pokemon")
        
        # Random rarity (gacha-style)
        rarity = self.get_random_rarity()
        rarity_data = RARITY_CONFIG[rarity]
        reward = cost * rarity_data["multiplier"]
        
        # Fetch Pokemon info
        pokemon_id = random.randint(1, 1025)
        pokemon = await self.fetch_pokemon_info(pokemon_id)
        
        # Add reward
        await self.quest_data.add_balance(user_id, guild_id, reward)
        new_balance = balance - cost + reward
        profit = reward - cost
        
        # Generate card image
        if pokemon:
            types_str = " / ".join(pokemon["types"])
            card_buffer = await generate_card_image(
                name=pokemon["name"],
                subtitle=types_str,
                rarity=rarity,
                sprite_url=pokemon["sprite"],
                multiplier=rarity_data["multiplier"],
                card_type="pokemon"
            )
        else:
            card_buffer = await generate_card_image(
                name=f"Mystery #{pokemon_id}",
                subtitle="Unknown Type",
                rarity=rarity,
                multiplier=rarity_data["multiplier"],
                card_type="pokemon"
            )
        
        file = discord.File(card_buffer, filename="pokemon_card.png")
        
        embed = discord.Embed(
            title="🃏 Pokémon Card Draw",
            color=rarity_data["color"]
        )
        embed.set_image(url="attachment://pokemon_card.png")
        
        result_name = "💰 Won" if profit > 0 else "📉 Result"
        embed.add_field(name=result_name, value=f"**{profit:+,}** pts", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await ctx.reply(embed=embed, file=file, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # ANIME GACHA - DRAW COMMANDS (Group)
    # ═══════════════════════════════════════════════════════════════
    
    @commands.group(name="draw", aliases=["d"], invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw(self, ctx):
        """🎴 Draw anime characters! Use `.draw` to pull or `.draw help` for info."""
        await self._execute_draw(ctx, gender_filter=None)
    
    @draw.command(name="waifu", aliases=["w", "female", "girl"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw_waifu(self, ctx):
        """🎴 Draw only female characters (waifus)."""
        await self._execute_draw(ctx, gender_filter="Female")
    
    @draw.command(name="husbando", aliases=["h", "male", "boy"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw_husbando(self, ctx):
        """🎴 Draw only male characters (husbandos)."""
        await self._execute_draw(ctx, gender_filter="Male")
    
    @draw.command(name="collection", aliases=["c", "inv", "inventory"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw_collection(self, ctx, member: discord.Member = None):
        """📦 View your anime character collection."""
        target = member or ctx.author
        guild_id = str(ctx.guild.id)
        user_id = str(target.id)
        
        inventory = await self.get_user_inventory(user_id, guild_id)
        
        if not inventory:
            if target == ctx.author:
                embed = discord.Embed(
                    title="📦 Empty Collection",
                    description=f"You haven't collected any characters yet!\nUse `{ctx.prefix}draw` to start collecting.",
                    color=discord.Color.greyple()
                )
            else:
                embed = discord.Embed(
                    title="📦 Empty Collection",
                    description=f"**{target.display_name}** hasn't collected any characters yet!",
                    color=discord.Color.greyple()
                )
            return await ctx.reply(embed=embed, mention_author=False)
        
        view = InventoryView(self, target, guild_id, inventory, filter_type="all")
        await ctx.reply(embed=view.get_embed(), view=view, mention_author=False)
    
    @draw.command(name="info", aliases=["help", "rates", "?"])
    async def draw_info(self, ctx):
        """📊 Show gacha rates and command help."""
        embed = discord.Embed(
            title="🎴 Anime Gacha - Draw Info",
            description="Collect anime characters from 3 sources!",
            color=discord.Color.gold()
        )
        
        # Commands
        embed.add_field(
            name="Commands",
            value=(
                f"`{ctx.prefix}draw` - Draw 3 random characters\n"
                f"`{ctx.prefix}draw waifu` - Draw female only\n"
                f"`{ctx.prefix}draw husbando` - Draw male only\n"
                f"`{ctx.prefix}draw collection` - View your collection\n"
                f"`{ctx.prefix}draw view <UID>` - Show off a character\n"
                f"`{ctx.prefix}draw release <UID>` - Sell for pts\n"
                f"`{ctx.prefix}draw trade @user <UID>` - Trade"
            ),
            inline=False
        )
        
        # Rates
        embed.add_field(
            name="⭐ Rarity Rates",
            value=(
                "⚪ **Common** (1★) - 50%\n"
                "🟢 **Uncommon** (2★) - 25%\n"
                "🔵 **Rare** (3★) - 15%\n"
                "🟣 **Epic** (4★) - 7%\n"
                "🌟 **Legendary** (5★) - 3%"
            ),
            inline=True
        )
        
        # Cost info
        gacha_config = get_timer_config("gacha")
        cooldown_minutes = gacha_config['cooldown'] // 60
        embed.add_field(
            name="Cost & Limits",
            value=f"**{GACHA_COST}** pts per draw\n**{gacha_config['max_uses']}** draws, then {cooldown_minutes} min cooldown",
            inline=True
        )
        
        embed.set_footer(text="Rarity is based on character popularity (favorites count)")
        await ctx.reply(embed=embed, mention_author=False)
    
    @draw.command(name="view", aliases=["show", "display", "v"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def draw_view(self, ctx, uid: str = None):
        """👁️ View and show off a character by UID."""
        if not uid:
            return await ctx.reply(f"Usage: `{ctx.prefix}draw view <UID>`\nFind UIDs in your collection!", mention_author=False)
        
        guild_id = str(ctx.guild.id)
        owner_id, char = await self.get_character_by_uid(guild_id, uid)
        
        if not char:
            return await ctx.reply(f"❌ No character found with UID `{uid.upper()}`", mention_author=False)
        
        # Get owner info
        try:
            owner = ctx.guild.get_member(int(owner_id))
            owner_name = owner.display_name if owner else "Unknown"
            owner_avatar = owner.display_avatar.url if owner else None
        except:
            owner_name = "Unknown"
            owner_avatar = None
        
        rarity = char.get("rarity", "common")
        rarity_data = GACHA_RARITY_TIERS.get(rarity, GACHA_RARITY_TIERS["common"])
        favorites = char.get("favorites", 0)
        
        # Calculate cover unlock progress (based on favorites)
        cover_unlocked = char.get("cover_unlocked", False)
        cover_progress = char.get("cover_progress", 0)
        unlock_threshold = max(100, favorites // 10)  # Need 10% of favorites as interactions
        
        # Create a beautiful character description
        description = char.get("about", "")
        if not description:
            description = f"A character from {char.get('anime', 'Unknown')}."
        
        embed = discord.Embed(
            title=f"{rarity_data['stars']} {char['name']}",
            description=f"*{description}*",
            color=rarity_data["color"]
        )
        
        # Character details in a clean format
        details = f"**Series:** {char.get('anime', 'Unknown')}\n"
        details += f"**Gender:** {char.get('gender', 'Unknown')}\n"
        details += f"**Rarity:** {rarity.title()}\n"
        details += f"**Favorites:** {favorites:,}\n"
        details += f"**UID:** `{char.get('uid', uid).upper()}`"
        
        embed.add_field(name="Character Details", value=details, inline=False)
        
        # Owner information
        embed.add_field(name="Owner", value=owner_name, inline=True)
        
        # Cover art status
        if cover_unlocked:
            embed.add_field(name="Cover Art", value="Unlocked", inline=True)
        else:
            progress_pct = min(100, int((cover_progress / unlock_threshold) * 100))
            embed.add_field(name="Cover Art Progress", value=f"{progress_pct}% ({cover_progress}/{unlock_threshold})", inline=True)
        
        # Set character image
        if char.get("image_url"):
            embed.set_image(url=char["image_url"])
        
        if owner_avatar:
            embed.set_thumbnail(url=owner_avatar)
        
        release_value = self.calculate_release_value(favorites, rarity)
        embed.set_footer(text=f"Release value: {release_value} pts")
        
        # Add cover art view button (commented out)
        # view = CharacterCoverArtView(char['uid'], ctx.author.id)
        # await ctx.reply(embed=embed, view=view, mention_author=False)
        await ctx.reply(embed=embed, mention_author=False)

    @draw.command(name="release", aliases=["sell", "remove"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw_release(self, ctx, uid: str = None):
        """💸 Release a character for stella points."""
        if not uid:
            return await ctx.reply(f"Usage: `{ctx.prefix}draw release <UID>`\nFind UIDs in your collection!", mention_author=False)
        
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check ownership
        owner_id, char = await self.get_character_by_uid(guild_id, uid)
        
        if not char:
            return await ctx.reply(f"❌ No character found with UID `{uid.upper()}`", mention_author=False)
        
        if owner_id != user_id:
            return await ctx.reply("❌ You don't own this character!", mention_author=False)
        
        # Calculate release value
        favorites = char.get("favorites", 0)
        rarity = char.get("rarity", "common")
        release_value = self.calculate_release_value(favorites, rarity)
        
        # Remove from inventory
        removed = await self.remove_character_from_inventory(user_id, guild_id, uid)
        
        if not removed:
            return await ctx.reply("❌ Failed to release character.", mention_author=False)
        
        # Add stella points
        await self.quest_data.add_balance(user_id, guild_id, release_value)
        new_balance = await self.quest_data.get_balance(user_id, guild_id)
        
        rarity_data = GACHA_RARITY_TIERS.get(rarity, GACHA_RARITY_TIERS["common"])
        
        embed = discord.Embed(
            title=f"💸 Released {char['name']}",
            description=f"*{char.get('anime', 'Unknown')}*\n\n"
                       f"**Received:** +{release_value:,} pts\n"
                       f"**New Balance:** {new_balance:,} pts",
            color=rarity_data["color"]
        )
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @draw.command(name="trade", aliases=["give", "transfer"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def draw_trade(self, ctx, member: discord.Member = None, uid: str = None):
        """🔄 Trade a character to another user."""
        if not member or not uid:
            return await ctx.reply(f"Usage: `{ctx.prefix}draw trade @user <UID>`", mention_author=False)
        
        if member.id == ctx.author.id:
            return await ctx.reply("❌ You can't trade with yourself!", mention_author=False)
        
        if member.bot:
            return await ctx.reply("❌ You can't trade with bots!", mention_author=False)
        
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        target_id = str(member.id)
        
        # Check ownership
        owner_id, char = await self.get_character_by_uid(guild_id, uid)
        
        if not char:
            return await ctx.reply(f"❌ No character found with UID `{uid.upper()}`", mention_author=False)
        
        if owner_id != user_id:
            return await ctx.reply("❌ You don't own this character!", mention_author=False)
        
        # Check if target already owns this character (by name)
        is_owned, existing_owner = await self.is_character_owned_in_server(
            guild_id, char.get("name"), char.get("id")
        )
        
        # Remove from sender
        removed = await self.remove_character_from_inventory(user_id, guild_id, uid)
        if not removed:
            return await ctx.reply("❌ Failed to transfer character.", mention_author=False)
        
        # Add to receiver with new UID
        new_uid = await self.add_character_to_inventory(target_id, guild_id, char)
        
        rarity_data = GACHA_RARITY_TIERS.get(char.get("rarity", "common"))
        
        embed = discord.Embed(
            title=f"🔄 Trade Complete!",
            description=f"**{char['name']}** transferred to **{member.display_name}**\n\n"
                       f"**New UID:** `{new_uid}`",
            color=rarity_data["color"]
        )
        
        if char.get("image_url"):
            embed.set_thumbnail(url=char["image_url"])
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @draw.command(name="market", aliases=["shop", "marketplace"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def draw_market(self, ctx):
        """🏪 View the global character marketplace."""
        # For now, show coming soon - full marketplace needs more infrastructure
        embed = discord.Embed(
            title="🏪 Character Marketplace",
            description="**Coming Soon!**\n\n"
                       "The global marketplace will allow you to:\n"
                       "• List characters for sale by UID\n"
                       "• Browse and buy characters from others\n"
                       "• Trade items like food and materials\n\n"
                       f"For now, use `{ctx.prefix}draw trade @user <UID>` for direct trades!",
            color=discord.Color.gold()
        )
        await ctx.reply(embed=embed, mention_author=False)
    
    async def _execute_draw(self, ctx, gender_filter: str = None):
        """Core draw logic shared by all draw commands."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cost = GACHA_COST
        
        # Check timer (cooldown + daily limit)
        timer_error = await self.check_timer(ctx, "gacha")
        if timer_error:
            return await ctx.reply(timer_error, mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            return await ctx.reply(f"❌ Need **{cost}** but have **{balance:,}** pts!", mention_author=False)
        
        # Set command cooldown, deduct cost and increment plays
        await self.set_cooldown(user_id, "gacha_command")
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        await self.increment_plays(user_id, guild_id, "gacha")
        
        # Filter text for title
        filter_text = ""
        if gender_filter == "Female":
            filter_text = " ♀️ Waifu"
        elif gender_filter == "Male":
            filter_text = " ♂️ Husbando"
        
        # Fetch characters instantly
        characters = await self.fetch_gacha_characters(GACHA_CARDS_PER_DRAW, gender_filter=gender_filter)
        
        # Check ownership for each character
        ownership_info = await self.check_character_ownership(ctx.guild, characters)
        
        # Generate draw image with ownership info
        img_buffer = await generate_gacha_draw_image(characters, ownership_info=ownership_info)
        file = discord.File(img_buffer, filename="gacha_draw.png")
        
        # Send image directly without embed
        new_balance = balance - cost
        gacha_config = get_timer_config("gacha")
        current_uses = await self.get_current_uses(user_id, guild_id, "gacha")
        draws_left = gacha_config['max_uses'] - current_uses
        # Clean, natural block output for draw summary
        content = (
            "```\n"
            f"{ctx.author.display_name}'s Draw\n"
            f"{new_balance:,} pts | {draws_left} left\n"
            f"Use {ctx.prefix}draw collection to view your collection!\n"
            "```"
        )
        
        # Create claim view and send instantly
        try:
            view = GachaClaimView(self, ctx.author, guild_id, characters)
            msg = await ctx.reply(content=content, file=file, view=view, mention_author=False)
            view.message = msg
        except Exception as e:
            logger.error(f"Error creating GachaClaimView: {e}", exc_info=True)
            # Fallback: send without view if view creation fails
            await ctx.reply(content=content, file=file, mention_author=False)

    # Keep old slots/dice as game subcommands for backwards compatibility
    @game.command(name="slots", hidden=True)
    async def game_slots(self, ctx, bet: int = 50):
        """Redirect to main slots command."""
        await ctx.invoke(self.slots_command, bet=bet)
    
    @game.command(name="dice", aliases=["roll"], hidden=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def dice_game(self, ctx, bet: int = 50, guess: int = None):
        """🎲 Guess the dice roll! Guess 1-6 to play."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if guess is None:
            embed = discord.Embed(
                title="🎲 Dice Game",
                description=f"`{ctx.prefix}game dice <bet> <guess>`\n\n"
                           f"Guess 1-6. Exact = **5x**, Off by 1 = **2x**",
                color=primary_color()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        if guess < 1 or guess > 6:
            return await ctx.reply("❌ Guess between **1** and **6**!", mention_author=False)
        if bet < 10 or bet > 5000:
            return await ctx.reply("❌ Bet between **10** and **5,000** pts!", mention_author=False)
        
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ Need **{bet:,}** but have **{balance:,}** pts!", mention_author=False)
        
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        roll = random.randint(1, 6)
        dice_faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
        
        diff = abs(roll - guess)
        if diff == 0:
            winnings = bet * 5
            result = "**PERFECT!**"
            color = discord.Color.gold()
        elif diff == 1:
            winnings = bet * 2
            result = "**Close!**"
            color = discord.Color.green()
        else:
            winnings = 0
            result = "**Miss!**"
            color = discord.Color.red()
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        embed = discord.Embed(title="🎲 Dice Game", color=color)
        embed.add_field(name="Roll", value=f"{dice_faces[roll]} **{roll}**", inline=True)
        embed.add_field(name="Guess", value=f"**{guess}**", inline=True)
        embed.add_field(name="Result", value=result, inline=False)
        embed.add_field(
            name="Won" if profit > 0 else "Lost",
            value=f"**{profit:+,}** pts",
            inline=True
        )
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await ctx.reply(embed=embed, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # MULTIPLAYER GAMES - HANGMAN
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="hangman", aliases=["hm"])
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def hangman_game(self, ctx):
        """Multiplayer Hangman! Play in DMs, results shown in channel."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check timer (cooldown + daily limit)
        timer_error = await self.check_timer(ctx, "hangman")
        if timer_error:
            return await ctx.reply(timer_error, mention_author=False)
        
        # Set command cooldown for starting a hangman game
        await self.set_cooldown(user_id, "hangman_command")
        await self.increment_plays(user_id, guild_id, "hangman")
        
        guild_id = str(ctx.guild.id)
        game_id = f"{guild_id}_{ctx.channel.id}_hangman_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Get word from API or fallback
        word = None
        try:
            session = await self.get_session()
            async with session.get("https://random-word-api.herokuapp.com/word") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data and len(data[0]) >= 4:
                        word = data[0].upper()
        except:
            pass
        
        if not word:
            fallback = CLASSIC_CONFIG.get("hangman", {}).get("fallback_words", [
                "MISSION", "SECRET", "AGENT", "FORGER", "TWILIGHT", "CIPHER", "PUZZLE", "MYSTERY"
            ])
            word = random.choice(fallback).upper()
        
        # Initialize multiplayer game
        self.active_games[game_id] = {
            "word": word,
            "players": {},
            "channel": ctx.channel,
            "guild_id": guild_id,
            "started": False,
            "game_msg": None
        }
        
        # Generate initial waiting room image
        host_avatar = None
        if ctx.author.avatar:
            async with aiohttp.ClientSession() as session:
                host_avatar = await fetch_avatar_bytes(session, ctx.author.avatar.url)
        
        img_buffer = await generate_waiting_room_image(
            game_name="HANGMAN",
            host_name=ctx.author.display_name,
            host_avatar_bytes=host_avatar,
            players=[],
            max_players=5,
            extra_info=f"{len(word)} letters • 6 lives"
        )
        
        file = discord.File(img_buffer, filename="hangman_lobby.png")
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_image(url="attachment://hangman_lobby.png")
        embed.set_footer(text="Game starts in 30 seconds or when full!")
        
        view = HangmanJoinView(self, game_id, host_user=ctx.author)
        msg = await ctx.reply(embed=embed, file=file, view=view, mention_author=False)
        self.active_games[game_id]["game_msg"] = msg
        
        # Wait for players
        await asyncio.sleep(30)
        
        if game_id in self.active_games:
            game = self.active_games[game_id]
            if len(game["players"]) == 0:
                embed.description = "❌ No players joined! Game cancelled."
                embed.color = discord.Color.red()
                await msg.edit(embed=embed, view=None)
                del self.active_games[game_id]
            else:
                game["started"] = True
                view.stop()
                await self._start_hangman_game(game_id)
    
    async def _start_hangman_game(self, game_id: str):
        """Start the multiplayer hangman game"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        channel = game["channel"]
        failed_users = []
        
        # Send DMs to all players
        for user_id, player_data in game["players"].items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                view = HangmanLetterView(self, game_id, user_id)
                
                word_display = " ".join("_" for _ in game["word"])
                embed = discord.Embed(
                    title="Hangman",
                    description=f"{HANGMAN_STAGES[0]}\n**Word:** `{word_display}`",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Guessed", value="None", inline=True)
                embed.add_field(name="Wrong", value="0/6", inline=True)
                
                dm_msg = await user.send(embed=embed, view=view)
                player_data["dm_msg"] = dm_msg
                player_data["view"] = view
            except discord.Forbidden:
                logger.warning(f"Cannot DM user {user_id} - DMs disabled")
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    failed_users.append(user_obj.mention)
                except:
                    failed_users.append(f"<@{user_id}>")
                player_data["status"] = "failed"
            except Exception as e:
                logger.error(f"Error sending hangman DM to {user_id}: {e}")
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    failed_users.append(user_obj.mention)
                except:
                    failed_users.append(f"<@{user_id}>")
                player_data["status"] = "failed"
        
        # Notify about failed DMs with mentions
        if failed_users:
            try:
                await channel.send(
                    f"⚠️ {' '.join(failed_users)} - Could not send you DMs!\n"
                    f"Please enable DMs from server members to play!",
                    delete_after=15
                )
            except:
                pass
        
        # Update channel message
        await self._update_hangman_leaderboard(game_id)
    
    async def _update_hangman_leaderboard(self, game_id: str):
        """Update the leaderboard in the channel"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        msg = game["game_msg"]
        
        # Build leaderboard
        leaderboard = []
        for user_id, player_data in game["players"].items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                display = player_data["display"]
                wrong = player_data["wrong"]
                status = player_data["status"]
                
                if status == "won":
                    emoji = "🏆"
                elif status == "lost":
                    emoji = "💀"
                else:
                    emoji = "🎮"
                
                lives = "❤️" * (6 - wrong)
                leaderboard.append(f"{emoji} **{user.display_name}** - `{display}` {lives}")
            except:
                pass
        
        embed = discord.Embed(
            title="🕵️ Hangman - Live Results",
            description="\n".join(leaderboard) if leaderboard else "No players",
            color=discord.Color.blue()
        )
        embed.add_field(name="Word Length", value=f"{len(game['word'])} letters", inline=True)
        
        # Check if game is over
        all_done = all(p["status"] != "playing" for p in game["players"].values())
        if all_done:
            winners = [uid for uid, p in game["players"].items() if p["status"] == "won"]
            embed.add_field(name="Game Over!", value=f"Word was: **{game['word']}**", inline=False)
            if winners:
                embed.color = discord.Color.green()
            else:
                embed.color = discord.Color.red()
        
        try:
            await msg.edit(embed=embed)
        except:
            pass
    
    async def _end_hangman_game(self, game_id: str, winner_user_id: str):
        """End the hangman game when someone wins and notify all players"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        channel = game["channel"]
        
        try:
            # Get winner info
            winner = await self.bot.fetch_user(int(winner_user_id))
            winner_name = winner.display_name
            
            # Send notification to channel
            embed = discord.Embed(
                title="🏆 Hangman Game Won!",
                description=f"**{winner_name}** solved the word first!\n\n**Word:** `{game['word']}`\n\nGame ended automatically for all players.",
                color=discord.Color.green()
            )
            await channel.send(embed=embed)
            
            # End game for all remaining players
            for user_id, player_data in game["players"].items():
                if player_data["status"] == "playing":
                    player_data["status"] = "ended"
                    
                    # Update their DM to show game ended
                    try:
                        if player_data.get("dm_msg") and player_data.get("view"):
                            end_embed = discord.Embed(
                                title="🏁 Game Ended",
                                description=f"**{winner_name}** won the game!\n\n**Word was:** `{game['word']}`\n\nBetter luck next time!",
                                color=discord.Color.orange()
                            )
                            await player_data["dm_msg"].edit(embed=end_embed, view=None)
                    except Exception as e:
                        logger.error(f"Error updating DM for user {user_id}: {e}")
            
            # Final leaderboard update
            await self._update_hangman_leaderboard(game_id)
            
        except Exception as e:
            logger.error(f"Error ending hangman game {game_id}: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # MULTIPLAYER GAMES - WORDLE
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="wordle")
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def wordle_game(self, ctx):
        """🟩 Multiplayer Wordle! Play in DMs, results shown in channel."""
        guild_id = str(ctx.guild.id)
        game_id = f"{guild_id}_{ctx.channel.id}_wordle_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Get 5-letter word
        word = None
        try:
            session = await self.get_session()
            async with session.get("https://random-word-api.herokuapp.com/word?length=5") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        word = data[0].upper()
        except:
            pass
        
        if not word:
            fallback = ["AGENT", "CODES", "QUEST", "SWORD", "FLAME", "STORM", "PEACE", "DREAM", "MAGIC", "BRAVE"]
            word = random.choice(fallback)
        
        # Initialize multiplayer game
        self.active_games[game_id] = {
            "word": word,
            "players": {},
            "channel": ctx.channel,
            "guild_id": guild_id,
            "started": False,
            "game_msg": None
        }
        
        # Generate initial waiting room image
        host_avatar = None
        if ctx.author.avatar:
            async with aiohttp.ClientSession() as session:
                host_avatar = await fetch_avatar_bytes(session, ctx.author.avatar.url)
        
        img_buffer = await generate_waiting_room_image(
            game_name="WORDLE",
            host_name=ctx.author.display_name,
            host_avatar_bytes=host_avatar,
            players=[],
            max_players=5,
            extra_info="5-letter word • 6 attempts"
        )
        
        file = discord.File(img_buffer, filename="wordle_lobby.png")
        embed = discord.Embed(color=discord.Color.green())
        embed.set_image(url="attachment://wordle_lobby.png")
        embed.set_footer(text="Game starts in 30 seconds or when full!")
        
        view = WordleJoinView(self, game_id, host_user=ctx.author)
        msg = await ctx.reply(embed=embed, file=file, view=view, mention_author=False)
        self.active_games[game_id]["game_msg"] = msg
        
        # Wait for players
        await asyncio.sleep(30)
        
        if game_id in self.active_games:
            game = self.active_games[game_id]
            if len(game["players"]) == 0:
                embed.description = "❌ No players joined! Game cancelled."
                embed.color = discord.Color.red()
                await msg.edit(embed=embed, view=None)
                del self.active_games[game_id]
            else:
                game["started"] = True
                view.stop()
                await self._start_wordle_game(game_id)
    
    async def _start_wordle_game(self, game_id: str):
        """Start the multiplayer wordle game"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        channel = game["channel"]
        failed_users = []
        
        # Send DMs to all players with Pillow image
        for user_id, player_data in game["players"].items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                player_data["display_name"] = user.display_name
                view = WordleGuessView(self, game_id, user_id)
                
                # Fetch avatar for the image
                avatar_bytes = None
                try:
                    session = await self.get_session()
                    avatar_url = user.display_avatar.with_size(64).url
                    avatar_bytes = await fetch_avatar_bytes(session, avatar_url)
                    player_data["avatar_bytes"] = avatar_bytes
                except:
                    pass
                
                # Generate empty board image with avatar
                img_buffer = generate_wordle_board_image(
                    [], game["word"],
                    avatar_bytes=avatar_bytes, player_name=user.display_name
                )
                file = discord.File(img_buffer, filename="wordle_board.png")
                
                embed = discord.Embed(
                    title="🟩 Your Wordle Game",
                    description=f"Click **Submit Guess** to enter a 5-letter word!\n"
                               f"❌ Wrong guess = **-15 stella points**",
                    color=discord.Color.green()
                )
                embed.set_image(url="attachment://wordle_board.png")
                embed.add_field(name="Attempts", value="0/6", inline=True)
                
                dm_msg = await user.send(embed=embed, file=file, view=view)
                player_data["dm_msg"] = dm_msg
                player_data["view"] = view
            except discord.Forbidden:
                logger.warning(f"Cannot DM user {user_id} - DMs disabled")
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    failed_users.append(user_obj.mention)
                except:
                    failed_users.append(f"<@{user_id}>")
                player_data["status"] = "failed"
            except Exception as e:
                logger.error(f"Error sending wordle DM to {user_id}: {e}")
                try:
                    user_obj = await self.bot.fetch_user(int(user_id))
                    failed_users.append(user_obj.mention)
                except:
                    failed_users.append(f"<@{user_id}>")
                player_data["status"] = "failed"
        
        # Notify about failed DMs with mentions
        if failed_users:
            try:
                await channel.send(
                    f"⚠️ {' '.join(failed_users)} - Could not send you DMs!\n"
                    f"Please enable DMs from server members to play!",
                    delete_after=15
                )
            except:
                pass
        
        # Update channel message with live image
        await self._update_wordle_leaderboard(game_id)
    
    async def _end_wordle_game(self, game_id: str, winner_id: str):
        """End the wordle game when someone wins - stops for everyone and pings winner"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        channel = game["channel"]
        
        # Mark game as ended
        game["ended"] = True
        
        # Get winner info
        try:
            winner = await self.bot.fetch_user(int(winner_id))
            winner_mention = winner.mention
            winner_name = winner.display_name
        except:
            winner_mention = f"<@{winner_id}>"
            winner_name = "Unknown"
        
        # End game for all other players - delete old DM and send new final one
        for user_id, player_data in game["players"].items():
            if user_id == winner_id:
                continue
            
            if player_data["status"] == "playing":
                player_data["status"] = "ended"
            
            # Delete old DM and send new final embed
            try:
                dm_msg = player_data.get("dm_msg")
                if dm_msg:
                    # Delete the old message
                    try:
                        await dm_msg.delete()
                    except:
                        pass
                    
                    # Send new final message
                    avatar_bytes = player_data.get("avatar_bytes")
                    player_name = player_data.get("display_name", "Player")
                    
                    img_buffer = generate_wordle_board_image(
                        player_data["attempts"], 
                        game["word"], 
                        show_word=True,
                        avatar_bytes=avatar_bytes,
                        player_name=player_name
                    )
                    file = discord.File(img_buffer, filename="wordle_final.png")
                    
                    embed = discord.Embed(
                        title="🏁 Game Over!",
                        description=f"**Word was:** {game['word']}",
                        color=discord.Color.orange()
                    )
                    embed.set_image(url="attachment://wordle_final.png")
                    
                    # Get user to send DM
                    try:
                        user = await self.bot.fetch_user(int(user_id))
                        await user.send(
                            content=f"🏆 **{winner_name}** won the Wordle game!",
                            embed=embed,
                            file=file
                        )
                    except:
                        pass
            except Exception as e:
                logger.error(f"Error updating DM for {user_id}: {e}")
        
        # Also update winner's DM - delete old and send new
        winner_data = game["players"].get(winner_id)
        if winner_data:
            try:
                dm_msg = winner_data.get("dm_msg")
                if dm_msg:
                    try:
                        await dm_msg.delete()
                    except:
                        pass
            except:
                pass
        
        # Generate final live image showing all boards
        players_with_names = {}
        for uid, pdata in game["players"].items():
            players_with_names[uid] = pdata.copy()
            if "display_name" not in players_with_names[uid]:
                try:
                    user = await self.bot.fetch_user(int(uid))
                    players_with_names[uid]["display_name"] = user.display_name
                except:
                    players_with_names[uid]["display_name"] = f"Player"
        
        img_buffer = generate_wordle_live_image(players_with_names, self.bot)
        file = discord.File(img_buffer, filename="wordle_final.png")
        
        # Create final embed
        embed = discord.Embed(
            title="🏆 Wordle Complete!",
            description=f"**Word:** {game['word']}",
            color=discord.Color.gold()
        )
        embed.set_image(url="attachment://wordle_final.png")
        
        # Delete old channel message and send new one with winner ping
        try:
            msg = game["game_msg"]
            try:
                await msg.delete()
            except:
                pass
            
            # Send new final message with winner ping in content
            await channel.send(
                content=f"🎉 Congratulations {winner_mention}! You won the Wordle!",
                embed=embed,
                file=file
            )
        except Exception as e:
            logger.error(f"Error sending wordle final message: {e}")
        
    async def _check_wordle_game_end(self, game_id: str):
        """Check if all players are done and end the game if so"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        
        # Check if all players are done
        all_done = all(p["status"] != "playing" for p in game["players"].values())
        if all_done:
            # Mark game as ended
            game["ended"] = True
            
            # No winner - everyone lost
            channel = game["channel"]
            
            # Delete old DMs and send new final ones for all players
            for user_id, player_data in game["players"].items():
                try:
                    dm_msg = player_data.get("dm_msg")
                    if dm_msg:
                        # Delete old message
                        try:
                            await dm_msg.delete()
                        except:
                            pass
                        
                        # Send new final message
                        avatar_bytes = player_data.get("avatar_bytes")
                        player_name = player_data.get("display_name", "Player")
                        
                        img_buffer = generate_wordle_board_image(
                            player_data["attempts"], 
                            game["word"], 
                            show_word=True,
                            avatar_bytes=avatar_bytes,
                            player_name=player_name
                        )
                        file = discord.File(img_buffer, filename="wordle_final.png")
                        
                        embed = discord.Embed(
                            title="💀 Game Over!",
                            description=f"**Word was:** {game['word']}",
                            color=discord.Color.red()
                        )
                        embed.set_image(url="attachment://wordle_final.png")
                        
                        try:
                            user = await self.bot.fetch_user(int(user_id))
                            await user.send(
                                content="😔 No one won the Wordle game!",
                                embed=embed,
                                file=file
                            )
                        except:
                            pass
                except Exception as e:
                    logger.error(f"Error updating DM for {user_id}: {e}")
            
            # Generate final live image
            players_with_names = {}
            for uid, pdata in game["players"].items():
                players_with_names[uid] = pdata.copy()
                if "display_name" not in players_with_names[uid]:
                    try:
                        user = await self.bot.fetch_user(int(uid))
                        players_with_names[uid]["display_name"] = user.display_name
                    except:
                        players_with_names[uid]["display_name"] = f"Player"
            
            img_buffer = generate_wordle_live_image(players_with_names, self.bot)
            file = discord.File(img_buffer, filename="wordle_final.png")
            
            embed = discord.Embed(
                title="💀 Wordle - Game Over!",
                description=f"**Word was:** {game['word']}",
                color=discord.Color.red()
            )
            embed.set_image(url="attachment://wordle_final.png")
            
            # Delete old channel message and send new one
            try:
                msg = game["game_msg"]
                try:
                    await msg.delete()
                except:
                    pass
                
                # Send new final message with "no one won" in content
                await channel.send(
                    content="😔 **No one won the Wordle!** Better luck next time!",
                    embed=embed,
                    file=file
                )
            except Exception as e:
                logger.error(f"Error sending wordle final message: {e}")
            
            # Clean up
            await asyncio.sleep(60)
            if game_id in self.active_games:
                del self.active_games[game_id]

    async def _update_wordle_leaderboard(self, game_id: str):
        """Update the wordle leaderboard in the channel with live image"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        
        # Don't update if game already ended
        if game.get("ended"):
            return
        
        msg = game["game_msg"]
        
        # Build player data with display names for image
        players_with_names = {}
        for user_id, player_data in game["players"].items():
            players_with_names[user_id] = player_data.copy()
            if "display_name" not in players_with_names[user_id]:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    players_with_names[user_id]["display_name"] = user.display_name
                    # Also store in original for future use
                    player_data["display_name"] = user.display_name
                except:
                    players_with_names[user_id]["display_name"] = f"Player"
        
        # Generate live image showing all boards
        img_buffer = generate_wordle_live_image(players_with_names, self.bot)
        file = discord.File(img_buffer, filename="wordle_live.png")
        
        # Build text leaderboard as well
        leaderboard = []
        for user_id, player_data in game["players"].items():
            try:
                attempts = len(player_data["attempts"])
                status = player_data["status"]
                name = player_data.get("display_name", "Player")
                
                if status == "won":
                    emoji = "🏆"
                elif status == "lost":
                    emoji = "💀"
                elif status == "ended":
                    emoji = "🏁"
                else:
                    emoji = "🎮"
                
                leaderboard.append(f"{emoji} **{name}** - {attempts}/6")
            except:
                pass
        
        embed = discord.Embed(
            title="🟩 Wordle - Live Results",
            description="\n".join(leaderboard) if leaderboard else "Waiting for players...",
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://wordle_live.png")
        embed.set_footer(text="First to guess correctly wins!")
        
        try:
            await msg.edit(embed=embed, attachments=[file])
        except Exception as e:
            logger.error(f"Error updating wordle leaderboard: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # CLASSIC GAMES - WORDLE (OLD - KEEPING FOR COMPATIBILITY)
    # ═══════════════════════════════════════════════════════════════
    
    async def _old_wordle_timeout_handler(self, game, game_key, msg):
        """Handle old wordle timeout"""
        def get_result(guess, answer):
            result = []
            answer_chars = list(answer)
            for i, (g, a) in enumerate(zip(guess, answer)):
                if g == a:
                    result.append("🟩")
                    answer_chars[i] = None
                else:
                    result.append(None)
            for i, g in enumerate(guess):
                if result[i] is None:
                    if g in answer_chars:
                        result[i] = "🟨"
                        answer_chars[answer_chars.index(g)] = None
                    else:
                        result[i] = "⬛"
            return "".join(result)
        
        def build_embed(game, status="playing"):
            if status == "win":
                title = "🎉 You Won!"
                color = discord.Color.green()
            elif status == "lose":
                title = "❌ Game Over!"
                color = discord.Color.red()
            else:
                title = "🟩 Wordle"
                color = discord.Color.blue()
            embed = discord.Embed(title=title, color=color)
            grid = []
            for attempt in game["attempts"]:
                result = get_result(attempt, game["word"])
                grid.append(f"{result} `{attempt}`")
            for _ in range(6 - len(game["attempts"])):
                grid.append("⬜⬜⬜⬜⬜")
            embed.description = "\n".join(grid)
            embed.add_field(name="Attempts", value=f"{len(game['attempts'])}/6", inline=True)
            return embed
        
        embed = build_embed(game, "lose")
        embed.add_field(name="⏰ Timeout!", value=f"The word was **{game['word']}**", inline=False)
        await msg.edit(embed=embed)
        del self.active_games[game_key]
        return

    # ═══════════════════════════════════════════════════════════════
    # GROUNDED GAMES (Spy x Family Themed Economy)
    # ═══════════════════════════════════════════════════════════════
    
    async def get_user_job(self, user_id: str, guild_id: str) -> Optional[str]:
        """Get the user's current job ID."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.current_job": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("current_job")
        except Exception as e:
            logger.error(f"Error getting user job: {e}")
        return None
    
    async def set_user_job(self, user_id: str, guild_id: str, job_id: Optional[str]):
        """Set the user's current job."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            if job_id is None:
                await server_col.update_one(
                    {"guild_id": guild_id},
                    {"$unset": {f"members.{user_id}.current_job": ""}},
                    upsert=True
                )
            else:
                await server_col.update_one(
                    {"guild_id": guild_id},
                    {"$set": {f"members.{user_id}.current_job": job_id}},
                    upsert=True
                )
        except Exception as e:
            logger.error(f"Error setting user job: {e}")
    
    async def get_user_activity(self, user_id: str, guild_id: str) -> int:
        """Get user's activity score (based on messages, commands used, etc.)."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.activity_score": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("activity_score", 0)
        except Exception as e:
            logger.error(f"Error getting activity: {e}")
        return 0
    
    async def increment_activity(self, user_id: str, guild_id: str, amount: int = 1):
        """Increment user's activity score."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$inc": {f"members.{user_id}.activity_score": amount}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error incrementing activity: {e}")
    
    async def get_user_stars(self, user_id: str, guild_id: str) -> int:
        """Get user's total stella stars earned (lifetime earnings)."""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.total_stars_earned": 1}
            )
            if result:
                return result.get("members", {}).get(user_id, {}).get("total_stars_earned", 0)
        except Exception as e:
            logger.error(f"Error getting stars: {e}")
        return 0
    
    def get_job_by_id(self, job_id: str) -> Optional[Dict]:
        """Get job data by ID from config."""
        jobs_config = GROUNDED_CONFIG.get("jobs_system", {}).get("available_jobs", [])
        for job in jobs_config:
            if job.get("id") == job_id:
                return job
        return None
    
    @commands.command(name="jobs", aliases=["job_list", "careers"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def jobs_command(self, ctx):
        """📋 View available jobs and apply for one!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Increment activity for using commands
        await self.increment_activity(user_id, guild_id, 1)
        
        # Get user stats
        current_job_id = await self.get_user_job(user_id, guild_id)
        balance = await self.quest_data.get_balance(user_id, guild_id)
        stars = await self.get_user_stars(user_id, guild_id)
        activity = await self.get_user_activity(user_id, guild_id)
        
        jobs_config = GROUNDED_CONFIG.get("jobs_system", {})
        available_jobs = jobs_config.get("available_jobs", [])
        categories = jobs_config.get("job_categories", {})
        
        # Build embed
        embed = discord.Embed(
            title="📋 Job Board",
            description="Apply for a job to start earning stella points with `.work`!\n\n"
                       f"**Your Stats:**\n"
                       f"⭐ Stars: **{stars:,}**\n"
                       f"📊 Activity: **{activity}**\n"
                       f"💰 Balance: **{balance:,}**",
            color=discord.Color.blue()
        )
        
        if current_job_id:
            current_job = self.get_job_by_id(current_job_id)
            if current_job:
                embed.add_field(
                    name="💼 Current Job",
                    value=f"{current_job['emoji']} **{current_job['title']}**\n"
                          f"Pay: {current_job['pay_range'][0]}-{current_job['pay_range'][1]} pts",
                    inline=False
                )
        
        # Group jobs by category
        jobs_by_category = {}
        for job in available_jobs:
            cat = job.get("category", "entry")
            if cat not in jobs_by_category:
                jobs_by_category[cat] = []
            jobs_by_category[cat].append(job)
        
        for cat_id, cat_jobs in jobs_by_category.items():
            cat_info = categories.get(cat_id, {"name": cat_id.title(), "emoji": "📋"})
            job_lines = []
            for job in cat_jobs:
                reqs = job.get("requirements", {})
                qualified = (
                    stars >= reqs.get("min_stars", 0) and
                    activity >= reqs.get("min_activity", 0) and
                    balance >= reqs.get("min_balance", 0)
                )
                status = "✅" if qualified else "🔒"
                job_lines.append(f"{status} {job['emoji']} **{job['title']}** - {job['pay_range'][0]}-{job['pay_range'][1]} pts")
            
            embed.add_field(
                name=f"{cat_info['emoji']} {cat_info['name']}",
                value="\n".join(job_lines) if job_lines else "No jobs",
                inline=False
            )
        
        # Create view with job select and buttons
        view = JobBoardView(self, ctx.author, guild_id, current_job_id)
        await view.setup()  # Async setup to add the select menu with user stats
        await ctx.reply(embed=embed, view=view, mention_author=False)
    
    @commands.command(name="work")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def work_command(self, ctx):
        """💼 Work at your job to earn stella points!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Increment activity
        await self.increment_activity(user_id, guild_id, 1)
        
        # Check if user has a job
        current_job_id = await self.get_user_job(user_id, guild_id)
        if not current_job_id:
            embed = discord.Embed(
                title="❌ No Job!",
                description="You don't have a job yet!\n\n"
                           f"Use `{ctx.prefix}jobs` to view available jobs and apply for one.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Get job data
        job_data = self.get_job_by_id(current_job_id)
        if not job_data:
            # Job no longer exists, clear it
            await self.set_user_job(user_id, guild_id, None)
            embed = discord.Embed(
                title="❌ Job Not Found!",
                description=f"Your job no longer exists. Use `{ctx.prefix}jobs` to find a new one.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Check cooldown
        cooldown = job_data.get("cooldown", 1800)
        remaining = await self.check_cooldown(user_id, "work", cooldown)
        if remaining:
            return await ctx.reply(f"⏳ You can work again in **{self.format_time(remaining)}**", mention_author=False)
        
        # Show task selection view
        view = WorkTaskView(self, ctx.author, guild_id, job_data)
        
        embed = discord.Embed(
            title=f"{job_data['emoji']} {job_data['title']}",
            description=f"**Choose a task to complete:**\n\n"
                       f"Select a task from the dropdown below to start working!",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="💰 Pay Range",
            value=f"{job_data['pay_range'][0]}-{job_data['pay_range'][1]} pts",
            inline=True
        )
        
        await ctx.reply(embed=embed, view=view, mention_author=False)
    
    
    @commands.command(name="rob", aliases=["steal"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rob_command(self, ctx, target: discord.Member = None):
        """💰 Attempt to steal stella points from another user. High risk!"""
        if target is None:
            return await ctx.reply(f"`{ctx.prefix}rob @user`", mention_author=False)
        
        if target.id == ctx.author.id:
            return await ctx.reply("You can't rob yourself!", mention_author=False)
        
        if target.bot:
            return await ctx.reply("You can't rob bots!", mention_author=False)
        
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        target_id = str(target.id)
        
        # Check cooldown (2 hours)
        remaining = await self.check_cooldown(user_id, "rob", 7200)
        if remaining:
            return await ctx.reply(f"⏳ You can rob again in **{self.format_time(remaining)}**", mention_author=False)
        
        # Check target balance
        target_balance = await self.quest_data.get_balance(target_id, guild_id)
        if target_balance < 500:
            return await ctx.reply(f"{target.display_name} doesn't have enough to steal (min 500 pts)", mention_author=False)
        
        config = GROUNDED_CONFIG.get("rob", {})
        base_success = config.get("success_rate", 0.4)
        steal_min, steal_max = config.get("steal_percent", [10, 30])
        fine_min, fine_max = config.get("fail_fine_percent", [15, 25])
        
        character = await self.get_user_character(user_id, guild_id)
        success_rate = base_success
        
        if character:
            char_bonus = config.get("character_bonuses", {}).get(character, {})
            success_rate += char_bonus.get("success_boost", 0)
        
        await self.set_cooldown(user_id, "rob")
        
        # Get avatar URLs for crime scene image
        robber_avatar_url = ctx.author.display_avatar.with_size(128).url
        victim_avatar_url = target.display_avatar.with_size(128).url
        
        if random.random() < success_rate:
            steal_percent = random.randint(steal_min, steal_max) / 100
            stolen = int(target_balance * steal_percent)
            
            await self.quest_data.add_balance(target_id, guild_id, -stolen)
            await self.quest_data.add_balance(user_id, guild_id, stolen)
            new_balance = await self.quest_data.get_balance(user_id, guild_id)
            
            success_msgs = config.get("success_messages", ["You stole their points!"])
            
            # Generate crime scene image
            img_buffer = await generate_crime_scene_image(
                robber_avatar_url, victim_avatar_url,
                ctx.author.display_name, target.display_name,
                success=True, amount=stolen
            )
            file = discord.File(img_buffer, filename="robbery.png")
            
            embed = discord.Embed(
                title="💰 Robbery Successful!",
                description=f"{random.choice(success_msgs)}",
                color=discord.Color.green()
            )
            embed.set_image(url="attachment://robbery.png")
            embed.add_field(name="💰 Stolen", value=f"+**{stolen}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
            
            await ctx.reply(embed=embed, file=file, mention_author=False)
        else:
            user_balance = await self.quest_data.get_balance(user_id, guild_id)
            fine_percent = random.randint(fine_min, fine_max) / 100
            fine = int(user_balance * fine_percent) if user_balance > 0 else 50
            fine = max(50, fine)
            
            await self.quest_data.add_balance(user_id, guild_id, -fine)
            new_balance = await self.quest_data.get_balance(user_id, guild_id)
            
            fail_msgs = config.get("fail_messages", ["You got caught!"])
            
            # Generate crime scene image
            img_buffer = await generate_crime_scene_image(
                robber_avatar_url, victim_avatar_url,
                ctx.author.display_name, target.display_name,
                success=False, amount=fine
            )
            file = discord.File(img_buffer, filename="caught.png")
            
            embed = discord.Embed(
                title="🚔 Caught!",
                description=f"{random.choice(fail_msgs)}",
                color=discord.Color.red()
            )
            embed.set_image(url="attachment://caught.png")
            embed.add_field(name="💸 Fine", value=f"-**{fine}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
            
            await ctx.reply(embed=embed, file=file, mention_author=False)
    
    @commands.command(name="claim", aliases=["daily"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def claim_command(self, ctx):
        """🎁 Claim your daily stella points reward!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check cooldown (24 hours)
        remaining = await self.check_cooldown(user_id, "claim", 86400)
        if remaining:
            return await ctx.reply(f"⏳ Next daily in **{self.format_time(remaining)}**", mention_author=False)
        
        config = GROUNDED_CONFIG.get("claim", {})
        base_min, base_max = config.get("base_reward", [100, 200])
        streak_bonus = config.get("streak_bonus", 25)
        max_streak = config.get("max_streak", 30)
        milestones = config.get("streak_milestone_bonuses", {})
        
        # Get and update streak
        streak = await self.get_daily_streak(user_id, guild_id)
        streak = min(streak + 1, max_streak)
        await self.update_daily_streak(user_id, guild_id, streak)
        
        # Calculate reward
        base_reward = random.randint(base_min, base_max)
        streak_reward = streak * streak_bonus
        
        # Character bonus
        character = await self.get_user_character(user_id, guild_id)
        char_bonus = 0
        if character:
            char_bonuses = config.get("character_bonuses", {}).get(character, {})
            char_bonus = char_bonuses.get("base_bonus", 0)
        
        # Milestone bonus
        milestone_bonus = milestones.get(str(streak), 0)
        
        total_reward = base_reward + streak_reward + char_bonus + milestone_bonus
        
        await self.quest_data.add_balance(user_id, guild_id, total_reward)
        await self.set_cooldown(user_id, "claim")
        
        new_balance = await self.quest_data.get_balance(user_id, guild_id)
        
        embed = discord.Embed(
            title="🎁 Daily Claimed!",
            color=discord.Color.gold()
        )
        
        breakdown = f"Base: +{base_reward}\nStreak ({streak}d): +{streak_reward}"
        if char_bonus > 0:
            breakdown += f"\n{character}: +{char_bonus}"
        if milestone_bonus > 0:
            breakdown += f"\n🏆 Milestone: +{milestone_bonus}"
        
        embed.add_field(name="💰 Reward", value=f"**+{total_reward}** pts\n-# {breakdown}", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        embed.add_field(name="🔥 Streak", value=f"**{streak}** days", inline=True)
        
        if milestone_bonus > 0:
            embed.set_footer(text=f"🎉 {streak}-day milestone bonus!")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="stats", aliases=["me"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def stats_command(self, ctx, member: discord.Member = None):
        """📊 View your profile card with game stats!"""
        target = member or ctx.author
        guild_id = str(ctx.guild.id)
        user_id = str(target.id)
        
        # Get user data
        balance = await self.quest_data.get_balance(user_id, guild_id)
        
        # Get job info
        current_job_id = await self.get_user_job(user_id, guild_id)
        job_data = self.get_job_by_id(current_job_id) if current_job_id else None
        job_title = job_data.get("title") if job_data else None
        job_emoji = job_data.get("emoji", "💼") if job_data else "💼"
        
        # Get streak
        daily_streak = await self.get_daily_streak(user_id, guild_id)
        
        # Get total earned and games played from database
        total_earned = 0
        total_games = 0
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            server_data = await server_col.find_one({"guild_id": guild_id})
            if server_data and "members" in server_data:
                member_data = server_data["members"].get(user_id, {})
                total_earned = member_data.get("total_stars_earned", 0)
                # Sum up game plays
                game_plays = member_data.get("daily_game_plays", {})
                for game_type, plays in game_plays.items():
                    if isinstance(plays, int):
                        total_games += plays
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
        
        # Generate profile card
        avatar_url = target.display_avatar.with_size(128).url
        
        img_buffer = await generate_profile_card(
            user_name=target.display_name,
            avatar_url=avatar_url,
            balance=balance,
            job_title=job_title,
            job_emoji=job_emoji,
            daily_streak=daily_streak,
            total_games=total_games,
            total_earned=total_earned
        )
        
        file = discord.File(img_buffer, filename="profile.png")
        
        embed = discord.Embed(color=discord.Color.blurple())
        embed.set_image(url="attachment://profile.png")
        embed.set_footer(text=f"Use {ctx.prefix}stats @user to view someone else's profile")
        
        await ctx.reply(embed=embed, file=file, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # ERROR HANDLERS
    # ═══════════════════════════════════════════════════════════════
    
    @slots_command.error
    @coinflip_command.error
    @guess_command.error
    @hangman_game.error
    @wordle_game.error
    @jobs_command.error
    @work_command.error
    @rob_command.error
    @claim_command.error
    async def game_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏳ Cooldown",
                description=f"Please wait **{error.retry_after:.1f}s** before playing again!",
                color=discord.Color.orange()
            )
            await ctx.reply(embed=embed, mention_author=False)
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ Invalid Input",
                description="Please enter valid numbers!",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, mention_author=False)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.reply("❌ Member not found!", mention_author=False)
        else:
            logger.error(f"Game error: {error}")
            raise error


    @commands.command(name="memo")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def memo_game(self, ctx):
        """🧠 Memory game - Remember the emoji!"""
        from utils.cogs.fun import Memo
        from data.local.const import primary_color
        
        emojis = ["😀","😊","😂","😍","😎","😢","😠","😱","😡","😐","🥳","😏","🙃","😇","😅","😜","😌","😋"]
        shuffled = emojis * 2
        random.shuffle(shuffled)
        chosen = random.choice(emojis)
        
        if not hasattr(self, 'correct_emojis'):
            self.correct_emojis = {}
        self.correct_emojis[ctx.channel.id] = chosen

        embed = discord.Embed(
            description=f"Remember this emoji: {chosen}",
            color=primary_color()
        )
        msg = await ctx.reply(embed=embed, mention_author=False)
        await asyncio.sleep(2)

        view = Memo(ctx, shuffled, chosen, msg)
        future = int((datetime.now(timezone.utc) + timedelta(seconds=13)).timestamp())
        
        def timestamp_gen(ts: int) -> str:
            return f"<t:{int(ts)}:R>"
        
        embed = discord.Embed(
            description=f"React with the emoji you remembered.\n`Remaining Time:` {timestamp_gen(future)}",
            color=primary_color(),
        )
        try:
            await msg.edit(embed=embed, view=view)
            await asyncio.sleep(10)
        except asyncio.TimeoutError:
            timeout_embed = discord.Embed(
                title="⏰ Time's Up...",
                description="||```You didn't click the emoji in time.```||",
                color=primary_color()
            )
            await msg.edit(embed=timeout_embed, view=None)


async def setup(bot):
    await bot.add_cog(Games(bot))
