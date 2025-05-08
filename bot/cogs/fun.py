"""                   commands                   """
# 8ball, bite, blush, builtdifferent, cry, cuddle, dance, gayrate, handhold, happy,
# hug, iq, kiss, lick, nervous, pat, pinch, poke, pp, simprate, slap,
# slowclap, smile, smug, slot, strength, waifurate, wave, wink

import types
from motor.motor_asyncio import AsyncIOMotorClient

from utils.cogs.fun import *
from imports.discord_imports import *
from data.commands.fun.emojis import *

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fun_cmd = Fun_Commands()
        self.create_action_commands()

    @commands.command(name='8ball')
    async def eight_ball(self, ctx, *, question):
        prediction = await self.fun_cmd.eight_ball()
        response_build = f'**:8ball: | {ctx.author.display_name} asked:** *"{question}"*\n{blank_emoji} | **Answer:** {prediction}'
        await ctx.reply(response_build, mention_author=False)

    def create_action_commands(self):
     actions = ['pat', 'cuddle', 'bite', 'kiss', 'lick', "hug", "cry", "kiss", "wave", "slowclap", "smug"]
     for action in actions:
        @commands.command(name=action)
        async def action_fn(ctx, user: Union[discord.Member, Literal["everyone"]] = None, *, additional_text: str = ""):
            if user is None: user = ctx.author
            embed = await  self.fun_cmd.action_command(ctx, user, additional_text)
            await ctx.send(embed=embed)
        action_fn.__name__ = action 
        self.bot.add_command(action_fn)


async def setup(bot):
    await bot.add_cog(Fun(bot))