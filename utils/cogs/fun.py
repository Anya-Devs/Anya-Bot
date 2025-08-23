"""                   commands                   """


import os, random, asyncio, logging, aiohttp, aiofiles
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from imports.discord_imports import *
from imports.log_imports import *
from data.local.const import *
from utils.cogs.quest import *






class Fun_Commands:
    def __init__(self):
        self._8ball_file = "data/commands/fun/8ball-responses.txt"
        action_file = "data/commands/fun/action-response.json"
        self.action_api = "https://api.otakugifs.xyz/gif?reaction={}"
        self.mongo = AsyncIOMotorClient(os.getenv("MONGO_URI")).Commands.fun
        with open(action_file) as f: data = json.load(f); self.emotes = data["emotes"]; self.phrases = data["phrases"]

    async def eight_ball(self):
        async with aiofiles.open(self._8ball_file, "r") as f: responses = await f.readlines()
        return random.choice([r.strip() for r in responses if r.strip()])

    async def action_command(self, ctx, user: Union[discord.Member, Literal["everyone"], None]=None, extra=""):
        if user is None: user = ctx.author
        action = ctx.command.name
        async with aiohttp.ClientSession() as s: gif = (await (await s.get(self.action_api.format(action))).json())["url"]
        emote = next((e for e, acts in self.emotes.items() if action in acts), "")
        if isinstance(user, str) and user.lower() == "everyone": target, phrase = "the whole server", self.phrases["everyone"].get(action, f"{action}s")
        elif isinstance(user, discord.Member) and user == ctx.author: target, phrase = "themselves", self.phrases["self"].get(action, f"{action}s")
        else: target, phrase = user.display_name, self.phrases["other"].get(action, f"{action}s")
        plain = "[no_embed]" in phrase; phrase = phrase.replace("[no_embed]", "").strip()
        msg = f"{phrase.format(user=ctx.author.display_name,target=target)} {emote} {extra}".strip()
        sid, aid = str(ctx.guild.id), str(ctx.author.id)
        if isinstance(user, discord.Member) and not user.bot and user != ctx.author:
            await self.mongo.update_one({"server_id": sid}, {"$inc": {f"members.{action}.intake.{user.id}": 1}}, upsert=True)
        if (isinstance(user, discord.Member) and not user.bot and user != ctx.author) or (isinstance(user, str) and user.lower()=="everyone"):
            await self.mongo.update_one({"server_id": sid}, {"$inc": {f"members.{action}.outake.{aid}": 1}}, upsert=True)
        doc = await self.mongo.find_one({"server_id": sid})
        sent = doc.get("members", {}).get(action, {}).get("outake", {}).get(aid, 0)
        received = doc.get("members", {}).get(action, {}).get("intake", {}).get(aid, 0)
        embed = None if plain else discord.Embed(title=msg,color=primary_color()).set_image(url=gif).set_footer(text=f"Sent: {sent} | Received: {received}")
        return embed, msg
  
  
  
  
  
  
  
  



# ---------------- Mini Games ---------------- #
class Mini_Games:
    def __init__(self): self.correct_emojis = {}

    @staticmethod
    def timeout_embed():
        return discord.Embed(
            title="⏰ Time's Up...",
            description="||```You didn't click the emoji in time.```||",
            color=discord.Color.red()
        )

    @staticmethod
    def timestamp_gen(ts: int) -> str:
        return f"<t:{int(datetime.utcfromtimestamp(ts).replace(tzinfo=timezone.utc).timestamp())}:R>"


