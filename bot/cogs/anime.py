import asyncio, aiohttp, logging
from imports.discord_imports import *
from utils.cogs.anime import *

class Anime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.jikan.moe/v4/"
        self.red = discord.Color.red()
        self.ar = Anime_Recommendation(bot)

    async def prompt_query(self, ctx, item):
        prompt = f"{ctx.author.display_name.title()}, can you try entering the `name` of the {item} you're looking for?"
        embed = discord.Embed(description=prompt)
        if item == "anime":
            embed.set_footer(text=f"Try {ctx.prefix}{ctx.command.name} recommend to find a random anime")
        message = await ctx.reply(embed=embed, mention_author=False)

        def check(m): return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for("message", timeout=60, check=check)
            await message.delete()
            if not msg.content.strip(): raise ValueError(f"{item.title()} name cannot be empty")
            query = msg.content.strip()
            await msg.delete()
            return query
        except asyncio.TimeoutError:
            await message.edit(embed=discord.Embed(description=f"Time's Up! You didn't provide a {item} title for me to look up.", color=self.red))
        except ValueError as e:
            await message.edit(embed=discord.Embed(description=f"Error: {e}", color=self.red))
        return None

    async def fetch_and_send(self, ctx, url, query, view_cls):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as r:
                    r.raise_for_status()
                    data = await r.json()

            if not data["data"]:
                await ctx.reply(f"No results found for '{query}'. Please try a different title.")
                return

            view = view_cls(data, 0, 0)
            embed = await view.update_embed()
            await ctx.reply(embed=embed, view=view, mention_author=False)

        except aiohttp.ClientError as e:
            logging.error(f"HTTP error: {e}")
            await ctx.send(f"An HTTP error occurred: {e}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            await ctx.send(f"An unexpected error occurred: {e}")

    @commands.command(name="anime")
    async def anime_search(self, ctx, recommend: Literal['recommend'] = None, query: Optional[str] = None):
        if recommend:
            d = await self.ar.fetch_random_anime()
            m = await ctx.reply(embed=discord.Embed(description=f'{neko_lurk} Fetching anime...', color=primary_color()), mention_author=False)
            return await self.ar.update_anime_embed(m, d)

        query = query or await self.prompt_query(ctx, "anime")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}anime?q={query}", query, AnimeView)

    @commands.command(name="character")
    async def character_search(self, ctx, *, query=None):
        query = query or await self.prompt_query(ctx, "character")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}characters?q={query}", query, CharacterView)

    @commands.command(name="manga")
    async def manga_search(self, ctx, *, query=None):
        query = query or await self.prompt_query(ctx, "manga")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}manga?q={query}", query, MangaView)

def setup(bot):
    bot.add_cog(Anime(bot))
