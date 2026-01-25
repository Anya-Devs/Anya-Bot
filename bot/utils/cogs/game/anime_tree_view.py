"""
Paginated Anime Tree View for Gacha System
Interactive Discord UI for browsing character collection by anime series
"""
import io
import discord
import asyncio
from difflib import SequenceMatcher
from collections import defaultdict
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp
from functools import partial

logger = logging.getLogger(__name__)

def fuzzy_match_anime(anime1: str, anime2: str, threshold: float = 0.75) -> bool:
    """Check if two anime names are similar using fuzzy matching."""
    if not anime1 or not anime2:
        return False
    
    a1 = anime1.lower().strip()
    a2 = anime2.lower().strip()
    
    if a1 == a2:
        return True
    if a1 in a2 or a2 in a1:
        return True
    
    ratio = SequenceMatcher(None, a1, a2).ratio()
    return ratio >= threshold

def process_character_chunk(char_chunk: list, anime_representatives: dict) -> tuple:
    """Process a chunk of characters for concurrent anime grouping."""
    chunk_groups = {}
    chunk_representatives = {}
    
    for char in char_chunk:
        anime = char.get("anime", "Unknown")
        if not anime:
            anime = "Unknown"
        
        matched = False
        # Check against existing representatives
        for canonical_anime in anime_representatives.keys():
            if fuzzy_match_anime(anime, canonical_anime):
                if canonical_anime not in chunk_groups:
                    chunk_groups[canonical_anime] = []
                chunk_groups[canonical_anime].append(char)
                matched = True
                break
        
        # Check against chunk representatives
        if not matched:
            for canonical_anime in chunk_representatives.keys():
                if fuzzy_match_anime(anime, canonical_anime):
                    chunk_representatives[anime] = chunk_representatives[canonical_anime]
                    chunk_groups[chunk_representatives[canonical_anime]].append(char)
                    matched = True
                    break
        
        if not matched:
            chunk_representatives[anime] = anime
            chunk_groups[anime] = [char]
    
    return chunk_groups, chunk_representatives

