
import json
import aiohttp
from datetime import datetime

from Data.const import *

from Data.const import primary_color, Information_Embed
from discord.ui import View, Select, Button
from Imports.discord_imports import *


class Helper:

   
    class PaginationView(View):
        def __init__(self, pages):
            super().__init__(timeout=None) 
            self.current_page = 0
            self.pages = pages

        async def update_embed(self, interaction):
            embed = self.create_embed(interaction,  self.current_page, self.pages)
            await interaction.response.edit_message(embed=embed, view=self)

        def create_embed(self, ctx, page_index, pages):
          if page_index == -1:
              page_index = len(pages)
          try:
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
          except Exception as e:
            print(e)

        @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
        async def previous_page(self, button, interaction):
          try:
            
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_embed(button)
          except Exception as e:
            print(e)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
        async def next_page(self, button, interaction):
           try:
            if self.current_page < len(self.pages) - 1:
                self.current_page += 1
                await self.update_embed(button)
           except Exception as e:
             print(e)

    
    @staticmethod
    async def get_information_embed(args, bot):
        if isinstance(args, discord.Member):
            return await Information_Embed.get_member_embed(bot, args)
        elif isinstance(args, int):
            guild = bot.get_guild(args)
            if guild:
                return await Information_Embed.get_guild_embed(guild)
            else:
                raise ValueError("Invalid server ID provided.")
        elif isinstance(args, str):
            async with aiohttp.ClientSession() as session:
                invite = await bot.fetch_invite(args)
                return await Information_Embed.get_invite_embed(invite)
        else:
            return await Information_Embed.get_bot_embed(bot.user, bot)



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

        self.prev_button = discord.ui.Button(emoji="◀️", style=discord.ButtonStyle.primary, custom_id="prev", row=1)
        self.next_button = discord.ui.Button(emoji="▶️", style=discord.ButtonStyle.primary, custom_id="next", row=1)

        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        self.update_navigation_buttons()

    def update_navigation_buttons(self):
        total_pages = self.get_total_pages(self.selected_role)

        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= total_pages - 1

    async def select_callback(self, interaction: discord.Interaction):
        role_id = int(interaction.data["values"][0])
        self.selected_role = discord.utils.get(interaction.guild.roles, id=role_id)

        if self.selected_role:
            self.current_page = 0  
            embed = self.cog.create_role_embed(self.selected_role, self.current_page)
            self.update_navigation_buttons()
            await interaction.response.edit_message(embed=embed, view=self)

    async def prev_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            embed = self.cog.create_role_embed(self.selected_role, self.current_page)
            self.update_navigation_buttons()
            await interaction.message.edit(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        """Handles the next page button."""
        await interaction.response.defer()
        total_pages = self.get_total_pages(self.selected_role)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            embed = self.cog.create_role_embed(self.selected_role, self.current_page)
            self.update_navigation_buttons()
            await interaction.message.edit(embed=embed, view=self)

    def get_total_pages(self, role):
        members = [member for member in role.members if not member.bot]
        total_members = len(members)
        return (total_members // self.members_per_page) + (1 if total_members % self.members_per_page != 0 else 0)
    


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

