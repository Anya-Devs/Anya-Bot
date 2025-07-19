from imports.discord_imports import *
from fuzzywuzzy import fuzz
import os, csv, re, json
from colorthief import ColorThief
from utils.subcogs.pokemon import *
from submodules.poketwo_autonamer.predict import Prediction
from bot.token import use_test_bot as ut
from data.local.const import *
from motor.motor_asyncio import AsyncIOMotorClient
import logging
import aiohttp
import io

logger = logging.getLogger(__name__)

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058

        self.pokemon_description_file = 'data/commands/pokemon/pokemon_description.csv'
        self.pokemon_special_names_file = 'data/commands/pokemon/pokemon_special_names.csv'
        self.pokemon_id_file = 'data/commands/pokemon/pokemon_names.csv'
        self.type_emojis_file = "data/commands/pokemon/pokemon_emojis/_pokemon_types.json"
        self.quest_emojis_file = "data/commands/pokemon/pokemon_emojis/_pokemon_quest.json"

        self.shiny_collection = "shiny_hunt"
        self.collection_collection = "collection"
        self.type_collection = "type_ping"
        self.quest_collection = "quest_ping"

        self.regional_forms = {
            'alola': 'Alolan', 'galar': 'Galarian', 'hisui': 'Hisuian',
            'paldea': 'Paldean', 'unova': 'Unovan'
        }

        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"

        self.emojis = {
            "shiny": "<:shiny_sparkle:1394386258406412380>",
            "collection": "<:collection_ball:1394386212961124504>"
        }

        self.predictor = Prediction()
        self.pp = Ping_Pokemon(bot)
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])

        self._type_emojis = {}
        self._quest_emojis = {}

        self.load_emojis()
        self.quest_regions = self.load_quest_regions()
        self.pokemon_ids = self.load_pokemon_ids()

        self.lang_flags = {
            "ja": "🇯🇵",
            "de": "🇩🇪",
            "fr": "🇫🇷",
            "en": "🇺🇸",
        }

    def load_emojis(self):
        for file, attr in [(self.type_emojis_file, "_type_emojis"), (self.quest_emojis_file, "_quest_emojis")]:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    setattr(self, attr, json.load(f))
            except Exception:
                setattr(self, attr, {})

    def load_quest_regions(self):
        regions = set()
        try:
            with open(self.pokemon_description_file, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    if region := row.get('region', '').strip().lower():
                        regions.add(region)
        except FileNotFoundError:
            pass
        return regions

    def load_pokemon_ids(self):
        id_map = {}
        try:
            with open(self.pokemon_id_file, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    id_map[row['name'].lower()] = row['id']
        except Exception as e:
            logger.warning(f"Failed to load Pokémon IDs: {e}")
        return id_map

    def format_name(self, name):
        parts = name.lower().split('-')
        if len(parts) > 1 and parts[1] in self.regional_forms:
            return f"{self.regional_forms.get(parts[1], '').title()} {parts[0].title()}"
        return name.replace('-', ' ').title()

    def load_pokemon_data(self):
        rare, regional = [], []
        try:
            with open(self.pokemon_special_names_file, 'r', newline='', encoding='utf-8') as f:
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

    def get_pokemon_row(self, slug):
        try:
            with open(self.pokemon_description_file, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    if row.get("slug", "").lower() == slug.lower():
                        return row
        except FileNotFoundError:
            pass
        return None

    def get_description(self, slug):
        row = self.get_pokemon_row(slug)
        if row:
            return row.get("description", ""), row.get("dex_number", "???"), row
        fallback_id = self.pokemon_ids.get(slug.lower(), "???")
        return "", fallback_id, {}

    def get_pokemon_types(self, slug):
        row = self.get_pokemon_row(slug)
        if not row:
            return []
        types = []
        if row.get("type.0"):
            types.append(row["type.0"].strip().lower())
        if row.get("type.1") and row["type.1"].strip():
            types.append(row["type.1"].strip().lower())
        return types

    def get_pokemon_region(self, slug):
        row = self.get_pokemon_row(slug)
        if not row:
            return ""
        return row.get("region", "").capitalize()

    async def get_server_config(self, guild_id):
        return await self.mongo.db["server_config"].find_one({"guild_id": guild_id}) or {}

    async def get_type_ping_users(self, guild, pokemon_name):
        try:
            if not self._type_emojis:
                self.load_emojis()

            pokemon_types_data = await self.pp.data_manager.pokemon_types
            pokemon_types = pokemon_types_data.get(pokemon_name.lower(), [])
            if not pokemon_types:
                pokemon_types = self.get_pokemon_types(pokemon_name)

            if not pokemon_types:
                return {}

            type_pings = {}
            for ptype in pokemon_types:
                ptype_lower = ptype.lower()
                emoji = self._type_emojis.get(f"{ptype_lower}_type", "")
                users = await self.mongo.db["type_ping_types"].find({"type": ptype_lower}).to_list(None)

                mentions = {
                    f"<@{user['user_id']}>"
                    for user in users
                    if user.get("user_id") and guild.get_member(user["user_id"])
                }

                if mentions:
                    label = f"{emoji} {ptype.capitalize()} Type".strip()
                    type_pings[label] = "".join(sorted(mentions))

            return type_pings

        except Exception as e:
            print(f"{self.error_emoji} Error in get_type_ping_users: {e}")
            return {}

    async def get_quest_ping_users(self, guild, pokemon_name):
        try:
            with open(self.pokemon_description_file, 'r', encoding='utf-8') as f:
                region = next((row['region'].lower() for row in csv.DictReader(f) if row.get("slug", "").lower() == pokemon_name.lower()), None)
            if not region or region not in self.quest_regions:
                return []
            users = await self.mongo.db[self.quest_collection].find({}).to_list(None)
            return [f"<@{u['user_id']}>" for u in users if guild.get_member(u["user_id"]) and region in [r.lower() for r in u.get("regions", [])]]
        except:
            return []

    async def get_ping_users(self, guild, pokemon_name):
        def fuzzy(t, n): return t == n or fuzz.ratio(t, n) > 85
        try:
            shiny = await self.mongo.db[self.shiny_collection].find({}).to_list(None)
            collect = await self.mongo.db[self.collection_collection].find({}).to_list(None)
            shiny_mentions = [f"<@{u['user_id']}>" for u in shiny if any(fuzzy(pokemon_name.lower(), p.lower()) for p in u.get("pokemon", [])) and guild.get_member(u["user_id"])]
            collect_mentions = [f"<@{u['user_id']}>" for u in collect if any(fuzzy(pokemon_name.lower(), p.lower()) for p in u.get("pokemon", [])) and guild.get_member(u["user_id"])]
            return shiny_mentions, collect_mentions
        except:
            return [], []

    async def get_image_color(self, url):
        fallback = 0x3498db
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return fallback
                    data = await resp.read()
            with io.BytesIO(data) as img_bytes:
                color_thief = ColorThief(img_bytes)
                r, g, b = color_thief.get_color(quality=1)
                return (r << 16) + (g << 8) + b
        except Exception as e:
            logger.warning(f"Failed to get image color: {e}")
            return fallback

    async def format_messages(self, slug, type_pings, quest_pings, shiny_pings, collection_pings, rare_regional_line, pred_text, dex_number, description, image_url):
        lines = []
        try:
            if rare_regional_line:
                lines.append(rare_regional_line)
            formatted_name = self.format_name(slug)
            lines.append(f"**{formatted_name}**: {pred_text}")

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
                lines.append("**Pings:** " + " • ".join(ping_parts))

            actual_types = self.get_pokemon_types(slug)
            actual_region = self.get_pokemon_region(slug)
            emoji_types = [f"{self._type_emojis.get(f'{t.lower()}_type','')} {t.title()}" for t in actual_types if t]

            _, _, row = self.get_description(slug)
            if not row:
                alt_names = []
            else:
                original = slug.lower()
                alt_names = []
                for lang_code in ['ja', 'de', 'fr', 'en2', 'en']:
                    key = f"name.{lang_code}"
                    if key in row and row[key] and row[key].lower() != original:
                        flag = self.lang_flags.get(lang_code.replace('2',''), "")
                        alt_names.append(f"{flag} {row[key]}")

                alt_names = list(set(alt_names))
                if alt_names:
                    min_len = min(len(name) for name in alt_names)
                    alt_names = [n for n in alt_names if len(n) == min_len]
                else:
                    alt_names = []

            # Fix here: Use slug-based URL for forms, fallback to dex_number, else image_url
            if slug and slug.lower() != "" and slug.lower() != "???":
                thumb_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{self.pokemon_ids.get(slug, '0')}.png"
            elif dex_number and dex_number.isdigit():
                thumb_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{dex_number}.png"
            else:
                thumb_url = image_url

            color = await self.get_image_color(thumb_url)

            embed = discord.Embed(color=color)
            if description:
                embed.description = description
            if alt_names:
                embed.add_field(name="Alt Names", value="\n".join(alt_names), inline=True)
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

    async def output_prediction(self, message, image_url):
        try:
            slug, conf = self.predictor.predict(image_url)  # raw slug e.g. 'lycanroc-midnight'

            pred_text = f"{float(conf):.2f}%" if isinstance(conf, (int, float)) else str(conf)

            rare, regional = self.load_pokemon_data()
            server_config = await self.get_server_config(message.guild.id)

            special_roles = []
            slug_lower = slug.lower()

            if any(p in slug_lower for p in rare) and server_config.get("rare_role"):
                special_roles.append(f"<@&{server_config['rare_role']}>")
            if (any(p in slug_lower for p in regional) or any(slug_lower.startswith(f"{form}-") for form in self.regional_forms.values())) and server_config.get("regional_role"):
                special_roles.append(f"<@&{server_config['regional_role']}>")

            shiny_pings, collection_pings = await self.get_ping_users(message.guild, slug)
            type_pings = await self.get_type_ping_users(message.guild, slug)
            quest_pings = await self.get_quest_ping_users(message.guild, slug)
            description, dex_number, _ = self.get_description(slug)

            if not dex_number or dex_number == "???":
                dex_number = self.pokemon_ids.get(slug_lower, "???")

            ping_msg, embed = await self.format_messages(
                slug, type_pings, quest_pings, shiny_pings,
                collection_pings, " ".join(special_roles), pred_text,
                dex_number, description, image_url
            )

            await message.channel.send(content=ping_msg, embed=embed, reference=message)

        except Exception as e:
            logger.error(f"Error in output_prediction: {type(e).__name__}: {e}")
            await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)

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
