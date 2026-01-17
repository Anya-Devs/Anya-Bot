"""Cover Art Gallery View with pagination and buying functionality"""

import discord
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CoverGalleryView(discord.ui.View):
    """View for browsing cover art gallery with pagination and purchase options"""
    
    def __init__(self, cover_system, character: Dict, user_id: str, guild_id: str, images: List[Dict], current_page: int = 1, total_pages: int = 1):
        super().__init__(timeout=180)
        self.cover_system = cover_system
        self.character = character
        self.user_id = user_id
        self.guild_id = guild_id
        self.current_images = images
        self.current_page = current_page
        self.total_pages = total_pages
        self.message: Optional[discord.Message] = None
        
        for child in self.children:
            if child.custom_id == "jump_page":
                child.label = f"{self.current_page}/{self.total_pages}"
                break
    
    async def on_timeout(self):
        """Disable buttons when view times out"""
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.grey, custom_id="prev_page")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if self.current_page <= 1:
            await interaction.response.send_message("You're already on the first page!", ephemeral=True)
            return
        
        # Defer immediately - no loading message
        await interaction.response.defer()
        
        try:
            char_name = self.character.get('name', '')
            series_name = self.character.get('anime', '')
            char_uid = self.character.get('uid', '')
            new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, self.current_page - 1, 30, char_uid)
            
            if new_images:
                self.current_page -= 1
                self.current_images = new_images
                
                embeds = await self.cover_system.create_cover_art_embeds(
                    self.character, new_images, self.current_page, self.total_pages
                )
                
                for child in self.children:
                    if child.custom_id == "jump_page":
                        child.label = f"{self.current_page}/{self.total_pages}"
                        break
                
                await interaction.message.edit(embeds=embeds, view=self)
        except Exception as e:
            logger.error(f"Error loading previous page: {e}")
            await interaction.followup.send("❌ Error loading previous page!", ephemeral=True)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.grey, custom_id="next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        if self.current_page >= self.total_pages:
            await interaction.response.send_message("You're already on the last page!", ephemeral=True)
            return
        
        # Defer immediately - no loading message
        await interaction.response.defer()
        
        try:
            char_name = self.character.get('name', '')
            series_name = self.character.get('anime', '')
            char_uid = self.character.get('uid', '')
            new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, self.current_page + 1, 30, char_uid)
            
            if new_images:
                self.current_page += 1
                self.current_images = new_images
                
                embeds = await self.cover_system.create_cover_art_embeds(
                    self.character, new_images, self.current_page, self.total_pages
                )
                
                for child in self.children:
                    if child.custom_id == "jump_page":
                        child.label = f"{self.current_page}/{self.total_pages}"
                        break
                
                await interaction.message.edit(embeds=embeds, view=self)
        except Exception as e:
            logger.error(f"Error loading next page: {e}")
            await interaction.followup.send("❌ Error loading next page!", ephemeral=True)
    
    @discord.ui.button(label="page/max", style=discord.ButtonStyle.secondary, custom_id="jump_page")
    async def jump_to_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Jump to a specific page"""
        from .cover_art import JumpToPageModal
        
        modal = JumpToPageModal(self.current_page, self.total_pages)
        await interaction.response.send_modal(modal)
        
        await modal.wait()
        
        if modal.page_number is not None:
            target_page = modal.page_number
            
            if target_page < 1 or target_page > self.total_pages:
                await interaction.followup.send(f"Page must be between 1 and {self.total_pages}!", ephemeral=True)
                return
            
            if target_page == self.current_page:
                await interaction.followup.send("You're already on that page!", ephemeral=True)
                return
            
            try:
                char_name = self.character.get('name', '')
                series_name = self.character.get('anime', '')
                char_uid = self.character.get('uid', '')
                new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, target_page, 30, char_uid)
                
                if new_images:
                    self.current_page = target_page
                    self.current_images = new_images
                    
                    embeds = await self.cover_system.create_cover_art_embeds(
                        self.character, new_images, self.current_page, self.total_pages
                    )
                    
                    button.label = f"{self.current_page}/{self.total_pages}"
                    
                    await interaction.message.edit(embeds=embeds, view=self)
                else:
                    # Page is empty - adjust total_pages to prevent accessing non-existent pages
                    self.total_pages = max(1, target_page - 1)
                    button.label = f"{self.current_page}/{self.total_pages}"
                    await interaction.message.edit(view=self)
                    await interaction.followup.send(f"⚠️ Page {target_page} has no images. Max pages adjusted to {self.total_pages}.", ephemeral=True)
                    
            except Exception as e:
                logger.error(f"Error jumping to page: {e}")
                await interaction.followup.send("Error jumping to page!", ephemeral=True)
    
    @discord.ui.button(label="🔍 View Details", style=discord.ButtonStyle.green, custom_id="view_details")
    async def view_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View detailed information about current images"""
        details_embed = discord.Embed(
            title="📊 Image Details",
            description=f"Page {self.current_page}/{self.total_pages}",
            color=discord.Color.blue()
        )
        
        for i, img in enumerate(self.current_images[:3], 1):
            seq_id = img.get('sequential_id', img.get('id', 'N/A'))
            details_embed.add_field(
                name=f"🖼️ Option {i} (ID: {seq_id})",
                value=f"**Source:** {img.get('source', 'Unknown')}\n"
                      f"**Score:** {img.get('score', 0)}\n"
                      f"**Size:** {img.get('width', 0)}×{img.get('height', 0)}\n"
                      f"**Tags:** {', '.join(img.get('tags', [])[:5])}",
                inline=True
            )
        
        await interaction.response.send_message(embed=details_embed, ephemeral=True)
