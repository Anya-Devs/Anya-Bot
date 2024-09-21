import aiohttp
from Data.const import Information_Embed
from Imports.discord_imports import *

class Information(commands.Cog):
    """
    A cog for displaying bot information.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='about', aliases=['info', 'details'])
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

        embed = await self.get_information_embed(id, self.bot)
        await ctx.reply(embed=embed)

    async def get_information_embed(self, id, bot):
        if isinstance(id, discord.Member):
            return await Information_Embed.get_member_embed(bot, id)
        elif isinstance(id, int):
            guild = bot.get_guild(id)
            if guild:
                return await Information_Embed.get_guild_embed(guild)
            else:
                raise ValueError("Invalid server ID provided.")
        elif isinstance(id, str):
            async with aiohttp.ClientSession() as session:
                invite = await bot.fetch_invite(id)
                return await Information_Embed.get_invite_embed(invite)
        else:
            return await Information_Embed.get_bot_embed(bot.user, bot)

def setup(bot):
    bot.add_cog(Information(bot))