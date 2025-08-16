from bson import ObjectId
from datetime import datetime
from typing import Union, Optional, Literal

from utils.cogs.information import *
from utils.subcogs.utils.reviews import *
from utils.cogs.information import Information_Commands, Information_Embed

from imports.discord_imports import * 
from data.local.const import primary_color


class Information(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.members_per_page = 25
        self.ic = Information_Commands()
        self.iv = Information_View()
        self.mongo = MongoManager()
        self.utils_review = ReviewUtils(self.mongo)

    
        
        
        
    @commands.command(name="reviews")
    async def reviews_command(
        self,
        ctx,
        member: Optional[discord.Member] = None,
        action: str = "view"
    ):
        if member is None:
            member = ctx.author

        action = action.lower()
        valid_actions = ["view", "add", "edit", "remove"]

        if action not in valid_actions:
            embed = discord.Embed(
                title="Invalid Action",
                description=(f"The action `{action}` is not valid.\n\n"
                             f"**Usage:** `{ctx.prefix}reviews <member> <action>`\n"
                             f"**Actions:** view | add | edit | remove\n"
                             f"Example: `{ctx.prefix}reviews @User add`"),
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        try:
            result = await self.handle_action(ctx, action, member)
            embed, view = result if isinstance(result, tuple) else (None, None)
            if embed:
                await ctx.reply(**{k: v for k, v in {"embed": embed, "view": view}.items() if v}, mention_author=False)
        except Exception as e:
            embed = discord.Embed(
                title="Error",
                description=f"An unexpected error occurred while processing your request.\n\n`{e}`",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed, mention_author=False)

    async def handle_action(self, ctx, action, member):
        func_map = {
            "view": self.utils_review.get_overview,
            "add": self.utils_review.add_review,
            "edit": self.utils_review.edit_review,
            "remove": self.utils_review.remove_review
        }
        func = func_map.get(action)
        if func is None:
            return None, None

        # Prevent editing/removing non-existent reviews
        if action in ("edit", "remove"):
            existing_review = await self.mongo.collection.find_one({
                "reviewer_id": str(ctx.author.id),
                "target_id": str(member.id)
            })
            if not existing_review:
                embed = discord.Embed(
                    title="No Review Found",
                    description=(f"You don't have a review for {member.mention} yet.\n"
                                 f"Use `{ctx.prefix}reviews {member.display_name} add` to create one first."),
                    color=discord.Color.orange()
                )
                await ctx.reply(embed=embed, mention_author=False)
                return None, None

        result = await func(ctx, member)
        return result if isinstance(result, tuple) else (result, None)





    @commands.command(name="about", aliases=["info", "details"])
    async def about(self, ctx, args: Union[discord.Member, int, str] = None):
     args = args or ctx.bot.user

     result = await Information_Commands.get_information_embed(args, self.bot)
     if isinstance(result, tuple) and len(result) == 2:
        embed, view = result
        await ctx.reply(embed=embed, view=view, mention_author=False)
     else:
        embed = result
        await ctx.reply(embed=embed, mention_author=False) 
        
    @commands.command(name="server")
    async def server_info(self, ctx, mode: Optional[Literal["roles", "emojis"]] = None):
        try:
            embed_or_view = await self.ic.server(
                ctx=ctx,
                mode=mode,
                cog=Information(self.bot),
                members_per_page=self.members_per_page,
            )
            if isinstance(embed_or_view, tuple):
                embed, view = embed_or_view
                await ctx.reply(embed=embed, view=view, mention_author=False)
            else:
                await ctx.reply(embed=embed_or_view, mention_author=False)
        except Exception as e:
            await error_custom_embed(self.bot, ctx, e)

    @commands.command(name="pfp")
    async def pfp(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        avatar_url = user.avatar.url  
        embed = discord.Embed(
            title=user.display_name,
            color=primary_color(),
            timestamp=datetime.now(),
            url=avatar_url,
        ).set_image(url=avatar_url)
        
        button = discord.ui.Button(label="Download", style=discord.ButtonStyle.link, url=avatar_url)
        await ctx.reply(embed=embed, mention_author=False, view=discord.ui.View().add_item(button))

    @commands.command(name="banner")
    async def banner(self, ctx, user: discord.Member = None):
     user = user or ctx.author
     banner_url = await get_user_banner_url(self.bot, user)
     embed = discord.Embed(title=f"{user.display_name}'s banner" if banner_url else user.display_name, description=None if banner_url else "No banner set", color=primary_color(), timestamp=datetime.now(), url=banner_url)
     if banner_url:
        dl_url = f"{banner_url.split('?')[0]}?format=png&size=4096"
        embed.set_image(url=dl_url)
        button = discord.ui.Button(label="Download Banner", style=discord.ButtonStyle.link, url=dl_url)
        await ctx.reply(embed=embed, mention_author=False, view=discord.ui.View().add_item(button))
     else:
        await ctx.reply(embed=embed, mention_author=False)
        
    @commands.command(name="invite")
    async def invite(self, ctx, link: str = None):
        if link:
            try:
                invite = await self.bot.fetch_invite(link)
                embed = await Information_Embed.get_invite_embed(invite)
                await ctx.reply(embed=embed, mention_author=False)
            except discord.NotFound:
                await ctx.reply("The provided invite link is invalid or expired. Generating a new invite...", mention_author=False)
                await self.create_and_send_invite(ctx)
        else:
            await self.create_and_send_invite(ctx)

    async def create_and_send_invite(self, ctx):        
        if ctx.channel.permissions_for(ctx.guild.me).create_instant_invite:
            invite = await ctx.channel.create_invite(max_uses=0, temporary=False, unique=True)
            await ctx.reply(f"Here is your permanent invite link: {invite.url}", mention_author=False)
        else:
            await ctx.reply("I do not have permission to create invites in this channel.", mention_author=False)

    @commands.command(name="perms")
    async def perms(self, ctx, target: Union[discord.Member, discord.Role] = None):
        target = target or ctx.author  
        permissions = target.guild_permissions if isinstance(target, discord.Member) else target.permissions
        if permissions:
            view = self.iv.PermissionsView(self, ctx, permissions, target)
            embed = view.build_perms_embed()
            await ctx.reply(embed=embed, view=view, mention_author=False)
        else:
            await ctx.reply("Please provide a valid user or role.", mention_author=False)

    @commands.command(name="roles")
    async def roles(self, ctx, mode: Optional[Literal["lookup", "members"]] = None, *, value: Optional[Union[discord.Member, str]] = None):
     if mode == "lookup" and isinstance(value, str):
        mf = 10
        parts = value.rsplit(" ", 1)
        rn = parts[0] if len(parts) == 2 and parts[1].isdigit() else value
        mf = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 10
        role = discord.utils.find(lambda r: r.name.lower() == rn.lower(), ctx.guild.roles)
        if not role:
            return await ctx.reply(f"❌ Role '{rn}' not found.", mention_author=False)
        roles = sorted((r for r in ctx.guild.roles if r.position < role.position), key=lambda r: r.position, reverse=True)[:mf]
        if not roles:
            return await ctx.reply(f"⚠️ No roles under `{role.name}`.", mention_author=False)
        return await ctx.reply(
            embed=discord.Embed(
                title=f"Roles under: `{role.name}`",
                description="\n".join(f"`<@&{r.id}>` — `{r.name}`" for r in roles),
                color=primary_color(),
                timestamp=datetime.now()
            ),
            mention_author=False
        )

     if mode == "members":
        embed = discord.Embed(
            title=" ",
            description=(
                "**What this does:**\n"
                "Displays a breakdown of a member's roles by permission type, channel access, and more.\n\n"
                "**How to use:**\n"
                "• Select one or more users from the menu.\n"
                "• Click the green ✅ Validate button to view their role breakdown.\n"
                "• Use the dropdown in the next message to explore each section."
            ),
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="Only roles the bot can see are shown.")
        embed.set_thumbnail(url=ctx.bot.user.display_avatar.url)
        return await ctx.reply(embed=embed, view=RoleLookupView(ctx.bot), mention_author=False)

     m = value if isinstance(value, discord.Member) else ctx.author
     await ctx.reply(
        embed=discord.Embed(
            title=f"Roles for {m.display_name}",
            description=", ".join(f"<@&{r.id}>" for r in m.roles[1:]) or "None",
            color=primary_color(),
            timestamp=datetime.now()
        ).set_footer(text=f"Found {len(m.roles)-1} roles"),
        mention_author=False
     )


    @roles.error
    async def roles_error(self, ctx, error):
      p = ctx.prefix
      embed = discord.Embed(
        title="❌ Command Error",
        description=(
            f"Usage:\n"
            f"`{p}roles` - shows your roles\n"
            f"`{p}roles <@member>` - shows roles for member\n"
            f"`{p}roles lookup <role> [max]` - shows roles below specified role\n"
            f"`{p}roles members` - enter usernames with button\n\n"
            f"Error: {error}"
        ),
        color=0xFF0000,
        timestamp=datetime.now()
      )
      await ctx.reply(embed=embed, mention_author=False)
 
def setup(bot):
    bot.add_cog(Information(bot))

