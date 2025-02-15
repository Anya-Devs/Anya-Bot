import json
import aiohttp
from datetime import datetime

from Data.const import *

from Data.const import primary_color, Information_Embed
from discord.ui import View, Select, Button
from Imports.discord_imports import *


GENERAL_PERMISSIONS = [
    "administrator",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "kick_members",
    "ban_members",
    "manage_messages",
    "embed_links",
    "attach_files",
    "read_message_history",
]

TEXT_PERMISSIONS = [
    "send_messages",
    "send_tts_messages",
    "manage_messages",
    "manage_threads",
    "read_messages",
    "mention_everyone",
    "use_external_emojis",
    "add_reactions",
]

VOICE_PERMISSIONS = [
    "connect",
    "speak",
    "mute_members",
    "deafen_members",
    "move_members",
    "use_voice_activation",
]


async def get_user_banner_url(bot, user):
    req = await bot.http.request(discord.http.Route("GET", "/users/{uid}", uid=user.id))
    banner_id = req.get("banner")
    if banner_id:
        image_size = "?size=1024"
        animated = banner_id.startswith("a_")
        file_extension = "gif" if animated else "png"
        image_base_url = "https://cdn.discordapp.com/"
        banners_endpoint = f"banners/{user.id}/{banner_id}.{file_extension}"
        return f"{image_base_url}{banners_endpoint}{image_size}"
    return None


