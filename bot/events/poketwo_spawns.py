from imports.discord_imports import *
from fuzzywuzzy import fuzz
import os, asyncio, csv, re
from utils.subcogs.pokemon import Ping_Pokemon, Pokemon_Subcogs
from submodules.poketwo_autonamer.predict import Prediction
from bot.token import use_test_bot as ut
from data.local.const import *
from motor.motor_asyncio import AsyncIOMotorClient

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.test_mode = ut
        self.shiny_collection = "shiny_hunt"
        self.collection_collection = "collection"
        self.target_id = 716390085896962058
        self.target_title = "pokémon has appeared!"
        self.predictor = Prediction()
        self.pp = Ping_Pokemon(bot)
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.message_rare_pokemon = "<@&1278580577104040023>"
        self.message_regional_pokemon = "<@&1278580577104040022>"
        self.csv_file = 'data/commands/pokemon/pokemon_special_names.csv'

    def format_name(self,n):
        f={'alola':'Alolan','galar':'Galarian','hisui':'Hisuian','paldea':'Paldean','unova':'Unovan'}
        p=n.lower().split('-')
        return (f[p[1]]+' '+p[0] if len(p)>1 and p[1] in f else n).replace('-',' ').title()

    def load_pokemon_data(self):
        r,reg=[],[]
        try:
            with open(self.csv_file,'r',newline='',encoding='utf-8') as f:
                reader=csv.reader(f)
                next(reader)
                for row in reader:
                    if len(row)>=1 and row[0]: r.append(row[0].strip().lower())
                    if len(row)>=2 and row[1]: reg.append(row[1].strip().lower())
        except: pass
        return r,reg

    

    async def filter_members_in_guild(self,guild,user_ids):
        return [m.mention for uid in user_ids if (m:=guild.get_member(int(uid.strip('<@!>'))))]

    async def output_prediction(self,message,image_url):
        name,conf=self.predictor.predict(image_url)
        fn=self.format_name(name)
        try: cv=float(conf); pred=f"{fn}: {cv:.2f}%"
        except: pred=f"{fn}: {conf}"
        lines=[]
        match=re.search(r"([a-zA-Z\s-]+):\s*([\d\.]+)%",pred)
        if match:
            pname=match.group(1).strip().lower()
            pname,_=Pokemon.transform_pokemon_name(pname)
            rare,reg=self.load_pokemon_data()
            if any(fuzz.ratio(pname,p)>90 for p in rare): lines.append(self.message_rare_pokemon)
            if any(fuzz.ratio(pname,p)>90 for p in reg): lines.append(self.message_regional_pokemon)
        tname,_=Pokemon.transform_pokemon_name(fn)
        shiny,collect=await self.get_ping_users(message.guild,tname)
        if shiny: lines.append(f"Shiny Pings: {' '.join(shiny)}")
        if collect: lines.append(f"Collection Pings: {' '.join(collect)}")
        lines+=["",pred]
        await message.channel.send("\n".join(lines),reference=message)

    async def get_ping_users(self,guild,pokemon_name):
        def fuzzy_match(t,n): return t==n or fuzz.ratio(t,n)>85
        try:
            c_users=await self.mongo.db[self.collection_collection].find({}).to_list(None)
            s_users=await self.mongo.db[self.shiny_collection].find({}).to_list(None)
        except: return [],[]
        shiny_ping,collection_ping=[],[]
        for d in s_users:
            for p in d.get("pokemon",[]):
                if fuzzy_match(pokemon_name.lower(),p.lower()):
                    if guild.get_member(d['user_id']): shiny_ping.append(f"<@{d['user_id']}>")
                    break
        for d in c_users:
            for p in d.get("pokemon",[]):
                if fuzzy_match(pokemon_name.lower(),p.lower()):
                    if guild.get_member(d['user_id']): collection_ping.append(f"<@{d['user_id']}>")
                    break
        return shiny_ping,collection_ping

    @commands.Cog.listener()
    async def on_message(self,m):
        try:
            if m.author.id!=(self.bot.user.id if self.test_mode else self.target_id): return
            for e in m.embeds:
                if self.target_title in (e.title or "").lower() and e.image:
                    await self.output_prediction(m,e.image.url)
        except Exception as e: print(f"❌ Error in on_message: {type(e).__name__}: {e}")

    @commands.command(name="ps",hidden=True)
    async def predict_spawn(self,ctx,image_url=None):
        try:
            m=ctx.message
            if not image_url:
                ref=m.reference
                if ref: m=await ctx.channel.fetch_message(ref.message_id)
                if m.attachments: image_url=m.attachments[0].url
                elif m.embeds and m.embeds[0].image: image_url=m.embeds[0].image.url
            if not image_url: return await ctx.send("❌ No image URL found.")
            await self.output_prediction(m,image_url)
        except Exception as e:
            await ctx.send(f"❌ Prediction error: {type(e).__name__}: {e}")



def setup(bot): 
    bot.add_cog(PoketwoSpawnDetector(bot))
