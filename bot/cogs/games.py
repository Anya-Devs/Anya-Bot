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


# ═══════════════════════════════════════════════════════════════
# MULTIPLAYER GAME VIEWS
# ═══════════════════════════════════════════════════════════════

class HangmanJoinView(discord.ui.View):
    """View for joining hangman game"""
    def __init__(self, cog, game_id: str):
        super().__init__(timeout=30)
        self.cog = cog
        self.game_id = game_id
    
    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green, emoji="🎮")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game no longer exists!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        user_id = str(interaction.user.id)
        
        if game["started"]:
            return await interaction.response.send_message("❌ Game already started!", ephemeral=True)
        
        if user_id in game["players"]:
            return await interaction.response.send_message("✅ You're already in this game!", ephemeral=True)
        
        if len(game["players"]) >= 5:
            return await interaction.response.send_message("❌ Game is full (5 players max)!", ephemeral=True)
        
        # Add player
        game["players"][user_id] = {
            "guessed": set(),
            "wrong": 0,
            "display": " ".join("_" for _ in game["word"]),
            "status": "playing",
            "dm_msg": None,
            "view": None
        }
        
        await interaction.response.send_message(f"✅ Joined! Check your DMs when the game starts.", ephemeral=True)
        
        # Update join message
        embed = interaction.message.embeds[0]
        embed.description = f"**Word Length:** {len(game['word'])} letters\n\n" \
                           f"**Players:** {len(game['players'])}/5\n" \
                           f"Click **Join Game** to play in your DMs!\n" \
                           f"Wrong guesses lose **10 stella points** each.\n" \
                           f"(You can play even with 0 points!)\n\n" \
                           f"Game starts in **30 seconds** or when 5 players join."
        await interaction.message.edit(embed=embed)
        
        # Start early if 5 players
        if len(game["players"]) >= 5:
            game["started"] = True
            self.stop()
            await self.cog._start_hangman_game(self.game_id)


