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
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"
        self.emojis = {"shiny": "<:shiny_sparkle:1394386258406412380>", "collection": "<:collection_ball:1394386212961124504>"}
        self.predictor = Prediction()
        self.pp = Ping_Pokemon(bot)
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.lang_flags = self.load_flag_map("data/commands/pokemon/flag_map.json")
        self.pokemon_utils = PokemonUtils(
            self.mongo,
            type_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_types.json",
            quest_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_quest.json",
            description_file='data/commands/pokemon/pokemon_description.csv',
            id_file='data/commands/pokemon/pokemon_names.csv',
            regional_forms=self.regional_forms,
            lang_flags=self.lang_flags,
            bot=self.bot,
            pp=self.pp
        )
        self.pokemon_image_builder = PokemonImageBuilder()
        self.alt_names_map = self.load_alt_names("data/commands/pokemon/alt_names.csv")
        self.flag_map = self.load_flag_map("data/commands/pokemon/flag_map.json")

    def load_alt_names(self, filepath):
        alt_map = {}
        if not Path(filepath).exists():
            return alt_map
        with open(filepath, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) < 2:
                    continue
                slug = row[0].strip().lower()
                alt_names = [name.strip() for name in row[1].split(",") if name.strip()]
                alt_map[slug] = alt_names
        return alt_map

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
            name for name in self.alt_names_map[slug]
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

            raw_flag = self.flag_map.get("en", "{flag_us}")
            flag_emoji = PokemonImageBuilder.country_code_to_flag_emoji(
                re.search(r'{flag_([a-z\-]+)}', raw_flag).group(1)
            ) if '{flag_' in raw_flag else raw_flag

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

    async def format_messages(self, slug, type_pings, quest_pings, shiny_pings, collection_pings,
                              special_roles, pred_text, dex_number, description, image_url):
        lines = []
        try:
            if special_roles:
                lines.append(special_roles)
            formatted_name = self.pokemon_utils.format_name(slug)
            best_alt = self.get_best_english_alt_name(slug.lower())
            display_name = self.pokemon_utils.format_name(slug)
            lines.append(f"**{display_name}**: {pred_text}")

            ping_parts = []
            if shiny_pings:
                ping_parts.append(f"Shiny: {' '.join(shiny_pings)}")
            if collection_pings:
                ping_parts.append(f"Collectors: {' '.join(collection_pings)}")
            if quest_pings:
                ping_parts.append(f"Regional: {' '.join(quest_pings)}")
            if type_pings:
                type_parts = [f"{label}: {users}" for label, users in type_pings.items() if users]
                if type_parts:
                    ping_parts.append("Types: " + " | ".join(type_parts))
            if ping_parts:
                lines.append("\n".join(ping_parts))

            actual_types = self.pokemon_utils.get_pokemon_types(slug)
            actual_region = self.pokemon_utils.get_pokemon_region(slug)
            emoji_types = [f"{self.pokemon_utils._type_emojis.get(f'{t.lower()}_type','')} {t.title()}" for t in actual_types if t]

            alt_names_field = []
            if slug.lower() in self.alt_names_map:
                alt_names_list = self.alt_names_map[slug.lower()]
                for alt_name in alt_names_list:
                    alt_names_field.append(alt_name)

            thumb_url = (f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{dex_number}.png"
                         if slug and slug.lower() not in ("", "???") else image_url)
            color = await self.pokemon_utils.get_image_color(thumb_url)

            embed = discord.Embed(color=color)
            if description:
                embed.description = description
            if alt_names_field:
                embed.add_field(name="Alt Names", value="\n".join(alt_names_field[:10]), inline=True)
            if emoji_types:
                embed.add_field(name="Types", value="\n".join(emoji_types), inline=True)
            if actual_region:
                embed.add_field(name="Region", value=actual_region, inline=True)
            embed.set_thumbnail(url=thumb_url)
            return "\n".join(lines), embed

        except Exception as e:
            logger.error(f"Error in format_messages: {type(e).__name__}: {e}")
            fallback = f"**{slug}**\nFailed to format spawn info."
            embed = discord.Embed(color=0xFF0000, description="An error occurred generating this embed.")
            return fallback, embed

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
