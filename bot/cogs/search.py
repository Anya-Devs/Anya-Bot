# Search & API Commands
# Commands: search, google, youtube, video, art, translate, weather, define, urban, wiki, image
from imports.discord_imports import *
from datetime import datetime, timezone
from typing import Optional, Literal
from utils.cogs.search import (
    GoogleSearch, YouTubeSearch, TranslationAPI, WeatherAPI,
    DictionaryAPI, WikipediaAPI, ArtGalleryAPI, UrbanDictionaryAPI,
    SearchViews
)
from data.local.const import primary_color


class ArtView(discord.ui.View):
    """Interactive view for art search results with save functionality"""
    
    def __init__(self, results, author, query, is_nsfw, ctx):
        super().__init__(timeout=180)
        self.results = results
        self.author = author
        self.query = query
        self.is_nsfw = is_nsfw
        self.ctx = ctx
        self.page = 0
        self.max_page = len(results) - 1
        
        self._update_buttons()
    
    def _update_buttons(self):
        self.clear_items()
        
        # Navigation buttons
        if self.page > 0:
            self.add_item(PreviousButton())
        if self.page < self.max_page:
            self.add_item(NextButton())
        
        # Save button
        self.add_item(SaveArtButton())
        
        # Source filter button (if NSFW)
        if self.is_nsfw:
            self.add_item(SourceButton())
    
    def build_embed(self):
        if not self.results:
            return discord.Embed(
                title="🎨 No Results",
                description="No artwork found",
                color=discord.Color.red()
            )
        
        art = self.results[self.page]
        
        embed = discord.Embed(
            title=f"🎨 {self.query}",
            color=discord.Color.from_rgb(255, 105, 180) if self.is_nsfw else primary_color()
        )
        
        # NSFW indicator
        if self.is_nsfw and art.get("rating") in ["e", "q", "explicit", "questionable"]:
            embed.description = "🔞 **NSFW Content**"
        
        # Art info
        embed.add_field(name="Source", value=art.get("source", "Unknown"), inline=True)
        embed.add_field(name="Artist", value=art.get("artist", "Unknown"), inline=True)
        embed.add_field(name="Score", value=f"⭐ {art.get('score', 0)}", inline=True)
        
        # Tags
        tags = art.get("tags", [])[:15]
        if tags:
            tag_str = ", ".join([f"`{tag}`" for tag in tags])
            embed.add_field(name="Tags", value=tag_str[:1024], inline=False)
        
        # Art ID for saving
        art_id = f"{art.get('source', 'unknown').lower()}_{art.get('id', 'unknown')}"
        embed.add_field(
            name="Save this art",
            value=f"Use: `.art save {art_id}` or click the button below",
            inline=False
        )
        
        # Image
        embed.set_image(url=art.get("url"))
        
        # Footer
        embed.set_footer(text=f"Page {self.page + 1}/{self.max_page + 1} • {art.get('page_url', '')}")
        
        return embed


class PreviousButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="◀ Previous", custom_id="art_prev")
    
    async def callback(self, interaction: discord.Interaction):
        view: ArtView = self.view
        if interaction.user != view.author:
            return await interaction.response.send_message("This is not your search.", ephemeral=True)
        
        view.page = max(0, view.page - 1)
        view._update_buttons()
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.primary, label="Next ▶", custom_id="art_next")
    
    async def callback(self, interaction: discord.Interaction):
        view: ArtView = self.view
        if interaction.user != view.author:
            return await interaction.response.send_message("This is not your search.", ephemeral=True)
        
        view.page = min(view.max_page, view.page + 1)
        view._update_buttons()
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class SaveArtButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.success, label="💾 Save to Favorites", custom_id="art_save")
    
    async def callback(self, interaction: discord.Interaction):
        view: ArtView = self.view
        if interaction.user != view.author:
            return await interaction.response.send_message("This is not your search.", ephemeral=True)
        
        art = view.results[view.page]
        art_id = f"{art.get('source', 'unknown').lower()}_{art.get('id', 'unknown')}"
        
        # Create modal for folder selection
        modal = SaveArtModal(art_id, art)
        await interaction.response.send_modal(modal)


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
                description=f"Saved to folder: **{folder_name}**\n"
                           f"Art ID: `{self.art_id}`",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=self.art_data.get("url"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to save: {e}", ephemeral=True)


class SourceButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.secondary, label="🔍 Filter by Source", custom_id="art_source")
    
    async def callback(self, interaction: discord.Interaction):
        view: ArtView = self.view
        if interaction.user != view.author:
            return await interaction.response.send_message("This is not your search.", ephemeral=True)
        
        # Show source info
        sources_count = {}
        for art in view.results:
            source = art.get("source", "Unknown")
            sources_count[source] = sources_count.get(source, 0) + 1
        
        embed = discord.Embed(
            title="📊 Results by Source",
            color=primary_color()
        )
        
        for source, count in sorted(sources_count.items(), key=lambda x: x[1], reverse=True):
            embed.add_field(name=source, value=f"{count} results", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


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

    # ═══════════════════════════════════════════════════════════════
    # GOOGLE SEARCH
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="google", aliases=["g"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def google_search(self, ctx, *, query: str):
        """🔍 Search Google"""
        async with ctx.typing():
            results = await self.google.search(query, num=5)
        
        if not results:
            embed = discord.Embed(
                title="🔍 Google Search",
                description=f"No results found for **{query}**\n\n"
                           f"*Note: Google API key may not be configured.*",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        embed = discord.Embed(
            title=f"🔍 Google: {query[:50]}",
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        for i, result in enumerate(results[:5], 1):
            title = result.get("title", "No Title")[:60]
            link = result.get("link", "")
            snippet = result.get("snippet", "No description")[:100]
            
            embed.add_field(
                name=f"{i}. {title}",
                value=f"{snippet}...\n[Link]({link})",
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # IMAGE SEARCH
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="image", aliases=["img", "images"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def image_search(self, ctx, *, query: str):
        """🖼️ Search for images"""
        async with ctx.typing():
            results = await self.google.image_search(query, num=5)
        
        if not results:
            embed = discord.Embed(
                title="🖼️ Image Search",
                description=f"No images found for **{query}**",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Show first image with navigation
        embed = discord.Embed(
            title=f"🖼️ Images: {query[:50]}",
            color=primary_color()
        )
        
        first_result = results[0]
        if first_result.get("link"):
            embed.set_image(url=first_result.get("link"))
        
        embed.set_footer(text=f"Result 1/{len(results)} • Requested by {ctx.author}")
        await ctx.reply(embed=embed, mention_author=False)

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
                title="📺 YouTube Search",
                description=f"No videos found for **{query}**",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        view = SearchViews.VideoSearchView(results, ctx.author, f"YouTube: {query[:30]}")
        embed = view.build_embed()
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # ART SEARCH - Multiple sources with NSFW support and favorites
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="art", aliases=["artwork"], invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def art_search(self, ctx, *, query: str = None):
        """🎨 Search anime/manga art from multiple sources
        
        Supports: Danbooru, Gelbooru, Safebooru, Konachan, Yande.re
        Use in NSFW channels for adult content access
        """
        if not query:
            embed = discord.Embed(
                title="🎨 Art Search",
                description="Search anime and manga art from multiple sources!",
                color=primary_color()
            )
            embed.add_field(
                name="Usage",
                value=f"`{ctx.prefix}art <search query>`\n"
                      f"`{ctx.prefix}art source <source> <query>`\n"
                      f"`{ctx.prefix}art save <art_id>` - Save to favorites\n"
                      f"`{ctx.prefix}art folder create <name>`\n"
                      f"`{ctx.prefix}art favorites` - View saved art",
                inline=False
            )
            embed.add_field(
                name="Sources",
                value="Danbooru, Gelbooru, Safebooru, Konachan, Yande.re, Rule34 (NSFW only)",
                inline=False
            )
            embed.add_field(
                name="NSFW Mode",
                value="🔞 Use in NSFW channels to access adult content",
                inline=False
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        # Check if in NSFW channel
        is_nsfw = False
        if isinstance(ctx.channel, discord.TextChannel):
            is_nsfw = ctx.channel.is_nsfw()
        
        async with ctx.typing():
            from utils.cogs.art import ArtAggregator
            if not hasattr(self, 'art_aggregator'):
                self.art_aggregator = ArtAggregator(self.session)
            
            results = await self.art_aggregator.search_all(query, limit=20, nsfw=is_nsfw)
        
        if not results:
            embed = discord.Embed(
                title="🎨 Art Search",
                description=f"No artwork found for **{query}**",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        view = ArtView(results, ctx.author, query, is_nsfw, ctx)
        embed = view.build_embed()
        await ctx.reply(embed=embed, view=view, mention_author=False)
    
    @art_search.command(name="source")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def art_source(self, ctx, source: str, *, query: str):
        """Search a specific art source"""
        is_nsfw = False
        if isinstance(ctx.channel, discord.TextChannel):
            is_nsfw = ctx.channel.is_nsfw()
        
        from utils.cogs.art import ArtAggregator
        if not hasattr(self, 'art_aggregator'):
            self.art_aggregator = ArtAggregator(self.session)
        
        async with ctx.typing():
            results = await self.art_aggregator.search_source(source, query, limit=20, nsfw=is_nsfw)
        
        if not results:
            embed = discord.Embed(
                title=f"🎨 {source.title()} Search",
                description=f"No artwork found for **{query}**",
                color=discord.Color.orange()
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        view = ArtView(results, ctx.author, f"{source}: {query}", is_nsfw, ctx)
        embed = view.build_embed()
        await ctx.reply(embed=embed, view=view, mention_author=False)
    
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
                title="✅ Art Saved",
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
                title="📁 Art Folders",
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
                    title="✅ Folder Created",
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
                    title="📁 Your Art Folders",
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
                    title="🖼️ Favorites",
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
                    title=f"📁 {folder}",
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
                    title="🖼️ Your Favorites",
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
                title="❌ Translation Failed",
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
            title="🔍 Language Detection",
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
                title="🌤️ Weather",
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
                title="🎨 Color Toolkit",
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
                name="🎭 Get Colors From",
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
            title=f"🎨 {color_name}",
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
        """🎭 Get color info from a role."""
        r, g, b = role.color.r, role.color.g, role.color.b
        
        if r == 0 and g == 0 and b == 0:
            return await ctx.reply(f"❌ {role.mention} has no color set (default)", mention_author=False)
        
        embed = discord.Embed(
            title=f"🎭 {role.name}'s Color",
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
        """👤 Get color from a user's top role."""
        member = member or ctx.author
        
        # Get top colored role
        colored_role = None
        for role in reversed(member.roles):
            if role.color.value != 0:
                colored_role = role
                break
        
        if not colored_role:
            return await ctx.reply(f"❌ {member.display_name} has no colored roles!", mention_author=False)
        
        r, g, b = colored_role.color.r, colored_role.color.g, colored_role.color.b
        hex_color = self._rgb_to_hex(r, g, b)
        
        embed = discord.Embed(
            title=f"👤 {member.display_name}'s Color",
            description=f"From role: {colored_role.mention}",
            color=colored_role.color
        )
        
        embed.add_field(name="Hex", value=f"`#{hex_color}`", inline=True)
        embed.add_field(name="RGB", value=f"`rgb({r}, {g}, {b})`", inline=True)
        embed.set_thumbnail(url=f"https://singlecolorimage.com/get/{hex_color}/100x100")
        
        await ctx.reply(embed=embed, mention_author=False)
    
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
        
        embed = discord.Embed(
            title=f"🎨 Color Palette for #{color}",
            color=discord.Color.from_rgb(r, g, b)
        )
        
        # Complementary
        embed.add_field(
            name="🔄 Complementary",
            value=f"`#{self._rgb_to_hex(*comp)}`",
            inline=True
        )
        
        # Analogous
        embed.add_field(
            name="↔️ Analogous",
            value="\n".join([f"`#{self._rgb_to_hex(*c)}`" for c in analogous]),
            inline=True
        )
        
        # Triadic
        embed.add_field(
            name="🔺 Triadic",
            value="\n".join([f"`#{self._rgb_to_hex(*c)}`" for c in triadic]),
            inline=True
        )
        
        # Shades & Tints
        embed.add_field(
            name="🌑 Shades (Darker)",
            value=" ".join([f"`#{self._rgb_to_hex(*c)}`" for c in shades]),
            inline=True
        )
        
        embed.add_field(
            name="☀️ Tints (Lighter)",
            value=" ".join([f"`#{self._rgb_to_hex(*c)}`" for c in tints]),
            inline=True
        )
        
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        # Create palette image URL
        palette_colors = [color, self._rgb_to_hex(*comp), self._rgb_to_hex(*analogous[0]), 
                         self._rgb_to_hex(*triadic[0]), self._rgb_to_hex(*shades[0])]
        embed.set_image(url=f"https://via.placeholder.com/500x60/{color}/{color}?text=+")
        
        embed.set_footer(text="💡 Click the colors to copy them!")
        await ctx.reply(embed=embed, mention_author=False)
    
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
        
        embed.add_field(
            name="📝 WCAG AA",
            value=f"Normal Text: {aa_normal}\nLarge Text: {aa_large}",
            inline=True
        )
        embed.add_field(
            name="🏅 WCAG AAA",
            value=f"Normal Text: {aaa_normal}\nLarge Text: {aaa_large}",
            inline=True
        )
        
        embed.set_footer(text="AA: Min 4.5:1 normal, 3:1 large | AAA: 7:1 normal, 4.5:1 large")
        await ctx.reply(embed=embed, mention_author=False)
    
    @color_group.command(name="preview", aliases=["demo", "show"])
    async def color_preview(self, ctx, color: str):
        """👁️ Preview how a color looks on common UI elements."""
        color = color.strip("#").upper()
        if len(color) == 3:
            color = "".join([c*2 for c in color])
        
        if len(color) != 6 or not all(c in "0123456789ABCDEF" for c in color):
            return await ctx.reply("❌ Invalid hex color!", mention_author=False)
        
        r, g, b = self._hex_to_rgb(color)
        
        # Determine best text color
        white_contrast = self._get_contrast_ratio((r, g, b), (255, 255, 255))
        black_contrast = self._get_contrast_ratio((r, g, b), (0, 0, 0))
        text_color = "FFFFFF" if white_contrast > black_contrast else "000000"
        
        embed = discord.Embed(
            title=f"👁️ Color Preview: #{color}",
            description=f"See how `#{color}` looks in different contexts!",
            color=discord.Color.from_rgb(r, g, b)
        )
        
        embed.add_field(
            name="💬 As Embed Color",
            value="← This embed uses your color!",
            inline=False
        )
        
        embed.add_field(
            name="📋 Copy-Paste Codes",
            value=f"**CSS:** `background-color: #{color};`\n"
                  f"**Tailwind:** `bg-[#{color}]`\n"
                  f"**Discord:** `color=discord.Color.from_rgb({r}, {g}, {b})`",
            inline=False
        )
        
        embed.add_field(
            name="🎨 Best Text Color",
            value=f"Use **{'White' if text_color == 'FFFFFF' else 'Black'}** text\n"
                  f"Contrast ratio: `{max(white_contrast, black_contrast):.1f}:1`",
            inline=True
        )
        
        embed.add_field(
            name="🔗 Color Name",
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
                title="🖼️ Image Color Extraction",
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
                    title="🖼️ Extracted Colors",
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
            return await ctx.reply("❌ Text too long! Max 500 characters.", mention_author=False)
        
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
