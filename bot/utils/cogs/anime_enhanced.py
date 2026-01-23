"""
Enhanced Anime Character & Image System
Provides rich character information, galleries, and multi-source image scraping
"""

import aiohttp
import asyncio
import random
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
import discord
from discord import ui

logger = logging.getLogger(__name__)


class ImageSource:
    """Multi-source image scraper for anime images with artist attribution"""
    
    def __init__(self):
        self.sources = {
            "safebooru": "https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1",
            "gelbooru": "https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1",
            "danbooru": "https://danbooru.donmai.us/posts.json",
            "konachan": "https://konachan.com/post.json",
        }
    
    async def fetch_neko_images(self, limit: int = 20) -> List[Dict]:
        """Fetch neko images from multiple sources with artist info"""
        tags = ["cat_ears", "cat_girl", "nekomimi", "rating:safe"]
        return await self._fetch_from_sources(tags, limit)
    
    async def fetch_kitsune_images(self, limit: int = 20) -> List[Dict]:
        """Fetch kitsune/fox girl images from multiple sources"""
        tags = ["fox_ears", "fox_girl", "kitsune", "rating:safe"]
        return await self._fetch_from_sources(tags, limit)
    
    async def _fetch_from_sources(self, tags: List[str], limit: int) -> List[Dict]:
        """Fetch images from multiple booru sources"""
        all_images = []
        
        async with aiohttp.ClientSession() as session:
            # Try Safebooru first (most reliable for SFW)
            safebooru_images = await self._fetch_safebooru(session, tags, limit)
            all_images.extend(safebooru_images)
            
            # Try Konachan for high quality images
            if len(all_images) < limit:
                konachan_images = await self._fetch_konachan(session, tags, limit - len(all_images))
                all_images.extend(konachan_images)
            
            # Try Danbooru for variety
            if len(all_images) < limit:
                danbooru_images = await self._fetch_danbooru(session, tags, limit - len(all_images))
                all_images.extend(danbooru_images)
        
        # Shuffle for variety
        random.shuffle(all_images)
        return all_images[:limit]
    
    async def _fetch_safebooru(self, session: aiohttp.ClientSession, tags: List[str], limit: int) -> List[Dict]:
        """Fetch from Safebooru (100% SFW)"""
        try:
            tag_str = " ".join(tags)
            url = f"{self.sources['safebooru']}&tags={tag_str}&limit={limit}"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    images = []
                    for post in data:
                        if isinstance(post, dict):
                            images.append({
                                "url": f"https://safebooru.org/images/{post.get('directory')}/{post.get('image')}",
                                "thumbnail": f"https://safebooru.org/thumbnails/{post.get('directory')}/thumbnail_{post.get('image')}",
                                "artist": post.get("owner", "Unknown"),
                                "source": post.get("source", ""),
                                "tags": post.get("tags", "").split(),
                                "rating": "safe",
                                "score": post.get("score", 0),
                                "site": "Safebooru"
                            })
                    return images
        except Exception as e:
            logger.error(f"Safebooru fetch error: {e}")
        return []
    
    async def _fetch_konachan(self, session: aiohttp.ClientSession, tags: List[str], limit: int) -> List[Dict]:
        """Fetch from Konachan (high quality)"""
        try:
            # Filter to only safe tags
            safe_tags = [t for t in tags if "rating:" not in t] + ["rating:s"]
            tag_str = " ".join(safe_tags)
            url = f"{self.sources['konachan']}?tags={tag_str}&limit={limit}"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    images = []
                    for post in data:
                        if post.get("rating") == "s":  # Safe only
                            images.append({
                                "url": post.get("file_url", ""),
                                "thumbnail": post.get("preview_url", ""),
                                "artist": post.get("author", "Unknown"),
                                "source": post.get("source", ""),
                                "tags": post.get("tags", "").split(),
                                "rating": "safe",
                                "score": post.get("score", 0),
                                "site": "Konachan"
                            })
                    return images
        except Exception as e:
            logger.error(f"Konachan fetch error: {e}")
        return []
    
    async def _fetch_danbooru(self, session: aiohttp.ClientSession, tags: List[str], limit: int) -> List[Dict]:
        """Fetch from Danbooru"""
        try:
            safe_tags = [t for t in tags if "rating:" not in t] + ["rating:general"]
            tag_str = " ".join(safe_tags)
            url = f"{self.sources['danbooru']}?tags={tag_str}&limit={limit}"
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    images = []
                    for post in data:
                        if post.get("rating") == "g":  # General/Safe only
                            images.append({
                                "url": post.get("file_url", ""),
                                "thumbnail": post.get("preview_file_url", ""),
                                "artist": post.get("tag_string_artist", "Unknown").replace("_", " "),
                                "source": post.get("source", ""),
                                "tags": post.get("tag_string_general", "").split(),
                                "rating": "safe",
                                "score": post.get("score", 0),
                                "site": "Danbooru"
                            })
                    return images
        except Exception as e:
            logger.error(f"Danbooru fetch error: {e}")
        return []


