import discord
from discord.ext import commands
import random
import asyncio
from datetime import datetime
from bot.cogs.quest import Quest_Data

class TicTacToeButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if interaction.user.id != view.current_player.id:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        
        if view.board[self.y][self.x] is not None:
            return await interaction.response.send_message("Already taken!", ephemeral=True)
        
        view.board[self.y][self.x] = view.current_symbol
        self.label = view.current_symbol
        self.style = discord.ButtonStyle.danger if view.current_symbol == "X" else discord.ButtonStyle.primary
        self.disabled = True
        
        winner = view.check_winner()
        if winner:
            view.disable_all()
            if winner == "X":
                result = f"{view.player_x.mention} wins!"
                await view.cog.quest_data.add_balance(str(view.player_x.id), str(interaction.guild.id), view.bet * 2)
            else:
                result = f"{view.player_o.mention} wins!"
                await view.cog.quest_data.add_balance(str(view.player_o.id), str(interaction.guild.id), view.bet * 2)
            embed = discord.Embed(title="Tic Tac Toe", description=result, color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=view)
            view.stop()
        elif view.is_full():
            view.disable_all()
            await view.cog.quest_data.add_balance(str(view.player_x.id), str(interaction.guild.id), view.bet)
            await view.cog.quest_data.add_balance(str(view.player_o.id), str(interaction.guild.id), view.bet)
            embed = discord.Embed(title="Tic Tac Toe", description="It's a draw! Bets returned.", color=discord.Color.light_gray())
            await interaction.response.edit_message(embed=embed, view=view)
            view.stop()
        else:
            view.switch_player()
            embed = discord.Embed(title="Tic Tac Toe", description=f"{view.current_player.mention}'s turn ({view.current_symbol})\nBet: {view.bet:,} pts each", color=discord.Color.blue())
            await interaction.response.edit_message(embed=embed, view=view)

class TicTacToeView(discord.ui.View):
    def __init__(self, cog, player_x: discord.Member, player_o: discord.Member, bet: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.player_x = player_x
        self.player_o = player_o
        self.bet = bet
        self.current_player = player_x
        self.current_symbol = "X"
        self.board = [[None for _ in range(3)] for _ in range(3)]
        
        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))
    
    def switch_player(self):
        if self.current_player == self.player_x:
            self.current_player = self.player_o
            self.current_symbol = "O"
        else:
            self.current_player = self.player_x
            self.current_symbol = "X"
    
    def check_winner(self):
        for row in self.board:
            if row[0] == row[1] == row[2] and row[0] is not None:
                return row[0]
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] and self.board[0][col] is not None:
                return self.board[0][col]
        if self.board[0][0] == self.board[1][1] == self.board[2][2] and self.board[0][0] is not None:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] and self.board[0][2] is not None:
            return self.board[0][2]
        return None
    
    def is_full(self):
        return all(self.board[y][x] is not None for y in range(3) for x in range(3))
    
    def disable_all(self):
        for item in self.children:
            item.disabled = True
    
    async def on_timeout(self):
        self.disable_all()

