import discord
from discord.ext import commands

class FirstMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='firstmessage')
    async def firstmessage(self, ctx):
        channel = ctx.channel
        # Fetch the first message in the channel
        first_message = None
        async for message in channel.history(limit=1, oldest_first=True):
            first_message = message
            break
        
        if not first_message:
            await ctx.send("No messages found in this channel.")
            return

        embed = discord.Embed(
            description=f'<:IconG_Message:1240919050578825236> {ctx.author.mention}: click the button below to take you to the first message on Emoji server',
            color=0xfefefe
        )
        
        view = discord.ui.View()
        button = discord.ui.Button(
            label="jump to message",
            url=first_message.jump_url,
            style=discord.ButtonStyle.link
        )
        view.add_item(button)
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(FirstMessage(bot))
    