class CharacterInfo:
    """Fetch detailed character information from MyAnimeList/Jikan API"""
    
    def __init__(self):
        self.api_url = "https://api.jikan.moe/v4"
    
    async def search_characters(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for characters by name"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/characters?q={query}&limit={limit}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", [])
        except Exception as e:
            logger.error(f"Character search error: {e}")
        return []
    
    async def get_character_full(self, character_id: int) -> Optional[Dict]:
        """Get full character information including anime appearances"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/characters/{character_id}/full"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("data", {})
        except Exception as e:
            logger.error(f"Character full info error: {e}")
        return None
    
    async def get_character_pictures(self, character_id: int) -> List[str]:
        """Get all available pictures for a character"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_url}/characters/{character_id}/pictures"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pictures = data.get("data", [])
                        return [p.get("jpg", {}).get("image_url", "") for p in pictures if p.get("jpg")]
        except Exception as e:
            logger.error(f"Character pictures error: {e}")
        return []


class CharacterSelectView(ui.View):
    """Interactive character selection from search results"""
    
    def __init__(self, characters: List[Dict], ctx, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.characters = characters
        self.ctx = ctx
        self.selected_character = None
        
        # Add character select dropdown
        options = []
        for i, char in enumerate(characters[:25]):  # Discord limit
            name = char.get("name", "Unknown")
            anime_list = char.get("anime", [])
            anime_name = anime_list[0].get("anime", {}).get("title", "Unknown") if anime_list else "Unknown"
            
            options.append(discord.SelectOption(
                label=name[:100],
                description=anime_name[:100],
                value=str(i)
            ))
        
        if options:
            select = ui.Select(
                placeholder="Select a character...",
                options=options,
                custom_id="character_select"
            )
            select.callback = self.character_selected
            self.add_item(select)
    
    async def character_selected(self, interaction: discord.Interaction):
        """Handle character selection"""
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't your menu!", ephemeral=True)
        
        idx = int(interaction.values[0])
        self.selected_character = self.characters[idx]
        
        # Show character details
        await self.show_character_details(interaction)
    
    async def show_character_details(self, interaction: discord.Interaction):
        """Display detailed character information"""
        char = self.selected_character
        char_id = char.get("mal_id")
        
        # Fetch full character info
        char_info_api = CharacterInfo()
        full_char = await char_info_api.get_character_full(char_id)
        
        if not full_char:
            return await interaction.response.send_message("❌ Could not fetch character details", ephemeral=True)
        
        # Build detailed embed
        name = full_char.get("name", "Unknown")
        about = full_char.get("about", "No description available.")[:1024]
        favorites = full_char.get("favorites", 0)
        image = full_char.get("images", {}).get("jpg", {}).get("image_url", "")
        
        # Get anime appearances
        anime_list = full_char.get("anime", [])[:5]
        anime_str = "\n".join([f"• {a.get('anime', {}).get('title', 'Unknown')}" for a in anime_list]) if anime_list else "No anime found"
        
        embed = discord.Embed(
            title=f"📖 {name}",
            description=about,
            color=discord.Color.from_rgb(255, 182, 193)
        )
        
        if image:
            embed.set_thumbnail(url=image)
        
        embed.add_field(name="❤️ Favorites", value=f"{favorites:,}", inline=True)
        embed.add_field(name="🎌 Appears In", value=anime_str[:1024], inline=False)
        embed.set_footer(text=f"MAL ID: {char_id}")
        
        # Add gallery button
        view = CharacterGalleryView(char_id, self.ctx)
        
        await interaction.response.edit_message(embed=embed, view=view)


class CharacterGalleryView(ui.View):
    """Image gallery for character with pagination"""
    
    def __init__(self, character_id: int, ctx, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.character_id = character_id
        self.ctx = ctx
        self.images = []
        self.current_page = 0
        self.loaded = False
    
    async def load_images(self):
        """Load character images"""
        if not self.loaded:
            char_info = CharacterInfo()
            self.images = await char_info.get_character_pictures(self.character_id)
            self.loaded = True
    
    @ui.button(label="📸 View Gallery", style=discord.ButtonStyle.primary)
    async def view_gallery(self, interaction: discord.Interaction, button: ui.Button):
        """Show image gallery"""
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't your gallery!", ephemeral=True)
        
        await interaction.response.defer()
        
        await self.load_images()
        
        if not self.images:
            return await interaction.followup.send("❌ No images found for this character", ephemeral=True)
        
        # Show first image with pagination
        await self.show_image_page(interaction)
    
    async def show_image_page(self, interaction: discord.Interaction):
        """Display current image page"""
        if not self.images:
            return
        
        embed = discord.Embed(
            title=f"🖼️ Character Gallery",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        embed.set_image(url=self.images[self.current_page])
        embed.set_footer(text=f"Image {self.current_page + 1}/{len(self.images)}")
        
        # Create pagination view
        view = ui.View(timeout=180)
        
        # Previous button
        prev_btn = ui.Button(emoji="⬅️", style=discord.ButtonStyle.gray, disabled=self.current_page == 0)
        async def prev_callback(inter: discord.Interaction):
            if inter.user != self.ctx.author:
                return await inter.response.send_message("This isn't your gallery!", ephemeral=True)
            self.current_page = max(0, self.current_page - 1)
            await self.show_image_page(inter)
        prev_btn.callback = prev_callback
        view.add_item(prev_btn)
        
        # Next button
        next_btn = ui.Button(emoji="➡️", style=discord.ButtonStyle.gray, disabled=self.current_page >= len(self.images) - 1)
        async def next_callback(inter: discord.Interaction):
            if inter.user != self.ctx.author:
                return await inter.response.send_message("This isn't your gallery!", ephemeral=True)
            self.current_page = min(len(self.images) - 1, self.current_page + 1)
            await self.show_image_page(inter)
        next_btn.callback = next_callback
        view.add_item(next_btn)
        
        # Close button
        close_btn = ui.Button(label="Close", style=discord.ButtonStyle.danger)
        async def close_callback(inter: discord.Interaction):
            if inter.user != self.ctx.author:
                return await inter.response.send_message("This isn't your gallery!", ephemeral=True)
            await inter.message.delete()
        close_btn.callback = close_callback
        view.add_item(close_btn)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)


class NekoKitsuneGalleryView(ui.View):
    """Gallery view for neko/kitsune images with artist credits"""
    
    def __init__(self, images: List[Dict], image_type: str, ctx, timeout: int = 180):
        super().__init__(timeout=timeout)
        self.images = images
        self.image_type = image_type
        self.ctx = ctx
        self.current_page = 0
    
    async def show_page(self, interaction: discord.Interaction):
        """Display current image with artist info"""
        if not self.images:
            return await interaction.response.send_message("❌ No images available", ephemeral=True)
        
        img = self.images[self.current_page]
        
        emoji = "🐱" if self.image_type == "neko" else "🦊"
        title = f"{emoji} {self.image_type.title()} Gallery"
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.from_rgb(255, 182, 193),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url=img["url"])
        
        # Artist and source info
        artist = img.get("artist", "Unknown")
        source = img.get("source", "")
        site = img.get("site", "Unknown")
        score = img.get("score", 0)
        
        footer_text = f"Artist: {artist} • Source: {site}"
        if score > 0:
            footer_text += f" • Score: {score}"
        footer_text += f" • Page {self.current_page + 1}/{len(self.images)}"
        
        embed.set_footer(text=footer_text)
        
        # Add source link if available
        view = ui.View(timeout=180)
        
        if source and source.startswith("http"):
            view.add_item(ui.Button(label="Source", style=discord.ButtonStyle.link, url=source))
        
        # Navigation buttons
        prev_btn = ui.Button(emoji="⬅️", style=discord.ButtonStyle.gray, disabled=self.current_page == 0)
        async def prev_callback(inter: discord.Interaction):
            if inter.user != self.ctx.author:
                return await inter.response.send_message("This isn't your gallery!", ephemeral=True)
            self.current_page = max(0, self.current_page - 1)
            await self.show_page(inter)
        prev_btn.callback = prev_callback
        view.add_item(prev_btn)
        
        next_btn = ui.Button(emoji="➡️", style=discord.ButtonStyle.gray, disabled=self.current_page >= len(self.images) - 1)
        async def next_callback(inter: discord.Interaction):
            if inter.user != self.ctx.author:
                return await inter.response.send_message("This isn't your gallery!", ephemeral=True)
            self.current_page = min(len(self.images) - 1, self.current_page + 1)
            await self.show_page(inter)
        next_btn.callback = next_callback
        view.add_item(next_btn)
        
        # Random button
        random_btn = ui.Button(label="🎲 Random", style=discord.ButtonStyle.primary)
        async def random_callback(inter: discord.Interaction):
            if inter.user != self.ctx.author:
                return await inter.response.send_message("This isn't your gallery!", ephemeral=True)
            self.current_page = random.randint(0, len(self.images) - 1)
            await self.show_page(inter)
        random_btn.callback = random_callback
        view.add_item(random_btn)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.edit_message(embed=embed, view=view)
