# Search & API Commands
# Commands: search, google, youtube, video, art, translate, weather, define, urban, wiki, image
from imports.discord_imports import *
from datetime import datetime, timezone
from typing import Optional, Literal, Set
from io import BytesIO
from utils.cogs.search import (
    GoogleSearch, YouTubeSearch, TranslationAPI, WeatherAPI,
    DictionaryAPI, WikipediaAPI, ArtGalleryAPI, UrbanDictionaryAPI,
    SearchViews
)
from utils.cogs.art import ART_SOURCES, ArtAggregator
from data.local.const import primary_color
import re

# ═══════════════════════════════════════════════════════════════
# CONTENT POLICY - Prohibited tags that violate Discord TOS
# ═══════════════════════════════════════════════════════════════

PROHIBITED_TAGS = {
    # CSAM / Minor sexualization
    "loli", "lolicon", "shota", "shotacon", "toddlercon", "child", "minor",
    "underage", "young_girl", "young_boy", "elementary", "preschool",
    # Gore / Extreme violence
    "gore", "guro", "snuff", "death", "dismemberment", "decapitation",
    "mutilation", "torture", "vore", "cannibalism", "necrophilia",
    # Bodily waste
    "scat", "scatology", "piss", "urine", "pee", "feces", "shit", "diaper",
    "watersports", "coprophilia", "omorashi",
    # Bestiality
    "bestiality", "zoophilia", "feral", "animal_abuse",
    # Non-consensual
    "rape", "non-con", "noncon", "forced", "drugged", "unconscious_sex",
    # Other illegal
    "real_child", "csam", "cp", "pedo", "pedophilia",
}

def contains_prohibited_content(text: str) -> bool:
    """Check if text contains any prohibited terms"""
    if not text:
        return False
    text_lower = text.lower().replace("-", "_").replace(" ", "_")
    # Check each prohibited tag
    for tag in PROHIBITED_TAGS:
        # Match as whole word or with underscores
        if re.search(rf'\b{re.escape(tag)}\b', text_lower) or tag in text_lower:
            return True
    return False

def filter_prohibited_results(results: list) -> list:
    """Filter out results that contain prohibited tags"""
    if not results:
        return results
    
    filtered = []
    for r in results:
        # Check tags
        tags = r.get("tags", [])
        if isinstance(tags, str):
            tags = tags.split()
        
        tags_str = " ".join(str(t).lower() for t in tags)
        
        # Check if any prohibited tag is in the result's tags
        is_prohibited = False
        for tag in PROHIBITED_TAGS:
            if tag in tags_str:
                is_prohibited = True
                break
        
        if not is_prohibited:
            filtered.append(r)
    
    return filtered


# ═══════════════════════════════════════════════════════════════
# ART GALLERY VIEW - Multi-source, multi-image gallery with filters
# ═══════════════════════════════════════════════════════════════

class PageSelectorModal(discord.ui.Modal, title="Go to Page"):
    """Modal for jumping to a specific page"""
    page_input = discord.ui.TextInput(
        label="Page Number",
        placeholder="Enter page number...",
        required=True,
        max_length=5
    )
    
    def __init__(self, max_pages: int):
        super().__init__()
        self.max_pages = max_pages
        self.selected_page = None
        self.page_input.placeholder = f"Enter 1-{max_pages}"
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            page_num = int(self.page_input.value)
            if 1 <= page_num <= self.max_pages:
                self.selected_page = page_num - 1  # Convert to 0-indexed
                await interaction.response.defer()
            else:
                await interaction.response.send_message(f"❌ Page must be between 1 and {self.max_pages}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number", ephemeral=True)


