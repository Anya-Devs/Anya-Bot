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
        emotes = {"<3": ["pat", "cuddle", "kiss", "hug"], ">:0": ["bite", "lick"]}
        emote = next((e for e, acts in emotes.items() if action in acts), "")
        everyone = isinstance(user, str) and user.lower() == "everyone"
        msg = f"{ctx.author.display_name} {action}s the whole server {emote} {additional_text}" if everyone else f"{ctx.author.display_name} {action}s {user.display_name} {emote} {additional_text}"
        embed = discord.Embed(title=msg.strip(), color=primary_color()).set_image(url=gif)

        sid, aid = str(ctx.guild.id), str(ctx.author.id)
        if not everyone:
            if user != ctx.author:
                uid = str(user.id)
                await self.mongo.update_one({"server_id": sid}, {"$inc": {f"members.intake.{uid}": 1}}, upsert=True)
            await self.mongo.update_one({"server_id": sid}, {"$inc": {f"members.outake.{aid}": 1}}, upsert=True)

        doc = await self.mongo.find_one({"server_id": sid})
        sent = doc.get("members", {}).get("outake", {}).get(aid, 0)
        received = doc.get("members", {}).get("intake", {}).get(aid, 0)
        embed.set_footer(text=f"Sent: {sent} | Received: {received}")
        return embed