def group_characters_by_anime(characters: list) -> dict:
    """Group characters by anime using concurrent fuzzy matching - only keep anime with 2+ characters."""
    if not characters:
        return {}
    
    # Use ThreadPoolExecutor for concurrent processing
    cpu_count = min(mp.cpu_count(), 8)  # Limit to 8 threads max
    chunk_size = max(1, len(characters) // cpu_count)
    character_chunks = [characters[i:i + chunk_size] for i in range(0, len(characters), chunk_size)]
    
    anime_groups = {}
    anime_representatives = {}
    
    with ThreadPoolExecutor(max_workers=cpu_count) as executor:
        # Process chunks concurrently
        futures = []
        for chunk in character_chunks:
            future = executor.submit(process_character_chunk, chunk, anime_representatives)
            futures.append(future)
        
        # Collect results
        for future in futures:
            chunk_groups, chunk_representatives = future.result()
            
            # Merge chunk representatives
            for anime, canonical in chunk_representatives.items():
                if canonical not in anime_representatives:
                    anime_representatives[canonical] = canonical
                    anime_groups[canonical] = chunk_groups.get(canonical, [])
                else:
                    # Merge characters
                    anime_groups[canonical].extend(chunk_groups.get(canonical, []))
    
    # Filter to only keep anime with 2+ characters (speed optimization)
    filtered_groups = {anime: chars for anime, chars in anime_groups.items() if len(chars) > 1}
    
    return filtered_groups

class AnimeTreeView(discord.ui.View):
    """Interactive view for browsing anime collection with image generation"""
    
    def __init__(self, cog, user, guild_id, characters, anime_groups):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.cog = cog
        self.user = user
        self.guild_id = guild_id
        self.characters = characters
        self.anime_groups = anime_groups
        self.anime_list = sorted(anime_groups.keys(), key=lambda x: len(anime_groups[x]), reverse=True)
        self.current_anime_index = 0
        self.current_image_buffer = None
        # Concurrent processing pools
        self.thread_pool = ThreadPoolExecutor(max_workers=min(mp.cpu_count(), 4))
        # Preload cache for faster navigation
        self.image_cache = {}
        self.preload_task = None
        
    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)
        await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources properly"""
        # Cleanup thread pool
        if self.thread_pool:
            self.thread_pool.shutdown(wait=False)
            self.thread_pool = None
        
        # Cancel preload task
        if self.preload_task and not self.preload_task.done():
            self.preload_task.cancel()
            try:
                await self.preload_task
            except asyncio.CancelledError:
                pass
            self.preload_task = None
        
        # Clear cache to free memory
        self.image_cache.clear()
    
    @property
    def current_anime(self):
        """Get the currently selected anime"""
        if self.current_anime_index < len(self.anime_list):
            return self.anime_list[self.current_anime_index]
        return None
    
    @property
    def current_anime_characters(self):
        """Get characters for the current anime"""
        anime = self.current_anime
        if anime and anime in self.anime_groups:
            return self.anime_groups[anime]
        return []
    
    def _generate_anime_image_sync(self, anime_name: str, characters: list):
        """Synchronous wrapper for anime image generation (for thread pool)"""
        import asyncio
        from bot.utils.cogs.game.images import generate_anime_series_image
        
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(generate_anime_series_image(anime_name, characters))
        finally:
            loop.close()

    async def generate_anime_image_cached(self, anime_name: str, characters: list):
        """Generate an image with caching for faster repeated access"""
        cache_key = f"{anime_name}_{len(characters)}"
        
        # Check cache first
        if cache_key in self.image_cache:
            logger.info(f"Using cached image for {anime_name}")
            return self.image_cache[cache_key]
        
        # Generate image concurrently
        loop = asyncio.get_event_loop()
        try:
            # Run synchronous wrapper in thread pool to avoid blocking
            buffer = await loop.run_in_executor(
                self.thread_pool, 
                partial(self._generate_anime_image_sync, anime_name, characters)
            )
            
            # Cache the result (limit cache size)
            if len(self.image_cache) < 10:  # Cache up to 10 anime images
                self.image_cache[cache_key] = buffer
            
            return buffer
        except Exception as e:
            logger.error(f"Error generating image for {anime_name}: {e}")
            return None
    
    async def preload_adjacent_images(self):
        """Preload adjacent anime images for faster navigation"""
        if not self.anime_list:
            return
        
        # Preload current, next, and previous
        indices_to_preload = [self.current_anime_index]
        if self.current_anime_index > 0:
            indices_to_preload.append(self.current_anime_index - 1)
        if self.current_anime_index < len(self.anime_list) - 1:
            indices_to_preload.append(self.current_anime_index + 1)
        
        # Create concurrent preload tasks
        preload_tasks = []
        for idx in indices_to_preload:
            if idx < len(self.anime_list):
                anime = self.anime_list[idx]
                chars = self.anime_groups[anime]
                task = asyncio.create_task(self.generate_anime_image_cached(anime, chars))
                preload_tasks.append(task)
        
        # Wait for all preloads to complete
        if preload_tasks:
            await asyncio.gather(*preload_tasks, return_exceptions=True)
    
    async def generate_anime_image(self, anime_name: str, characters: list):
        """Generate an image showing all character cards for an anime series"""
        return await self.generate_anime_image_cached(anime_name, characters)
    
    def update_navigation_state(self):
        """Update button states based on current position"""
        # Only anime navigation
        self.prev_anime_button.disabled = self.current_anime_index <= 0
        self.next_anime_button.disabled = self.current_anime_index >= len(self.anime_list) - 1
    
    async def create_message_content(self):
        """Generate image and embed for current anime"""
        anime = self.current_anime
        if not anime:
            return None, discord.Embed(
                title="🌳 Anime Collection",
                description="No anime series found in your collection!",
                color=discord.Color.red()
            )
        
        chars = self.current_anime_characters
        if not chars:
            return None, discord.Embed(
                title=f"🌳 {anime}",
                description="No characters found for this anime series!",
                color=discord.Color.orange()
            )
        
        try:
            # Generate image with concurrent processing
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Generating anime image for {anime} with {len(chars)} characters (concurrent)")
            
            buffer = await self.generate_anime_image_cached(anime, chars)
            self.current_image_buffer = buffer
            
            # Start preloading adjacent images in background
            if not self.preload_task or self.preload_task.done():
                self.preload_task = asyncio.create_task(self.preload_adjacent_images())
            
            # Create embed
            embed = discord.Embed(
                title=f"🌳 {anime}",
                description=f"**{len(chars)}** characters from this series",
                color=discord.Color.blue()
            )
            
            # Attach image to embed if buffer exists
            if buffer:
                embed.set_image(url=f"attachment://anime_{self.current_anime_index}.png")
            
            # Footer with navigation info
            anime_info = f"Anime {self.current_anime_index + 1}/{len(self.anime_list)}"
            embed.set_footer(text=f"{anime_info} • Total: {len(self.characters)} characters")
            
            return buffer, embed
            
        except Exception as e:
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating anime image for {anime}: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Return error embed
            embed = discord.Embed(
                title=f"🌳 {anime}",
                description=f"Error generating image: {str(e)}",
                color=discord.Color.red()
            )
            return None, embed
    
    async def update_message(self, interaction: discord.Interaction = None):
        """Update the message with new image and button states"""
        try:
            self.update_navigation_state()
            buffer, embed = await self.create_message_content()
            
            if buffer:
                file = discord.File(buffer, filename=f"anime_{self.current_anime_index}.png")
                embed.set_image(url=f"attachment://anime_{self.current_anime_index}.png")
                
                # Always edit the original message (interaction expires after 3 seconds)
                await self.message.edit(embed=embed, attachments=[file], view=self)
            else:
                # No image, just edit embed
                await self.message.edit(embed=embed, view=self)
                
        except Exception as e:
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Error updating anime tree message: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Send error message
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to update view: {str(e)}",
                color=discord.Color.red()
            )
            try:
                if interaction and not interaction.response.is_done():
                    await interaction.response.edit_message(embed=error_embed, view=self)
                else:
                    await self.message.edit(embed=error_embed, view=self)
            except:
                pass
    
    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev_anime")
    async def prev_anime_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to previous anime series"""
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        
        try:
            if interaction.user != self.user:
                await interaction.response.send_message("You can't use this view!", ephemeral=True)
                return
            
            logger.info(f"Previous anime button clicked by user {interaction.user.id}")
            
            if self.current_anime_index > 0:
                self.current_anime_index -= 1
                logger.info(f"Navigating to anime index {self.current_anime_index}")
                await interaction.response.defer()
                await self.update_message()
            else:
                logger.info("Already at first anime, ignoring navigation")
                await interaction.response.defer()
                
        except Exception as e:
            logger.error(f"Error in prev_anime_button: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            logger.error(f"User: {interaction.user.id if interaction.user else 'Unknown'}")
            logger.error(f"Current anime index: {self.current_anime_index}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error navigating to previous anime. Please try again.", ephemeral=True)
            except Exception as response_error:
                logger.error(f"Could not send error response: {response_error}")
    
    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next_anime")
    async def next_anime_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Navigate to next anime series"""
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        
        try:
            if interaction.user != self.user:
                await interaction.response.send_message("You can't use this view!", ephemeral=True)
                return
            
            logger.info(f"Next anime button clicked by user {interaction.user.id}")
            
            if self.current_anime_index < len(self.anime_list) - 1:
                self.current_anime_index += 1
                logger.info(f"Navigating to anime index {self.current_anime_index}")
                await interaction.response.defer()
                await self.update_message()
            else:
                logger.info("Already at last anime, ignoring navigation")
                await interaction.response.defer()
                
        except Exception as e:
            logger.error(f"Error in next_anime_button: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            logger.error(f"User: {interaction.user.id if interaction.user else 'Unknown'}")
            logger.error(f"Current anime index: {self.current_anime_index}")
            logger.error(f"Total anime count: {len(self.anime_list)}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error navigating to next anime. Please try again.", ephemeral=True)
            except Exception as response_error:
                logger.error(f"Could not send error response: {response_error}")
    
    @discord.ui.button(label="Select Anime", emoji="📋", style=discord.ButtonStyle.success, custom_id="select_anime")
    async def select_anime_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show dropdown to select anime series"""
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        
        try:
            if interaction.user != self.user:
                await interaction.response.send_message("You can't use this view!", ephemeral=True)
                return
            
            logger.info(f"Select anime button clicked by user {interaction.user.id}")
            
            # Create select menu
            select = discord.ui.Select(
                placeholder="Choose an anime series...",
                options=[
                    discord.SelectOption(
                        label=f"{anime[:50]}{'...' if len(anime) > 50 else ''} ({len(self.anime_groups[anime])} chars)",
                        value=str(idx),
                        description=f"Browse {len(self.anime_groups[anime])} characters from {anime[:30]}{'...' if len(anime) > 30 else ''}"
                    )
                    for idx, anime in enumerate(self.anime_list[:25])  # Limit to 25 options
                ]
            )
            
            async def select_callback(select_interaction: discord.Interaction):
                try:
                    if select_interaction.user != self.user:
                        await select_interaction.response.send_message("You can't use this view!", ephemeral=True)
                        return
                    
                    selected_idx = int(select.values[0])
                    logger.info(f"User selected anime index {selected_idx}")
                    self.current_anime_index = selected_idx
                    # Defer the ephemeral select interaction, then edit main message
                    await select_interaction.response.defer()
                    await self.update_message()
                    
                except Exception as e:
                    logger.error(f"Error in anime select callback: {e}")
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    
                    try:
                        if not select_interaction.response.is_done():
                            await select_interaction.response.send_message("❌ Error selecting anime. Please try again.", ephemeral=True)
                    except Exception as response_error:
                        logger.error(f"Could not send error response: {response_error}")
            
            select.callback = select_callback
            
            # Create temporary view with just the select menu
            temp_view = discord.ui.View(timeout=60)
            temp_view.add_item(select)
            
            await interaction.response.send_message("Select an anime series:", view=temp_view, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in select_anime_button: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            logger.error(f"User: {interaction.user.id if interaction.user else 'Unknown'}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ Error opening anime selection. Please try again.", ephemeral=True)
            except Exception as response_error:
                logger.error(f"Could not send error response: {response_error}")

async def create_anime_tree_view(cog, ctx, characters):
    """Create and send the anime tree view with image generation"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Group characters by anime (only anime with 2+ characters)
        anime_groups = group_characters_by_anime(characters)
        
        if not anime_groups:
            await ctx.reply("❌ No anime series with 2+ characters found in your collection!", mention_author=False)
            return
        
        logger.info(f"Creating anime tree view with {len(anime_groups)} anime groups")
        
        # Create view
        view = AnimeTreeView(cog, ctx.author, ctx.guild.id, characters, anime_groups)
        
        # Generate initial content
        buffer, embed = await view.create_message_content()
        
        # Send initial message
        if buffer:
            file = discord.File(buffer, filename=f"anime_{view.current_anime_index}.png")
            message = await ctx.reply(embed=embed, file=file, view=view, mention_author=False)
        else:
            message = await ctx.reply(embed=embed, view=view, mention_author=False)
        
        view.message = message
        logger.info("Anime tree view created successfully")
        
    except Exception as e:
        import traceback
        logger.error(f"Error creating anime tree view: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Cleanup view if it was created
        if 'view' in locals():
            try:
                await view.cleanup()
            except Exception as cleanup_error:
                logger.error(f"Error during cleanup: {cleanup_error}")
        
        await ctx.reply(f"❌ Error creating anime tree view: {str(e)}", mention_author=False)