class TicTacToeChallenge(discord.ui.View):
    def __init__(self, cog, challenger: discord.Member, opponent: discord.Member, bet: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet
        self.message = None
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        
        gid = str(interaction.guild.id)
        bal = await self.cog.quest_data.get_balance(str(self.opponent.id), gid)
        if bal < self.bet:
            return await interaction.response.send_message(f"You need {self.bet:,} pts!", ephemeral=True)
        
        await self.cog.quest_data.add_balance(str(self.opponent.id), gid, -self.bet)
        
        view = TicTacToeView(self.cog, self.challenger, self.opponent, self.bet)
        embed = discord.Embed(title="Tic Tac Toe", description=f"{self.challenger.mention}'s turn (X)\nBet: {self.bet:,} pts each", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=view)
        self.stop()
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        
        await self.cog.quest_data.add_balance(str(self.challenger.id), str(interaction.guild.id), self.bet)
        embed = discord.Embed(title="Challenge Declined", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    async def on_timeout(self):
        await self.cog.quest_data.add_balance(str(self.challenger.id), str(self.message.guild.id), self.bet)
        try:
            await self.message.edit(embed=discord.Embed(title="Challenge Expired", color=discord.Color.dark_gray()), view=None)
        except: pass

class FishingView(discord.ui.View):
    def __init__(self, cog, user: discord.Member, guild_id: str):
        super().__init__(timeout=30)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.caught = False
        self.fish_appeared = False
        self.message = None
    
    @discord.ui.button(label="🎣 Cast", style=discord.ButtonStyle.primary)
    async def cast_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Not your rod!", ephemeral=True)
        
        if self.fish_appeared:
            return
        
        button.disabled = True
        button.label = "Waiting..."
        await interaction.response.edit_message(embed=discord.Embed(title="🎣 Fishing", description="Line cast... waiting for a bite...", color=discord.Color.blue()), view=self)
        
        await asyncio.sleep(random.uniform(2, 5))
        
        if self.caught:
            return
        
        self.fish_appeared = True
        self.children[1].disabled = False
        self.children[1].style = discord.ButtonStyle.success
        
        embed = discord.Embed(title="🎣 Fishing", description="**🐟 FISH ON THE LINE! REEL IT IN!**", color=discord.Color.green())
        await self.message.edit(embed=embed, view=self)
        
        await asyncio.sleep(2.5)
        
        if not self.caught:
            self.disable_all()
            embed = discord.Embed(title="🎣 Fishing", description="The fish got away! Too slow!", color=discord.Color.red())
            await self.message.edit(embed=embed, view=self)
            self.stop()
    
    @discord.ui.button(label="🔄 Reel", style=discord.ButtonStyle.secondary, disabled=True)
    async def reel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message("Not your rod!", ephemeral=True)
        
        if not self.fish_appeared or self.caught:
            return
        
        self.caught = True
        self.disable_all()
        
        fish_types = [
            ("🐟 Common Fish", 10, 30, 0.4),
            ("🐠 Tropical Fish", 30, 60, 0.25),
            ("🐡 Pufferfish", 50, 100, 0.15),
            ("🦈 Shark", 100, 200, 0.1),
            ("🐋 Whale", 200, 500, 0.07),
            ("👑 Golden Fish", 500, 1000, 0.03),
        ]
        
        roll = random.random()
        cumulative = 0
        caught_fish = fish_types[0]
        for fish in fish_types:
            cumulative += fish[3]
            if roll < cumulative:
                caught_fish = fish
                break
        
        reward = random.randint(caught_fish[1], caught_fish[2])
        await self.cog.quest_data.add_balance(str(self.user.id), self.guild_id, reward)
        
        embed = discord.Embed(title="🎣 Nice Catch!", description=f"You caught a **{caught_fish[0]}**!\n\n+**{reward:,}** pts", color=discord.Color.gold())
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    def disable_all(self):
        for item in self.children:
            item.disabled = True

class RockPaperScissorsView(discord.ui.View):
    def __init__(self, cog, player1: discord.Member, player2: discord.Member, bet: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.player1 = player1
        self.player2 = player2
        self.bet = bet
        self.choices = {}
        self.message = None
    
    @discord.ui.button(label="🪨 Rock", style=discord.ButtonStyle.secondary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "rock")
    
    @discord.ui.button(label="📄 Paper", style=discord.ButtonStyle.secondary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "paper")
    
    @discord.ui.button(label="✂️ Scissors", style=discord.ButtonStyle.secondary)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "scissors")
    
    async def make_choice(self, interaction: discord.Interaction, choice: str):
        if interaction.user.id not in [self.player1.id, self.player2.id]:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        
        if interaction.user.id in self.choices:
            return await interaction.response.send_message("Already chose!", ephemeral=True)
        
        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"You chose {choice}!", ephemeral=True)
        
        if len(self.choices) == 2:
            await self.resolve()
    
    async def resolve(self):
        c1 = self.choices[self.player1.id]
        c2 = self.choices[self.player2.id]
        
        wins = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        
        gid = str(self.message.guild.id)
        
        if c1 == c2:
            await self.cog.quest_data.add_balance(str(self.player1.id), gid, self.bet)
            await self.cog.quest_data.add_balance(str(self.player2.id), gid, self.bet)
            result = "It's a tie! Bets returned."
            color = discord.Color.light_gray()
        elif wins[c1] == c2:
            await self.cog.quest_data.add_balance(str(self.player1.id), gid, self.bet * 2)
            result = f"{self.player1.mention} wins!"
            color = discord.Color.gold()
        else:
            await self.cog.quest_data.add_balance(str(self.player2.id), gid, self.bet * 2)
            result = f"{self.player2.mention} wins!"
            color = discord.Color.gold()
        
        embed = discord.Embed(title="Rock Paper Scissors", description=f"{self.player1.mention}: {emojis[c1]}\n{self.player2.mention}: {emojis[c2]}\n\n**{result}**", color=color)
        self.disable_all()
        await self.message.edit(embed=embed, view=self)
        self.stop()
    
    def disable_all(self):
        for item in self.children:
            item.disabled = True
    
    async def on_timeout(self):
        gid = str(self.message.guild.id)
        if self.player1.id not in self.choices:
            await self.cog.quest_data.add_balance(str(self.player1.id), gid, self.bet)
        if self.player2.id not in self.choices:
            await self.cog.quest_data.add_balance(str(self.player2.id), gid, self.bet)
        self.disable_all()
        try:
            await self.message.edit(embed=discord.Embed(title="Game Expired", color=discord.Color.dark_gray()), view=self)
        except: pass

class RPSChallenge(discord.ui.View):
    def __init__(self, cog, challenger: discord.Member, opponent: discord.Member, bet: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet
        self.message = None
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        
        gid = str(interaction.guild.id)
        bal = await self.cog.quest_data.get_balance(str(self.opponent.id), gid)
        if bal < self.bet:
            return await interaction.response.send_message(f"You need {self.bet:,} pts!", ephemeral=True)
        
        await self.cog.quest_data.add_balance(str(self.opponent.id), gid, -self.bet)
        
        view = RockPaperScissorsView(self.cog, self.challenger, self.opponent, self.bet)
        embed = discord.Embed(title="Rock Paper Scissors", description=f"{self.challenger.mention} vs {self.opponent.mention}\nBet: {self.bet:,} pts each\n\nBoth players choose!", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = await interaction.original_response()
        self.stop()
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        
        await self.cog.quest_data.add_balance(str(self.challenger.id), str(interaction.guild.id), self.bet)
        await interaction.response.edit_message(embed=discord.Embed(title="Challenge Declined", color=discord.Color.red()), view=None)
        self.stop()
    
    async def on_timeout(self):
        await self.cog.quest_data.add_balance(str(self.challenger.id), str(self.message.guild.id), self.bet)
        try:
            await self.message.edit(embed=discord.Embed(title="Challenge Expired", color=discord.Color.dark_gray()), view=None)
        except: pass

class ConnectFourButton(discord.ui.Button):
    def __init__(self, col: int):
        super().__init__(style=discord.ButtonStyle.secondary, label=str(col + 1))
        self.col = col

    async def callback(self, interaction: discord.Interaction):
        view: ConnectFourView = self.view
        if interaction.user.id != view.current_player.id:
            return await interaction.response.send_message("Not your turn!", ephemeral=True)
        
        row = view.drop_piece(self.col)
        if row == -1:
            return await interaction.response.send_message("Column full!", ephemeral=True)
        
        winner = view.check_winner(row, self.col)
        if winner:
            view.disable_all()
            if winner == 1:
                result = f"🔴 {view.player1.mention} wins!"
                await view.cog.quest_data.add_balance(str(view.player1.id), str(interaction.guild.id), view.bet * 2)
            else:
                result = f"🟡 {view.player2.mention} wins!"
                await view.cog.quest_data.add_balance(str(view.player2.id), str(interaction.guild.id), view.bet * 2)
            embed = discord.Embed(title="Connect Four", description=f"{view.render_board()}\n\n{result}", color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=view)
            view.stop()
        elif view.is_full():
            view.disable_all()
            await view.cog.quest_data.add_balance(str(view.player1.id), str(interaction.guild.id), view.bet)
            await view.cog.quest_data.add_balance(str(view.player2.id), str(interaction.guild.id), view.bet)
            embed = discord.Embed(title="Connect Four", description=f"{view.render_board()}\n\nDraw! Bets returned.", color=discord.Color.light_gray())
            await interaction.response.edit_message(embed=embed, view=view)
            view.stop()
        else:
            view.switch_player()
            symbol = "🔴" if view.current_turn == 1 else "🟡"
            embed = discord.Embed(title="Connect Four", description=f"{view.render_board()}\n\n{symbol} {view.current_player.mention}'s turn", color=discord.Color.blue())
            await interaction.response.edit_message(embed=embed, view=view)

class ConnectFourView(discord.ui.View):
    def __init__(self, cog, player1: discord.Member, player2: discord.Member, bet: int):
        super().__init__(timeout=180)
        self.cog = cog
        self.player1 = player1
        self.player2 = player2
        self.bet = bet
        self.current_turn = 1
        self.current_player = player1
        self.board = [[0 for _ in range(7)] for _ in range(6)]
        
        for col in range(7):
            self.add_item(ConnectFourButton(col))
    
    def drop_piece(self, col: int) -> int:
        for row in range(5, -1, -1):
            if self.board[row][col] == 0:
                self.board[row][col] = self.current_turn
                return row
        return -1
    
    def switch_player(self):
        if self.current_turn == 1:
            self.current_turn = 2
            self.current_player = self.player2
        else:
            self.current_turn = 1
            self.current_player = self.player1
    
    def render_board(self) -> str:
        symbols = {0: "⚫", 1: "🔴", 2: "🟡"}
        lines = []
        for row in self.board:
            lines.append("".join(symbols[cell] for cell in row))
        lines.append("1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣")
        return "\n".join(lines)
    
    def check_winner(self, row: int, col: int) -> int:
        piece = self.board[row][col]
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        
        for dr, dc in directions:
            count = 1
            for d in [1, -1]:
                r, c = row + dr * d, col + dc * d
                while 0 <= r < 6 and 0 <= c < 7 and self.board[r][c] == piece:
                    count += 1
                    r += dr * d
                    c += dc * d
            if count >= 4:
                return piece
        return 0
    
    def is_full(self):
        return all(self.board[0][c] != 0 for c in range(7))
    
    def disable_all(self):
        for item in self.children:
            item.disabled = True

class C4Challenge(discord.ui.View):
    def __init__(self, cog, challenger: discord.Member, opponent: discord.Member, bet: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.challenger = challenger
        self.opponent = opponent
        self.bet = bet
        self.message = None
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        
        gid = str(interaction.guild.id)
        bal = await self.cog.quest_data.get_balance(str(self.opponent.id), gid)
        if bal < self.bet:
            return await interaction.response.send_message(f"You need {self.bet:,} pts!", ephemeral=True)
        
        await self.cog.quest_data.add_balance(str(self.opponent.id), gid, -self.bet)
        
        view = ConnectFourView(self.cog, self.challenger, self.opponent, self.bet)
        embed = discord.Embed(title="Connect Four", description=f"{view.render_board()}\n\n🔴 {self.challenger.mention}'s turn", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=view)
        self.stop()
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message("Not for you!", ephemeral=True)
        
        await self.cog.quest_data.add_balance(str(self.challenger.id), str(interaction.guild.id), self.bet)
        await interaction.response.edit_message(embed=discord.Embed(title="Challenge Declined", color=discord.Color.red()), view=None)
        self.stop()
    
    async def on_timeout(self):
        await self.cog.quest_data.add_balance(str(self.challenger.id), str(self.message.guild.id), self.bet)
        try:
            await self.message.edit(embed=discord.Embed(title="Challenge Expired", color=discord.Color.dark_gray()), view=None)
        except: pass

class MiniGames(commands.Cog):
    """Mini-games with buttons - TicTacToe, Fishing, RPS, Connect Four"""
    
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
    
    @commands.command(name="tictactoe", aliases=["ttt"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def tictactoe_cmd(self, ctx, opponent: discord.Member, bet: int = 50):
        """Play Tic Tac Toe against another player"""
        if opponent.id == ctx.author.id or opponent.bot:
            return await ctx.reply("Invalid opponent!", mention_author=False)
        
        if bet < 10 or bet > 5000:
            return await ctx.reply("Bet must be 10-5,000 pts!", mention_author=False)
        
        gid = str(ctx.guild.id)
        bal = await self.quest_data.get_balance(str(ctx.author.id), gid)
        if bal < bet:
            return await ctx.reply(f"You need {bet:,} pts!", mention_author=False)
        
        await self.quest_data.add_balance(str(ctx.author.id), gid, -bet)
        
        view = TicTacToeChallenge(self, ctx.author, opponent, bet)
        embed = discord.Embed(title="Tic Tac Toe Challenge", description=f"{ctx.author.mention} challenges {opponent.mention}!\nBet: {bet:,} pts each", color=discord.Color.blue())
        view.message = await ctx.send(embed=embed, view=view)
    
    @commands.command(name="fish", aliases=["fishing"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def fish_cmd(self, ctx):
        """Go fishing! Cast your line and catch fish for rewards"""
        view = FishingView(self, ctx.author, str(ctx.guild.id))
        embed = discord.Embed(title="🎣 Fishing", description="Press **Cast** to throw your line!", color=discord.Color.blue())
        view.message = await ctx.reply(embed=embed, view=view, mention_author=False)
    
    @commands.command(name="rps", aliases=["rockpaperscissors"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def rps_cmd(self, ctx, opponent: discord.Member, bet: int = 50):
        """Play Rock Paper Scissors against another player"""
        if opponent.id == ctx.author.id or opponent.bot:
            return await ctx.reply("Invalid opponent!", mention_author=False)
        
        if bet < 10 or bet > 5000:
            return await ctx.reply("Bet must be 10-5,000 pts!", mention_author=False)
        
        gid = str(ctx.guild.id)
        bal = await self.quest_data.get_balance(str(ctx.author.id), gid)
        if bal < bet:
            return await ctx.reply(f"You need {bet:,} pts!", mention_author=False)
        
        await self.quest_data.add_balance(str(ctx.author.id), gid, -bet)
        
        view = RPSChallenge(self, ctx.author, opponent, bet)
        embed = discord.Embed(title="Rock Paper Scissors Challenge", description=f"{ctx.author.mention} challenges {opponent.mention}!\nBet: {bet:,} pts each", color=discord.Color.blue())
        view.message = await ctx.send(embed=embed, view=view)
    
    @commands.command(name="connect4", aliases=["c4", "connectfour"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def connect4_cmd(self, ctx, opponent: discord.Member, bet: int = 50):
        """Play Connect Four against another player"""
        if opponent.id == ctx.author.id or opponent.bot:
            return await ctx.reply("Invalid opponent!", mention_author=False)
        
        if bet < 10 or bet > 5000:
            return await ctx.reply("Bet must be 10-5,000 pts!", mention_author=False)
        
        gid = str(ctx.guild.id)
        bal = await self.quest_data.get_balance(str(ctx.author.id), gid)
        if bal < bet:
            return await ctx.reply(f"You need {bet:,} pts!", mention_author=False)
        
        await self.quest_data.add_balance(str(ctx.author.id), gid, -bet)
        
        view = C4Challenge(self, ctx.author, opponent, bet)
        embed = discord.Embed(title="Connect Four Challenge", description=f"{ctx.author.mention} challenges {opponent.mention}!\nBet: {bet:,} pts each", color=discord.Color.blue())
        view.message = await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(MiniGames(bot))
