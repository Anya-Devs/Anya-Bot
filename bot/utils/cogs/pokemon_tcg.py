"""
Pokemon TCG Card View UI
Handles the interactive card browsing interface with pagination and sorting
"""

import discord
import random


class PokemonTCGCardView(discord.ui.View):
    """Navigation view for Pokemon TCG cards with pricing and sorting"""
    
    def __init__(self, ctx, cards: list, pokemon_name: str):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.cards = cards
        self.pokemon_name = pokemon_name
        self.current_index = 0
        self.message = None
        self.sort_mode = "price"  # price, rarity, set, name
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current index"""
        # Disable prev/next if at boundaries
        self.children[0].disabled = len(self.cards) <= 1  # Prev
        self.children[2].disabled = len(self.cards) <= 1  # Next
        self.children[1].disabled = len(self.cards) <= 1  # Random
    
    def build_embed(self):
        """Build embed for current card"""
        if not self.cards or self.current_index >= len(self.cards):
            return discord.Embed(
                title="No cards available",
                description="No Pokemon TCG cards found.",
                color=discord.Color.red()
            )
        
        card = self.cards[self.current_index]
        
        # Extract card info
        name = card.get("name", "Unknown")
        card_set = card.get("set", {}).get("name", "Unknown Set")
        set_series = card.get("set", {}).get("series", "")
        rarity = card.get("rarity", "Common")
        number = card.get("number", "?")
        total_in_set = card.get("set", {}).get("printedTotal", "?")
        artist = card.get("artist", "Unknown")
        
        # Get card image
        images = card.get("images", {})
        card_image = images.get("large") or images.get("small", "")
        
        # Get pricing
        tcgplayer = card.get("tcgplayer", {})
        prices = tcgplayer.get("prices", {})
        tcg_url = tcgplayer.get("url", "")
        
        # Build price string
        price_lines = []
        if "holofoil" in prices and prices["holofoil"]:
            market = prices["holofoil"].get("market")
            if market:
                price_lines.append(f"Holofoil: **${market:.2f}**")
        if "reverseHolofoil" in prices and prices["reverseHolofoil"]:
            market = prices["reverseHolofoil"].get("market")
            if market:
                price_lines.append(f"Reverse Holo: **${market:.2f}**")
        if "normal" in prices and prices["normal"]:
            market = prices["normal"].get("market")
            if market:
                price_lines.append(f"Normal: **${market:.2f}**")
        if "1stEditionHolofoil" in prices and prices["1stEditionHolofoil"]:
            market = prices["1stEditionHolofoil"].get("market")
            if market:
                price_lines.append(f"1st Edition Holo: **${market:.2f}**")
        
        price_text = "\n".join(price_lines) if price_lines else "Price data not available"
        
        # Rarity colors
        rarity_colors = {
            "Common": 0x808080,
            "Uncommon": 0x00FF00,
            "Rare": 0x0000FF,
            "Rare Holo": 0x9400D3,
            "Rare Ultra": 0xFF1493,
            "Rare Secret": 0xFFD700,
            "Rare Rainbow": 0xFF69B4,
            "Amazing Rare": 0xFF4500,
            "Radiant Rare": 0xFFD700,
        }
        embed_color = rarity_colors.get(rarity, 0x3498db)
        
        # Build embed
        embed = discord.Embed(
            title=name,
            description=f"**{card_set}** ({set_series})" if set_series else f"**{card_set}**",
            color=embed_color
        )
        
        if card_image:
            embed.set_image(url=card_image)
        
        # Card details
        embed.add_field(
            name="Card Information",
            value=(
                f"**Rarity:** {rarity}\n"
                f"**Number:** {number}/{total_in_set}\n"
                f"**Artist:** {artist}"
            ),
            inline=True
        )
        
        # Pricing
        embed.add_field(
            name="Market Prices",
            value=price_text,
            inline=True
        )
        
        # Types and HP if available
        types = card.get("types", [])
        hp = card.get("hp", "")
        if types or hp:
            type_str = " / ".join(types) if types else "N/A"
            hp_str = f"{hp} HP" if hp else "N/A"
            embed.add_field(
                name="Pokemon Stats",
                value=f"**Type:** {type_str}\n**HP:** {hp_str}",
                inline=False
            )
        
        # Footer with navigation
        footer_text = f"Card {self.current_index + 1} of {len(self.cards)} • Sorted by {self.sort_mode.title()}"
        if tcg_url:
            footer_text += " • TCGPlayer"
        embed.set_footer(text=footer_text)
        
        return embed
    
    def sort_cards(self):
        """Sort cards based on current sort mode"""
        if self.sort_mode == "price":
            self.cards.sort(key=lambda x: x.get("_price_sort", 0), reverse=True)
        elif self.sort_mode == "rarity":
            rarity_order = {
                "Common": 1, "Uncommon": 2, "Rare": 3, "Rare Holo": 4,
                "Rare Ultra": 5, "Rare Secret": 6, "Rare Rainbow": 7,
                "Amazing Rare": 8, "Radiant Rare": 9
            }
            self.cards.sort(key=lambda x: rarity_order.get(x.get("rarity", "Common"), 0), reverse=True)
        elif self.sort_mode == "set":
            self.cards.sort(key=lambda x: x.get("set", {}).get("releaseDate", ""), reverse=True)
        elif self.sort_mode == "name":
            self.cards.sort(key=lambda x: x.get("name", ""))
    
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This isn't your card browser!", ephemeral=True)
        
        self.current_index = (self.current_index - 1) % len(self.cards)
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Random", style=discord.ButtonStyle.primary)
    async def random_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This isn't your card browser!", ephemeral=True)
        
        self.current_index = random.randint(0, len(self.cards) - 1)
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This isn't your card browser!", ephemeral=True)
        
        self.current_index = (self.current_index + 1) % len(self.cards)
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Sort", style=discord.ButtonStyle.success)
    async def sort_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This isn't your card browser!", ephemeral=True)
        
        # Cycle through sort modes
        sort_modes = ["price", "rarity", "set", "name"]
        current_idx = sort_modes.index(self.sort_mode)
        self.sort_mode = sort_modes[(current_idx + 1) % len(sort_modes)]
        
        # Re-sort cards
        self.sort_cards()
        self.current_index = 0  # Reset to first card after sorting
        
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        for child in self.children:
            child.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass