import discord
from discord.ext import commands
import random
import asyncio
import aiohttp
import logging
import json
import io
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Load config files
def load_config(filename: str) -> dict:
    """Load a JSON config file from data/commands/minigames/"""
    try:
        path = Path(__file__).parent.parent.parent / "data" / "commands" / "minigames" / filename
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {filename}: {e}")
        return {}

GAMBLING_CONFIG = load_config("gambling.json")
CLASSIC_CONFIG = load_config("classic.json")
GROUNDED_CONFIG = load_config("grounded.json")

# Slot machine symbols from config or fallback
SLOT_SYMBOLS = GAMBLING_CONFIG.get("slots", {}).get("symbols", {
    "🍒": {"name": "Cherry", "multiplier": 2, "weight": 30},
    "🍋": {"name": "Lemon", "multiplier": 3, "weight": 25},
    "🍊": {"name": "Orange", "multiplier": 4, "weight": 20},
    "🍇": {"name": "Grape", "multiplier": 5, "weight": 15},
    "🔔": {"name": "Bell", "multiplier": 10, "weight": 7},
    "⭐": {"name": "Star", "multiplier": 25, "weight": 2},
    "💎": {"name": "Diamond", "multiplier": 50, "weight": 1},
})

# Rarity config for card games
RARITY_CONFIG = {
    "common": {"chance": 0.50, "color": discord.Color.light_grey(), "multiplier": 1, "stars": "⭐"},
    "uncommon": {"chance": 0.30, "color": discord.Color.green(), "multiplier": 2, "stars": "⭐⭐"},
    "rare": {"chance": 0.15, "color": discord.Color.blue(), "multiplier": 5, "stars": "⭐⭐⭐"},
    "epic": {"chance": 0.04, "color": discord.Color.purple(), "multiplier": 15, "stars": "⭐⭐⭐⭐"},
    "legendary": {"chance": 0.01, "color": discord.Color.gold(), "multiplier": 50, "stars": "⭐⭐⭐⭐⭐"},
}

