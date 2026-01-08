
"""
Game UI Views - Discord Interactive Components
"""

import discord
from discord.ext import commands
import random
import aiohttp
import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from motor.motor_asyncio import AsyncIOMotorClient
from utils.cogs.cover_art import CoverArtVariantView, CoverArtDatabase
from .const import *
from .images import *
from .const import GameEmojis
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# GAMBLING GAME VIEWS
# ═══════════════════════════════════════════════════════════════

class DoubleOrNothingView(discord.ui.View):
    """View for Double or Nothing after winning coinflip"""
    def __init__(self, cog, user_id: str, guild_id: str, winnings: int):
        super().__init__(timeout=30)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.winnings = winnings
        self.used = False
    
    @discord.ui.button(label="Double or Nothing!", style=discord.ButtonStyle.green, emoji=GameEmojis.DICE)
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} This isn't your game!", ephemeral=True)
        
        if self.used:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} Already used!", ephemeral=True)
        
        self.used = True
        self.stop()
        
        # 50/50 chance
        won = random.choice([True, False])
        
        if won:
            new_winnings = self.winnings * 2
            await self.cog.quest_data.add_balance(self.user_id, self.guild_id, self.winnings)
            balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
            
            embed = discord.Embed(
                title=f"{GameEmojis.CELEBRATION} DOUBLED!",
                description=f"You turned **{self.winnings:,}** into **{new_winnings:,}** pts!",
                color=discord.Color.gold()
            )
            embed.add_field(name=f"{GameEmojis.MONEY} Total Won", value=f"+**{new_winnings:,}** pts", inline=True)
            embed.add_field(name=f"{GameEmojis.CREDIT_CARD} Balance", value=f"**{balance:,}** pts", inline=True)
            
            # Offer another double
            new_view = DoubleOrNothingView(self.cog, self.user_id, self.guild_id, new_winnings)
            await interaction.response.edit_message(embed=embed, view=new_view)
        else:
            await self.cog.quest_data.add_balance(self.user_id, self.guild_id, -self.winnings)
            balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
            
            embed = discord.Embed(
                title=f"{GameEmojis.SKULL} BUSTED!",
                description=f"You lost your **{self.winnings:,}** pts!",
                color=discord.Color.red()
            )
            embed.add_field(name=f"{GameEmojis.CHART_DOWN} Lost", value=f"-**{self.winnings:,}** pts", inline=True)
            embed.add_field(name=f"{GameEmojis.CREDIT_CARD} Balance", value=f"**{balance:,}** pts", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.secondary, emoji=GameEmojis.MONEY)
    async def cashout_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} This isn't your game!", ephemeral=True)
        
        if self.used:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} Already cashed out!", ephemeral=True)
        
        self.used = True
        self.stop()
        
        balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
        
        embed = discord.Embed(
            title=f"{GameEmojis.MONEY} Cashed Out!",
            description=f"Smart move! You kept your **{self.winnings:,}** pts.",
            color=discord.Color.green()
        )
        embed.add_field(name=f"{GameEmojis.CREDIT_CARD} Balance", value=f"**{balance:,}** pts", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def on_timeout(self):
        # Auto cash-out on timeout
        pass


# ═══════════════════════════════════════════════════════════════
# GACHA SYSTEM VIEWS
# ═══════════════════════════════════════════════════════════════

class CharacterInfoView(discord.ui.View):
    """View for showing character information after claiming"""
    def __init__(self, cog, character: dict, uid: str, user: discord.Member, draws_left: int = 0, guild_id: str = None):
        super().__init__(timeout=None)  # Persistent view
        self.cog = cog
        self.character = character
        self.uid = uid
        self.user = user
        self.draws_left = draws_left
        self.guild_id = guild_id
        self.message = None  # Will be set after creation
        
        # Only add redraw button if user has draws left
        if draws_left > 0 and guild_id:
            self.add_item(self.create_redraw_button())
    
    @discord.ui.button(label="Info", style=discord.ButtonStyle.gray)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            try:
                return await interaction.response.send_message(f"{GameEmojis.ERROR} This isn't your character!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(f"{GameEmojis.ERROR} This isn't your character!", ephemeral=True)
        
        char = self.character
        rarity_data = GACHA_RARITY_TIERS.get(char.get("rarity", "common"))
        favorites = char.get("favorites", 0)
        
        # Calculate release value
        from .const import calculate_release_value
        release_value = calculate_release_value(favorites, char.get("rarity", "common"), char.get('name', 'unknown'))
        
        # Create character info embed
        embed = discord.Embed(
            title=f"{rarity_data['stars']} {char['name']}",
            description=f"*{char.get('anime', 'Unknown')}*",
            color=rarity_data["color"]
        )
        
        # Character details
        details = f"**UID:** `{self.uid}`\n"
        details += f"**Rarity:** {char.get('rarity', 'common').title()}\n"
        details += f"**Gender:** {char.get('gender', 'Unknown')}\n"
        details += f"**Favorites:** {favorites:,}\n"
        details += f"**Release Value:** {release_value:,} pts"
        
        embed.add_field(name="Character Details", value=details, inline=False)
        embed.add_field(
            name="Commands", 
            value="• `.draw view <UID>` - Show off character\n• `.draw release <UID>` - Sell for points", 
            inline=False
        )
        
        if char.get("image_url"):
            embed.set_thumbnail(url=char["image_url"])
        
        embed.set_footer(text="Click Info again to refresh this message")
        
        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    def create_redraw_button(self):
        """Create a redraw button dynamically"""
        button = discord.ui.Button(label="Redraw", style=discord.ButtonStyle.primary)
        button.callback = self.redraw_callback
        return button
    
    async def redraw_callback(self, interaction: discord.Interaction):
        """Handle redraw button click"""
        if interaction.user.id != self.user.id:
            try:
                return await interaction.response.send_message(f"{GameEmojis.ERROR} This isn't your draw!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(f"{GameEmojis.ERROR} This isn't your draw!", ephemeral=True)
        
        user_id = str(self.user.id)
        guild_id = str(self.guild_id)
        cost = GACHA_COST
        
        # Check balance
        balance = await self.cog.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            try:
                return await interaction.response.send_message(
                    f"❌ Need **{cost}** but have **{balance:,}** pts!", 
                    ephemeral=True
                )
            except discord.InteractionResponded:
                return await interaction.followup.send(f"❌ Need **{cost}** but have **{balance:,}** pts!", ephemeral=True)
        
        # Check timer
        class MockContext:
            def __init__(self, user, guild):
                self.author = user
                self.guild = guild
        
        mock_ctx = MockContext(self.user, interaction.guild)
        timer_error = await self.cog.check_timer(mock_ctx, "gacha")
        if timer_error:
            try:
                return await interaction.response.send_message(timer_error, ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(timer_error, ephemeral=True)
        
        # Deduct cost and increment plays
        await self.cog.set_cooldown(user_id, "gacha_command")
        await self.cog.quest_data.add_balance(user_id, guild_id, -cost)
        await self.cog.increment_plays(user_id, guild_id, "gacha")
        
        # Defer the response to prevent timeout
        try:
            await interaction.response.defer()
        except:
            pass
        
        # Disable ALL buttons during processing to prevent any interaction
        try:
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
        except:
            pass
        
        # Edit message content to show loading status
        try:
            await interaction.message.edit(content="Rendering new characters... Please wait!", view=self)
        except:
            pass
        
        # Fetch new characters
        new_characters = await self.cog.pull_three_cards_real()
        
        # Check ownership for each character
        ownership_info = await self.cog.check_character_ownership(interaction.guild, new_characters)
        
        # Generate new image
        img_buffer = await generate_gacha_draw_image(new_characters, ownership_info=ownership_info)
        file = discord.File(img_buffer, filename="gacha_redraw.png")
        
        # Update balance and draws left
        new_balance = balance - cost
        gacha_config = get_timer_config("gacha")
        current_uses = await self.cog.get_current_uses(user_id, guild_id, "gacha")
        new_draws_left = gacha_config['max_uses'] - current_uses
        new_is_out_of_draws = new_draws_left <= 0
        
        # Create new claim view
        new_view = GachaClaimView(
            self.cog, self.user, guild_id, new_characters, 
            new_balance, new_draws_left, new_is_out_of_draws, 
            message=self.message
        )
        
        # Edit the message with new draw and clear content
        try:
            await self.message.edit(content="", attachments=[file], view=new_view)
            new_view.message = self.message
        except Exception as e:
            logger.error(f"Error editing message in redraw: {e}")
            try:
                await interaction.followup.send("❌ Failed to update the message. Please try drawing again.", ephemeral=True)
            except:
                pass


class GachaClaimView(discord.ui.View):
    """View for claiming a character from gacha draw - prevents double claiming"""
    def __init__(self, cog, user: discord.Member, guild_id: str, characters: list, balance: int, draws_left: int, is_out_of_draws: bool, message=None):
        super().__init__(timeout=GACHA_CLAIM_TIMEOUT)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.characters = characters
        self.balance = balance
        self.draws_left = draws_left
        self.is_out_of_draws = is_out_of_draws
        self.message = message
        self.claimed = False
        self.claimed_indices = []  # Track which cards have been claimed
    
    async def claim_character(self, interaction: discord.Interaction, index: int):
        if interaction.user.id != self.user.id:
            try:
                return await interaction.response.send_message(f"{GameEmojis.ERROR} This isn't your draw!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(f"{GameEmojis.ERROR} This isn't your draw!", ephemeral=True)
        
        if self.claimed:
            try:
                return await interaction.response.send_message(f"{GameEmojis.ERROR} You already claimed a character!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(f"{GameEmojis.ERROR} You already claimed a character!", ephemeral=True)
        
        if index in self.claimed_indices:
            try:
                return await interaction.response.send_message(f"{GameEmojis.ERROR} This character was already claimed!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(f"{GameEmojis.ERROR} This character was already claimed!", ephemeral=True)
        
        if index < 0 or index >= len(self.characters):
            try:
                return await interaction.response.send_message(f"{GameEmojis.ERROR} Invalid choice!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(f"{GameEmojis.ERROR} Invalid choice!", ephemeral=True)
        
        char = self.characters[index]
        user_id = str(self.user.id)
        
        # Check if character is already owned in this server
        is_owned, owner_id = await self.cog.is_character_owned_in_server(
            self.guild_id, char.get("name"), char.get("id")
        )
        
        if is_owned:
            try:
                owner = interaction.guild.get_member(int(owner_id))
                owner_name = owner.display_name if owner else "Someone"
            except:
                owner_name = "Someone"
            try:
                return await interaction.response.send_message(
                    f"❌ **{char['name']}** is already owned by **{owner_name}** in this server!",
                    ephemeral=True
                )
            except discord.InteractionResponded:
                return await interaction.followup.send(
                    f"❌ **{char['name']}** is already owned by **{owner_name}** in this server!",
                    ephemeral=True
                )
        
        self.claimed = True
        self.claimed_indices.append(index)
        self.stop()
        
        # Add to inventory in MongoDB and get UID
        uid = await self.cog.add_character_to_inventory(user_id, self.guild_id, char)
        
        # Regenerate image with claimed card marked
        img_buffer = await generate_gacha_draw_image(self.characters, claimed_indices=self.claimed_indices)
        file = discord.File(img_buffer, filename="gacha_claimed.png")
        
        rarity_data = GACHA_RARITY_TIERS.get(char.get("rarity", "common"))
        favorites = char.get("favorites", 0)
        
        # Create info view for the claimed character
        info_view = CharacterInfoView(self.cog, char, uid, self.user, self.draws_left, self.guild_id)
        
        try:
            await interaction.response.edit_message(attachments=[file], view=info_view)
            # Set the message reference to the interaction's message
            info_view.message = interaction.message
        except discord.InteractionResponded:
            try:
                await interaction.followup.send("Character claimed! Check the updated message above.", ephemeral=True)
                # Try to edit the original message if possible
                if self.message:
                    await self.message.edit(attachments=[file], view=info_view)
                    info_view.message = self.message
            except:
                pass
        except discord.NotFound:
            # Message was deleted, try to send a new one in the channel
            try:
                if hasattr(interaction, 'channel') and interaction.channel:
                    new_msg = await interaction.channel.send(file=file, view=info_view)
                    info_view.message = new_msg
            except:
                pass
    
    def _update_buttons(self):
        """Disable buttons for claimed characters"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label == "1" and 0 in self.claimed_indices:
                    item.disabled = True
                    item.style = discord.ButtonStyle.secondary
                elif item.label == "2" and 1 in self.claimed_indices:
                    item.disabled = True
                    item.style = discord.ButtonStyle.secondary
                elif item.label == "3" and 2 in self.claimed_indices:
                    item.disabled = True
                    item.style = discord.ButtonStyle.secondary
    
    @discord.ui.button(label="1", style=discord.ButtonStyle.success)
    async def claim_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_character(interaction, 0)
    
    @discord.ui.button(label="2", style=discord.ButtonStyle.success)
    async def claim_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_character(interaction, 1)
    
    @discord.ui.button(label="3", style=discord.ButtonStyle.success)
    async def claim_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.claim_character(interaction, 2)
    
    @discord.ui.button(label="Info", style=discord.ButtonStyle.secondary, row=1)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            try:
                return await interaction.response.send_message(f"{GameEmojis.ERROR} This isn't your draw!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(f"{GameEmojis.ERROR} This isn't your draw!", ephemeral=True)
        
        summary_content = self.cog._get_draw_summary_content(
            self.user.display_name, self.balance, self.draws_left, self.is_out_of_draws
        )
        try:
            await interaction.response.send_message(summary_content, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(summary_content, ephemeral=True)
    
    @discord.ui.button(label="Redraw", style=discord.ButtonStyle.primary, row=1)
    async def redraw_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            try:
                return await interaction.response.send_message(f"{GameEmojis.ERROR} This isn't your draw!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(f"{GameEmojis.ERROR} This isn't your draw!", ephemeral=True)
        
        if self.is_out_of_draws:
            try:
                return await interaction.response.send_message("❌ No draws left!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send("❌ No draws left!", ephemeral=True)
        
        if self.claimed:
            try:
                return await interaction.response.send_message("❌ Already claimed!", ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send("❌ Already claimed!", ephemeral=True)
        
        # Check if user can still redraw BEFORE marking as claimed
        user_id = str(self.user.id)
        guild_id = str(self.guild_id)
        cost = GACHA_COST
        
        # Check balance first
        balance = await self.cog.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            try:
                return await interaction.response.send_message(
                    f"❌ Need **{cost}** but have **{balance:,}** pts!", 
                    ephemeral=True
                )
            except discord.InteractionResponded:
                return await interaction.followup.send(f"❌ Need **{cost}** but have **{balance:,}** pts!", ephemeral=True)
        
        # Check timer - create mock context since check_timer expects ctx.author
        class MockContext:
            def __init__(self, user, guild):
                self.author = user
                self.guild = guild
        
        mock_ctx = MockContext(self.user, self.user.guild)
        timer_error = await self.cog.check_timer(mock_ctx, "gacha")
        if timer_error:
            try:
                return await interaction.response.send_message(timer_error, ephemeral=True)
            except discord.InteractionResponded:
                return await interaction.followup.send(timer_error, ephemeral=True)
        
        # Only mark as claimed AFTER all checks pass
        self.claimed = True
        self.stop()
        
        # Deduct cost and increment plays
        await self.cog.set_cooldown(user_id, "gacha_command")
        await self.cog.quest_data.add_balance(user_id, guild_id, -cost)
        await self.cog.increment_plays(user_id, guild_id, "gacha")
        
        # Defer the response first to prevent timeout
        try:
            await interaction.response.defer()
        except:
            pass
        
        # Disable ALL buttons during processing to prevent any interaction
        try:
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
        except:
            pass
        
        # Edit message content to show loading status
        try:
            await interaction.message.edit(content="🎲 Rendering new characters... Please wait!", view=self)
        except:
            pass
        
        # Fetch new characters
        new_characters = await self.cog.pull_three_cards_real()
        
        # Check ownership for each character
        ownership_info = await self.cog.check_character_ownership(self.user.guild, new_characters)
        
        # Generate new image
        img_buffer = await generate_gacha_draw_image(new_characters, ownership_info=ownership_info)
        file = discord.File(img_buffer, filename="gacha_redraw.png")
        
        # Update balance and draws left
        new_balance = balance - cost
        gacha_config = get_timer_config("gacha")
        current_uses = await self.cog.get_current_uses(user_id, guild_id, "gacha")
        new_draws_left = gacha_config['max_uses'] - current_uses
        new_is_out_of_draws = new_draws_left <= 0
        
        # Create new view with updated data
        new_view = GachaClaimView(self.cog, self.user, guild_id, new_characters, new_balance, new_draws_left, new_is_out_of_draws, message=interaction.message)
        
        # Edit the current message with new image and view, clearing content
        try:
            await interaction.message.edit(content="", attachments=[file], view=new_view)
            new_view.message = interaction.message
        except Exception as e:
            logger.error(f"Error editing message in redraw: {e}")
            # Fallback: send ephemeral message
            try:
                await interaction.followup.send("❌ Failed to update the message. Please try drawing again.", ephemeral=True)
            except:
                pass
    
    async def on_timeout(self):
        if not self.claimed and self.message:
            try:
                # Keep showing cards, just remove buttons
                await self.message.edit(content="**Time's up** - No character claimed", embed=None, view=None)
            except Exception as e:
                logger.error(f"GachaClaimView timeout error: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Handle errors in view interactions with proper logging."""
        logger.error(f"GachaClaimView error in {item.__class__.__name__}: {error}", exc_info=True)
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while processing your request. Please try again.",
                    ephemeral=True
                )
        except Exception as response_error:
            logger.error(f"Failed to send error response: {response_error}")


# ═══════════════════════════════════════════════════════════════
# CHARACTER & COVER ART VIEWS
# ═══════════════════════════════════════════════════════════════

class CharacterCoverArtView(discord.ui.View):
    """View with cover art button for gacha character display"""
    
    _db_cache: Optional[CoverArtDatabase] = None
    
    def __init__(self, character_uid: str, user_id: int):
        super().__init__(timeout=300)
        self.character_uid = character_uid
        self.user_id = user_id
    
    @classmethod
    def _get_cover_art_db(cls) -> CoverArtDatabase:
        """Get CoverArtDatabase either from cog or create fallback."""
        if cls._db_cache:
            return cls._db_cache
        
        mongo_url = os.getenv("MONGO_URI")
        if not mongo_url:
            raise RuntimeError("MONGO_URL/MONGO_URI is not set; cannot connect cover art database.")
        client = AsyncIOMotorClient(mongo_url)
        database = client["anya_bot"]
        cls._db_cache = CoverArtDatabase(database)
        return cls._db_cache
    
    @discord.ui.button(label="Cover Art", style=discord.ButtonStyle.primary)
    async def cover_art_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can only use your own character buttons!", ephemeral=True)
            return
        
        # Defer early to keep interaction alive during API lookups
        send = interaction.response.send_message
        if not interaction.response.is_done():
            try:
                await interaction.response.defer(ephemeral=True)
                send = interaction.followup.send
            except Exception as defer_err:
                logger.warning("CoverArt defer failed: %s", defer_err)
                send = interaction.response.send_message if not interaction.response.is_done() else interaction.followup.send
        else:
            send = interaction.followup.send
        
        try:
            # Get character data from the games cog
            games_cog = interaction.client.get_cog("Games")
            if not games_cog:
                await send("❌ Games cog not found!", ephemeral=True)
                return
            
            # Get character data from UID
            guild_id = str(interaction.guild.id)
            owner_id, character_data = await games_cog.get_character_by_uid(guild_id, self.character_uid)
            
            if not character_data:
                await send("❌ Character not found!", ephemeral=True)
                return
            
            character_name = character_data.get("name", "Unknown")
            
            # Fetch anisearch screenshot
            async with aiohttp.ClientSession() as session:
                screenshot_url = await fetch_anisearch_screenshot(session, character_name)
            
            if screenshot_url:
                # Create embed with screenshot
                embed = discord.Embed(
                    title=f"🎨 {character_name} - Cover Art",
                    description=f"From: {character_data.get('anime', 'Unknown')}",
                    color=discord.Color.blue()
                )
                embed.set_image(url=screenshot_url)
                embed.set_footer(text="Image source: anisearch.org")
                
                view = discord.ui.View()
                view.add_item(discord.ui.Button(
                    label="View Full Image",
                    style=discord.ButtonStyle.link,
                    url=screenshot_url
                ))
                
                await send(embed=embed, view=view, ephemeral=True)
            else:
                # Fallback to original image if available
                original_image = character_data.get("image_url")
                if original_image:
                    embed = discord.Embed(
                        title=f"🎨 {character_name} - Cover Art",
                        description=f"From: {character_data.get('anime', 'Unknown')}",
                        color=discord.Color.blue()
                    )
                    embed.set_image(url=original_image)
                    embed.set_footer(text="Original character image")
                    
                    await send(embed=embed, ephemeral=True)
                else:
                    await send(f"❌ No cover art found for {character_name}", ephemeral=True)
                    
        except Exception as e:
            logger.error(f"Error in cover_art_button: {e}")
            await send("❌ An error occurred while fetching cover art!", ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# INVENTORY & COLLECTION VIEWS
# ═══════════════════════════════════════════════════════════════

class InventoryView(discord.ui.View):
    """Paginated inventory view with filters and search"""
    
    def __init__(self, cog, user: discord.Member, guild_id: str, characters: list, filter_type: str = "all", search_query: str = None):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.all_characters = characters
        self.page = 0
        self.per_page = 10
        
        # Filters
        self.rarity_filter = "all"
        self.gender_filter = "all"
        self.search_query = search_query  # Search by name/anime
        
        self.filtered_chars = self._filter_characters()
        self.max_pages = max(1, (len(self.filtered_chars) + self.per_page - 1) // self.per_page)
        
        # Add components
        self.add_item(InventoryRaritySelect(self))
        self.add_item(InventoryGenderSelect(self))
    
    def _filter_characters(self):
        """Apply rarity, gender, and name search filters."""
        from utils.cogs.game.const import get_rarity_from_favorites
        
        chars = self.all_characters
        
        # Recalculate rarity for all characters based on favorites
        for char in chars:
            favorites = char.get("favorites", 0)
            char["rarity"] = get_rarity_from_favorites(favorites)
        
        # Apply name search filter (case-insensitive, searches both name and anime)
        if self.search_query:
            search_lower = self.search_query.lower().strip()
            if search_lower:
                chars = [c for c in chars if 
                        (c.get("name", "").lower().find(search_lower) != -1) or 
                        (c.get("anime", "").lower().find(search_lower) != -1)]
        
        # Apply rarity filter
        if self.rarity_filter == "legendary":
            chars = [c for c in chars if c.get("rarity") == "legendary"]
        elif self.rarity_filter == "epic":
            chars = [c for c in chars if c.get("rarity") == "epic"]
        elif self.rarity_filter == "rare":
            chars = [c for c in chars if c.get("rarity") == "rare"]
        elif self.rarity_filter == "uncommon":
            chars = [c for c in chars if c.get("rarity") == "uncommon"]
        elif self.rarity_filter == "common":
            chars = [c for c in chars if c.get("rarity") == "common"]
        
        # Apply gender filter
        if self.gender_filter == "female":
            chars = [c for c in chars if c.get("gender") == "Female"]
        elif self.gender_filter == "male":
            chars = [c for c in chars if c.get("gender") == "Male"]
        elif self.gender_filter == "unknown":
            chars = [c for c in chars if c.get("gender") not in ["Female", "Male"]]
        
        return chars
    
    async def get_embed(self):
        from utils.cogs.game.const import get_rarity_from_favorites
        
        # Recalculate rarity for all characters based on favorites
        for char in self.filtered_chars:
            favorites = char.get("favorites", 0)
            char["rarity"] = get_rarity_from_favorites(favorites)
        
        # Sort by rarity priority then favorites
        rarity_order = {"legendary": 0, "epic": 1, "rare": 2, "uncommon": 3, "common": 4}
        sorted_chars = sorted(
            self.filtered_chars,
            key=lambda c: (rarity_order.get(c.get("rarity", "common"), 4), -c.get("favorites", 0))
        )
        
        # Get current page characters
        start = self.page * self.per_page
        end = start + self.per_page
        page_chars = sorted_chars[start:end]
        
        # Count by rarity for stats
        rarity_counts = {"legendary": 0, "epic": 0, "rare": 0, "uncommon": 0, "common": 0}
        for c in self.filtered_chars:
            r = c.get("rarity", "common")
            if r in rarity_counts:
                rarity_counts[r] += 1
        
        # Build filter description
        rarity_labels = {"all": "All", "legendary": "Legendary", "epic": "Epic", "rare": "Rare", "uncommon": "Uncommon", "common": "Common"}
        gender_labels = {"all": "All", "female": f"{GameEmojis.FEMALE} Female", "male": f"{GameEmojis.MALE} Male", "unknown": f"{GameEmojis.NONBINARY} Unknown"}
        
        filter_text = f"**Rarity:** {rarity_labels.get(self.rarity_filter, 'All')} • **Gender:** {gender_labels.get(self.gender_filter, 'All')}"
        
        # Add search query to filter text if present
        if self.search_query:
            filter_text += f"\n🔍 **Search:** '{self.search_query}'"
        
        # Stats line
        stats = f"{GameEmojis.LEGENDARY} {rarity_counts['legendary']} • {GameEmojis.EPIC} {rarity_counts['epic']} • {GameEmojis.RARE} {rarity_counts['rare']} • {GameEmojis.UNCOMMON} {rarity_counts['uncommon']} • {GameEmojis.COMMON} {rarity_counts['common']}"
        
        embed = discord.Embed(
            title=f"{GameEmojis.BOX} {self.user.display_name}'s Collection",
            description=f"{filter_text}\n{stats}\n**Total:** {len(self.filtered_chars)} characters",
            color=discord.Color.blurple()
        )
        
        # Build character list
        if page_chars:
            char_lines = []
            for char in page_chars:
                rarity = char.get("rarity", "common")
                rarity_data = GACHA_RARITY_TIERS.get(rarity, GACHA_RARITY_TIERS["common"])
                gender_emoji = GameEmojis.FEMALE if char.get("gender") == "Female" else GameEmojis.MALE if char.get("gender") == "Male" else GameEmojis.NONBINARY
                uid = char.get("uid", "")
                if not uid:
                    continue
                name = char.get('name', 'Unknown')
                anime = char.get('anime', 'Unknown')
                likes = char.get("favorites", 0)
                
                # Check if character has active cover art
                cover_indicator = ""
                if char.get('active_cover_url'):
                    cover_indicator = " 🎨"
                
                # Improved format: UID on same line, cleaner spacing
                line = f"**{uid}**{cover_indicator} {rarity_data['emoji']} **{name}** {gender_emoji}\n> *{anime}* • ❤️ {likes:,}"
                char_lines.append(line)
            
            embed.add_field(
                name="Characters",
                value="\n".join(char_lines) if char_lines else "No characters found.",
                inline=False
            )
        else:
            embed.add_field(
                name="No Characters",
                value="No characters match these filters.\nTry adjusting your filter settings!",
                inline=False
            )
        
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages} • Use dropdowns to filter")
        return embed
    
    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.primary, row=2)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} Not your inventory!", ephemeral=True)
        
        self.page = (self.page - 1) % self.max_pages
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary, row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} Not your inventory!", ephemeral=True)
        
        self.page = (self.page + 1) % self.max_pages
        await interaction.response.edit_message(embed=await self.get_embed(), view=self)


class InventoryRaritySelect(discord.ui.Select):
    """Filter by rarity tier."""
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label="All Rarities", value="all", emoji=GameEmojis.BOX, default=True),
            discord.SelectOption(label="Legendary", value="legendary", emoji=GameEmojis.LEGENDARY, description=f"5★ - 10,000+ {GameEmojis.HEARTS}"),
            discord.SelectOption(label="Epic", value="epic", emoji=GameEmojis.EPIC, description=f"4★ - 5,000+ {GameEmojis.HEARTS}"),
            discord.SelectOption(label="Rare", value="rare", emoji=GameEmojis.RARE, description=f"3★ - 1,000+ {GameEmojis.HEARTS}"),
            discord.SelectOption(label="Uncommon", value="uncommon", emoji=GameEmojis.UNCOMMON, description=f"2★ - 100+ {GameEmojis.HEARTS}"),
            discord.SelectOption(label="Common", value="common", emoji=GameEmojis.COMMON, description=f"1★ - <100 {GameEmojis.HEARTS}"),
        ]
        super().__init__(placeholder="🎖️ Filter by Rarity...", options=options, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.user.id:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} Not your inventory!", ephemeral=True)
        
        self.parent_view.rarity_filter = self.values[0]
        self.parent_view.filtered_chars = self.parent_view._filter_characters()
        self.parent_view.max_pages = max(1, (len(self.parent_view.filtered_chars) + self.parent_view.per_page - 1) // self.parent_view.per_page)
        self.parent_view.page = 0
        
        # Update default selection
        for opt in self.options:
            opt.default = opt.value == self.values[0]
        
        await interaction.response.edit_message(embed=await self.parent_view.get_embed(), view=self.parent_view)


class InventoryGenderSelect(discord.ui.Select):
    """Filter by gender."""
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label="All Genders", value="all", emoji="👥", default=True),
            discord.SelectOption(label="Waifu", value="female", emoji="♀️", description="Female characters"),
            discord.SelectOption(label="Husbando", value="male", emoji="♂️", description="Male characters"),
            discord.SelectOption(label="Unknown", value="unknown", emoji="⚧", description="Unknown gender"),
        ]
        super().__init__(placeholder="👤 Filter by Gender...", options=options, row=1)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.user.id:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} Not your inventory!", ephemeral=True)
        
        self.parent_view.gender_filter = self.values[0]
        self.parent_view.filtered_chars = self.parent_view._filter_characters()
        self.parent_view.max_pages = max(1, (len(self.parent_view.filtered_chars) + self.parent_view.per_page - 1) // self.parent_view.per_page)
        self.parent_view.page = 0
        
        # Update default selection
        for opt in self.options:
            opt.default = opt.value == self.values[0]
        
        await interaction.response.edit_message(embed=await self.parent_view.get_embed(), view=self.parent_view)


# ═══════════════════════════════════════════════════════════════
# MULTIPLAYER GAME VIEWS
# ═══════════════════════════════════════════════════════════════

class HangmanJoinView(discord.ui.View):
    """View for joining hangman game with visual waiting room"""
    def __init__(self, cog, game_id: str, host_user: discord.User = None):
        super().__init__(timeout=30)
        self.cog = cog
        self.game_id = game_id
        self.host_user = host_user
    
    async def _update_waiting_room(self, message):
        """Update the waiting room image with current players"""
        game = self.cog.active_games.get(self.game_id)
        if not game:
            return
        
        # Build player list with avatars
        players = []
        async with aiohttp.ClientSession() as session:
            for user_id in game["players"].keys():
                try:
                    user = await self.cog.bot.fetch_user(int(user_id))
                    avatar_bytes = None
                    if user.avatar:
                        avatar_bytes = await fetch_avatar_bytes(session, user.avatar.url)
                    players.append({"name": user.display_name, "avatar_bytes": avatar_bytes})
                except:
                    players.append({"name": "Player", "avatar_bytes": None})
        
        # Get host avatar
        host_avatar = None
        host_name = "Unknown"
        if self.host_user:
            host_name = self.host_user.display_name
            if self.host_user.avatar:
                async with aiohttp.ClientSession() as session:
                    host_avatar = await fetch_avatar_bytes(session, self.host_user.avatar.url)
        
        # Generate waiting room image
        word_len = len(game.get("word", ""))
        img_buffer = await generate_waiting_room_image(
            game_name="HANGMAN",
            host_name=host_name,
            host_avatar_bytes=host_avatar,
            players=players,
            max_players=5,
            extra_info=f"{word_len} letters • 6 lives"
        )
        
        file = discord.File(img_buffer, filename="hangman_lobby.png")
        embed = discord.Embed(color=discord.Color.blue())
        embed.set_image(url="attachment://hangman_lobby.png")
        embed.set_footer(text="Game starts in 30 seconds or when full!")
        
        await message.edit(embed=embed, attachments=[file])
    
    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game no longer exists!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        user_id = str(interaction.user.id)
        
        if game["started"]:
            self._remove_join_button()
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
        
        # Update waiting room image
        await self._update_waiting_room(interaction.message)
        
        # Start early if 5 players
        if len(game["players"]) >= 5:
            game["started"] = True
            self._remove_join_button()
            self.stop()
            await self.cog._start_hangman_game(self.game_id)
    
    def _remove_join_button(self):
        """Completely remove the join button when game starts."""
        for item in list(self.children):
            if isinstance(item, discord.ui.Button) and item.label == "Join Game":
                self.remove_item(item)
    
    async def on_timeout(self):
        """Handle timeout with proper cleanup and logging."""
        try:
            if self.game_id in self.cog.active_games:
                game = self.cog.active_games[self.game_id]
                if not game["started"]:
                    # Cancel game if not started
                    del self.cog.active_games[self.game_id]
                    logger.info(f"Hangman game {self.game_id} cancelled due to timeout")
        except Exception as e:
            logger.error(f"HangmanJoinView timeout error: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Handle errors in view interactions with proper logging."""
        logger.error(f"HangmanJoinView error in {item.__class__.__name__}: {error}", exc_info=True)
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while joining the game. Please try again.",
                    ephemeral=True
                )
        except Exception as response_error:
            logger.error(f"Failed to send error response: {response_error}")


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
                title="Hangman",
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
                title="Hangman",
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
                
                # Check if this is the first winner
                other_winners = [p for uid, p in game["players"].items() if uid != self.user_id and p["status"] == "won"]
                is_first_winner = len(other_winners) == 0
                
                embed = discord.Embed(
                    title="🏆 You Won!",
                    description=f"{HANGMAN_STAGES[player['wrong']]}\n**Word:** {game['word']}\n\n💰 Won **+{winnings}** stella points!",
                    color=discord.Color.green()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                
                # If first winner, notify channel and end game for all players
                if is_first_winner:
                    await self.cog._end_hangman_game(self.game_id, self.user_id)
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
                    title="Hangman",
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
    """View for joining wordle game with visual waiting room"""
    def __init__(self, cog, game_id: str, host_user: discord.User = None):
        super().__init__(timeout=30)
        self.cog = cog
        self.game_id = game_id
        self.host_user = host_user
    
    async def _update_waiting_room(self, message):
        """Update the waiting room image with current players"""
        game = self.cog.active_games.get(self.game_id)
        if not game:
            return
        
        # Build player list with avatars
        players = []
        async with aiohttp.ClientSession() as session:
            for user_id in game["players"].keys():
                try:
                    user = await self.cog.bot.fetch_user(int(user_id))
                    avatar_bytes = None
                    if user.avatar:
                        avatar_bytes = await fetch_avatar_bytes(session, user.avatar.url)
                    players.append({"name": user.display_name, "avatar_bytes": avatar_bytes})
                except:
                    players.append({"name": f"Player", "avatar_bytes": None})
        
        # Get host avatar
        host_avatar = None
        host_name = "Unknown"
        if self.host_user:
            host_name = self.host_user.display_name
            if self.host_user.avatar:
                async with aiohttp.ClientSession() as session:
                    host_avatar = await fetch_avatar_bytes(session, self.host_user.avatar.url)
        
        # Generate waiting room image
        img_buffer = await generate_waiting_room_image(
            game_name="WORDLE",
            host_name=host_name,
            host_avatar_bytes=host_avatar,
            players=players,
            max_players=5,
            extra_info="5-letter word • 6 attempts"
        )
        
        file = discord.File(img_buffer, filename="wordle_lobby.png")
        embed = discord.Embed(color=discord.Color.green())
        embed.set_image(url="attachment://wordle_lobby.png")
        embed.set_footer(text="Game starts in 30 seconds or when full!")
        
        await message.edit(embed=embed, attachments=[file])
    
    @discord.ui.button(label="Join Game", style=discord.ButtonStyle.green)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game no longer exists!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        user_id = str(interaction.user.id)
        
        if game["started"]:
            self._remove_join_button()
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
        
        # Update waiting room image
        await self._update_waiting_room(interaction.message)
        
        # Start early if 5 players
        if len(game["players"]) >= 5:
            game["started"] = True
            self._remove_join_button()
            self.stop()
            await self.cog._start_wordle_game(self.game_id)
    
    def _remove_join_button(self):
        """Completely remove the join button when game starts."""
        for item in list(self.children):
            if isinstance(item, discord.ui.Button) and item.label == "Join Game":
                self.remove_item(item)
    
    async def on_timeout(self):
        """Handle timeout with proper cleanup and logging."""
        try:
            if self.game_id in self.cog.active_games:
                game = self.cog.active_games[self.game_id]
                if not game["started"]:
                    # Cancel game if not started
                    del self.cog.active_games[self.game_id]
                    logger.info(f"Wordle game {self.game_id} cancelled due to timeout")
        except Exception as e:
            logger.error(f"WordleJoinView timeout error: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        """Handle errors in view interactions with proper logging."""
        logger.error(f"WordleJoinView error in {item.__class__.__name__}: {error}", exc_info=True)
        
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while joining the game. Please try again.",
                    ephemeral=True
                )
        except Exception as response_error:
            logger.error(f"Failed to send error response: {response_error}")


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
        
        # Fetch user avatar for the image
        user = interaction.user
        player_name = user.display_name
        avatar_bytes = None
        try:
            session = await self.cog.get_session()
            avatar_url = user.display_avatar.with_size(64).url
            avatar_bytes = await fetch_avatar_bytes(session, avatar_url)
        except:
            pass
        
        if guess == game["word"]:
            player["status"] = "won"
            attempt_num = len(player["attempts"])
            winnings = payouts.get(attempt_num, 100)
            guild_id = game["guild_id"]
            await self.cog.quest_data.add_balance(self.user_id, guild_id, winnings)
            
            # Generate win image with avatar
            img_buffer = generate_wordle_board_image(
                player["attempts"], game["word"], show_word=False,
                avatar_bytes=avatar_bytes, player_name=player_name
            )
            file = discord.File(img_buffer, filename="wordle_win.png")
            
            embed = discord.Embed(
                title="🏆 You Won!",
                description=f"💰 Won **+{winnings}** stella points!",
                color=discord.Color.gold()
            )
            embed.set_image(url="attachment://wordle_win.png")
            await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
            
            # End game for everyone and ping winner in channel
            await self.cog._end_wordle_game(self.game_id, self.user_id)
        elif len(player["attempts"]) >= 6:
            player["status"] = "lost"
            
            # Generate loss image with avatar
            img_buffer = generate_wordle_board_image(
                player["attempts"], game["word"], show_word=True,
                avatar_bytes=avatar_bytes, player_name=player_name
            )
            file = discord.File(img_buffer, filename="wordle_loss.png")
            
            embed = discord.Embed(
                title="💀 Game Over!",
                description=f"**Word was:** {game['word']}",
                color=discord.Color.red()
            )
            embed.set_image(url="attachment://wordle_loss.png")
            await interaction.response.edit_message(embed=embed, attachments=[file], view=None)
            
            # Check if all players are done
            await self.cog._check_wordle_game_end(self.game_id)
        else:
            # Continue playing - generate board image with avatar
            img_buffer = generate_wordle_board_image(
                player["attempts"], game["word"],
                avatar_bytes=avatar_bytes, player_name=player_name
            )
            file = discord.File(img_buffer, filename="wordle_board.png")
            
            embed = discord.Embed(
                title="🟩 Your Wordle Game",
                description=f"Click **Submit Guess** to enter a 5-letter word!\n"
                           f"❌ Wrong guess = **-15 stella points**",
                color=discord.Color.green()
            )
            embed.set_image(url="attachment://wordle_board.png")
            embed.add_field(name="Attempts", value=f"{len(player['attempts'])}/6", inline=True)
            
            await interaction.response.edit_message(embed=embed, attachments=[file])
        
        # Update leaderboard with live image
        await self.cog._update_wordle_leaderboard(self.game_id)


class WordleGuessView(discord.ui.View):
    """View for wordle game with submit button and view others"""
    def __init__(self, cog, game_id: str, user_id: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.game_id = game_id
        self.user_id = user_id
    
    @discord.ui.button(label="Submit Guess", style=discord.ButtonStyle.green, emoji="📝")
    async def submit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = WordleGuessModal(self.cog, self.game_id, self.user_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="View Others", style=discord.ButtonStyle.secondary, emoji="👀")
    async def view_others_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View other players' Wordle boards"""
        if self.game_id not in self.cog.active_games:
            return await interaction.response.send_message("❌ Game ended!", ephemeral=True)
        
        game = self.cog.active_games[self.game_id]
        other_players = {uid: pdata for uid, pdata in game["players"].items() if uid != self.user_id}
        
        if not other_players:
            return await interaction.response.send_message("👤 No other players in this game!", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        
        # Generate live image showing all other players' boards
        players_with_names = {}
        for uid, pdata in other_players.items():
            players_with_names[uid] = pdata.copy()
            if "display_name" not in players_with_names[uid]:
                try:
                    user = await self.cog.bot.fetch_user(int(uid))
                    players_with_names[uid]["display_name"] = user.display_name
                except:
                    players_with_names[uid]["display_name"] = "Player"
        
        img_buffer = generate_wordle_live_image(players_with_names, self.cog.bot)
        file = discord.File(img_buffer, filename="wordle_others.png")
        
        # Build status summary
        status_lines = []
        for uid, pdata in other_players.items():
            name = pdata.get("display_name", "Player")
            status = pdata.get("status", "playing")
            attempts = len(pdata.get("attempts", []))
            
            if status == "won":
                status_lines.append(f"🏆 **{name}** - Won!")
            elif status == "lost":
                status_lines.append(f"**{name}** - Lost ({attempts}/6)")
            elif status == "ended":
                status_lines.append(f"**{name}** - Game ended ({attempts}/6)")
            else:
                status_lines.append(f"**{name}** - Playing ({attempts}/6)")
        
        embed = discord.Embed(
            title="👀 Other Players' Progress",
            description="\n".join(status_lines) if status_lines else "No other players",
            color=discord.Color.blue()
        )
        embed.set_image(url="attachment://wordle_others.png")
        embed.set_footer(text="Their boards are hidden - only showing progress!")
        
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# SLOT MACHINE VIEW
# ═══════════════════════════════════════════════════════════════

class SlotMachineView(discord.ui.View):
    """View for slot machine with Play Again button"""
    def __init__(self, cog, user_id: str, guild_id: str, last_bet: int, results: list = None):
        super().__init__(timeout=180)  # Extended timeout for cooldown
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.last_bet = last_bet
        self.results = results or []
        self.cooldown_end = None
        
        # Start cooldown immediately
        import time
        self.cooldown_end = time.time() + 3600  # 60 minutes
    
    @discord.ui.button(label="Play Again", style=discord.ButtonStyle.green, emoji="🎰")
    async def play_again(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} This isn't your game!", ephemeral=True)
        
        # Check cooldown
        import time
        if self.cooldown_end and time.time() < self.cooldown_end:
            remaining = int(self.cooldown_end - time.time())
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60
            
            if hours > 0:
                time_str = f"**{hours}h {minutes}m {seconds}s**"
            else:
                time_str = f"**{minutes}m {seconds}s**"
                
            return await interaction.response.send_message(
                f"⏰ Slot machine is cooling down! Wait {time_str} before playing again.",
                ephemeral=True
            )
        
        # Check balance
        balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
        if balance < self.last_bet:
            return await interaction.response.send_message(
                f"❌ You need **{self.last_bet:,}** but only have **{balance:,}** stella points!", 
                ephemeral=True
            )
        
        # Disable button and start new game
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # Run the slot machine
        await self.cog._run_slot_machine(interaction.channel, interaction.user, self.last_bet)
    
    @discord.ui.button(label="Change Bet", style=discord.ButtonStyle.secondary, emoji="💰")
    async def change_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message(f"{GameEmojis.ERROR} This isn't your game!", ephemeral=True)
        
        modal = SlotBetModal(self.cog, self.user_id, self.guild_id)
        await interaction.response.send_modal(modal)


class SlotBetModal(discord.ui.Modal, title="Change Bet Amount"):
    """Modal for changing slot bet"""
    bet_input = discord.ui.TextInput(
        label="Enter bet amount (10 - 10,000)",
        placeholder="100",
        min_length=1,
        max_length=6,
        required=True
    )
    
    def __init__(self, cog, user_id: str, guild_id: str):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet = int(self.bet_input.value.replace(",", ""))
            if bet < 10:
                return await interaction.response.send_message("❌ Minimum bet is **10** pts!", ephemeral=True)
            if bet > 10000:
                return await interaction.response.send_message("❌ Maximum bet is **10,000** pts!", ephemeral=True)
            
            balance = await self.cog.quest_data.get_balance(self.user_id, self.guild_id)
            if balance < bet:
                return await interaction.response.send_message(
                    f"❌ You need **{bet:,}** but only have **{balance:,}** pts!", 
                    ephemeral=True
                )
            
            await interaction.response.defer()
            await self.cog._run_slot_machine(interaction.channel, interaction.user, bet)
        except ValueError:
            await interaction.response.send_message("❌ Invalid bet amount!", ephemeral=True)


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
        
        # Fallback option if no jobs are configured
        if not options:
            options = [
                discord.SelectOption(
                    label="No jobs available",
                    value="no_jobs",
                    description="Jobs system not configured",
                    emoji="❌"
                )
            ]
        
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
        
        if job_id == "no_jobs":
            return await interaction.response.send_message(
                "❌ No jobs are currently available. The jobs system needs to be configured.",
                ephemeral=True
            )
        
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
        
        # Calculate base reward
        pay_min, pay_max = self.job_data.get("pay_range", [50, 100])
        base_reward = random.randint(pay_min, pay_max)
        
        # Check for overtime event (10% chance)
        is_overtime = random.random() < 0.10
        overtime_bonus = base_reward if is_overtime else 0
        
        # Apply character bonus
        character = await self.cog.get_user_character(user_id, self.guild_id)
        char_bonus_amount = 0
        if character:
            work_config = GROUNDED_CONFIG.get("work", {})
            char_bonus = work_config.get("character_bonuses", {}).get(character, {})
            multiplier = char_bonus.get("multiplier", 1.0)
            char_bonus_amount = int(base_reward * (multiplier - 1))
        
        # Task bonus (random 0-20%)
        task_bonus = int(base_reward * random.uniform(0, 0.2))
        
        # Total reward
        total_reward = base_reward + char_bonus_amount + task_bonus + overtime_bonus
        
        # Add reward and set cooldown
        await self.cog.quest_data.add_balance(user_id, self.guild_id, total_reward)
        await self.cog.set_cooldown(user_id, "work")
        
        # Track total stars earned
        try:
            db = self.cog.quest_data.mongoConnect[self.cog.quest_data.DB_NAME]
            server_col = db["Servers"]
            await server_col.update_one(
                {"guild_id": self.guild_id},
                {"$inc": {f"members.{user_id}.total_stars_earned": total_reward}},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error tracking stars: {e}")
        
        new_balance = await self.cog.quest_data.get_balance(user_id, self.guild_id)
        
        # Generate paycheck image
        avatar_bytes = None
        try:
            session = await self.cog.get_session()
            avatar_url = interaction.user.display_avatar.with_size(128).url
            avatar_bytes = await fetch_avatar_bytes(session, avatar_url)
        except Exception as e:
            logger.debug(f"Avatar fetch failed: {e}")
        
        paycheck_buffer = generate_paycheck_image(
            job_title=self.job_data.get("title", "Worker"),
            job_emoji=self.job_data.get("emoji", "💼"),
            base_pay=base_reward,
            bonus=task_bonus,
            overtime=is_overtime,
            character_bonus=char_bonus_amount,
            pay_to=interaction.user.display_name,
            avatar_bytes=avatar_bytes
        )
        file = discord.File(paycheck_buffer, filename="paycheck.png")
        
        if is_overtime:
            embed = discord.Embed(
                title=f"⭐ OVERTIME! {task_name}",
                description=f"{task_message}\n\n🎉 **You worked overtime and earned DOUBLE pay!**",
                color=discord.Color.gold()
            )
        else:
            embed = discord.Embed(
                title=f"{self.job_data['emoji']} {task_name}",
                description=task_message,
                color=discord.Color.green()
            )
        
        embed.set_image(url="attachment://paycheck.png")
        embed.add_field(name="💳 New Balance", value=f"**{new_balance:,}** pts", inline=True)
        
        if character:
            embed.set_footer(text=f"🌟 {character} bonus applied!")
        
        await interaction.response.edit_message(embed=embed, attachments=[file], view=None)

