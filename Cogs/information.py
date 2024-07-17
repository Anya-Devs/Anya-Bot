from Data.const import Information_Embed
from Imports.discord_imports import *

class Information(commands.Cog):
    """
    A cog for displaying bot information.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def about(self, ctx, id: Union[discord.Member, int, str] = None):
        """
        Displays bot information.

        Parameters:
            `ctx (commands.Context)`: The context in which the command is being invoked.
            id `(Optional[Union[discord.Member, int, str]])`: The ID of the Discord member, server, or invite link.
                Default is None, indicating the bot itself.

        Returns:
            `None`
        """
        if id is None:
            id = ctx.bot.user


        embed = await Information_Embed.get_embed(id, self.bot)
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Information(bot))