# ---------------- Memo Game ---------------- #
class Memo(discord.ui.View):
    def __init__(self, ctx, emojis, chosen_emoji, message):
        super().__init__(timeout=10)
        self.ctx, self.emojis, self.chosen_emoji, self.message = ctx, list(emojis), chosen_emoji, message
        self.quest_data, self.memo_data = Quest_Data(), Memo_Data()
        self.user_points, self.streak_increment, self.base_points, self.points_multiplier = {}, 1, 5, 2

        # Buttons
        options = random.sample(set(self.emojis) - {chosen_emoji}, min(4, len(self.emojis)-1))
        for idx, emoji in enumerate(options+[chosen_emoji]):
            btn = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                custom_id="correct_emoji" if emoji == chosen_emoji else f"emoji_{idx}",
                emoji=emoji
            )
            btn.callback = self.on_button_click; self.add_item(btn)
        for b in [("Stop", discord.ButtonStyle.red, self.on_stop_click),
                  ("Continue", discord.ButtonStyle.green, self.on_continue_click)]:
            btn = discord.ui.Button(label=b[0], style=b[1]); btn.callback = b[2]; setattr(self, f"{b[0].lower()}_button", btn)

    # ---------- Game Logic ---------- #
    async def on_button_click(self, inter: discord.Interaction):
        u, cid = inter.user, inter.data["custom_id"]
        if cid == "correct_emoji":
            streak = await self.memo_data.get_streak(u.guild.id,u.id)+self.streak_increment
            await self.memo_data.set_streak(u.guild.id,u.id,streak)
            pts = self.base_points if streak<=1 else int(streak*self.points_multiplier)
            self.user_points[u.id]=self.user_points.get(u.id,0)+pts
            await self.quest_data.add_balance(str(u.id),str(inter.guild.id),pts)
            bal = await self.quest_data.get_balance(str(u.id),str(inter.guild.id))
            emb = await MemoEmbeds.continue_game_embed(pts,streak,bal,u)
            self.clear_items(); [self.add_item(x) for x in (self.stop_button,self.continue_button)]
            await inter.response.edit_message(embed=emb, view=self)
        else:
            streak=await self.memo_data.get_streak(u.guild.id,u.id)
            await self.memo_data.set_streak(u.guild.id,u.id,0)
            await inter.response.edit_message(embed=MemoEmbeds.incorrect_embed(streak), view=None)

    async def on_stop_click(self, inter: discord.Interaction):
        if inter.user!=self.ctx.author: return await inter.response.send_message("Only author can stop!",ephemeral=True)
        streak=await self.memo_data.get_streak(inter.guild.id,inter.user.id)
        high=await self.memo_data.get_user_highscore(inter.guild.id,inter.user.id)
        emb=await MemoEmbeds.stop_game_embed(streak,high,str(inter.user.avatar))
        await inter.response.edit_message(embed=emb,view=None)

    async def on_continue_click(self, inter: discord.Interaction):
        if inter.user!=self.ctx.author: return await inter.response.send_message("Only author can continue!",ephemeral=True)
        await inter.response.defer()
        streak=await self.memo_data.get_streak(inter.guild.id,inter.user.id)
        pts=self.base_points if streak<=0 else int(streak*self.points_multiplier)
        self.user_points[inter.user.id]=self.user_points.get(inter.user.id,0)+pts
        new=random.choice(self.emojis)
        ts=self.ctx.cog.timestamp_gen(int((datetime.utcnow()+timedelta(seconds=self.timeout)).timestamp()))
        emb=await MemoEmbeds.blank_embed(); emb.description=f"Remember this emoji: {new}"
        emb.add_field(name="",value=f"React with the emoji you remembered {ts}",inline=False)
        newv=Memo(self.ctx,self.emojis,new,self.message)
        await self.message.edit(embed=emb,view=newv); await asyncio.sleep(1)
        emb.description=" "; await self.message.edit(embed=emb,view=newv)

    async def on_timeout(self):
        await self.memo_data.set_streak(self.ctx.guild.id,self.ctx.author.id,0)
        self.user_points[self.ctx.author.id]=0
        await self.message.edit(embed=await MemoEmbeds.timeout_embed(),view=None)


# ---------------- Database Layer ---------------- #
class Memo_Data:
    def __init__(self):
        uri=os.getenv("MONGO_URI"); 
        if not uri: raise ValueError("Missing MONGO_URI env var")
        self.mongo=motor.motor_asyncio.AsyncIOMotorClient(uri); self.DB_NAME="Memo"

    async def _fetch(self,c,q,f): 
        try: d=await self.mongo[self.DB_NAME][c].find_one(q); return d[f] if d else 0
        except PyMongoError: return 0
    async def _update(self,c,q,d): 
        try: await self.mongo[self.DB_NAME][c].update_one(q,{"$set":d},upsert=True)
        except PyMongoError: pass

    async def get_user_highscore(self,g,u): return await self._fetch("highscores",{"guild_id":g,"user_id":u},"highscore")
    async def get_streak(self,g,u): return await self._fetch("streaks",{"guild_id":g,"user_id":u},"streak")
    async def set_user_highscore(self,g,u,s): await self._update("highscores",{"guild_id":g,"user_id":u},{"highscore":s})
    async def set_streak(self,g,u,s): await self._update("streaks",{"guild_id":g,"user_id":u},{"streak":s})


# ---------------- Embeds ---------------- #
class MemoEmbeds:
    @staticmethod
    def incorrect_embed(streak): return discord.Embed(
        title="❌ Incorrect",description=f"Your streak ended.\n```End Streak: {streak}```",color=discord.Color.red()
    )
    @staticmethod
    async def stop_game_embed(streak,high,av): 
        desc=f"```New Highscore: {streak}```" if streak>high else f"```Current Highscore: {streak}```"
        return discord.Embed(title="🛑 Game Stopped",description=desc,color=primary_color()).set_thumbnail(url=av)
    @staticmethod
    async def blank_embed(): return discord.Embed(color=primary_color())
    @staticmethod
    async def continue_game_embed(pts,streak,bal,u):
        emb=discord.Embed(color=primary_color())
        emb.add_field(name="Reward",value=f"⭐ `{pts} stp`",inline=True)
        emb.add_field(name="Stella Points",value=f"{bal:,}",inline=True)
        emb.set_footer(text=f"Current Streak: {streak}")
        emb.set_author(icon_url=u.avatar,name=f"{u.name}'s Progress"); return emb
    @staticmethod
    async def timeout_embed(): return discord.Embed(
        title="⏳ Time's Up!",description="You took too long. Streak reset to `0`.",color=discord.Color.red()
    ).set_footer(text="Try again next round!")
