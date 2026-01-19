"""Cover Art Gallery View with advanced filtering and navigation"""

import discord
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CoverGalleryView(discord.ui.View):
    """Advanced view for browsing cover art with source filtering, view modes, and navigation"""
    
    def __init__(self, cover_system, character: Dict, user_id: str, guild_id: str, all_images: List[Dict], current_page: int = 1, total_pages: int = 1):
        super().__init__(timeout=300)
        self.cover_system = cover_system
        self.character = character
        self.user_id = user_id
        self.guild_id = guild_id
        self.all_images = all_images  # All images from all sources
        self.filtered_images = all_images  # Currently filtered images
        self.current_page = current_page
        self.message: Optional[discord.Message] = None
        
        # UI State
        self.selected_sources = []  # Empty = all sources
        self.view_mode = "gallery"  # "gallery" or "single"
        
        # Calculate total_pages based on actual image count (3 images per page in gallery mode)
        # This overrides any passed-in total_pages which may have been calculated differently
        images_per_page = 3  # Gallery mode default
        self.total_pages = max(1, (len(all_images) + images_per_page - 1) // images_per_page)
        
        # Extract available sources dynamically
        self.available_sources = self._get_available_sources()
        
        # Add UI components
        self._add_ui_components()
    
    def _get_available_sources(self) -> List[str]:
        """Extract unique sources from images"""
        sources = set()
        for img in self.all_images:
            source = img.get('source', 'Unknown')
            if source:
                sources.add(source)
        return sorted(list(sources))
    
    def _add_ui_components(self):
        """Add all UI components in proper order"""
        # Row 0: Source Filter Select
        if self.available_sources:
            self.add_item(SourceFilterSelect(self.available_sources))
        
        # Row 1: View Mode Select
        self.add_item(ViewModeSelect())
        
        # Row 2: Navigation buttons (Prev, Page, Next)
        self.add_item(PrevButton())
        self.add_item(PageButton(self.current_page, self.total_pages))
        self.add_item(NextButton())
    
    def _apply_filters(self):
        """Apply source filters to images"""
        if not self.selected_sources:
            # No filter = show all
            self.filtered_images = self.all_images
        else:
            # Filter by selected sources
            self.filtered_images = [
                img for img in self.all_images 
                if img.get('source', 'Unknown') in self.selected_sources
            ]
        
        # Recalculate total pages based on filtered results
        # Gallery mode shows 3 images per page (3 embeds), single mode shows 1
        images_per_page = 1 if self.view_mode == "single" else 3
        self.total_pages = max(1, (len(self.filtered_images) + images_per_page - 1) // images_per_page)
        
        # Adjust current page if needed
        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
    
    def _get_current_page_images(self) -> List[Dict]:
        """Get images for current page based on view mode"""
        # Gallery mode shows 3 images per page (3 embeds), single mode shows 1
        images_per_page = 1 if self.view_mode == "single" else 3
        start_idx = (self.current_page - 1) * images_per_page
        end_idx = start_idx + images_per_page
        return self.filtered_images[start_idx:end_idx]
    
    async def refresh_view(self, interaction: discord.Interaction):
        """Refresh the view with current filters and settings"""
        import asyncio
        
        self._apply_filters()
        
        current_images = self._get_current_page_images()
        
        if not current_images:
            await interaction.response.send_message(
                "❌ No images match the selected filters!",
                ephemeral=True
            )
            return
        
        # Create embeds based on view mode
        embeds = await self.cover_system.create_cover_art_embeds(
            self.character, current_images, self.current_page, self.total_pages
        )
        
        # Update page button label
        for child in self.children:
            if isinstance(child, PageButton):
                child.label = f"{self.current_page}/{self.total_pages}"
                break
        
        # Give Discord a moment to process/cache the image URLs
        await asyncio.sleep(0.1)
        
        try:
            await interaction.response.edit_message(embeds=embeds, view=self)
        except discord.InteractionResponded:
            await interaction.edit_original_response(embeds=embeds, view=self)
    
    async def on_timeout(self):
        """Disable all components when view times out"""
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass


class SourceFilterSelect(discord.ui.Select):
    """Select menu for filtering by image sources"""
    
    def __init__(self, available_sources: List[str]):
        options = [
            discord.SelectOption(
                label="All Sources",
                value="all",
                description="Show images from all sources",
                emoji="🌐"
            )
        ]
        
        # Add each source as an option
        source_emojis = {
            "Safebooru": "🛡️",
            "Danbooru": "🎨",
            "Gelbooru": "🖼️",
            "Yande.re": "⭐",
            "Konachan": "🌸",
            "TBIB": "📚",
            "Anime-Pictures": "🎭",
            "Tumblr": "📱"
        }
        
        for source in available_sources:
            emoji = source_emojis.get(source, "📷")
            options.append(
                discord.SelectOption(
                    label=source,
                    value=source,
                    description=f"Show only {source} images",
                    emoji=emoji
                )
            )
        
        super().__init__(
            placeholder="🔍 Filter by source...",
            options=options,
            min_values=1,
            max_values=len(options),
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: CoverGalleryView = self.view
        
        # Update selected sources
        if "all" in self.values:
            view.selected_sources = []
        else:
            view.selected_sources = self.values
        
        # Reset to page 1 when filter changes
        view.current_page = 1
        
        await view.refresh_view(interaction)


class ViewModeSelect(discord.ui.Select):
    """Select menu for switching view modes"""
    
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Gallery View",
                value="gallery",
                description="Show 3 images per page",
                emoji="🖼️"
            ),
            discord.SelectOption(
                label="Single View",
                value="single",
                description="Show 1 image per page",
                emoji="🔍"
            )
        ]
        
        super().__init__(
            placeholder="👁️ View Mode: Gallery",
            options=options,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: CoverGalleryView = self.view
        
        view.view_mode = self.values[0]
        
        # Update placeholder
        mode_name = "Gallery" if view.view_mode == "gallery" else "Single"
        self.placeholder = f"👁️ View Mode: {mode_name}"
        
        # Reset to page 1 when view mode changes
        view.current_page = 1
        
        await view.refresh_view(interaction)


class PrevButton(discord.ui.Button):
    """Previous page button"""
    
    def __init__(self):
        super().__init__(
            label="◀️ Prev",
            style=discord.ButtonStyle.primary,
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: CoverGalleryView = self.view
        
        if view.current_page <= 1:
            await interaction.response.send_message(
                "❌ You're already on the first page!",
                ephemeral=True
            )
            return
        
        view.current_page -= 1
        await view.refresh_view(interaction)


class PageButton(discord.ui.Button):
    """Page indicator button - click to jump to a specific page"""
    
    def __init__(self, current_page: int, total_pages: int):
        super().__init__(
            label=f"{current_page}/{total_pages}",
            style=discord.ButtonStyle.secondary,
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Open modal to jump to a specific page"""
        view: CoverGalleryView = self.view
        
        modal = PageJumpModal(view)
        await interaction.response.send_modal(modal)


class NextButton(discord.ui.Button):
    """Next page button"""
    
    def __init__(self):
        super().__init__(
            label="Next ▶️",
            style=discord.ButtonStyle.primary,
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: CoverGalleryView = self.view
        
        if view.current_page >= view.total_pages:
            await interaction.response.send_message(
                "❌ You're already on the last page!",
                ephemeral=True
            )
            return
        
        view.current_page += 1
        await view.refresh_view(interaction)


class PageJumpModal(discord.ui.Modal, title="Jump to Page"):
    """Modal for jumping to a specific page"""
    
    page_number = discord.ui.TextInput(
        label="Page Number",
        placeholder="Enter page number...",
        required=True,
        min_length=1,
        max_length=5,
        style=discord.TextStyle.short
    )
    
    def __init__(self, view: CoverGalleryView):
        super().__init__()
        self.view = view
        self.page_number.default = str(view.current_page)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value)
            
            if page < 1:
                await interaction.response.send_message(
                    "❌ Page number must be at least 1!",
                    ephemeral=True
                )
                return
            
            if page > self.view.total_pages:
                await interaction.response.send_message(
                    f"❌ Page number must be at most {self.view.total_pages}!",
                    ephemeral=True
                )
                return
            
            self.view.current_page = page
            await self.view.refresh_view(interaction)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number!",
                ephemeral=True
            )
