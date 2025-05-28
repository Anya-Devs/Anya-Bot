import os, re, csv, json, asyncio, multiprocessing as mp, csv
from functools import partial
from tqdm import tqdm, asyncio as async_tqdm
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from fuzzywuzzy import fuzz
from motor.motor_asyncio import AsyncIOMotorClient

from imports.discord_imports import *
from data.local.const import *
from bot.token import use_test_bot as ut
from utils.subcogs.pokemon import *


MAX_POKEMON, CHUNK_SIZE = 50, 15
class Ping_Pokemon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shiny_collection = "shiny_hunt"
        self.collection_collection = "collection"
        self.pokemon_description = os.path.join("data", "commands", "pokemon", "pokemon_description.csv")
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.valid_slugs = self.load_valid_slugs()
        self.pe = Pokemon_Emojis(bot)

    def load_valid_slugs(self):
        with open(self.pokemon_description, newline='', encoding='utf-8') as f:
            return {row["slug"] for row in csv.DictReader(f)}

    async def paginate_and_send(self, ctx, entries: list[str], title: str = "Your Pokémon Collection List"):
        pages = [entries[i:i + CHUNK_SIZE] for i in range(0, len(entries), CHUNK_SIZE)]
        embeds = [Embed(title=title, description="\n".join(chunk), color=primary_color()) for chunk in pages]

        class NavView(View):
            def __init__(self, index=0):
                super().__init__(timeout=60)
                self.index = index
                self.prev_button = Button(label="◀", style=ButtonStyle.secondary, disabled=index == 0)
                self.next_button = Button(label="▶", style=ButtonStyle.secondary, disabled=index >= len(embeds) - 1)
                self.prev_button.callback = self.go_prev
                self.next_button.callback = self.go_next
                self.add_item(self.prev_button)
                self.add_item(self.next_button)

            async def interaction_check(self, interaction: Interaction) -> bool:
                return interaction.user == ctx.author

            async def go_prev(self, interaction: Interaction):
                if self.index > 0:
                    self.index -= 1
                    await interaction.response.edit_message(embed=embeds[self.index], view=NavView(self.index))

            async def go_next(self, interaction: Interaction):
                if self.index < len(embeds) - 1:
                    self.index += 1
                    await interaction.response.edit_message(embed=embeds[self.index], view=NavView(self.index))

        await ctx.reply(embed=embeds[0], view=NavView(), mention_author=False)

    async def handle_collection(self, ctx, col, action, pokemon=None, max_one=False):
        uid = ctx.author.id
        cur = await self.mongo.list(col, uid)

        # remove invalids
        invalids = [n for n in cur if n not in self.valid_slugs]
        for n in invalids:
            await self.mongo.remove(col, n, uid)
        cur = await self.mongo.list(col, uid)

        # enforce limit
        if len(cur) > MAX_POKEMON:
            for n in cur[MAX_POKEMON:]:
                await self.mongo.remove(col, n, uid)
            cur = cur[:MAX_POKEMON]

        if action == "list":
            if not cur:
                return await ctx.reply(embed=Embed(description="Your list is empty."), mention_author=False)
            entries = [f"{self.pe.get_emoji_for_pokemon(Pokemon_Subcogs.pokemon_name_to_id(n)) or ''} {n.title()}" for n in cur]
            return await self.paginate_and_send(ctx, entries)

        if action == "clear":
            await self.mongo.clear(col, uid)
            return await ctx.reply(embed=Embed(description="🗑️ Cleared your Pokémon list."), mention_author=False)

        if not pokemon:
            return await ctx.reply(embed=Embed(description="❌ Specify Pokémon name(s)."), mention_author=False)

        names = [n.strip() for n in pokemon.split(',') if n.strip()]
        results = []
        cur = await self.mongo.list(col, uid)

        for raw in names:
            name, _ = Pokemon.transform_pokemon_name(raw)
            if not name or name not in self.valid_slugs:
                results.append(f"❌ Invalid Pokémon name: {raw}")
                continue
            pid = Pokemon_Subcogs.pokemon_name_to_id(name)
            emoji = self.pe.get_emoji_for_pokemon(pid) or ''
            if action == "add":
                if max_one:
                    await self.mongo.replace(col, name, uid)
                    results.append(f"{emoji} Set to {name.title()}")
                    break
                if len(cur) >= MAX_POKEMON and name not in cur:
                    results.append(f"❌ Max {MAX_POKEMON} Pokémon. `{name.title()}` not added.")
                    continue
                ok = await self.mongo.add(col, name, uid)
                results.append(f"{emoji} Added {name.title()}" if ok else f"{emoji} {name.title()} already exists.")
                if ok:
                    cur.append(name)
            elif action == "remove":
                ok = await self.mongo.remove(col, name, uid)
                results.append(f"{emoji} Removed {name.title()}" if ok else f"{emoji} {name.title()} not found.")

        if len(results) <= CHUNK_SIZE:
            await ctx.reply(embed=Embed(description="\n".join(results)), mention_author=False)
        else:
            await self.paginate_and_send(ctx, results, title="Collection Update")

    @commands.command(name="sh")
    async def sh(self, ctx, action: str = "add", *, pokemon: str = None):
        if action not in {"add", "remove", "list", "clear"}:
            pokemon, action = f"{action} {pokemon}".strip(), "add"
        if not action and pokemon:
            pokemon, action = None, "list"
        await self.handle_collection(ctx, self.shiny_collection, action, pokemon, max_one=True)

    @commands.command(name="cl", aliases=["collection"])
    async def cl(self, ctx, action: Literal["add", "remove", "list", "clear"] = "list", *, pokemon: str = None):
        await self.handle_collection(ctx, self.collection_collection, action, pokemon) 
        
        
        
        
                 
