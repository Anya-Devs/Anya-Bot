
import aiohttp
import os, csv, json, re, asyncio
from tqdm import tqdm

from fuzzywuzzy import fuzz
from Imports.log_imports import *
from Imports.discord_imports import *

class Ping_Pokemon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.csv_file = 'data/commands/pokemon/pokemon_special_names.csv'
        self.user_author_id = 854233015475109888                                                   
                                                           
        self.message_rare_pokemon = "<@&1278580577104040023>"
        self.message_regional_pokemon = "<@&1278580577104040022>"
                                                                                                                                  

    def load_pokemon_data(self):
        rare_pokemon = []
        regional_pokemon = []
        
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)                   
                for row in reader:
                    rare_name = row[0].strip()
                    regional_name = row[1].strip()

                    if rare_name:
                        rare_pokemon.append(rare_name.lower())                                        
                    if regional_name:
                        regional_pokemon.append(regional_name.lower())                                            
            
            return rare_pokemon, regional_pokemon
        except FileNotFoundError:
            logger.error(f"CSV file not found: {self.csv_file}")
            return [], []

    def transform_pokemon_name(self, name):
                                               
        translation_map = {
            "alolan": "-alola",
            "galarian": "-galar",
            "hisui": "-hisui",
            "paldean": "-paldea",
            "mega": "-mega"
        }

                                                                                                              
        name_cleaned = re.sub(r'[^a-zA-Z\s]', '', name)                                                

                                                                                 
        name_lower = name_cleaned.lower()
        for region, suffix in translation_map.items():
            if region in name_lower:
                                                                                           
                parts = name_cleaned.split()
                base_name = parts[1].capitalize() if len(parts) > 1 else parts[0].capitalize()                                   
                return f"{base_name.lower()}{suffix}", region                                                   

                                                                                     
        return name_cleaned, None

    @commands.Cog.listener()
    async def on_message(self, message):
                                                           
        if message.author.id != self.user_author_id:
            return

                                                                          
        pattern = re.compile(r"([a-zA-Z\s-]+):\s([\d\.]+)%")
        match = pattern.search(message.content.split("\n")[0].strip())
        
        message_content = message.content
        if match:
            pokemon_name = match.group(1).strip()                                 
            percentage = match.group(2)

            #print(f"Matched Pokémon name: {pokemon_name}, Percentage: {percentage}")

                                                         
            translated_pokemon_name, region = self.transform_pokemon_name(pokemon_name)
        
            translated_pokemon_name = translated_pokemon_name.lower()
                                                   
            rare_pokemon, regional_pokemon = self.load_pokemon_data()

                                                                        
            matched_rare = None
            matched_regional = None
            for rare in rare_pokemon:
                if fuzz.ratio(translated_pokemon_name, rare) > 90:                         
                    matched_rare = rare
                    break

            for regional in regional_pokemon:
                if fuzz.ratio(translated_pokemon_name, regional) > 90:                         
                    matched_regional = regional
                    break

            if matched_rare:
                await message.channel.send(self.message_rare_pokemon)
            elif matched_regional:
                await message.channel.send(self.message_regional_pokemon)
            """
            else:
                await message.channel.send(self.message_unknown_pokemon)
            """


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
        self.POKEMON_IMAGES_FOLDER = "data/commands/pokemon/pokemon_emojis"
        self.POKE_API_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{}.png"
        self.emoji_json_path = "data/commands/pokemon/pokemon_emojis.json"
        self.owner_id = [1124389055598170182,1320515815270907957]
        
        
        self.emoji_mapping = self.load_emoji_mapping()

        os.makedirs(os.path.dirname(self.emoji_json_path), exist_ok=True)
        os.makedirs(self.POKEMON_IMAGES_FOLDER, exist_ok=True)

        self.semaphore = asyncio.Semaphore(5)

    def load_emoji_mapping(self):
        """Load emoji mappings from a JSON file using standard JSON parsing."""
        if os.path.exists(self.emoji_json_path):
            with open(self.emoji_json_path, "r", encoding="utf-8") as f:
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
     """Upload a single emoji to the given server if it isn’t already uploaded."""
     
     existing_emojis = await self.list_existing_emojis(server)
     if str(pokemon_id) in existing_emojis:
        print(f"Emoji for Pokémon ID {pokemon_id} already exists in {server.name}. Skipping upload.")
        return False

     
     if str(server.id) in self.emoji_mapping and str(pokemon_id) in self.emoji_mapping[str(server.id)]:
        print(f"Emoji for Pokémon ID {pokemon_id} is already mapped for {server.name}. Skipping upload.")
        return False

     emoji_image_path = os.path.join(self.POKEMON_IMAGES_FOLDER, f"{pokemon_id}.png")
    
     
     try:
        with open(emoji_image_path, "rb") as emoji_file:
            emoji_data = emoji_file.read()
     except FileNotFoundError:
        print(f"Image for Pokémon ID {pokemon_id} not found at {emoji_image_path}. Attempting to create the emoji image.")
        
        
        await self.create_emoji_image(pokemon_id)
        
        try:
            with open(emoji_image_path, "rb") as emoji_file:
                emoji_data = emoji_file.read()
        except FileNotFoundError:
            print(f"Failed to create the image for Pokémon ID {pokemon_id}. Aborting upload for this emoji.")
            return False

     try:
        
        emoji = await server.create_custom_emoji(name=str(pokemon_id), image=emoji_data)
        if str(server.id) not in self.emoji_mapping:
            self.emoji_mapping[str(server.id)] = {}
        self.emoji_mapping[str(server.id)][str(pokemon_id)] = {"name": str(pokemon_id), "id": emoji.id}
        print(f"Uploaded emoji for Pokémon ID {pokemon_id} in server: {server.name}")

        
        with open(self.emoji_json_path, "w", encoding="utf-8") as f:
            json.dump(self.emoji_mapping, f, indent=4)
        return True

     except discord.errors.HTTPException as e:
        if e.status == 429:
            
            retry_after = int(e.response.headers.get("Retry-After", 60))
            print(f"Rate limited when uploading Pokémon ID {pokemon_id}. Retrying in {retry_after} seconds.")
            await asyncio.sleep(retry_after)
            return await self.upload_single_emoji(server, pokemon_id)  
        else:
            print(f"Error uploading emoji for Pokémon ID {pokemon_id} in server {server.name}: {e}")
     except Exception as e:
        print(f"Error uploading emoji for Pokémon ID {pokemon_id} in server {server.name}: {e}")

     return False
    
    async def create_emoji_image(self, pokemon_id):

     image_url = self.POKE_API_URL.format(pokemon_id)  
     emoji_image_path = os.path.join(self.POKEMON_IMAGES_FOLDER, f"{pokemon_id}.png")

     
     os.makedirs(self.POKEMON_IMAGES_FOLDER, exist_ok=True)

     async with aiohttp.ClientSession() as session:
        async with session.get(image_url) as response:
            if response.status == 200:
                image_data = await response.read()
                with open(emoji_image_path, "wb") as f:
                    f.write(image_data)
                print(f"✅ Successfully downloaded and saved emoji image for Pokémon ID {pokemon_id}.")
            else:
                print(f"❌ Failed to download image for Pokémon ID {pokemon_id} from {image_url}. HTTP Status: {response.status}")
    
    async def upload_emojis_for_server(self, servers, global_existing, max_emojis_per_server=50, embed_message=None, ctx=None, embed=None):
     images = self.load_images()
     total_emojis = len(images)
     emojis_uploaded = 0
     current_server_index = 0

     print(f"Starting emoji upload process. Total images available: {total_emojis}")

     
     for img in images:
        pokemon_id = self.get_pokemon_id(img)
        
        if pokemon_id in global_existing:
            print(f"Skipping Pokémon ID {pokemon_id} as it is already uploaded globally.")
            continue

        
        attempts = 0
        uploaded = False
        while attempts < len(servers) and not uploaded:
            server = servers[current_server_index]
            
            server_emojis = await self.list_existing_emojis(server)
            if len(server_emojis) < max_emojis_per_server:
                uploaded = await self.upload_single_emoji(server, pokemon_id)
                if uploaded:
                    emojis_uploaded += 1
                    
                    await asyncio.sleep(3)
            else:
                print(f"Server {server.name} has reached its emoji capacity. Skipping.")
            
            current_server_index = (current_server_index + 1) % len(servers)
            attempts += 1

        
        await asyncio.sleep(1)

     print("Local emoji upload process completed.")

     
     print("Checking for any missing Pokémon emojis via API...")
     await self.upload_missing_emojis(available_servers=servers, max_emojis_per_server=max_emojis_per_server,
                                     embed_message=embed_message, ctx=ctx, embed=embed)

     if embed_message:
        embed.description = "All missing Pokémon emojis have been created and mapping saved!"
        await embed_message.edit(embed=embed)
     elif ctx:
        await ctx.send("All missing Pokémon emojis have been created and mapping saved!")

     print("Emoji creation process completed.")

    async def upload_missing_emojis(self, available_servers=None, max_emojis_per_server=50, embed_message=None, ctx=None, embed=None):
     
     all_pokemon_ids = await self.fetch_all_pokemon_ids()
     print(f"Fetched {len(all_pokemon_ids)} Pokémon IDs from the API.")

     
     global_existing = set()
     for guild_emojis in self.emoji_mapping.values():
        global_existing.update(guild_emojis.keys())

     
     all_pokemon_ids_str = set(str(pid) for pid in all_pokemon_ids)

     
     missing_ids = list(all_pokemon_ids_str - global_existing)
     print(f"Total missing Pokémon emojis: {len(missing_ids)}")

     
     servers = []
     if available_servers is not None:
        servers = available_servers
     else:
        for guild_id in self.GUILD_IDS:
            guild = self.bot.get_guild(int(guild_id))
            if guild is not None:
                servers.append(guild)
     if not servers:
        print("No valid servers found to upload emojis.")
        return

     
     emojis_uploaded = 0
     current_server_index = 0

     for pokemon_id in missing_ids:
        attempts = 0
        uploaded = False
        while attempts < len(servers) and not uploaded:
            server = servers[current_server_index]
            server_emojis = await self.list_existing_emojis(server)
            if len(server_emojis) < max_emojis_per_server:
                uploaded = await self.upload_single_emoji(server, pokemon_id)
                if uploaded:
                    emojis_uploaded += 1
                    
                    await asyncio.sleep(3)
            else:
                print(f"Server {server.name} has reached its emoji capacity. Skipping.")
            current_server_index = (current_server_index + 1) % len(servers)
            attempts += 1

        
        await asyncio.sleep(1)

     
     if embed_message:
        embed.description = "All missing Pokémon emojis have been created and mapping saved!"
        await embed_message.edit(embed=embed)
     elif ctx:
        await ctx.send("All missing Pokémon emojis have been created and mapping saved!")

     print(f"Emoji creation process completed. Total emojis uploaded: {emojis_uploaded}")
    
    
    
    
    @commands.command(hidden=True)
    async def create_emojis(self, ctx):
        print("create_emojis command invoked")
        if ctx.author.id not in self.owner_id:
            await ctx.reply("You do not have permission to use this command")
            return
        print("User has permission. Proceeding...")

        embed = discord.Embed(
            description="Downloading Pokémon images and uploading emojis.",
            color=discord.Color.default()
        )
        initial_message = await ctx.send(embed=embed)

        
        self.emoji_mapping = self.load_emoji_mapping()

        
        global_existing = set()
        for server_data in self.emoji_mapping.values():
            for pokemon in server_data.keys():
                global_existing.add(pokemon)

        
        servers = [self.bot.get_guild(int(guild_id)) for guild_id in self.GUILD_IDS]
        servers = [server for server in servers if server]
        print(f"Found {len(servers)} valid servers.")

        print("Starting image download...")
        await self.download_pokemon_images()
        print("Image download completed.")

        await self.upload_emojis_for_server(servers, global_existing, embed_message=initial_message, ctx=ctx, embed=embed)

        await ctx.send("All missing Pokemon emojis have been created and mapping saved!")
        print("Emoji creation process completed.")

    def get_emoji_for_pokemon(self, pokemon_id):
        """Return the emoji in the format <:emoji_name:emoji_id> for a given Pokemon ID across all servers."""
        emoji_name = str(pokemon_id).zfill(3)
        
        
        for server_id, server_data in self.emoji_mapping.items():
            if pokemon_id in server_data:
                emoji_data = server_data[pokemon_id]
                emoji_name = emoji_data['name']
                emoji_id = emoji_data['id']
                return f"<:{emoji_name}:{emoji_id}>"
        
        
        return None

    def call_emoji(self, emoji_mapping, pokemon_id):
        """
        Return a discord.PartialEmoji for a given Pokémon ID across all servers.
        """
        pokemon_id = pokemon_id['id']
        
        for server_id, server_data in emoji_mapping.items():
            if str(pokemon_id) in server_data:
                emoji_data = server_data[str(pokemon_id)]
                emoji_name = emoji_data['name']
                emoji_id = int(emoji_data['id'])  
                print(f"Emoji found: {emoji_name} (ID: {emoji_id})")  
                return f"<:{emoji_name}:{emoji_id}>"
        print(f"No emoji found for Pokémon ID {pokemon_id}")  
        
        return None

    @commands.command(hidden=True)
    async def get_pokemon_emoji(self, ctx, pokemon_id: int):
        emoji_str = self.get_emoji_for_pokemon(pokemon_id)
        
        if emoji_str:
            await ctx.send(f"Here is your Pokémon emoji: {emoji_str}")
        else:
            await ctx.send(f"No emoji found for Pokémon ID {pokemon_id} across all servers.")
