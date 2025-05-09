"""                   commands                   """
# 8ball, bite, blush, builtdifferent, cry, cuddle, dance, gayrate, handhold, happy,
# hug, iq, kiss, lick, nervous, pat, pinch, poke, pp, simprate, slap,
# slowclap, smile, smug, slot, strength, waifurate, wave, wink

from data.const import *
import aiofiles, random, aiohttp
from imports.discord_imports import *
from motor.motor_asyncio import AsyncIOMotorClient




class Fun_Commands:
    def __init__(self):
        self._8ball_file = "data/commands/fun/8ball-responses.txt"
        self.action_command_api = "https://api.otakugifs.xyz/gif?reaction={}"
        self.mongo = AsyncIOMotorClient(os.getenv("MONGO_URI")).Commands.fun

    async def eight_ball(self):
        async with aiofiles.open(self._8ball_file, mode="r") as file:
            responses = await file.readlines()
        return random.choice([r.strip() for r in responses if r.strip()])

    async def action_command(self, ctx, user: Union[discord.Member, Literal["everyone"]], additional_text=""):
     action = ctx.command.name
     async with aiohttp.ClientSession() as s: 
      gif = (await (await s.get(self.action_command_api.format(action))).json())["url"]
      emotes = {"<3": ["pat", "cuddle", "kiss", "hug"], ">:0": ["bite", "lick", "slap"], ":(": ["cry"], "= w =": ["slowclap", "wave", "smug"]}
      emote = next((e for e, acts in emotes.items() if action in acts), "")
      action_phrases = {"pat": "gives a gentle pat to", "cuddle": "cuddles", "kiss": "gives a kiss to", "hug": "hugs", "bite": "bites", "lick": "licks", "slap": "slaps", "cry": "is crying", "slowclap": "gives a slow clap", "wave": "waves at", "smug": "gives a smug look to"}
      msg = f"{ctx.author.display_name} {action_phrases.get(action, f'{action}s')} {('the whole server' if isinstance(user, str) and user.lower() == 'everyone' else user.display_name)} {emote} {additional_text}"
      embed = discord.Embed(title=msg.strip(), color=primary_color()).set_image(url=gif)
      sid, aid = str(ctx.guild.id), str(ctx.author.id)
      if isinstance(user, discord.Member) and not user.bot and user != ctx.author: await self.mongo.update_one({"server_id": sid}, {"$inc": {f"members.{action}.intake.{str(user.id)}": 1}}, upsert=True)
      if not ctx.author.bot and not isinstance(user, str) and user != "everyone" and not user.bot: await self.mongo.update_one({"server_id": sid}, {"$inc": {f"members.{action}.outake.{aid}": 1}}, upsert=True)
      doc = await self.mongo.find_one({"server_id": sid})
      sent, received = doc.get("members", {}).get(action, {}).get("outake", {}).get(aid, 0), doc.get("members", {}).get(action, {}).get("intake", {}).get(aid, 0)
      embed.set_footer(text=f"Sent: {sent} | Received: {received}")
      return embed