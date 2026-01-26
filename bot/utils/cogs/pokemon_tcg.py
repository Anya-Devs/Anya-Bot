"""
Pokemon TCG Card View UI
Handles the interactive card browsing interface with paginated select dropdowns
"""

import discord
import random
import math


class PokemonTCGCardView(discord.ui.View):
    """Navigation view for Pokemon TCG cards with paginated select dropdowns"""
    
    def __init__(self, ctx, cards: list, pokemon_name: str):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.cards = cards
        self.pokemon_name = pokemon_name
        self.current_index = 0
        self.current_page = 0
        self.message = None
        self.sort_mode = "price"  # price, rarity, set, name
        self.items_per_page = 25  # Discord select menu limit
        
        # Calculate total pages
        self.total_pages = math.ceil(len(self.cards) / self.items_per_page)
        
        # Build the view with select and navigation
        self.rebuild_view()
    
    def rebuild_view(self):
        """Rebuild the view with current page's select menu"""
        self.clear_items()
        
        if not self.cards:
            return
        
        # Add card select dropdown for current page
        start_idx = self.current_page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.cards))
        page_cards = self.cards[start_idx:end_idx]
        
        if page_cards:
            select = CardSelectDropdown(self, page_cards, start_idx)
            self.add_item(select)
        
        # Add pagination buttons if multiple pages
        if self.total_pages > 1:
            self.add_item(PrevPageButton())
            self.add_item(PageInfoButton(self.current_page + 1, self.total_pages))
            self.add_item(NextPageButton())
        
        # Add sort button
        self.add_item(SortButton())
        
        # Add random button
        self.add_item(RandomButton())
    
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
    
    async def on_timeout(self):
        """Disable all components when the view times out"""
        try:
            for child in self.children:
                child.disabled = True
            
            if self.message:
                await self.message.edit(view=self)
        except discord.NotFound:
            pass  # Message was deleted
        except:
            pass  # Silently handle other errors


