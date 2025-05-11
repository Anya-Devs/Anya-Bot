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
        action_command_file = "data/commands/fun/action-response.json"
        self.action_command_api = "https://api.otakugifs.xyz/gif?reaction={}"
        self.mongo = AsyncIOMotorClient(os.getenv("MONGO_URI")).Commands.fun

        with open(action_command_file) as f: self.action_data = json.load(f)
        self.emotes = self.action_data["emotes"]
        self.phrases = self.action_data["phrases"]

    async def eight_ball(self):
        async with aiofiles.open(self._8ball_file, mode="r") as file:
            responses = await file.readlines()
        return random.choice([r.strip() for r in responses if r.strip()])

    async def action_command(self, ctx, user: Union[discord.Member, Literal["everyone"]], additional_text=""):
     action = ctx.command.name
     async with aiohttp.ClientSession() as s:
        gif = (await (await s.get(self.action_command_api.format(action))).json())["url"]
     emote = next((e for e, acts in self.emotes.items() if action in acts), "")
     if isinstance(user, str) and user.lower() == "everyone":
        action_target, action_phrase = "the whole server", self.phrases["everyone"].get(action, f"{action}s")
     elif isinstance(user, discord.Member) and user == ctx.author:
        action_target, action_phrase = "themselves", self.phrases["self"].get(action, f"{action}s")
     else:
        action_target, action_phrase = user.display_name, self.phrases["other"].get(action, f"{action}s")
     is_plain = "[no_embed]" in action_phrase
     action_phrase = action_phrase.replace("[no_embed]", "").strip()
     msg = f"{action_phrase.format(user=ctx.author.display_name, target=action_target)} {emote} {additional_text}".strip()
     sid, aid = str(ctx.guild.id), str(ctx.author.id)
     if isinstance(user, discord.Member) and not user.bot and user != ctx.author:
        await self.mongo.update_one({"server_id": sid}, {"$inc": {f"members.{action}.intake.{str(user.id)}": 1}}, upsert=True)
     if (isinstance(user, discord.Member) and not user.bot and user != ctx.author) or (isinstance(user, str) and user.lower() == "everyone"):
        await self.mongo.update_one({"server_id": sid}, {"$inc": {f"members.{action}.outake.{aid}": 1}}, upsert=True)
     doc = await self.mongo.find_one({"server_id": sid})
     sent = doc.get("members", {}).get(action, {}).get("outake", {}).get(aid, 0)
     received = doc.get("members", {}).get(action, {}).get("intake", {}).get(aid, 0)
     embed = None if is_plain else discord.Embed(title=msg, color=primary_color()).set_image(url=gif).set_footer(text=f"Sent: {sent} | Received: {received}")
     return embed, msg