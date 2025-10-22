import os, json, random, asyncio, requests, aiohttp, aiofiles, concurrent.futures
from urllib.request import urlopen
import numpy as np, cv2 as cv
from PIL import Image
from imports.log_imports import *
from imports.discord_imports import *
from utils.cogs.pokemon import *
from utils.subcogs.pokemon import *
from utils.subcogs.utils.mongo import *
from utils.cogs.poketwo_commands import *
from bot.events.starboard import StarboardProcessor


from data.local.const import error_custom_embed as err_embed, primary_color as p_color



class Pokemon(commands.Cog):
    def __init__(self, bot, folder="data/commands/pokemon/pokemon_images"):
        self.bot, self.folder = bot, folder
        self.uid, self.bot_ids = 716390085896962058, [854233015475109888, 874910942490677270]
        self.msg, self.cache, self.color_mem = "Shiny hunt pings:", {}, []
        self.color, self.err = p_color, err_embed
        self.ph = PokemonNameHelper()
        self.api, self.info = "https://pokeapi.co/api/v2/pokemon", "https://pokeapi.co/api/v2/pokemon/{}/"
        self.poke_json = "data/commands/pokemon/pokemon.json"
        self.pokemon_names_csv = os.path.join("data", "commands", "pokemon", "pokemon_names.csv")

        self.wait = 11

    @commands.command(help="Displays Pokémon dex info.", aliases=["dex", "d"])
    async def pokedex(self, ctx, *, pokemon=None, form=None):
     async with ctx.typing():
        ph = PokemonNameHelper()
        pc, pp = Pokemon_Commands(self.bot), PoketwoCommands(self.bot)

        if not pokemon:
            with open(self.pokemon_names_csv, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                names = [row["name"] for row in reader if row.get("name")]
            pokemon = random.choice(names)

        is_shiny = "shiny" in pokemon.lower()
        name_input = pokemon.replace("shiny", "").strip().lower()
        name, _ = ph.transform_name(name_input)
        pid = name.replace(" ", "-") if name else random.randint(1, 1302)
        form_suffix = f"-{form}" if form else ""

        if not os.path.exists(self.poke_json):
            with open(self.poke_json, "w") as f: f.write("{}")
        with open(self.poke_json) as f:
            cache = json.load(f)

        if str(pid) in cache:
            return await pc.send_pokemon_info(ctx, data=cache[str(pid)], type="shiny" if is_shiny else None, color=p_color())

        url = f"https://pokeapi.co/api/v2/pokemon-form/{pid}{form_suffix}" if form else self.info.format(pid)
        r = requests.get(url)
        if r.status_code != 200:
            return await ctx.send(f"{'Form data' if form else 'Data'} not found for `{pid}`.")

        try:
            data = r.json()
            await (self.send_form_pokemon if form else pc.send_pokemon_info)(
                ctx, data=data, type="shiny" if is_shiny else None, color=p_color()
            )
            cache[str(pid)] = data
            with open(self.poke_json, "w") as f: json.dump(cache, f, indent=2)
        except json.JSONDecodeError:
            await ctx.send(f"Failed to parse JSON for `{pid}`.")


class PoketwoCommands(commands.Cog):
    """PokéTwo-like commands with .pt command group."""

    def __init__(self, bot):
        self.bot = bot

        # Collections
        self.shiny_collection = "shiny_hunt"
        self.collection_collection = "collection"
        self.type_collection = "type_ping"
        self.quest_collection = "quest_ping"
        self.server_config_collection = "server_config"

        # Files & Managers
        self.pokemon_names_file = "data/commands/pokemon/pokemon_names.csv"
        self.pokemon_types_file = "data/commands/pokemon/pokemon_types.csv"
        self.pokemon_rarity_file = "data/commands/pokemon/pokemon_rarity.csv"
        self.embed_default_color = primary_color()
        self.RESULTS_PER_PAGE = 10
        self.MAX_POKEMON = 50

        # Emojis
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"

        try:
            self.mongo_sh = MongoShHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
            self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        except Exception as e:
            logger.error(f"Failed to initialize MongoDB: {e}")
            self.mongo = None

        try:
            self.pe = Pokemon_Emojis(bot)
            self.ph = PokemonNameHelper()
        except Exception as e:
            logger.error(f"Failed to initialize Pokemon Emojis/NameHelper: {e}")
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
            icons={"success": "<:check:1399603549100441723>", "error": "<:x_:1399603637105463386>"},
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
                    if row.get("types"):
                        for p in row["types"].strip('"').split(','):
                            types.add(p.strip().lower())
        except FileNotFoundError:
            logger.warning(f"Pokemon types file not found: {self.pokemon_types_file}")
            types = {"normal", "fire", "water", "electric", "grass", "ice", "fighting", "poison", "ground",
                     "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark", "steel", "fairy"}
        return sorted(types)

    def load_quest_regions(self):
        return {"kanto", "johto", "hoenn", "sinnoh", "unova", "kalos", "alola", "galar", "hisui", "paldea"}

    async def get_server_config(self, guild_id: int) -> dict:
        if not self.mongo:
            logger.warning("MongoDB not initialized, returning default config")
            return {
                "images_enabled": True,
                "buttons_enabled": True,
                "rare_enabled": True,
                "regional_enabled": True,
                "cl_enabled": True,
                "sh_enabled": True,
                "type_enabled": True,
                "quest_enabled": True
            }
        config = await self.mongo.db[self.server_config_collection].find_one({"guild_id": guild_id}) or {}
        defaults = {
            "images_enabled": True,
            "buttons_enabled": True,
            "rare_enabled": True,
            "regional_enabled": True,
            "cl_enabled": True,
            "sh_enabled": True,
            "type_enabled": True,
            "quest_enabled": True
        }
        config.update({k: config.get(k, v) for k, v in defaults.items()})
        logger.debug(f"Retrieved server config for guild {guild_id}: {config}")
        return config

    def create_config_embed(self, config: dict, guild: discord.Guild) -> discord.Embed:
        rare_role = guild.get_role(config.get("rare_role"))
        regional_role = guild.get_role(config.get("regional_role"))

        embed = discord.Embed(
            title="Pokétwo Server Configuration",
            description="Current settings for spawns and notifications.",
            color=self.embed_default_color
        )
        embed.add_field(
            name="Spawn Settings",
            value=(
                f"- Images Enabled: `{'✅' if config.get('images_enabled', True) else '❌'}`\n"
                f"- Buttons Enabled: `{'✅' if config.get('buttons_enabled', True) else '❌'}`"
            ),
            inline=False
        )
        embed.add_field(
            name="Notification Settings",
            value=(
                f"- Rare Pokémon: `{'✅' if config.get('rare_enabled', True) else '❌'}` ({rare_role.mention if rare_role else 'Not set'})\n"
                f"- Regional Pokémon: `{'✅' if config.get('regional_enabled', True) else '❌'}` ({regional_role.mention if regional_role else 'Not set'})\n"
                f"- Collection Pings: `{'✅' if config.get('cl_enabled', True) else '❌'}`\n"
                f"- Shiny Pings: `{'✅' if config.get('sh_enabled', True) else '❌'}`\n"
                f"- Type Pings: `{'✅' if config.get('type_enabled', True) else '❌'}`\n"
                f"- Quest Pings: `{'✅' if config.get('quest_enabled', True) else '❌'}`"
            ),
            inline=False
        )
        return embed

    async def show_help(self, ctx, topic: str = None):
        await self.pt_help(ctx, topic)

    # -------------------
    # Main Command Group
    # -------------------
    @commands.group(name="pt", invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def pt(self, ctx):
        await self.show_help(ctx)

    @commands.cooldown(1, 5, commands.BucketType.user)
    @pt.command(name="help")
    async def pt_help(self, ctx, topic: str = None):
        # Assuming pt_help_description is defined elsewhere
        description = pt_help_description.format(*[ctx.prefix] * pt_help_description.count("{}"))
        embed = discord.Embed(title="How to Use (.pt)", description=description, color=self.embed_default_color)

        class DeleteButton(discord.ui.View):
            def __init__(self, ctx):
                super().__init__(timeout=None)
                self.ctx = ctx

            @discord.ui.button(label="🗑️", style=discord.ButtonStyle.red)
            async def delete_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id == self.ctx.author.id:
                    await interaction.message.delete()
                    await self.ctx.message.delete()

        await ctx.reply(embed=embed, view=DeleteButton(ctx), mention_author=False)

    # -------------------
    # Hidden non-group aliases
    # -------------------
    @commands.command(name="tp", hidden=True)
    async def hidden_type_ping(self, ctx): await self.type_ping(ctx)

    @commands.command(name="qp", hidden=True)
    async def hidden_quest_ping(self, ctx): await self.quest_ping(ctx)

    @commands.command(name="shiny", aliases=["sh"], hidden=True)
    async def hidden_shiny_hunt(self, ctx, action: str = None, *, pokemon: str = None):
        await self.shiny_hunt(ctx, action, pokemon=pokemon)

    @commands.command(name="collection", aliases=["cl", "col"], hidden=True)
    async def hidden_collection_manage(self, ctx, *, args: str = "list"):
        await self.collection_manage(ctx, args=args)

    # -------------------
    # Config Command Group
    # -------------------
    @pt.group(name="config", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def config(self, ctx):
        """View current server configuration."""
        guild_id = ctx.guild.id
        config = await self.get_server_config(guild_id)
        embed = self.create_config_embed(config, ctx.guild)
        view = ConfigView(self, guild_id, self.mongo, config)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # -------------------
    # Type Ping
    # -------------------
    @pt.command(name="tp")
    async def type_ping(self, ctx):
        user_id = ctx.author.id
        try:
            current_types_data = await self.mongo.db["type_ping_types"].find({"user_id": user_id}).to_list(None)
            current_types = [entry["type"] for entry in current_types_data]
        except Exception as e:
            logger.error(f"Failed to fetch type pings for user {user_id}: {e}")
            current_types = []

        view = PokemonTypeSelect(self.bot, user_id, "type_ping", self.mongo, self.pokemon_types, current_types)
        await view.refresh_view()
        embed = await view._create_embed(ctx=ctx)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # -------------------
    # Quest Ping
    # -------------------
    @pt.command(name="qp")
    async def quest_ping(self, ctx):
        user_id = ctx.author.id
        try:
            current_regions_data = await self.mongo.db[self.quest_collection].find_one({"user_id": user_id})
            current_regions = current_regions_data.get("regions", []) if current_regions_data else []
        except Exception as e:
            logger.error(f"Failed to fetch quest pings for user {user_id}: {e}")
            current_regions = []

        available_regions = sorted(list(self.load_quest_regions()))
        view = PokemonRegionSelect(self.bot, user_id, self.quest_collection, self.mongo, available_regions, current_regions)
        await view.refresh_view()
        embed = await view._create_embed(ctx=ctx)
        await ctx.reply(embed=embed, view=view, mention_author=False)

    # -------------------
    # Shiny Hunt
    # -------------------
    @pt.command(name="shiny", aliases=["sh"])
    async def shiny_hunt(self, ctx, action: str = None, *, pokemon: str = None):
        try:
            user_id = ctx.author.id
            prefix = ctx.prefix

            if action == "help":
                return await self.show_help(ctx, "shiny")

            if action == "remove":
                deleted = await self.mongo.db[self.shiny_collection].delete_many({"user_id": user_id})
                msg = "✅ Your shiny hunt has been cleared." if deleted.deleted_count > 0 else "⚠ You don't have a shiny hunt to remove."
                return await ctx.reply(embed=discord.Embed(description=msg, color=self.embed_default_color))

            if not action and not pokemon:
                cur = await self.mongo.list(self.shiny_collection, user_id) if self.mongo else []
                if not cur:
                    return await ctx.reply(embed=discord.Embed(description="You don't have a shiny hunt set.", color=self.embed_default_color))
                name = cur[0]
                emoji = self.pe.get_emoji_for_pokemon(Pokemon_Subcogs.pokemon_name_to_id(name)) if self.pe else ""
                disp = self.data_manager.display_name_with_region(name)
                return await ctx.reply(embed=discord.Embed(description=f"You are shiny hunting: **{emoji} {disp}**", color=self.embed_default_color))

            if action not in {"add", "remove", "list", "clear"}:
                action, pokemon = "add", f"{action} {pokemon}".strip() if pokemon else action
            flags = self.flag_parser.parse_flags_from_string(pokemon or "")
            await self.collection_handler.handle_collection(ctx, self.shiny_collection, action, pokemon=pokemon, flags_obj=flags, max_one=True)
        except Exception as e:
            logger.error(f"Error in shiny_hunt command: {e}")
            await ctx.reply(embed=discord.Embed(description=f"❌ Error: {e}", color=self.embed_default_color))

    # -------------------
    # Collection
    # -------------------
    @pt.command(name="collection", aliases=["cl", "col"])
    async def collection_manage(self, ctx, *, args: str = "list"):
        action = "list"
        remaining = args
        args_lower = args.lower().strip()
        if args_lower.startswith(('add ', 'remove ', 'delete ', 'clear', 'help')):
            parts = args.split(' ', 1)
            action = parts[0].lower()
            if action == "delete":
                action = "remove"
            remaining = parts[1] if len(parts) > 1 else ""
        if action == "help":
            return await self.show_help(ctx, "collection")
        flags_dict = self.flag_parser.parse_flags_from_string(remaining)
        pokemon_names, _ = self.flag_parser.extract_pokemon_names_from_string(remaining, action)
        await self.collection_handler.handle_collection(ctx, self.collection_collection, action, pokemon=pokemon_names or None, flags_obj=flags_dict)

    # -------------------
    # Shiny Hunt Config
    # -------------------
    @pt.group(name="shinychannel", aliases=["sc"], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def shiny_channel(self, ctx, *channels: discord.TextChannel):
        """Set or view protected shiny channels."""
        guild_id = ctx.guild.id
        if channels:
            channel_ids = [ch.id for ch in channels]
            await self.mongo_sh.set_shiny_channels(guild_id, channel_ids)
            mentions = ", ".join(ch.mention for ch in channels)
            await ctx.reply(f"✅ Shiny hunt protection enabled in: {mentions}", mention_author=False)
        else:
            current_channels = await self.mongo_sh.get_shiny_channels(guild_id)
            mentions = ", ".join(f"<#{ch_id}>" for ch_id in current_channels) if current_channels else "None"
            await ctx.reply(f"🔹 Current protected channels: {mentions}", mention_author=False)

    @shiny_channel.group(name="log", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def shiny_log(self, ctx, channel: discord.TextChannel = None):
        """Set, remove, or view the shiny log channel."""
        guild_id = ctx.guild.id

        if channel:
            await self.mongo_sh.set_shiny_log_channel(guild_id, channel.id)
            await ctx.reply(f"✅ Shiny log channel set to {channel.mention}", mention_author=False)
        else:
            current = await self.mongo_sh.get_shiny_log_channel(guild_id)
            if current:
                await ctx.reply(f"🔹 Current shiny log channel: <#{current}>", mention_author=False)
            else:
                await ctx.reply("⚠ No shiny log channel set.", mention_author=False)

    @shiny_log.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def remove_log(self, ctx):
        """Remove the shiny log channel."""
        guild_id = ctx.guild.id
        await self.mongo_sh.remove_shiny_log_channel(guild_id)
        await ctx.reply("✅ Shiny log channel removed.", mention_author=False)




def setup(bot):
    bot.add_cog(Pokemon(bot))
    bot.add_cog(PoketwoCommands(bot))
    bot.add_cog(Pokemon_Emojis(bot))
    bot.add_cog(PoketwoSpecialPing(bot))