# Hangman ASCII art stages
HANGMAN_STAGES = [
    "```\n  +---+\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]


class HangmanLetterView(discord.ui.View):
    """View for guessing letters in hangman with pagination"""
    def __init__(self, cog, game_id: str, user_id: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.game_id = game_id
        self.user_id = user_id
        self.page = 0
        
        # Letter pages: 5 letters per row, 3 rows = 15 letters per page
        self.letter_pages = [
            "ABCDEFGHIJKLMNO",  # Page 0: A-O
            "PQRSTUVWXYZ"       # Page 1: P-Z
        ]
        
        self._build_buttons()
    
    def _build_buttons(self):
        """Build the current page of letter buttons"""
        self.clear_items()
        
        letters = self.letter_pages[self.page]
        game = self.cog.active_games.get(self.game_id)
        if not game:
            return
        
        player = game["players"].get(self.user_id)
        if not player:
            return
        
        # Add letter buttons (5 per row, up to 3 rows)
        for i, letter in enumerate(letters):
            # Determine button style based on guess status
            if letter in player.get("guessed", set()):
                if letter in game["word"]:
                    style = discord.ButtonStyle.success  # Green for correct
                else:
                    style = discord.ButtonStyle.danger   # Red for wrong
                disabled = True
            else:
                style = discord.ButtonStyle.primary
                disabled = False
            
            button = discord.ui.Button(
                label=letter,
                style=style,
                disabled=disabled,
                row=i // 5
            )
            button.callback = self._create_letter_callback(letter)
            self.add_item(button)
        
        # Add navigation buttons on row 4
        if len(self.letter_pages) > 1:
            prev_btn = discord.ui.Button(
                label="⬅️ Back",
                style=discord.ButtonStyle.secondary,
                disabled=(self.page == 0),
                row=4
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)
            
            next_btn = discord.ui.Button(
                label="Next ➡️",
                style=discord.ButtonStyle.secondary,
                disabled=(self.page == len(self.letter_pages) - 1),
                row=4
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)
    
    async def _prev_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if self.page > 0:
            self.page -= 1
            self._build_buttons()
            
            game = self.cog.active_games.get(self.game_id)
            player = game["players"].get(self.user_id)
            guessed_str = ", ".join(sorted(player["guessed"])) or "None"
            
            embed = discord.Embed(
                title="🕵️ Hangman",
                description=f"{HANGMAN_STAGES[player['wrong']]}\n**Word:** `{player['display']}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Guessed", value=guessed_str, inline=True)
            embed.add_field(name="Wrong", value=f"{player['wrong']}/6", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def _next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if self.page < len(self.letter_pages) - 1:
            self.page += 1
            self._build_buttons()
            
            game = self.cog.active_games.get(self.game_id)
            player = game["players"].get(self.user_id)
            guessed_str = ", ".join(sorted(player["guessed"])) or "None"
            
            embed = discord.Embed(
                title="🕵️ Hangman",
                description=f"{HANGMAN_STAGES[player['wrong']]}\n**Word:** `{player['display']}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="Guessed", value=guessed_str, inline=True)
            embed.add_field(name="Wrong", value=f"{player['wrong']}/6", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=self)
    
    def _create_letter_callback(self, letter: str):
        """Create callback for letter button"""
        async def callback(interaction: discord.Interaction):
            if self.game_id not in self.cog.active_games:
                return await interaction.response.send_message("❌ Game ended!", ephemeral=True)
            
            game = self.cog.active_games[self.game_id]
            player = game["players"].get(self.user_id)
            
            if not player or player["status"] != "playing":
                return await interaction.response.send_message("❌ You're not playing!", ephemeral=True)
            
            if letter in player["guessed"]:
                return await interaction.response.send_message(f"❌ Already guessed **{letter}**!", ephemeral=True)
            
            # Process guess
            player["guessed"].add(letter)
            guild_id = game["guild_id"]
            
            # Check if letter is in word
            is_correct = letter in game["word"]
            if not is_correct:
                player["wrong"] += 1
                await self.cog.quest_data.add_balance(self.user_id, guild_id, -10)
            
            # Update display
            player["display"] = " ".join(c if c in player["guessed"] else "_" for c in game["word"])
            
            # Rebuild buttons FIRST to update colors
            self._build_buttons()
            
            # Check win/lose
            if "_" not in player["display"]:
                player["status"] = "won"
                word_len = len(game["word"])
                winnings = 100 + (word_len * 10) + ((6 - player["wrong"]) * 20)
                await self.cog.quest_data.add_balance(self.user_id, guild_id, winnings)
                
                embed = discord.Embed(
                    title="🏆 You Won!",
                    description=f"{HANGMAN_STAGES[player['wrong']]}\n**Word:** {game['word']}\n\n💰 Won **+{winnings}** stella points!",
                    color=discord.Color.green()
                )
                await interaction.response.edit_message(embed=embed, view=None)
            elif player["wrong"] >= 6:
                player["status"] = "lost"
                embed = discord.Embed(
                    title="💀 Game Over!",
                    description=f"{HANGMAN_STAGES[6]}\n**Word was:** {game['word']}",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                # Update DM with hangman drawing
                guessed_str = ", ".join(sorted(player["guessed"])) or "None"
                
                embed = discord.Embed(
                    title="🕵️ Hangman",
                    description=f"{HANGMAN_STAGES[player['wrong']]}\n**Word:** `{player['display']}`",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Guessed", value=guessed_str, inline=True)
                embed.add_field(name="Wrong", value=f"{player['wrong']}/6", inline=True)
                
                await interaction.response.edit_message(embed=embed, view=self)
            
            # Update leaderboard
            await self.cog._update_hangman_leaderboard(self.game_id)
        
        return callback


class WordleJoinView(discord.ui.View):
    """View for joining wordle game"""
    def __init__(self, cog, game_id: str):
        super().__init__(timeout=30)
        self.cog = cog
        self.game_id = game_id
    
    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green, emoji="🎮")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game no longer exists!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        user_id = str(interaction.user.id)
        
        if game["started"]:
            return await interaction.response.send_message("❌ Game already started!", ephemeral=True)
        
        if user_id in game["players"]:
            return await interaction.response.send_message("✅ You're already in this game!", ephemeral=True)
        
        if len(game["players"]) >= 5:
            return await interaction.response.send_message("❌ Game is full (5 players max)!", ephemeral=True)
        
        # Add player
        game["players"][user_id] = {
            "attempts": [],
            "status": "playing",
            "dm_msg": None,
            "view": None
        }
        
        await interaction.response.send_message(f"✅ Joined! Check your DMs when the game starts.", ephemeral=True)
        
        # Update join message
        embed = interaction.message.embeds[0]
        embed.description = f"Guess the **5-letter word** in 6 tries!\n\n" \
                           f"**Players:** {len(game['players'])}/5\n" \
                           f"Click **Join Game** to play in your DMs!\n" \
                           f"Wrong guesses lose **15 stella points** each.\n" \
                           f"(You can play even with 0 points!)\n\n" \
                           f"Game starts in **30 seconds** or when 5 players join."
        await interaction.message.edit(embed=embed)
        
        # Start early if 5 players
        if len(game["players"]) >= 5:
            game["started"] = True
            self.stop()
            await self.cog._start_wordle_game(self.game_id)


class WordleGuessModal(discord.ui.Modal, title="Submit Your Guess"):
    """Modal for submitting wordle guesses"""
    guess_input = discord.ui.TextInput(
        label="Enter a 5-letter word",
        placeholder="AGENT",
        min_length=5,
        max_length=5,
        required=True
    )
    
    def __init__(self, cog, game_id: str, user_id: str):
        super().__init__()
        self.cog = cog
        self.game_id = game_id
        self.user_id = user_id
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game ended!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        player = game["players"].get(self.user_id)
        
        if not player or player["status"] != "playing":
            return await interaction.response.send_message("❌ You're not playing!", ephemeral=True)
        
        guess = self.guess_input.value.upper()
        
        if not guess.isalpha():
            return await interaction.response.send_message("❌ Only letters allowed!", ephemeral=True)
        
        # Calculate result
        def get_result(guess_word, answer):
            result = []
            answer_chars = list(answer)
            for i, (g, a) in enumerate(zip(guess_word, answer)):
                if g == a:
                    result.append("🟩")
                    answer_chars[i] = None
                else:
                    result.append(None)
            for i, g in enumerate(guess_word):
                if result[i] is None:
                    if g in answer_chars:
                        result[i] = "🟨"
                        answer_chars[answer_chars.index(g)] = None
                    else:
                        result[i] = "⬛"
            return "".join(result)
        
        result = get_result(guess, game["word"])
        
        # Deduct points if not correct
        if guess != game["word"]:
            guild_id = game["guild_id"]
            await self.cog.quest_data.add_balance(self.user_id, guild_id, -15)
        
        # Add attempt
        player["attempts"].append({"word": guess, "result": result})
        
        # Check win/lose
        payouts = {1: 500, 2: 400, 3: 300, 4: 200, 5: 150, 6: 100}
        
        if guess == game["word"]:
            player["status"] = "won"
            attempt_num = len(player["attempts"])
            winnings = payouts.get(attempt_num, 100)
            guild_id = game["guild_id"]
            await self.cog.quest_data.add_balance(self.user_id, guild_id, winnings)
            
            grid = [att["result"] + f" `{att['word']}`" for att in player["attempts"]]
            
            embed = discord.Embed(
                title="🏆 You Won!",
                description="\n".join(grid) + f"\n\n💰 Won **+{winnings}** stella points!",
                color=discord.Color.gold()
            )
            await interaction.response.edit_message(embed=embed, view=None)
        elif len(player["attempts"]) >= 6:
            player["status"] = "lost"
            grid = [att["result"] + f" `{att['word']}`" for att in player["attempts"]]
            
            embed = discord.Embed(
                title="💀 Game Over!",
                description="\n".join(grid) + f"\n\n**Word was:** {game['word']}",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            # Continue playing
            grid = [att["result"] + f" `{att['word']}`" for att in player["attempts"]]
            for _ in range(6 - len(player["attempts"])):
                grid.append("⬜⬜⬜⬜⬜")
            
            embed = discord.Embed(
                title="🟩 Your Wordle Game",
                description="\n".join(grid) + "\n\n"
                           f"Click **Submit Guess** to enter a 5-letter word!\n"
                           f"❌ Wrong guess = **-15 stella points**",
                color=discord.Color.green()
            )
            embed.add_field(name="Attempts", value=f"{len(player['attempts'])}/6", inline=True)
            
            await interaction.response.edit_message(embed=embed)
        
        # Update leaderboard
        await self.cog._update_wordle_leaderboard(self.game_id)


class WordleGuessView(discord.ui.View):
    """View for wordle game with submit button"""
    def __init__(self, cog, game_id: str, user_id: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.game_id = game_id
        self.user_id = user_id
    
    @discord.ui.button(label="Submit Guess", style=discord.ButtonStyle.green, emoji="📝")
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WordleGuessModal(self.cog, self.game_id, self.user_id)
        await interaction.response.send_modal(modal)


# ═══════════════════════════════════════════════════════════════
# JOB SYSTEM VIEWS
# ═══════════════════════════════════════════════════════════════

class JobSelectMenu(discord.ui.Select):
    """Dropdown menu for selecting a job to apply for"""
    def __init__(self, cog, user: discord.Member, guild_id: str, user_stats: dict):
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.user_stats = user_stats
        
        jobs_config = GROUNDED_CONFIG.get("jobs_system", {}).get("available_jobs", [])
        
        options = []
        for job in jobs_config:
            reqs = job.get("requirements", {})
            qualified = (
                user_stats["stars"] >= reqs.get("min_stars", 0) and
                user_stats["activity"] >= reqs.get("min_activity", 0) and
                user_stats["balance"] >= reqs.get("min_balance", 0)
            )
            
            desc = f"Pay: {job['pay_range'][0]}-{job['pay_range'][1]} pts"
            if not qualified:
                desc = f"🔒 Requires: ⭐{reqs.get('min_stars', 0)} 📊{reqs.get('min_activity', 0)}"
            
            options.append(discord.SelectOption(
                label=job["title"],
                value=job["id"],
                description=desc[:100],
                emoji=job.get("emoji", "💼")
            ))
        
        super().__init__(
            placeholder="Select a job to apply for...",
            min_values=1,
            max_values=1,
            options=options[:25]
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your job board!", ephemeral=True)
        
        job_id = self.values[0]
        job_data = self.cog.get_job_by_id(job_id)
        
        if not job_data:
            return await interaction.response.send_message("❌ Job not found!", ephemeral=True)
        
        # Check requirements
        reqs = job_data.get("requirements", {})
        if (self.user_stats["stars"] < reqs.get("min_stars", 0) or
            self.user_stats["activity"] < reqs.get("min_activity", 0) or
            self.user_stats["balance"] < reqs.get("min_balance", 0)):
            
            # Build requirement status with checkmarks
            stars_ok = "✅" if self.user_stats["stars"] >= reqs.get("min_stars", 0) else "❌"
            activity_ok = "✅" if self.user_stats["activity"] >= reqs.get("min_activity", 0) else "❌"
            balance_ok = "✅" if self.user_stats["balance"] >= reqs.get("min_balance", 0) else "❌"
            
            embed = discord.Embed(
                title="❌ Requirements Not Met",
                description=f"You don't qualify for **{job_data['title']}** yet!\n\n"
                           f"**Requirements:**\n"
                           f"{stars_ok} ⭐ Stars: {reqs.get('min_stars', 0):,} (You: {self.user_stats['stars']:,})\n"
                           f"{activity_ok} 📊 Activity: {reqs.get('min_activity', 0)} (You: {self.user_stats['activity']})\n"
                           f"{balance_ok} 💰 Balance: {reqs.get('min_balance', 0):,} (You: {self.user_stats['balance']:,})",
                color=discord.Color.red()
            )
            
            # Add tips on how to earn each requirement
            tips = []
            if self.user_stats["stars"] < reqs.get("min_stars", 0):
                tips.append("⭐ **Stars** = Total stella points earned lifetime. Use `.work` at your current job to earn more!")
            if self.user_stats["activity"] < reqs.get("min_activity", 0):
                tips.append("📊 **Activity** = Commands used. Keep using bot commands to increase!")
            if self.user_stats["balance"] < reqs.get("min_balance", 0):
                tips.append("💰 **Balance** = Current stella points. Earn with `.work`, `.claim`, games, etc.")
            
            embed.add_field(
                name="💡 How to Qualify",
                value="\n".join(tips) if tips else "Keep playing to meet requirements!",
                inline=False
            )
            
            # Suggest a job they might qualify for
            embed.set_footer(text="Tip: Start with entry-level jobs and work your way up!")
            
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Apply for job
        user_id = str(interaction.user.id)
        await self.cog.set_user_job(user_id, self.guild_id, job_id)
        
        embed = discord.Embed(
            title="✅ Job Application Accepted!",
            description=f"Congratulations! You are now employed as a **{job_data['emoji']} {job_data['title']}**!\n\n"
                       f"Use `.work` to start earning stella points!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="💰 Pay Range",
            value=f"{job_data['pay_range'][0]}-{job_data['pay_range'][1]} pts per shift",
            inline=True
        )
        
        await interaction.response.edit_message(embed=embed, view=None)


class JobBoardView(discord.ui.View):
    """View for the job board with apply/quit buttons"""
    def __init__(self, cog, user: discord.Member, guild_id: str, current_job_id: Optional[str]):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.current_job_id = current_job_id
        self.user_stats = {}
    
    async def setup(self):
        """Async setup to fetch user stats"""
        user_id = str(self.user.id)
        self.user_stats = {
            "stars": await self.cog.get_user_stars(user_id, self.guild_id),
            "activity": await self.cog.get_user_activity(user_id, self.guild_id),
            "balance": await self.cog.quest_data.get_balance(user_id, self.guild_id)
        }
        
        # Add job select menu
        self.add_item(JobSelectMenu(self.cog, self.user, self.guild_id, self.user_stats))
    
    @discord.ui.button(label="Quit Job", style=discord.ButtonStyle.danger, emoji="🚪", row=1)
    async def quit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your job board!", ephemeral=True)
        
        user_id = str(interaction.user.id)
        current_job_id = await self.cog.get_user_job(user_id, self.guild_id)
        
        if not current_job_id:
            return await interaction.response.send_message("❌ You don't have a job to quit!", ephemeral=True)
        
        job_data = self.cog.get_job_by_id(current_job_id)
        job_name = job_data["title"] if job_data else "Unknown"
        
        await self.cog.set_user_job(user_id, self.guild_id, None)
        
        embed = discord.Embed(
            title="👋 Job Quit",
            description=f"You quit your job as **{job_name}**.\n\n"
                       f"Use `.jobs` to find a new job!",
            color=discord.Color.orange()
        )
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your job board!", ephemeral=True)
        
        # Refresh stats and rebuild view
        user_id = str(interaction.user.id)
        current_job_id = await self.cog.get_user_job(user_id, self.guild_id)
        balance = await self.cog.quest_data.get_balance(user_id, self.guild_id)
        stars = await self.cog.get_user_stars(user_id, self.guild_id)
        activity = await self.cog.get_user_activity(user_id, self.guild_id)
        
        jobs_config = GROUNDED_CONFIG.get("jobs_system", {})
        available_jobs = jobs_config.get("available_jobs", [])
        categories = jobs_config.get("job_categories", {})
        
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
            current_job = self.cog.get_job_by_id(current_job_id)
            if current_job:
                embed.add_field(
                    name="💼 Current Job",
                    value=f"{current_job['emoji']} **{current_job['title']}**\n"
                          f"Pay: {current_job['pay_range'][0]}-{current_job['pay_range'][1]} pts",
                    inline=False
                )
        
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
        
        # Update user stats for the select menu
        self.user_stats = {"stars": stars, "activity": activity, "balance": balance}
        
        await interaction.response.edit_message(embed=embed)


class TaskSelectMenu(discord.ui.Select):
    """Dropdown menu for selecting a work task"""
    def __init__(self, cog, user: discord.Member, guild_id: str, job_data: dict):
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.job_data = job_data
        
        tasks = job_data.get("tasks", [])
        options = []
        for i, task in enumerate(tasks):
            options.append(discord.SelectOption(
                label=task["name"],
                value=str(i),
                description=task["message"][:100] if len(task["message"]) > 100 else task["message"],
                emoji="📝"
            ))
        
        super().__init__(
            placeholder="Choose your task...",
            min_values=1,
            max_values=1,
            options=options if options else [discord.SelectOption(label="Work", value="0")]
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your work shift!", ephemeral=True)
        
        user_id = str(interaction.user.id)
        task_idx = int(self.values[0])
        tasks = self.job_data.get("tasks", [])
        
        if task_idx < len(tasks):
            task = tasks[task_idx]
            task_name = task["name"]
            task_message = task["message"]
        else:
            task_name = "Work"
            task_message = "You completed your work shift!"
        
        # Calculate reward
        pay_min, pay_max = self.job_data.get("pay_range", [50, 100])
        reward = random.randint(pay_min, pay_max)
        
        # Apply character bonus if any
        character = await self.cog.get_user_character(user_id, self.guild_id)
        if character:
            work_config = GROUNDED_CONFIG.get("work", {})
            char_bonus = work_config.get("character_bonuses", {}).get(character, {})
            multiplier = char_bonus.get("multiplier", 1.0)
            reward = int(reward * multiplier)
        
        # Add reward and set cooldown
        await self.cog.quest_data.add_balance(user_id, self.guild_id, reward)
        await self.cog.set_cooldown(user_id, "work")
        
        # Track total stars earned
        try:
            db = self.cog.quest_data.mongoConnect[self.cog.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": self.guild_id},
                {"$inc": {f"members.{user_id}.total_stars_earned": reward}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error tracking stars: {e}")
        
        new_balance = await self.cog.quest_data.get_balance(user_id, self.guild_id)
        
        embed = discord.Embed(
            title=f"{self.job_data['emoji']} {task_name}",
            description=task_message,
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Earned", value=f"+**{reward}** pts", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        if character:
            embed.set_footer(text=f"🌟 {character} bonus applied!")
        
        await interaction.response.edit_message(embed=embed, view=None)


class WorkTaskView(discord.ui.View):
    """View for selecting work tasks"""
    def __init__(self, cog, user: discord.Member, guild_id: str, job_data: dict):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.job_data = job_data
        
        # Add task select menu
        self.add_item(TaskSelectMenu(cog, user, guild_id, job_data))
    
    @discord.ui.button(label="Quick Work", style=discord.ButtonStyle.green, emoji="⚡", row=1)
    async def quick_work_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Do a random task quickly"""
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("❌ This isn't your work shift!", ephemeral=True)
        
        user_id = str(interaction.user.id)
        tasks = self.job_data.get("tasks", [])
        
        if tasks:
            task = random.choice(tasks)
            task_name = task["name"]
            task_message = task["message"]
        else:
            task_name = "Work"
            task_message = "You completed your work shift!"
        
        # Calculate reward
        pay_min, pay_max = self.job_data.get("pay_range", [50, 100])
        reward = random.randint(pay_min, pay_max)
        
        # Apply character bonus
        character = await self.cog.get_user_character(user_id, self.guild_id)
        if character:
            work_config = GROUNDED_CONFIG.get("work", {})
            char_bonus = work_config.get("character_bonuses", {}).get(character, {})
            multiplier = char_bonus.get("multiplier", 1.0)
            reward = int(reward * multiplier)
        
        # Add reward and set cooldown
        await self.cog.quest_data.add_balance(user_id, self.guild_id, reward)
        await self.cog.set_cooldown(user_id, "work")
        
        # Track total stars earned
        try:
            db = self.cog.quest_data.mongoConnect[self.cog.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": self.guild_id},
                {"$inc": {f"members.{user_id}.total_stars_earned": reward}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error tracking stars: {e}")
        
        new_balance = await self.cog.quest_data.get_balance(user_id, self.guild_id)
        
        embed = discord.Embed(
            title=f"{self.job_data['emoji']} {task_name}",
            description=task_message,
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Earned", value=f"+**{reward}** pts", inline=True)
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        if character:
            embed.set_footer(text=f"🌟 {character} bonus applied!")
        
        await interaction.response.edit_message(embed=embed, view=None)


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
        
        # Pre-generate final results
        results = [self.get_slot_symbol() for _ in range(3)]
        
        # Send initial spinning message
        spinning_embed = discord.Embed(
            title="🎰 Spinning...",
            description="```\n╔══════════════╗\n║  🎲  │  🎲  │  🎲  ║\n╚══════════════╝\n```",
            color=discord.Color.blue()
        )
        spinning_embed.set_footer(text=f"Bet: {bet:,} pts")
        message = await ctx.reply(embed=spinning_embed, mention_author=False)
        
        # Animate each reel spinning one at a time
        spinning_symbols = ["🎲", "🎪", "🎭", "🎨", "🎬", "🎯"]
        
        # Reel 1 spinning
        for _ in range(4):
            reel1 = random.choice(spinning_symbols)
            anim_embed = discord.Embed(
                title="🎰 Spinning...",
                description=f"```\n╔══════════════╗\n║  {reel1}  │  🎲  │  🎲  ║\n╚══════════════╝\n```",
                color=discord.Color.blue()
            )
            anim_embed.set_footer(text=f"Bet: {bet:,} pts")
            await message.edit(embed=anim_embed)
            await asyncio.sleep(0.3)
        
        # Reel 1 stops
        anim_embed = discord.Embed(
            title="🎰 Spinning...",
            description=f"```\n╔══════════════╗\n║  {results[0]}  │  🎲  │  🎲  ║\n╚══════════════╝\n```",
            color=discord.Color.blue()
        )
        anim_embed.set_footer(text=f"Bet: {bet:,} pts")
        await message.edit(embed=anim_embed)
        await asyncio.sleep(0.5)
        
        # Reel 2 spinning
        for _ in range(4):
            reel2 = random.choice(spinning_symbols)
            anim_embed = discord.Embed(
                title="🎰 Spinning...",
                description=f"```\n╔══════════════╗\n║  {results[0]}  │  {reel2}  │  🎲  ║\n╚══════════════╝\n```",
                color=discord.Color.blue()
            )
            anim_embed.set_footer(text=f"Bet: {bet:,} pts")
            await message.edit(embed=anim_embed)
            await asyncio.sleep(0.3)
        
        # Reel 2 stops
        anim_embed = discord.Embed(
            title="🎰 Spinning...",
            description=f"```\n╔══════════════╗\n║  {results[0]}  │  {results[1]}  │  🎲  ║\n╚══════════════╝\n```",
            color=discord.Color.blue()
        )
        anim_embed.set_footer(text=f"Bet: {bet:,} pts")
        await message.edit(embed=anim_embed)
        await asyncio.sleep(0.5)
        
        # Reel 3 spinning
        for _ in range(4):
            reel3 = random.choice(spinning_symbols)
            anim_embed = discord.Embed(
                title="🎰 Spinning...",
                description=f"```\n╔══════════════╗\n║  {results[0]}  │  {results[1]}  │  {reel3}  ║\n╚══════════════╝\n```",
                color=discord.Color.blue()
            )
            anim_embed.set_footer(text=f"Bet: {bet:,} pts")
            await message.edit(embed=anim_embed)
            await asyncio.sleep(0.3)
        
        # Reel 3 stops - show final result
        await asyncio.sleep(0.3)
        
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
        
        # Create final embed
        slot_display = f"╔══════════════╗\n║  {results[0]}  │  {results[1]}  │  {results[2]}  ║\n╚══════════════╝"
        
        embed = discord.Embed(title=title, description=f"```{slot_display}```", color=color)
        
        if profit > 0:
            embed.add_field(name="💰 Won", value=f"+**{profit:,}** pts", inline=True)
        else:
            embed.add_field(name="📉 Lost", value=f"**{profit:,}** pts", inline=True)
        
        embed.add_field(name="💳 Balance", value=f"**{new_balance:,}** pts", inline=True)
        embed.set_footer(text=f"Bet: {bet:,} pts")
        
        await message.edit(embed=embed)
    
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
    # MULTIPLAYER GAMES - HANGMAN
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="hangman", aliases=["hm"])
    @commands.cooldown(1, 5, commands.BucketType.channel)
    async def hangman_game(self, ctx):
        """Multiplayer Hangman! Play in DMs, results shown in channel."""
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
        
        # Create join embed
        embed = discord.Embed(
            title="🕵️ Multiplayer Hangman Starting!",
            description=f"**Word Length:** {len(word)} letters\n\n"
                       f"Click **Join Game** to play in your DMs!\n"
                       f"Wrong guesses lose **10 stella points** each.\n"
                       f"(You can play even with 0 points!)\n\n"
                       f"Game starts in **30 seconds** or when 5 players join.",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Results will be shown here!")
        
        view = HangmanJoinView(self, game_id)
        msg = await ctx.reply(embed=embed, view=view, mention_author=False)
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
                    title="🕵️ Hangman",
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
        
        # Create join embed
        embed = discord.Embed(
            title="🟩 Multiplayer Wordle Starting!",
            description=f"Guess the **5-letter word** in 6 tries!\n\n"
                       f"Click **Join Game** to play in your DMs!\n"
                       f"Wrong guesses lose **15 stella points** each.\n"
                       f"(You can play even with 0 points!)\n\n"
                       f"Game starts in **30 seconds** or when 5 players join.",
            color=discord.Color.green()
        )
        embed.set_footer(text="Results will be shown here!")
        
        view = WordleJoinView(self, game_id)
        msg = await ctx.reply(embed=embed, view=view, mention_author=False)
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
        
        # Send DMs to all players
        for user_id, player_data in game["players"].items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                view = WordleGuessView(self, game_id, user_id)
                
                embed = discord.Embed(
                    title="🟩 Your Wordle Game",
                    description="⬜⬜⬜⬜⬜\n⬜⬜⬜⬜⬜\n⬜⬜⬜⬜⬜\n⬜⬜⬜⬜⬜\n⬜⬜⬜⬜⬜\n⬜⬜⬜⬜⬜\n\n"
                               f"Click **Submit Guess** to enter a 5-letter word!\n"
                               f"❌ Wrong guess = **-15 stella points**",
                    color=discord.Color.green()
                )
                embed.add_field(name="Attempts", value="0/6", inline=True)
                
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
        
        # Update channel message
        await self._update_wordle_leaderboard(game_id)
    
    async def _update_wordle_leaderboard(self, game_id: str):
        """Update the wordle leaderboard in the channel"""
        if game_id not in self.active_games:
            return
        
        game = self.active_games[game_id]
        msg = game["game_msg"]
        
        # Build leaderboard
        leaderboard = []
        for user_id, player_data in game["players"].items():
            try:
                user = await self.bot.fetch_user(int(user_id))
                attempts = len(player_data["attempts"])
                status = player_data["status"]
                
                if status == "won":
                    emoji = "🏆"
                elif status == "lost":
                    emoji = "💀"
                else:
                    emoji = "🎮"
                
                # Show last attempt result
                last_result = ""
                if player_data["attempts"]:
                    last_result = player_data["attempts"][-1]["result"]
                
                leaderboard.append(f"{emoji} **{user.display_name}** - {attempts}/6 {last_result}")
            except:
                pass
        
        embed = discord.Embed(
            title="🟩 Wordle - Live Results",
            description="\n".join(leaderboard) if leaderboard else "No players",
            color=discord.Color.green()
        )
        
        # Check if game is over
        all_done = all(p["status"] != "playing" for p in game["players"].values())
        if all_done:
            winners = [uid for uid, p in game["players"].items() if p["status"] == "won"]
            embed.add_field(name="Game Over!", value=f"Word was: **{game['word']}**", inline=False)
            if winners:
                embed.color = discord.Color.gold()
            else:
                embed.color = discord.Color.red()
        
        try:
            await msg.edit(embed=embed)
        except:
            pass
    
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

        view = Memo(ctx, shuffled, chosen, msg, bot=self.bot)
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