class ArtSourceSelect(discord.ui.Select):
    """Multi-select dropdown for choosing art sources"""
    
    def __init__(self, available_sources: dict, selected_sources: Set[str], is_nsfw: bool, sources_with_results: Set[str], row: int = 0):
        # Get available sources based on NSFW and safety requirements
        self.available_sources = {}
        for key, meta in ART_SOURCES.items():
            # Block NSFW-only sources if not in NSFW channel
            if meta["nsfw_only"] and not is_nsfw:
                continue
            # Block mixed-content sources if not in NSFW channel
            if meta.get("requires_nsfw_channel") and not is_nsfw:
                continue
            # Only show sources that have results for this query
            if sources_with_results is not None and key not in sources_with_results:
                continue
            self.available_sources[key] = meta
        
        options = []
        for key, meta in self.available_sources.items():
            options.append(discord.SelectOption(
                label=meta["name"],
                value=key,
                description=meta["description"][:50],
                default=key in selected_sources
            ))
        
        # Limit to 25 options (Discord limit)
        options = options[:25]

        disabled = False
        if not options:
            options = [discord.SelectOption(label="No sources available", value="__none__")]
            disabled = True
        
        # Ensure max_values doesn't exceed Discord's limit of 25
        max_vals = min(len(options), 25) if not disabled else 1
        min_vals = 1 if not disabled else 0
        
        super().__init__(
            placeholder="Select art sources...",
            min_values=min_vals,
            max_values=max_vals,
            options=options,
            row=row,
            disabled=disabled
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: ArtGalleryView = self.view
        if interaction.user != view.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        # Skip if disabled or no valid selection
        if self.disabled or "__none__" in self.values:
            return await interaction.response.send_message("❌ No valid sources selected!", ephemeral=True)
        
        # Update selected sources
        view.selected_sources = set(self.values)
        
        # Update select defaults
        for opt in self.options:
            opt.default = opt.value in view.selected_sources
        
        # Refetch results with new sources
        await interaction.response.defer()
        view.page = 0
        view.results = []
        
        try:
            await view.fetch_results()
            embeds = view.build_embeds()
            view.update_buttons()
            await interaction.edit_original_response(embeds=embeds, view=view)
        except Exception as e:
            await interaction.followup.send(f"❌ Error updating results: {str(e)[:100]}", ephemeral=True)


class ArtViewModeSelect(discord.ui.Select):
    """Select for switching between single and gallery view modes"""
    
    def __init__(self, current_mode: str = "gallery", row: int = 1):
        options = [
            discord.SelectOption(
                label="Gallery Mode",
                value="gallery",
                description="Show 4 images per page",
                default=current_mode == "gallery"
            ),
            discord.SelectOption(
                label="Single Mode",
                value="single",
                description="Show 1 large image per page",
                default=current_mode == "single"
            ),
            discord.SelectOption(
                label="Preview Mode",
                value="preview",
                description="Show 6 thumbnail previews",
                default=current_mode == "preview"
            )
        ]
        super().__init__(
            placeholder="View mode...",
            options=options,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: ArtGalleryView = self.view
        if interaction.user != view.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        old_mode = view.view_mode
        new_mode = self.values[0]
        
        # Calculate which image index we're currently viewing
        old_images_per_page = {"gallery": 3, "single": 1, "preview": 6}.get(old_mode, 3)
        new_images_per_page = {"gallery": 3, "single": 1, "preview": 6}.get(new_mode, 3)
        
        # Get the first image index of current page and translate to new page
        current_image_index = view.page * old_images_per_page
        new_page = current_image_index // new_images_per_page
        
        view.view_mode = new_mode
        view.page = min(new_page, max(0, (len(view.results) - 1) // new_images_per_page)) if view.results else 0
        
        # Update select defaults
        for opt in self.options:
            opt.default = opt.value == view.view_mode
        
        embeds = view.build_embeds()
        view.update_buttons()
        await interaction.response.edit_message(embeds=embeds, view=view)


class ArtGalleryView(discord.ui.View):
    """Advanced art gallery with multi-source selection and gallery mode"""
    
    def __init__(
        self, 
        cog,
        author: discord.Member,
        query: str,
        is_nsfw: bool,
        ctx,
        initial_results: list = None,
        selected_sources: Set[str] = None
    ):
        super().__init__(timeout=300)  # 5 minute timeout
        self.cog = cog
        self.author = author
        self.query = query
        self.is_nsfw = is_nsfw
        self.ctx = ctx
        self.results = initial_results or []
        self.page = 0
        self.view_mode = "gallery"  # gallery, single, preview
        self.loading_more = False
        self.api_page = 0  # Track API pagination
        self.source_pages = {}  # Track page number per source for pagination
        self.total_loaded = len(initial_results) if initial_results else 0
        self.background_loading = False
        self.all_loaded = False
        
        # Source category filter: "all", "safe", "mix", "nsfw"
        self.source_category = "mix"
        
        self.available_sources = self.get_available_sources(self.is_nsfw)
        
        # Default to sources matching the default category (mix)
        if selected_sources is None:
            filtered_sources = self.get_sources_by_category()
            self.selected_sources = set(filtered_sources.keys())
        else:
            self.selected_sources = selected_sources
        
        # Initialize source pages
        for source in self.selected_sources:
            self.source_pages[source] = 0

        self.sources_with_results = self.get_sources_with_results()
        
        self._setup_components()
    
    def _setup_components(self):
        """Setup all UI components - simplified layout"""
        self.clear_items()
        
        # Row 0: Source selection (filtered by category)
        filtered_sources = self.get_sources_by_category()
        self.source_select = ArtSourceSelect(
            filtered_sources, 
            self.selected_sources,
            self.is_nsfw,
            self.sources_with_results,
            row=0
        )
        self.add_item(self.source_select)
        
        # Row 1: View mode selection
        self.mode_select = ArtViewModeSelect(self.view_mode, row=1)
        self.add_item(self.mode_select)
        
        # Row 2: Navigation buttons (simplified)
        self.add_item(self.prev_btn)
        self.add_item(self.page_indicator)
        self.add_item(self.next_btn)
        self.add_item(self.load_more_btn)
    
    @property
    def images_per_page(self) -> int:
        """Number of images per page based on view mode"""
        return {"gallery": 3, "single": 1, "preview": 6}.get(self.view_mode, 3)
    
    @property
    def max_pages(self) -> int:
        """Calculate max pages"""
        if not self.results:
            return 1
        return max(1, (len(self.results) + self.images_per_page - 1) // self.images_per_page)
    
    async def fetch_results(self, aggressive: bool = True):
        """Fetch art results from selected sources
        
        Args:
            aggressive: If True, fetches multiple pages from all sources at once
        """
        if not hasattr(self.cog, 'art_aggregator'):
            import aiohttp
            if not hasattr(self.cog, 'session') or self.cog.session.closed:
                self.cog.session = aiohttp.ClientSession()
            self.cog.art_aggregator = ArtAggregator(self.cog.session)
        
        new_results = await self.cog.art_aggregator.search_all(
            self.query,
            limit=500,  # Higher limit for aggressive loading
            nsfw=self.is_nsfw,
            selected_sources=self.selected_sources,
            page=self.api_page,
            aggressive_load=aggressive,
            max_pages_per_source=10 if aggressive else 1  # 10 pages for load all button
        )
        
        # Filter out prohibited content
        new_results = filter_prohibited_results(new_results)
        
        if new_results:
            # Add new results, avoiding duplicates
            existing_ids = {(r.get("source"), r.get("id")) for r in self.results}
            added = 0
            for r in new_results:
                if (r.get("source"), r.get("id")) not in existing_ids:
                    self.results.append(r)
                    existing_ids.add((r.get("source"), r.get("id")))
                    added += 1

            self.refresh_sources_with_results()
            
            self.total_loaded = len(self.results)
            
            # If we got fewer than expected, we might be done
            if added < 50:
                self.all_loaded = True
            
            return added
        else:
            self.all_loaded = True
            return 0
    
    async def fetch_from_source(self, source_key: str, page: int = None):
        """Fetch next page from a specific source
        
        Args:
            source_key: The source to fetch from
            page: Specific page number, or None to use tracked page
        """
        if not hasattr(self.cog, 'art_aggregator'):
            import aiohttp
            if not hasattr(self.cog, 'session') or self.cog.session.closed:
                self.cog.session = aiohttp.ClientSession()
            self.cog.art_aggregator = ArtAggregator(self.cog.session)
        
        # Get current page for this source
        if page is None:
            page = self.source_pages.get(source_key, 0) + 1
        
        # Fetch from specific source
        new_results = await self.cog.art_aggregator.search_source(
            source_key,
            self.query,
            limit=50,
            nsfw=self.is_nsfw,
            page=page
        )
        
        # Filter out prohibited content
        new_results = filter_prohibited_results(new_results)
        
        if new_results:
            # Add new results, avoiding duplicates
            existing_ids = {(r.get("source"), r.get("id")) for r in self.results}
            added = 0
            for r in new_results:
                if (r.get("source"), r.get("id")) not in existing_ids:
                    self.results.append(r)
                    existing_ids.add((r.get("source"), r.get("id")))
                    added += 1

            self.refresh_sources_with_results()
            
            # Update source page tracker
            self.source_pages[source_key] = page
            self.total_loaded = len(self.results)
            
            return added
        return 0
    
    async def fetch_more(self, aggressive: bool = False):
        """Fetch more results when approaching the end"""
        if self.loading_more or self.all_loaded:
            return 0
        self.loading_more = True
        try:
            self.api_page += 1
            added = await self.fetch_results(aggressive=aggressive)
            return added
        finally:
            self.loading_more = False
    
    async def start_background_loading(self):
        """Start background task to continuously load more results"""
        if self.background_loading or self.all_loaded:
            return
        
        self.background_loading = True
        
        # Continue fetching in background
        while not self.all_loaded and self.background_loading:
            try:
                added = await self.fetch_more(aggressive=True)
                if added == 0:
                    break
                # Small delay to avoid overwhelming the APIs
                await asyncio.sleep(2)
            except Exception:
                break
        
        self.background_loading = False
    
    def get_available_sources(self, nsfw: bool = False) -> dict:
        """Get available sources based on NSFW setting and channel safety"""
        available = {}
        for key, meta in ART_SOURCES.items():
            # Block NSFW-only sources if not in NSFW channel
            if meta["nsfw_only"] and not nsfw:
                continue
            # Block mixed-content sources if not in NSFW channel
            if meta.get("requires_nsfw_channel") and not nsfw:
                continue
            available[key] = meta
        return available
    
    def get_sources_by_category(self) -> dict:
        """Get sources filtered by the current category (safe/mix/nsfw/all)"""
        if self.source_category == "all":
            return self.available_sources
        
        filtered = {}
        for key, meta in self.available_sources.items():
            if self.source_category == "safe":
                # Safe sources: not nsfw_only and don't require nsfw channel
                if not meta["nsfw_only"] and not meta.get("requires_nsfw_channel"):
                    filtered[key] = meta
            elif self.source_category == "mix":
                # Mixed sources: require nsfw channel but not nsfw_only
                if not meta["nsfw_only"] and meta.get("requires_nsfw_channel"):
                    filtered[key] = meta
            elif self.source_category == "nsfw":
                # NSFW only sources
                if meta["nsfw_only"]:
                    filtered[key] = meta
        return filtered

    def get_sources_with_results(self) -> Set[str]:
        """Return ART_SOURCES keys that have at least 1 result in current results list."""
        if not self.results:
            return set()

        name_to_key = {meta.get("name"): key for key, meta in ART_SOURCES.items()}
        lower_name_to_key = {str(meta.get("name", "")).lower(): key for key, meta in ART_SOURCES.items()}

        found = set()
        for r in self.results:
            src = r.get("source")
            if not src:
                continue
            key = name_to_key.get(src) or lower_name_to_key.get(str(src).lower())
            if key:
                found.add(key)
        return found

    def refresh_sources_with_results(self):
        """Refresh dropdown options to only include sources that currently have results."""
        new_sources = self.get_sources_with_results()
        if new_sources != getattr(self, "sources_with_results", set()):
            self.sources_with_results = new_sources

            # Keep selections only if they still exist
            self.selected_sources = set(self.selected_sources) & set(self.sources_with_results)
            if not self.selected_sources and self.sources_with_results:
                self.selected_sources = set(self.sources_with_results)

            self._setup_components()
    
    def get_page_results(self) -> list:
        """Get results for current page"""
        start = self.page * self.images_per_page
        end = start + self.images_per_page
        return self.results[start:end]
    
    def build_embeds(self) -> list:
        """Build embeds for current page based on view mode"""
        page_results = self.get_page_results()
        
        if not page_results:
            loading_msg = "Loading more results..." if self.background_loading else "No artwork found. Try different sources or search terms."
            embed = discord.Embed(
                title=f"🎨 Art Search: {self.query[:40]}",
                description=loading_msg,
                color=discord.Color.orange() if not self.background_loading else discord.Color.blue()
            )
            embed.add_field(
                name="Selected Sources",
                value=", ".join([ART_SOURCES.get(s, {}).get("name", s) for s in self.selected_sources][:5]) or "None",
                inline=False
            )
            if self.total_loaded > 0:
                embed.add_field(
                    name="Progress",
                    value=f"Loaded {self.total_loaded} results" + (" (still loading...)" if self.background_loading else ""),
                    inline=False
                )
            return [embed]
        
        embeds = []
        base_color = discord.Color.from_rgb(255, 105, 180) if self.is_nsfw else primary_color()
        
        if self.view_mode == "single":
            # Single large image mode
            art = page_results[0]
            embed = self._build_single_embed(art, base_color)
            embeds.append(embed)
            
        elif self.view_mode == "gallery":
            # Gallery mode - up to 4 images with embeds
            for i, art in enumerate(page_results):
                embed = self._build_gallery_embed(art, i, len(page_results), base_color)
                embeds.append(embed)
                
        elif self.view_mode == "preview":
            # Preview mode - compact list with thumbnails
            embed = self._build_preview_embed(page_results, base_color)
            embeds.append(embed)
        
        return embeds
    
    def _build_single_embed(self, art: dict, color) -> discord.Embed:
        """Build embed for single image view"""
        embed = discord.Embed(
            title=f"🎨 {self.query[:50]}",
            url=art.get("page_url"),
            color=color
        )
        
        # Content safety warning system
        rating = art.get("rating", "s")
        source = art.get("source", "Unknown")
        source_meta = ART_SOURCES.get(source.lower().replace(" ", "_").replace(".", ""), {})
        requires_nsfw = source_meta.get("requires_nsfw_channel", False)
        
        # Build safety warning
        warnings = []
        if rating in ["e", "explicit"]:
            warnings.append("🔞 **Explicit NSFW Content**")
        elif rating in ["q", "questionable"]:
            warnings.append("⚠️ **Questionable Content**")
        
        # Warn about mixed-content sources
        if requires_nsfw and not self.is_nsfw:
            warnings.append("⚠️ **Warning: This source may contain unsafe content**")
        
        if warnings:
            embed.description = " | ".join(warnings)
        else:
            embed.description = "✅ Safe content"
        
        # Art info in compact format
        info_parts = [
            f"**Source:** {art.get('source', 'Unknown')}",
            f"**Artist:** {art.get('artist', 'Unknown')[:30]}",
            f"**Score:** ⭐ {art.get('score', 0)}"
        ]
        
        if art.get("width") and art.get("height"):
            info_parts.append(f"**Size:** {art.get('width')}x{art.get('height')}")
        
        embed.add_field(name="Info", value=" • ".join(info_parts), inline=False)
        
        # Tags
        tags = art.get("tags", [])[:12]
        if tags:
            tag_str = " ".join([f"`{tag}`" for tag in tags])
            embed.add_field(name="Tags", value=tag_str[:1024], inline=False)
        
        # Image
        embed.set_image(url=art.get("url"))
        
        # Footer with loading indicator
        art_id = f"{art.get('source', 'unknown').lower()}_{art.get('id', 'unknown')}"
        footer_text = f"Page {self.page + 1}/{self.max_pages} • {len(self.results)} total"
        if self.background_loading:
            footer_text += " • 🔄 Loading more..."
        elif self.all_loaded:
            footer_text += " • ✅ All loaded"
        footer_text += f" • ID: {art_id}"
        embed.set_footer(text=footer_text)
        
        return embed
    
    def _build_gallery_embed(self, art: dict, index: int, total: int, color) -> discord.Embed:
        """Build embed for gallery mode (multiple images)"""
        # Only first embed gets full info
        if index == 0:
            desc_parts = [f"Showing {total} images • Page {self.page + 1}/{self.max_pages}"]
            if self.is_nsfw:
                desc_parts.insert(0, "🔞 NSFW")
            if self.background_loading:
                desc_parts.append("🔄 Loading more...")
            elif self.all_loaded:
                desc_parts.append(f"✅ {len(self.results)} total loaded")
            
            embed = discord.Embed(
                title=f"🖼️ {self.query[:40]} - Gallery",
                description=" • ".join(desc_parts),
                color=color
            )
        else:
            embed = discord.Embed(color=color)
        
        # Compact info for each image
        embed.add_field(
            name=f"{art.get('source', 'Unknown')}",
            value=f"⭐ {art.get('score', 0)} • {art.get('artist', 'Unknown')[:20]}",
            inline=True
        )
        
        embed.set_image(url=art.get("url"))
        
        return embed
    
    def _build_preview_embed(self, arts: list, color) -> discord.Embed:
        """Build embed for preview mode (thumbnails list)"""
        embed = discord.Embed(
            title=f"📋 {self.query[:40]} - Preview",
            description=f"Page {self.page + 1}/{self.max_pages} • {len(self.results)} total results",
            color=color
        )
        
        if self.is_nsfw:
            embed.description = f"🔞 NSFW • " + embed.description
        
        for i, art in enumerate(arts, 1):
            art_id = f"{art.get('source', '?').lower()}_{art.get('id', '?')}"
            embed.add_field(
                name=f"{i}. {art.get('source', 'Unknown')}",
                value=f"⭐ {art.get('score', 0)} • [{art.get('artist', 'Unknown')[:15]}]({art.get('page_url', '')})",
                inline=True
            )
        
        # Set first image as thumbnail
        if arts:
            embed.set_thumbnail(url=arts[0].get("preview_url") or arts[0].get("url"))
        
        embed.set_footer(text="Use Single Mode to view full images")
        
        return embed
    
    def update_buttons(self):
        """Update button states"""
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.max_pages - 1
        
        # Update page indicator
        self.page_indicator.label = f"{self.page + 1}/{self.max_pages}"
    
    # Navigation buttons (Row 2) - Simplified
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary, row=2)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        self.page = max(0, self.page - 1)
        self.update_buttons()
        embeds = self.build_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, row=2)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Page selector - opens modal to jump to specific page"""
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        # Show page selector modal
        modal = PageSelectorModal(self.max_pages)
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.selected_page is not None:
            self.page = modal.selected_page
            self.update_buttons()
            embeds = self.build_embeds()
            await interaction.edit_original_response(embeds=embeds, view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary, row=2)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        self.page = min(self.max_pages - 1, self.page + 1)
        
        # Fetch more if approaching end
        if self.page >= self.max_pages - 2 and len(self.results) < 500:
            await interaction.response.defer()
            await self.fetch_more()
            self.update_buttons()
            embeds = self.build_embeds()
            await interaction.edit_original_response(embeds=embeds, view=self)
        else:
            self.update_buttons()
            embeds = self.build_embeds()
            await interaction.response.edit_message(embeds=embeds, view=self)
    
    @discord.ui.button(label="🔀", style=discord.ButtonStyle.secondary, row=2)
    async def shuffle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Shuffle/randomize results order"""
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        import random
        random.shuffle(self.results)
        self.page = 0  # Reset to first page after shuffle
        self.update_buttons()
        embeds = self.build_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    @discord.ui.button(label="📥 More", style=discord.ButtonStyle.secondary, row=2)
    async def load_more_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        if self.loading_more:
            return await interaction.response.send_message("⏳ Already loading more results...", ephemeral=True)
        
        await interaction.response.defer()
        
        # Fetch next page from all selected sources simultaneously
        added = await self.fetch_more(aggressive=True)
        
        if added > 0:
            self.update_buttons()
            embeds = self.build_embeds()
            await interaction.edit_original_response(embeds=embeds, view=self)
        else:
            await interaction.followup.send("ℹ️ No more results available.", ephemeral=True)


class SaveArtModal(discord.ui.Modal, title="Save Art to Favorites"):
    folder = discord.ui.TextInput(
        label="Folder Name",
        placeholder="Enter folder name (default: 'default')",
        default="default",
        required=False,
        max_length=50
    )
    
    def __init__(self, art_id: str, art_data: dict):
        super().__init__()
        self.art_id = art_id
        self.art_data = art_data
    
    async def on_submit(self, interaction: discord.Interaction):
        folder_name = self.folder.value or "default"
        
        from utils.cogs.quest import Quest_Data
        quest_data = Quest_Data(interaction.client)
        
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        try:
            await quest_data.mongoConnect[quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {
                    "$push": {
                        f"members.{user_id}.art_favorites.{folder_name}": {
                            "id": self.art_id,
                            "source": self.art_data.get("source"),
                            "url": self.art_data.get("url"),
                            "preview_url": self.art_data.get("preview_url"),
                            "artist": self.art_data.get("artist"),
                            "tags": self.art_data.get("tags", [])[:10],
                            "saved_at": discord.utils.utcnow().timestamp()
                        }
                    }
                },
                upsert=True
            )
            
            embed = discord.Embed(
                title="✅ Art Saved!",
                description=f"Saved to folder: **{folder_name}**\nArt ID: `{self.art_id}`",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=self.art_data.get("preview_url") or self.art_data.get("url"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to save: {e}", ephemeral=True)


# Legacy ArtView for backwards compatibility
class ArtView(ArtGalleryView):
    """Legacy wrapper - redirects to new ArtGalleryView"""
    def __init__(self, results, author, query, is_nsfw, ctx):
        super().__init__(
            cog=None,
            author=author,
            query=query,
            is_nsfw=is_nsfw,
            ctx=ctx,
            initial_results=results
        )


class GoogleSearchTypeSelect(discord.ui.Select):
    """Select menu for switching between search types"""
    def __init__(self, current_type: str = "web"):
        options = [
            discord.SelectOption(label="Web Results", value="web", emoji="🔗", default=(current_type == "web")),
            discord.SelectOption(label="Images", value="images", emoji="🖼️", default=(current_type == "images")),
            discord.SelectOption(label="Videos", value="videos", emoji="🎬", default=(current_type == "videos")),
        ]
        super().__init__(placeholder="Select search type...", options=options, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        view: GoogleSearchView = self.view
        if interaction.user.id != view.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        view.search_type = self.values[0]
        view.page = 0
        
        # Update select default
        for opt in self.options:
            opt.default = (opt.value == view.search_type)
        
        # Fetch new results
        await interaction.response.defer()
        await view.fetch_results()
        embed = view.build_embed()
        view.update_buttons()
        await interaction.edit_original_response(embed=embed, view=view)


class GoogleSearchView(discord.ui.View):
    """Interactive view for Google search with tabs for web/images/videos"""
    
    def __init__(self, cog, author: discord.Member, query: str, search_type: str = "web", safe_search: bool = True):
        super().__init__(timeout=180)
        self.cog = cog
        self.author = author
        self.query = query
        self.search_type = search_type
        self.safe_search = safe_search  # SafeSearch enabled by default
        self.page = 0
        self.results = {"web": [], "images": [], "videos": []}
        self.per_page = {"web": 5, "images": 1, "videos": 1}
        self.image_fetch_offset = 0  # Track how many batches we've fetched for images
        self.loading_more = False  # Prevent duplicate fetches
        
        # Add select menu
        self.type_select = GoogleSearchTypeSelect(search_type)
        self.add_item(self.type_select)
    
    async def fetch_results(self):
        """Fetch results for current search type with SafeSearch"""
        if self.search_type == "web" and not self.results["web"]:
            self.results["web"] = await self.cog.google.search(self.query, num=10, safe=self.safe_search)
        elif self.search_type == "images" and not self.results["images"]:
            self.results["images"] = await self.cog.google.image_search(self.query, num=50, safe=self.safe_search)
            self.image_fetch_offset = 50
        elif self.search_type == "videos" and not self.results["videos"]:
            self.results["videos"] = await self.cog.google.video_search(self.query, num=10, safe=self.safe_search)
    
    async def fetch_more_images(self):
        """Fetch more images when user reaches near the end (infinite scroll)"""
        if self.loading_more:
            return
        self.loading_more = True
        try:
            new_images = await self.cog.google.image_search(
                self.query, num=50, start=self.image_fetch_offset, safe=self.safe_search
            )
            if new_images:
                # Filter out duplicates
                existing_urls = {img.get("link") for img in self.results["images"]}
                for img in new_images:
                    if img.get("link") not in existing_urls:
                        self.results["images"].append(img)
                        existing_urls.add(img.get("link"))
                self.image_fetch_offset += 50
        finally:
            self.loading_more = False
    
    def get_current_results(self):
        return self.results.get(self.search_type, [])
    
    def get_max_pages(self):
        results = self.get_current_results()
        per_page = self.per_page.get(self.search_type, 1)
        return max(1, (len(results) + per_page - 1) // per_page)
    
    def update_buttons(self):
        self.prev_btn.disabled = self.page <= 0
        # For images, never disable next button (infinite scroll)
        if self.search_type == "images":
            self.next_btn.disabled = False
        else:
            self.next_btn.disabled = self.page >= self.get_max_pages() - 1
        # Show/hide set image button based on search type
        self.set_image_btn.disabled = self.search_type != "images" or not self.get_current_results()
    
    def build_embed(self) -> discord.Embed:
        results = self.get_current_results()
        
        if not results:
            embed = discord.Embed(
                title=f"Google Search: {self.query[:50]}",
                description=f"No {self.search_type} results found for **{self.query}**\n\n"
                           f"Try a different search term or type.",
                color=discord.Color.orange()
            )
            return embed
        
        if self.search_type == "web":
            return self._build_web_embed(results)
        elif self.search_type == "images":
            return self._build_image_embed(results)
        elif self.search_type == "videos":
            return self._build_video_embed(results)
        
        return discord.Embed(title="Error", color=discord.Color.red())
    
    def _build_web_embed(self, results: list) -> discord.Embed:
        embed = discord.Embed(
            title=f"Web Results: {self.query[:40]}",
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        start = self.page * 5
        page_results = results[start:start + 5]
        
        for i, result in enumerate(page_results, start + 1):
            title = result.get("title", "No Title")[:55]
            link = result.get("link", "")
            snippet = result.get("snippet", "No description")[:150]
            
            # Clean up the snippet
            snippet = snippet.replace("\n", " ").strip()
            
            embed.add_field(
                name=f"{i}. {title}",
                value=f"{snippet}\n🔗 [Visit]({link})",
                inline=False
            )
        
        embed.set_footer(text=f"Page {self.page + 1}/{self.get_max_pages()} • {len(results)} results")
        return embed
    
    def _build_image_embed(self, results: list) -> discord.Embed:
        if self.page >= len(results):
            self.page = 0
        
        image = results[self.page]
        
        embed = discord.Embed(
            title=f"Images: {self.query[:40]}",
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        image_url = image.get("link", "")
        if image_url:
            embed.set_image(url=image_url)
        
        if image.get("source"):
            embed.add_field(name="Source", value=f"[View Source]({image['source']})", inline=True)
        
        embed.set_footer(text=f"Image {self.page + 1}/{len(results)}+ • Click 📌 Set Image to select • Infinite scroll enabled")
        return embed
    
    def _build_video_embed(self, results: list) -> discord.Embed:
        if self.page >= len(results):
            self.page = 0
        
        video = results[self.page]
        
        platform_emoji = "🎬"
        if video.get("platform") == "youtube":
            platform_emoji = "📺"
        elif video.get("platform") == "vimeo":
            platform_emoji = "🎥"
        
        embed = discord.Embed(
            title=f"{platform_emoji} Videos: {self.query[:40]}",
            url=video.get("url", ""),
            color=discord.Color.red() if video.get("platform") == "youtube" else primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="🎬 Watch Video",
            value=f"**[Click to Watch]({video.get('url', '')})**",
            inline=False
        )
        
        if video.get("platform") == "youtube":
            embed.add_field(name="Platform", value="YouTube", inline=True)
            embed.add_field(name="Video ID", value=f"`{video.get('video_id', 'N/A')}`", inline=True)
        
        # Set thumbnail
        if video.get("thumbnail"):
            embed.set_image(url=video["thumbnail"])
        
        embed.set_footer(text=f"Video {self.page + 1}/{len(results)} • Click link to watch")
        return embed
    
    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        self.page = max(0, self.page - 1)
        self.update_buttons()
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        # For images, implement infinite scroll
        if self.search_type == "images":
            self.page += 1
            # Fetch more images when approaching the end
            if self.page >= len(self.results["images"]) - 5:
                await interaction.response.defer()
                await self.fetch_more_images()
                self.update_buttons()
                embed = self.build_embed()
                await interaction.edit_original_response(embed=embed, view=self)
                return
        else:
            self.page = min(self.get_max_pages() - 1, self.page + 1)
        
        self.update_buttons()
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary, row=1)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        # Clear cached results for current type and refetch
        self.results[self.search_type] = []
        self.image_fetch_offset = 0
        await interaction.response.defer()
        await self.fetch_results()
        self.page = 0
        self.update_buttons()
        embed = self.build_embed()
        await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(label="📌 Set Image", style=discord.ButtonStyle.success, row=1)
    async def set_image_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        if self.search_type != "images" or not self.results["images"]:
            return await interaction.response.send_message("❌ No image to set!", ephemeral=True)
        
        # Get current image
        image = self.results["images"][self.page]
        image_url = image.get("link", "")
        
        if not image_url:
            return await interaction.response.send_message("❌ Could not get image URL!", ephemeral=True)
        
        # Send the image as a standalone message
        embed = discord.Embed(
            title=f"Selected Image",
            description=f"**Search:** {self.query}\n**Image {self.page + 1}** of {len(self.results['images'])}+",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url=image_url)
        embed.add_field(name="Direct Link", value=f"[Click to open]({image_url})", inline=False)
        embed.set_footer(text=f"Selected by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)


class Search(commands.Cog):
    """🔍 Search & Lookup - Search the web, translate, get weather, and more"""
    
    def __init__(self, bot):
        self.bot = bot
        self.google = GoogleSearch()
        self.youtube = YouTubeSearch()
        self.translator = TranslationAPI()
        self.weather = WeatherAPI()
        self.dictionary = DictionaryAPI()
        self.wikipedia = WikipediaAPI()
        self.art_gallery = ArtGalleryAPI()
        self.urban = UrbanDictionaryAPI()
        
        # Processing gateway - Track active command executions per user
        self.active_art_searches = {}  # {user_id: timestamp}
        self.processing_lock = set()  # Set of user_ids currently processing
    
    async def cog_load(self):
        """Initialize session on load"""
        import aiohttp
        self.session = aiohttp.ClientSession()
    
    def cog_unload(self):
        """Cleanup sessions on unload"""
        import asyncio
        for api in [self.google, self.youtube, self.translator, self.weather, 
                    self.dictionary, self.wikipedia, self.art_gallery, self.urban]:
            asyncio.create_task(api.close())
    
    def is_user_processing(self, user_id: int) -> bool:
        """Check if user has an active art search processing"""
        return user_id in self.processing_lock
    
    def start_processing(self, user_id: int) -> bool:
        """Mark user as processing. Returns False if already processing."""
        if user_id in self.processing_lock:
            return False
        self.processing_lock.add(user_id)
        self.active_art_searches[user_id] = datetime.now(timezone.utc).timestamp()
        return True
    
    def end_processing(self, user_id: int):
        """Mark user as done processing"""
        self.processing_lock.discard(user_id)
        self.active_art_searches.pop(user_id, None)

    # ═══════════════════════════════════════════════════════════════
    # GOOGLE SEARCH - Main unified command
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="google", aliases=["g", "search", "gsearch"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def google_search(self, ctx, *, query: str):
        """🔍 Search Google for web results, images, and videos
        
        Use the dropdown to switch between:
        • 🔗 Web Results - Links and descriptions
        • 🖼️ Images - Browse images in embeds
        • 🎬 Videos - Find YouTube and other videos
        
        SafeSearch is ON by default. Use in NSFW channels to disable.
        
        Example: .google cute cats
        """
        # SafeSearch: ON in normal channels, OFF in NSFW channels
        is_nsfw = isinstance(ctx.channel, discord.TextChannel) and ctx.channel.is_nsfw()
        safe_search = not is_nsfw
        
        async with ctx.typing():
            view = GoogleSearchView(self, ctx.author, query, "web", safe_search=safe_search)
            await view.fetch_results()
            view.update_buttons()
            embed = view.build_embed()
            
            # Add SafeSearch indicator
            if not safe_search:
                embed.set_footer(text=f"🔞 SafeSearch OFF (NSFW channel) • Page {view.page + 1}/{view.get_max_pages()}")
        
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # IMAGE SEARCH - Direct image search
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="image", aliases=["img", "images", "pic", "pics"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def image_search(self, ctx, *, query: str):
        """🖼️ Search Google Images directly
        
        Browse through images with navigation buttons.
        SafeSearch is ON by default. Use in NSFW channels to disable.
        
        Example: .image anya forger
        """
        # SafeSearch: ON in normal channels, OFF in NSFW channels
        is_nsfw = isinstance(ctx.channel, discord.TextChannel) and ctx.channel.is_nsfw()
        safe_search = not is_nsfw
        
        async with ctx.typing():
            view = GoogleSearchView(self, ctx.author, query, "images", safe_search=safe_search)
            await view.fetch_results()
            view.update_buttons()
            embed = view.build_embed()
            
            # Add SafeSearch indicator for NSFW
            if not safe_search:
                embed.set_footer(text=f"🔞 SafeSearch OFF (NSFW channel) • Image {view.page + 1}/{len(view.get_current_results())}")
        
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # YOUTUBE / VIDEO SEARCH
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="youtube", aliases=["yt", "video"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def youtube_search(self, ctx, *, query: str):
        """📺 Search YouTube videos"""
        async with ctx.typing():
            results = await self.youtube.search(query, max_results=5)
        
        if not results:
            embed = discord.Embed(
                title="YouTube Search",
                description=f"No videos found for **{query}**",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        view = SearchViews.VideoSearchView(results, ctx.author, f"YouTube: {query[:30]}")
        embed = view.build_embed()
        await ctx.reply(embed=embed, view=view, mention_author=False)

    async def _background_load_and_update(self, view: ArtGalleryView, message: discord.Message):
        """Background task to continue loading results and update the message"""
        try:
            await view.start_background_loading()
            
            # Update the message periodically as more results load
            last_count = len(view.results)
            update_count = 0
            
            while view.background_loading and update_count < 10:  # Max 10 updates
                await asyncio.sleep(3)  # Wait 3 seconds between updates
                
                # Only update if we got new results
                if len(view.results) > last_count:
                    last_count = len(view.results)
                    update_count += 1
                    
                    try:
                        # Update buttons and embeds
                        view.update_buttons()
                        embeds = view.build_embeds()
                        await message.edit(embeds=embeds, view=view)
                    except discord.HTTPException:
                        # Message might be deleted or we hit rate limit
                        break
                
                if view.all_loaded:
                    break
            
            # Final update when done
            if not view.all_loaded:
                view.all_loaded = True
            
            view.update_buttons()
            embeds = view.build_embeds()
            try:
                await message.edit(embeds=embeds, view=view)
            except discord.HTTPException:
                pass
                
        except Exception:
            # Silently fail - background loading is not critical
            pass
    
    # ═══════════════════════════════════════════════════════════════
    # ART SEARCH - Multiple sources with NSFW support and favorites
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="art", aliases=["artwork"], invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def art_search(self, ctx, *, query: str = None):
        """🎨 Search anime/manga art from 12+ sources with gallery view
        
        Use --random or -r flag to randomize results order.
        
        **Features:**
        • Multi-source search (Danbooru, Gelbooru, Safebooru, Konachan, Yande.re, Zerochan, Waifu.im, Nekos.best, and more)
        • Gallery mode with 4 images per page
        • Single image mode for detailed view
        • Preview mode for quick browsing
        • Source filter dropdown to pick which sources to use
        • Save favorites to folders
        
        Use in NSFW channels for adult content access (Rule34, e621, Realbooru)
        """
        # Check for --random or -r flag
        randomize = False
        if query:
            if query.endswith(" --random") or query.endswith(" -r"):
                randomize = True
                query = query.rsplit(" ", 1)[0].strip()
            elif " --random " in query:
                randomize = True
                query = query.replace(" --random ", " ").strip()
            elif " -r " in query:
                randomize = True
                query = query.replace(" -r ", " ").strip()
        
        if not query:
            # Check if in NSFW channel for help display
            is_nsfw_channel = isinstance(ctx.channel, discord.TextChannel) and ctx.channel.is_nsfw()
            
            # Build source lists by safety level
            guaranteed_safe = [m['name'] for k, m in ART_SOURCES.items() if not m['nsfw_only'] and not m.get('requires_nsfw_channel')]
            mixed_content = [m['name'] for k, m in ART_SOURCES.items() if not m['nsfw_only'] and m.get('requires_nsfw_channel')]
            nsfw_only = [m['name'] for k, m in ART_SOURCES.items() if m['nsfw_only']]
            
            embed = discord.Embed(
                title="Art Search - Multi-Source Gallery",
                description="Search anime and manga art with **content safety guarantees**",
                color=primary_color()
            )
            embed.add_field(
                name="Usage",
                value=f"`{ctx.prefix}art <search query>` - Search all sources\n"
                      f"`{ctx.prefix}art source <source> <query>` - Search specific source\n"
                      f"`{ctx.prefix}art save <art_id>` - Save to favorites\n"
                      f"`{ctx.prefix}art favorites` - View saved art",
                inline=False
            )
            embed.add_field(
                name="View Modes",
                value="**Gallery** - 4 images per page\n"
                      "**Single** - 1 large image with details\n"
                      "**Preview** - 6 thumbnails for quick browse",
                inline=True
            )
            embed.add_field(
                name="Features",
                value="- Multi-select source filter\n"
                      "- Content safety warnings\n"
                      "- Infinite scroll pagination\n"
                      "- Save to custom folders",
                inline=True
            )
            
            # Show guaranteed safe sources
            embed.add_field(
                name="✅ Guaranteed Safe (All Channels)",
                value=", ".join(guaranteed_safe) if guaranteed_safe else "None",
                inline=False
            )
            
            # Show mixed-content sources (only in NSFW channels)
            if is_nsfw_channel:
                embed.add_field(
                    name="⚠️ Mixed Content (NSFW Channel Only)",
                    value=", ".join(mixed_content) if mixed_content else "None",
                    inline=False
                )
                embed.add_field(
                    name="🔞 NSFW Only (NSFW Channel Only)",
                    value=", ".join(nsfw_only) if nsfw_only else "None",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚠️ Safety Notice",
                    value="Mixed-content and NSFW sources are **only available in NSFW channels** for your protection.",
                    inline=False
                )
            
            return await ctx.reply(embed=embed, mention_author=False)
        
        # ═══ CONTENT POLICY CHECK ═══
        if contains_prohibited_content(query):
            embed = discord.Embed(
                title="🚫 Search Blocked - Content Policy Violation",
                description=f"{ctx.author.mention} your search contains terms that violate Discord's Terms of Service and our content policy.\n\n"
                           "**Prohibited content includes:**\n"
                           "• Content sexualizing minors (CSAM)\n"
                           "• Gore, extreme violence, or death\n"
                           "• Bestiality or zoophilia\n"
                           "• Non-consensual content\n"
                           "• Other illegal content\n\n"
                           "This incident may be logged.",
                color=discord.Color.red()
            )
            try:
                embed.set_thumbnail(url=ctx.author.display_avatar.url)
            except Exception:
                pass
            embed.set_footer(text="⚠️ Repeated violations may result in being blocked from using this command.")
            return await ctx.reply(embed=embed, mention_author=False)
        
        # ═══ PROCESSING GATEWAY CHECK ═══
        user_id = ctx.author.id
        
        # Check if user already has an active art search processing
        if self.is_user_processing(user_id):
            # Calculate time since started
            start_time = self.active_art_searches.get(user_id, 0)
            elapsed = datetime.now(timezone.utc).timestamp() - start_time
            
            embed = discord.Embed(
                title="⏳ Search Already Processing",
                description=f"You already have an art search running!\n\n"
                           f"**Time elapsed:** {int(elapsed)}s\n"
                           f"**Please wait** for your current search to complete before starting a new one.\n\n"
                           f"This prevents API abuse and ensures fair usage for everyone.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="💡 Tip: Use the Load More button in your active search instead!")
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Mark user as processing
        if not self.start_processing(user_id):
            return await ctx.reply("⚠️ Failed to start processing. Please try again.", mention_author=False)
        
        try:
            # Check if in NSFW channel
            is_nsfw = False
            if isinstance(ctx.channel, discord.TextChannel):
                is_nsfw = ctx.channel.is_nsfw()
            
            # Send processing indicator
            processing_msg = await ctx.reply("🔄 **Processing your art search...**\nFetching from multiple sources simultaneously...", mention_author=False)
            
            async with ctx.typing():
                if not hasattr(self, 'art_aggregator'):
                    self.art_aggregator = ArtAggregator(self.session)
                
                # Fetch initial results with aggressive loading (3 pages per source)
                results = await self.art_aggregator.search_all(
                    query, 
                    limit=500, 
                    nsfw=is_nsfw,
                    aggressive_load=True,
                    max_pages_per_source=3
                )
                
                # Filter out prohibited content from results
                results = filter_prohibited_results(results)
                
                # Randomize order if --random flag was used
                if randomize:
                    import random
                    random.shuffle(results)
            
            # Create the new gallery view
            view = ArtGalleryView(
                cog=self,
                author=ctx.author,
                query=query,
                is_nsfw=is_nsfw,
                ctx=ctx,
                initial_results=results
            )
            view.update_buttons()
            embeds = view.build_embeds()
            
            # Delete processing message and send results
            try:
                await processing_msg.delete()
            except:
                pass
            
            message = await ctx.reply(embeds=embeds, view=view, mention_author=False)
            
            # Start background loading task to continue fetching more results
            import asyncio
            asyncio.create_task(self._background_load_and_update(view, message))
            
        finally:
            # Always release the processing lock when done
            self.end_processing(user_id)
    
    @art_search.command(name="source", aliases=["src"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def art_source(self, ctx, source: str, *, query: str):
        """Search a specific art source
        
        Available sources: danbooru, gelbooru, safebooru, konachan, yandere, 
        zerochan, anime_pictures, waifu_im, nekos_best, rule34, e621, realbooru
        """
        # ═══ CONTENT POLICY CHECK ═══
        if contains_prohibited_content(query):
            embed = discord.Embed(
                title="🚫 Search Blocked - Content Policy Violation",
                description=f"{ctx.author.mention} your search contains terms that violate Discord's Terms of Service and our content policy.\n\n"
                           "**Prohibited content includes:**\n"
                           "• Content sexualizing minors (CSAM)\n"
                           "• Gore, extreme violence, or death\n"
                           "• Bestiality or zoophilia\n"
                           "• Non-consensual content\n"
                           "• Other illegal content\n\n"
                           "This incident may be logged.",
                color=discord.Color.red()
            )
            try:
                embed.set_thumbnail(url=ctx.author.display_avatar.url)
            except Exception:
                pass
            embed.set_footer(text="⚠️ Repeated violations may result in being blocked from using this command.")
            return await ctx.reply(embed=embed, mention_author=False)
        
        # ═══ PROCESSING GATEWAY CHECK ═══
        user_id = ctx.author.id
        
        if self.is_user_processing(user_id):
            start_time = self.active_art_searches.get(user_id, 0)
            elapsed = datetime.now(timezone.utc).timestamp() - start_time
            
            embed = discord.Embed(
                title="⏳ Search Already Processing",
                description=f"You already have an art search running!\n\n"
                           f"**Time elapsed:** {int(elapsed)}s\n"
                           f"Please wait for your current search to complete.",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        if not self.start_processing(user_id):
            return await ctx.reply("⚠️ Failed to start processing. Please try again.", mention_author=False)
        
        try:
            is_nsfw = False
            if isinstance(ctx.channel, discord.TextChannel):
                is_nsfw = ctx.channel.is_nsfw()
            
            # Validate source
            source_key = source.lower().replace("-", "_").replace(" ", "_")
            if source_key not in ART_SOURCES:
                available = ", ".join([f"`{k}`" for k in ART_SOURCES.keys()])
                embed = discord.Embed(
                    title="❌ Invalid Source",
                    description=f"**{source}** is not a valid source.\n\n**Available sources:**\n{available}",
                    color=discord.Color.red()
                )
                return await ctx.reply(embed=embed, mention_author=False)
            
            # Check NSFW restriction
            if ART_SOURCES[source_key]["nsfw_only"] and not is_nsfw:
                embed = discord.Embed(
                    title="🔞 NSFW Source",
                    description=f"**{ART_SOURCES[source_key]['name']}** is only available in NSFW channels.",
                    color=discord.Color.red()
                )
                return await ctx.reply(embed=embed, mention_author=False)
            
            if not hasattr(self, 'art_aggregator'):
                self.art_aggregator = ArtAggregator(self.session)
            
            processing_msg = await ctx.reply(f"🔄 **Searching {ART_SOURCES[source_key]['name']}...**", mention_author=False)
            
            async with ctx.typing():
                results = await self.art_aggregator.search_source(source_key, query, limit=100, nsfw=is_nsfw)
                
                # Filter out prohibited content from results
                results = filter_prohibited_results(results)
            
            # Create gallery view with only this source selected
            view = ArtGalleryView(
                cog=self,
                author=ctx.author,
                query=f"{ART_SOURCES[source_key]['name']}: {query}",
                is_nsfw=is_nsfw,
                ctx=ctx,
                initial_results=results,
                selected_sources={source_key}
            )
            view.update_buttons()
            embeds = view.build_embeds()
            
            try:
                await processing_msg.delete()
            except:
                pass
            
            await ctx.reply(embeds=embeds, view=view, mention_author=False)
            
        finally:
            self.end_processing(user_id)
    
    @art_search.command(name="save", aliases=["favorite", "fav"])
    async def art_save(self, ctx, art_id: str = None, folder: str = "default"):
        """Save art to your favorites"""
        if not art_id:
            return await ctx.reply("❌ Please provide an art ID to save.", mention_author=False)
        
        # Save to MongoDB
        from utils.cogs.quest import Quest_Data
        if not hasattr(self, 'quest_data'):
            self.quest_data = Quest_Data(self.bot)
        
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        # Store in user's art favorites
        try:
            await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {
                    "$push": {
                        f"members.{user_id}.art_favorites.{folder}": {
                            "id": art_id,
                            "saved_at": discord.utils.utcnow().timestamp()
                        }
                    }
                },
                upsert=True
            )
            
            embed = discord.Embed(
                title="Art Saved",
                description=f"Saved art `{art_id}` to folder **{folder}**",
                color=discord.Color.green()
            )
            await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ Failed to save art: {e}", mention_author=False)
    
    @art_search.command(name="folder")
    async def art_folder(self, ctx, action: str = None, *, name: str = None):
        """Manage art folders
        
        Actions: create, delete, list, rename
        """
        if not action:
            embed = discord.Embed(
                title="Art Folders",
                description="Organize your favorite art into folders!",
                color=primary_color()
            )
            embed.add_field(
                name="Commands",
                value=f"`{ctx.prefix}art folder create <name>`\n"
                      f"`{ctx.prefix}art folder delete <name>`\n"
                      f"`{ctx.prefix}art folder list`\n"
                      f"`{ctx.prefix}art folder rename <old> <new>`",
                inline=False
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        from utils.cogs.quest import Quest_Data
        if not hasattr(self, 'quest_data'):
            self.quest_data = Quest_Data(self.bot)
        
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        if action.lower() == "create":
            if not name:
                return await ctx.reply("❌ Please provide a folder name.", mention_author=False)
            
            try:
                await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].update_one(
                    {"guild_id": guild_id},
                    {"$set": {f"members.{user_id}.art_favorites.{name}": []}},
                    upsert=True
                )
                
                embed = discord.Embed(
                    title="Folder Created",
                    description=f"Created folder **{name}**",
                    color=discord.Color.green()
                )
                await ctx.reply(embed=embed, mention_author=False)
            except Exception as e:
                await ctx.reply(f"❌ Failed to create folder: {e}", mention_author=False)
        
        elif action.lower() == "list":
            try:
                doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                    {"guild_id": guild_id},
                    {f"members.{user_id}.art_favorites": 1}
                )
                
                folders = (((doc or {}).get("members") or {}).get(user_id) or {}).get("art_favorites", {})
                
                if not folders:
                    return await ctx.reply("📁 You don't have any folders yet.", mention_author=False)
                
                embed = discord.Embed(
                    title="Your Art Folders",
                    color=primary_color()
                )
                
                for folder_name, items in folders.items():
                    count = len(items) if isinstance(items, list) else 0
                    embed.add_field(
                        name=folder_name,
                        value=f"🖼️ {count} items",
                        inline=True
                    )
                
                await ctx.reply(embed=embed, mention_author=False)
            except Exception as e:
                await ctx.reply(f"❌ Failed to list folders: {e}", mention_author=False)
    
    @art_search.command(name="favorites", aliases=["favs", "saved"])
    async def art_favorites(self, ctx, folder: str = None):
        """View your saved favorite art"""
        from utils.cogs.quest import Quest_Data
        if not hasattr(self, 'quest_data'):
            self.quest_data = Quest_Data(self.bot)
        
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.art_favorites": 1}
            )
            
            favorites = (((doc or {}).get("members") or {}).get(user_id) or {}).get("art_favorites", {})
            
            if not favorites:
                embed = discord.Embed(
                    title="Favorites",
                    description="You haven't saved any art yet!\n"
                               f"Use `{ctx.prefix}art save <id>` to save art.",
                    color=primary_color()
                )
                return await ctx.reply(embed=embed, mention_author=False)
            
            if folder:
                items = favorites.get(folder, [])
                if not items:
                    return await ctx.reply(f"📁 Folder **{folder}** is empty.", mention_author=False)
                
                embed = discord.Embed(
                    title=f"{folder}",
                    description=f"**{len(items)}** saved items",
                    color=primary_color()
                )
                
                for i, item in enumerate(items[:10]):
                    art_id = item.get("id") if isinstance(item, dict) else item
                    embed.add_field(
                        name=f"#{i+1}",
                        value=f"`{art_id}`",
                        inline=True
                    )
                
                await ctx.reply(embed=embed, mention_author=False)
            else:
                embed = discord.Embed(
                    title="Your Favorites",
                    description=f"Use `{ctx.prefix}art favorites <folder>` to view a specific folder",
                    color=primary_color()
                )
                
                total = 0
                for folder_name, items in favorites.items():
                    count = len(items) if isinstance(items, list) else 0
                    total += count
                    embed.add_field(
                        name=f"📁 {folder_name}",
                        value=f"{count} items",
                        inline=True
                    )
                
                embed.set_footer(text=f"Total: {total} saved items")
                await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            await ctx.reply(f"❌ Error loading favorites: {e}", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # TRANSLATE
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="translate", aliases=["tr", "trans"], invoke_without_command=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def translate(self, ctx, target_lang: str = "en", *, text: str = None):
        """🌐 Translate text to another language
        
        Usage: translate <language_code> <text>
        Example: translate es Hello, how are you?
        
        Language codes: en, es, fr, de, it, pt, ru, ja, ko, zh, ar, hi
        """
        if text is None:
            # Show help
            embed = discord.Embed(
                title="🌐 Translation",
                description="Translate text between languages",
                color=primary_color()
            )
            embed.add_field(
                name="Usage",
                value=f"`{ctx.prefix}translate <lang> <text>`\n"
                      f"`{ctx.prefix}translate es Hello world`",
                inline=False
            )
            embed.add_field(
                name="Language Codes",
                value="**en** - English | **es** - Spanish | **fr** - French\n"
                      "**de** - German | **it** - Italian | **pt** - Portuguese\n"
                      "**ru** - Russian | **ja** - Japanese | **ko** - Korean\n"
                      "**zh** - Chinese | **ar** - Arabic | **hi** - Hindi",
                inline=False
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        async with ctx.typing():
            result = await self.translator.translate(text, target=target_lang)
        
        if not result.get("success"):
            embed = discord.Embed(
                title="Translation Failed",
                description="Could not translate the text. Please try again.",
                color=discord.Color.red()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        lang_name = TranslationAPI.LANGUAGES.get(target_lang, target_lang.upper())
        
        embed = discord.Embed(
            title=f"🌐 Translation → {lang_name}",
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Original", value=f"```{text[:500]}```", inline=False)
        embed.add_field(name="Translated", value=f"```{result['translated'][:500]}```", inline=False)
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        await ctx.reply(embed=embed, mention_author=False)

    @translate.command(name="detect")
    async def translate_detect(self, ctx, *, text: str):
        """Detect the language of text"""
        async with ctx.typing():
            lang = await self.translator.detect_language(text)
        
        lang_name = TranslationAPI.LANGUAGES.get(lang, lang.upper())
        
        embed = discord.Embed(
            title="Language Detection",
            description=f"Detected language: **{lang_name}** (`{lang}`)",
            color=primary_color()
        )
        embed.add_field(name="Text", value=f"```{text[:200]}```", inline=False)
        
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # WEATHER
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="weather", aliases=["w", "forecast"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def weather_cmd(self, ctx, *, location: str):
        """🌤️ Get weather for a location"""
        async with ctx.typing():
            data = await self.weather.get_weather(location)
        
        if not data:
            embed = discord.Embed(
                title="Weather",
                description=f"Could not find weather for **{location}**",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        emoji = WeatherAPI.get_weather_emoji(data.get("weather_code"))
        temp = data.get("temperature")
        temp_f = round(temp * 9/5 + 32, 1) if temp else "N/A"
        
        embed = discord.Embed(
            title=f"{emoji} Weather in {data.get('location')}",
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="🌡️ Temperature",
            value=f"**{temp}°C** / **{temp_f}°F**",
            inline=True
        )
        embed.add_field(
            name="📊 High / Low",
            value=f"**{data.get('high')}°C** / **{data.get('low')}°C**",
            inline=True
        )
        embed.add_field(
            name="💨 Wind",
            value=f"**{data.get('wind_speed')}** km/h",
            inline=True
        )
        embed.add_field(
            name="💧 Humidity",
            value=f"**{data.get('humidity')}%**",
            inline=True
        )
        
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # DICTIONARY
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="define", aliases=["dict", "dictionary", "meaning"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def define(self, ctx, *, word: str):
        """📖 Look up a word in the dictionary"""
        async with ctx.typing():
            data = await self.dictionary.define(word.lower())
        
        if not data:
            embed = discord.Embed(
                title="📖 Dictionary",
                description=f"No definition found for **{word}**",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        embed = discord.Embed(
            title=f"📖 {data.get('word', word).title()}",
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        if data.get("phonetic"):
            embed.description = f"*{data.get('phonetic')}*"
        
        for i, defn in enumerate(data.get("definitions", [])[:4], 1):
            part = defn.get("part_of_speech", "").title()
            definition = defn.get("definition", "")[:200]
            example = defn.get("example", "")
            
            value = f"{definition}"
            if example:
                value += f"\n*Example: {example[:100]}*"
            
            embed.add_field(
                name=f"{i}. {part}" if part else f"{i}.",
                value=value,
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # URBAN DICTIONARY
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="urban", aliases=["ud", "urbandictionary"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def urban_define(self, ctx, *, term: str):
        """📕 Look up a term on Urban Dictionary"""
        async with ctx.typing():
            data = await self.urban.define(term)
        
        if not data:
            embed = discord.Embed(
                title="📕 Urban Dictionary",
                description=f"No definition found for **{term}**",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        embed = discord.Embed(
            title=f"📕 {data.get('word', term)}",
            url=data.get("url", ""),
            color=discord.Color.from_rgb(239, 255, 0),
            timestamp=datetime.now(timezone.utc)
        )
        
        definition = data.get("definition", "")[:1000]
        example = data.get("example", "")[:500]
        
        embed.add_field(name="Definition", value=definition or "No definition", inline=False)
        
        if example:
            embed.add_field(name="Example", value=f"*{example}*", inline=False)
        
        embed.add_field(
            name="Votes",
            value=f"👍 {data.get('thumbs_up', 0)} | 👎 {data.get('thumbs_down', 0)}",
            inline=True
        )
        embed.add_field(name="Author", value=data.get("author", "Anonymous"), inline=True)
        
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # WIKIPEDIA
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="wiki", aliases=["wikipedia", "wp"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def wiki_search(self, ctx, *, query: str):
        """📚 Search Wikipedia"""
        async with ctx.typing():
            data = await self.wikipedia.search(query)
        
        if not data:
            embed = discord.Embed(
                title="📚 Wikipedia",
                description=f"No article found for **{query}**",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        embed = discord.Embed(
            title=f"📚 {data.get('title', query)}",
            url=data.get("url", ""),
            description=data.get("extract", "")[:1000],
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        if data.get("thumbnail"):
            embed.set_thumbnail(url=data.get("thumbnail"))
        
        if data.get("url"):
            embed.add_field(name="Read More", value=f"[Full Article]({data.get('url')})", inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author} • Wikipedia")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # COLOR TOOLKIT - Designer's Best Friend
    # ═══════════════════════════════════════════════════════════════
    
    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Convert hex to RGB tuple."""
        hex_color = hex_color.strip("#").upper()
        if len(hex_color) == 3:
            hex_color = "".join([c*2 for c in hex_color])
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r, g, b)
    
    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """Convert RGB to hex string."""
        return f"{r:02X}{g:02X}{b:02X}"
    
    def _rgb_to_hsl(self, r: int, g: int, b: int) -> tuple:
        """Convert RGB to HSL."""
        r, g, b = r/255, g/255, b/255
        max_c, min_c = max(r, g, b), min(r, g, b)
        l = (max_c + min_c) / 2
        
        if max_c == min_c:
            h = s = 0
        else:
            d = max_c - min_c
            s = d / (2 - max_c - min_c) if l > 0.5 else d / (max_c + min_c)
            if max_c == r:
                h = ((g - b) / d + (6 if g < b else 0)) / 6
            elif max_c == g:
                h = ((b - r) / d + 2) / 6
            else:
                h = ((r - g) / d + 4) / 6
        
        return (int(h * 360), int(s * 100), int(l * 100))
    
    def _rgb_to_cmyk(self, r: int, g: int, b: int) -> tuple:
        """Convert RGB to CMYK."""
        if r == 0 and g == 0 and b == 0:
            return (0, 0, 0, 100)
        r, g, b = r/255, g/255, b/255
        k = 1 - max(r, g, b)
        c = (1 - r - k) / (1 - k) if k != 1 else 0
        m = (1 - g - k) / (1 - k) if k != 1 else 0
        y = (1 - b - k) / (1 - k) if k != 1 else 0
        return (int(c*100), int(m*100), int(y*100), int(k*100))
    
    def _get_complementary(self, r: int, g: int, b: int) -> tuple:
        """Get complementary color."""
        return (255 - r, 255 - g, 255 - b)
    
    def _get_analogous(self, h: int, s: int, l: int) -> list:
        """Get analogous colors (±30°)."""
        return [((h - 30) % 360, s, l), ((h + 30) % 360, s, l)]
    
    def _get_triadic(self, h: int, s: int, l: int) -> list:
        """Get triadic colors (120° apart)."""
        return [((h + 120) % 360, s, l), ((h + 240) % 360, s, l)]
    
    def _hsl_to_rgb(self, h: int, s: int, l: int) -> tuple:
        """Convert HSL to RGB."""
        h, s, l = h/360, s/100, l/100
        if s == 0:
            r = g = b = l
        else:
            def hue_to_rgb(p, q, t):
                if t < 0: t += 1
                if t > 1: t -= 1
                if t < 1/6: return p + (q - p) * 6 * t
                if t < 1/2: return q
                if t < 2/3: return p + (q - p) * (2/3 - t) * 6
                return p
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        return (int(r * 255), int(g * 255), int(b * 255))
    
    def _get_contrast_ratio(self, rgb1: tuple, rgb2: tuple) -> float:
        """Calculate WCAG contrast ratio."""
        def luminance(r, g, b):
            rs, gs, bs = r/255, g/255, b/255
            r = rs/12.92 if rs <= 0.03928 else ((rs + 0.055)/1.055)**2.4
            g = gs/12.92 if gs <= 0.03928 else ((gs + 0.055)/1.055)**2.4
            b = bs/12.92 if bs <= 0.03928 else ((bs + 0.055)/1.055)**2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b
        
        l1 = luminance(*rgb1)
        l2 = luminance(*rgb2)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)
    
    def _get_color_name(self, r: int, g: int, b: int) -> str:
        """Get approximate color name."""
        colors = {
            "Red": (255, 0, 0), "Green": (0, 128, 0), "Blue": (0, 0, 255),
            "Yellow": (255, 255, 0), "Cyan": (0, 255, 255), "Magenta": (255, 0, 255),
            "Orange": (255, 165, 0), "Purple": (128, 0, 128), "Pink": (255, 192, 203),
            "Brown": (139, 69, 19), "Gray": (128, 128, 128), "White": (255, 255, 255),
            "Black": (0, 0, 0), "Navy": (0, 0, 128), "Teal": (0, 128, 128),
            "Lime": (0, 255, 0), "Coral": (255, 127, 80), "Salmon": (250, 128, 114),
            "Gold": (255, 215, 0), "Silver": (192, 192, 192), "Maroon": (128, 0, 0),
            "Olive": (128, 128, 0), "Aqua": (0, 255, 255), "Indigo": (75, 0, 130),
        }
        
        min_dist = float('inf')
        closest = "Unknown"
        for name, (cr, cg, cb) in colors.items():
            dist = ((r - cr)**2 + (g - cg)**2 + (b - cb)**2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                closest = name
        return closest
    
    @commands.group(name="color", aliases=["colour", "clr"], invoke_without_command=True)
    async def color_group(self, ctx, *, color_input: str = None):
        """🎨 Designer's color toolkit - analyze colors, extract from images, check contrast & more!"""
        if color_input is None:
            embed = discord.Embed(
                title="Color Toolkit",
                description="Your designer's best friend for all things color!",
                color=discord.Color.from_rgb(255, 105, 180)
            )
            
            embed.add_field(
                name="🔍 Analyze Colors",
                value=f"`{ctx.prefix}color #FF5733` - Full color breakdown\n"
                      f"`{ctx.prefix}color rgb 255 87 51` - From RGB values\n"
                      f"`{ctx.prefix}color random` - Random color inspiration",
                inline=False
            )
            
            embed.add_field(
                name="Get Colors From",
                value=f"`{ctx.prefix}color role @role` - Role's color\n"
                      f"`{ctx.prefix}color user @user` - User's top role color\n"
                      f"`{ctx.prefix}color image` - Extract from attached image",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Designer Tools",
                value=f"`{ctx.prefix}color palette #hex` - Harmony palette\n"
                      f"`{ctx.prefix}color contrast #hex1 #hex2` - Check accessibility\n"
                      f"`{ctx.prefix}color preview #hex` - See color on UI elements",
                inline=False
            )
            
            embed.set_footer(text="💡 Tip: Works with hex (#FF5733), RGB, or color names!")
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Try to parse as hex color
        color_input = color_input.strip()
        
        # Check if it's RGB format
        import re
        rgb_match = re.match(r'rgb\s*\(?\s*(\d+)\s*,?\s*(\d+)\s*,?\s*(\d+)\s*\)?', color_input, re.I)
        if rgb_match:
            r, g, b = int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))
            if all(0 <= x <= 255 for x in (r, g, b)):
                return await self._send_color_info(ctx, r, g, b)
            return await ctx.reply("❌ RGB values must be 0-255!", mention_author=False)
        
        # Try hex
        hex_color = color_input.strip("#").upper()
        if len(hex_color) == 3:
            hex_color = "".join([c*2 for c in hex_color])
        
        if len(hex_color) == 6 and all(c in "0123456789ABCDEF" for c in hex_color):
            r, g, b = self._hex_to_rgb(hex_color)
            return await self._send_color_info(ctx, r, g, b)
        
        # Try color name
        color_names = {
            "red": (255, 0, 0), "green": (0, 128, 0), "blue": (0, 0, 255),
            "yellow": (255, 255, 0), "cyan": (0, 255, 255), "magenta": (255, 0, 255),
            "orange": (255, 165, 0), "purple": (128, 0, 128), "pink": (255, 192, 203),
            "white": (255, 255, 255), "black": (0, 0, 0), "gray": (128, 128, 128),
            "grey": (128, 128, 128), "navy": (0, 0, 128), "teal": (0, 128, 128),
            "coral": (255, 127, 80), "gold": (255, 215, 0), "silver": (192, 192, 192),
            "blurple": (88, 101, 242), "discord": (88, 101, 242),
        }
        
        if color_input.lower() in color_names:
            r, g, b = color_names[color_input.lower()]
            return await self._send_color_info(ctx, r, g, b)
        
        await ctx.reply(f"❌ Could not parse color: `{color_input}`\n"
                       f"Try: `#FF5733`, `rgb(255, 87, 51)`, or a color name!", mention_author=False)
    
    async def _send_color_info(self, ctx, r: int, g: int, b: int):
        """Send comprehensive color information."""
        hex_color = self._rgb_to_hex(r, g, b)
        hsl = self._rgb_to_hsl(r, g, b)
        cmyk = self._rgb_to_cmyk(r, g, b)
        color_name = self._get_color_name(r, g, b)
        
        # Contrast with white and black
        white_contrast = self._get_contrast_ratio((r, g, b), (255, 255, 255))
        black_contrast = self._get_contrast_ratio((r, g, b), (0, 0, 0))
        best_text = "White" if white_contrast > black_contrast else "Black"
        
        embed = discord.Embed(
            title=f"{color_name}",
            color=discord.Color.from_rgb(r, g, b)
        )
        
        # Color codes section
        embed.add_field(
            name="📋 Color Codes",
            value=f"**Hex:** `#{hex_color}`\n"
                  f"**RGB:** `rgb({r}, {g}, {b})`\n"
                  f"**HSL:** `hsl({hsl[0]}, {hsl[1]}%, {hsl[2]}%)`\n"
                  f"**CMYK:** `{cmyk[0]}%, {cmyk[1]}%, {cmyk[2]}%, {cmyk[3]}%`\n"
                  f"**Decimal:** `{int(hex_color, 16)}`",
            inline=False
        )
        
        # Accessibility
        wcag_aa = "✅" if max(white_contrast, black_contrast) >= 4.5 else "⚠️"
        wcag_aaa = "✅" if max(white_contrast, black_contrast) >= 7 else "❌"
        
        embed.add_field(
            name="♿ Accessibility",
            value=f"Best text: **{best_text}**\n"
                  f"Contrast: `{max(white_contrast, black_contrast):.2f}:1`\n"
                  f"WCAG AA: {wcag_aa} | AAA: {wcag_aaa}",
            inline=True
        )
        
        # Quick palette
        comp = self._get_complementary(r, g, b)
        embed.add_field(
            name="🎯 Quick Palette",
            value=f"Complementary: `#{self._rgb_to_hex(*comp)}`\n"
                  f"Use `{ctx.prefix}color palette #{hex_color}`\nfor full harmony palette",
            inline=True
        )
        
        # Color preview image
        embed.set_thumbnail(url=f"https://singlecolorimage.com/get/{hex_color}/150x150")
        embed.set_image(url=f"https://via.placeholder.com/400x80/{hex_color}/{hex_color}?text=+")
        
        embed.set_footer(text=f"💡 {ctx.prefix}color palette #{hex_color} for harmonies")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @color_group.command(name="random", aliases=["rand", "rng"])
    async def color_random(self, ctx):
        """🎲 Generate a random color for inspiration."""
        import random
        r, g, b = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
        await self._send_color_info(ctx, r, g, b)
    
    @color_group.command(name="rgb")
    async def color_from_rgb(self, ctx, r: int, g: int, b: int):
        """📊 Get color info from RGB values."""
        if not all(0 <= x <= 255 for x in (r, g, b)):
            return await ctx.reply("❌ RGB values must be 0-255!", mention_author=False)
        await self._send_color_info(ctx, r, g, b)
    
    @color_group.command(name="role")
    async def color_from_role(self, ctx, *, role: discord.Role):
        """Get color info from a role."""
        r, g, b = role.color.r, role.color.g, role.color.b
        
        if r == 0 and g == 0 and b == 0:
            return await ctx.reply(f"❌ {role.mention} has no color set (default)", mention_author=False)
        
        embed = discord.Embed(
            title=f"{role.name}'s Color",
            color=role.color
        )
        
        hex_color = self._rgb_to_hex(r, g, b)
        embed.add_field(name="Hex", value=f"`#{hex_color}`", inline=True)
        embed.add_field(name="RGB", value=f"`rgb({r}, {g}, {b})`", inline=True)
        embed.add_field(name="Members", value=f"`{len(role.members)}`", inline=True)
        embed.set_thumbnail(url=f"https://singlecolorimage.com/get/{hex_color}/100x100")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @color_group.command(name="user", aliases=["member"])
    async def color_from_user(self, ctx, *, member: discord.Member = None):
        """👤 Get color palette from user's avatar + their role color."""
        member = member or ctx.author
        
        async with ctx.typing():
            # Get avatar palette
            avatar_url = member.display_avatar.with_size(64).url
            avatar_colors = await self._extract_avatar_palette(avatar_url)
            
            # Get top colored role
            colored_role = None
            for role in reversed(member.roles):
                if role.color.value != 0:
                    colored_role = role
                    break
            
            # Build embed
            embed = discord.Embed(
                title=f"{member.display_name}'s Colors",
                color=colored_role.color if colored_role else discord.Color.blurple()
            )
            
            # Avatar palette section
            if avatar_colors:
                palette_str = ""
                for i, (r, g, b) in enumerate(avatar_colors[:5], 1):
                    hex_c = self._rgb_to_hex(r, g, b)
                    color_name = self._get_color_name(r, g, b)
                    palette_str += f"`#{hex_c}` {color_name}\n"
                
                embed.add_field(
                    name="🖼️ Avatar Palette",
                    value=palette_str or "Could not extract colors",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🖼️ Avatar Palette",
                    value="Could not extract colors from avatar",
                    inline=False
                )
            
            # Role color section
            if colored_role:
                r, g, b = colored_role.color.r, colored_role.color.g, colored_role.color.b
                hex_color = self._rgb_to_hex(r, g, b)
                color_name = self._get_color_name(r, g, b)
                
                embed.add_field(
                    name="Role Color",
                    value=f"{colored_role.mention}\n"
                          f"`#{hex_color}` {color_name}\n"
                          f"`rgb({r}, {g}, {b})`",
                    inline=True
                )
            else:
                embed.add_field(
                    name="Role Color",
                    value="No colored role",
                    inline=True
                )
            
            # Set avatar as thumbnail
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Generate palette table image from avatar colors
            file = None
            if avatar_colors and len(avatar_colors) >= 1:
                image_bytes = self._generate_palette_image(avatar_colors[:5])
                file = discord.File(BytesIO(image_bytes), filename="avatar_palette.png")
                embed.set_image(url="attachment://avatar_palette.png")
            
            embed.set_footer(text=f"💡 Use {ctx.prefix}color #{self._rgb_to_hex(*avatar_colors[0]) if avatar_colors else 'hex'} for detailed info")
        
        if file:
            await ctx.reply(embed=embed, file=file, mention_author=False)
        else:
            await ctx.reply(embed=embed, mention_author=False)
    
    async def _extract_avatar_palette(self, url: str) -> list:
        """Extract dominant colors from an avatar image."""
        try:
            import aiohttp
            from collections import Counter
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return []
                    image_data = await resp.read()
            
            # Use PIL to extract colors
            from io import BytesIO
            from PIL import Image
            
            img = Image.open(BytesIO(image_data))
            img = img.convert("RGB")
            img = img.resize((50, 50))  # Resize for faster processing
            
            pixels = list(img.getdata())
            
            # Quantize colors to reduce noise
            def quantize(color, factor=32):
                return tuple((c // factor) * factor for c in color)
            
            quantized = [quantize(p) for p in pixels]
            
            # Count and get most common
            counter = Counter(quantized)
            most_common = counter.most_common(10)
            
            # Filter out very dark and very light colors, and dedupe similar colors
            filtered = []
            for color, count in most_common:
                r, g, b = color
                # Skip very dark or very light
                brightness = (r + g + b) / 3
                if brightness < 20 or brightness > 240:
                    continue
                
                # Skip if too similar to existing
                is_similar = False
                for existing in filtered:
                    er, eg, eb = existing
                    if abs(r - er) < 40 and abs(g - eg) < 40 and abs(b - eb) < 40:
                        is_similar = True
                        break
                
                if not is_similar:
                    filtered.append(color)
                
                if len(filtered) >= 5:
                    break
            
            return filtered
        except Exception as e:
            print(f"Avatar palette extraction error: {e}")
            return []
    
    def _generate_palette_image(self, colors: list) -> bytes:
        """Generate a color palette image with hex and RGB values."""
        from PIL import Image, ImageDraw, ImageFont
        from io import BytesIO
        
        # Image dimensions
        row_height = 50
        color_width = 120
        hex_width = 140
        rgb_width = 160
        total_width = color_width + hex_width + rgb_width
        total_height = row_height * len(colors) + 60  # Extra for header
        
        # Create image with white background
        img = Image.new('RGB', (total_width, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # Try to load a font, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", 18)
            header_font = ImageFont.truetype("arial.ttf", 22)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
                header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
            except:
                font = ImageFont.load_default()
                header_font = font
        
        # Draw header
        header_y = 15
        draw.text((color_width // 2 - 20, header_y), "Color", fill=(70, 70, 70), font=header_font)
        draw.text((color_width + hex_width // 2 - 20, header_y), "Hex", fill=(70, 70, 70), font=header_font)
        draw.text((color_width + hex_width + rgb_width // 2 - 20, header_y), "RGB", fill=(70, 70, 70), font=header_font)
        
        # Draw separator line under header
        draw.line([(10, 50), (total_width - 10, 50)], fill=(200, 200, 200), width=2)
        
        # Draw each color row
        for i, (r, g, b) in enumerate(colors):
            y_start = 60 + (i * row_height)
            
            # Draw color swatch
            draw.rectangle(
                [(10, y_start + 5), (color_width - 10, y_start + row_height - 5)],
                fill=(r, g, b),
                outline=(180, 180, 180),
                width=1
            )
            
            # Draw hex code
            hex_code = f"#{r:02X}{g:02X}{b:02X}".lower()
            draw.text((color_width + 20, y_start + 15), hex_code, fill=(70, 130, 180), font=font)
            
            # Draw RGB values
            rgb_text = f"({r},{g},{b})"
            draw.text((color_width + hex_width + 20, y_start + 15), rgb_text, fill=(70, 70, 70), font=font)
        
        # Save to bytes
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer.getvalue()
    
    @color_group.command(name="palette", aliases=["harmony", "scheme"])
    async def color_palette(self, ctx, color: str):
        """🎯 Generate a color harmony palette."""
        color = color.strip("#").upper()
        if len(color) == 3:
            color = "".join([c*2 for c in color])
        
        if len(color) != 6 or not all(c in "0123456789ABCDEF" for c in color):
            return await ctx.reply("❌ Invalid hex color!", mention_author=False)
        
        r, g, b = self._hex_to_rgb(color)
        h, s, l = self._rgb_to_hsl(r, g, b)
        
        # Generate harmonies
        comp = self._get_complementary(r, g, b)
        analogous = [self._hsl_to_rgb(*c) for c in self._get_analogous(h, s, l)]
        triadic = [self._hsl_to_rgb(*c) for c in self._get_triadic(h, s, l)]
        
        # Shades (darker) and tints (lighter)
        shades = [self._hsl_to_rgb(h, s, max(0, l - 20)), self._hsl_to_rgb(h, s, max(0, l - 40))]
        tints = [self._hsl_to_rgb(h, s, min(100, l + 20)), self._hsl_to_rgb(h, s, min(100, l + 40))]
        
        # Collect all palette colors for the image
        palette_colors = [
            (r, g, b),  # Original
            comp,  # Complementary
            analogous[0],  # Analogous 1
            analogous[1],  # Analogous 2
            triadic[0],  # Triadic 1
            triadic[1],  # Triadic 2
        ]
        
        # Generate palette image
        image_bytes = self._generate_palette_image(palette_colors)
        file = discord.File(BytesIO(image_bytes), filename="palette.png")
        
        embed = discord.Embed(
            title=f"Color Palette for #{color}",
            color=discord.Color.from_rgb(r, g, b)
        )
        
        # Build palette info in embed
        palette_text = ""
        labels = ["Original", "Complementary", "Analogous 1", "Analogous 2", "Triadic 1", "Triadic 2"]
        for label, (pr, pg, pb) in zip(labels, palette_colors):
            hex_c = f"#{pr:02X}{pg:02X}{pb:02X}"
            palette_text += f"**{label}:** `{hex_c}` → `rgb({pr},{pg},{pb})`\n"
        
        embed.add_field(
            name="🎯 Colors in Palette",
            value=palette_text,
            inline=False
        )
        
        # Shades & Tints info
        shades_text = " ".join([f"`#{self._rgb_to_hex(*c)}`" for c in shades])
        tints_text = " ".join([f"`#{self._rgb_to_hex(*c)}`" for c in tints])
        
        embed.add_field(
            name="🌑 Shades (Darker)",
            value=shades_text,
            inline=True
        )
        
        embed.add_field(
            name="☀️ Tints (Lighter)",
            value=tints_text,
            inline=True
        )
        
        embed.set_image(url="attachment://palette.png")
        embed.set_footer(text="💡 Copy hex codes directly from the image or embed!")
        
        await ctx.reply(embed=embed, file=file, mention_author=False)
    
    @color_group.command(name="contrast", aliases=["check", "wcag"])
    async def color_contrast(self, ctx, color1: str, color2: str):
        """♿ Check contrast ratio between two colors (WCAG accessibility)."""
        # Parse colors
        color1 = color1.strip("#").upper()
        color2 = color2.strip("#").upper()
        
        for c in [color1, color2]:
            if len(c) == 3:
                c = "".join([x*2 for x in c])
        
        if len(color1) == 3:
            color1 = "".join([x*2 for x in color1])
        if len(color2) == 3:
            color2 = "".join([x*2 for x in color2])
        
        try:
            rgb1 = self._hex_to_rgb(color1)
            rgb2 = self._hex_to_rgb(color2)
        except:
            return await ctx.reply("❌ Invalid hex colors!", mention_author=False)
        
        ratio = self._get_contrast_ratio(rgb1, rgb2)
        
        # WCAG ratings
        aa_normal = "✅ Pass" if ratio >= 4.5 else "❌ Fail"
        aa_large = "✅ Pass" if ratio >= 3 else "❌ Fail"
        aaa_normal = "✅ Pass" if ratio >= 7 else "❌ Fail"
        aaa_large = "✅ Pass" if ratio >= 4.5 else "❌ Fail"
        
        # Overall rating
        if ratio >= 7:
            rating = "🏆 Excellent"
            rating_color = discord.Color.green()
        elif ratio >= 4.5:
            rating = "✅ Good"
            rating_color = discord.Color.green()
        elif ratio >= 3:
            rating = "⚠️ Okay for large text"
            rating_color = discord.Color.orange()
        else:
            rating = "❌ Poor - Hard to read"
            rating_color = discord.Color.red()
        
        embed = discord.Embed(
            title="♿ Contrast Checker",
            description=f"**Ratio:** `{ratio:.2f}:1`\n**Rating:** {rating}",
            color=rating_color
        )
        
        embed.add_field(
            name=f"🎨 Color 1",
            value=f"`#{color1}`",
            inline=True
        )
        embed.add_field(
            name=f"🎨 Color 2",
            value=f"`#{color2}`",
            inline=True
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        await ctx.reply(embed=embed, mention_author=False)
    
    @color_group.command(name="preview", aliases=["demo", "show"])
    async def color_preview(self, ctx, color: str):
        """👁️ Preview how a color looks on common UI elements."""
        color = color.strip("#").upper()
        if len(color) == 3:
            color = "".join([c*2 for c in color])
        
        if len(color) != 6 or not all(c in "0123456789ABCDEF" for c in color):
            return await ctx.reply("Invalid hex color!", mention_author=False)
        
        r, g, b = self._hex_to_rgb(color)
        
        # Determine best text color
        white_contrast = self._get_contrast_ratio((r, g, b), (255, 255, 255))
        black_contrast = self._get_contrast_ratio((r, g, b), (0, 0, 0))
        text_color = "FFFFFF" if white_contrast > black_contrast else "000000"
        
        embed = discord.Embed(
            title=f"Color Preview: #{color}",
            description=f"See how `#{color}` looks in different contexts!",
            color=discord.Color.from_rgb(r, g, b)
        )
        
        embed.add_field(
            name="As Embed Color",
            value="← This embed uses your color!",
            inline=False
        )
        
        embed.add_field(
            name="Copy-Paste Codes",
            value=f"**CSS:** `background-color: #{color};`\n"
                  f"**Tailwind:** `bg-[#{color}]`\n"
                  f"**Discord:** `color=discord.Color.from_rgb({r}, {g}, {b})`",
            inline=False
        )
        
        embed.add_field(
            name="Best Text Color",
            value=f"Use **{'White' if text_color == 'FFFFFF' else 'Black'}** text\n"
                  f"Contrast ratio: `{max(white_contrast, black_contrast):.1f}:1`",
            inline=True
        )
        
        embed.add_field(
            name="Color Name",
            value=f"**{self._get_color_name(r, g, b)}**",
            inline=True
        )
        
        # Preview images
        embed.set_thumbnail(url=f"https://singlecolorimage.com/get/{color}/100x100")
        embed.set_image(url=f"https://via.placeholder.com/400x100/{color}/{text_color}?text=Sample+Text")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    @color_group.command(name="image", aliases=["extract", "img"])
    async def color_from_image(self, ctx):
        """🖼️ Extract dominant colors from an attached image."""
        # Check for attachment
        if not ctx.message.attachments:
            embed = discord.Embed(
                title="Image Color Extraction",
                description="Attach an image to extract its colors!\n\n"
                           f"**Usage:** `{ctx.prefix}color image` (with image attached)",
                color=primary_color()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        attachment = ctx.message.attachments[0]
        
        # Check if it's an image
        if not attachment.content_type or not attachment.content_type.startswith("image"):
            return await ctx.reply("❌ Please attach a valid image!", mention_author=False)
        
        async with ctx.typing():
            try:
                # Download image
                image_data = await attachment.read()
                
                # Use colorthief-like extraction (simplified)
                from io import BytesIO
                from PIL import Image
                
                img = Image.open(BytesIO(image_data))
                img = img.convert("RGB")
                img = img.resize((100, 100))  # Resize for speed
                
                # Get all pixels
                pixels = list(img.getdata())
                
                # Simple color clustering - get most common colors
                from collections import Counter
                
                # Quantize colors to reduce variations
                def quantize(color, factor=32):
                    return tuple((c // factor) * factor for c in color)
                
                quantized = [quantize(p) for p in pixels]
                color_counts = Counter(quantized)
                
                # Get top 5 colors
                top_colors = color_counts.most_common(5)
                
                embed = discord.Embed(
                    title="Extracted Colors",
                    color=discord.Color.from_rgb(*top_colors[0][0])
                )
                
                color_list = []
                for i, (color, count) in enumerate(top_colors):
                    hex_code = self._rgb_to_hex(*color)
                    percentage = (count / len(pixels)) * 100
                    emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
                    color_list.append(f"{emoji} `#{hex_code}` ({percentage:.1f}%)")
                
                embed.add_field(
                    name="🎨 Dominant Colors",
                    value="\n".join(color_list),
                    inline=False
                )
                
                embed.set_thumbnail(url=attachment.url)
                embed.set_footer(text="Colors extracted from image analysis")
                
                await ctx.reply(embed=embed, mention_author=False)
                
            except ImportError:
                embed = discord.Embed(
                    title="❌ Missing Dependency",
                    description="Image color extraction requires `Pillow`.\n"
                               "Install with: `pip install Pillow`",
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed, mention_author=False)
            except Exception as e:
                await ctx.reply(f"❌ Error extracting colors: {str(e)}", mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # QR CODE GENERATOR - Replacing useless crypto
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="qr", aliases=["qrcode"])
    async def qr_generator(self, ctx, *, text: str):
        """📱 Generate a QR code from text or URL."""
        import urllib.parse
        
        if len(text) > 500:
            return await ctx.reply("Text too long! Max 500 characters.", mention_author=False)
        
        # URL encode the text
        encoded = urllib.parse.quote(text)
        
        # Generate QR using Google Charts API
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded}"
        
        embed = discord.Embed(
            title="📱 QR Code Generated",
            description=f"**Content:** {text[:100]}{'...' if len(text) > 100 else ''}",
            color=primary_color()
        )
        
        embed.set_image(url=qr_url)
        embed.set_footer(text="Scan with any QR reader!")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # SCREENSHOT TOOL - Modern utility
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="screenshot", aliases=["ss", "snap"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def screenshot_website(self, ctx, url: str):
        """📸 Take a screenshot of a website."""
        import urllib.parse
        
        # Validate URL
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        # Use screenshot API
        encoded_url = urllib.parse.quote(url)
        screenshot_url = f"https://api.screenshotmachine.com/?key=guest&url={encoded_url}&dimension=1024x768"
        
        embed = discord.Embed(
            title="📸 Website Screenshot",
            description=f"**URL:** {url}",
            color=primary_color()
        )
        
        embed.set_image(url=screenshot_url)
        embed.set_footer(text=f"Requested by {ctx.author}")
        
        await ctx.reply(embed=embed, mention_author=False)
    
    # ═══════════════════════════════════════════════════════════════
    # SHORTEN URL - Modern utility
    # ═══════════════════════════════════════════════════════════════
    
    @commands.command(name="shorten", aliases=["short", "tinyurl"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def shorten_url(self, ctx, url: str):
        """🔗 Shorten a URL using TinyURL."""
        import aiohttp
        
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        
        async with ctx.typing():
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(f"https://tinyurl.com/api-create.php?url={url}") as resp:
                        if resp.status == 200:
                            short_url = await resp.text()
                            
                            embed = discord.Embed(
                                title="🔗 URL Shortened!",
                                color=discord.Color.green()
                            )
                            embed.add_field(name="Original", value=f"`{url[:50]}{'...' if len(url) > 50 else ''}`", inline=False)
                            embed.add_field(name="Shortened", value=f"**{short_url}**", inline=False)
                            
                            return await ctx.reply(embed=embed, mention_author=False)
                except Exception:
                    pass
        
        await ctx.reply("❌ Could not shorten URL", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # MATH CALCULATOR
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="calc", aliases=["calculate", "math"])
    async def calculator(self, ctx, *, expression: str):
        """🔢 Calculate a math expression"""
        import ast
        import operator
        
        # Safe operators
        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.Mod: operator.mod,
        }
        
        def safe_eval(node):
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.BinOp):
                return operators[type(node.op)](safe_eval(node.left), safe_eval(node.right))
            elif isinstance(node, ast.UnaryOp):
                return operators[type(node.op)](safe_eval(node.operand))
            else:
                raise ValueError("Invalid expression")
        
        try:
            # Clean expression
            expression = expression.replace("^", "**").replace("x", "*").replace("×", "*").replace("÷", "/")
            tree = ast.parse(expression, mode='eval')
            result = safe_eval(tree.body)
            
            embed = discord.Embed(
                title="🔢 Calculator",
                color=primary_color()
            )
            embed.add_field(name="Expression", value=f"```{expression}```", inline=False)
            embed.add_field(name="Result", value=f"```{result:,.10g}```", inline=False)
            
            await ctx.reply(embed=embed, mention_author=False)
        except Exception:
            await ctx.reply("❌ Invalid math expression", mention_author=False)


async def setup(bot):
    await bot.add_cog(Search(bot))
