import json
import aiohttp
from datetime import datetime

from data.const import *
from utils.cogs.information import *

from discord.ui import *
from data.const import primary_color, Information_Embed
from Imports.discord_imports import *



class Information(commands.Cog):
    
    def __init__(self, bot):
        self.bot = bot
        self.members_per_page = 25


    @commands.command(name="about", aliases=["info", "details"])
    async def about(self, ctx, args: Union[discord.Member, int, str] = None):
        if args is None:
            args = ctx.bot.user
        embed = await Helper.get_information_embed(args, self.bot)
        await ctx.reply(embed=embed, mention_author=False)
        


    
    @commands.command(name="server")
    async def server_info(self, ctx):
     guild = ctx.guild
     owner = guild.owner
     boosts = guild.premium_subscription_count
     boost_tier = f"Tier {guild.premium_tier}" if boosts > 0 else "Not boosted"

     
     bots = len([member for member in guild.members if member.bot])
     users = len([member for member in guild.members if not member.bot])
     total_members = guild.member_count

     overview = (
        f"Owner: {owner.mention}\n"
        f"Boosts: {boosts}/14\n"
        f"Boost Tier: {boost_tier}"
     )

     other_info = (
        f"Roles: {len(guild.roles)}\n"
        f"Channels: {len(guild.channels)} - Text: {len([c for c in guild.channels if isinstance(c, discord.TextChannel)])} - Voice: {len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])}\n"
        f"Members: {total_members} (Users: {users}, Bots: {bots})"
     )

     embed = discord.Embed(color=primary_color(), timestamp=datetime.now())
 
     embed.add_field(name="Overview", value=overview, inline=True)
     embed.add_field(name="Other", value=other_info, inline=True)

     embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
     embed.set_footer(text=f"ID: {guild.id}")

     embed.set_author(name=f"{guild.name}", icon_url=owner.avatar.url)

     await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="pfp")
    async def pfp(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        avatar_url = user.avatar.url  

        
        embed = discord.Embed(
            title=user.display_name,
            color=primary_color(),
            timestamp=datetime.now(),
            url=avatar_url,  
        )
        embed.set_image(url=avatar_url)

        
        button = discord.ui.Button(
            label="Download", style=discord.ButtonStyle.link, url=avatar_url
        )
        view = discord.ui.View()
        view.add_item(button)

        
        await ctx.reply(embed=embed, mention_author=False, view=view)

    
    @commands.command(name="banner")
    async def banner(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        banner_url = await get_user_banner_url(self.bot, user)

        if banner_url:
            
            embed = discord.Embed(
                title=f"{user.display_name}'s banner",
                color=primary_color(),
                timestamp=datetime.now(),
                url=banner_url,  
            )
            embed.set_image(url=banner_url)

            
            button = discord.ui.Button(
                label="Download Banner", style=discord.ButtonStyle.link, url=banner_url
            )
            view = discord.ui.View()
            view.add_item(button)
        else:
            
            embed = discord.Embed(
                title=user.display_name,
                description="No banner set",
                color=primary_color(),
                timestamp=datetime.now(),
            )
            view = None  

        
        await ctx.reply(embed=embed, mention_author=False, view=view)


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

        if isinstance(target, discord.Member):
            permissions = target.guild_permissions
        elif isinstance(target, discord.Role):
            permissions = target.permissions
        else:
            await ctx.reply(
                "Please provide a valid user or role.", mention_author=False
            )
            return

        view = PermissionsView(self, ctx, permissions, target)
        embed = view.build_perms_embed()
        await ctx.reply(embed=embed, view=view, mention_author=False)


    @commands.command(name="server_emojis")
    async def server_emojis(self, ctx):
        emojis = ctx.guild.emojis
        if not emojis:
            await ctx.reply("This server has no custom emojis!", mention_author=False)
            return

        emojis_per_page = 10
        pages = [
            emojis[i: i + emojis_per_page]
            for i in range(0, len(emojis), emojis_per_page)
        ]

        view = Helper.PaginationView(pages)
        embed = view.create_embed(ctx, 0, pages)
        await ctx.reply(embed=embed, view=view, mention_author=False)


        
    @commands.command(name="server_roles")
    async def role_select(self, ctx):
        guild = ctx.guild
        roles = sorted(
            guild.roles,
            key=lambda role: (len(role.members), role.color.value),
            reverse=True,
        )
        most_common_roles = [
            role for role in roles if len(role.members) >= 5 and role.name
        ]
        select_roles = most_common_roles[:25]  

        if not select_roles:
            await ctx.send("No roles available for selection.")
            return
        
        select_view = Select_Role(roles=select_roles, cog=self, members_per_page=self.members_per_page)
        embed = self.create_role_embed(select_roles[0], 0)
        await ctx.send(embed=embed, view=select_view)

    def create_role_embed(self, role, current_page):
        """Create an embed displaying members of the selected role."""
        
        members = [member for member in role.members if not member.bot]
        total_members = len(members)

        
        total_pages = (total_members // self.members_per_page) + (1 if total_members % self.members_per_page != 0 else 0)

        
        start_index = current_page * self.members_per_page
        end_index = start_index + self.members_per_page
        members_for_page = members[start_index:end_index]
        member_mentions = ",".join([member.mention for member in members_for_page]) or "No members with this role."

        
        embed = discord.Embed(
            title=f"{role.name}",
            color=role.color or discord.Color.blurple(),
            timestamp=datetime.now(),
            description=f"**Role**: {role.mention}\n\n**Members ({total_members})**:\n{member_mentions}"  
        )

        
        embed.set_thumbnail(url=role.guild.icon.url if role.guild.icon else None)

        
        embed.set_footer(text=f"Role ID: {role.id} | Page {current_page + 1}/{total_pages}")

        return embed  

def setup(bot):
    bot.add_cog(Information(bot))
