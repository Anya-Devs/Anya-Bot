import aiohttp;from imports.discord_imports import *;from data.const import primary_color;from data.local.emojis import *

class Recommendation(commands.Cog):
    def __init__(self, bot): self.bot = bot; self.API_URL = "https://api.jikan.moe/v4/random/anime"

    async def fetch_random_anime(self) -> dict | None:
        async with aiohttp.ClientSession() as s:
            async with s.get(self.API_URL) as r: return await r.json() if r.status == 200 else None

    @staticmethod
    def get_image_url(imgs: dict) -> str | None:
        for f in ("jpg", "webp"):
            for s in ("large", "medium", "small"):
                u = imgs.get(f, {}).get(f"{s}_image_url")
                if u: return u
        return None

    async def update_anime_embed(self, m: discord.Message, d: dict):
        a = d["data"]; g = ", ".join(g["name"] for g in a.get("genres", [])) or "N/A"
        s = a.get("score") or 0; stars = "▰" * int(s) + "▱" * (10 - int(s))
        e = discord.Embed(
            title=a.get("title", "Unknown Title"),
            description=a.get("synopsis", "> <:anya_angy:1268976144548630608> Synopsis not available"),
            color=primary_color()
        )
        e.add_field(name=" ", value=f"**Episodes:** `{a.get('episodes','N/A')}`\n**Status:** `{a.get('status','N/A')}`\n**Genres:** `{g if len(g)> 2 else 'Not Rated'}`\n" + (f"**Trailer:** `{a.get('trailer',{}).get('url')}`\n" if a.get("trailer") else "") + f"```py\nScore: {s:.1f}\n{stars}```", inline=False)
        e.set_image(url=self.get_image_url(a.get("images", {}))); e.set_footer(text="Anime Recommendation")

        v = View()
        v.add_item(Button(label="View Reviews", style=discord.ButtonStyle.link, url=f"https://myanimelist.net/anime/{a.get('mal_id')}/reviews", disabled=not a.get("mal_id")))
        b = Button(label="Get Another Random Anime", style=discord.ButtonStyle.primary, custom_id="random_anime_button")
        b.callback = self.random_anime_callback; v.add_item(b)
        await m.edit(embed=e, view=v)

    async def random_anime_callback(self, i: discord.Interaction):
        d = await self.fetch_random_anime()
        await self.update_anime_embed(i.message, d)
        await i.response.defer()

    @commands.command(name="anime_recommend", aliases=["ar"])
    async def recommend_anime(self, ctx: commands.Context):
        d = await self.fetch_random_anime(); m = await ctx.reply(embed=discord.Embed(description=f'{neko_lurk} Fetching anime...',color=primary_color()), mention_author=False)
        await self.update_anime_embed(m, d)
