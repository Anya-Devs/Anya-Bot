import csv
import json
import re
from pathlib import Path
from imports.discord_imports import *
from fuzzywuzzy import fuzz
import os, aiohttp, logging
from colorthief import ColorThief
from utils.subcogs.pokemon import *
from submodules.poketwo_autonamer.predict import Prediction
from bot.token import use_test_bot as ut
from data.local.const import *
from motor.motor_asyncio import AsyncIOMotorClient
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils

logger = logging.getLogger(__name__)

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058
        self.regional_forms = {'alola': 'Alolan', 'galar': 'Galarian', 'hisui': 'Hisuian', 'paldea': 'Paldean', 'unova': 'Unovan'}
        
        # Load flag mapping from JSON
        self.flag_map = self.load_flag_map("data/commands/pokemon/flag_map.json")

        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"
        self.emojis = {"shiny": "<:shiny_sparkle:1394386258406412380>", "collection": "<:collection_ball:1394386212961124504>"}
        self.predictor = Prediction()
        self.pp = Ping_Pokemon(bot)
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.pokemon_utils = PokemonUtils(
            self.mongo,
            type_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_types.json",
            quest_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_quest.json",
            description_file='data/commands/pokemon/pokemon_description.csv',
            id_file='data/commands/pokemon/pokemon_names.csv',
            regional_forms=self.regional_forms,
            lang_flags=self.flag_map,  # Updated to use flag_map
            bot=self.bot,
            pp=self.pp
        )
        self.pokemon_image_builder = PokemonImageBuilder()
        self.alt_names_map = self.load_alt_names("data/commands/pokemon/alt_name_v2.csv")

    def load_alt_names(self, filepath):
        alt_map = {}
        if not Path(filepath).exists():
            return alt_map
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)  # Get the header row (languages/flags)
            flag_index_map = {col.split(" ")[1].strip("()"): col for col in header[1:]}  # Map region code (en, fr, etc.) to header name
            for row in reader:
                if len(row) < 2:
                    continue
                slug = row[0].strip().lower()
                alt_names = [name.strip() for name in row[1].split(",") if name.strip()]
                alt_map[slug] = {'names': alt_names, 'flags': flag_index_map}
        return alt_map
        
     async def load_special_names(self):
        rare, regional = [], []
        try:
            with open('data/commands/pokemon/pokemon_special_names.csv', 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if len(row) >= 1 and row[0]:
                        rare.append(row[0].strip().lower())
                    if len(row) >= 2 and row[1]:
                        regional.append(row[1].strip().lower())
        except FileNotFoundError:
            pass
        return rare, regional

    def load_flag_map(self, filepath):
        if not Path(filepath).exists():
            return {}
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)

    def get_best_english_alt_name(self, slug):
        if slug not in self.alt_names_map:
            return None
        original_len = len(slug)
        candidates = [
            name for name in self.alt_names_map[slug]['names']
            if self.is_english_name(name) and len(name) < original_len
        ]
        if not candidates:
            return None
        return min(candidates, key=len)

    def is_english_name(self, name):
        return bool(re.fullmatch(r"[A-Za-z0-9\- ']+", name))

    async def output_prediction(self, message, image_url):
        try:
            slug, conf = self.predictor.predict(image_url)
            pred_text = f"{float(conf):.2f}%" if isinstance(conf, (int, float)) else str(conf)

            rare, regional = await self.load_special_names()
            server_config = await self.pokemon_utils.get_server_config(message.guild.id)

            special_roles = []
            slug_lower = slug.lower()
            if any(p in slug_lower for p in rare) and server_config.get("rare_role"):
                special_roles.append(f"<@&{server_config['rare_role']}>")
            if (any(p in slug_lower for p in regional) or any(slug_lower.startswith(f"{form}-") for form in self.regional_forms.values())) and server_config.get("regional_role"):
                special_roles.append(f"<@&{server_config['regional_role']}>")
            special_roles_str = " ".join(special_roles)

            shiny_pings, collection_pings = await self.pokemon_utils.get_ping_users(message.guild, slug)
            type_pings = await self.pokemon_utils.get_type_ping_users(message.guild, slug)
            quest_pings = await self.pokemon_utils.get_quest_ping_users(message.guild, slug)
            description, dex_number, row = self.pokemon_utils.get_description(slug)
            if not dex_number or dex_number == "???":
                dex_number = self.pokemon_utils.load_pokemon_ids().get(slug_lower, "???")

            ping_msg, embed = await self.format_messages(
                slug, type_pings, quest_pings, shiny_pings,
                collection_pings, special_roles_str, pred_text,
                dex_number, description, image_url
            )

            best_alt = self.get_best_english_alt_name(slug_lower)
            flag_emoji = self.get_flag_for_region(slug_lower)
            if best_alt:
                best_alt = f"{flag_emoji} {best_alt}"

            self.pokemon_image_builder.create_image(
                pokemon_id=int(self.pokemon_utils.load_pokemon_ids().get(slug_lower, 0)),
                pokemon_name=self.pokemon_utils.format_name(slug),
                best_name=best_alt or "",
                types=self.pokemon_utils.get_pokemon_types(slug),
                bg_url=None
            )
            saved_path = "data/events/poketwo_spawns/image/test.png"
            file = discord.File(saved_path, filename="pokemon_spawn.png")

            info_button = discord.ui.Button(label="Info", style=discord.ButtonStyle.primary)

            async def info_callback(interaction):
                await interaction.response.send_message(embed=embed, ephemeral=True)

            info_button.callback = info_callback
            view = discord.ui.View(timeout=None)
            view.add_item(info_button)

            await message.channel.send(content=ping_msg, file=file, view=view, reference=message)

        except Exception as e:
            logger.error(f"Error in output_prediction: {type(e).__name__}: {e}")
            await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)

    def get_flag_for_region(self, slug):
        # Default to USA if region not found
        for region, flag_code in self.alt_names_map.get(slug, {}).get('flags', {}).items():
            flag_emoji = self.flag_map.get(flag_code, "🇺🇸")  # Get flag emoji from flag map
            if flag_emoji:
                return flag_emoji
        return "🇺🇸"  # Default to USA if region not found

    async def format_messages(self, slug, type_pings, quest_pings, shiny_pings, collection_pings,
                              special_roles, pred_text, dex_number, description, image_url):
        # The formatting function remains unchanged
        ...

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if not ut and message.author.id == self.target_id:
                for e in message.embeds:
                    if e.title and "pokémon has appeared!" in e.title.lower() and e.image:
                        await self.output_prediction(message, e.image.url)
        except Exception as e:
            print(f"{self.cross_emoji} Error in on_message: {type(e).__name__}: {e}")

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        try:
            message = ctx.message
            if not image_url:
                if ref := message.reference:
                    message = await ctx.channel.fetch_message(ref.message_id)
                if message.attachments:
                    image_url = message.attachments[0].url
                elif message.embeds and message.embeds[0].image:
                    image_url = message.embeds[0].image.url
            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")
            await self.output_prediction(message, image_url)
        except Exception as e:
            await ctx.send(f"{self.cross_emoji} Prediction error: {type(e).__name__}: {e}")
def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