# Daily limits
DAILY_LIMITS = {
    "pokemon": 15,
    "anime": 15,
    "slots": 50,
    "dice": 50,
    "coinflip": 100,
    "guess": 30,
    "hangman": 20,
    "wordle": 10,
    "work": 999,
    "job": 999,
    "rob": 999,
    "crime": 999,
}


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
            name="📝 **CLASSIC**",
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
        
        # Validate bet
        if bet < 10:
            return await ctx.reply("❌ Minimum bet is **10** stella points!", mention_author=False)
        if bet > 10000:
            return await ctx.reply("❌ Maximum bet is **10,000** stella points!", mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ You need **{bet:,}** but only have **{balance:,}** stella points!", mention_author=False)
        
        # Deduct bet
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Spin animation
        results = [self.get_slot_symbol() for _ in range(3)]
        
        # Calculate winnings
        winnings = 0
        if results[0] == results[1] == results[2]:
            multiplier = SLOT_SYMBOLS[results[0]]["multiplier"]
            winnings = bet * multiplier
            title = f"🎉 JACKPOT! {SLOT_SYMBOLS[results[0]]['name']}!"
            color = discord.Color.gold()
        elif results[0] == results[1] or results[1] == results[2] or results[0] == results[2]:
            winnings = int(bet * 1.5)
            title = "✨ Two Match!"
            color = discord.Color.green()
        else:
            title = "💨 No Match..."
            color = discord.Color.red()
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        # Create embed
        slot_display = f"╔══════════════╗\n║  {results[0]}  │  {results[1]}  │  {results[2]}  ║\n╚══════════════╝"
        
        embed = discord.Embed(title=title, description=f"```{slot_display}```", color=color)
        
        if profit > 0:
            embed.add_field(name="💰 Won", value=f"+**{profit:,}** pts", inline=True)
        else:
            embed.add_field(name="📉 Lost", value=f"**{profit:,}** pts", inline=True)
        
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        embed.set_footer(text=f"Bet: {bet:,} pts")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="coinflip", aliases=["cf", "flip"])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def coinflip_command(self, ctx, bet: int = 50, choice: str = None):
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
        
        # Normalize choice
        choice = choice.lower()
        if choice in ["h", "head", "heads"]:
            choice = "heads"
        elif choice in ["t", "tail", "tails"]:
            choice = "tails"
        else:
            return await ctx.reply("❌ Choose **heads** or **tails**!", mention_author=False)
        
        # Validate bet
        if bet < 10:
            return await ctx.reply("❌ Minimum bet is **10** stella points!", mention_author=False)
        if bet > 5000:
            return await ctx.reply("❌ Maximum bet is **5,000** stella points!", mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ You need **{bet:,}** but only have **{balance:,}** stella points!", mention_author=False)
        
        # Deduct bet
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Flip!
        result = random.choice(["heads", "tails"])
        won = result == choice
        
        if won:
            winnings = bet * 2
            await self.quest_data.add_balance(user_id, guild_id, winnings)
            profit = bet
            title = "🎉 You Won!"
            color = discord.Color.green()
            result_emoji = "👑" if result == "heads" else "🦅"
        else:
            winnings = 0
            profit = -bet
            title = "💸 You Lost!"
            color = discord.Color.red()
            result_emoji = "👑" if result == "heads" else "🦅"
        
        new_balance = balance - bet + winnings
        
        embed = discord.Embed(
            title=title,
            description=f"{result_emoji} The coin landed on **{result.upper()}**!\n"
                       f"You called **{choice}**.",
            color=color
        )
        
        if profit > 0:
            embed.add_field(name="💰 Won", value=f"+**{profit:,}** pts", inline=True)
        else:
            embed.add_field(name="📉 Lost", value=f"**{profit:,}** pts", inline=True)
        
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="guess", aliases=["number", "guessnumber"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def guess_command(self, ctx, bet: int = 50):
        """🔢 Guess a number 1-100! Closer guesses win more."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Validate bet
        if bet < 20:
            return await ctx.reply("❌ Minimum bet is **20** stella points!", mention_author=False)
        if bet > 5000:
            return await ctx.reply("❌ Maximum bet is **5,000** stella points!", mention_author=False)
        
        # Check balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ You need **{bet:,}** but only have **{balance:,}** stella points!", mention_author=False)
        
        # Deduct bet
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Generate secret number
        secret = random.randint(1, 100)
        attempts_left = 5
        
        embed = discord.Embed(
            title="🔢 Number Guess Game",
            description=f"I'm thinking of a number between **1** and **100**!\n\n"
                       f"You have **{attempts_left}** attempts.\n"
                       f"Type your guess in chat!",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Bet: {bet:,} pts • Timeout: 60s")
        
        msg = await ctx.reply(embed=embed, mention_author=False)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
        
        hints = []
        while attempts_left > 0:
            try:
                guess_msg = await self.bot.wait_for("message", timeout=60.0, check=check)
                guess = int(guess_msg.content)
                
                if guess < 1 or guess > 100:
                    await ctx.send("Please guess between 1-100!", delete_after=3)
                    continue
                
                attempts_left -= 1
                diff = abs(secret - guess)
                
                if diff == 0:
                    # Perfect guess!
                    winnings = bet * 10
                    await self.quest_data.add_balance(user_id, guild_id, winnings)
                    new_balance = balance - bet + winnings
                    
                    embed = discord.Embed(
                        title="🎯 PERFECT!",
                        description=f"The number was **{secret}**!\n\n"
                                   f"💰 You won **+{winnings - bet:,}** stella points!\n"
                                   f"💳 Balance: **{new_balance:,}** pts",
                        color=discord.Color.gold()
                    )
                    return await msg.edit(embed=embed)
                
                # Give hints
                if guess < secret:
                    hints.append(f"**{guess}** - Too low! ⬆️")
                else:
                    hints.append(f"**{guess}** - Too high! ⬇️")
                
                embed = discord.Embed(
                    title="🔢 Number Guess Game",
                    description=f"**Hints:**\n" + "\n".join(hints[-5:]) + f"\n\n"
                               f"Attempts left: **{attempts_left}**",
                    color=discord.Color.blue()
                )
                await msg.edit(embed=embed)
                
            except asyncio.TimeoutError:
                break
        
        # Game over - calculate partial winnings based on closest guess
        if hints:
            # Get the closest guess
            guesses = [int(h.split("**")[1]) for h in hints]
            closest = min(guesses, key=lambda x: abs(x - secret))
            diff = abs(closest - secret)
            
            if diff <= 5:
                winnings = bet * 3
            elif diff <= 10:
                winnings = bet * 2
            elif diff <= 20:
                winnings = int(bet * 1.5)
            else:
                winnings = 0
        else:
            winnings = 0
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        embed = discord.Embed(
            title="⏰ Game Over!",
            description=f"The number was **{secret}**!\n\n"
                       f"{'💰 Won' if profit > 0 else '📉 Lost'}: **{profit:+,}** pts\n"
                       f"💳 Balance: **{new_balance:,}** pts",
            color=discord.Color.green() if profit > 0 else discord.Color.red()
        )
        await msg.edit(embed=embed)
    
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
        
        embed = discord.Embed(title=f"🃏 Pokémon Card Draw", color=rarity_data["color"])
        
        if pokemon:
            types_str = " / ".join(pokemon["types"])
            embed.add_field(
                name=f"{rarity_data['stars']} {rarity.upper()}",
                value=f"**{pokemon['name']}** #{pokemon['id']}\nType: {types_str}",
                inline=False
            )
            if pokemon["sprite"]:
                embed.set_thumbnail(url=pokemon["sprite"])
        else:
            embed.add_field(
                name=f"{rarity_data['stars']} {rarity.upper()}",
                value=f"**Mystery Pokémon** #{pokemon_id}",
                inline=False
            )
        
        result_name = "💰 Won" if profit > 0 else "📉 Result"
        embed.add_field(name=result_name, value=f"**{profit:+,}** pts", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        plays_left = DAILY_LIMITS["pokemon"] - plays_today - 1
        embed.set_footer(text=f"Draws left today: {plays_left}")
        await ctx.reply(embed=embed, mention_author=False)
    
    @game.command(name="anime", aliases=["char", "character"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def anime_draw(self, ctx):
        """🎴 Draw a random anime character card for 100 points."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cost = 100
        
        plays_today = await self.get_daily_plays(user_id, guild_id, "anime")
        if plays_today >= DAILY_LIMITS["anime"]:
            return await ctx.reply(
                embed=discord.Embed(
                    title="⏰ Daily Limit!",
                    description=f"Used all **{DAILY_LIMITS['anime']}** draws today.",
                    color=discord.Color.orange()
                ), mention_author=False
            )
        
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            return await ctx.reply(f"❌ Need **{cost}** but have **{balance:,}** pts!", mention_author=False)
        
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        await self.increment_daily_plays(user_id, guild_id, "anime")
        
        rarity = self.get_random_rarity()
        rarity_data = RARITY_CONFIG[rarity]
        reward = cost * rarity_data["multiplier"]
        
        character = await self.fetch_anime_character_info()
        
        await self.quest_data.add_balance(user_id, guild_id, reward)
        new_balance = balance - cost + reward
        profit = reward - cost
        
        embed = discord.Embed(title=f"🎴 Anime Card Draw", color=rarity_data["color"])
        
        if character:
            embed.add_field(
                name=f"{rarity_data['stars']} {rarity.upper()}",
                value=f"**{character['name']}**\n*{character['anime']}*",
                inline=False
            )
            if character["image"]:
                embed.set_thumbnail(url=character["image"])
        else:
            embed.add_field(
                name=f"{rarity_data['stars']} {rarity.upper()}",
                value=f"**Mystery Character**",
                inline=False
            )
        
        result_name = "💰 Won" if profit > 0 else "📉 Result"
        embed.add_field(name=result_name, value=f"**{profit:+,}** pts", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await ctx.reply(embed=embed, mention_author=False)

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
                color=discord.Color.blue()
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
            result = "🎯 **PERFECT!**"
            color = discord.Color.gold()
        elif diff == 1:
            winnings = bet * 2
            result = "✨ **Close!**"
            color = discord.Color.green()
        else:
            winnings = 0
            result = "💨 **Miss!**"
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
            name="💰 Won" if profit > 0 else "📉 Lost",
            value=f"**{profit:+,}** pts",
            inline=True
        )
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await ctx.reply(embed=embed, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # CLASSIC GAMES - HANGMAN
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="hangman", aliases=["hm"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def hangman_game(self, ctx):
        """📝 Play hangman! Guess the word letter by letter."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cost = 50
        
        # Check if already in a game
        game_key = f"{guild_id}_{user_id}_hangman"
        if game_key in self.active_games:
            return await ctx.reply("❌ You're already in a hangman game!", mention_author=False)
        
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            return await ctx.reply(f"❌ Need **{cost}** pts to play! You have **{balance:,}**", mention_author=False)
        
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        
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
                "MISSION", "SECRET", "AGENT", "FORGER", "TWILIGHT", "CIPHER"
            ])
            word = random.choice(fallback).upper()
        
        # Initialize game state
        self.active_games[game_key] = {
            "word": word,
            "guessed": set(),
            "wrong": 0,
            "max_wrong": 6
        }
        
        hangman_stages = [
            "```\n  +---+\n      |\n      |\n      |\n=========```",
            "```\n  +---+\n  O   |\n      |\n      |\n=========```",
            "```\n  +---+\n  O   |\n  |   |\n      |\n=========```",
            "```\n  +---+\n  O   |\n /|   |\n      |\n=========```",
            "```\n  +---+\n  O   |\n /|\\  |\n      |\n=========```",
            "```\n  +---+\n  O   |\n /|\\  |\n /    |\n=========```",
            "```\n  +---+\n  O   |\n /|\\  |\n / \\  |\n=========```"
        ]
        
        def get_display(word, guessed):
            return " ".join(c if c in guessed else "_" for c in word)
        
        def build_embed(game, stage_idx, status="playing"):
            display = get_display(game["word"], game["guessed"])
            guessed_str = ", ".join(sorted(game["guessed"])) or "None"
            
            if status == "win":
                title = "✅ You Won!"
                color = discord.Color.green()
            elif status == "lose":
                title = "❌ Game Over!"
                color = discord.Color.red()
            else:
                title = "🕵️ Hangman"
                color = discord.Color.blue()
            
            embed = discord.Embed(title=title, color=color)
            embed.add_field(name="Word", value=f"`{display}`", inline=False)
            embed.description = hangman_stages[min(stage_idx, 6)]
            embed.add_field(name="Guessed", value=guessed_str, inline=True)
            embed.add_field(name="Wrong", value=f"{game['wrong']}/6", inline=True)
            return embed
        
        embed = build_embed(self.active_games[game_key], 0)
        embed.set_footer(text="Type a letter to guess! (60s timeout)")
        msg = await ctx.reply(embed=embed, mention_author=False)
        
        def check(m):
            return (m.author == ctx.author and m.channel == ctx.channel and 
                    len(m.content) == 1 and m.content.isalpha())
        
        while game_key in self.active_games:
            game = self.active_games[game_key]
            
            try:
                guess_msg = await self.bot.wait_for("message", timeout=60.0, check=check)
                letter = guess_msg.content.upper()
                
                try:
                    await guess_msg.delete()
                except:
                    pass
                
                if letter in game["guessed"]:
                    continue
                
                game["guessed"].add(letter)
                
                if letter not in game["word"]:
                    game["wrong"] += 1
                
                # Check win/lose
                display = get_display(game["word"], game["guessed"])
                
                if "_" not in display:
                    # Won!
                    word_len = len(game["word"])
                    winnings = 100 + (word_len * 10) + ((6 - game["wrong"]) * 20)
                    await self.quest_data.add_balance(user_id, guild_id, winnings)
                    new_balance = await self.quest_data.get_balance(user_id, guild_id)
                    
                    embed = build_embed(game, game["wrong"], "win")
                    embed.add_field(name="💰 Won", value=f"+**{winnings}** pts", inline=True)
                    embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
                    await msg.edit(embed=embed)
                    del self.active_games[game_key]
                    return
                
                if game["wrong"] >= 6:
                    # Lost
                    embed = build_embed(game, 6, "lose")
                    embed.add_field(name="The word was", value=f"**{game['word']}**", inline=False)
                    await msg.edit(embed=embed)
                    del self.active_games[game_key]
                    return
                
                embed = build_embed(game, game["wrong"])
                embed.set_footer(text="Type a letter to guess!")
                await msg.edit(embed=embed)
                
            except asyncio.TimeoutError:
                embed = build_embed(game, game["wrong"], "lose")
                embed.add_field(name="⏰ Timeout!", value=f"The word was **{game['word']}**", inline=False)
                await msg.edit(embed=embed)
                del self.active_games[game_key]
                return
    
    # ═══════════════════════════════════════════════════════════════
    # CLASSIC GAMES - WORDLE
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="wordle")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def wordle_game(self, ctx):
        """🟩 Play Wordle! Guess the 5-letter word in 6 tries."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        cost = 75
        
        game_key = f"{guild_id}_{user_id}_wordle"
        if game_key in self.active_games:
            return await ctx.reply("❌ You're already in a wordle game!", mention_author=False)
        
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            return await ctx.reply(f"❌ Need **{cost}** pts! You have **{balance:,}**", mention_author=False)
        
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        
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
            fallback = ["AGENT", "CODES", "QUEST", "SWORD", "FLAME", "STORM", "PEACE", "DREAM"]
            word = random.choice(fallback)
        
        self.active_games[game_key] = {
            "word": word,
            "attempts": [],
            "max_attempts": 6
        }
        
        def get_result(guess, answer):
            result = []
            answer_chars = list(answer)
            
            # First pass: correct positions
            for i, (g, a) in enumerate(zip(guess, answer)):
                if g == a:
                    result.append("🟩")
                    answer_chars[i] = None
                else:
                    result.append(None)
            
            # Second pass: wrong positions
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
            
            # Add empty rows
            for _ in range(6 - len(game["attempts"])):
                grid.append("⬜⬜⬜⬜⬜")
            
            embed.description = "\n".join(grid)
            embed.add_field(name="Attempts", value=f"{len(game['attempts'])}/6", inline=True)
            return embed
        
        embed = build_embed(self.active_games[game_key])
        embed.set_footer(text="Type a 5-letter word! (90s timeout)")
        msg = await ctx.reply(embed=embed, mention_author=False)
        
        def check(m):
            return (m.author == ctx.author and m.channel == ctx.channel and 
                    len(m.content) == 5 and m.content.isalpha())
        
        payouts = {1: 500, 2: 400, 3: 300, 4: 200, 5: 150, 6: 100}
        
        while game_key in self.active_games:
            game = self.active_games[game_key]
            
            try:
                guess_msg = await self.bot.wait_for("message", timeout=90.0, check=check)
                guess = guess_msg.content.upper()
                
                try:
                    await guess_msg.delete()
                except:
                    pass
                
                game["attempts"].append(guess)
                
                if guess == game["word"]:
                    # Won!
                    attempt_num = len(game["attempts"])
                    winnings = payouts.get(attempt_num, 100)
                    await self.quest_data.add_balance(user_id, guild_id, winnings)
                    new_balance = await self.quest_data.get_balance(user_id, guild_id)
                    
                    embed = build_embed(game, "win")
                    embed.add_field(name="💰 Won", value=f"+**{winnings}** pts", inline=True)
                    embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
                    await msg.edit(embed=embed)
                    del self.active_games[game_key]
                    return
                
                if len(game["attempts"]) >= 6:
                    embed = build_embed(game, "lose")
                    embed.add_field(name="The word was", value=f"**{game['word']}**", inline=False)
                    await msg.edit(embed=embed)
                    del self.active_games[game_key]
                    return
                
                embed = build_embed(game)
                embed.set_footer(text="Type a 5-letter word!")
                await msg.edit(embed=embed)
                
            except asyncio.TimeoutError:
                embed = build_embed(game, "lose")
                embed.add_field(name="⏰ Timeout!", value=f"The word was **{game['word']}**", inline=False)
                await msg.edit(embed=embed)
                del self.active_games[game_key]
                return

    # ═══════════════════════════════════════════════════════════════
    # GROUNDED GAMES (Spy x Family Themed Economy)
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="work")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def work_command(self, ctx):
        """💼 Do honest work for guaranteed stella points."""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check cooldown (30 minutes)
        remaining = await self.check_cooldown(user_id, "work", 1800)
        if remaining:
            return await ctx.reply(f"⏳ You can work again in **{self.format_time(remaining)}**", mention_author=False)
        
        # Get character bonus
        character = await self.get_user_character(user_id, guild_id)
        config = GROUNDED_CONFIG.get("work", {})
        
        base_min, base_max = config.get("base_reward", [50, 150])
        reward = random.randint(base_min, base_max)
        
        # Apply character bonus
        title = "Worker"
        message = "You did some work around town."
        
        if character:
            char_bonus = config.get("character_bonuses", {}).get(character, {})
            multiplier = char_bonus.get("multiplier", 1.0)
            reward = int(reward * multiplier)
            title = char_bonus.get("title", "Worker")
            message = char_bonus.get("message", message)
        else:
            jobs = config.get("default_jobs", [{"title": "Worker", "message": "You worked hard."}])
            job = random.choice(jobs)
            title = job["title"]
            message = job["message"]
        
        await self.quest_data.add_balance(user_id, guild_id, reward)
        await self.set_cooldown(user_id, "work")
        
        new_balance = await self.quest_data.get_balance(user_id, guild_id)
        
        embed = discord.Embed(
            title=f"💼 {title}",
            description=message,
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Earned", value=f"+**{reward}** pts", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        if character:
            embed.set_footer(text=f"🌟 {character} bonus applied!")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="job", aliases=["mission"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def job_command(self, ctx):
        """🎯 Take on a risky mission for bigger rewards. May fail!"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check cooldown (1 hour)
        remaining = await self.check_cooldown(user_id, "job", 3600)
        if remaining:
            return await ctx.reply(f"⏳ Next mission available in **{self.format_time(remaining)}**", mention_author=False)
        
        character = await self.get_user_character(user_id, guild_id)
        config = GROUNDED_CONFIG.get("job", {})
        
        base_success = config.get("success_rate", 0.65)
        base_min, base_max = config.get("base_reward", [100, 400])
        fail_min, fail_max = config.get("fail_penalty", [25, 100])
        
        success_rate = base_success
        reward_mult = 1.0
        mission_name = "Secret Mission"
        
        if character:
            char_bonus = config.get("character_bonuses", {}).get(character, {})
            success_rate += char_bonus.get("success_boost", 0)
            reward_mult = char_bonus.get("reward_multiplier", 1.0)
            missions = char_bonus.get("missions", [mission_name])
            mission_name = random.choice(missions)
        else:
            missions = config.get("default_missions", [{"title": "Mission"}])
            mission = random.choice(missions)
            mission_name = mission.get("title", "Mission")
        
        await self.set_cooldown(user_id, "job")
        
        # Roll for success
        if random.random() < success_rate:
            reward = int(random.randint(base_min, base_max) * reward_mult)
            await self.quest_data.add_balance(user_id, guild_id, reward)
            new_balance = await self.quest_data.get_balance(user_id, guild_id)
            
            embed = discord.Embed(
                title=f"✅ Mission Complete!",
                description=f"**{mission_name}**\n\nYou successfully completed the mission!",
                color=discord.Color.green()
            )
            embed.add_field(name="💰 Earned", value=f"+**{reward}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        else:
            penalty = random.randint(fail_min, fail_max)
            await self.quest_data.add_balance(user_id, guild_id, -penalty)
            new_balance = await self.quest_data.get_balance(user_id, guild_id)
            
            fail_messages = config.get("fail_messages", ["Mission failed!"])
            
            embed = discord.Embed(
                title=f"❌ Mission Failed!",
                description=f"**{mission_name}**\n\n{random.choice(fail_messages)}",
                color=discord.Color.red()
            )
            embed.add_field(name="📉 Lost", value=f"-**{penalty}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        if character:
            embed.set_footer(text=f"🌟 {character}")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="rob", aliases=["steal"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rob_command(self, ctx, target: discord.Member = None):
        """💰 Attempt to steal stella points from another user. High risk!"""
        if target is None:
            return await ctx.reply(f"❌ Usage: `{ctx.prefix}rob @user`", mention_author=False)
        
        if target.id == ctx.author.id:
            return await ctx.reply("❌ You can't rob yourself!", mention_author=False)
        
        if target.bot:
            return await ctx.reply("❌ You can't rob bots!", mention_author=False)
        
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
            return await ctx.reply(f"❌ {target.display_name} doesn't have enough to steal (min 500 pts)", mention_author=False)
        
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
        
        if random.random() < success_rate:
            steal_percent = random.randint(steal_min, steal_max) / 100
            stolen = int(target_balance * steal_percent)
            
            await self.quest_data.add_balance(target_id, guild_id, -stolen)
            await self.quest_data.add_balance(user_id, guild_id, stolen)
            new_balance = await self.quest_data.get_balance(user_id, guild_id)
            
            success_msgs = config.get("success_messages", ["You stole their points!"])
            
            embed = discord.Embed(
                title="💰 Robbery Successful!",
                description=f"{random.choice(success_msgs)}\n\n"
                           f"You stole from **{target.display_name}**!",
                color=discord.Color.green()
            )
            embed.add_field(name="💰 Stolen", value=f"+**{stolen}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        else:
            user_balance = await self.quest_data.get_balance(user_id, guild_id)
            fine_percent = random.randint(fine_min, fine_max) / 100
            fine = int(user_balance * fine_percent) if user_balance > 0 else 50
            fine = max(50, fine)
            
            await self.quest_data.add_balance(user_id, guild_id, -fine)
            new_balance = await self.quest_data.get_balance(user_id, guild_id)
            
            fail_msgs = config.get("fail_messages", ["You got caught!"])
            
            embed = discord.Embed(
                title="🚔 Caught!",
                description=f"{random.choice(fail_msgs)}\n\n"
                           f"You were caught trying to rob **{target.display_name}**!",
                color=discord.Color.red()
            )
            embed.add_field(name="💸 Fine", value=f"-**{fine}** pts", inline=True)
            embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await ctx.reply(embed=embed, mention_author=False)
    
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
    
    # ═══════════════════════════════════════════════════════════════
    # ERROR HANDLERS
    # ═══════════════════════════════════════════════════════════════
    
    @slots_command.error
    @coinflip_command.error
    @guess_command.error
    @hangman_game.error
    @wordle_game.error
    @work_command.error
    @job_command.error
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


async def setup(bot):
    await bot.add_cog(Games(bot))
