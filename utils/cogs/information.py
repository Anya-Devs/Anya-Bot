
import json
import aiohttp
from datetime import datetime

from data.const import *

from data.const import primary_color, Information_Embed
from discord.ui import View, Select, Button
from imports.discord_imports import *





class Information_Commands:
    

    async def server(self, ctx: commands.Context, mode: Optional[Literal["roles", "emojis"]] = None, cog=None, members_per_page=10) -> Union[discord.Embed, tuple[discord.Embed, discord.ui.View]]: 
        guild = ctx.guild

        if mode == "emojis":
            emojis = guild.emojis
            if not emojis:
                return discord.Embed(description="This server has no custom emojis.", color=primary_color())
            pages = [emojis[i:i+10] for i in range(0, len(emojis), 10)]
            view = Information_View.PaginationView(pages)
            return view.create_embed(ctx, 0, pages), view

        if mode == "roles":
            roles = sorted(guild.roles, key=lambda r: (len(r.members), r.color.value), reverse=True)
            roles = [r for r in roles if len(r.members) >= 5 and r.name][:25]
            if not roles:
                return discord.Embed(description="No roles available for selection.", color=primary_color())
            view = Information_View.Select_Role(roles=roles, cog=cog, members_per_page=members_per_page)
            return self.create_role_embed(roles[0], 0), view

        owner = guild.owner
        boosts = guild.premium_subscription_count
        overview = f"Owner: {owner.mention}\nBoosts: {boosts}/14\nBoost Tier: {'Tier ' + str(guild.premium_tier) if boosts else 'Not boosted'}"
        other = f"Roles: {len(guild.roles)}\nChannels: {len(guild.channels)} - Text: {len(guild.text_channels)} - Voice: {len(guild.voice_channels)}\nMembers: {guild.member_count} (Users: {len([m for m in guild.members if not m.bot])}, Bots: {len([m for m in guild.members if m.bot])})"

        embed = discord.Embed(color=primary_color(), timestamp=datetime.now())
        embed.set_author(name=guild.name, icon_url=owner.avatar.url)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_footer(text=f"ID: {guild.id}")
        embed.add_field(name="Overview", value=overview, inline=True)
        embed.add_field(name="Other", value=other, inline=True)
        return embed

    def create_role_embed(self, role, current_page):
        self.members_per_page = 25
        members = [member for member in role.members if not member.bot]
        total_members = len(members)
        total_pages = (total_members // self.members_per_page) + (1 if total_members % self.members_per_page else 0)
        start_index, end_index = current_page * self.members_per_page, (current_page + 1) * self.members_per_page
        members_for_page = members[start_index:end_index]
        member_mentions = ",".join([member.mention for member in members_for_page]) or "No members with this role."

        embed = discord.Embed(
            title=f"{role.name}",
            color=role.color or discord.Color.blurple(),
            timestamp=datetime.now(),
            description=f"**Role**: {role.mention}\n**Members ({total_members})**:\n{member_mentions}"
        )
        embed.set_thumbnail(url=role.guild.icon.url if role.guild.icon else None)
        embed.set_footer(text=f"Role ID: {role.id} | Page {current_page + 1}/{total_pages}")
        return embed









class Information_View:
    class PaginationView(View):
        def __init__(self, pages):
            super().__init__(timeout=None)
            self.current_page, self.pages = 0, pages

        async def update_embed(self, interaction):
            embed = self.create_embed(interaction, self.current_page, self.pages)
            await interaction.response.edit_message(embed=embed, view=self)

        def create_embed(self, ctx, page_index, pages):
            if page_index == -1: page_index = len(pages)
            try:
                embed = discord.Embed(
                    title="Server Emojis",
                    description="\n".join(f"{emoji} : `{emoji}`" for emoji in pages[page_index]),
                    color=primary_color()
                )
                if ctx.guild.icon: embed.set_thumbnail(url=ctx.guild.icon.url)
                embed.set_footer(text=f"{ctx.guild.name} • Page {page_index + 1}/{len(pages)}")
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

    class Select_Role(discord.ui.View):
        def __init__(self, roles, cog, members_per_page=25):
            super().__init__(timeout=120)
            self.cog, self.roles, self.current_page = cog, roles, 0
            self.selected_role, self.members_per_page = self.roles[0], members_per_page

            select = discord.ui.Select(
                placeholder="Select a role to view details...",
                options=[discord.SelectOption(label=r.name, description=f"{len(r.members)} members", value=str(r.id)) for r in roles]
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

        async def select_callback(self, interaction):
            role_id = int(interaction.data["values"][0])
            self.selected_role = discord.utils.get(interaction.guild.roles, id=role_id)
            if self.selected_role:
                self.current_page = 0
                embed = self.cog.create_role_embed(self.selected_role, self.current_page)
                self.update_navigation_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

        async def prev_page(self, interaction):
            await interaction.response.defer()
            if self.current_page > 0:
                self.current_page -= 1
                embed = self.cog.create_role_embed(self.selected_role, self.current_page)
                self.update_navigation_buttons()
                await interaction.message.edit(embed=embed, view=self)

        async def next_page(self, interaction):
            await interaction.response.defer()
            if self.current_page < self.get_total_pages(self.selected_role) - 1:
                self.current_page += 1
                embed = self.cog.create_role_embed(self.selected_role, self.current_page)
                self.update_navigation_buttons()
                await interaction.message.edit(embed=embed, view=self)

        def get_total_pages(self, role):
            members = [m for m in role.members if not m.bot]
            return (len(members) + self.members_per_page - 1) // self.members_per_page

    class PermissionsView(discord.ui.View):
        GENERAL_PERMISSIONS = ["administrator", "manage_guild", "manage_roles", "manage_channels", "kick_members", "ban_members", "manage_messages", "embed_links", "attach_files", "read_message_history"]
        TEXT_PERMISSIONS = ["send_messages", "send_tts_messages", "manage_messages", "manage_threads", "read_messages", "mention_everyone", "use_external_emojis", "add_reactions"]
        VOICE_PERMISSIONS = ["connect", "speak", "mute_members", "deafen_members", "move_members", "use_voice_activation"]

        def __init__(self, cog, ctx, permissions, target):
            super().__init__(timeout=None)
            self.cog, self.ctx, self.permissions, self.target, self.page = cog, ctx, permissions, target, 0
            self.perm_categories = [("General", self.GENERAL_PERMISSIONS), ("Text", self.TEXT_PERMISSIONS), ("Voice", self.VOICE_PERMISSIONS)]
            self.perm_details_dict = {}
            self.generate_permission_details()

        def generate_permission_details(self):
            for idx, (name, perms) in enumerate(self.perm_categories):
                details = [f"{'✅' if getattr(self.permissions, p) else '❌'} {p.replace('_', ' ').title()}" for p in perms]
                self.perm_details_dict[idx] = {"category_name": name, "perm_details": details}

        @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray, custom_id="previous")
        async def previous(self, button, interaction):
            if self.page > 0: self.page -= 1
            embed = self.build_perms_embed()
            await button.response.edit_message(embed=embed, view=self)

        @discord.ui.button(label="Next", style=discord.ButtonStyle.gray, custom_id="next")
        async def next(self, button, interaction):
            if self.page < len(self.perm_categories) - 1: self.page += 1
            embed = self.build_perms_embed()
            await button.response.edit_message(embed=embed, view=self)

        def build_perms_embed(self):
            category = self.perm_details_dict[self.page]
            embed = discord.Embed(
                title=f"{self.target.name}'s {category['category_name']} Permissions",
                description="\n".join(category["perm_details"]),
                color=primary_color()
            )
            return embed


 



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

