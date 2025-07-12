from imports.discord_imports import *
from fuzzywuzzy import fuzz
import os, csv, re
from utils.subcogs.pokemon import *
from submodules.poketwo_autonamer.predict import Prediction
from bot.token import use_test_bot as ut
from data.local.const import *
from motor.motor_asyncio import AsyncIOMotorClient

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.test_mode = ut
        self.target_id = 716390085896962058
        self.target_title = "pokémon has appeared!"
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
        except:
            return {}

    def format_name(self, n):
        p = n.lower().split('-')
        return (self.regional_forms[p[1]] + ' ' + p[0] if len(p) > 1 and p[1] in self.regional_forms else n).replace('-', ' ').title()

    def load_pokemon_data(self):
        rare, reg = [], []
        try:
            with open(self.pokemon_special_names_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if len(row) >= 1 and row[0]:
                        rare.append(row[0].strip().lower())
                    if len(row) >= 2 and row[1]:
                        reg.append(row[1].strip().lower())
        except FileNotFoundError:
            print(f"⚠️ Pokemon special names file not found: {self.pokemon_special_names_file}")
        return rare, reg

    async def filter_members_in_guild(self, guild, user_ids):
        return [m.mention for uid in user_ids if (m := guild.get_member(int(uid.strip('<@!>'))))]

    async def get_type_ping_users(self, guild, pokemon_name):
        try:
            pokemon_types_data = await self.pp.data_manager.pokemon_types
            pokemon_types = pokemon_types_data.get(pokemon_name.lower(), [])
            if not pokemon_types:
                return [], []
            shiny_pings = []
            collection_pings = []
            for ptype in pokemon_types:
                shiny_users = await self.mongo.db[f"{self.shiny_collection}_types"].find({"type": ptype}).to_list(None)
                collection_users = await self.mongo.db[f"{self.collection_collection}_types"].find({"type": ptype}).to_list(None)
                for user_data in shiny_users:
                    user_id = user_data.get("user_id")
                    if guild.get_member(user_id):
                        ping = f"<@{user_id}>"
                        if ping not in shiny_pings:
                            shiny_pings.append(ping)
                for user_data in collection_users:
                    user_id = user_data.get("user_id")
                    if guild.get_member(user_id):
                        ping = f"<@{user_id}>"
                        if ping not in collection_pings:
                            collection_pings.append(ping)
            return shiny_pings, collection_pings
        except Exception as e:
            print(f"Error in get_type_ping_users: {e}")
            return [], []

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
            print(f"Error in get_quest_ping_users: {e}")
            return []

    async def output_prediction(self, message, image_url):
        name, conf = self.predictor.predict(image_url)
        formatted_name = self.format_name(name)
        try:
            conf_value = float(conf)
            pred_text = f"{formatted_name}: {conf_value:.2f}%"
        except:
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
        type_shiny, type_collect = await self.get_type_ping_users(message.guild, transformed_name)
        quest_pings = await self.get_quest_ping_users(message.guild, transformed_name)
        all_shiny = list(set(shiny + type_shiny))
        all_collect = list(set(collect + type_collect))
        if all_shiny:
            lines.append(f"Shiny Pings: {' '.join(all_shiny)}")
        if all_collect:
            lines.append(f"Collection Pings: {' '.join(all_collect)}")
        if quest_pings:
            lines.append(f"Quest Pings: {' '.join(quest_pings)}")
        lines += ["", pred_text]
        await message.channel.send("\n".join(lines), reference=message)

    async def get_ping_users(self, guild, pokemon_name):
        def fuzzy_match(t, n): return t == n or fuzz.ratio(t, n) > 85
        try:
            c_users = await self.mongo.db[self.collection_collection].find({}).to_list(None)
            s_users = await self.mongo.db[self.shiny_collection].find({}).to_list(None)
        except:
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

    @commands.Cog.listener()
    async def on_message(self, m):
        try:
            if m.author.id != (self.bot.user.id if self.test_mode else self.target_id):
                return
            for e in m.embeds:
                if self.target_title in (e.title or "").lower() and e.image:
                    await self.output_prediction(m, e.image.url)
        except Exception as e:
            print(f"{self.cross_emoji} Error in on_message: {type(e).__name__}: {e}")

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        try:
            m = ctx.message
            if not image_url:
                ref = m.reference
                if ref:
                    m = await ctx.channel.fetch_message(ref.message_id)
                if m.attachments:
                    image_url = m.attachments[0].url
                elif m.embeds and m.embeds[0].image:
                    image_url = m.embeds[0].image.url
            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")
            await self.output_prediction(m, image_url)
        except Exception as e:
            await ctx.send(f"{self.cross_emoji} Prediction error: {type(e).__name__}: {e}")


def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