class Pokemon_Emojis(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.GUILD_IDS = ["1216270817101611058","1216270002127114340","1216269922263371876","1340447626105065585", "1340447685685153852", "1340447747974762556", "1340447749111545998", "1340447923548459133", "1340447977340145717", "1340448026740916338", "1340448028196212807", "1340448148866469971", "1340448241069723749", "1340448280966074519", "1340448379729346560", "1340448496100053055", "1340448546603667619", "1340448595052335104", "1340448664157687830", "1340448723603296300", "1340448725314703390", "1340448849281548363", "1340449016089153598", "1340449082971390033", "1340449185933299723", "1340449231194030121", "1340449271366815806", "1340449391533625398", "1340449491765166231", "1340449540175691847", "1340698929922183300", "1340699061992558665", "1340699001011437610"]
        self.POKEMON_IMAGES_FOLDER = "data/commands/pokemon/pokemon_emojis"
        self.IMAGE_SOURCES = ["https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{}.png", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{}.png", "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/{}.png"]
        self.emoji_json_path = "data/commands/pokemon/pokemon_emojis.json"
        self.owner_id = [1124389055598170182, 1320515815270907957]
        self.failed_downloads = set()
        self.emoji_mapping = self.load_emoji_mapping()
        os.makedirs(os.path.dirname(self.emoji_json_path), exist_ok=True)
        os.makedirs(self.POKEMON_IMAGES_FOLDER, exist_ok=True)


    def get_server_emoji_limit(self, guild):
        if guild.premium_tier >= 2:
            return 512 * 1024
        else:
            return 256 * 1024

    def resize_image_for_discord(self, image_data, guild=None):
        try:
            max_size_bytes = self.get_server_emoji_limit(guild) if guild else 256 * 1024
            img = Image.open(io.BytesIO(image_data))
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            max_dimension = 128
            quality = 95
            while max_dimension >= 32:
                img_resized = img.copy()
                img_resized.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                for current_quality in range(quality, 50, -5):
                    output = io.BytesIO()
                    img_resized.save(output, format='PNG', optimize=True, compress_level=9)
                    output_size = output.tell()
                    self.logger.debug(f"Resized to {max_dimension}x{max_dimension}, size: {output_size} bytes (limit: {max_size_bytes})")
                    if output_size <= max_size_bytes:
                        output.seek(0)
                        return output.read()
                max_dimension = int(max_dimension * 0.8)
            img_minimal = img.copy()
            img_minimal.thumbnail((32, 32), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            img_minimal.save(output, format='PNG', optimize=True, compress_level=9)
            output.seek(0)
            final_size = output.tell()
            self.logger.warning(f"Had to reduce image to minimal size: {final_size} bytes")
            output.seek(0)
            return output.read()
        except Exception as e:
            self.logger.error(f"Error resizing image: {e}")
            return None

    def validate_image_size(self, image_data, guild=None):
        if not image_data:
            return False, "No image data"
        max_size = self.get_server_emoji_limit(guild) if guild else 256 * 1024
        actual_size = len(image_data)
        if actual_size > max_size:
            return False, f"Image too large: {actual_size} bytes (limit: {max_size} bytes)"
        return True, "OK"

    def load_emoji_mapping(self):
        if os.path.exists(self.emoji_json_path):
            with open(self.emoji_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def get_pokemon_id(self, filename):
        return filename.split(".")[0].zfill(3)

    async def get_server_emoji_counts(self):
        self.logger.info("Fetching server emoji counts...")
        tasks = []
        for guild_id in self.GUILD_IDS:
            guild = self.bot.get_guild(int(guild_id))
            if guild and guild.me.guild_permissions.manage_emojis:
                tasks.append(self._get_single_server_count(guild, guild_id))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        counts = {r[0]: r[1] for r in results if not isinstance(r, Exception)}
        self.logger.info(f"Found {len(counts)} available servers")
        return counts

    async def _get_single_server_count(self, guild, guild_id):
        emoji_count = len(guild.emojis)
        max_emojis = 50 + (guild.premium_tier * 50)
        return guild_id, {'current': emoji_count, 'max': max_emojis, 'available': max_emojis - emoji_count, 'guild': guild}

    async def find_available_servers(self, min_slots=1):
        server_counts = await self.get_server_emoji_counts()
        available = [info['guild'] for info in server_counts.values() if info['available'] >= min_slots]
        self.logger.info(f"Found {len(available)} servers with {min_slots}+ available slots")
        return available

    async def download_pokemon_images(self):
        self.logger.info("Starting Pokemon image download process...")
        pokemon_ids = await self.fetch_all_pokemon_ids()
        existing_images = set(self.load_images())
        missing_pokemon_ids = [pid for pid in pokemon_ids if f"{str(pid).zfill(3)}.png" not in existing_images and pid not in self.failed_downloads]
        if not missing_pokemon_ids:
            self.logger.info("No missing images to download")
            return
        self.logger.info(f"Downloading {len(missing_pokemon_ids)} missing Pokemon images")
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=20)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(50)
            tasks = [self._download_with_semaphore(semaphore, session, pid) for pid in missing_pokemon_ids]
            results = []
            batch_size = 100
            for batch_start in range(0, len(tasks), batch_size):
                batch = tasks[batch_start:batch_start + batch_size]
                self.logger.info(f"Processing download batch {batch_start//batch_size + 1}/{(len(tasks) + batch_size - 1)//batch_size}")
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)
                await asyncio.sleep(0.1)
        successful = sum(1 for r in results if r is True)
        self.logger.info(f"Download complete: {successful}/{len(missing_pokemon_ids)} successful")

    async def _download_with_semaphore(self, semaphore, session, pokemon_id):
        async with semaphore:
            success = await self.download_single_image(session, pokemon_id)
            if not success:
                self.failed_downloads.add(pokemon_id)
                self.logger.warning(f"Failed to download Pokemon ID {pokemon_id}")
            return success

    async def download_single_image(self, session, pokemon_id):
        img_path = os.path.join(self.POKEMON_IMAGES_FOLDER, f"{str(pokemon_id).zfill(3)}.png")
        for source_url_template in self.IMAGE_SOURCES:
            img_url = source_url_template.format(pokemon_id)
            try:
                async with session.get(img_url) as response:
                    if response.status == 200:
                        content = await response.read()
                        resized_content = await asyncio.get_event_loop().run_in_executor(None, self.resize_image_for_discord, content, None)
                        if resized_content:
                            is_valid, message = self.validate_image_size(resized_content)
                            if is_valid:
                                await asyncio.get_event_loop().run_in_executor(None, self._write_image_file, img_path, resized_content)
                                self.logger.debug(f"Successfully downloaded and resized Pokemon {pokemon_id}")
                                return True
                            else:
                                self.logger.error(f"Image validation failed for Pokemon {pokemon_id}: {message}")
                        else:
                            self.logger.error(f"Failed to resize image for Pokemon {pokemon_id}")
            except Exception as e:
                self.logger.debug(f"Error downloading {img_url}: {e}")
                continue
        return False

    def _write_image_file(self, path, content):
        with open(path, "wb") as f:
            f.write(content)

    def load_images(self):
        try:
            return os.listdir(self.POKEMON_IMAGES_FOLDER)
        except:
            return []

    async def fetch_all_pokemon_ids(self):
        self.logger.info("Fetching all Pokemon IDs from PokeAPI...")
        pokemon_ids = []
        invalid_ids = {10265, 10266, 10267, 10268, 10269}
        connector = aiohttp.TCPConnector(limit=50)
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            url = "https://pokeapi.co/api/v2/pokemon"
            all_pokemon = []
            page_count = 0
            while url:
                page_count += 1
                self.logger.info(f"Fetching Pokemon list page {page_count}...")
                async with session.get(url) as response:
                    if response.status != 200:
                        break
                    data = await response.json()
                    all_pokemon.extend(data["results"])
                    url = data.get("next")
            self.logger.info(f"Found {len(all_pokemon)} Pokemon entries across {page_count} pages")
            semaphore = asyncio.Semaphore(30)
            tasks = [self._fetch_pokemon_data(semaphore, session, result, invalid_ids) for result in all_pokemon]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            pokemon_ids = [r for r in results if isinstance(r, int)]
        self.logger.info(f"Valid Pokemon IDs collected: {len(pokemon_ids)}")
        return sorted(pokemon_ids)

    async def _fetch_pokemon_data(self, semaphore, session, result, invalid_ids):
        async with semaphore:
            try:
                async with session.get(result["url"]) as response:
                    if response.status == 200:
                        data = await response.json()
                        poke_id = data["id"]
                        if poke_id not in invalid_ids:
                            return poke_id
            except Exception as e:
                self.logger.debug(f"Error fetching Pokemon data for {result.get('name', 'unknown')}: {e}")
        return None

    async def list_existing_emojis(self, server):
        if not server or not server.me.guild_permissions.manage_emojis:
            return {}
        try:
            return {emoji.name: emoji.id for emoji in server.emojis}
        except:
            return {}

    async def upload_single_emoji(self, server, pokemon_id):
        existing_emojis = await self.list_existing_emojis(server)
        emoji_name = str(pokemon_id).zfill(3)
        if emoji_name in existing_emojis:
            return False
        if (str(server.id) in self.emoji_mapping and str(pokemon_id) in self.emoji_mapping[str(server.id)]):
            return False
        if pokemon_id in self.failed_downloads:
            return False
        emoji_image_path = os.path.join(self.POKEMON_IMAGES_FOLDER, f"{emoji_name}.png")
        try:
            emoji_data = await asyncio.get_event_loop().run_in_executor(None, self._read_image_file, emoji_image_path)
            if not emoji_data:
                self.logger.error(f"Could not read image file for Pokemon {pokemon_id}")
                return False
            is_valid, message = self.validate_image_size(emoji_data, server)
            if not is_valid:
                self.logger.error(f"Image validation failed for Pokemon {pokemon_id} on {server.name}: {message}")
                original_data = emoji_data
                resized_data = await asyncio.get_event_loop().run_in_executor(None, self.resize_image_for_discord, original_data, server)
                if resized_data:
                    is_valid, message = self.validate_image_size(resized_data, server)
                    if is_valid:
                        emoji_data = resized_data
                        await asyncio.get_event_loop().run_in_executor(None, self._write_image_file, emoji_image_path, resized_data)
                    else:
                        self.logger.error(f"Could not resize image small enough for Pokemon {pokemon_id}: {message}")
                        return False
                else:
                    return False
            emoji = await server.create_custom_emoji(name=emoji_name, image=emoji_data)
            if str(server.id) not in self.emoji_mapping:
                self.emoji_mapping[str(server.id)] = {}
            self.emoji_mapping[str(server.id)][str(pokemon_id)] = {"name": emoji_name, "id": emoji.id}
            await asyncio.get_event_loop().run_in_executor(None, self._save_emoji_mapping)
            self.logger.info(f"SUCCESS: Uploaded Pokemon {pokemon_id} to {server.name}")
            return True
        except discord.errors.HTTPException as e:
            if e.status == 429:
                retry_after = int(e.response.headers.get("Retry-After", 30))
                self.logger.warning(f"Rate limited, waiting {retry_after}s for Pokemon {pokemon_id}")
                await asyncio.sleep(retry_after)
                return await self.upload_single_emoji(server, pokemon_id)
            elif e.code == 30008:
                self.logger.warning(f"Server {server.name} at emoji capacity")
                return False
            elif e.code == 50045:
                self.logger.error(f"Asset too large for Pokemon {pokemon_id} on {server.name}: {len(emoji_data) if 'emoji_data' in locals() else 'unknown'} bytes")
                return False
            else:
                self.logger.error(f"HTTP Error uploading Pokemon {pokemon_id} to {server.name}: {e}")
                return False
        except Exception as e:
            self.logger.error(f"Unexpected error uploading Pokemon {pokemon_id} to {server.name}: {e}")
            return False

    def _read_image_file(self, path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except:
            return None

    def _save_emoji_mapping(self):
        with open(self.emoji_json_path, "w", encoding="utf-8") as f:
            json.dump(self.emoji_mapping, f, indent=2)

    async def create_emoji_image(self, pokemon_id):
        connector = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=connector) as session:
            return await self.download_single_image(session, pokemon_id)

    async def upload_emojis_for_server(self, servers, global_existing, embed_message=None, ctx=None, embed=None):
        self.logger.info("Starting emoji upload process...")
        available_servers = await self.find_available_servers(min_slots=5)
        if not available_servers:
            message = "ERROR: All servers at emoji capacity!"
            self.logger.warning(message)
            if embed_message and embed:
                embed.description = message
                await embed_message.edit(embed=embed)
            elif ctx:
                await ctx.send(message)
            return
        images = self.load_images()
        pokemon_ids = [int(self.get_pokemon_id(img)) for img in images if str(int(self.get_pokemon_id(img))) not in global_existing and int(self.get_pokemon_id(img)) not in self.failed_downloads]
        if not pokemon_ids:
            self.logger.info("No new Pokemon to upload")
            return
        self.logger.info(f"Uploading {len(pokemon_ids)} Pokemon emojis across {len(available_servers)} servers")
        emojis_uploaded = 0
        server_index = 0
        upload_semaphore = asyncio.Semaphore(5)
        
        async def upload_with_server_rotation(pokemon_id):
            nonlocal server_index, emojis_uploaded
            async with upload_semaphore:
                for attempt in range(len(available_servers)):
                    if not available_servers:
                        return False
                    server = available_servers[server_index % len(available_servers)]
                    current_count = len(await self.list_existing_emojis(server))
                    max_emojis = 50 + (server.premium_tier * 50)
                    if current_count >= max_emojis:
                        available_servers.remove(server)
                        self.logger.info(f"Server {server.name} removed - at capacity")
                        continue
                    result = await self.upload_single_emoji(server, pokemon_id)
                    if result:
                        emojis_uploaded += 1
                        server_index += 1
                        await asyncio.sleep(0.5)
                        return True
                    server_index += 1
                return False

        batch_size = 10
        total_batches = (len(pokemon_ids) + batch_size - 1) // batch_size
        for i in range(0, len(pokemon_ids), batch_size):
            batch = pokemon_ids[i:i + batch_size]
            batch_num = i // batch_size + 1
            self.logger.info(f"Processing upload batch {batch_num}/{total_batches} ({len(batch)} Pokemon)")
            tasks = [upload_with_server_rotation(pid) for pid in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            if not available_servers:
                self.logger.warning("No more available servers, stopping upload")
                break
            if embed_message and embed:
                embed.description = f"Uploading... {emojis_uploaded} emojis added (Batch {batch_num}/{total_batches})"
                await embed_message.edit(embed=embed)
            await asyncio.sleep(2)
        
        final_message = f"SUCCESS: Upload complete! Added {emojis_uploaded}/{len(pokemon_ids)} emojis"
        self.logger.info(final_message)
        if embed_message and embed:
            embed.description = final_message
            embed.color = discord.Color.green()
            await embed_message.edit(embed=embed)

    @commands.command(hidden=True)
    async def create_emojis(self, ctx):
        if ctx.author.id not in self.owner_id:
            await ctx.reply("ERROR: No permission")
            return
        self.logger.info(f"Emoji creation command started by {ctx.author}")
        embed = discord.Embed(description="Starting emoji creation process...", color=discord.Color.blue())
        initial_message = await ctx.send(embed=embed)
        self.emoji_mapping = self.load_emoji_mapping()
        global_existing = set()
        for server_data in self.emoji_mapping.values():
            global_existing.update(server_data.keys())
        self.logger.info(f"Found {len(global_existing)} existing emojis")
        servers = [self.bot.get_guild(int(gid)) for gid in self.GUILD_IDS]
        servers = [s for s in servers if s]
        server_counts = await self.get_server_emoji_counts()
        available_servers = [info['guild'] for info in server_counts.values() if info['available'] > 0]
        if not available_servers:
            embed.description = "ERROR: All servers at capacity!"
            embed.color = discord.Color.red()
            await initial_message.edit(embed=embed)
            return
        embed.description = "Downloading Pokemon images..."
        embed.color = discord.Color.orange()
        await initial_message.edit(embed=embed)
        await self.download_pokemon_images()
        embed.description = "Uploading emojis to servers..."
        embed.color = discord.Color.yellow()
        await initial_message.edit(embed=embed)
        await self.upload_emojis_for_server(servers, global_existing, embed_message=initial_message, ctx=ctx, embed=embed)

    @commands.command(hidden=True)
    async def server_status(self, ctx):
        if ctx.author.id not in self.owner_id:
            await ctx.reply("ERROR: No permission")
            return
        self.logger.info(f"Server status requested by {ctx.author}")
        server_counts = await self.get_server_emoji_counts()
        embed = discord.Embed(title="Server Emoji Status", color=discord.Color.blue())
        total_emojis = sum(info['current'] for info in server_counts.values())
        total_capacity = sum(info['max'] for info in server_counts.values())
        embed.description = f"**Total: {total_emojis}/{total_capacity} emojis used**"
        for guild_id, info in server_counts.items():
            guild = info['guild']
            percentage = (info['current'] / info['max']) * 100
            status_emoji = "RED" if percentage >= 90 else "YELLOW" if percentage >= 70 else "GREEN"
            status = f"{status_emoji} {info['current']}/{info['max']} ({info['available']} free)"
            embed.add_field(name=guild.name[:20], value=status, inline=True)
        await ctx.send(embed=embed)

    def get_emoji_for_pokemon(self, pokemon_id):
        pokemon_id_str = str(pokemon_id).zfill(3)
        for server_id, server_data in self.emoji_mapping.items():
            if str(pokemon_id) in server_data:
                emoji_data = server_data[str(pokemon_id)]
                return f"<:{emoji_data['name']}:{emoji_data['id']}>"
        return None

    def call_emoji(self, emoji_mapping, pokemon_id):
        pokemon_id = pokemon_id['id']
        for server_id, server_data in emoji_mapping.items():
            if str(pokemon_id) in server_data:
                emoji_data = server_data[str(pokemon_id)]
                return f"<:{emoji_data['name']}:{int(emoji_data['id'])}>"
        return None

    @commands.command(hidden=True)
    async def get_pokemon_emoji(self, ctx, pokemon_id: int):
        emoji_str = self.get_emoji_for_pokemon(pokemon_id)
        if emoji_str:
            await ctx.send(f"Pokemon emoji: {emoji_str}")
        else:
            await ctx.send(f"ERROR: No emoji found for Pokemon ID {pokemon_id}")

    @commands.command(hidden=True)
    async def force_download(self, ctx, start_id: int = 1, end_id: int = 2000):
        if ctx.author.id not in self.owner_id:
            return
        self.logger.info(f"Force download requested by {ctx.author} for IDs {start_id}-{end_id}")
        embed = discord.Embed(description=f"Force downloading Pokemon {start_id}-{end_id}...", color=discord.Color.orange())
        msg = await ctx.send(embed=embed)
        pokemon_ids = list(range(start_id, end_id + 1))
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            semaphore = asyncio.Semaphore(60)
            tasks = [self._download_with_semaphore(semaphore, session, pid) for pid in pokemon_ids]
            results = []
            batch_size = 50
            total_batches = (len(tasks) + batch_size - 1) // batch_size
            for i in range(0, len(tasks), batch_size):
                batch = tasks[i:i + batch_size]
                batch_num = i // batch_size + 1
                embed.description = f"Downloading batch {batch_num}/{total_batches}..."
                await msg.edit(embed=embed)
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                results.extend(batch_results)
        successful = sum(1 for r in results if r)
        embed.description = f"SUCCESS: Downloaded {successful}/{len(pokemon_ids)} images"
        embed.color = discord.Color.green()
        await msg.edit(embed=embed)
        self.logger.info(f"Force download complete: {successful}/{len(pokemon_ids)} successful")

            
            
            
            
            
            
            
            
class Pokemon_Subcogs:
    
 @staticmethod
 def pokemon_name_to_id(pokemon_name, file_path="data/commands/pokemon/pokemon_description.csv"):
    try:
        with open(file_path, mode="r", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if row["slug"].lower() == pokemon_name.lower():
                    return row["id"]
    except Exception as e:
        print(f"Error: {e}")
        return None
    
class MongoHelper:
    def __init__(self, db): self.db = db
    async def add(self, col, pokemon, uid):
        c, d = self.db[col], await self.db[col].find_one({"user_id": uid})
        if not d: await c.insert_one({"user_id": uid, "pokemon": [pokemon]}); return True
        if pokemon in d["pokemon"]: return False
        await c.update_one({"user_id": uid}, {"$push": {"pokemon": pokemon}}); return True
    async def remove(self, col, pokemon, uid):
        d = await self.db[col].find_one({"user_id": uid})
        if not d or pokemon not in d["pokemon"]: return False
        await self.db[col].update_one({"user_id": uid}, {"$pull": {"pokemon": pokemon}}); return True
    async def list(self, col, uid):
        d = await self.db[col].find_one({"user_id": uid})
        return d["pokemon"] if d else []
    async def replace(self, col, pokemon, uid):
        await self.db[col].update_one({"user_id": uid}, {"$set": {"pokemon": [pokemon]}}, upsert=True); return True
    async def clear(self, col, uid):
        await self.db[col].update_one({"user_id": uid}, {"$set": {"pokemon": []}}); return True

class PokemonNameHelper:
    def __init__(self, csv_file):
        self.csv_file = csv_file
        self.rare, self.regional = [], []

    def load_data(self):
        try:
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if row[0]: self.rare.append(row[0].lower().strip())
                    if row[1]: self.regional.append(row[1].lower().strip())
        except FileNotFoundError:
            self.rare, self.regional = [], []

    def transform_name(self, name):
        map_ = {"alolan":"-alola","galarian":"-galar","hisui":"-hisui","paldean":"-paldea","mega":"-mega"}
        name_clean = re.sub(r'[^a-zA-Z\s]', '', name)
        lower = name_clean.lower()
        for k,v in map_.items():
            if k in lower:
                parts = name_clean.split()
                base = parts[1].capitalize() if len(parts)>1 else parts[0].capitalize()
                return f"{base.lower()}{v}", k
        return name_clean, None

    def check_match(self, name):
        rare_match = next((p for p in self.rare if fuzz.ratio(name, p) > 90), None)
        regional_match = next((p for p in self.regional if fuzz.ratio(name, p) > 90), None)
        return rare_match, regional_match
