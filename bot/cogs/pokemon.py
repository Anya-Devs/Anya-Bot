import os, json, random, asyncio, requests, aiohttp, aiofiles, concurrent.futures
from urllib.request import urlopen
import numpy as np, cv2 as cv
from PIL import Image
from imports.log_imports import *
from imports.discord_imports import *
from utils.cogs.pokemon import *
from utils.subcogs.pokemon import Ping_Pokemon, Pokemon_Emojis
from data.local.const import error_custom_embed as err_embed, primary_color as p_color

class Pokemon(commands.Cog):
    def __init__(self, bot, folder="data/commands/pokemon/pokemon_images"):
        self.bot, self.folder = bot, folder
        self.uid, self.bot_ids = 716390085896962058, [854233015475109888, 874910942490677270]
        self.msg, self.cache, self.color_mem = "Shiny hunt pings:", {}, []
        self.color, self.err = p_color, err_embed
        self.api, self.info = "https://pokeapi.co/api/v2/pokemon", "https://pokeapi.co/api/v2/pokemon/{}/"
        self.poke_json = "data/commands/pokemon/pokemon.json"
        self.wait = 11

    @commands.command(help="Displays Pokemon dex information.", aliases=["dex", "d"])
    async def pokdex(self, ctx, *, pokemon=None, form=None):
     async with ctx.typing():
        pc, pp = Pokemon_Commands(self.bot), Ping_Pokemon(self.bot)
        is_shiny = pokemon and "shiny" in pokemon.lower()
        name = pokemon.lower().replace(" ", "-").replace("shiny-", "").replace("shiny", "") if pokemon else ""
        pid = name if name else random.randint(1, 1021)
        has_form = form is not None

        if not os.path.exists(self.poke_json): open(self.poke_json, "w").write("{}")
        with open(self.poke_json) as f: cache = json.load(f)

        if str(pid) in cache:
            return await pc.send_pokemon_info(ctx, data=cache[str(pid)], type="shiny" if is_shiny else None, color=p_color())

        url = f"https://pokeapi.co/api/v2/pokemon-form/{pid}-{form}" if has_form else self.info.format(pid)
        r = requests.get(url)
        if r.status_code != 200:
            return await ctx.send(f"{'Form data' if has_form else 'Data'} not found for `{pid}`.")

        try:
            data = r.json()
            await (self.send_form_pokemon if has_form else pc.send_pokemon_info)(ctx, data=data, type="shiny" if is_shiny else None, color=p_color())
            cache[str(pid)] = data
            with open(self.poke_json, "w") as f: json.dump(cache, f, indent=2)
        except json.JSONDecodeError:
            if isinstance(pid, int): await ctx.send(f"Failed to parse JSON data for `{pid}`.")   

def setup(bot):
    bot.add_cog(Pokemon(bot))
    bot.add_cog(Ping_Pokemon(bot))
    bot.add_cog(Pokemon_Emojis(bot))

