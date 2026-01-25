"""
Gambling Commands - Slots, Coinflip, Dice, Guess, Blackjack
"""

from discord.ext import commands
import random
import asyncio
import io
import discord
from typing import Optional
from bot.utils.cogs.game import *
from bot.utils.cogs.game.images import *
from bot.utils.cogs.game.blackjack import Deck, Card, calculate_hand_value
from bot.utils.cogs.game.blackjack_view import BlackjackView
from bot.utils.cogs.game.const import *
from bot.utils.cogs.game.view import DoubleOrNothingView
from bot.cogs.quest import Quest_Data
import logging

logger = logging.getLogger(__name__)

class Gamble(commands.Cog):
    """🎰 Gambling games - Slots, Coinflip, Dice, Blackjack & more!"""
    
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        self.user_cooldowns = {}
    
    async def check_timer(self, ctx, command: str) -> Optional[str]:
        """Check if user can use command based on timer config"""
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id)
        config = get_timer_config(command)
        
        # Check cooldown
        remaining = await self.check_cooldown(user_id, f"{command}_main", config["cooldown"], guild_id)
        if remaining:
            wait_time = self.format_time(remaining)
            return format_cooldown_message(remaining, command)
        
        # Check uses
        current_uses = await self.get_current_uses(user_id, guild_id, command)
        if current_uses >= config["max_uses"]:
            return f"⏰ You've used all **{config['max_uses']}** {command} plays! Wait for cooldown to reset."
        
        return None
    
    async def check_cooldown(self, user_id: str, cooldown_key: str, cooldown_seconds: int, guild_id: str) -> Optional[int]:
        """Check if user is on cooldown. Returns remaining seconds or None."""
        from datetime import datetime, timezone, timedelta
        
        db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
        server_col = db["Servers"]
        
        result = await server_col.find_one(
            {"guild_id": guild_id},
            {f"members.{user_id}.cooldowns.{cooldown_key}": 1}
        )
        
        if result and "members" in result:
            member_data = result["members"].get(user_id, {})
            cooldowns = member_data.get("cooldowns", {})
            last_use = cooldowns.get(cooldown_key)
            
            if last_use:
                elapsed = (datetime.now(timezone.utc) - last_use).total_seconds()
                if elapsed < cooldown_seconds:
                    return int(cooldown_seconds - elapsed)
        
        return None
    
    async def set_cooldown(self, user_id: str, cooldown_key: str, guild_id: str = None):
        """Set cooldown for a user"""
        from datetime import datetime, timezone
        
        db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
        server_col = db["Servers"]
        
        if guild_id:
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.cooldowns.{cooldown_key}": datetime.now(timezone.utc)}},
                upsert=True
            )
    
    async def get_current_uses(self, user_id: str, guild_id: str, command: str) -> int:
        """Get current uses for a command"""
        db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
        server_col = db["Servers"]
        
        result = await server_col.find_one(
            {"guild_id": guild_id},
            {f"members.{user_id}.command_uses.{command}": 1}
        )
        
        if result and "members" in result:
            member_data = result["members"].get(user_id, {})
            return member_data.get("command_uses", {}).get(command, 0)
        
        return 0
    
    async def increment_plays(self, user_id: str, guild_id: str, command: str):
        """Increment play count for a command"""
        db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
        server_col = db["Servers"]
        
        await server_col.update_one(
            {"guild_id": guild_id},
            {"$inc": {f"members.{user_id}.command_uses.{command}": 1}},
            upsert=True
        )
    
    def format_time(self, seconds: int) -> str:
        """Format seconds into readable time string"""
        from datetime import timedelta
        td = timedelta(seconds=seconds)
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_slot_symbol(self) -> str:
        """Get random slot symbol based on weights"""
        symbols = list(SLOT_SYMBOLS.keys())
        weights = [SLOT_SYMBOLS[s]["weight"] for s in symbols]
        return random.choices(symbols, weights=weights)[0]
    
    def parse_bet(self, bet_str: str) -> int:
        """Parse a bet string that may contain commas (e.g., '5,000' -> 5000)."""
        if bet_str is None:
            return 50
        cleaned = str(bet_str).replace(",", "").replace(" ", "")
        return int(cleaned)
    
    # ═══════════════════════════════════════════════════════════════
    # GAMBLING COMMANDS
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="slots", aliases=["slot", "spin"])
    @commands.cooldown(3, 1800, commands.BucketType.user)
    async def slots_command(self, ctx, bet: int = 50):
        """Spin the slot machine and match symbols to win multiplied rewards"""
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
        """Generate slot machine GIF - imported from Games class"""
        import math
        from PIL import Image, ImageDraw, ImageFont
        
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
        symbol_height = 45
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
        
        # Load font
        try:
            font = _load_emoji_font(28)
        except:
            font = ImageFont.load_default()
        
        # Find result indices
        result_indices = [all_symbols.index(r) for r in results]
        
        # Animation parameters
        initial_velocity = 18.0
        reel_stop_times = [1.6, 2.6, 3.8]
        fps = 30
        total_duration = 5.0
        total_frames = int(total_duration * fps)
        
        # Initialize reel states
        reel_positions_anim = [0.0, 0.0, 0.0]
        reel_velocities = [initial_velocity, initial_velocity, initial_velocity]
        reel_stopped = [False, False, False]
        reel_landing = [False, False, False]
        
        for frame_idx in range(total_frames):
            current_time = frame_idx / fps
            
            img = Image.new('RGB', (width, height), bg_dark)
            draw = ImageDraw.Draw(img)
            
            # Draw machine frame
            draw.rounded_rectangle([3, 3, width-1, height-1], radius=15, fill=frame_shadow)
            draw.rounded_rectangle([0, 0, width-4, height-4], radius=15, fill=bg_dark, outline=frame_gold, width=4)
            draw.rounded_rectangle([8, 8, width-12, height-12], radius=12, outline=(40, 35, 50), width=1)
            
            # Update physics for each reel
            for reel_idx in range(3):
                stop_time = reel_stop_times[reel_idx]
                target_pos = result_indices[reel_idx]
                
                if reel_stopped[reel_idx]:
                    reel_positions_anim[reel_idx] = target_pos
                    reel_velocities[reel_idx] = 0
                elif current_time >= stop_time - 0.4 and not reel_landing[reel_idx]:
                    reel_landing[reel_idx] = True
                
                if reel_landing[reel_idx] and not reel_stopped[reel_idx]:
                    landing_progress = (current_time - (stop_time - 0.4)) / 0.4
                    landing_progress = min(1.0, max(0.0, landing_progress))
                    smooth = landing_progress * landing_progress * (3 - 2 * landing_progress)
                    
                    spin_pos = reel_positions_anim[reel_idx]
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
                    time_to_landing = (stop_time - 0.4) - current_time
                    if time_to_landing < 0.8:
                        ease = time_to_landing / 0.8
                        ease = 0.4 + ease * 0.6
                        current_vel = initial_velocity * ease
                    else:
                        current_vel = initial_velocity
                    
                    reel_velocities[reel_idx] = current_vel
                    reel_positions_anim[reel_idx] += current_vel / fps
                    reel_positions_anim[reel_idx] = reel_positions_anim[reel_idx] % num_symbols
            
            # Draw each reel
            for reel_idx, x in enumerate(reel_positions):
                draw.rounded_rectangle([x-3, reel_y-3, x + reel_width+3, reel_y + reel_height+3], 
                                       radius=8, fill=(3, 3, 6))
                draw.rounded_rectangle([x, reel_y, x + reel_width, reel_y + reel_height], 
                                       radius=6, fill=reel_bg)
                
                reel_center_y = reel_y + reel_height // 2
                pos = reel_positions_anim[reel_idx]
                is_stopped = reel_stopped[reel_idx]
                velocity = reel_velocities[reel_idx]
                
                # Draw symbols
                for offset in [-1, 0, 1]:
                    symbol_idx = int(pos + offset) % num_symbols
                    symbol = all_symbols[symbol_idx]
                    frac = pos - int(pos)
                    symbol_y = reel_center_y + (offset - frac) * symbol_height
                    
                    if reel_y - symbol_height < symbol_y < reel_y + reel_height + symbol_height:
                        symbol_color = SLOT_SYMBOL_COLORS.get(symbol, (255, 255, 255))
                        
                        if velocity > 5 and not is_stopped:
                            fade = max(0.3, 1.0 - (velocity / initial_velocity) * 0.6)
                            symbol_color = tuple(int(c * fade) for c in symbol_color)
                        
                        bbox = draw.textbbox((0, 0), symbol, font=font)
                        text_w = bbox[2] - bbox[0]
                        text_x = x + (reel_width - text_w) // 2
                        text_y = int(symbol_y - symbol_height // 2 + 5)
                        
                        if offset == 0 and is_stopped:
                            glow = tuple(min(255, int(c * 0.4)) for c in symbol_color)
                            for glow_offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                draw.text((text_x + glow_offset[0], text_y + glow_offset[1]), 
                                         symbol, font=font, fill=glow)
                        
                        draw.text((text_x, text_y), symbol, font=font, fill=symbol_color)
                
                # Gradient fade
                for i in range(12):
                    fade_color = (bg_dark[0], bg_dark[1], bg_dark[2])
                    draw.line([(x, reel_y + i), (x + reel_width, reel_y + i)], 
                             fill=tuple(int(c * (1 - i/12)) for c in fade_color), width=1)
                    draw.line([(x, reel_y + reel_height - i), (x + reel_width, reel_y + reel_height - i)], 
                             fill=tuple(int(c * (1 - i/12)) for c in fade_color), width=1)
                
                if is_stopped:
                    draw.rounded_rectangle([x-1, reel_y-1, x + reel_width+1, reel_y + reel_height+1], 
                                           radius=7, outline=result_color, width=2)
            
            # Payline
            line_y = reel_y + reel_height // 2
            draw.polygon([(32, line_y), (18, line_y - 10), (18, line_y + 10)], fill=frame_gold)
            draw.polygon([(width - 32, line_y), (width - 18, line_y - 10), (width - 18, line_y + 10)], fill=frame_gold)
            draw.line([(35, line_y), (width - 35, line_y)], fill=(frame_gold[0]//3, frame_gold[1]//3, frame_gold[2]//3), width=1)
            
            frames.append(img)
            durations.append(33)
        
        # Hold frames
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
            loop=0
        )
        gif_buffer.seek(0)
        return gif_buffer
    
    async def _run_slot_machine(self, channel, user, bet: int):
        """Run the slot machine game"""
        guild_id = str(channel.guild.id)
        user_id = str(user.id)
        
        balance = await self.quest_data.get_balance(user_id, guild_id)
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        results = [self.get_slot_symbol() for _ in range(3)]
        
        gif_task = asyncio.get_event_loop().run_in_executor(
            None, self._generate_slot_gif, results
        )
        
        spin_embed = discord.Embed(
            title="🎰 Slot Machine",
            description=f"**{user.display_name}** is spinning...\n💰 Bet: **{bet:,}** pts",
            color=discord.Color.blue()
        )
        spin_msg = await channel.send(embed=spin_embed)
        
        gif_buffer = await gif_task
        
        # Determine outcome
        winnings = 0
        if results[0] == results[1] == results[2]:
            multiplier = SLOT_SYMBOLS[results[0]]["multiplier"]
            winnings = bet * multiplier
            final_title = "🎰 Jackpot!"
            final_color = discord.Color.gold()
        elif results[0] == results[1] or results[1] == results[2] or results[0] == results[2]:
            winnings = int(bet * 1.5)
            final_title = "🎰 Double Match!"
            final_color = discord.Color.green()
        else:
            final_title = "🎰 No Match"
            final_color = discord.Color.red()
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        
        final_embed = discord.Embed(
            title=final_title,
            color=final_color
        )
        
        if winnings > 0:
            final_embed.add_field(name="Won", value=f"+{winnings:,} pts", inline=True)
        else:
            final_embed.add_field(name="Lost", value=f"{abs(winnings):,} pts", inline=True)
        
        final_embed.add_field(name="Balance", value=f"{new_balance:,} pts", inline=True)
        final_embed.set_image(url="attachment://slots.gif")
        
        file = discord.File(gif_buffer, filename="slots.gif")
        await spin_msg.edit(embed=final_embed, attachments=[file])
    
    @commands.command(name="coinflip", aliases=["cf", "flip"])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def coinflip_command(self, ctx, choice: str = None, bet: str = "50"):
        """Flip a coin and call heads or tails to double your bet"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if choice is None:
            embed = discord.Embed(
                title="🪙 Coin Flip",
                description=f"**How to play:**\n"
                           f"`{ctx.prefix}coinflip <heads/tails> [bet]`\n\n"
                           f"Call it right and **double** your bet!\n"
                           f"Default bet: **50** pts\n\n"
                           f"**Examples:**\n"
                           f"`{ctx.prefix}coinflip heads` - Bet 50 pts on heads\n"
                           f"`{ctx.prefix}coinflip tails 100` - Bet 100 pts on tails",
                color=discord.Color.gold()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Parse bet
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
        
        # Check timer
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
        
        # Set cooldown and deduct bet
        await self.set_cooldown(user_id, "coinflip_command")
        await self.increment_plays(user_id, guild_id, "coinflip")
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Flip
        result = random.choice(["heads", "tails"])
        won = result == choice
        
        spin_embed = discord.Embed(
            title="🪙 Flipping...",
            description=f"You called **{choice.upper()}**!",
            color=discord.Color.gold()
        )
        msg = await ctx.reply(embed=spin_embed, mention_author=False)
        
        await asyncio.sleep(1.2)
        
        if won:
            winnings = bet * 2
            await self.quest_data.add_balance(user_id, guild_id, winnings)
            profit = bet
            title = "🎉 You Won!"
            color = discord.Color.green()
        else:
            winnings = 0
            profit = -bet
            title = "💸 You Lost!"
            color = discord.Color.red()
        
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
        
        if won:
            view = DoubleOrNothingView(self, user_id, guild_id, profit)
            embed.set_footer(text="Double your winnings or cash out!")
            await msg.edit(embed=embed, view=view, attachments=[])
        else:
            await msg.edit(embed=embed, attachments=[])
    
    @commands.command(name="dice", aliases=["roll", "d6"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def dice_command(self, ctx, bet: str = "50", guess: int = None):
        """Roll a six-sided die and guess the number to win multiplied rewards"""
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
        
        # Check timer
        timer_error = await self.check_timer(ctx, "dice")
        if timer_error:
            return await ctx.reply(timer_error, mention_author=False)
        
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < bet:
            return await ctx.reply(f"❌ Need **{bet:,}** but have **{balance:,}** pts!", mention_author=False)
        
        # Set cooldown and deduct bet
        await self.set_cooldown(user_id, "dice_command")
        await self.increment_plays(user_id, guild_id, "dice")
        await self.quest_data.add_balance(user_id, guild_id, -bet)
        
        # Roll
        roll = random.randint(1, 6)
        dice_faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
        
        # Calculate winnings
        diff = abs(roll - guess)
        if diff == 0:
            winnings = bet * 5
            result = "PERFECT!"
            color = discord.Color.gold()
        elif diff == 1:
            winnings = bet * 2
            result = "Close!"
            color = discord.Color.green()
        else:
            winnings = 0
            result = "Miss!"
            color = discord.Color.red()
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        
        embed = discord.Embed(
            title=f"{dice_faces[roll]} {result}",
            description=f"Rolled **{roll}** | You guessed **{guess}**",
            color=color
        )
        
        if winnings > 0:
            embed.add_field(name="Won", value=f"+**{winnings:,}** pts", inline=True)
        else:
            embed.add_field(name="Lost", value=f"**-{bet:,}** pts", inline=True)
        
        embed.add_field(name="Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.command(name="guess", aliases=["number", "guessnumber"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def guess_command(self, ctx, bet: int = 50):
        """Guess a number between 1-100 with rewards based on attempts taken"""
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Check timer
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
        
        # Set cooldown and deduct bet
        await self.set_cooldown(user_id, "guess_command")
        await self.increment_plays(user_id, guild_id, "guess")
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
                    # Perfect guess
                    attempts_taken = len(guesses_list)
                    attempt_multiplier = max(1.0, 6.0 - (attempts_taken - 1) * 0.8)
                    winnings = int(bet * attempt_multiplier)
                    await self.quest_data.add_balance(user_id, guild_id, winnings)
                    new_balance = balance - bet + winnings
                    
                    img_buffer = generate_guess_result_image(guesses_list, secret, True, winnings - bet)
                    file = discord.File(img_buffer, filename="guess_result.png")
                    
                    embed = discord.Embed(
                        title="🎯 PERFECT!",
                        description=f"You got it in **{attempts_taken}** {'guess' if attempts_taken == 1 else 'guesses'}!\n"
                                   f"🎚️ Multiplier: **{attempt_multiplier:.1f}x**\n"
                                   f"💰 Won: **+{winnings - bet:,}** pts\n💳 Balance: **{new_balance:,}** pts",
                        color=discord.Color.gold()
                    )
                    embed.set_image(url="attachment://guess_result.png")
                    return await msg.edit(embed=embed, attachments=[file])
                
                # Update thermometer
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
        
        # Game over
        if guesses_list:
            closest = min(guesses_list, key=lambda x: abs(x - secret))
            diff = abs(closest - secret)
            attempts_taken = len(guesses_list)
            
            if diff == 0:
                base_winnings = bet * 4
            elif diff <= 2:
                base_winnings = int(bet * 1.0)
            elif diff <= 5:
                base_winnings = int(bet * 0.6)
            elif diff <= 10:
                base_winnings = int(bet * 0.2)
            else:
                base_winnings = 0
            
            if base_winnings > 0:
                attempt_multiplier = max(0.7, 1.0 - (attempts_taken - 1) * 0.08)
                profit = int(base_winnings * attempt_multiplier)
                winnings = profit + bet
            else:
                profit = 0
                winnings = 0
        else:
            winnings = 0
        
        if winnings > 0:
            await self.quest_data.add_balance(user_id, guild_id, winnings)
        
        new_balance = balance - bet + winnings
        profit = winnings - bet
        
        img_buffer = generate_guess_result_image(guesses_list, secret, False, profit)
        file = discord.File(img_buffer, filename="guess_result.png")
        
        embed = discord.Embed(
            title="💀 Game Over" if profit < 0 else "✅ Close!",
            description=f"The number was **{secret}**\n"
                       f"{'📉 Lost' if profit < 0 else '💰 Won'}: **{profit:+,}** pts\n"
                       f"💳 Balance: **{new_balance:,}** pts",
            color=discord.Color.green() if profit >= 0 else discord.Color.red()
        )
        embed.set_image(url="attachment://guess_result.png")
        await msg.edit(embed=embed, attachments=[file])
    
    @commands.group(name="blackjack", aliases=["bj"], invoke_without_command=True)
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def blackjack(self, ctx, bet: str = "100"):
        """🃏 Play Blackjack against the dealer! 
        Usage: .blackjack <amount/all/half>
        """
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Parse bet amount
        balance = await self.quest_data.get_balance(user_id, guild_id)
        
        if bet.lower() == "all":
            amount = balance
        elif bet.lower() == "half":
            amount = balance // 2
        else:
            try:
                amount = int(bet.replace(",", ""))
            except ValueError:
                return await ctx.reply("❌ Invalid bet amount!", mention_author=False)
        
        if amount > balance:
            return await ctx.reply(f"❌ You don't have enough points! Balance: **{balance:,}**", mention_author=False)
        if amount <= 0:
            return await ctx.reply("❌ Bet must be positive!", mention_author=False)
        if amount < 10:
            return await ctx.reply("❌ Minimum bet is **10** pts!", mention_author=False)
        if amount > 50000:
            return await ctx.reply("❌ Max bet is 50,000 pts!", mention_author=False)

        # Start game
        deck = Deck()
        player_hand = [deck.draw(), deck.draw()]
        dealer_hand = [deck.draw(), deck.draw()]
        
        # Initial Blackjack check
        player_val = calculate_hand_value(player_hand)
        dealer_val = calculate_hand_value(dealer_hand)
        
        if player_val == 21:
            if dealer_val == 21:
                # Push
                embed = discord.Embed(
                    title="🃏 Blackjack - Push!",
                    description=f"Both got Blackjack! Money returned.\n\n**Your Hand:** {player_hand[0]}, {player_hand[1]}\n**Dealer:** {dealer_hand[0]}, {dealer_hand[1]}",
                    color=discord.Color.gold()
                )
                return await ctx.reply(embed=embed, mention_author=False)
            else:
                # Player Blackjack Win (2.5x payout = 1.5x profit)
                winnings = int(amount * 2.5)
                await self.quest_data.add_balance(user_id, guild_id, winnings)
                new_balance = await self.quest_data.get_balance(user_id, guild_id)
                embed = discord.Embed(
                    title="🃏 Blackjack!",
                    description=f"**Natural 21!** You won **{winnings:,}** pts!\n\n**Your Hand:** {player_hand[0]}, {player_hand[1]}\n**Dealer:** {dealer_hand[0]}, {dealer_hand[1]}\n\n💳 Balance: **{new_balance:,}** pts",
                    color=discord.Color.gold()
                )
                return await ctx.reply(embed=embed, mention_author=False)

        # Deduct bet
        await self.quest_data.add_balance(user_id, guild_id, -amount)
        
        # Create view for gameplay
        view = BlackjackView(self, ctx, amount, deck, player_hand, dealer_hand)
        view.balance = balance - amount  # Set initial balance for display
        
        embed = view.get_embed()
        
        # Generate initial game image
        img_buffer = view.get_game_image("playing")
        file = discord.File(img_buffer, filename="blackjack.png")
        
        view.message = await ctx.reply(embed=embed, file=file, view=view, mention_author=False)

async def setup(bot):
    await bot.add_cog(Gamble(bot))
