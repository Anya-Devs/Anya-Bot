# Anime & Manga Commands
# Commands: anime, manga, waifu, husbando, quote, schedule, wallpaper, gif, neko, smug, cuddle
import asyncio, aiohttp, logging, random
from datetime import datetime, timezone
from typing import Optional, Literal
from imports.discord_imports import *
from bot.utils.cogs.anime import *
from data.local.const import primary_color


class Anime(commands.Cog):
    """🎌 Anime & Manga - Search anime, manga, get waifus, quotes, and more"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.jikan.moe/v4/"
        self.mangadex_url = "https://api.mangadex.org"
        self.waifu_api = "https://api.waifu.pics"
        self.nekos_api = "https://nekos.best/api/v2"
        self.red = discord.Color.red()
        self.ar = Anime_Recommendation(bot)
        self.mr = Manga_Recommendation(bot)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self.session
    
    def cog_unload(self):
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())

    async def prompt_query(self, ctx, item):
        prompt = f"{ctx.author.display_name.title()}, enter the `name` of the {item} you're looking for."
        embed = discord.Embed(description=prompt)
        if item == "anime":
            embed.set_footer(text=f"Try {ctx.prefix}anime recommend for a random anime")
        message = await ctx.reply(embed=embed, mention_author=False)

        def check(m): return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for("message", timeout=60, check=check)
            await message.delete()
            if not msg.content.strip():
                raise ValueError(f"{item.title()} name cannot be empty")
            query = msg.content.strip()
            await msg.delete()
            return query
        except asyncio.TimeoutError:
            await message.edit(embed=discord.Embed(description=f"Time's Up! No {item} title provided.", color=self.red))
        except ValueError as e:
            await message.edit(embed=discord.Embed(description=f"Error: {e}", color=self.red))
        return None

    async def fetch_and_send(self, ctx, url, query, view_cls):
     try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as r:
                r.raise_for_status()
                data = await r.json()

        if not data.get("data"):
            await ctx.reply(f"No results found for '{query}'.")
            return

        # Instantiate view depending on type
        if view_cls == CharacterView:
            view = view_cls(character_data=data)
            embed = await view.update_embed()
            await ctx.reply(embed=embed, view=view, mention_author=False)
        elif view_cls == AnimeView:
            view = view_cls(anime_data=data)
            embed = await view.update_embed()
            await ctx.reply(embed=embed, view=view, mention_author=False)
        elif view_cls == MangaView:
            view = view_cls(manga_data=data)
            embed = await view.update_embed()
            await ctx.reply(embed=embed, view=view, mention_author=False)
        else:
            # Fallback for unknown views
            embed = discord.Embed(
                title=f"Search Results for: {query}",
                color=primary_color(),
                description="No interactive view available."
            )
            await ctx.reply(embed=embed)

     except aiohttp.ClientError as e:
        logging.error(f"HTTP error: {e}")
        await ctx.send(f"HTTP error occurred: {e}")
     except Exception as e:
        logging.error(f"Unexpected error: {e}")
        await ctx.send(f"Unexpected error occurred: {e}")

    @commands.group(name="anime", invoke_without_command=True)
    async def anime_group(self, ctx):
        await ctx.send("Use a subcommand: `search`, `recommend`, or `character`.")
    
    

    @anime_group.command(name="search")
    async def anime_search(self, ctx, *, query: Optional[str] = None):
        query = query or await self.prompt_query(ctx, "anime")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}anime?q={query}", query, AnimeView)

   
    @anime_group.command(name="character")
    async def anime_character(self, ctx, *, query=None):
        query = query or await self.prompt_query(ctx, "character")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}characters?q={query}", query, CharacterView)
    
    @anime_group.command(name="recommend")
    async def anime_recommend(self, ctx):
        d = await self.ar.fetch_random_anime()
        m = await ctx.reply(embed=discord.Embed(description=f'{neko_lurk} Fetching anime...', color=primary_color()), mention_author=False)
        await self.ar.update_anime_embed(m, d)


    # Manga commands
    @commands.group(name="manga")
    async def manga_group(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use a subcommand: `search`, `read`, or `recommend`.")

    @manga_group.command(name="search")
    async def manga_search(self, ctx, *, query=None):
        query = query or await self.prompt_query(ctx, "manga")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}manga?q={query}", query, MangaView)

    @manga_group.command(name="read")
    async def manga_read(self, ctx, *, query=None):
        query = query or await self.prompt_query(ctx, "manga")
        if not query:
            return await ctx.send("❌ No query provided.")

        async with aiohttp.ClientSession() as session:
            url = f"{self.mangadex_url}/manga?title={query}&limit=25"
            async with session.get(url) as resp:
                data = await resp.json()

        if not data.get("data"):
            return await ctx.send(f"❌ No manga found for `{query}`.")

        view = MangaSession(ctx, data)
        embed = discord.Embed(
            title=f"📚 Search results for `{query}`",
            description="Select a manga from the dropdown below.",
            color=primary_color()
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @manga_group.command(name="recommend")
    async def manga_recommend(self, ctx):
        d = await self.mr.fetch_random_manga()
        m = await ctx.reply(embed=discord.Embed(description=f'{neko_lurk} Fetching manga...', color=primary_color()), mention_author=False)
        await self.mr.update_manga_embed(m, d)


    # ═══════════════════════════════════════════════════════════════
    # WAIFU / HUSBANDO COMMANDS (Enhanced)
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="waifu")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def waifu(self, ctx, *, query: str = None):
        """💕 Search for waifu characters with detailed info and image gallery
        
        Usage:
        - `.waifu` - Random waifu image
        - `.waifu Asuna` - Search for specific character
        - `.waifu Rem Re:Zero` - Search with anime name
        """
        from bot.utils.cogs.anime_enhanced import CharacterInfo, CharacterSelectView
        
        if not query:
            # Random waifu image (fallback to simple mode)
            session = await self.get_session()
            try:
                async with session.get(f"{self.waifu_api}/sfw/waifu") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        url = data.get("url", "")
                        
                        embed = discord.Embed(
                            title="💕 Random Waifu",
                            description="Use `.waifu <name>` to search for specific characters!",
                            color=discord.Color.from_rgb(255, 182, 193),
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.set_image(url=url)
                        embed.set_footer(text=f"Requested by {ctx.author}")
                        
                        return await ctx.reply(embed=embed, mention_author=False)
            except Exception as e:
                logging.error(f"Waifu API error: {e}")
                return await ctx.reply("❌ Could not fetch waifu image", mention_author=False)
        
        # Character search mode
        async with ctx.typing():
            char_info = CharacterInfo()
            characters = await char_info.search_characters(query, limit=25)
            
            if not characters:
                return await ctx.reply(f"❌ No characters found for `{query}`", mention_author=False)
            
            # Filter for female characters
            female_chars = [c for c in characters if "Female" in str(c.get("name_kanji", "")) or 
                           any("female" in str(a.get("role", "")).lower() for a in c.get("anime", []))]
            
            if not female_chars:
                female_chars = characters  # Fallback to all results
            
            # Show character selection
            embed = discord.Embed(
                title=f"💕 Waifu Search Results for '{query}'",
                description="Select a character from the dropdown to view detailed information, anime appearances, and image gallery!",
                color=discord.Color.from_rgb(255, 182, 193)
            )
            embed.set_footer(text=f"Found {len(female_chars)} character(s)")
            
            view = CharacterSelectView(female_chars, ctx)
            await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="husbando")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def husbando(self, ctx, *, query: str = None):
        """💙 Search for husbando characters with detailed info and image gallery
        
        Usage:
        - `.husbando` - Random husbando image
        - `.husbando Kirito` - Search for specific character
        - `.husbando Levi Attack on Titan` - Search with anime name
        """
        from bot.utils.cogs.anime_enhanced import CharacterInfo, CharacterSelectView
        
        if not query:
            # Random husbando image (fallback to simple mode)
            session = await self.get_session()
            try:
                async with session.get(f"{self.nekos_api}/husbando") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            url = results[0].get("url", "")
                            artist = results[0].get("artist_name", "Unknown")
                            
                            embed = discord.Embed(
                                title="💙 Random Husbando",
                                description="Use `.husbando <name>` to search for specific characters!",
                                color=discord.Color.blue(),
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.set_image(url=url)
                            embed.set_footer(text=f"Artist: {artist} • Requested by {ctx.author}")
                            
                            return await ctx.reply(embed=embed, mention_author=False)
            except Exception as e:
                logging.error(f"Husbando API error: {e}")
                return await ctx.reply("❌ Could not fetch husbando image", mention_author=False)
        
        # Character search mode
        async with ctx.typing():
            char_info = CharacterInfo()
            characters = await char_info.search_characters(query, limit=25)
            
            if not characters:
                return await ctx.reply(f"❌ No characters found for `{query}`", mention_author=False)
            
            # Filter for male characters
            male_chars = [c for c in characters if "Male" in str(c.get("name_kanji", "")) or 
                         any("male" in str(a.get("role", "")).lower() for a in c.get("anime", []))]
            
            if not male_chars:
                male_chars = characters  # Fallback to all results
            
            # Show character selection
            embed = discord.Embed(
                title=f"💙 Husbando Search Results for '{query}'",
                description="Select a character from the dropdown to view detailed information, anime appearances, and image gallery!",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Found {len(male_chars)} character(s)")
            
            view = CharacterSelectView(male_chars, ctx)
            await ctx.reply(embed=embed, view=view, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # ANIME REACTION GIFS
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="neko")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def neko(self, ctx):
        """🐱 Get neko/catgirl images with artist credits and gallery
        
        Features high-quality SFW images from multiple sources with artist attribution.
        Use the navigation buttons to browse through multiple images!
        """
        from bot.utils.cogs.anime_enhanced import ImageSource, NekoKitsuneGalleryView
        
        loading_msg = await ctx.reply("🐱 Fetching neko images from multiple sources...", mention_author=False)
        
        try:
            img_source = ImageSource()
            images = await img_source.fetch_neko_images(limit=20)
            
            if not images:
                return await loading_msg.edit(content="❌ Could not fetch neko images")
            
            # Create gallery view and show first image
            view = NekoKitsuneGalleryView(images, "neko", ctx)
            
            # Build first image embed
            img = images[0]
            embed = discord.Embed(
                title="🐱 Neko Gallery",
                color=discord.Color.from_rgb(255, 182, 193),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_image(url=img["url"])
            
            artist = img.get("artist", "Unknown")
            source = img.get("source", "")
            site = img.get("site", "Unknown")
            score = img.get("score", 0)
            
            footer_text = f"Artist: {artist} • Source: {site}"
            if score > 0:
                footer_text += f" • Score: {score}"
            footer_text += f" • Image 1/{len(images)}"
            embed.set_footer(text=footer_text)
            
            await loading_msg.edit(content=None, embed=embed, view=view)
        except Exception as e:
            logging.error(f"Neko command error: {e}")
            await loading_msg.edit(content="❌ Error fetching neko images")

    @commands.command(name="kitsune")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def anime_kitsune(self, ctx):
        """🦊 Get kitsune/foxgirl images with artist credits and gallery
        
        Features high-quality SFW images from multiple sources with artist attribution.
        Use the navigation buttons to browse through multiple images!
        """
        from bot.utils.cogs.anime_enhanced import ImageSource, NekoKitsuneGalleryView
        
        loading_msg = await ctx.reply("🦊 Fetching kitsune images from multiple sources...", mention_author=False)
        
        try:
            img_source = ImageSource()
            images = await img_source.fetch_kitsune_images(limit=20)
            
            if not images:
                return await loading_msg.edit(content="❌ Could not fetch kitsune images")
            
            # Create gallery view and show first image
            view = NekoKitsuneGalleryView(images, "kitsune", ctx)
            
            # Build first image embed
            img = images[0]
            embed = discord.Embed(
                title="🦊 Kitsune Gallery",
                color=discord.Color.from_rgb(255, 182, 193),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_image(url=img["url"])
            
            artist = img.get("artist", "Unknown")
            source = img.get("source", "")
            site = img.get("site", "Unknown")
            score = img.get("score", 0)
            
            footer_text = f"Artist: {artist} • Source: {site}"
            if score > 0:
                footer_text += f" • Score: {score}"
            footer_text += f" • Image 1/{len(images)}"
            embed.set_footer(text=footer_text)
            
            await loading_msg.edit(content=None, embed=embed, view=view)
        except Exception as e:
            logging.error(f"Kitsune command error: {e}")
            await loading_msg.edit(content="❌ Error fetching kitsune images")

    @anime_group.command(name="smug")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def anime_smug(self, ctx):
        """😏 Get a smug anime reaction"""
        await self._send_waifu_gif(ctx, "smug", "😏 Smug")

    @anime_group.command(name="cry")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def anime_cry(self, ctx):
        """😢 Get a crying anime reaction"""
        await self._send_waifu_gif(ctx, "cry", "T w T Cry")

    @anime_group.command(name="blush")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def anime_blush(self, ctx):
        """😊 Get a blushing anime reaction"""
        await self._send_nekos_image(ctx, "blush", ">///< Blush")

    @anime_group.command(name="happy")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def anime_happy(self, ctx):
        """😄 Get a happy anime reaction"""
        await self._send_waifu_gif(ctx, "happy", "^w^ Happy")

    @anime_group.command(name="dance")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def anime_dance(self, ctx):
        """💃 Get a dancing anime reaction"""
        await self._send_waifu_gif(ctx, "dance", "💃 Dance")

    async def _send_waifu_gif(self, ctx, category: str, title: str):
        """Helper to send waifu.pics gifs"""
        session = await self.get_session()
        try:
            async with session.get(f"{self.waifu_api}/sfw/{category}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    url = data.get("url", "")
                    
                    embed = discord.Embed(title=title, color=primary_color())
                    embed.set_image(url=url)
                    embed.set_footer(text=f"Requested by {ctx.author}")
                    
                    return await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            logging.error(f"Waifu API error: {e}")
        
        await ctx.reply(f"❌ Could not fetch {category} gif", mention_author=False)

    async def _send_nekos_image(self, ctx, category: str, title: str):
        """Helper to send nekos.best images"""
        session = await self.get_session()
        try:
            async with session.get(f"{self.nekos_api}/{category}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        url = results[0].get("url", "")
                        artist = results[0].get("artist_name", "Unknown")
                        
                        embed = discord.Embed(title=title, color=primary_color())
                        embed.set_image(url=url)
                        embed.set_footer(text=f"Artist: {artist} • Requested by {ctx.author}")
                        
                        return await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            logging.error(f"Nekos API error: {e}")
        
        await ctx.reply(f"❌ Could not fetch {category} image", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # ANIME QUOTE
    # ═══════════════════════════════════════════════════════════════
    @anime_group.command(name="quote")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anime_quote(self, ctx):
        """💬 Get a random anime quote"""
        session = await self.get_session()
        try:
            async with session.get("https://animechan.io/api/v1/quotes/random") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    quote_data = data.get("data", {})
                    
                    quote = quote_data.get("content", "No quote found")
                    character = quote_data.get("character", {}).get("name", "Unknown")
                    anime = quote_data.get("anime", {}).get("name", "Unknown Anime")
                    
                    embed = discord.Embed(
                        description=f"*\"{quote}\"*",
                        color=primary_color(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed.set_author(name=f"💬 Anime Quote")
                    embed.add_field(name="Character", value=character, inline=True)
                    embed.add_field(name="Anime", value=anime, inline=True)
                    embed.set_footer(text=f"Requested by {ctx.author}")
                    
                    return await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            logging.error(f"Quote API error: {e}")
        
        # Fallback quotes
        fallback_quotes = [
            {"quote": "People's lives don't end when they die. It ends when they lose faith.", "character": "Itachi Uchiha", "anime": "Naruto"},
            {"quote": "The world isn't perfect. But it's there for us, doing the best it can.", "character": "Roy Mustang", "anime": "Fullmetal Alchemist"},
            {"quote": "If you don't take risks, you can't create a future.", "character": "Monkey D. Luffy", "anime": "One Piece"},
            {"quote": "Whatever you lose, you'll find it again. But what you throw away you'll never get back.", "character": "Kenshin Himura", "anime": "Rurouni Kenshin"},
        ]
        q = random.choice(fallback_quotes)
        embed = discord.Embed(
            description=f"*\"{q['quote']}\"*",
            color=primary_color()
        )
        embed.add_field(name="Character", value=q["character"], inline=True)
        embed.add_field(name="Anime", value=q["anime"], inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # ANIME SCHEDULE
    # ═══════════════════════════════════════════════════════════════
    @anime_group.command(name="schedule", aliases=["airing"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def anime_schedule(self, ctx, day: str = None):
        """📅 Get anime airing schedule
        
        Days: monday, tuesday, wednesday, thursday, friday, saturday, sunday
        """
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        if day is None:
            day = days[datetime.now().weekday()]
        elif day.lower() not in days:
            return await ctx.reply(f"❌ Invalid day. Use: {', '.join(days)}", mention_author=False)
        
        day = day.lower()
        
        session = await self.get_session()
        try:
            async with session.get(f"{self.api_url}schedules?filter={day}&limit=15") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    anime_list = data.get("data", [])
                    
                    if not anime_list:
                        return await ctx.reply(f"No anime airing on {day.title()}", mention_author=False)
                    
                    embed = discord.Embed(
                        title=f"Anime Schedule - {day.title()}",
                        color=primary_color(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    
                    for anime in anime_list[:10]:
                        title = anime.get("title", "Unknown")[:40]
                        episodes = anime.get("episodes", "?")
                        score = anime.get("score", "N/A")
                        
                        embed.add_field(
                            name=title,
                            value=f"Episodes: {episodes} | Score: {score}",
                            inline=True
                        )
                    
                    embed.set_footer(text=f"Requested by {ctx.author}")
                    return await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            logging.error(f"Schedule API error: {e}")
        
        await ctx.reply("❌ Could not fetch anime schedule", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # ANIME WALLPAPER
    # ═══════════════════════════════════════════════════════════════
    @anime_group.command(name="wallpaper", aliases=["wall"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anime_wallpaper(self, ctx):
        """🖼️ Get random anime wallpapers"""
        session = await self.get_session()
        try:
            # Use nekos.best wallpaper endpoint
            async with session.get(f"{self.nekos_api}/wallpaper") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        url = results[0].get("url", "")
                        artist = results[0].get("artist_name", "Unknown")
                        
                        embed = discord.Embed(
                            title="🖼️ Anime Wallpaper",
                            color=primary_color(),
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.set_image(url=url)
                        embed.set_footer(text=f"Artist: {artist} • Requested by {ctx.author}")
                        
                        view = discord.ui.View()
                        view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.link, url=url))
                        
                        return await ctx.reply(embed=embed, view=view, mention_author=False)
        except Exception as e:
            logging.error(f"Wallpaper API error: {e}")
        
        await ctx.reply("❌ Could not fetch wallpaper", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # ANIME TRIVIA
    # ═══════════════════════════════════════════════════════════════
    @anime_group.command(name="trivia")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def anime_trivia(self, ctx):
        """🎯 Anime trivia game - Guess the anime from the character"""
        session = await self.get_session()
        
        try:
            # Get a random character
            char_id = random.randint(1, 5000)
            async with session.get(f"{self.api_url}characters/{char_id}/full") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    char_data = data.get("data", {})
                    
                    if not char_data:
                        return await ctx.reply("❌ Could not fetch trivia", mention_author=False)
                    
                    name = char_data.get("name", "Unknown")
                    image = char_data.get("images", {}).get("jpg", {}).get("image_url", "")
                    anime_list = char_data.get("anime", [])
                    
                    if not anime_list:
                        return await ctx.reply("❌ Could not fetch trivia", mention_author=False)
                    
                    correct_anime = anime_list[0].get("anime", {}).get("title", "Unknown")
                    
                    embed = discord.Embed(
                        title="🎯 Anime Trivia",
                        description=f"**Which anime is this character from?**\n\nCharacter: **{name}**",
                        color=primary_color()
                    )
                    embed.set_image(url=image)
                    embed.set_footer(text="Type your answer in chat! (30 seconds)")
                    
                    await ctx.reply(embed=embed, mention_author=False)
                    
                    def check(m):
                        return m.author == ctx.author and m.channel == ctx.channel
                    
                    try:
                        msg = await self.bot.wait_for("message", timeout=30, check=check)
                        
                        if correct_anime.lower() in msg.content.lower() or msg.content.lower() in correct_anime.lower():
                            embed = discord.Embed(
                                title="✅ Correct!",
                                description=f"The anime is **{correct_anime}**!",
                                color=discord.Color.green()
                            )
                        else:
                            embed = discord.Embed(
                                title="❌ Wrong!",
                                description=f"The correct answer was **{correct_anime}**",
                                color=discord.Color.red()
                            )
                        
                        await ctx.reply(embed=embed, mention_author=False)
                    except asyncio.TimeoutError:
                        embed = discord.Embed(
                            title="⏰ Time's Up!",
                            description=f"The correct answer was **{correct_anime}**",
                            color=discord.Color.orange()
                        )
                        await ctx.reply(embed=embed, mention_author=False)
                    return
        except Exception as e:
            logging.error(f"Trivia error: {e}")
        
        await ctx.reply("❌ Could not start trivia", mention_author=False)


async def setup(bot):
    await bot.add_cog(Anime(bot))