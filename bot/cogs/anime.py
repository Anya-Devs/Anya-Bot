# Anime & Manga Commands
import asyncio, aiohttp, logging, random
from datetime import datetime, timezone
from typing import Optional
from imports.discord_imports import *
from bot.utils.cogs.anime import *
from data.local.const import primary_color


class Anime(commands.Cog):
    """🎌 Anime & Manga - Search shows, get waifus, quotes, and more!"""
    
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
        prompt = f"What {item} are you looking for?"
        embed = discord.Embed(description=prompt, color=primary_color())
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
            await message.edit(embed=discord.Embed(description=f"⏰ Timeout - no {item} name provided.", color=self.red))
        except ValueError as e:
            await message.edit(embed=discord.Embed(description=f"❌ {e}", color=self.red))
        return None

    async def fetch_and_send(self, ctx, url, query, view_cls):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as r:
                    r.raise_for_status()
                    data = await r.json()

            if not data.get("data"):
                return await ctx.reply(f"No results found for `{query}` 😕", mention_author=False)

            if view_cls == CharacterView:
                view = view_cls(character_data=data)
            elif view_cls == AnimeView:
                view = view_cls(anime_data=data)
            elif view_cls == MangaView:
                view = view_cls(manga_data=data)
            else:
                return await ctx.reply(f"No results found for `{query}`", mention_author=False)
            
            embed = await view.update_embed()
            await ctx.reply(embed=embed, view=view, mention_author=False)

        except Exception as e:
            logging.error(f"Error: {e}")
            await ctx.send(f"Oops! Something went wrong: {e}")

    # ═══════════════════════════════════════════════════════════════
    # ANIME COMMANDS
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="anime", invoke_without_command=True)
    async def anime_group(self, ctx):
        """Anime commands - search, recommendations, quotes & more"""
        embed = discord.Embed(
            title="Commands",
            description=(
                f"`{ctx.prefix}anime search <name>` - Find an anime\n"
                f"`{ctx.prefix}anime recommend` - Get random anime\n"
                f"`{ctx.prefix}anime character <name>` - Search characters\n"
                f"`{ctx.prefix}anime quote` - Random anime quote\n"
                f"`{ctx.prefix}anime schedule` - Today's airing anime"
            ),
            color=primary_color()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @anime_group.command(name="search")
    async def anime_search(self, ctx, *, query: Optional[str] = None):
        """Search for anime by name"""
        query = query or await self.prompt_query(ctx, "anime")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}anime?q={query}", query, AnimeView)

    @anime_group.command(name="character")
    async def anime_character(self, ctx, *, query=None):
        """Search for anime characters"""
        query = query or await self.prompt_query(ctx, "character")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}characters?q={query}", query, CharacterView)
    
    @anime_group.command(name="recommend")
    async def anime_recommend(self, ctx):
        """Get a random anime recommendation"""
        d = await self.ar.fetch_random_anime()
        m = await ctx.reply(embed=discord.Embed(description=f'🔍 Finding you an anime...', color=primary_color()), mention_author=False)
        await self.ar.update_anime_embed(m, d)

    @anime_group.command(name="quote")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anime_quote(self, ctx):
        """Get a random anime quote"""
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
                        description=f"💬 *\"{quote}\"*",
                        color=primary_color(),
                        timestamp=datetime.now(timezone.utc)
                    )
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
            description=f"💬 *\"{q['quote']}\"*",
            color=primary_color()
        )
        embed.add_field(name="Character", value=q["character"], inline=True)
        embed.add_field(name="Anime", value=q["anime"], inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    @anime_group.command(name="schedule", aliases=["airing"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def anime_schedule(self, ctx, day: str = None):
        """Check what's airing today (or specify a day)"""
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        if day is None:
            day = days[datetime.now().weekday()]
        elif day.lower() not in days:
            return await ctx.reply(f"❌ Use: {', '.join(days)}", mention_author=False)
        
        day = day.lower()
        
        session = await self.get_session()
        try:
            async with session.get(f"{self.api_url}schedules?filter={day}&limit=10") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    anime_list = data.get("data", [])
                    
                    if not anime_list:
                        return await ctx.reply(f"No anime airing on {day.title()} 🤔", mention_author=False)
                    
                    embed = discord.Embed(
                        title=f"📅 Airing on {day.title()}",
                        color=primary_color()
                    )
                    
                    description = []
                    for i, anime in enumerate(anime_list[:8], 1):
                        title = anime.get("title", "Unknown")[:35]
                        score = anime.get("score", "N/A")
                        description.append(f"`{i}.` **{title}** (⭐ {score})")
                    
                    embed.description = "\n".join(description)
                    embed.set_footer(text=f"Requested by {ctx.author}")
                    return await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            logging.error(f"Schedule API error: {e}")
        
        await ctx.reply("❌ Couldn't fetch the schedule", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # MANGA COMMANDS
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="manga", invoke_without_command=True)
    async def manga_group(self, ctx):
        """Manga commands - search, read, and recommendations"""
        embed = discord.Embed(
            title="📚 Manga Commands",
            description=(
                f"`{ctx.prefix}manga search <name>` - Find a manga\n"
                f"`{ctx.prefix}manga recommend` - Get random manga\n"
                f"`{ctx.prefix}manga read <name>` - Read manga chapters"
            ),
            color=primary_color()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @manga_group.command(name="search")
    async def manga_search(self, ctx, *, query=None):
        """Search for manga by name"""
        query = query or await self.prompt_query(ctx, "manga")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}manga?q={query}", query, MangaView)

    @manga_group.command(name="read")
    async def manga_read(self, ctx, *, query=None):
        """Read manga chapters online"""
        query = query or await self.prompt_query(ctx, "manga")
        if not query:
            return await ctx.send("❌ No manga name provided.")

        async with aiohttp.ClientSession() as session:
            url = f"{self.mangadex_url}/manga?title={query}&limit=25"
            async with session.get(url) as resp:
                data = await resp.json()

        if not data.get("data"):
            return await ctx.send(f"❌ No manga found for `{query}`.")

        view = MangaSession(ctx, data)
        embed = discord.Embed(
            title=f"📖 Results for `{query}`",
            description="Pick a manga from the dropdown below!",
            color=primary_color()
        )
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @manga_group.command(name="recommend")
    async def manga_recommend(self, ctx):
        """Get a random manga recommendation"""
        d = await self.mr.fetch_random_manga()
        m = await ctx.reply(embed=discord.Embed(description=f'🔍 Finding you a manga...', color=primary_color()), mention_author=False)
        await self.mr.update_manga_embed(m, d)

    # ═══════════════════════════════════════════════════════════════
    # FUN IMAGE COMMANDS
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="waifu")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def waifu(self, ctx):
        """Get a random waifu image"""
        session = await self.get_session()
        try:
            async with session.get(f"{self.waifu_api}/sfw/waifu") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    embed = discord.Embed(
                        title="Waifu",
                        color=discord.Color.from_rgb(255, 182, 193),
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed.set_image(url=data.get("url", ""))
                    embed.set_footer(text=f"Requested by {ctx.author}")
                    return await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            logging.error(f"Waifu API error: {e}")
        await ctx.reply("❌ Couldn't fetch waifu image", mention_author=False)

    @commands.command(name="neko")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def neko(self, ctx):
        """Get a random neko image"""
        session = await self.get_session()
        try:
            async with session.get(f"{self.nekos_api}/neko") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        url = results[0].get("url", "")
                        artist = results[0].get("artist_name", "Unknown")
                        
                        embed = discord.Embed(
                            title="Neko",
                            color=discord.Color.from_rgb(255, 182, 193),
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.set_image(url=url)
                        embed.set_footer(text=f"Artist: {artist} • Requested by {ctx.author}")
        except Exception as e:
            print(e)
             
    @commands.command(name="wallpaper")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def wallpaper(self, ctx):
        """Get a random anime wallpaper"""
        session = await self.get_session()
        
        # Try multiple APIs for better reliability
        apis = [
            "https://nekos.best/api/v2/wallpaper",  # Nekos.best - backup
            "https://api.waifu.im/search/?included_tags=wallpaper&limit=1",  # Waifu.im - fallback
        ]
        
        for i, api_url in enumerate(apis):
            try:
                async with session.get(api_url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Handle different API response formats
                        url = None
                        artist = "Unknown"
                        
                        if "waifu.pics" in api_url:
                            url = data.get("url", "")
                            artist = "Waifu.pics"
                        elif "nekos.best" in api_url:
                            results = data.get("results", [])
                            if results:
                                url = results[0].get("url", "")
                                artist = results[0].get("artist_name", "Nekos.best")
                        elif "waifu.im" in api_url:
                            results = data.get("results", [])
                            if results:
                                url = results[0].get("url", "")
                                artist = results[0].get("artist", "Waifu.im")
                        
                        if url:
                            embed = discord.Embed(
                                title="🖼️ Anime Wallpaper",
                                color=primary_color(),
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.set_image(url=url)
                            embed.set_footer(text=f"Source: {artist} • Requested by {ctx.author}")
                            
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(
                                label="Download",
                                style=discord.ButtonStyle.link,
                                url=url,
                                emoji="⬇️"
                            ))
                            
                            return await ctx.reply(embed=embed, view=view, mention_author=False)
                    else:
                        logging.warning(f"Wallpaper API {i+1} returned status {resp.status}: {api_url}")
                        
            except asyncio.TimeoutError:
                logging.warning(f"Wallpaper API {i+1} timeout: {api_url}")
                continue
            except Exception as e:
                logging.error(f"Wallpaper API {i+1} error: {e}", exc_info=True)
                continue
        
        await ctx.reply("❌ Couldn't fetch wallpaper from any source", mention_author=False)


async def setup(bot):
    await bot.add_cog(Anime(bot))