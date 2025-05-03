import os, json, random, asyncio, requests, aiohttp, aiofiles, concurrent.futures
from urllib.request import urlopen
import numpy as np, cv2 as cv
from PIL import Image
from imports.log_imports import *
from imports.discord_imports import *
from utils.cogs.pokemon import *
from utils.subcogs.pokemon import Ping_Pokemon, Pokemon_Emojis
from data.const import error_custom_embed as err_embed, primary_color as p_color

class Pokemon(commands.Cog):
    def __init__(self, bot, folder="data/commands/pokemon/pokemon_images"):
        self.bot, self.folder = bot, folder
        self.uid, self.bot_ids = 716390085896962058, [854233015475109888, 874910942490677270]
        self.msg, self.cache, self.color_mem = "Shiny hunt pings:", {}, []
        self.color, self.err, self.executor = p_color, err_embed, concurrent.futures.ThreadPoolExecutor()
        self.api, self.info = "https://pokeapi.co/api/v2/pokemon", "https://pokeapi.co/api/v2/pokemon/{}/"
        self.orb = cv.ORB_create()
        self.ds_file = "data/commands/pokemon/dataset.npy"
        self.out_folder = "data/commands/pokemon/predictions"
        self.poke_json = "data/commands/pokemon/pokemon.json"
        self.wait = 11
        self.data = PokemonData()

    async def fetch_names(self):
        names, url = [], self.api
        async with aiohttp.ClientSession() as s:
            while url:
                async with s.get(url) as r:
                    if r.status != 200: logger.error("Failed to fetch Pokémon."); break
                    d = await r.json(); names += [p["name"] for p in d["results"]]; url = d.get("next")
        return names

    async def fetch_info(self, name):
        url = self.info.format(name.lower())
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status == 200: return (await r.json())["sprites"]["other"]["official-artwork"]["front_default"]
                logger.error(f"Failed to fetch {name} info.")

    @commands.command(name="predict")
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def predict(self, ctx, *, url=None):
        if not url:
            if ctx.message.attachments: url = ctx.message.attachments[0].url
            elif ctx.message.reference:
                ref = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref.attachments: url = ref.attachments[0].url
                elif ref.embeds and ref.embeds[0].image: url = ref.embeds[0].image.url
        if not url: return await ctx.send("No image found to predict.")
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status != 200: return await ctx.reply(f"Failed to download image. Status code: {r.status}", mention_author=False)
                loop = asyncio.get_event_loop()
                img = await loop.run_in_executor(self.executor, lambda: bytearray(requests.get(url).content))
                img = cv.imdecode(np.asarray(img, dtype=np.uint8), cv.IMREAD_COLOR)
                pred, time_taken, name = await self.predictor.predict_pokemon(img)
                hunters = await self.data.get_hunters_for_pokemon(name)
                reply = f"{ctx.author.mention}, {pred}" if ctx.author.id in hunters else pred
                await ctx.reply(reply, mention_author=False)

    @commands.command(name="hunt")
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def hunt(self, ctx, action="list", *names):
        uid = ctx.author.id
        if action == "list":
            lst = await self.data.get_user_pokemon(uid)
            return await ctx.reply("### Your Pokétwo Pokémon List:\n" + "\n".join(f"{i+1}. {p.lower()}" for i, p in enumerate(sorted(lst))) if lst else f"### No Pokémon yet!\n- `Try {ctx.prefix}hunt add <name>`", mention_author=False)
        elif action == "add":
            if not names: return await ctx.reply("Provide at least one name to add.", mention_author=False)
            lst = await self.data.get_user_pokemon(uid)
            if len(lst) + len(names) > 1: return await ctx.reply("Only 1 Pokémon allowed. Remove one before adding.", mention_author=False)
            added, exists, dup = [], [], []
            for n in names:
                if not await self.data.check_pokemon_exists(n.lower()): exists.append(n); continue
                if n.lower() in map(str.lower, lst): dup.append(n); continue
                await self.data.add_pokemon_to_user(uid, n); added.append(n)
            msgs = []
            if added: msgs.append(f"`{', '.join(p.lower() for p in added)}` added!")
            if dup: msgs.append(f"Already in list: `{', '.join(dup)}`.")
            if exists: msgs.append(f"Invalid Pokémon: `{', '.join(exists)}`.")
            await ctx.reply("\n".join(msgs), mention_author=False)
        elif action == "remove":
            if not names: return await ctx.reply("Provide at least one name to remove.", mention_author=False)
            lst = await self.data.get_user_pokemon(uid)
            rem, miss = [], []
            for n in names:
                if n.lower() not in map(str.lower, lst): miss.append(n); continue
                await self.data.remove_pokemon_from_user(uid, n); rem.append(n)
            msgs = []
            if rem: msgs.append(f"`{', '.join(rem)}` removed!")
            if miss: msgs.append(f"Not in list: `{', '.join(miss)}`.")
            await ctx.reply("\n".join(msgs), mention_author=False)
        else:
            acts = ["list", "add <name>", "remove <name>"]
            await ctx.reply(f"Invalid action. Use: `{ctx.prefix}hunt {' | '.join(acts)}`", mention_author=False)

    @commands.command(
        help="Displays Pokemon dex information.", aliases=["pokdex", "dex", "d", "p"]
    )
    async def pokemon(self, ctx, *, pokemon=None, form=None):
     async with ctx.typing():
        pc = Pokemon_Commands(self.bot)
        pp = Ping_Pokemon(self.bot)

        pokemon = pp.transform_pokemon_name(pokemon)
        pokemon = pokemon[0]

        is_shiny = pokemon and pokemon.lower().startswith("shiny")
        cleaned_name = (
            pokemon.lower()
            .replace(" ", "-")
            .replace("shiny-", "shiny ")
            .replace("shiny ", "")
            if pokemon else ""
        )

        pokemon_id = random.randint(1, 1021) if not pokemon or is_shiny else cleaned_name
        has_form = form is not None
        db_path = self.poke_json

        if not os.path.exists(db_path):
            with open(db_path, "w") as f:
                f.write("{}")

        with open(db_path, "r") as f:
            cache = json.load(f)

        if str(pokemon_id) in cache:
            return await pc.send_pokemon_info(
                ctx=ctx,
                data=cache[str(pokemon_id)],
                type="shiny" if is_shiny else None,
                color=p_color(),
            )

        url = (
            f"https://pokeapi.co/api/v2/pokemon-form/{pokemon_id}-{form}"
            if has_form else
            f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
        )

        response = requests.get(url)
        if response.status_code != 200:
            label = f"Form data" if has_form else "Data"
            return await ctx.send(f"{label} not found for `{pokemon_id}`.")

        try:
            data = response.json()
            await (
                self.send_form_pokemon if has_form else pc.send_pokemon_info
            )(
                ctx,
                data=data,
                type="shiny" if is_shiny else None,
                color=p_color(),
            )

            cache[str(pokemon_id)] = data
            with open(db_path, "w") as f:
                json.dump(cache, f)

        except json.JSONDecodeError:
            if isinstance(pokemon_id, int):
                await ctx.send(f"Failed to parse JSON data for `{pokemon_id}`.")

def setup(bot):
    bot.add_cog(Pokemon(bot))
    bot.add_cog(Ping_Pokemon(bot))
    bot.add_cog(Pokemon_Emojis(bot))


