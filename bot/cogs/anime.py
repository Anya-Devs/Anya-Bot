import asyncio, aiohttp, logging
from imports.discord_imports import *
from utils.cogs.anime import *

class Anime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.jikan.moe/v4/"
        self.mangadex_url = "https://api.mangadex.org"
        self.red = discord.Color.red()
        self.ar = Anime_Recommendation(bot)
        self.mr = Manga_Recommendation(bot)

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


def setup(bot):
    bot.add_cog(Anime(bot))