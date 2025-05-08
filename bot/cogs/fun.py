"""                   commands                   """
# 8ball, bite, blush, builtdifferent, cry, cuddle, dance, gayrate, handhold, happy,
# hug, iq, kiss, lick, nervous, pat, pinch, poke, pp, simprate, slap,
# slowclap, smile, smug, slot, strength, waifurate, wave, wink

from utils.cogs.fun import *
from imports.discord_imports import *
from data.commands.fun.emojis import *



class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fun_cmd = Fun_Commands()

    @commands.command(name='8ball')
    async def eight_ball(self, ctx, *, question):
        prediction = await self.fun_cmd.eight_ball()
        response_build = f'**:8ball: | {ctx.author.display_name} asked:** *"{question}"*\n{blank_emoji} | **Answer:** {prediction}'
        await ctx.reply(response_build, mention_author=False)

    @commands.command(name='pat')
    async def pat(self, ctx, user: Union[discord.Member, Literal["everyone"]]):
        pass



 

   

def setup(bot):
    bot.add_cog(Fun)