class CardSelectDropdown(discord.ui.Select):
    """Select dropdown for choosing cards from current page"""
    
    def __init__(self, view: PokemonTCGCardView, cards: list, start_idx: int):
        self.parent_view = view
        
        # Build options from cards
        options = []
        for i, card in enumerate(cards):
            card_idx = start_idx + i
            name = card.get("name", "Unknown")
            card_set = card.get("set", {}).get("name", "Unknown Set")
            rarity = card.get("rarity", "Common")
            
            # Get price for label
            price_val = card.get("_price_sort", 0)
            price_str = f"${price_val:.2f}" if price_val > 0 else "N/A"
            
            # Rarity emoji
            rarity_emoji = {
                "Common": "⚪", "Uncommon": "🟢", "Rare": "🔵",
                "Rare Holo": "🟣", "Rare Ultra": "🔴", "Rare Secret": "🟡",
                "Rare Rainbow": "🌈", "Amazing Rare": "⭐", "Radiant Rare": "✨"
            }.get(rarity, "⚪")
            
            label = f"{name[:50]}"  # Limit to 50 chars
            description = f"{rarity_emoji} {rarity} • {card_set[:30]} • {price_str}"[:100]
            
            options.append(discord.SelectOption(
                label=label,
                description=description,
                value=str(card_idx)
            ))
        
        super().__init__(
            placeholder=f"Select a card ({start_idx + 1}-{start_idx + len(cards)} of {len(view.cards)})",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.ctx.author.id:
            return await interaction.response.send_message("This isn't your card browser!", ephemeral=True)
        
        # Update current index
        self.parent_view.current_index = int(self.values[0])
        
        # Update page if needed
        self.parent_view.current_page = self.parent_view.current_index // self.parent_view.items_per_page
        
        # Rebuild view and update message
        self.parent_view.rebuild_view()
        embed = self.parent_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class PrevPageButton(discord.ui.Button):
    """Button to go to previous page"""
    
    def __init__(self):
        super().__init__(label="◀ Prev Page", style=discord.ButtonStyle.secondary, row=1)
    
    async def callback(self, interaction: discord.Interaction):
        view: PokemonTCGCardView = self.view
        
        if interaction.user.id != view.ctx.author.id:
            return await interaction.response.send_message("This isn't your card browser!", ephemeral=True)
        
        # Go to previous page
        view.current_page = (view.current_page - 1) % view.total_pages
        view.rebuild_view()
        
        # Update current index to first card of new page
        view.current_index = view.current_page * view.items_per_page
        
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PageInfoButton(discord.ui.Button):
    """Button showing current page info (disabled, for display only)"""
    
    def __init__(self, current_page: int, total_pages: int):
        super().__init__(
            label=f"Page {current_page}/{total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        pass  # Disabled button, no action


class NextPageButton(discord.ui.Button):
    """Button to go to next page"""
    
    def __init__(self):
        super().__init__(label="Next Page ▶", style=discord.ButtonStyle.secondary, row=1)
    
    async def callback(self, interaction: discord.Interaction):
        view: PokemonTCGCardView = self.view
        
        if interaction.user.id != view.ctx.author.id:
            return await interaction.response.send_message("This isn't your card browser!", ephemeral=True)
        
        # Go to next page
        view.current_page = (view.current_page + 1) % view.total_pages
        view.rebuild_view()
        
        # Update current index to first card of new page
        view.current_index = view.current_page * view.items_per_page
        
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class SortButton(discord.ui.Button):
    """Button to cycle through sort modes"""
    
    def __init__(self):
        super().__init__(label="🔄 Sort", style=discord.ButtonStyle.success, row=2)
    
    async def callback(self, interaction: discord.Interaction):
        view: PokemonTCGCardView = self.view
        
        if interaction.user.id != view.ctx.author.id:
            return await interaction.response.send_message("This isn't your card browser!", ephemeral=True)
        
        # Cycle through sort modes
        sort_modes = ["price", "rarity", "set", "name"]
        current_idx = sort_modes.index(view.sort_mode)
        view.sort_mode = sort_modes[(current_idx + 1) % len(sort_modes)]
        
        # Re-sort cards
        view.sort_cards()
        view.current_index = 0
        view.current_page = 0
        view.rebuild_view()
        
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class RandomButton(discord.ui.Button):
    """Button to jump to random card"""
    
    def __init__(self):
        super().__init__(label="🎲 Random", style=discord.ButtonStyle.primary, row=2)
    
    async def callback(self, interaction: discord.Interaction):
        view: PokemonTCGCardView = self.view
        
        if interaction.user.id != view.ctx.author.id:
            return await interaction.response.send_message("This isn't your card browser!", ephemeral=True)
        
        # Pick random card
        view.current_index = random.randint(0, len(view.cards) - 1)
        view.current_page = view.current_index // view.items_per_page
        view.rebuild_view()
        
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class CardBrowserButtonView(discord.ui.View):
    """View with a button that opens an ephemeral card browser"""
    
    def __init__(self, ctx, cards: list, pokemon_name: str):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.cards = cards
        self.pokemon_name = pokemon_name
    
    @discord.ui.button(label="📋 Browse All Cards", style=discord.ButtonStyle.primary, row=0)
    async def browse_cards_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message("This isn't your card search!", ephemeral=True)
        
        try:
            # Create the paginated select view
            browser_view = PokemonTCGCardView(self.ctx, self.cards, self.pokemon_name)
            browser_embed = browser_view.build_embed()
            
            # Send ephemeral message with select UI
            await interaction.response.send_message(
                embed=browser_embed,
                view=browser_view,
                ephemeral=True
            )
            
            # Store message reference for timeout handling
            browser_view.message = await interaction.original_response()
        except discord.NotFound:
            pass  # Interaction expired
        except Exception as e:
            try:
                await interaction.response.send_message(f"❌ Error loading card browser: {e}", ephemeral=True)
            except:
                pass