class Information(commands.Cog):
    """
    A cog for displaying bot information.
    """

    def __init__(self, bot):
        self.bot = bot
        self.members_per_page = 25


    @commands.command(name="about", aliases=["info", "details"])
    async def about(self, ctx, topic: Union[discord.Member, int, str] = None):
        if topic is None:
            topic = ctx.bot.user
        embed = await self.get_information_embed(id, self.bot)
        await ctx.reply(embed=embed, mention_author=False)
        
 

    @commands.command(name="json")
    async def json(self, ctx, member: discord.Member = None):
        """Command to generate a JSON report of a member's info."""
        if not member:
            member = ctx.author  

        
        member_info = {
            "username": member.name,
            "nickname": member.nick or "None",
            "current_name": member.display_name,
            "joined_at": self.format_time(member.joined_at),
            "created_at": self.format_time(member.created_at),
            "status": member.status.name.capitalize(),
            "presence": member.activity.name if member.activity else "None",
            "top_role": member.top_role.name,
            "permissions": await self.get_permissions(member),  
            "roles": [role.name for role in member.roles if role.name != "@everyone"],
            "last_message": await self.get_last_message(member, ctx),
            "pinged_by": await self.get_pinged_by(ctx, member),
            "avatar_url": str(member.avatar),
        }

        
        embed = discord.Embed(
            title=f"{member.name}'s Info",
            description=f"```json\n{json.dumps(member_info, indent=4)}\n```",
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_footer(icon_url=ctx.author.avatar ,text=f"User: {ctx.author}・ID: {ctx.author.id}")

        
        await ctx.reply(embed=embed,mention_author=False)

    def format_time(self, time):
        """Formats a datetime object into a human-readable format."""
        return time.strftime("%A, %B %d, %Y at %I:%M %p")

    async def get_permissions(self, member):
        """Returns a formatted list of permissions for the member."""
        permissions = member.guild_permissions
        perms = []
        for perm, value in permissions:
            if value:
                perms.append(f"{perm.replace('_', ' ').capitalize()}")
        return perms or ["No special permissions"]



    async def get_last_message(self, member, ctx):
     """Fetches the last message sent by the member in the current channel."""
     async for message in ctx.channel.history(limit=100):
        
        if message.author == self.bot.user or message.content.startswith(ctx.prefix):
            continue

        
        if message.author == member:
            return f"[{message.content}]({message.jump_url})"
    
     return "No messages found"

    async def get_pinged_by(self, ctx, member):
     """Fetches who mentioned the member in the current channel."""
     mentioned_by = []
     async for message in ctx.channel.history(limit=100):
        
        if message.author == self.bot.user or message.content.startswith(ctx.prefix):
            continue

        
        if member.mention in message.content and message.author != member:
            mentioned_by.append(message.author.name)
    
     return mentioned_by or ["No one"]
    
    @staticmethod
    async def get_information_embed(id, bot):
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

    @commands.command(name="joined")
    async def joined(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        description = (
            f"Joined on: {timestamp_gen(user.joined_at.timestamp())}\n"
            f"Account created on: {timestamp_gen(user.created_at.timestamp())}"
        )
        embed = discord.Embed(
            description=description, color=primary_color(), timestamp=datetime.now()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="invite")
    async def invite(self, ctx, link: str = None):
        """Command to fetch an invite link or generate a new one if invalid."""

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
        """Generates a new infinite invite link and sends it."""
        
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

    @commands.command(name="emojis")
    async def list_emojis(self, ctx):
        """Lists all server emojis with pagination."""
        emojis = ctx.guild.emojis
        if not emojis:
            await ctx.reply("This server has no custom emojis!", mention_author=False)
            return

        emojis_per_page = 10
        pages = [
            emojis[i: i + emojis_per_page]
            for i in range(0, len(emojis), emojis_per_page)
        ]

        def create_embed(page_index):
            embed = discord.Embed(
                title="Server Emojis",
                description="\n".join(
                    f"{emoji} : `{emoji}`" for emoji in pages[page_index]
                ),
                color=primary_color(),
            )
            embed.set_thumbnail(
                url=ctx.guild.icon.url if ctx.guild.icon else None)
            embed.set_footer(
                text=f"{ctx.guild.name} • Page {page_index + 1}/{len(pages)}"
            )
            return embed

        class PaginationView(View):
            def __init__(self):
                super().__init__(timeout=60)
                self.current_page = 0

            async def update_embed(self, interaction):
                embed = create_embed(self.current_page)
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
            async def previous_page(self, button, interaction):
                if self.current_page > 0:
                    self.current_page -= 1
                    await self.update_embed(button)

            @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
            async def next_page(self, button, interaction):
                if self.current_page < len(pages) - 1:
                    self.current_page += 1
                    await self.update_embed(button)

        embed = create_embed(0)
        view = PaginationView()
        await ctx.reply(embed=embed, view=view, mention_author=False)

    @commands.command(name="server_roles")
    async def role_select(self, ctx):
        """Command to let users select roles and navigate members."""
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

    
class PermissionsView(discord.ui.View):
    GENERAL_PERMISSIONS = [
        "administrator",
        "manage_guild",
        "manage_roles",
        "manage_channels",
        "kick_members",
        "ban_members",
        "manage_messages",
        "embed_links",
        "attach_files",
        "read_message_history",
    ]
    TEXT_PERMISSIONS = [
        "send_messages",
        "send_tts_messages",
        "manage_messages",
        "manage_threads",
        "read_messages",
        "mention_everyone",
        "use_external_emojis",
        "add_reactions",
    ]
    VOICE_PERMISSIONS = [
        "connect",
        "speak",
        "mute_members",
        "deafen_members",
        "move_members",
        "use_voice_activation",
    ]

    def __init__(self, cog, ctx, permissions, target):
        super().__init__(timeout=None)
        self.cog = cog
        self.ctx = ctx
        self.permissions = permissions
        self.target = target
        self.page = 0

        
        self.perm_categories = [
            ("General", self.GENERAL_PERMISSIONS),
            ("Text", self.TEXT_PERMISSIONS),
            ("Voice", self.VOICE_PERMISSIONS),
        ]

        
        self.perm_details_dict = {}
        self.generate_permission_details()

        
        print(
            f"PermissionsView initialized with target: {target} and page: {self.page}"
        )
        print(f"Permission categories: {self.perm_categories}")

    def generate_permission_details(self):
        """Generates the permission details for each page and stores them in a dictionary."""
        for idx, (category_name, permissions_list) in enumerate(self.perm_categories):
            perm_details = [
                f"{'✅' if getattr(self.permissions, perm) else '❌'} {perm.replace('_', ' ').title()}"
                for perm in permissions_list
            ]
            self.perm_details_dict[idx] = {
                "category_name": category_name,
                "perm_details": perm_details,
            }
            print(
                f"Stored permissions for page {idx}: {self.perm_details_dict[idx]}")

    @discord.ui.button(
        label="Previous", style=discord.ButtonStyle.gray, custom_id="previous"
    )
    async def previous(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        
        print(f"Interaction received: previous")

        
        if self.page > 0:
            self.page -= 1
            print(f"Previous button clicked, moving to page {self.page}")
        else:
            print("Cannot move to previous page (already on the first page).")

        
        embed = self.build_perms_embed()
        print(f"Built embed for page {self.page}: {embed.title}")

        
        await button.response.edit_message(embed=embed, view=self)
        print("Message updated with new embed and view.")

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray, custom_id="next")
    async def next(self, button: discord.ui.Button, interaction: discord.Interaction):
        print(f"Interaction received: next")  

        
        if self.page < len(self.perm_categories) - 1:
            self.page += 1
            print(f"Next button clicked, moving to page {self.page}")
        else:
            print("Cannot move to next page (already on the last page).")

        
        embed = self.build_perms_embed()
        print(f"Built embed for page {self.page}: {embed.title}")

        
        await button.response.edit_message(embed=embed, view=self)
        print("Message updated with new embed and view.")

    def build_perms_embed(self):
        """Generates an embed showing the permissions for the current page."""
        category_name = self.perm_details_dict[self.page]["category_name"]
        perm_details = self.perm_details_dict[self.page]["perm_details"]

        print(
            f"Permissions details for page {self.page}: {perm_details}"
        )  

        
        embed = discord.Embed(
            title=f"{category_name} Permissions for {self.target.display_name}",
            description="\n".join(perm_details),
            color=primary_color(),  
            timestamp=datetime.now(),  
        )
        embed.set_footer(
            text=f"Page {self.page + 1} of {len(self.perm_categories)}")
        return embed
    
 

class Select_Role(discord.ui.View):
    def __init__(self, roles, cog, members_per_page):
        super().__init__(timeout=120)  
        self.cog = cog
        self.roles = roles
        self.current_page = 0
        self.selected_role = self.roles[0]  
        self.members_per_page = members_per_page  

        
        select = discord.ui.Select(
            placeholder="Select a role to view details...",
            options=[
                discord.SelectOption(
                    label=role.name,
                    description=f"{len(role.members)} members",
                    value=str(role.id)
                )
                for role in self.roles
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

        
        self.add_item(discord.ui.Button(emoji="◀️", style=discord.ButtonStyle.primary, custom_id="prev", row=1))
        self.add_item(discord.ui.Button(emoji="▶️", style=discord.ButtonStyle.primary, custom_id="next", row=1))

        
        for button in self.children:
            if isinstance(button, discord.ui.Button):
                button.callback = self.button_callback

        self.update_navigation_buttons()  

    def update_navigation_buttons(self):
        """Enable/Disable navigation buttons based on current page and total pages."""
        total_pages = self.get_total_pages(self.selected_role)

        
        prev_button = next((btn for btn in self.children if btn.custom_id == "prev"), None)
        next_button = next((btn for btn in self.children if btn.custom_id == "next"), None)

        
        if prev_button:
            prev_button.disabled = self.current_page <= 0

        
        if next_button:
            next_button.disabled = self.current_page >= total_pages - 1

    async def select_callback(self, interaction: discord.Interaction):
        """Handles role selection from the dropdown menu."""
        role_id = int(interaction.data["values"][0])
        self.selected_role = discord.utils.get(interaction.guild.roles, id=role_id)

        if self.selected_role:
            self.current_page = 0  
            embed = self.cog.create_role_embed(self.selected_role, self.current_page)
            self.update_navigation_buttons()  
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=self)

    async def button_callback(self, interaction: discord.Interaction):
        """Handle the navigation buttons (previous/next)."""
        
        if not interaction.response.is_done():
            await interaction.response.defer()

        
        if interaction.data["custom_id"] == "prev" and self.current_page > 0:
            self.current_page -= 1
        elif interaction.data["custom_id"] == "next":
            total_pages = self.get_total_pages(self.selected_role)
            if self.current_page < total_pages - 1:
                self.current_page += 1

        
        embed = self.cog.create_role_embed(self.selected_role, self.current_page)  

        
        self.update_navigation_buttons()  

        
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)

    def get_total_pages(self, role):
        """Calculate the total number of pages needed to display members."""
        members = [member for member in role.members if not member.bot]
        total_members = len(members)
        return (total_members // self.members_per_page) + (1 if total_members % self.members_per_page != 0 else 0)
    
    
    
    
    
    
def setup(bot):
    bot.add_cog(Information(bot))
