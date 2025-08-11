from imports.discord_imports import *
from utils.subcogs.utils.reviews import *
from bson import ObjectId

class Reviews(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mongo = MongoManager()
        self.utils_review = ReviewUtils(self.mongo)

    @commands.command(name="reviews")
    async def reviews_command(self, ctx, action: Literal["view", "add", "edit", "remove"], member: Optional[discord.Member] = None):
        embed, view = await self.handle_action(ctx, action, member)
        if embed is None:
            return
        await ctx.send(embed=embed, view=view)

    async def handle_action(self, ctx, action, member):
        func_map = {
            "view": self.utils_review.get_overview,
            "add": self.utils_review.add_review,
            "edit": self.utils_review.edit_review,
            "remove": self.utils_review.remove_review
        }
        if action not in func_map:
            return None, None
        return await func_map[action](ctx, member)


async def setup(bot):
    await bot.add_cog(Reviews(bot))
