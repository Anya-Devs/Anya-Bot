
import json
import csv
import time
import os
import logging
import random
import asyncio
import pandas as pd
from tqdm import tqdm
from typing import List, Tuple, Optional
from urllib.request import urlopen


import cv2
import cv2 as cv
import numpy as np
import aiohttp
import requests
import motor.motor_asyncio
from PIL import Image



from concurrent import *
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor



from Imports.discord_imports import *
from Subcogs.pokemon import Ping_Pokemon
from Imports.log_imports import logger
from Data.const import error_custom_embed, primary_color



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)




class Pokemon_Emojis(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.GUILD_IDS = [
            "1340447626105065585", "1340447685685153852", "1340447747974762556",
            "1340447749111545998", "1340447923548459133", "1340447977340145717",
            "1340448026740916338", "1340448028196212807", "1340448148866469971",
            "1340448241069723749", "1340448280966074519", "1340448379729346560",
            "1340448496100053055", "1340448546603667619", "1340448595052335104",
            "1340448664157687830", "1340448723603296300", "1340448725314703390",
            "1340448849281548363", "1340449016089153598", "1340449082971390033",
            "1340449185933299723", "1340449231194030121", "1340449271366815806",
            "1340449391533625398", "1340449491765166231", "1340449540175691847",
            "1340698929922183300", "1340699061992558665", "1340699001011437610"
        ]
        self.POKEMON_IMAGES_FOLDER = "Data/pokemon/pokemon_emojis"
        self.POKE_API_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{}.png"
        self.emoji_json_path = os.path.join("Data", "pokemon", "pokemon_emojis.json")
        self.owner_id = 1124389055598170182
        
        self.emoji_mapping = self.load_emoji_mapping()


        os.makedirs(os.path.dirname(self.emoji_json_path), exist_ok=True)
        os.makedirs(self.POKEMON_IMAGES_FOLDER, exist_ok=True)

        

        if os.path.exists(self.emoji_json_path):
            with open(self.emoji_json_path, "r") as f:
                self.emoji_mapping = json.load(f)
        else:
            self.emoji_mapping = {}

        self.semaphore = asyncio.Semaphore(5)

    def load_emoji_mapping(self):
        """Load emoji mappings from the JSON file."""
        if os.path.exists(self.emoji_json_path):
            with open(self.emoji_json_path, "r") as f:
                return json.load(f)
        else:
            return {}
        
    def get_pokemon_id(self, filename):
        return filename.split(".")[0].zfill(3)

    async def download_pokemon_images(self):
        print("Starting Pokémon image download...")
        pokemon_ids = await self.fetch_all_pokemon_ids()
        existing_images = set(self.load_images())
        missing_pokemon_ids = []

        for pokemon_id in pokemon_ids:
            img_filename = f"{str(pokemon_id).zfill(3)}.png"
            if img_filename not in existing_images:
                missing_pokemon_ids.append(pokemon_id)

        if missing_pokemon_ids:
            async with aiohttp.ClientSession() as session:
                for pokemon_id in tqdm(missing_pokemon_ids, desc="Downloading Pokémon images"):
                    img_url = self.POKE_API_URL.format(pokemon_id)
                    img_path = os.path.join(self.POKEMON_IMAGES_FOLDER, f"{str(pokemon_id).zfill(3)}.png")
                    try:
                        async with session.get(img_url) as response:
                            if response.status == 200:
                                with open(img_path, "wb") as img_file:
                                    img_file.write(await response.read())
                                print(f"Downloaded image for Pokémon ID: {pokemon_id}")
                            else:
                                print(f"Failed to download image for Pokémon ID: {pokemon_id}")
                    except Exception as e:
                        print(f"Error downloading Pokémon ID {pokemon_id}: {e}")
        else:
            print("All Pokémon images are already downloaded.")

    def load_images(self):
        return os.listdir(self.POKEMON_IMAGES_FOLDER)

    async def fetch_all_pokemon_ids(self):
        pokemon_ids = []
        url = "https://pokeapi.co/api/v2/pokemon"
        async with aiohttp.ClientSession() as session:
            while url:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for result in data["results"]:
                            async with session.get(result["url"]) as poke_response:
                                if poke_response.status == 200:
                                    poke_data = await poke_response.json()
                                    pokemon_ids.append(poke_data["id"])
                        url = data.get("next")
                    else:
                        print("Failed to fetch Pokémon IDs.")
                        break
        return pokemon_ids

    async def list_existing_emojis(self, server):
        """List existing emojis in the server."""
        if server is None:
            print("Server is None, cannot list emojis.")
            return {}

        if not server.me.guild_permissions.manage_emojis:
            print(f"Bot does not have permission to manage emojis in {server.name}.")
            return {}

        try:
            existing_emojis = {emoji.name: emoji.id for emoji in server.emojis}
            return existing_emojis
        except AttributeError:
            print(f"Error: Unable to access emojis for {server.name}.")
            return {}

    async def upload_single_emoji(self, server, pokemon_id):
        # Check if the emoji already exists in the server
        existing_emojis = await self.list_existing_emojis(server)
        if pokemon_id in existing_emojis:
            print(f"Emoji for Pokémon ID {pokemon_id} already exists in {server.name}. Skipping upload.")
            return

        # Check if the emoji is already mapped in emoji_mapping
        if str(server.id) in self.emoji_mapping and pokemon_id in self.emoji_mapping[str(server.id)]:
            print(f"Emoji for Pokémon ID {pokemon_id} is already mapped for {server.name}. Skipping upload.")
            return

        emoji_image_path = os.path.join(self.POKEMON_IMAGES_FOLDER, f"{pokemon_id}.png")
        with open(emoji_image_path, "rb") as emoji_file:
            emoji_data = emoji_file.read()
        
        try:
            # Attempt to create the custom emoji
            emoji = await server.create_custom_emoji(name=pokemon_id, image=emoji_data)
            if str(server.id) not in self.emoji_mapping:
                self.emoji_mapping[str(server.id)] = {}
            self.emoji_mapping[str(server.id)][pokemon_id] = {"name": pokemon_id, "id": emoji.id}
            print(f"Uploaded emoji for Pokémon ID {pokemon_id} in server: {server.name}")

            # Save updated emoji mapping incrementally
            with open(self.emoji_json_path, "w") as f:
                json.dump(self.emoji_mapping, f, indent=4)

        except discord.errors.HTTPException as e:
            if e.status == 429:
                # Retrieve Retry-After from the response headers (default to 60 seconds if not provided)
                retry_after = int(e.response.headers.get("Retry-After", 60))
                print(f"Rate limited when uploading Pokémon ID {pokemon_id}. Retrying in {retry_after} seconds.")
                await asyncio.sleep(retry_after)
                await self.upload_single_emoji(server, pokemon_id)  # Retry the upload
            else:
                print(f"Error uploading emoji for Pokémon ID {pokemon_id} in server {server.name}: {e}")
        except Exception as e:
            print(f"Error uploading emoji for Pokémon ID {pokemon_id} in server {server.name}: {e}")

    async def upload_emojis_for_server(self, servers, max_emojis_per_server=50, embed_message=None, ctx=None):
        images = self.load_images()
        total_emojis = len(images)
        emojis_uploaded = 0
        current_server_index = 0

        print(f"Starting emoji upload process. Total images to upload: {total_emojis}")

        while emojis_uploaded < total_emojis:
            server = servers[current_server_index]

            if not server:
                print(f"Invalid server at index {current_server_index}. Skipping...")
                current_server_index = (current_server_index + 1) % len(servers)
                continue

            print(f"Processing server: {server.name} (ID: {server.id})")

            existing_emojis = await self.list_existing_emojis(server)
            print(f"Found {len(existing_emojis)} existing emojis in {server.name}")

            max_uploads_for_server = max_emojis_per_server - len(existing_emojis)

            if len(existing_emojis) >= max_emojis_per_server:
                print(f"Server {server.name} already has the max number of emojis. Skipping...")
                current_server_index = (current_server_index + 1) % len(servers)
                continue

            for img in images[emojis_uploaded:emojis_uploaded + max_uploads_for_server]:
                pokemon_id = self.get_pokemon_id(img)

                if pokemon_id in existing_emojis or (str(server.id) in self.emoji_mapping and pokemon_id in self.emoji_mapping[str(server.id)]):
                    print(f"Emoji for Pokémon ID {pokemon_id} already exists. Skipping...")
                    continue

                try:
                    await self.upload_single_emoji(server, pokemon_id)
                    emojis_uploaded += 1
                    print(f"Uploaded emoji for Pokémon ID: {pokemon_id} in server: {server.name}")

                    # Fixed 10-second delay after each emoji upload
                    await asyncio.sleep(3)

                except Exception as e:
                    print(f"Error uploading emoji for Pokémon ID {pokemon_id} in server {server.name}: {e}")

                await asyncio.sleep(1)  # Short delay between uploads

                if emojis_uploaded >= total_emojis:
                    break

            current_server_index = (current_server_index + 1) % len(servers)

        if embed_message:
            embed_message.description = "All Pokémon emojis have been created and mapping saved!"
            await embed_message.edit(embed=embed_message)
        else:
            await ctx.send("All Pokémon emojis have been created and mapping saved!")
        
        print("Emoji creation process completed.")

    @commands.command()
    async def create_emojis(self, ctx):
        print("create_emojis command invoked")
        if ctx.author.id != self.owner_id:
            await ctx.reply("You do not have permission to use this command")
            return  
        print("User has permission. Proceeding...")

        embed = discord.Embed(
            description="Downloading Pokémon images and uploading emojis.",
            color=discord.Color.default()
        )
        initial_message = await ctx.send(embed=embed)

        print("Starting image download...")
        await self.download_pokemon_images()
        print("Image download completed.")

        # Process only servers listed in GUILD_IDS
        servers = [self.bot.get_guild(int(guild_id)) for guild_id in self.GUILD_IDS]
        servers = [server for server in servers if server]
        print(f"Found {len(servers)} valid servers.")

        await self.upload_emojis_for_server(servers, embed_message=initial_message, ctx=ctx)

        await ctx.send("All Pokémon emojis have been created and mapping saved!")
        print("Emoji creation process completed.")
    
    @staticmethod
    def get_emoji_for_pokemon(self, pokemon_id):
        """Return the emoji in the format <:emoji_name:emoji_id> for a given Pokémon ID across all servers."""
        emoji_name = str(pokemon_id).zfill(3)
        
        # Loop through all the server data in the emoji mapping
        for server_id, server_data in self.emoji_mapping.items():
            if str(pokemon_id) in server_data:
                emoji_data = server_data[str(pokemon_id)]
                emoji_name = emoji_data['name']
                emoji_id = emoji_data['id']
                return f"<:{emoji_name}:{emoji_id}>"
        
        # Return None if no emoji is found for that Pokémon ID across all servers
        return None
    
    def call_emoji(self, emoji_mapping, pokemon_id):
     """
     Return a discord.PartialEmoji for a given Pokémon ID across all servers.
     """
     pokemon_id = pokemon_id['id']
     # Iterate over each server's emoji mapping
     for server_id, server_data in emoji_mapping.items():
        if str(pokemon_id) in server_data:
            emoji_data = server_data[str(pokemon_id)]
            emoji_name = emoji_data['name']
            emoji_id = int(emoji_data['id'])  # Ensure the emoji ID is an integer
            print(f"Emoji found: {emoji_name} (ID: {emoji_id})")  # Debug print
            return f"<:{emoji_name}:{emoji_id}>"
            
            
            # Return a discord.PartialEmoji object
            return discord.PartialEmoji(name=emoji_name, id=emoji_id)
    
     print(f"No emoji found for Pokémon ID {pokemon_id}")  # Debug print
     # Return None if no matching emoji is found
     return None
    
    
    @commands.command()
    async def get_emoji(self, ctx, pokemon_id: int):
        emoji_str = self.get_emoji_for_pokemon(pokemon_id)
        
        if emoji_str:
            await ctx.send(f"Here is your Pokémon emoji: {emoji_str}")
        else:
            await ctx.send(f"No emoji found for Pokémon ID {pokemon_id} across all servers.")
   
   
   
   
   
   
   
    @commands.command(name="clear_emojis")
    async def delete_all_emojis(self, ctx):
     # Loop through each server in GUILD_IDS
     for guild_id in self.GUILD_IDS:
        server = self.bot.get_guild(int(guild_id))
        
        if not server:
            print(f"Server with ID {guild_id} not found.")
            continue

        if not server.me.guild_permissions.manage_emojis:
            await ctx.send(f"I do not have permission to manage emojis in server {server.name} (ID: {server.id})!")
            continue

        print(f"Starting to delete all emojis in server: {server.name} (ID: {server.id})")
        
        # Get all emojis from the server and delete them
        emojis_to_delete = list(server.emojis)

        if not emojis_to_delete:
            print(f"No emojis to delete in server: {server.name}")
            continue

        for emoji in emojis_to_delete:
            try:
                await emoji.delete()
                print(f"Deleted emoji: {emoji.name} from server: {server.name}")
            except discord.HTTPException as e:
                # If error code 10014 (Unknown Emoji) is returned, ignore it
                if hasattr(e, "code") and e.code == 10014:
                    print(f"Emoji {emoji.name} not found (possibly already deleted). Skipping...")
                    continue
                else:
                    print(f"Failed to delete emoji {emoji.name}: {e}")

        await ctx.send(f"All emojis have been deleted in {server.name} (ID: {server.id})!")
        print(f"Finished deleting emojis in server: {server.name}")



















class PokemonData:
    def __init__(self):
        self.DB_NAME = "Pokemon_SH"

        
        mongo_url = os.getenv("MONGO_URI")
        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")
        self.mongoConnect = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        self.db = self.mongoConnect[self.DB_NAME]
        self.users_collection = self.db["users_pokemon"]

        
        self.pokemon_df = pd.read_csv("Data/pokemon/pokemon_description.csv")

    async def check_pokemon_exists(self, pokemon_name):
        
        return not self.pokemon_df[
            self.pokemon_df["slug"].str.lower() == pokemon_name.lower()
        ].empty

    async def get_user_pokemon(self, user_id):
        
        user_data = await self.users_collection.find_one({"user_id": user_id})
        if user_data:
            return user_data["pokemon_list"]
        return []

    async def add_pokemon_to_user(self, user_id, pokemon_name):
        
        user_pokemon = await self.get_user_pokemon(user_id)
        user_pokemon.append(pokemon_name)
        await self.users_collection.update_one(
            {"user_id": user_id}, {"$set": {"pokemon_list": user_pokemon}}, upsert=True
        )

    async def remove_pokemon_from_user(self, user_id, pokemon_name):
        
        user_pokemon = await self.get_user_pokemon(user_id)
        user_pokemon = [p for p in user_pokemon if p.lower() !=
                        pokemon_name.lower()]
        await self.users_collection.update_one(
            {"user_id": user_id}, {"$set": {"pokemon_list": user_pokemon}}
        )

    async def get_hunters_for_pokemon(self, pokemon_name):
        
        hunters = await self.users_collection.find(
            {"pokemon_list": {"$in": [pokemon_name]}}
        ).to_list(None)

        
        return [hunter["user_id"] for hunter in hunters]


class Pokemon(commands.Cog):
    def __init__(self, bot, dataset_folder="Data/pokemon/pokemon_images"):
        self.bot = bot
        self.author_id = 716390085896962058
        self.detect_bot_id = [
            854233015475109888,
            874910942490677270,
        ]  
        self.phrase = "Shiny hunt pings:"
        #self.predictor = PokemonPredictor()
        self.data_handler = PokemonData()  
        self.primary_color = primary_color
        self.error_custom_embed = error_custom_embed
        self.local_color_memory = []  
        self.pokemon_api_url = "https://pokeapi.co/api/v2/pokemon"
        self.pokemon_info_url = "https://pokeapi.co/api/v2/pokemon/{}/"
        self.dataset_file = "Data/pokemon/dataset.npy"
        self.output_folder = "Data/pokemon/predictions"
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

    async def download_all_images(self, max_concurrent_tasks=10):
        pokemon_names = await self.fetch_all_pokemon_names()
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

        async with aiohttp.ClientSession() as session:
            tasks = []
            semaphore = asyncio.Semaphore(max_concurrent_tasks)
            for pokemon_name in pokemon_names:
                tasks.append(self.download_image(
                    session, pokemon_name, semaphore))
            await asyncio.gather(*tasks)

    async def download_image(self, session, pokemon_name, semaphore):
        async with semaphore:
            filename = f"{pokemon_name.lower()}.png"
            filepath = os.path.join(self.image_folder, filename)
            if not os.path.exists(filepath):
                official_artwork_url = await self.fetch_pokemon_info(pokemon_name)
                if official_artwork_url:
                    try:
                        async with session.get(official_artwork_url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                async with aiofiles.open(filepath, "wb") as f:
                                    await f.write(image_data)
                                logger.info(
                                    f"Downloaded image for {pokemon_name}.")
                            else:
                                logger.error(
                                    f"Failed to download image for {pokemon_name}."
                                )
                    except Exception as e:
                        logger.error(
                            f"Error downloading image for {pokemon_name}: {e}")
                else:
                    logger.error(
                        f"Failed to fetch information for {pokemon_name}.")
            else:
                logger.info(
                    f"Image for {pokemon_name} already exists, skipping download."
                )

    @staticmethod
    def remove_srgb_profile(img_path):
        try:
            with Image.open(img_path) as img:
                img.save(img_path, icc_profile=None)
                logger.debug(f"Removed sRGB profile from {img_path}")
        except Exception as e:
            logger.error(f"Error removing sRGB profile: {e}")

    @staticmethod
    def ensure_correct_color_format(img):
        """
        Convert image to RGB format.
        """
        if img.shape[2] == 3:  
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        elif img.shape[2] == 4:
            return cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        return img

    @staticmethod
    def download_file(url, filename):
        response = urlopen(url)
        with open(filename, "wb") as f:
            f.write(response.read())

    @commands.command(name="predict")
    
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def predict(self, ctx, *, arg=None):
        image_url = None

        if arg:
            image_url = arg
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
        joiner = "\n -"

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
            actions = ["list", "add <pokemon>", "remove <pokemon>"]
            await ctx.reply(
                f"Invalid action! Use `...hunt {'`, `...hunt '.join(actions)}`.",
                mention_author=False,
            )

    @commands.command(
        help="Displays Pokemon dex information.", aliases=["pokdex", "dex", "d", "p"]
    )
    @commands.cooldown(1, 6, commands.BucketType.user)
    async def pokemon(self, ctx, *, args=None, form=None):
        
        primary_color = self.primary_color()
        async with ctx.typing():
            is_shiny = False
            is_form = False
            is_mega = None

            if not args:
                pokemon_id = random.randint(1, 1021)
            elif args.lower() == "shiny":
                is_shiny = True
                pokemon_id = random.randint(1, 1021)
            else:
                args = args.lower().replace(" ", "-").replace("shiny-", "shiny ")
                is_shiny = args.startswith("shiny ")
                is_form = form is not None

                args = args.replace("shiny ", "")
                pokemon_id = args

            folder_path = "Data"
            os.makedirs(folder_path, exist_ok=True)
            pokemon_folder_path = os.path.join(folder_path, "pokemon")
            os.makedirs(pokemon_folder_path, exist_ok=True)
            file_path = os.path.join(pokemon_folder_path, "pokemon.json")

            if not os.path.exists(file_path):
                with open(file_path, "w") as file:
                    file.write("{}")  

            pokemon_data = {}

            if os.path.exists(file_path):
                with open(file_path, "r") as file:
                    pokemon_data = json.load(file)

                if str(pokemon_id) in pokemon_data:
                    existing_data = pokemon_data[str(pokemon_id)]
                    return await self.send_pokemon_info(
                        ctx,
                        existing_data,
                        type="mega" if is_mega else "shiny" if is_shiny else None,
                        color=primary_color,
                    )

            if is_form:
                url = f"https://pokeapi.co/api/v2/pokemon-form/{pokemon_id}-{form}"
            else:
                url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"

            response = requests.get(url)
            if response.status_code != 200:
                if is_form:
                    return await ctx.send(f"Form data not found for `{pokemon_id}`.")
                else:
                    return await ctx.send(f"Pokemon `{pokemon_id}` not found.")

            try:
                data = response.json()
                if is_form:
                    await self.send_form_pokemon(ctx, data)
                else:
                    await self.send_pokemon_info(
                        ctx,
                        data,
                        type="mega" if is_mega else "shiny" if is_shiny else None,
                        color=primary_color,
                    )

                
                pokemon_data[str(pokemon_id)] = data

                with open(file_path, "w") as file:
                    json.dump(pokemon_data, file)

            except json.JSONDecodeError:
                if isinstance(pokemon_id, int):
                    await ctx.send(f"Failed to parse JSON data for `{pokemon_id}`.")

    async def send_pokemon_info(self, ctx, data, type, color):
        name = data["name"].capitalize()
        id = data["id"]

        types = [t["type"]["name"].capitalize() for t in data["types"]]
        pokemon_type_unformatted = types

        formatted_types = "\n".join(types)

        abilities = [a["ability"]["name"].capitalize()
                     for a in data["abilities"]]

        pokemon_name = name
        base_url = "https://pokeapi.co/api/v2/pokemon-species/"
        if type == "mega":
            print("Getting Mega Evolution")
            mega_url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}-mega"
            mega_response = requests.get(mega_url)
            print(requests.get(mega_url))
            if mega_response.status_code == 200:
                try:
                    mega_data = mega_response.json()
                    data_species = mega_response.json()  

                except json.JSONDecodeError:
                    await ctx.send(
                        f"Failed to parse JSON data for mega evolution of `{pokemon_name}`."
                    )
            else:
                await ctx.send(f"Mega evolution data not found for `{pokemon_name}`.")
        else:
            print("Getting Basic Pokemon")
            url = f"{base_url}{pokemon_name.lower()}/"
            response_species = requests.get(url)
            if response_species.status_code != 200:
                
                url = f"https://pokeapi.co/api/v2/pokemon-form/{pokemon_name.lower()}/"
                form_response = requests.get(url)
                if form_response.status_code == 200:
                    data_species = form_response.json()
            else:
                data_species = response_species.json()

        if type == "mega":
            print(f"Pokemon {name} is mega")

        async def title_case_except_all_caps(text):
            words = text.split()
            result = []

            for word in words:
                if word.isupper():
                    result.append(word.title())
                else:
                    result.append(word)

            return " ".join(result)

        async def get_pokemon_info(data_species, pokemon_name):
            try:
                flavor = data_species["flavor_text_entries"][0]["flavor_text"]
                english_flavor = next(
                    (
                        entry["flavor_text"]
                        for entry in data_species["flavor_text_entries"]
                        if entry["language"]["name"] == "en"
                    ),
                    None,
                )

                if english_flavor:
                    flavor = english_flavor
                    formatted_flavor = " ".join(flavor.split())
                    formatted_description = await capitalize_sentences(formatted_flavor)

                    word_replacements = {
                        "POKéMON": "Pokémon",
                        "POKé BALL": "Poké Ball",
                        
                    }

                    formatted_description = await replace_words(
                        formatted_description, word_replacements
                    )

                    return formatted_description
                else:
                    await find_pokemon_description(pokemon_name)
            except Exception as e:
                await find_pokemon_description(pokemon_name)
                print(f"Error: An unexpected error occurred - {e}")

        def get_pokemon_description(
            pokemon_id, file_path="Data/pokemon/pokemon_description.csv"
        ):
            with open(file_path, mode="r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)

                for row in reader:
                    if row["id"] == str(pokemon_id):
                        return row["description"]

            return "Pokémon ID not found"

        def get_pokemon_region(
            pokemon_id, file_path="Data/pokemon/pokemon_description.csv"
        ):
            try:
                with open(file_path, mode="r", encoding="utf-8") as csv_file:
                    reader = csv.DictReader(csv_file)
                    for row in reader:
                        if row["id"] == str(pokemon_id):
                            return row["region"]
            except FileNotFoundError:
                return None
            except PermissionError:
                return None
            except Exception as e:
                print(f"An error occurred: {e}")
                return None
            return None

        def get_pokemon_alternate_names(data_species, pokemon_name):
            try:
                if data_species:
                    alternate_names = [
                        (name["name"], name["language"]["name"])
                        for name in data_species["names"]
                    ]
                    return alternate_names
                else:
                    print(f"Error: Unable to retrieve data for {pokemon_name}")
                    return None
            except KeyError:
                return None  

        region = get_pokemon_region(id) or None

        pokemon_description = get_pokemon_description(id)

        species_url = data["species"]["url"]
        species_data = requests.get(species_url).json()
        species_name = species_data["name"]

        if type == "shiny":
            image_url = data["sprites"]["other"]["official-artwork"]["front_shiny"]
            image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"][
                "animated"
            ]["front_shiny"]
        elif type == "mega":
            print("Getting Mega Evolution")
            mega_url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}-mega"
            mega_response = requests.get(mega_url)
            print(requests.get(mega_url))
            if mega_response.status_code == 200:
                try:
                    mega_data = mega_response.json()
                    
                    data = mega_data
                    image_url = mega_data["sprites"]["other"]["official-artwork"][
                        "front_default"
                    ]
                    image_thumb = mega_data["sprites"]["versions"]["generation-v"][
                        "black-white"
                    ]["animated"]["front_default"]
                except json.JSONDecodeError:
                    await ctx.send(
                        f"Failed to parse JSON data for mega evolution of `{pokemon_name}`."
                    )
            else:
                await ctx.send(f"Mega evolution data not found for `{pokemon_name}`.")
        else:
            image_url = data["sprites"]["other"]["official-artwork"]["front_default"]
            image_thumb = data["sprites"]["versions"]["generation-v"]["black-white"][
                "animated"
            ]["front_default"]

        height, weight = (
            float(int(data["height"])) / 10,
            float(int(data["weight"])) / 10,
        )
        max_stat = 255
        bar_length = 13  
        fixed_bar_length = 13

        
        stat_name_mapping = {
            "hp": "Hp",
            "special-attack": "Sp. Atk",
            "special-defense": "Sp. Def",
        }

        
        bar_symbols = {
            0: {
                "front": "<:__:1194757522041618572>",
                "mid": "<:__:1194758504490205364>",
                "end": "<:__:1194758898721239040>",
            },
            1: {
                "front": "<:__:1194759037024206859>",
                "mid": "<:__:1194759109401133136>",
                "end": "<:__:1194759199071141999>",
            },
        }
        
        
        base_stats = [
            f"{str(stat_name_mapping.get(stat['stat']['name'], stat['stat']['name']).title()).replace('Hp', 'Health'):<10} {str(stat['base_stat']):>5} {'▒' * int(stat['base_stat'] / max_stat * bar_length)}{'░' * (bar_length - int(stat['base_stat'] / max_stat * bar_length))}"
            for stat in data["stats"]
        ]
        formatted_base_stats = "\n".join(base_stats)

        _base_stats = [
            f"**{str(stat_name_mapping.get(stat['stat']['name'], stat['stat']['name']).title()).replace('Hp', 'HP')}:** {str(stat['base_stat'])}"
            for stat in data["stats"]
        ]
        basic_base_stats = "\n".join(_base_stats)

        mot = ctx.guild.get_member(ctx.bot.user.id)
        

        def get_pokemon_species_data(name):
            response = requests.get(
                f"https://pokeapi.co/api/v2/pokemon-species/{name.lower()}"
            )
            if response.status_code == 200:
                species_data = response.json()
                return species_data
            else:
                return None

        language_codes = ["ja", "ja", "ja", "en", "de", "fr"]
        
        flag_mapping = {
            "en": "🇬🇧",
            "fr": "🇫🇷",
            "es": "🇪🇸",
            "de": "🇩🇪",
            "it": "🇮🇹",
            "ja": "🇯🇵",
            "ko": "🇰🇷",
            "zh-Hans": "🇨🇳",
            "ru": "🇷🇺",
            "es-MX": "🇲🇽",
            "pt": "🇵🇹",
            "nl": "🇳🇱",
            "tr": "🇹🇷",
            "ar": "🇸🇦",
            "th": "🇹🇭",
            "vi": "🇻🇳",
            "pl": "🇵🇱",
            "sv": "🇸🇪",
            "da": "🇩🇰",
            "no": "🇳🇴",
            "fi": "🇫🇮",
            "el": "🇬🇷",
            "id": "🇮🇩",
            "ms": "🇲🇾",
            "fil": "🇵🇭",
            "hu": "🇭🇺",
            "cs": "🇨🇿",
            "sk": "🇸🇰",
            "ro": "🇷🇴",
            "uk": "🇺🇦",
            "hr": "🇭🇷",
            "bg": "🇧🇬",
            "et": "🇪🇪",
            "lv": "🇱🇻",
            "lt": "🇱🇹",
            "sl": "🇸🇮",
            "mt": "🇲🇹",
            "sq": "🇦🇱",
            "mk": "🇲🇰",
            "bs": "🇧🇦",
            "sr": "🇷🇸",
            "cy": "🇨🇾",
            "ga": "🇮🇪",
            "gd": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
            "kw": "🇰🇾",
            "br": "🇧🇷",
            "af": "🇿🇦",
            "xh": "🇿🇦",
            "zu": "🇿🇦",
            "tn": "🇿🇦",
            "st": "🇿🇦",
            "ss": "🇿🇦",
            "nr": "🇿🇦",
            "nso": "🇿🇦",
            "ts": "🇿🇦",
            "ve": "🇿🇦",
            "xog": "🇺🇬",
            "lg": "🇺🇬",
            "ak": "🇬🇭",
            "tw": "🇬🇭",
            "bm": "🇧🇫",
            "my": "🇲🇲",
            "km": "🇰🇭",
            "lo": "🇱🇦",
            "am": "🇪🇹",
            "ti": "🇪🇹",
            "om": "🇪🇹",
            "so": "🇸🇴",
            "sw": "🇰🇪",
            "rw": "🇷🇼",
            "yo": "🇳🇬",
            "ig": "🇳🇬",
            "ha": "🇳🇬",
            "bn": "🇧🇩",
            "pa": "🇮🇳",
            "gu": "🇮🇳",
            "or": "🇮🇳",
            "ta": "🇮🇳",
            "te": "🇮🇳",
            "kn": "🇮🇳",
            "ml": "🇮🇳",
            "si": "🇱🇰",
            "ne": "🇳🇵",
            "dz": "🇧🇹",
            "ti": "🇪🇷",
            "be": "🇧🇾",
            "kk": "🇰🇿",
            "uz": "🇺🇿",
            "ky": "🇰🇬",
        }

        
        alternate_names = get_pokemon_alternate_names(
            data_species, species_name)

        desired_pokemon = name  

        if alternate_names:
            alt_names_info = {}

            for name, lang in alternate_names:
                
                key = name.lower()

                flag = flag_mapping.get(
                    lang, None
                )  

                
                if name.lower() != lang.lower() and flag is not None:
                    if key not in alt_names_info:
                        alt_names_info[key] = f"{flag} {name}"

            
            name_list = sorted(
                list(alt_names_info.values()), key=lambda x: x.split(" ")[-1]
            )

            
            alt_names_str = "\n".join(name_list[:6])

        else:
            alt_names_str = "No alternate names available."
            print(alt_names_str)

        def organize_pokemon_names_by_region(pokemon_name):
            region = get_pokemon_region(data_species, pokemon_name)

            if region:
                result = f"Region: {region.capitalize()}\n"

                
                alternate_names = get_pokemon_alternate_names(
                    data_species, pokemon_name
                )

                if alternate_names:
                    alt_names_info = {}

                    for name, lang in alternate_names:
                        key = name.lower()

                        flag = flag_mapping.get(lang, None)
                        if key not in alt_names_info and flag is not None:
                            alt_names_info[key] = f"{flag} {name.capitalize()}"

                    name_list = sorted(
                        list(alt_names_info.values()),
                        key=lambda x: x.split(" ")[1],
                        reverse=True,
                    )
                    alt_names_str = "\n".join(f"`{name_list}`")

                    result += alt_names_str
                else:
                    result += "No alternate names available."
            else:
                result = "Region information not available."

            return result

        p = organize_pokemon_names_by_region(name)

        print(p)

        async def get_type_chart(max_retries=3):
            url = "https://pokeapi.co/api/v2/type"

            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                type_chart = {}
                                types_data = (await response.json())["results"]

                                for type_data in types_data:
                                    type_name = type_data["name"]
                                    effectiveness_url = type_data["url"]

                                    async with session.get(
                                        effectiveness_url
                                    ) as effectiveness_response:
                                        if effectiveness_response.status == 200:
                                            damage_relations = (
                                                await effectiveness_response.json()
                                            )["damage_relations"]
                                            type_chart[type_name] = {
                                                "double_damage_to": [],
                                                "half_damage_to": [],
                                                "no_damage_to": [],
                                                "double_damage_from": [],
                                                "half_damage_from": [],
                                                "no_damage_from": [],
                                            }

                                            for key, values in damage_relations.items():
                                                for value in values:
                                                    type_chart[type_name][key].append(
                                                        value["name"]
                                                    )

                                return type_chart
                            else:
                                
                                print(
                                    f"Error: HTTP request failed with status code {response.status}"
                                )
                                return None
                except aiohttp.ClientError as e:
                    print(f"Error: aiohttp client error - {e}")
                except Exception as e:
                    print(f"Error: An unexpected error occurred - {e}")

                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)

        def find_pokemon_weaknesses(pokemon_info, type_chart):
            if pokemon_info is None:
                print("Failed to retrieve Pokemon info.")
                return None, None

            types = [t["type"]["name"] for t in pokemon_info["types"]]

            weaknesses = set()
            strengths = set()

            for pokemon_type in types:
                weaknesses.update(
                    type_chart.get(pokemon_type, {}).get(
                        "double_damage_from", [])
                )
                strengths.update(
                    type_chart.get(pokemon_type, {}).get(
                        "double_damage_to", [])
                )

            weaknesses.discard("")

            
            weaknesses = {weakness.capitalize() for weakness in weaknesses}
            strengths = {strength.capitalize() for strength in strengths}

            return weaknesses, strengths

        type_chart = await get_type_chart()

        def get_pokemon_gender_ratio_display(data_species):
            try:
                
                gender_rate = data_species["gender_rate"]

                
                
                
                
                if gender_rate == -1:
                    return "Genderless"
                elif gender_rate == 0:
                    return "♂️ Male only"
                else:
                    female_ratio = (8 - gender_rate) / 8
                    male_ratio = gender_rate / 8
                    male_percentage = int(female_ratio * 100)
                    female_percentage = int(male_ratio * 100)
                    if female_percentage == 100:
                        return "♀️ Female only"
                    elif male_percentage == 100:
                        return "♂️ Male only"

                    

                    
                    
                    gender_ratio_display = (
                        f"♂ {male_percentage}% - ♀ {female_percentage}%"
                    )

                    return gender_ratio_display
            except KeyError:
                return None  

        gender = get_pokemon_gender_ratio_display(data_species) or None

        def determine_pokemon_category(data_species):
            try:
                pokemon_info = data_species

                if pokemon_info:
                    if pokemon_info["is_legendary"]:
                        return "Legendary"
                    elif pokemon_info["is_mythical"]:
                        return f"Mythical"
                    else:
                        flavor_text_entries = pokemon_info["flavor_text_entries"]
                        english_flavor = next(
                            (
                                entry["flavor_text"]
                                for entry in flavor_text_entries
                                if entry["language"]["name"] == "en"
                            ),
                            None,
                        )
                        if english_flavor and "ultra beast" in english_flavor.lower():
                            return f"Ultra Beast"
                        else:
                            return None
                else:
                    return None
            except KeyError:
                return None  

        rarity = determine_pokemon_category(data_species) or None

        if pokemon_description != " ":
            embed = discord.Embed(
                title=(
                    f" #{id} — {species_name.title()}"
                    if type != "shiny"
                    else f" #{id} — ✨ {species_name.title()}"
                ),
                description=f"\n{pokemon_description}\n",
                color=color,
            )  
        else:
            embed = discord.Embed(
                title=(
                    f" #{id} — {species_name.title()}"
                    if type != "shiny"
                    else f" #{id} — ✨ {species_name.title()}"
                ),
                color=color,
            )

        pokemon_dex_name = (
            f" #{id} — {species_name.title()}"
            if type != "shiny"
            else f" #{id} — ✨ {species_name.title()}"
        )
        embed.set_image(url=image_url)
        description = (
            f"\n{pokemon_description}\n" if pokemon_description != " " else None
        )

        

        """
      [Gender] [Apperence]
     
      [Rarity] [Region]    [Names] 
     
     
      [Names]

    
     """
        type_chart = await get_type_chart()
        pokemon_info = data
        weaknesses, strengths = find_pokemon_weaknesses(
            pokemon_info, type_chart)
        label_width = max(len("Type"), len("Weaknesses"), len("Strengths"))

        result = "● Strengths\n" "{2}" "{3}\n\n" "● Weaknesses\n" "{4}" "{5}"
        weaknesses = list(weaknesses)
        strengths = list(strengths)

        if len(weaknesses) == 1:
            weaknesses_formatted = f"╚ {weaknesses[0]}"
        else:
            weaknesses_formatted = "\n".join(
                [f"╠ {weakness}" for weakness in weaknesses[:-1]]
            ) + (f"\n╚ {weaknesses[-1]}" if weaknesses else "╚ None")
        if len(strengths) == 1:
            strengths_formatted = f"╚ {strengths[0]}"
        else:
            strengths_formatted = "\n".join(
                [f"╠ {strength}" for strength in strengths[:-1]]
            ) + (f"\n╚ {strengths[-1]}" if strengths else "╚ None")
        wes = result.format("", "", strengths_formatted,
                            "", weaknesses_formatted, "")

        pokemon_type_result = "● Type\n" "{2}\n\n"
        if len(pokemon_type_unformatted) == 1:
            pokemon_types_formatted = f"╚ {pokemon_type_unformatted[0]}"
        else:
            pokemon_types_formatted = "\n".join(
                [f"╠ {types}" for types in pokemon_type_unformatted[:-1]]
            ) + (
                f"\n╚ {pokemon_type_unformatted[-1]}"
                if pokemon_type_unformatted
                else "╚ None"
            )

        pokemon_type = pokemon_type_result.format(
            "", "", pokemon_types_formatted)
        print(pokemon_type)

        """" Weakness stuff  """
        weaknesses, _ = find_pokemon_weaknesses(pokemon_info, type_chart)

        result = "{0}"

        weaknesses_formatted = (
            "\n".join(
                [
                    f"    {i}. {weakness}"
                    for i, weakness in enumerate(weaknesses, start=1)
                ]
            )
            if weaknesses
            else "None"
        )

        output_weak = result.format(weaknesses_formatted)
        print(output_weak)

        """" Strengths stuff  """
        _, strengths = find_pokemon_weaknesses(pokemon_info, type_chart)

        result = "{0}"

        strengths_formatted = (
            "\n".join(
                [
                    f"    {i}. {strength}"
                    for i, strength in enumerate(strengths, start=1)
                ]
            )
            if strengths
            else "None"
        )

        output_strength = result.format(strengths_formatted)
        print(output_strength)

        s_and_w = wes

        
        region_mappings = {
            "Paldea": "<:Paldea:1212335178714980403>",
            "Sinnoh": "<:Sinnoh:1212335180459544607>",
            "Alola": "<:Alola:1212335185228472411>",
            "Kalos": "<:Kalos:1212335190656024608>",
            "Galar": "<:Galar:1212335192740470876>",
            "Pasio": "<:848495108667867139:1212335194628034560>",
            "Hoenn": "<:Hoenn:1212335197304004678>",
            "Unova": "<:Unova:1212335199095095306>",
            "Kanto": "<:Kanto:1212335202341363713>",
            "Johto": "<:Kanto:1212335202341363713>",
        }
        if region:
            region = region.title()
        else:
            region = None

        appearance_info = [
            f"**Height:** {height:.2f} m",
            f"**Weight:** {weight:.2f} kg",
        ]
        appearance = "\n".join(appearance_info)

        

        if region is not None:
            if region in region_mappings:
                region_emoji = region_mappings[region]
                embed.add_field(
                    name="Region", value=f"{region_emoji} {region}", inline=True
                )
                region = f"{region_emoji} {region}" or region

        embed.add_field(name="Names", value=alt_names_str, inline=True)

        if gender is not None:
            gender_differ = bool(
                gender != "♀️ Female only" or "♂️ Male only" or "Genderless"
            )
        else:
            gender_differ = False

        
        base_stats = formatted_base_stats

        

        appearance = (
            f"Height: {height:.2f} m\nWeight: {weight:.2f} kg\t\t"
            if gender is not None and gender != "♂ 50% - ♀ 50%"
            else f"Height: {height:.2f} m\nWeight: {weight:.2f} kg"
        )

        gender_info = None

        if image_thumb:
            embed.set_footer(icon_url=image_thumb, text=appearance)
            gender_info = None
            if gender is not None and gender != "♂ 50% - ♀ 50%":
                embed.set_footer(
                    icon_url=image_thumb, text=appearance + f"Gender: {gender}"
                )
                appearance_footer = embed.set_footer(
                    icon_url=image_thumb, text=appearance + f"Gender: {gender}"
                )
                gender_info = f"Gender: {gender}"

        else:
            if type == "shiny":
                image_thumb = data["sprites"]["versions"]["generation-v"][
                    "black-white"
                ]["front_shiny"]
            else:
                image_thumb = data["sprites"]["versions"]["generation-v"][
                    "black-white"
                ]["front_default"]

            if image_thumb:
                embed.set_footer(icon_url=image_thumb, text=appearance)
            else:
                image_thumb = None
                embed.set_footer(text=appearance)

            if gender and rarity is not None and gender != "♂ 50% - ♀ 50%":
                embed.set_footer(
                    icon_url=image_thumb,
                    text=f"Rarity: {rarity}\n\n" +
                    appearance + f"Gender: {gender}",
                )
                appearance_footer = embed.set_footer(
                    icon_url=image_thumb,
                    text=f"Rarity: {rarity}\n\n" +
                    appearance + f"Gender: {gender}",
                )
                gender_info = f"Gender: {gender}"

            elif gender is not None and gender != "♂ 50% - ♀ 50%":
                embed.set_footer(
                    icon_url=image_thumb, text=appearance + f"Gender: {gender}"
                )
                appearance_footer = embed.set_footer(
                    icon_url=image_thumb, text=appearance + f"Gender: {gender}"
                )
                gender_info = f"Gender: {gender}"

        h_w = f"Height: {height:.2f} m\nWeight: {weight:.2f} kg"
        print("is_shiny: ", type)
        self.bot.add_view(Pokebuttons(alt_names_str, species_name))

        await ctx.reply(
            embed=embed,
            view=Pokebuttons(
                alt_names_str,
                species_name,
                formatted_base_stats,
                type,
                wes,
                pokemon_type,
                base_stats,
                image_url,
                h_w,
                image_thumb,
                pokemon_dex_name,
                color,
                data,
                gender_differ,
                region,
                description,
                gender_info,
                self.bot
            ),
            mention_author=False,
        )


