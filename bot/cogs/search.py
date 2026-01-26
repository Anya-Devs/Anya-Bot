# Search & API Commands
# Commands: search, google, youtube, video, art, translate, weather, define, urban, wiki, image
from imports.discord_imports import *
from datetime import datetime, timezone
from typing import Optional, Literal, Set
from io import BytesIO
from bot.utils.cogs.search import *

from bot.utils.cogs.art import ART_SOURCES, ArtAggregator
from data.local.const import primary_color
import re



class Search(commands.Cog):
    """🔍 Search & Lookup - Search the web, translate, get weather, and more"""
    
    def __init__(self, bot):
        self.bot = bot
        self.translator = TranslationAPI()
        self.dictionary = DictionaryAPI()
        self.art_gallery = ArtGalleryAPI()
        self.urban = UrbanDictionaryAPI()
        
        # Processing gateway - Track active command executions per user
        self.active_art_searches = {}  # {user_id: timestamp}
        self.processing_lock = set()  # Set of user_ids currently processing
        
        # Art command access control
        self.art_commands_public = True  # Public access enabled with proper TOS filtering
    
    async def cog_load(self):
        """Initialize session on load"""
        import aiohttp
        self.session = aiohttp.ClientSession()
    
    def cog_unload(self):
        """Cleanup sessions on unload"""
        import asyncio
        for api in [self.google, self.youtube, self.translator, 
                    self.dictionary, self.art_gallery, self.urban]:
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
    
    async def check_art_access(self, ctx) -> bool:
        """Check if user has access to art commands based on public setting"""
        if self.art_commands_public:
            return True  # Commands are public, everyone can access
        
        # Commands are restricted to owner only
        if not await self.bot.is_owner(ctx.author):
            embed = discord.Embed(
                title="⚠️ Safety Hazard - Command Restricted",
                description=f"{ctx.author.mention}, this command is currently restricted to the bot developer only.\n\n"
                           "**Reason:** This command is not fully filtered yet and may return inappropriate content that violates Discord's Terms of Service.\n\n"
                           "The art search system is still under development to ensure maximum safety for all users. "
                           "Once the filtering system is fully tested and verified, this command will be available to everyone.\n\n"
                           "Thank you for your understanding! 🛡️",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Bot Developer Only • Safety First")
            try:
                embed.set_thumbnail(url=ctx.author.display_avatar.url)
            except:
                pass
            await ctx.reply(embed=embed, mention_author=False)
            return False
        
        return True  # Owner access granted



    
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
        # ═══ ACCESS CHECK ═══
        if not await self.check_art_access(ctx):
            return
        
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
                
                # Fetch initial results with EXTREME loading (get maximum results)
                # Adjust search depth based on potential video interest
                video_keywords = ['video', 'mp4', 'webm', 'gifv', 'animation', 'animated', 'gif', 'motion', 'moving', 'clip', 'movie']
                is_video_search = any(keyword in query.lower() for keyword in video_keywords)
                
                if is_video_search:
                    # For video-related searches, go extremely deep
                    max_pages = 200
                    limit = 3000
                else:
                    # Standard extreme search
                    max_pages = 100
                    limit = 2000
                
                results = await self.art_aggregator.search_all(
                    query, 
                    limit=limit,
                    nsfw=is_nsfw,
                    aggressive_load=True,
                    max_pages_per_source=max_pages
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
    # ═══════════════════════════════════════════════════════════════
    # OWNER-ONLY SETTINGS
    # ═══════════════════════════════════════════════════════════════
    @art_search.command(name="access", hidden=True)
    @commands.is_owner()
    async def toggle_art_access(self, ctx, status: str = None):
        """🔧 Toggle art commands public access (Owner only)
        
        Usage: .artaccess <on|off|status>
        """
        if not status:
            # Show current status
            status_text = "🔓 **PUBLIC** - Everyone can use art commands" if self.art_commands_public else "🔒 **PRIVATE** - Owner only"
            embed = discord.Embed(
                title="🎨 Art Commands Access Status",
                description=status_text,
                color=discord.Color.green() if self.art_commands_public else discord.Color.orange()
            )
            embed.add_field(
                name="To change access:",
                value=f"`{ctx.prefix}artaccess on` - Make commands public\n"
                      f"`{ctx.prefix}artaccess off` - Restrict to owner only",
                inline=False
            )
            return await ctx.reply(embed=embed, mention_author=False)
        
        status_lower = status.lower()
        if status_lower in ["on", "public", "enable", "true"]:
            self.art_commands_public = True
            embed = discord.Embed(
                title="✅ Art Commands Now Public",
                description="🎨 All art commands are now available to everyone!",
                color=discord.Color.green()
            )
            embed.set_footer(text="Use .artaccess status to check current setting")
            await ctx.reply(embed=embed, mention_author=False)
            
        elif status_lower in ["off", "private", "disable", "false"]:
            self.art_commands_public = False
            embed = discord.Embed(
                title="🔒 Art Commands Now Private",
                description="🎨 Art commands are restricted to bot owner only.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Use .artaccess status to check current setting")
            await ctx.reply(embed=embed, mention_author=False)
            
        elif status_lower in ["status", "check", "current"]:
            status_text = "🔓 **PUBLIC** - Everyone can use art commands" if self.art_commands_public else "🔒 **PRIVATE** - Owner only"
            embed = discord.Embed(
                title="🎨 Art Commands Access Status",
                description=status_text,
                color=discord.Color.green() if self.art_commands_public else discord.Color.orange()
            )
            await ctx.reply(embed=embed, mention_author=False)
            
        else:
            embed = discord.Embed(
                title="❌ Invalid Option",
                description=f"**Usage:** `{ctx.prefix}artaccess <on|off|status>`\n\n"
                           "**Options:**\n"
                           "• `on` - Make commands public\n"
                           "• `off` - Restrict to owner only\n"
                           "• `status` - Show current setting",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, mention_author=False)


    @art_search.command(name="source", aliases=["src"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def art_source(self, ctx, source: str, *, query: str):
        """Search a specific art source
        
        Available sources: danbooru, gelbooru, safebooru, konachan, yandere, 
        zerochan, anime_pictures, waifu_im, nekos_best, rule34, e621, realbooru
        """
        # ═══ ACCESS CHECK ═══
        if not await self.check_art_access(ctx):
            return
        
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
        # ═══ ACCESS CHECK ═══
        if not await self.check_art_access(ctx):
            return
        
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
        # ═══ ACCESS CHECK ═══
        if not await self.check_art_access(ctx):
            return
        
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
        # ═══ ACCESS CHECK ═══
        if not await self.check_art_access(ctx):
            return
        
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
    
   
    
async def setup(bot):
    await bot.add_cog(Search(bot))
