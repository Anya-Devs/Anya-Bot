import aiohttp
from datetime import datetime

from Data.const import *
from Subcogs.information import Guide
from Data.const import primary_color, Information_Embed
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

    @commands.command(name="about", aliases=["info", "details"])
    async def about(self, ctx, id: Union[discord.Member, int, str] = None):
        if id is None:
            id = ctx.bot.user
        embed = await self.get_information_embed(id, self.bot)
        await ctx.reply(embed=embed, mention_author=False)

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

     # Count members
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

    @commands.command(name="role")
    async def role(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        role = user.top_role
        member_count = sum(
            1 for member in ctx.guild.members if role in member.roles)
        description = (
            f"Role: {role.mention}\n"
            f"Members with this role: `{member_count}`\n"
            f"Rank: `{ctx.guild.roles.index(role) + 1}`"
        )
        embed = discord.Embed(
            description=description, color=role.color, timestamp=datetime.now()
        )
        await ctx.reply(embed=embed, mention_author=False)

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

    @commands.command(name="roles")
    async def roles(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        roles = [role.mention for role in user.roles if role !=
                 ctx.guild.default_role]
        embed = discord.Embed(
            description=", ".join(roles),
            color=primary_color(),
            timestamp=datetime.now(),
        )
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="invite")
    async def invite(self, ctx, link: str):
        invite = await self.bot.fetch_invite(link)
        embed = await Information_Embed.get_invite_embed(invite)
        await ctx.reply(embed=embed, mention_author=False)

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


def setup(bot):
    bot.add_cog(Guide(bot))
    bot.add_cog(Information(bot))
