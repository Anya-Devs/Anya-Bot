import discord
from discord.ext import commands
import random
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Slot machine symbols
SLOT_SYMBOLS = {
    "🍒": {"name": "Cherry", "multiplier": 2, "weight": 30},
    "🍋": {"name": "Lemon", "multiplier": 3, "weight": 25},
    "🍊": {"name": "Orange", "multiplier": 4, "weight": 20},
    "🍇": {"name": "Grape", "multiplier": 5, "weight": 15},
    "🔔": {"name": "Bell", "multiplier": 10, "weight": 7},
    "⭐": {"name": "Star", "multiplier": 25, "weight": 2},
    "💎": {"name": "Diamond", "multiplier": 50, "weight": 1},
}

# Rarity config for card games (gacha-style random)
RARITY_CONFIG = {
    "common": {"chance": 0.50, "color": discord.Color.light_grey(), "multiplier": 1, "stars": "⭐"},
    "uncommon": {"chance": 0.30, "color": discord.Color.green(), "multiplier": 2, "stars": "⭐⭐"},
    "rare": {"chance": 0.15, "color": discord.Color.blue(), "multiplier": 5, "stars": "⭐⭐⭐"},
    "epic": {"chance": 0.04, "color": discord.Color.purple(), "multiplier": 15, "stars": "⭐⭐⭐⭐"},
    "legendary": {"chance": 0.01, "color": discord.Color.gold(), "multiplier": 50, "stars": "⭐⭐⭐⭐⭐"},
}

# Daily limits
DAILY_LIMITS = {
    "pokemon": 10,
    "anime": 10,
    "slots": 20,
    "dice": 20,
}


