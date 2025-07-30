import os, re, csv, json, asyncio, multiprocessing as mp, csv, difflib
from imports.log_imports import *
from functools import partial
from tqdm import tqdm, asyncio as async_tqdm
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from fuzzywuzzy import fuzz
from motor.motor_asyncio import AsyncIOMotorClient

from imports.discord_imports import *
from data.local.const import *
from bot.token import use_test_bot as ut
from utils.subcogs.pokemon import *
from utils.subcogs.utils.cls_ping_pokemon import PokemonDataManager, PokemonEmbedManager, PokemonCollectionHandler, AdvancedStringFlagParser, PokemonHelpEmbed, ServerConfigView, PokemonTypeSelect, PokemonRegionSelect


class Ping_Pokemon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.shiny_collection = "shiny_hunt"
        self.collection_collection = "collection"
        self.type_collection = "type_ping"
        self.quest_collection = "quest_ping"

        self.pokemon_names_file = "data/commands/pokemon/pokemon_names.csv"
        self.pokemon_types_file = "data/commands/pokemon/pokemon_types.csv"
        self.pokemon_rarity_file = "data/commands/pokemon/pokemon_rarity.csv"
        self.pokemon_description_file = None

        self.embed_default_color = primary_color()
        self.RESULTS_PER_PAGE = 10
        self.MAX_POKEMON = 50

        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.check_emoji = "✅"
        self.cross_emoji = "❌"
        self.star_emoji = "⭐"
        self.globe_emoji = "🌍"
        self.trash_emoji = "🗑️"

        try:
            self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        except:
            print("⚠️ MongoDB connection failed.")
            self.mongo = None

        try:
            self.pe = Pokemon_Emojis(bot)
            self.ph = PokemonNameHelper()
        except:
            print("⚠️ Pokemon helper classes not loaded.")
            self.pe = None
            self.ph = None

        self.data_manager = PokemonDataManager(
            mongo_client=self.mongo,
            pokemon_names_csv=self.pokemon_names_file,
            pokemon_types_csv=self.pokemon_types_file,
            pokemon_rarity_csv=self.pokemon_rarity_file
        ) 

        self.embed_manager = PokemonEmbedManager(
            embed_default_color=self.embed_default_color,
            icons = {"success": "<:check:1399603549100441723>", "error": "<:x_:1399603637105463386>", "exists": "<:already_exists:1399604560598663188>", "removed": "<:minus:1399613745784946728>", "not_found": "<:not_found:1399604993228804136>"},
            results_per_page=self.RESULTS_PER_PAGE,
            chunk_size=15
        )

        self.collection_handler = PokemonCollectionHandler(
            data_manager=self.data_manager,
            embed_manager=self.embed_manager,
            pokemon_emojis=self.pe,
            pokemon_subcogs=self.ph,
            max_pokemon=self.MAX_POKEMON
        )

        self.flag_parser = AdvancedStringFlagParser()
        self.pokemon_types = self.load_pokemon_types()

    def load_pokemon_types(self):
        types = set()
        try:
            with open(self.pokemon_types_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if 'types' in row and row['types']:
                        pokemon_types = row['types'].strip('"').split(',')
                        for ptype in pokemon_types:
                            types.add(ptype.strip().lower())
        except FileNotFoundError:
            print(f"⚠️ Pokemon types file not found: {self.pokemon_types_file}")
            types = {
                "normal", "fire", "water", "electric", "grass", "ice",
                "fighting", "poison", "ground", "flying", "psychic", "bug",
                "rock", "ghost", "dragon", "dark", "steel", "fairy"
            }
        return sorted(list(types))

    def load_quest_regions(self):
        return {
            "kanto", "johto", "hoenn", "sinnoh", "unova", "kalos",
            "alola", "galar", "hisui", "paldea"
        }

    async def get_server_config(self, guild_id: int) -> dict:
        if not self.mongo:
            return {}
        config = await self.mongo.db["server_config"].find_one({"guild_id": guild_id}) or {}
        return config

    @commands.command(name="type_ping", aliases=["tp"])
    async def type_ping(self, ctx):
        user_id = ctx.author.id
        try:
            current_types_data = await self.mongo.db["type_ping_types"].find({"user_id": user_id}).to_list(None)
            current_types = [entry["type"] for entry in current_types_data]
        except Exception:
            current_types = []

        view = PokemonTypeSelect(user_id, "type_ping", self.mongo, self.pokemon_types, current_types)
        embed = view._create_embed(ctx=ctx)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.hybrid_command(name="quest_ping", aliases=["qp"])
    async def quest_ping(self, ctx):
        user_id = ctx.author.id
        try:
            current_regions_data = await self.mongo.db[self.quest_collection].find_one({"user_id": user_id})
            current_regions = current_regions_data.get("regions", []) if current_regions_data else []
        except Exception:
            current_regions = []

        available_regions = sorted(list(self.load_quest_regions()))
        view = PokemonRegionSelect(user_id, self.quest_collection, self.mongo, available_regions, current_regions)
        embed = view._create_embed(ctx=ctx)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @app_commands.command(
        name="specialping",
        description="Set or remove role pings for rare or regional Pokémon spawns."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        ping_type="Select the ping category: rare or regional Pokémon.",
        role="Role to mention for the selected ping type (leave empty to remove)."
    )
    @app_commands.choices(ping_type=[
        app_commands.Choice(name="Rare Pokémon", value="rare"),
        app_commands.Choice(name="Regional Pokémon", value="regional"),
    ])
    async def special_ping(
        self,
        interaction: discord.Interaction,
        ping_type: app_commands.Choice[str],
        role: discord.Role | None = None
    ):
        guild_id = interaction.guild.id
        key = f"{ping_type.value}_role"

        try:
            config = await self.get_server_config(guild_id)

            if role:
                config[key] = role.id
                message = f"{ping_type.name} ping role set to {role.mention}."
            else:
                config.pop(key, None)
                message = f"{ping_type.name} ping role has been removed."

            await self.mongo.db["server_config"].update_one(
                {"guild_id": guild_id},
                {"$set": config},
                upsert=True
            )

            rare_role = interaction.guild.get_role(config.get("rare_role"))
            regional_role = interaction.guild.get_role(config.get("regional_role"))

            embed = discord.Embed(
                title="Special Ping Configuration Updated",
                description=message,
                color=discord.Color.default()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(
                name="Current Ping Roles",
                value=(
                    f"**Rare Pokémon:** {rare_role.mention if rare_role else 'Not set'}\n"
                    f"**Regional Pokémon:** {regional_role.mention if regional_role else 'Not set'}"
                ),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"Failed to update ping roles: `{e}`",
                color=discord.Color.red()
            )
            error_embed.set_thumbnail(url=interaction.user.display_avatar.url)
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @special_ping.error
    async def special_ping_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        embed = discord.Embed(
            title="Error in specialping command",
            description=f"```py\n{error}```",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.command(name="shiny_hunt", aliases=["sh"])
    async def shiny_hunt(self, ctx, action: str = None, *, pokemon: str = None):
        prefix = ctx.prefix

        if action == "help":
            desc = (
                f"**Usage:**\n"
                f"`{prefix}sh` — View your current shiny hunt\n"
                f"`{prefix}sh <pokemon>` — Set shiny target\n"
                f"`{prefix}sh add <pokemon>` — Add to shiny hunt\n"
                f"`{prefix}sh remove` — Remove shiny hunt\n"
                f"`{prefix}sh remove <pokemon>` — Remove specific target\n"
                f"`{prefix}sh list` — List shiny hunt targets\n"
                f"`{prefix}sh clear` — Clear all shiny targets\n\n"
            )
            return await ctx.reply(embed=discord.Embed(title="Shiny Hunt Help", description=desc, color=self.embed_default_color), mention_author=False)

        if not action and not pokemon:
            if not self.mongo:
                return await ctx.reply("❌ Database connection not available.", mention_author=False)
            cur = await self.mongo.list(self.shiny_collection, ctx.author.id)
            if not cur:
                return await ctx.reply(embed=discord.Embed(description="You don't have a shiny hunt set.", color=self.embed_default_color), mention_author=False)
            name = cur[0]
            pid = Pokemon_Subcogs.pokemon_name_to_id(name) if 'Pokemon_Subcogs' in globals() else None
            emoji = self.pe.get_emoji_for_pokemon(pid) if self.pe and pid else ""
            disp = self.data_manager.display_name_with_region(name)
            return await ctx.reply(embed=discord.Embed(description=f"You are currently shiny hunting: **{emoji} {disp}**", color=self.embed_default_color), mention_author=False)

        if action == "remove" and not pokemon:
            if not self.mongo:
                return await ctx.reply("❌ Database connection not available.", mention_author=False)
            await self.mongo.clear(self.shiny_collection, ctx.author.id)
            return await ctx.reply(embed=discord.Embed(description="🗑️ Your shiny hunt has been removed.", color=self.embed_default_color), mention_author=False)

        if action not in {"add", "remove", "list", "clear"}:
            full = f"{action} {pokemon}".strip() if pokemon else action
            if self.ph:
                full, _ = self.ph.transform_name(full)
            action, pokemon = "add", full

        flags = self.flag_parser.parse_flags_from_string(pokemon or "")
        await self.collection_handler.handle_collection(ctx, self.shiny_collection, action, pokemon=pokemon, flags_obj=flags, max_one=True)

    @commands.command(name="collection", aliases=["cl"])
    async def collection_string(self, ctx, *, args: str = "list"):
        try:
            action = "list"
            pokemon_names = ""
            args_lower = args.lower().strip()

            if args_lower.startswith(('add ', 'remove ', 'delete ', 'clear', 'help')):
                parts = args.split(' ', 1)
                action = parts[0].lower()
                if action == "delete":
                    action = "remove"
                remaining = parts[1] if len(parts) > 1 else ""
            else:
                remaining = args

            if action == "help":
                embed = PokemonHelpEmbed.generate_collection_help_embed(self, ctx)
                return await ctx.reply(embed=embed, mention_author=False)

            flags_dict = self.flag_parser.parse_flags_from_string(remaining)
            pokemon_names, _ = self.flag_parser.extract_pokemon_names_from_string(remaining, action)

            await self.collection_handler.handle_collection(
                ctx,
                self.collection_collection,
                action,
                pokemon=pokemon_names or None,
                flags_obj=flags_dict
            )

        except Exception as e:
            await ctx.reply(f"An error occurred while processing your command:\n`{type(e).__name__}: {e}`", mention_author=False)

    @commands.command(name="server_config", aliases=["sc"])
    @commands.has_permissions(manage_guild=True)
    async def server_config(self, ctx):
        embed = discord.Embed(
            title="Server Configuration",
            description="Configure server-wide Pokemon ping settings",
            color=self.embed_default_color
        )

        config = await self.get_server_config(ctx.guild.id)
        rare_role = ctx.guild.get_role(config.get("rare_role")) if config.get("rare_role") else None
        regional_role = ctx.guild.get_role(config.get("regional_role")) if config.get("regional_role") else None

        embed.add_field(
            name="Current Settings",
            value=f"**Rare Pokemon Role:** {rare_role.mention if rare_role else 'Not set'}\n"
                  f"**Regional Pokemon Role:** {regional_role.mention if regional_role else 'Not set'}",
            inline=False
        )

        view = ServerConfigView(ctx.guild.id, self.mongo)
        await ctx.reply(embed=embed, view=view, mention_author=False)











        
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
 def pokemon_name_to_id(pokemon_name, file_path="data/commands/pokemon/pokemon_names.csv"):
    try:
        with open(file_path, mode="r", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if row["name"].lower() == pokemon_name.lower():
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
    def __init__(self, csv_file=None):
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

    @staticmethod
    def pokemon_name_to_id(pokemon_name, file_path="data/commands/pokemon/pokemon_names.csv"):
     try:
        with open(file_path, mode="r", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if row["name"].lower() == pokemon_name.lower():
                    return row["id"]
     except Exception as e:
        print(f"Error: {e}")
        return None
 

    def transform_name(self, name):
        map_ = {"alolan":"-alola","galarian":"-galar","hisuian":"-hisui","paldean":"-paldea","mega":"-mega"}
        name_clean = re.sub(r'[^a-zA-Z\s]', '', name)
        lower = name_clean.lower()
        for k,v in map_.items():
            if k in lower:
                parts = name_clean.split()
                base = parts[1].capitalize() if len(parts)>1 else parts[0].capitalize()
                return f"{base.lower()}{v}", k
        return name_clean, None
    
    def reverse_transform_name(self, name):
     rev_map = {"-alola": "Alolan", "-galar": "Galarian", "-hisui": "Hisuian", "-paldea": "Paldean", "-mega": "Mega"}
     n = name.lower()
     for suf, pre in rev_map.items():
        if n.endswith(suf):
            base = name[:-len(suf)]
            return f"{pre} {base}", pre
     return name, ''
    
    def check_match(self, name):
        rare_match = next((p for p in self.rare if fuzz.ratio(name, p) > 90), None)
        regional_match = next((p for p in self.regional if fuzz.ratio(name, p) > 90), None)
        return rare_match, regional_match


class PokemonNameHelperCollection:
    def transform_name(self, name):
        name = name.lower().strip()
        if any(name.endswith(suffix) for suffix in CollectionViewUI.REGIONAL_SUFFIXES):
            return name, name
        return name, name




























class CollectionViewUI(View):
    REGIONAL_SUFFIXES = ("-alola", "-galar", "-hisui", "-paldea")
    REGIONAL_PREFIXES = {
        "alolan": "-alola",
        "galarian": "-galar",
        "hisuian": "-hisui",
        "paldean": "-paldea"
    }
    REGION_EMOJIS = {
        "paldea": "<:Paldea:1212335178714980403>",
        "sinnoh": "<:Sinnoh:1212335180459544607>",
        "alola": "<:Alola:1212335185228472411>",
        "kalos": "<:Kalos:1212335190656024608>",
        "galar": "<:Galar:1212335192740470876>",
        "pasio": "<:848495108667867139:1212335194628034560>",
        "hoenn": "<:Hoenn:1212335197304004678>",
        "unova": "<:Unova:1212335199095095306>",
        "kanto": "<:Kanto:1212335202341363713>",
        "johto": "<:Kanto:1212335202341363713>"
    }
    FILTER_KEYS = ["rare", "regional", "show_all"]
    FILTER_LABELS = {"rare": "Rare", "regional": "Regional", "show_all": "Showing All"}
    NAV_BUTTONS = [("⏮", 0), ("◀", 1), ("▶", 2), ("⏭", 3)]
    ALL_REGIONS = set(REGION_EMOJIS.keys())

    def __init__(self, ctx, entries, title):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.entries = entries
        self.title = title
        self.page = 0
        self.filters = {k: False for k in self.FILTER_KEYS}
        self.selected_regions = set()
        self.ph = PokemonNameHelperCollection()
        self.description_path = "data/commands/pokemon/pokemon_description.csv"
        self.special_path = "data/commands/pokemon/pokemon_special_names.csv"
        self.name_to_region = self._load_region_map()
        self.rare_names, self.regional_names = self._load_special_names()
        
        self.user_regions = self._extract_user_regions()
        self.has_rare = any(self._is_rare_pokemon(e) for e in self.entries)
        self.has_regional = any(self._is_regional_pokemon(e) for e in self.entries)
        self._update_filtered_entries()
        self._update_embeds()
        self._build_components()

    def _extract_pokemon_name(self, entry):
        return re.sub(r'<:[^:]+:\d+>\s*', '', entry).strip()

    def _normalize_name_to_slug(self, name):
        clean = name.lower().strip()
        for prefix, suffix in self.REGIONAL_PREFIXES.items():
            if clean.startswith(f"{prefix} "):
                base_name = clean[len(prefix) + 1:]
                return base_name + suffix
        return clean

    def _normalize_name(self, name):
        n = self._extract_pokemon_name(name) if '<:' in name else name.lower().strip()
        return self._normalize_name_to_slug(n)

    def convert_regional_name(self, name: str) -> str:
        region_map = {
            "alolan": "-alola",
            "galarian": "-galar",
            "hisuian": "-hisui",
            "paldean": "-paldea"
        }
        name_lower = name.lower().strip()
        for prefix, suffix in region_map.items():
            if name_lower.startswith(f"{prefix} "):
                base_name = name_lower[len(prefix) + 1:]
                return base_name + suffix
        return name_lower

    def _load_region_map(self):
        region_map = {}
        try:
            with open(self.description_path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    slug = row["slug"].lower()
                    region = row.get("region", "").strip().lower()
                    if region in self.ALL_REGIONS:
                        region_map[slug] = region
        except Exception:
            pass
        return region_map

    def _load_special_names(self):
        rare, regional = set(), set()
        try:
            with open(self.special_path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fields = {k.lower().replace(" ", "").replace("é", "e"): k for k in reader.fieldnames}
                rare_col = fields.get("rarepokemon", "")
                regional_col = fields.get("regionalpokemon", "")
                for row in reader:
                    rare_name = row.get(rare_col, "").strip().lower()
                    regional_name = row.get(regional_col, "").strip().lower()
                    if rare_name:
                        rare.add(rare_name)
                    if regional_name:
                        
                        regional.add(regional_name)
        except Exception as e:
            print(f"Error loading special names: {e}")
            pass
        return rare, regional

    def _extract_user_regions(self):
        regions = set()
        for e in self.entries:
            name = self._extract_pokemon_name(e)
            slug = self._normalize_name_to_slug(name)
            try:
                slug, _ = self.ph.transform_name(slug)
            except:
                pass
            if not any(slug.endswith(sfx) for sfx in self.REGIONAL_SUFFIXES):
                region = self.name_to_region.get(slug)
                if region:
                    regions.add(region)
        return sorted(regions)

    def _is_rare_pokemon(self, entry):
        name = self._extract_pokemon_name(entry)
        slug = self._normalize_name_to_slug(name)
        try:
            slug, _ = self.ph.transform_name(slug)
            return slug in self.rare_names
        except:
            return slug in self.rare_names

    def _is_regional_pokemon(self, entry):
        name = self._extract_pokemon_name(entry)
        raw_name = self.convert_regional_name(name)
        try:
            raw_name, _ = self.ph.transform_name(raw_name)
        except:
            pass
        return raw_name in self.regional_names

    def filter_rare_and_regional(self, type: str, entries: list[str]) -> list[str]:
        ready = []
        for e in entries:
            name = self._extract_pokemon_name(e)
            slug = self._normalize_name_to_slug(name)
            try:
                slug, _ = self.ph.transform_name(slug)
            except:
                pass
            region = self.name_to_region.get(slug) if not any(slug.endswith(s) for s in self.REGIONAL_SUFFIXES) else None

            if type == "rare":
                if slug in self.rare_names:
                    ready.append(e)
            elif type == "regional":
                raw_name = self.convert_regional_name(name)
                try:
                    raw_name, _ = self.ph.transform_name(raw_name)
                except:
                    pass
                print(f"[DEBUG] Regional filter check: Entry='{e}', Name='{name}', Raw='{raw_name}', In regional_names={raw_name in self.regional_names}")
                if raw_name in self.regional_names:
                    ready.append(e)
            elif type == "region_filter":
                if self.selected_regions:
                    if region in self.selected_regions:
                        ready.append(e)
                else:
                    ready.append(e)
            else:
                ready.append(e)

        if type == "regional":
            print(f"[DEBUG] Regional filter result count: {len(ready)} out of {len(entries)} entries")
            print(f"[DEBUG] After regional filter: {len(ready)} entries")

        return ready

    def _update_filtered_entries(self):
        if self.filters["show_all"]:
            self.filtered_entries = self.entries[:]
            return
        entries = self.entries[:]
        if self.filters["rare"]:
            print("[DEBUG] Filter 'rare' toggled to True")
            entries = self.filter_rare_and_regional("rare", entries)
        if self.filters["regional"]:
            print("[DEBUG] Filter 'regional' toggled to True")
            entries = self.filter_rare_and_regional("regional", entries)
        if self.selected_regions:
            entries = self.filter_rare_and_regional("region_filter", entries)
        self.filtered_entries = entries

    def _update_embeds(self):
        chunks = [self.filtered_entries[i:i+CHUNK_SIZE] for i in range(0, len(self.filtered_entries), CHUNK_SIZE)] or [[]]
        self.embeds = []
        for i, chunk in enumerate(chunks):
            start = i * CHUNK_SIZE + 1
            end = start + len(chunk) - 1
            active = [self.FILTER_LABELS[k] for k in self.FILTER_KEYS if k != "show_all" and self.filters[k]]
            if self.selected_regions:
                active.append(f"Regions: {', '.join(sorted(self.selected_regions))}")
            if self.filters["show_all"]:
                active.append(self.FILTER_LABELS["show_all"])
            footer = f"Page {i+1}/{len(chunks)} | Showing entries {start}–{end} out of {len(self.filtered_entries)} | {' | '.join(active) or 'No filters active'}"
            embed = Embed(
                title=self.title,
                description="\n".join(chunk) or "No Pokémon found.",
                color=self.primary_color() if chunk else 0xFF0000
            )
            embed.set_footer(text=footer)
            self.embeds.append(embed)
        self.page = min(self.page, len(self.embeds) - 1)

    def _build_components(self):
        self.clear_items()
        last = len(self.embeds) - 1
        for label, idx in self.NAV_BUTTONS:
            disabled = (idx in (0, 1) and self.page == 0) or (idx in (2, 3) and self.page == last)
            b = Button(label=label, style=ButtonStyle.gray, disabled=disabled, row=0)
            b.callback = [self._first, self._prev, self._next, self._last][idx]
            self.add_item(b)
        region_button_labels = set()
        for e in self.entries:
            name = self._extract_pokemon_name(e).lower()
            for region in self.ALL_REGIONS:
                if name.startswith(region + " "):
                    region_button_labels.add(region)
        for region in sorted(region_button_labels):
            b = Button(
                label=region.capitalize(),
                style=ButtonStyle.primary if region in self.selected_regions else ButtonStyle.secondary,
                row=1
            )
            b.callback = self._region_button_callback(region)
            self.add_item(b)
        region_opts = [r for r in self.user_regions if r not in region_button_labels]
        opts = [
            SelectOption(
                label=r.capitalize(),
                value=r,
                emoji=self.REGION_EMOJIS.get(r),
                default=r in self.selected_regions
            )
            for r in region_opts
        ]
        if opts:
            class RegionSelect(Select):
                def __init__(s):
                    super().__init__(placeholder="Select Regions...", options=opts, min_values=0, max_values=len(opts), row=2)
                async def callback(s, interaction):
                    await self._region_select(interaction, s.values)
            self.add_item(RegionSelect())
        if self.has_rare:
            b = Button(
                label=self.FILTER_LABELS["rare"],
                style=ButtonStyle.success if self.filters["rare"] else ButtonStyle.secondary,
                row=3
            )
            b.callback = self._toggle("rare")
            self.add_item(b)
        if self.has_regional:
            b = Button(
                label=self.FILTER_LABELS["regional"],
                style=ButtonStyle.success if self.filters["regional"] else ButtonStyle.secondary,
                row=3
            )
            b.callback = self._toggle("regional")
            self.add_item(b)
        if any(self.filters[k] for k in ("rare", "regional")) or self.selected_regions:
            b = Button(
                label=self.FILTER_LABELS["show_all"],
                style=ButtonStyle.primary if self.filters["show_all"] else ButtonStyle.secondary,
                row=3
            )
            b.callback = self._toggle("show_all", clear_others=True)
            self.add_item(b)

    def _region_button_callback(self, region):
        async def cb(interaction):
            if region in self.selected_regions:
                self.selected_regions.remove(region)
            else:
                self.selected_regions.add(region)
            self.filters["show_all"] = False
            self._update_filtered_entries()
            self._update_embeds()
            self._build_components()
            await interaction.response.edit_message(embed=self.embeds[self.page], view=self)
        return cb

    def _toggle(self, key, clear_others=False):
        async def cb(interaction):
            if clear_others:
                self.filters = {k: False for k in self.filters}
                self.selected_regions.clear()
            self.filters[key] = not self.filters[key]
            self._update_filtered_entries()
            self._update_embeds()
            self._build_components()
            await interaction.response.edit_message(embed=self.embeds[self.page], view=self)
        return cb

    async def _region_select(self, interaction, values):
        self.selected_regions = set(values)
        self.filters["show_all"] = False
        self._update_filtered_entries()
        self._update_embeds()
        self._build_components()
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    async def _first(self, interaction):
        self.page = 0
        await self._refresh(interaction)

    async def _prev(self, interaction):
        self.page = max(0, self.page - 1)
        await self._refresh(interaction)

    async def _next(self, interaction):
        self.page = min(self.page + 1, len(self.embeds) - 1)
        await self._refresh(interaction)

    async def _last(self, interaction):
        self.page = len(self.embeds) - 1
        await self._refresh(interaction)

    async def _refresh(self, interaction):
        self._update_embeds()
        self._build_components()
        await interaction.response.edit_message(embed=self.embeds[self.page], view=self)

    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author





















































































