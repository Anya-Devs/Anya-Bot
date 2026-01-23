import discord
import asyncio
import io
from bot.utils.cogs.game.blackjack import calculate_hand_value, format_hand
from bot.utils.cogs.game.images import generate_blackjack_image

class BlackjackView(discord.ui.View):
    def __init__(self, cog, ctx, bet, deck, player_hand, dealer_hand):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.bet = bet
        self.deck = deck
        self.player_hand = player_hand
        self.dealer_hand = dealer_hand
        self.message = None
        self.ended = False
        self.balance = 0

    def get_embed(self, status="playing", winnings=0):
        player_val = calculate_hand_value(self.player_hand)
        dealer_val = calculate_hand_value(self.dealer_hand)
        
        color = discord.Color.blue()
        title = "🃏 Blackjack"
        result_text = None
        
        if status == "playing":
            dealer_display = f"{self.dealer_hand[0]} [?]"
            dealer_value_display = "?"
        else:
            dealer_display = format_hand(self.dealer_hand)
            dealer_value_display = str(dealer_val)
            
            if status == "win":
                color = discord.Color.green()
                title = "🃏 Blackjack - You Won!"
                result_text = "WIN"
            elif status == "loss":
                color = discord.Color.red()
                title = "🃏 Blackjack - You Lost"
                result_text = "LOSS"
            elif status == "push":
                color = discord.Color.gold()
                title = "🃏 Blackjack - Push"
                result_text = "PUSH"
            elif status == "bust":
                color = discord.Color.red()
                title = "🃏 Blackjack - BUST!"
                result_text = "BUST"

        embed = discord.Embed(title=title, color=color)
        embed.set_image(url="attachment://blackjack.png")
        embed.set_footer(text=f"Bet: {self.bet:,} pts")
        return embed
    
    def get_game_image(self, status="playing", winnings=0):
        """Generate the blackjack game image."""
        player_val = calculate_hand_value(self.player_hand)
        dealer_val = calculate_hand_value(self.dealer_hand)
        
        hide_dealer = status == "playing"
        result_text = None
        
        if status == "win":
            result_text = "YOU WIN!"
        elif status == "loss":
            result_text = "YOU LOSE"
        elif status == "push":
            result_text = "PUSH - TIE"
        elif status == "bust":
            result_text = "BUST!"
        
        return generate_blackjack_image(
            player_hand=self.player_hand,
            dealer_hand=self.dealer_hand,
            player_value=player_val,
            dealer_value=dealer_val,
            hide_dealer=hide_dealer,
            result=result_text,
            bet=self.bet,
            winnings=winnings,
            balance=self.balance
        )

    async def end_game(self, interaction, result):
        self.ended = True
        
        player_val = calculate_hand_value(self.player_hand)
        dealer_val = calculate_hand_value(self.dealer_hand)
        
        # Calculate Winnings (assuming bet was already deducted)
        winnings = 0
        profit = 0
        if result == "win":
            winnings = self.bet * 2
            profit = self.bet
        elif result == "push":
            winnings = self.bet
            profit = 0
        elif result == "loss" or result == "bust":
            winnings = 0
            profit = -self.bet
            
        if winnings > 0:
            await self.cog.quest_data.add_balance(str(self.ctx.author.id), str(self.ctx.guild.id), winnings)
        
        # Get updated balance
        self.balance = await self.cog.quest_data.get_balance(str(self.ctx.author.id), str(self.ctx.guild.id))
            
        embed = self.get_embed(result, winnings=profit)
        embed.description = f"**Result:** {result.title()}! {'(Dealer Bust)' if dealer_val > 21 else ''}\n**Winnings:** {winnings:,} pts"
        
        # Generate game image
        img_buffer = self.get_game_image(result, winnings=profit)
        file = discord.File(img_buffer, filename="blackjack.png")
        
        self.stop()
        await interaction.response.edit_message(embed=embed, attachments=[file], view=None)

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.success)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
            
        self.player_hand.append(self.deck.draw())
        val = calculate_hand_value(self.player_hand)
        
        if val > 21:
            self.ended = True
            self.balance = await self.cog.quest_data.get_balance(str(self.ctx.author.id), str(self.ctx.guild.id))
            
            embed = self.get_embed("bust", winnings=-self.bet)
            embed.description = f"**BUST!** You went over 21.\n**Lost:** {self.bet:,} pts"
            
            img_buffer = self.get_game_image("bust", winnings=-self.bet)
            file = discord.File(img_buffer, filename="blackjack.png")
            
            self.stop()
            await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
        else:
            # Update image for playing state
            img_buffer = self.get_game_image("playing")
            file = discord.File(img_buffer, filename="blackjack.png")
            await interaction.response.edit_message(embed=self.get_embed(), attachments=[file], view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.danger)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
            
        # Dealer turn
        while calculate_hand_value(self.dealer_hand) < 17:
             self.dealer_hand.append(self.deck.draw())
             
        player_val = calculate_hand_value(self.player_hand)
        dealer_val = calculate_hand_value(self.dealer_hand)
        
        if dealer_val > 21:
            result = "win"
        elif dealer_val > player_val:
            result = "loss"
        elif dealer_val < player_val:
            result = "win"
        else:
            result = "push"
            
        await self.end_game(interaction, result)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.primary)
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        
        # Can only double down on first two cards
        if len(self.player_hand) != 2:
            return await interaction.response.send_message("Can only double down on first two cards!", ephemeral=True)
        
        # Check if user has enough balance
        current_balance = await self.cog.quest_data.get_balance(str(self.ctx.author.id), str(self.ctx.guild.id))
        if current_balance < self.bet:
            return await interaction.response.send_message(f"Not enough balance to double down! Need {self.bet:,} pts.", ephemeral=True)
        
        # Double the bet and deduct
        await self.cog.quest_data.add_balance(str(self.ctx.author.id), str(self.ctx.guild.id), -self.bet)
        self.bet *= 2
        
        # Draw one card and stand
        self.player_hand.append(self.deck.draw())
        val = calculate_hand_value(self.player_hand)
        
        if val > 21:
            # Bust
            self.ended = True
            self.balance = await self.cog.quest_data.get_balance(str(self.ctx.author.id), str(self.ctx.guild.id))
            
            embed = self.get_embed("bust", winnings=-self.bet)
            embed.description = f"**BUST!** You went over 21.\n**Lost:** {self.bet:,} pts (Double Down)"
            
            img_buffer = self.get_game_image("bust", winnings=-self.bet)
            file = discord.File(img_buffer, filename="blackjack.png")
            
            self.stop()
            await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
        else:
            # Dealer turn
            while calculate_hand_value(self.dealer_hand) < 17:
                self.dealer_hand.append(self.deck.draw())
            
            player_val = calculate_hand_value(self.player_hand)
            dealer_val = calculate_hand_value(self.dealer_hand)
            
            if dealer_val > 21:
                result = "win"
            elif dealer_val > player_val:
                result = "loss"
            elif dealer_val < player_val:
                result = "win"
            else:
                result = "push"
            
            await self.end_game(interaction, result)
        
    async def on_timeout(self):
        if not self.ended:
            if self.message:
                try:
                    await self.message.edit(content="⏱️ Timed out! You folded.", view=None)
                except:
                    pass