class Pokebuttons(discord.ui.View):
    def __init__(
        self,
        alt_names_str=None,
        name=None,
        formatted_base_stats=None,
        type=None,
        wes=None,
        pokemon_type=None,
        base_stats=None,
        image_url=None,
        h_w=None,
        image_thumb=None,
        pokemon_dex_name=None,
        color=None,
        pokemon_data=None,
        gender_differ=None,
        region=None,
        description=None,
        gender_info=None,
        bot=None
    ):
        super().__init__(timeout=None)
        self.alt_names_str = alt_names_str
        self.pokemon_name = name
        self.pokemon_shiny = type
        self.formatted_base_stats = formatted_base_stats
        self.s_and_w = wes
        self.pokemon_type = pokemon_type
        self.base_stats = base_stats
        self.image_url = image_url
        self.height_and_weight = h_w
        self.image_thumb = image_thumb
        self.pokemon_dex_name = pokemon_dex_name
        self.color = color
        self.pokemon_data = pokemon_data
        self.gender_differ = gender_differ
        self.region = region
        self.description = description
        self.gender_info = gender_info
        self.bot = bot


        
        pokemon_forms = self.get_pokemon_forms()

        if pokemon_forms and len(pokemon_forms) > 1:
            self.add_item(
                PokeSelect(
                    pokemon_forms,
                    self.image_url,
                    self.alt_names_str,
                    self.pokemon_shiny,
                    self.gender_info,
                    self.bot
                )
            )

        
        self.POKEMON_DIR = "Data/pokemon"
        os.makedirs(self.POKEMON_DIR, exist_ok=True)
        self.POKEMON_IMAGES_FILE = os.path.join(
            self.POKEMON_DIR, "pokemon_images.txt")

        if not os.path.exists(self.POKEMON_IMAGES_FILE):
            with open(self.POKEMON_IMAGES_FILE, "w") as file:
                file.write("")  

        
        self.pokemon_images = self.load_pokemon_images()

    def get_pokemon_forms(self):
        url = f"https://pokeapi.co/api/v2/pokemon-species/{self.pokemon_name.lower()}"
        print(f"Requesting forms for {self.pokemon_name} from URL: {url}")
        response = requests.get(url)
        print(f"Response status code: {response.status_code}")
        if response.status_code == 200:
            forms = response.json().get("varieties", [])
            form_details = []

            for form in forms:
                form_name = form["pokemon"]["name"]
                form_url = f"https://pokeapi.co/api/v2/pokemon/{form_name.lower()}"
                form_details.append({"name": form_name, "url": form_url})

            return form_details

        return []

    def load_pokemon_images(self):
        pokemon_images = {}
        try:
            with open(self.POKEMON_IMAGES_FILE, "r") as file:
                for line in file:
                    pokemon_name, image_link = line.strip().split(":", 1)
                    pokemon_images[self.pokemon_name.lower()
                                   ] = image_link.strip()
        except FileNotFoundError:
            print(f"Error: {self.POKEMON_IMAGES_FILE} not found")
        return pokemon_images

    async def on_button_click(self, interaction: discord.Interaction):
        selected_button_id = interaction.data["custom_id"]
        print(f"Selected button ID: {selected_button_id}")
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == selected_button_id:
                    child.style = discord.ButtonStyle.blurple
                else:
                    child.style = discord.ButtonStyle.blurple

        if selected_button_id == "Pokemon_Male_Button":
            await self.show_gender_image(interaction, "male")
        elif selected_button_id == "Pokemon_Female_Button":
            await self.show_gender_image(interaction, "female")

    async def show_gender_image(self, interaction: discord.Interaction, gender):
        if gender == "male":
            
            male_button = self.children[0]
            female_button = self.children[
                1
            ]  
        else:
            
            male_button = self.children[1]
            female_button = self.children[
                0
            ]  

        try:
            print(f"Male Button ID: {male_button.custom_id}")
            print(f"Female Button ID: {female_button.custom_id}")

            if gender == "male":
                image_url = self.pokemon_data["sprites"]["other"]["official-artwork"][
                    "front_default"
                ]
                print(image_url)
            else:
                
                pokemon_name_lower = self.pokemon_name.lower()
                if pokemon_name_lower in self.pokemon_images:
                    image_url = self.pokemon_images[pokemon_name_lower]
                else:
                    image_url = self.pokemon_images["front_female"]

            embed = interaction.message.embeds[0]
            embed.set_image(url=image_url)
            await interaction.response.edit_message(embed=embed)

            
            male_button.style = discord.ButtonStyle.blurple
            female_button.style = discord.ButtonStyle.gray

            print("Button colors changed successfully.")

        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(
        label="Evolves",
        style=discord.ButtonStyle.gray,
        custom_id="Pokemon_Evolutions_Button",
        row=1,
    )
    async def show_evolutions_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        
        try:
            await self.show_evolutions(button)
        except requests.exceptions.RequestException as e:
            await interaction.response.send_message(
                f"Error fetching Pokémon evolution chain: {str(e)}", ephemeral=True
            )

    async def show_evolutions(self, interaction: discord.Interaction):
        try:
            
            evolution_chain_data = await self.get_pokemon_evolution_chain(
                self.pokemon_name
            )

            if not evolution_chain_data:
                await interaction.response.send_message(
                    f"No evolution chain found for {self.pokemon_name.title()}.",
                    ephemeral=True,
                )
                
                self.disabled = True
                await interaction.message.edit(view=self.view)
                return

            
            embeds = await self.display_evolution_chain(evolution_chain_data)
            await interaction.response.send_message(embeds=embeds, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"Error fetching Pokémon evolution chain: {str(e)}", ephemeral=True
            )

    @staticmethod
    async def get_pokemon_evolution_chain(pokemon_name):
        async with aiohttp.ClientSession() as session:
            species_url = (
                f"https://pokeapi.co/api/v2/pokemon-species/{pokemon_name.lower()}/"
            )
            async with session.get(species_url) as response:
                if response.status != 200:
                    raise Exception(
                        f"Error fetching species data for {pokemon_name}")

                species_data = await response.json()
                evolution_chain_url = species_data.get(
                    "evolution_chain", {}).get("url")

                if not evolution_chain_url:
                    raise Exception(
                        f"No evolution chain found for {pokemon_name}")

            async with session.get(evolution_chain_url) as response:
                if response.status != 200:
                    raise Exception(
                        f"Error fetching evolution chain data for {pokemon_name}"
                    )

                evolution_chain_data = await response.json()
                return evolution_chain_data.get("chain")

    async def display_evolution_chain(self, chain):
        embeds = []
        queue = [chain]
        final_forms = set()  

        while queue:
            current_chain = queue.pop(0)
            species_name = current_chain["species"]["name"].title()

            
            if not current_chain.get("evolves_to"):
                final_forms.add(species_name)
                continue

            for evolution in current_chain["evolves_to"]:
                details = evolution["evolution_details"][0]
                next_pokemon_name = evolution["species"]["name"].title()
                method = await self.determine_evolution_method(
                    species_name, details, next_pokemon_name
                )

                if method:
                    embed = await self.create_pokemon_embed(
                        species_name, method, next_pokemon_name
                    )
                    embeds.append(embed)

                
                queue.append(evolution)

        
        if final_forms:
            for final_form in final_forms:
                embed = await self.create_pokemon_embed(
                    final_form, "is the final form", final_form
                )
                embeds.append(embed)

        return embeds

    @staticmethod
    async def determine_evolution_method(
        current_pokemon, evolution_details, next_pokemon
    ):
        trigger = evolution_details.get("trigger", {}).get("name")
        item = evolution_details.get("item")
        known_move_type = evolution_details.get("known_move_type")
        time_of_day = evolution_details.get("time_of_day")
        min_level = evolution_details.get("min_level")
        min_happiness = evolution_details.get("min_happiness")
        method = ""

        if trigger == "level-up":
            
            if known_move_type:
                method += f"when leveled up while knowing a {known_move_type['name'].replace('-', ' ').title()} move"
            else:
                method = f"when leveled up"
                if time_of_day:
                    method += f" at {time_of_day.title()} time"
                if min_level:
                    method += f" starting from level {min_level}"
                if min_happiness:
                    method += " while holding a Friendship Bracelet"
        elif trigger == "use-item":
            
            if item:
                method = f"using a {item['name'].replace('-', ' ').title()}"
        elif trigger == "trade":
            
            if item:
                method = (
                    f"when traded holding a {item['name'].replace('-', ' ').title()}"
                )
            else:
                method = f"when traded"

        return method

    async def create_pokemon_embed(self, current_pokemon, method, next_pokemon):
        embed = discord.Embed()
        sprite_url = (
            f"https://pokemonshowdown.com/sprites/dex/{current_pokemon.lower()}.png"
        )
        print("create_pokemon_embed: ", self.pokemon_type)
        if self.pokemon_shiny:
            sprite_url = f"https://pokemonshowdown.com/sprites/dex-shiny/{current_pokemon.lower()}.png"

        embed.set_thumbnail(url=sprite_url)

        if current_pokemon == next_pokemon:
            
            embed.description = f"```{current_pokemon} is the final form.```"
        else:
            
            embed.description = (
                f"```{current_pokemon} evolves into {next_pokemon} {method}```"
            )

        return embed

    @discord.ui.button(
        label="Stats", style=discord.ButtonStyle.gray, custom_id="Pokemon_Stats", row=1
    )
    async def s_and_w(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        embed = discord.Embed(color=self.color)
        embed.add_field(
            name="Base Stats", value=f"```py\n{self.base_stats}```", inline=False
        )
        
        strength_weakness = "```" + self.pokemon_type + self.s_and_w + "```"
        if self.pokemon_type != "shiny":
            image = f"https://pokemonshowdown.com/sprites/dex/{self.pokemon_name}.png"
        else:
            image = (
                f"https://pokemonshowdown.com/sprites/dex-shiny/{self.pokemon_name}.png"
            )
        
        if self.image_thumb is None:
            embed.set_footer(text=self.pokemon_dex_name)
        else:
            embed.set_footer(icon_url=self.image_thumb,
                             text=self.pokemon_dex_name)

        embed.set_thumbnail(url=self.image_url)

        thumbnail = self.image_url
        footer = self.image_thumb
        footer_text = self.pokemon_dex_name
        pokemon_data = self.pokemon_data
        color = self.color

        await button.response.send_message(
            embed=embed,
            view=Strength_weakness(
                color, strength_weakness, thumbnail, footer, footer_text, pokemon_data
            ),
            ephemeral=True,
        )

class RegionFlagMapping:
    def __init__(self):
        self.region_mappings = {
            "paldea": "<:Paldea:1212335178714980403>",
            "sinnoh": "<:Sinnoh:1212335180459544607>",
            "alola": "<:Alola:1212335185228472411>",
            "kalos": "<:Kalos:1212335190656024608>",
            "galar": "<:Galar:1212335192740470876>",
            "pasio": "<:848495108667867139:1212335194628034560>",
            "hoenn": "<:Hoenn:1212335197304004678>",
            "unova": "<:Unova:1212335199095095306>",
            "kanto": "<:Kanto:1212335202341363713>",
            "johto": "<:Johto:1212335202341363713>",
        }

        self.flag_mapping = {
            "en": "🇬🇧",
            "fr": "🇫🇷",
            "es": "🇪🇸",
            "de": "🇩🇪",
            "it": "🇮🇹",
            "ja": "🇯🇵",
            "ko": "🇰🇷",
            "zh-Hans": "🇨🇳",
            "ru": "🇷🇺",
            "es-MX": "🇲🇽",
            "pt": "🇵🇹",
            "nl": "🇳🇱",
            "tr": "🇹🇷",
            "ar": "🇸🇦",
            "th": "🇹🇭",
            "vi": "🇻🇳",
            "pl": "🇵🇱",
            "sv": "🇸🇪",
            "da": "🇩🇰",
            "no": "🇳🇴",
            "fi": "🇫🇮",
            "el": "🇬🇷",
            "id": "🇮🇩",
            "ms": "🇲🇾",
            "fil": "🇵🇭",
            "hu": "🇭🇺",
            "cs": "🇨🇿",
            "sk": "🇸🇰",
            "ro": "🇷🇴",
            "uk": "🇺🇦",
            "hr": "🇭🇷",
            "bg": "🇧🇬",
            "et": "🇪🇪",
            "lv": "🇱🇻",
            "lt": "🇱🇹",
            "sl": "🇸🇮",
            "mt": "🇲🇹",
            "sq": "🇦🇱",
            "mk": "🇲🇰",
            "bs": "🇧🇦",
            "sr": "🇷🇸",
            "cy": "🇨🇾",
            "ga": "🇮🇪",
            "gd": "🏴",
            "kw": "🇰🇾",
            "br": "🇧🇷",
            "af": "🇿🇦",
            "xh": "🇿🇦",
            "zu": "🇿🇦",
            "tn": "🇿🇦",
            "st": "🇿🇦",
            "ss": "🇿🇦",
            "nr": "🇿🇦",
            "nso": "🇿🇦",
            "ts": "🇿🇦",
            "ve": "🇿🇦",
            "xog": "🇺🇬",
            "lg": "🇺🇬",
            "ak": "🇬🇭",
            "tw": "🇬🇭",
            "bm": "🇧🇫",
            "my": "🇲🇲",
            "km": "🇰🇭",
            "lo": "🇱🇦",
            "am": "🇪🇹",
            "ti": "🇪🇹",
            "om": "🇪🇹",
            "so": "🇸🇴",
            "sw": "🇰🇪",
            "rw": "🇷🇼",
            "yo": "🇳🇬",
            "ig": "🇳🇬",
            "ha": "🇳🇬",
            "bn": "🇧🇩",
            "pa": "🇮🇳",
            "gu": "🇮🇳",
            "or": "🇮🇳",
            "ta": "🇮🇳",
            "te": "🇮🇳",
            "kn": "🇮🇳",
            "ml": "🇮🇳",
            "si": "🇱🇰",
            "ne": "🇳🇵",
            "dz": "🇧🇹",
            "ti": "🇪🇷",
            "be": "🇧🇾",
            "kk": "🇰🇿",
            "uz": "🇺🇿",
            "ky": "🇰🇬",
        }
        




        
class PokeSelect(discord.ui.Select):
    def __init__(
        self, pokemon_forms, default_image_url, alt_names, pokemon_shiny, gender, bot
    ):
        self.emoji_mapping = self.load_emoji_mapping()
        self.pokemon_df = pd.read_csv("Data/pokemon/pokemon_description.csv")
        self.emoji_json_path = os.path.join("Data", "pokemon", "pokemon_emojis.json")
        self.bot = bot
        
        options = []
        for index, form in enumerate(pokemon_forms):
            form_name = form["name"]
            formatted_name  = self.format_pokemon_name(form_name)
            pokemon_id = self.get_pokemon_id(form_name)
            description = self.get_pokemon_description_first(form_name)
            emo = Pokemon_Emojis(bot=self.bot)
            emoji = emo.call_emoji(self.emoji_mapping, pokemon_id)

            form_url = f"https://pokeapi.co/api/v2/pokemon/{form_name.lower()}"
            
            # Correct way to add emoji to SelectOption
            option = discord.SelectOption(
                label=formatted_name,
                value=form_url,
                description=f"{description[:50]}...",
                emoji=emoji
            )
            options.append(option)
        
        super().__init__(
            placeholder="Form", options=options, custom_id="Select_Pokemon_Form"
        )
        self.default_image_url = default_image_url
        self.alt_names = alt_names
        self.pokemon_type = pokemon_shiny
        self.gender = gender

        self.region_flag_mapping = RegionFlagMapping()
        self.region_mappings = self.region_flag_mapping.region_mappings
        self.flag_mapping = self.region_flag_mapping.flag_mapping
          
    def get_flag(self, lang):
        return self.flag_mapping.get(lang)
    
    def get_pokemon_id(self, form_name):
        # Fetch pokemon data from PokeAPI
        url = f"https://pokeapi.co/api/v2/pokemon/{form_name.lower()}"
        response = requests.get(url)
        data = response.json()
        # Get pokemon ID from the response
        return {"id": data["id"], "slug": form_name.lower()}

    def get_pokemon_description_first(self, pokemon_name):
      file_path="Data/pokemon/pokemon_description.csv"
      with open(file_path, mode="r", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            if row["slug"].lower() == pokemon_name.lower():  # Match by name (slug)
                return row["description"]

      return "Pokémon not found"

    def format_pokemon_name(self, name):
     """Format Pokemon names by handling forms like Alolan Vulpix, Gigantamax, etc."""
     # Handle specific cases for formatting like "vulpix-alola" -> "Alolan Vulpix"
     special_forms = {
        "alola": "Alolan",
        "gmax": "Gigantamax",  # Updated to Gigantamax
        "mega": "Mega",
        "galar": "Galarian",
        "hisui": "Hisuian",
        "kalos": "Kalosian",
        # Add more special forms here as needed
     }

     if "-" in name:
        parts = name.split("-")
        # Capitalize the special form part and then capitalize the rest in reverse order
        formatted_parts = [special_forms.get(parts[1], parts[1].capitalize()), parts[0].capitalize()]
        formatted_name = " ".join(formatted_parts)
        return formatted_name
     else:
        # If there are no hyphens, simply capitalize the name
        return name.capitalize()


    def load_emoji_mapping(self):
        """Load emoji mappings from the JSON file."""
        if os.path.exists("Data/pokemon/pokemon_emojis.json"):
            with open("Data/pokemon/pokemon_emojis.json", "r") as f:
                return json.load(f)
        else:
            return {}
    @staticmethod
    def get_pokemon_description(
        pokemon_id, file_path="Data/pokemon/pokemon_description.csv"
    ):
        try:
            with open(file_path, mode="r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    if row["id"] == str(pokemon_id):
                        return row["description"]
        except FileNotFoundError:
            return "File not found"
        except PermissionError:
            return "Permission denied"
        except Exception as e:
            print(f"An error occurred: {e}")
            return f"An error occurred: {e}"
        return "Pokémon ID not found"

    @staticmethod
    def get_pokemon_region(
        pokemon_id, file_path="Data/pokemon/pokemon_description.csv"
    ):
        try:
            with open(file_path, mode="r", encoding="utf-8") as csv_file:
                reader = csv.DictReader(csv_file)
                for row in reader:
                    if row["id"] == str(pokemon_id):
                        return row["region"]
        except FileNotFoundError:
            return None
        except PermissionError:
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None
        return None

    def get_alternate_names(self, pokemon_name):
        alternate_names = []
        form_endpoint = f"https://pokeapi.co/api/v2/pokemon-form/{pokemon_name}"
        try:
            response = requests.get(form_endpoint)
            response.raise_for_status()
            data = response.json()
            for name_data in data["names"]:
                lang = name_data["language"]["name"]
                name = name_data["name"]
                flag = self.flag_mapping.get(lang)
                if flag and name.lower() != lang.lower():
                    alternate_names.append((name, lang))
        except requests.exceptions.RequestException:
            species_endpoint = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name}"
            try:
                response = requests.get(species_endpoint)
                response.raise_for_status()
                data = response.json()
                for name_data in data["names"]:
                    lang = name_data["language"]["name"]
                    name = name_data["name"]
                    flag = self.flag_mapping.get(lang)
                    if flag and name.lower() != lang.lower():
                        alternate_names.append((name, lang))
            except requests.exceptions.RequestException as e:
                print(f"Error fetching alternate names: {e}")
        return alternate_names

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_form_url = self.values[0]
        response = requests.get(selected_form_url)

        if response.status_code == 200:
            data = response.json()
            official_artwork_url = None
            if "sprites" in data and "other" in data["sprites"]:
                if "official-artwork" in data["sprites"]["other"]:
                    if self.pokemon_type == "shiny":
                        official_artwork_url = data["sprites"]["other"][
                            "official-artwork"
                        ]["front_shiny"]
                        image_thumb = data["sprites"]["versions"]["generation-v"][
                            "black-white"
                        ]["front_shiny"]
                    else:
                        official_artwork_url = data["sprites"]["other"][
                            "official-artwork"
                        ]["front_default"]
                        image_thumb = data["sprites"]["versions"]["generation-v"][
                            "black-white"
                        ]["front_default"]

            embed = interaction.message.embeds[0]
            if official_artwork_url:
                embed.set_image(url=official_artwork_url)
            else:
                embed.set_image(url=self.default_image_url)

            pokemon_data = requests.get(selected_form_url).json()
            if pokemon_data:
                description = self.get_pokemon_description(pokemon_data["id"])
                height, weight = (
                    float(int(pokemon_data["height"])) / 10,
                    float(int(pokemon_data["weight"])) / 10,
                )
                footer_text = (
                    f"Height: {height:.2f} m\nWeight: {weight:.2f} kg"
                    if self.gender is None
                    else f"Height: {height:.2f} m\nWeight: {weight:.2f} kg\t\t"
                    + self.gender
                )
                embed.title = (
                    f"#{pokemon_data['id']} — {pokemon_data['name'].replace('-', ' ').title()}"
                    if self.pokemon_type != "shiny"
                    else f"#{pokemon_data['id']} — ✨ {pokemon_data['name'].replace('-', ' ').title()}"
                )
                embed.description = description
                if image_thumb:
                    embed.set_footer(icon_url=str(
                        image_thumb), text=footer_text)
                else:
                    embed.set_footer(text=footer_text)

                
                names_field = next(
                    (field for field in embed.fields if field.name == "Names"), None
                )
                if names_field:
                    embed.remove_field(embed.fields.index(names_field))

                embed.clear_fields()  

                
                pokemon_region = self.get_pokemon_region(pokemon_data["id"])
                if pokemon_region and pokemon_region in self.region_mappings:
                    region_emoji = self.region_mappings[pokemon_region]
                    embed.add_field(
                        name="Region",
                        value=f"{region_emoji} {pokemon_region.title()}",
                        inline=True,
                    )

                
                if names_field:
                    alternate_names = self.get_alternate_names(
                        pokemon_data["name"])
                    alt_names_info = {}
                    for name, lang in alternate_names:
                        key = name.lower()
                        flag = self.flag_mapping.get(lang, None)
                        if name.lower() != lang.lower() and flag is not None:
                            name_with_flag = f"{flag} {name}"
                            alt_names_info[key] = name_with_flag

                    sorted_names_by_length = dict(
                        sorted(alt_names_info.items(),
                               key=lambda item: len(item[1]))
                    )

                    if len(sorted_names_by_length) != len(alt_names_info):
                        sorted_names_by_name = dict(
                            sorted(alt_names_info.items(),
                                   key=lambda item: item[1])
                        )
                        name_list = sorted(list(sorted_names_by_name.values()))
                    else:
                        name_list = sorted(
                            list(sorted_names_by_length.values()))

                    alt_names_str = "\n".join(name_list[:6])
                    embed.add_field(
                        name="Names", value=alt_names_str, inline=True)

            await interaction.message.edit(embed=embed)
        else:
            await interaction.response.send_message(
                "Error fetching data for the selected form.", ephemeral=True
            )














class Strength_weakness(discord.ui.View):
    def __init__(
        self,
        color=None,
        strength_weakness_text=None,
        thumbnail_url=None,
        footer=None,
        footer_text=None,
        pokemon_data=None,
    ):
        super().__init__()
        self.color = color
        self.strength_weakness_text = strength_weakness_text
        self.thumbnail_url = thumbnail_url
        self.footer = footer
        self.footer_text = footer_text
        self.pokemon_data = pokemon_data

    @discord.ui.button(
        label="S/W", style=discord.ButtonStyle.gray, custom_id="Pokemon_S_and_W_Button"
    )
    async def strengths_and_weaknesses(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        try:
            embed = discord.Embed(color=self.color)
            embed.add_field(
                name=" ", value=self.strength_weakness_text, inline=False)

            if self.footer is None:
                embed.set_footer(text=self.footer_text)
            else:
                embed.set_footer(icon_url=self.footer, text=self.footer_text)
            embed.set_thumbnail(url=self.thumbnail_url)

            await button.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await button.response.send_message(e, ephemeral=True)

            print(e)
            return

    @discord.ui.button(
        label="Moveset",
        style=discord.ButtonStyle.gray,
        custom_id="Pokemon_Moveset_Button",
    )
    async def moves_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await button.response.defer()
        await self.show_moves(button)

    async def show_moves(self, interaction: discord.Interaction):
        try:
            moves_data = await self.get_pokemon_moves()
            embed = discord.Embed(
                title=f"{self.pokemon_data['name'].title().replace('-', ' ')}'s — Moveset",
                color=self.color,
            )

            for level, move_info in sorted(moves_data.items()):
                move_name = move_info["name"].title().replace("-", " ")
                move_power = move_info["power"]
                move_accuracy = move_info["accuracy"]
                move_effect = move_info["effect"]

                embed.add_field(
                    name=f"(Level {level}) : {move_name}",
                    value=f"`Power:` **{move_power}**\n`Accuracy:` **{move_accuracy}**\n> ```Effect: {move_effect}```",
                    inline=True,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except requests.exceptions.RequestException as e:
            await interaction.followup.send(
                f"Error fetching moves data: {str(e)}", ephemeral=True
            )
        except IndexError:
            await interaction.followup.send(
                "Error: Move data is incomplete or unavailable.", ephemeral=True
            )

    async def get_pokemon_moves(self):
        moves_data = {}
        moves = self.pokemon_data.get("moves", [])
        for move in moves:
            move_name = move["move"]["name"]
            level = [
                version_group_details["level_learned_at"]
                for version_group_details in move["version_group_details"]
            ]
            if level:
                move_url = move["move"]["url"]
                move_data = await self.fetch_move_details(move_url)
                move_power = move_data.get("power", "N/A")
                move_accuracy = move_data.get("accuracy", "N/A")
                move_effect_entries = move_data.get("effect_entries", [])
                move_effect = (
                    move_effect_entries[0]["short_effect"]
                    if move_effect_entries
                    else "N/A"
                )
                moves_data.setdefault(
                    level[0],
                    {
                        "name": move_name,
                        "power": move_power,
                        "accuracy": move_accuracy,
                        "effect": move_effect,
                    },
                )
        return moves_data

    @staticmethod
    async def fetch_move_details(move_url):
        response = requests.get(move_url)
        if response.status_code == 200:
            move_data = response.json()
            return move_data

        return {}


def setup(bot):
    bot.add_cog(Pokemon(bot))
    bot.add_cog(Ping_Pokemon(bot))
    bot.add_cog(Pokemon_Emojis(bot))


