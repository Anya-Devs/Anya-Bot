from bson import ObjectId
from itertools import islice
from datetime import datetime
from typing import Union, Optional, Literal

from utils.cogs.information import *
from utils.subcogs.utils.reviews import *
from utils.cogs.information import (
    Information_Commands, Information_Embed, Information_View,
    ActivityUtils, ActivityDiscoveryView, format_number
)

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

    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx):
     try:
        mongo = MongoManager()
        data = await mongo.get_leaderboard_data(str(ctx.guild.id), min_reviews=1, limit=200)
        if not data:
            return await ctx.reply(embed=discord.Embed(
                title="Review Leaderboard",
                description="No reviews found for this server.",
                color=primary_color()
            ), mention_author=False)

        members = {str(m.id): m for m in ctx.guild.members}
        per_page = 25
        pages = [data[i:i + per_page] for i in range(0, len(data), per_page)]
        view = LeaderboardView(self, pages, members, ctx, per_page)
        await ctx.reply(embed=view.build_embed(), view=view, mention_author=False)
     except Exception as e:
        await ctx.reply(f"Error loading leaderboard: `{e}`", mention_author=False)

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
        
    @commands.group(name="server", invoke_without_command=True)
    async def server_group(self, ctx, mode: Optional[Literal["roles", "emojis"]] = None):
        """Server information commands."""
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
    
    @server_group.command(name="icon")
    async def server_icon(self, ctx):
        """Get the server's icon in full resolution."""
        if not ctx.guild.icon:
            return await ctx.reply("This server doesn't have an icon.", mention_author=False)
        
        embed = discord.Embed(
            title=f"{ctx.guild.name}'s Icon",
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_image(url=ctx.guild.icon.url)
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.link, url=ctx.guild.icon.url))
        
        await ctx.reply(embed=embed, view=view, mention_author=False)
    
    @server_group.command(name="banner")
    async def server_banner(self, ctx):
        """Get the server's banner in full resolution."""
        if not ctx.guild.banner:
            return await ctx.reply("This server doesn't have a banner.", mention_author=False)
        
        embed = discord.Embed(
            title=f"{ctx.guild.name}'s Banner",
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_image(url=ctx.guild.banner.url)
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Download", style=discord.ButtonStyle.link, url=ctx.guild.banner.url))
        
        await ctx.reply(embed=embed, view=view, mention_author=False)

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

    @commands.command(name="permissions", aliases=["perms"])
    async def permissions(self, ctx, target: Union[discord.Member, discord.Role] = None):
        """View permissions for a user or role."""
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
     try:
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
            embed = discord.Embed(
                title=f"Roles under: `{role.name}`",
                description="\n".join(f"`<@&{r.id}>` — `{r.name}`" for r in roles),
                color=primary_color(),
                timestamp=datetime.now()
            )
            return await ctx.reply(embed=embed, mention_author=False)

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
        roles = m.roles[1:]
        if not roles:
            embed = discord.Embed(
                title=f"Roles for {m.display_name}",
                description="⚠️ This user has no roles.",
                color=primary_color(),
                timestamp=datetime.now()
            )
            embed.set_footer(text="Found 0 roles")
            return await ctx.reply(embed=embed, mention_author=False)

        highest = roles[0]
        managed = [r for r in roles if r.managed]
        normal = [r for r in roles if not r.managed and r != highest]

        embed = discord.Embed(
            title=f"Roles for {m.display_name}",
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.add_field(name="```    Highest Role    ```", value=f"<@&{highest.id}>", inline=False)
        if managed:
            embed.add_field(name="```    Managed Roles    ```", value=", ".join(f"<@&{r.id}>" for r in managed), inline=False)
        if normal:
            embed.add_field(name="```    Other Roles    ```", value=", ".join(f"<@&{r.id}>" for r in normal), inline=False)
        embed.set_footer(text=f"Found {len(roles)} roles")
        return await ctx.reply(embed=embed, mention_author=False)

     except Exception as e:
        await ctx.reply(f"⚠️ An error occurred: `{e}`", mention_author=False)


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

    @commands.command(name="activity", aliases=["playing", "activities"])
    @commands.guild_only()
    async def activity_discovery(self, ctx, *, game_name: str = None):
        """
        Discover what members are playing and find others with shared interests.
        Requires Guild Presences Intent for real-time activity tracking.
        """
        data = ActivityUtils.collect_activities(ctx.guild)
        activities_map = data["games"]
        streamers = data["streamers"]
        listening = data["listening"]
        watching = data["watching"]
        
        if game_name:
            matching = [
                (name, members) for name, members in activities_map.items()
                if game_name.lower() in name.lower()
            ]
            
            if not matching:
                embed = discord.Embed(
                    title="No Players Found",
                    description=f"No one is currently playing anything matching **{game_name}**.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Use {ctx.prefix}activity to see all current activities")
                return await ctx.reply(embed=embed, mention_author=False)
            
            embed = discord.Embed(
                title=f"{ctx.guild.name} — Players: {game_name}",
                color=primary_color(),
                timestamp=datetime.now()
            )
            
            for game, members in sorted(matching, key=lambda x: len(x[1]), reverse=True)[:10]:
                member_mentions = ", ".join(m.mention for m in members[:8])
                if len(members) > 8:
                    member_mentions += f" +{format_number(len(members) - 8)} more"
                embed.add_field(
                    name=f"{game[:40]} ({format_number(len(members))})",
                    value=member_mentions,
                    inline=False
                )
            
            total = sum(len(m) for _, m in matching)
            embed.set_footer(text=f"Found {format_number(total)} player(s) across {format_number(len(matching))} game(s)")
            return await ctx.reply(embed=embed, mention_author=False)
        
        view = ActivityDiscoveryView(ctx, activities_map, streamers, listening, watching)
        embed = view.build_overview_embed()
        await ctx.reply(embed=embed, view=view, mention_author=False)


def setup(bot):
    bot.add_cog(Information(bot))