class Games(commands.Cog):
    """Mini-games that use stella points."""
    
    def __init__(self, bot):
        self.bot = bot
        from utils.cogs.quest import Quest_Data
        self.quest_data = Quest_Data(bot)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
        return self.session
    
    def cog_unload(self):
        """Cleanup when cog unloads."""
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())
    
    async def get_daily_plays(self, user_id: str, guild_id: str, game: str) -> int:
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
    
    async def increment_daily_plays(self, user_id: str, guild_id: str, game: str):
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
    
    @commands.group(name="game", aliases=["games", "play"], invoke_without_command=True)
    async def game(self, ctx):
        """Play mini-games to win or lose stella points!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Get daily plays for each game
        pokemon_plays = await self.get_daily_plays(user_id, guild_id, "pokemon")
        anime_plays = await self.get_daily_plays(user_id, guild_id, "anime")
        slots_plays = await self.get_daily_plays(user_id, guild_id, "slots")
        dice_plays = await self.get_daily_plays(user_id, guild_id, "dice")
        
        embed = discord.Embed(
            title="🎮 Anya's Game Corner",
            description="*Waku waku!* Play games to win stella points!\n\n"
                        "**Available Games:**",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        
        embed.add_field(
            name="🃏 Pokémon Card Draw",
            value=f"`{ctx.prefix}game pokemon` - 100 pts\n"
                  f"-# Plays: {pokemon_plays}/{DAILY_LIMITS['pokemon']} today",
            inline=True
        )
        embed.add_field(
            name="🎴 Anime Card Draw", 
            value=f"`{ctx.prefix}game anime` - 100 pts\n"
                  f"-# Plays: {anime_plays}/{DAILY_LIMITS['anime']} today",
            inline=True
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(
            name="🎰 Slot Machine",
            value=f"`{ctx.prefix}game slots <bet>`\n"
                  f"-# Plays: {slots_plays}/{DAILY_LIMITS['slots']} today",
            inline=True
        )
        embed.add_field(
            name="🎲 Dice Game",
            value=f"`{ctx.prefix}game dice <bet> <guess>`\n"
                  f"-# Plays: {dice_plays}/{DAILY_LIMITS['dice']} today",
            inline=True
        )
        
        embed.set_footer(text="Daily limits reset at midnight UTC")
        await ctx.reply(embed=embed, mention_author=False)
    
    @game.command(name="pokemon", aliases=["poke", "pkm"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pokemon_draw(self, ctx):
        """Draw a random Pokémon card for 100 points."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cost = 100
        
        # Check daily limit
        plays_today = await self.get_daily_plays(user_id, guild_id, "pokemon")
        if plays_today >= DAILY_LIMITS["pokemon"]:
            embed = discord.Embed(
                title="⏰ Daily Limit Reached!",
                description=f"You've used all **{DAILY_LIMITS['pokemon']}** Pokémon draws today.\n"
                           f"Come back tomorrow!",
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
        
        # Deduct cost and increment plays
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        await self.increment_daily_plays(user_id, guild_id, "pokemon")
        
        # Random rarity (gacha-style) - NOT based on Pokemon stats
        rarity = self.get_random_rarity()
        rarity_data = RARITY_CONFIG[rarity]
        reward = cost * rarity_data["multiplier"]
        
        # Try to fetch Pokemon info for display (fallback if API fails)
        pokemon_id = random.randint(1, 1025)
        pokemon = await self.fetch_pokemon_info(pokemon_id)
        
        # Add reward
        await self.quest_data.add_balance(user_id, guild_id, reward)
        new_balance = balance - cost + reward
        profit = reward - cost
        
        # Create embed
        embed = discord.Embed(
            title=f"🃏 Pokémon Card Draw",
            color=rarity_data["color"]
        )
        
        if pokemon:
            types_str = " / ".join(pokemon["types"])
            embed.add_field(
                name=f"{rarity_data['stars']} {rarity.upper()}",
                value=f"**{pokemon['name']}** #{pokemon['id']}\n"
                      f"Type: {types_str}",
                inline=False
            )
            if pokemon["sprite"]:
                embed.set_thumbnail(url=pokemon["sprite"])
        else:
            # Fallback if API failed
            embed.add_field(
                name=f"{rarity_data['stars']} {rarity.upper()}",
                value=f"**Mystery Pokémon** #{pokemon_id}",
                inline=False
            )
        
        if profit > 0:
            embed.add_field(
                name="� Winnings",
                value=f"+**{profit:,}** pts ({rarity_data['multiplier']}x)",
                inline=True
            )
        else:
            embed.add_field(
                name="📉 Result",
                value=f"**{profit:,}** pts",
                inline=True
            )
        
        embed.add_field(
            name="💳 Balance",
            value=f"**{new_balance:,}** pts",
            inline=True
        )
        
        plays_left = DAILY_LIMITS["pokemon"] - plays_today - 1
        embed.set_footer(text=f"Draws left today: {plays_left}")
        await ctx.reply(embed=embed, mention_author=False)
    
    @game.command(name="anime", aliases=["char", "character"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def anime_draw(self, ctx):
        """Draw a random anime character card for 100 points."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cost = 100
        
        # Check daily limit
        plays_today = await self.get_daily_plays(user_id, guild_id, "anime")
        if plays_today >= DAILY_LIMITS["anime"]:
            embed = discord.Embed(
                title="⏰ Daily Limit Reached!",
                description=f"You've used all **{DAILY_LIMITS['anime']}** anime draws today.\n"
                           f"Come back tomorrow!",
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
        
        # Deduct cost and increment plays
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        await self.increment_daily_plays(user_id, guild_id, "anime")
        
        # Random rarity (gacha-style) - NOT based on character popularity
        rarity = self.get_random_rarity()
        rarity_data = RARITY_CONFIG[rarity]
        reward = cost * rarity_data["multiplier"]
        
        # Try to fetch character info for display (fallback if API fails)
        character = await self.fetch_anime_character_info()
        
        # Add reward
        await self.quest_data.add_balance(user_id, guild_id, reward)
        new_balance = balance - cost + reward
        profit = reward - cost
        
        # Create embed
        embed = discord.Embed(
            title=f"🎴 Anime Card Draw",
            color=rarity_data["color"]
        )
        
        if character:
            embed.add_field(
                name=f"{rarity_data['stars']} {rarity.upper()}",
                value=f"**{character['name']}**\n"
                      f"*{character['anime']}*",
                inline=False
            )
            if character["image"]:
                embed.set_thumbnail(url=character["image"])
        else:
            # Fallback if API failed
            embed.add_field(
                name=f"{rarity_data['stars']} {rarity.upper()}",
                value=f"**Mystery Character**\n*Unknown Anime*",
                inline=False
            )
        
        if profit > 0:
            embed.add_field(
                name="� Winnings",
                value=f"+**{profit:,}** pts ({rarity_data['multiplier']}x)",
                inline=True
            )
        else:
            embed.add_field(
                name="📉 Result",
                value=f"**{profit:,}** pts",
                inline=True
            )
        
        embed.add_field(
            name="💳 Balance",
            value=f"**{new_balance:,}** pts",
            inline=True
        )
        
        plays_left = DAILY_LIMITS["anime"] - plays_today - 1
        embed.set_footer(text=f"Draws left today: {plays_left}")
        await ctx.reply(embed=embed, mention_author=False)
    
    @game.command(name="slots", aliases=["slot", "spin"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def slot_machine(self, ctx, bet: int = 50):
        """Play the slot machine! Bet stella points to win big."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check daily limit
        plays_today = await self.get_daily_plays(user_id, guild_id, "slots")
        if plays_today >= DAILY_LIMITS["slots"]:
            embed = discord.Embed(
                title="⏰ Daily Limit Reached!",
                description=f"You've used all **{DAILY_LIMITS['slots']}** slot spins today.\n"
                           f"Come back tomorrow!",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Validate bet
        if bet < 10:
            embed = discord.Embed(
                title="❌ Minimum Bet",
                description="Minimum bet is **10** stella points!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        if bet > 5000:
            embed = discord.Embed(
                title="❌ Maximum Bet",
                description="Maximum bet is **5,000** stella points!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            embed = discord.Embed(
                title="❌ Not Enough Points!",
                description=f"You need **{bet:,}** stella points but only have **{balance:,}**.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Deduct bet and increment plays
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        await self.increment_daily_plays(user_id, guild_id, "slots")
        
        # Spin the slots
        results = [self.get_slot_symbol() for _ in range(3)]
        
        # Calculate winnings
        winnings = 0
        if results[0] == results[1] == results[2]:
            # Jackpot - all three match
            multiplier = SLOT_SYMBOLS[results[0]]["multiplier"]
            winnings = bet * multiplier
        elif results[0] == results[1] or results[1] == results[2] or results[0] == results[2]:
            # Two match - small win
            winnings = bet * 2
        
        # Add winnings
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        # Show result (no animation to keep it snappy)
        slot_display = f"```\n{results[0]} | {results[1]} | {results[2]}\n```"
        
        if winnings > 0:
            if results[0] == results[1] == results[2]:
                title = "🎉 JACKPOT!"
                color = discord.Color.gold()
            else:
                title = "✨ Winner!"
                color = discord.Color.green()
            result_text = f"+**{profit:,}** pts"
        else:
            title = "💨 No Match"
            color = discord.Color.red()
            result_text = f"**{profit:,}** pts"
        
        embed = discord.Embed(
            title=title,
            description=slot_display,
            color=color
        )
        
        embed.add_field(name="Result", value=result_text, inline=True)
        embed.add_field(name="Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        plays_left = DAILY_LIMITS["slots"] - plays_today - 1
        embed.set_footer(text=f"Bet: {bet:,} pts • Spins left: {plays_left}")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @game.command(name="dice", aliases=["roll", "guess"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def dice_game(self, ctx, bet: int = 50, guess: int = None):
        """Guess the dice roll! Guess 1-6 to play."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Validate guess
        if guess is None:
            plays_today = await self.get_daily_plays(user_id, guild_id, "dice")
            embed = discord.Embed(
                title="🎲 Dice Game",
                description=f"**How to play:**\n"
                           f"`{ctx.prefix}game dice <bet> <guess>`\n\n"
                           f"Guess a number from 1-6.\n"
                           f"• Exact match: **5x** your bet!\n"
                           f"• Off by 1: **2x** your bet\n"
                           f"• Otherwise: You lose your bet\n\n"
                           f"**Example:** `{ctx.prefix}game dice 100 4`\n\n"
                           f"-# Plays today: {plays_today}/{DAILY_LIMITS['dice']}",
                color=discord.Color.blue()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Check daily limit
        plays_today = await self.get_daily_plays(user_id, guild_id, "dice")
        if plays_today >= DAILY_LIMITS["dice"]:
            embed = discord.Embed(
                title="⏰ Daily Limit Reached!",
                description=f"You've used all **{DAILY_LIMITS['dice']}** dice rolls today.\n"
                           f"Come back tomorrow!",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        if guess < 1 or guess > 6:
            embed = discord.Embed(
                title="❌ Invalid Guess",
                description="Please guess a number between **1** and **6**!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Validate bet
        if bet < 10:
            embed = discord.Embed(
                title="❌ Minimum Bet",
                description="Minimum bet is **10** stella points!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        if bet > 5000:
            embed = discord.Embed(
                title="❌ Maximum Bet",
                description="Maximum bet is **5,000** stella points!",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            embed = discord.Embed(
                title="❌ Not Enough Points!",
                description=f"You need **{bet:,}** stella points but only have **{balance:,}**.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Deduct bet and increment plays
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        await self.increment_daily_plays(user_id, guild_id, "dice")
        
        # Roll the dice
        roll = random.randint(1, 6)
        dice_faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
        
        # Calculate winnings
        diff = abs(roll - guess)
        if diff == 0:
            winnings = bet * 5  # Exact match
            result_text = "🎯 **PERFECT!** Exact match!"
            color = discord.Color.gold()
        elif diff == 1:
            winnings = bet * 2  # Close
            result_text = "✨ **Close!** Off by 1"
            color = discord.Color.green()
        else:
            winnings = 0
            result_text = "💨 **Miss!** Better luck next time"
            color = discord.Color.red()
        
        # Add winnings
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        # Create embed
        embed = discord.Embed(
            title="🎲 Dice Game",
            color=color
        )
        
        embed.add_field(
            name="Roll",
            value=f"{dice_faces[roll]} **{roll}**",
            inline=True
        )
        embed.add_field(
            name="Your Guess",
            value=f"**{guess}**",
            inline=True
        )
        embed.add_field(
            name="\u200b",
            value="\u200b",
            inline=True
        )
        
        embed.add_field(
            name="Result",
            value=result_text,
            inline=False
        )
        
        if profit > 0:
            embed.add_field(
                name="💰 Winnings",
                value=f"+**{profit:,}** stella points!",
                inline=True
            )
        elif profit < 0:
            embed.add_field(
                name="📉 Loss",
                value=f"**{profit:,}** stella points",
                inline=True
            )
        
        embed.add_field(
            name="💳 Balance",
            value=f"**{new_balance:,}** pts",
            inline=True
        )
        
        plays_left = DAILY_LIMITS["dice"] - plays_today - 1
        embed.set_footer(text=f"Bet: {bet:,} pts • Rolls left: {plays_left}")
        await ctx.reply(embed=embed, mention_author=False)
    
    @pokemon_draw.error
    @anime_draw.error
    @slot_machine.error
    @dice_game.error
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
                description="Please enter valid numbers for bet and guess!",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, mention_author=False)
        else:
            logger.error(f"Game error: {error}")
            raise error


async def setup(bot):
    await bot.add_cog(Games(bot))
