import os, json, random, asyncio
from urllib.request import urlopen

import concurrent
import requests, aiohttp, aiofiles
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures as futures

import numpy as np
import cv2 as cv
from PIL import Image

from Imports.log_imports import *
from Imports.discord_imports import *

from utils.cogs.pokemon import *
from utils.subcogs.pokemon import Ping_Pokemon, Pokemon_Emojis
from data.const import error_custom_embed, primary_color


class Pokemon(commands.Cog):
    def __init__(self, bot, dataset_folder="data/commands/pokemon/pokemon_images"):
        self.bot = bot
        self.author_id = 716390085896962058 #poketwo
        self.detect_bot_id = [
            854233015475109888,
            874910942490677270,
        ]  
        self.phrase = "Shiny hunt pings:"
        
        self.data_handler = PokemonData()  
        self.primary_color = primary_color
        self.error_custom_embed = error_custom_embed
        self.local_color_memory = []  
        self.pokemon_api_url = "https://pokeapi.co/api/v2/pokemon"
        self.pokemon_info_url = "https://pokeapi.co/api/v2/pokemon/{}/"
        self.dataset_file = "data/commands/pokemon/dataset.npy"
        self.output_folder = "data/commands/pokemon/predictions"
        self.pokemon_json = "data/commands/pokemon/pokemon.json"
        self.cache = {}
        self.orb = cv.ORB_create()  
        self.executor = (
            concurrent.futures.ThreadPoolExecutor()
        )  
        self.dataset_folder = dataset_folder  
        self.wait_time = 11

    async def fetch_all_pokemon_names(self):
        pokemon_names = []
        url = self.pokemon_api_url
        while url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for result in data["results"]:
                            pokemon_names.append(result["name"])
                        url = data.get("next")
                    else:
                        logger.error("Failed to fetch Pokémon names.")
                        break
        return pokemon_names

    async def fetch_pokemon_info(self, pokemon_name):
        url = self.pokemon_info_url.format(pokemon_name.lower())
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["sprites"]["other"]["official-artwork"]["front_default"]
                else:
                    logger.error(f"Failed to fetch info for {pokemon_name}.")
                    return None

    @commands.command(name="predict")
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def predict(self, ctx, *, image_url=None):
        image_url = None

        if image_url:
            image_url = image_url
        elif ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        elif ctx.message.reference:
            reference_message = await ctx.channel.fetch_message(
                ctx.message.reference.message_id
            )
            if reference_message.attachments:
                image_url = reference_message.attachments[0].url
            elif reference_message.embeds:
                embed = reference_message.embeds[0]
                if embed.image:
                    image_url = embed.image.url

        if image_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        loop = asyncio.get_event_loop()
                        img_bytes = await loop.run_in_executor(
                            self.executor,
                            lambda: bytearray(requests.get(image_url).content),
                        )
                        img = np.asarray(img_bytes, dtype=np.uint8)
                        img = cv.imdecode(img, cv.IMREAD_COLOR)
                        
                        (
                            prediction,
                            time_taken,
                            predicted_name,
                        ) = await self.predictor.predict_pokemon(img)

                        
                        hunters = await self.data_handler.get_hunters_for_pokemon(
                            predicted_name
                        )
                        user_id = ctx.author.id
                        is_hunter = user_id in hunters

                        
                        response_message = prediction
                        if is_hunter:
                            
                            response_message = (
                                f"{ctx.author.mention}, {response_message}"
                            )

                        await ctx.reply(response_message, mention_author=False)
                    else:
                        await ctx.reply(
                            f"Failed to download image. Status code: {response.status}",
                            mention_author=False,
                        )
        else:
            await ctx.send("No image found to predict.")

    @commands.command(name="hunt")
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def hunt(self, ctx, action="list", *pokemon_names):
        user_id = ctx.author.id
        if action == "list":
            
            user_pokemon = await self.data_handler.get_user_pokemon(user_id)

            if user_pokemon:
                await ctx.reply(
                    f"### Your Pokétwo Pokémon List:\n"
                    + "\n".join(
                        f"{i + 1}. {pokemon.lower()}"
                        for i, pokemon in enumerate(sorted(user_pokemon, key=str.lower))
                    )
                    + "\n",
                    mention_author=False,
                )
            else:
                await ctx.reply(
                    f"### You don't have any Pokémon in your hunting list yet!\n- `Try doing {ctx.prefix} hunt add <pokemon_name>`",
                    mention_author=False,
                )

        elif action == "add":
            if not pokemon_names:
                await ctx.reply(
                    "Please provide at least one Pokémon name to add.",
                    mention_author=False,
                )
                return

            
            user_pokemon = await self.data_handler.get_user_pokemon(user_id)

            
            if len(user_pokemon) + len(pokemon_names) > 1:
                await ctx.reply(
                    "You already have 1 Pokémon in your hunt list. Please **remove** one to add new ones.",
                    mention_author=False,
                )
                return

            added_pokemon = []
            not_exist_pokemon = []
            already_have_pokemon = []

            for pokemon_name in pokemon_names:
                
                exists = await self.data_handler.check_pokemon_exists(
                    pokemon_name.lower()
                )
                if not exists:
                    not_exist_pokemon.append(pokemon_name)
                    continue

                
                if any(p.lower() == pokemon_name.lower() for p in user_pokemon):
                    already_have_pokemon.append(pokemon_name)
                    continue

                
                await self.data_handler.add_pokemon_to_user(user_id, pokemon_name)
                added_pokemon.append(pokemon_name)

            
            response_messages = []
            if added_pokemon:
                response_messages.append(
                    f"`{', '.join(p.lower() for p in added_pokemon)}` has been **added** to your Pokémon list!"
                )

            if already_have_pokemon:
                response_messages.append(
                    f"You already have: `{'/n- '.join(already_have_pokemon)}`."
                )

            if not_exist_pokemon:
                response_messages.append(
                    f"The following Pokémon do not exist in the database: `{'/n- '.join(not_exist_pokemon)}`."
                )

            await ctx.reply("\n".join(response_messages), mention_author=False)

        elif action == "remove":
            if not pokemon_names:
                await ctx.reply(
                    "Please provide at least one Pokémon name to **remove**.",
                    mention_author=False,
                )
                return

            
            user_pokemon = await self.data_handler.get_user_pokemon(user_id)

            removed_pokemon = []
            not_in_list_pokemon = []

            for pokemon_name in pokemon_names:
                
                if not any(p.lower() == pokemon_name.lower() for p in user_pokemon):
                    not_in_list_pokemon.append(pokemon_name)
                    continue

                
                await self.data_handler.remove_pokemon_from_user(user_id, pokemon_name)
                removed_pokemon.append(pokemon_name)

            
            response_messages = []
            if removed_pokemon:
                response_messages.append(
                    f"`{', '.join(removed_pokemon)}` has been **removed** from your Pokémon list!"
                )

            if not_in_list_pokemon:
                response_messages.append(
                    f"The following Pokémon are not in your list: `{', '.join(not_in_list_pokemon)}`."
                )

            await ctx.reply("\n".join(response_messages), mention_author=False)

        else:
            actions = ["list", "add <pokemon_name>", "remove <pokemon_name>"]
            await ctx.reply(
                f"Invalid action! Use `{ctx.prefix}hunt {f'`, `{ctx.prefix}hunt '.join(actions)}`.",
                mention_author=False,
            )

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
        db_path = self.pokemon_json

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
                color=primary_color(),
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
                color=primary_color,
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


