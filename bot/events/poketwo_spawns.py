from imports.discord_imports import *
from fuzzywuzzy import fuzz
import os, csv, re, json
from utils.subcogs.pokemon import *
from submodules.poketwo_autonamer.predict import Prediction
from bot.token import use_test_bot as ut
from data.local.const import *
from motor.motor_asyncio import AsyncIOMotorClient

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058
        self.pokemon_special_names_file = 'data/commands/pokemon/pokemon_special_names.csv'
        self.pokemon_types_file = 'data/commands/pokemon/pokemon_types.csv'
        self.pokemon_description_file = 'data/commands/pokemon/pokemon_description.csv'
        self.shiny_collection = "shiny_hunt"
        self.collection_collection = "collection"
        self.type_collection = "type_ping"
        self.quest_collection = "quest_ping"
        self.regional_forms = {
            'alola': 'Alolan',
            'galar': 'Galarian',
            'hisui': 'Hisuian',
            'paldea': 'Paldean',
            'unova': 'Unovan'
        }
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.check_emoji = "✅"
        self.cross_emoji = "❌"
        self.star_emoji = "⭐"
        self.globe_emoji = "🌍"
        self.trash_emoji = "🗑️"
        self.predictor = Prediction()
        self.pp = Ping_Pokemon(bot)
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.pokemon_types = self.load_pokemon_types()
        self.quest_regions = self.load_quest_regions()
        self._type_emojis = None
        self.load_type_emojis()

    def load_type_emojis(self):
        try:
            with open("data/commands/pokemon/pokemon_emojis/_pokemon_types.json", "r", encoding="utf-8") as f:
                self._type_emojis = json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load type emojis: {e}")
            self._type_emojis = {}

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
        regions = set()
        try:
            with open(self.pokemon_description_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    region = row.get('region', '').strip().lower()
                    if region:
                        regions.add(region)
        except FileNotFoundError:
            print(f"⚠️ Pokemon description file not found: {self.pokemon_description_file}")
        return regions

    async def get_server_config(self, guild_id):
        try:
            config = await self.mongo.db["server_config"].find_one({"guild_id": guild_id})
            return config or {}
        except Exception:
            return {}

    def format_name(self, name):
        parts = name.lower().split('-')
        if len(parts) > 1 and parts[1] in self.regional_forms:
            return f"{self.regional_forms[parts[1]]} {parts[0]}".title()
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
            print(f"⚠️ Pokemon special names file not found: {self.pokemon_special_names_file}")
        return rare, regional

    async def filter_members_in_guild(self, guild, user_ids):
        return [m.mention for uid in user_ids if (m := guild.get_member(int(uid.strip('<@!>'))))]

    async def get_type_ping_users(self, guild, pokemon_name):
        try:
            if self._type_emojis is None:
                self.load_type_emojis()
            pokemon_types_data = await self.pp.data_manager.pokemon_types
            pokemon_types = pokemon_types_data.get(pokemon_name.lower(), [])
            if not pokemon_types:
                return {}
            type_pings = {}
            for ptype in pokemon_types:
                ptype = ptype.lower()
                emoji_key = f"{ptype}_type"
                emoji = self._type_emojis.get(emoji_key)
                type_ping_users = await self.mongo.db["type_ping_types"].find({"type": ptype}).to_list(None)
                mentions = set()
                for user_data in type_ping_users:
                    user_id = user_data.get("user_id")
                    if not user_id:
                        continue
                    member = guild.get_member(user_id)
                    if member:
                        mentions.add(f"<@{user_id}>")
                if mentions:
                    joined_mentions = " ".join(sorted(mentions))
                    type_label = f"{emoji if emoji else ''} {ptype.capitalize()}"
                    type_pings[type_label] = joined_mentions
            return type_pings
        except Exception as e:
            print(f"{self.error_emoji} Error in get_type_ping_users: {e}")
            return {}

    async def get_quest_ping_users(self, guild, pokemon_name):
        try:
            region = None
            with open(self.pokemon_description_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('name.en', '').strip().lower() == pokemon_name.lower():
                        region = row.get('region', '').strip().lower()
                        break
            if not region or region not in self.quest_regions:
                return []
            quest_users = await self.mongo.db[self.quest_collection].find({}).to_list(None)
            quest_pings = []
            for user_data in quest_users:
                user_regions = [r.lower() for r in user_data.get('regions', [])]
                user_id = user_data.get("user_id")
                if region in user_regions and guild.get_member(user_id):
                    ping = f"<@{user_id}>"
                    if ping not in quest_pings:
                        quest_pings.append(ping)
            return quest_pings
        except Exception as e:
            print(f"{self.error_emoji} Error in get_quest_ping_users: {e}")
            return []

    async def get_ping_users(self, guild, pokemon_name):
        def fuzzy_match(t, n): return t == n or fuzz.ratio(t, n) > 85
        try:
            c_users = await self.mongo.db[self.collection_collection].find({}).to_list(None)
            s_users = await self.mongo.db[self.shiny_collection].find({}).to_list(None)
        except Exception:
            return [], []
        shiny_ping, collection_ping = [], []
        for d in s_users:
            for p in d.get("pokemon", []):
                if fuzzy_match(pokemon_name.lower(), p.lower()):
                    if guild.get_member(d['user_id']):
                        shiny_ping.append(f"<@{d['user_id']}>")
                    break
        for d in c_users:
            for p in d.get("pokemon", []):
                if fuzzy_match(pokemon_name.lower(), p.lower()):
                    if guild.get_member(d['user_id']):
                        collection_ping.append(f"<@{d['user_id']}>")
                    break
        return shiny_ping, collection_ping

    async def output_prediction(self, message, image_url):
        name, conf = self.predictor.predict(image_url)
        formatted_name = self.format_name(name)
        try:
            conf_value = float(conf)
            pred_text = f"{formatted_name}: {conf_value:.2f}%"
        except Exception:
            pred_text = f"{formatted_name}: {conf}"
        lines = []
        server_config = await self.get_server_config(message.guild.id)
        match = re.search(r"([a-zA-Z\s-]+):\s*([\d\.]+)%", pred_text)
        if match:
            pname = match.group(1).strip().lower()
            pname, _ = Pokemon.transform_pokemon_name(pname)
            rare, reg = self.load_pokemon_data()
            is_regional_prefix = any(formatted_name.startswith(v) for v in self.regional_forms.values())
            if any(p in pname for p in rare) and server_config.get("rare_role"):
                lines.append(f"<@&{server_config['rare_role']}>")
            if (any(p in pname for p in reg) or is_regional_prefix) and server_config.get("regional_role"):
                lines.append(f"<@&{server_config['regional_role']}>")
        transformed_name, _ = Pokemon.transform_pokemon_name(formatted_name)
        shiny, collect = await self.get_ping_users(message.guild, transformed_name)
        type_pings = await self.get_type_ping_users(message.guild, transformed_name)
        quest_pings = await self.get_quest_ping_users(message.guild, transformed_name)
        if shiny:
            lines.append(f"Shiny Pings: {' '.join(sorted(set(shiny)))}")
        if collect:
            lines.append(f"Collection Pings: {' '.join(sorted(set(collect)))}")
        for type_label, mentions in type_pings.items():
            lines.append(f"{type_label}: {mentions}")
        if quest_pings:
            lines.append(f"Quest Pings: {' '.join(sorted(set(quest_pings)))}")
        lines.append("")
        lines.append(pred_text)
        await message.channel.send("\n".join(lines), reference=message)

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if message.author.id != self.target_id or message.author.bot is False:
                return
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
                ref = message.reference
                if ref:
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