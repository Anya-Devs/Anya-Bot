
import json
import aiohttp
from datetime import datetime

from data.local.const import *
from data.local.const import primary_color
from discord.ui import View
from imports.discord_imports import *
from imports.log_imports import *


class Information_Commands:
    def __init__(self):
        self.members_per_page = 25

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
            view = Information_View.Select_Role(roles=roles, cog=Information_Commands(), members_per_page=members_per_page)
            return self.create_role_embed(roles[0], 0), view

        owner = guild.owner
        boosts = guild.premium_subscription_count
        overview = f"Owner: {owner.mention}\nBoosts: {boosts}/14\nBoost Tier: {'Tier ' + str(guild.premium_tier) if boosts else 'Not boosted'}"
        other = f"Roles: {len(guild.roles)}\nChannels: {len(guild.channels)} - Text: {len(guild.text_channels)} - Voice: {len(guild.voice_channels)}\nMembers: {guild.member_count} (Users: {len([m for m in guild.members if not m.bot])}, Bots: {len([m for m in guild.members if m.bot])})"

        embed = discord.Embed(title=guild.name, color=primary_color(), timestamp=datetime.now())
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_footer(text=f"ID: {guild.id}")
        embed.add_field(name="Overview", value=overview, inline=True)
        embed.add_field(name="Other", value=other, inline=True)
        return embed

    def create_role_embed(self, role, current_page):
        members = [member for member in role.members if not member.bot]
        total_members = len(members)
        total_pages = (total_members // self.members_per_page) + (1 if total_members % self.members_per_page else 0)
        start_index = current_page * self.members_per_page
        end_index = (current_page + 1) * self.members_per_page
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

    async def next_page(self, interaction):
        try:
            await interaction.response.defer()
            if self.current_page < self.get_total_pages(self.selected_role) - 1:
                self.current_page += 1
                embed = self.create_role_embed(self.selected_role, self.current_page)  
                self.update_navigation_buttons()
                await interaction.message.edit(embed=embed, view=self)
        except Exception as e:
            logging.error(f"Error in next_page: {e}")
    
    
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
                return await Information_Embed.get_invite_embed(invite, bot)
        else:
            return await Information_Embed.get_bot_embed(bot.user, bot)








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
     def __init__(self, roles, cog, members_per_page):
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
        try:
            role_id = int(interaction.data["values"][0])
            self.selected_role = discord.utils.get(interaction.guild.roles, id=role_id)
            if self.selected_role:
                self.current_page = 0
                embed = self.cog.create_role_embed(self.selected_role, self.current_page)
                self.update_navigation_buttons()
                await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logging.error(f"Error in select_callback: {e}")

     async def prev_page(self, interaction):
        try:
            await interaction.response.defer()
            if self.current_page > 0:
                self.current_page -= 1
                embed = self.cog.create_role_embed(self.selected_role, self.current_page)
                self.update_navigation_buttons()
                await interaction.message.edit(embed=embed, view=self)
        except Exception as e:
            logging.error(f"Error in prev_page: {e}")

     async def next_page(self, interaction):
        try:
            await interaction.response.defer()
            if self.current_page < self.get_total_pages(self.selected_role) - 1:
                self.current_page += 1
                embed = self.cog.create_role_embed(self.selected_role, self.current_page)
                self.update_navigation_buttons()
                await interaction.message.edit(embed=embed, view=self)
        except Exception as e:
            logging.error(f"Error in next_page: {e}")

     def get_total_pages(self, role):
        try:
            members = [m for m in role.members if not m.bot]
            return (len(members) + self.members_per_page - 1) // self.members_per_page
        except Exception as e:
            logging.error(f"Error in get_total_pages: {e}")
            return 0
    
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







class Information_Embed:
    @staticmethod
    async def get_user_banner_url(bot, user):
        user_data = await bot.fetch_user(user.id)
        return user_data.banner.url if user_data.banner else None

    @staticmethod
    async def get_bot_embed(bot_user: discord.User, bot):
        def timestamp_gen(ts: int) -> str:
            return f"<t:{int(datetime.utcfromtimestamp(ts).timestamp())}:R>"

        try:
            cpu = f"{psutil.cpu_percent(1):.0f}% of {psutil.cpu_count()} cores"
            ram_data = psutil.virtual_memory()
            ram = f"{ram_data.percent:.0f}% of {ram_data.total / 1e9:.0f}GB ({ram_data.total * ram_data.percent / 100 / 1e9:.0f}GB)"
            total_users = sum(g.member_count for g in bot.guilds)
            created = timestamp_gen(int(bot_user.created_at.timestamp()))
            owner = bot.get_user(1124389055598170182)
            embed = discord.Embed(
                title="Bot Information",
                description=(
                    "Assigns member's quests to encourage server activity. Has other commands for everyone.\n\n"
                    f"🌐 Global:\n- Servers: {len(bot.guilds)}\n- Members: {total_users}\n\n"
                    f"❤️ Internal:\n- **CPU**: {cpu}\n- **RAM**: {ram}\n\n"
                    f":clock: Creation:\n- **Developer**: {owner}\n- **When?**: {created}\n\n"
                    "-# [Support server](https://discord.gg/vFwPn74mfJ)\n"
                    "-# [Invite bot](https://discord.com/oauth2/authorize?client_id=1234247716243112100&permissions=27482422508608&scope=bot)\n"
                ),
                timestamp=datetime.now(), color=primary_color()
            )
            embed.set_thumbnail(url=owner.avatar)
            embed.set_image(url=await Information_Embed.get_user_banner_url(bot, bot.user))
            embed.set_footer(text="About Myself")
            return embed, None
        except Exception as e:
            print(e)

    @staticmethod
    async def get_member_embed(bot, member):
     def timestamp_gen(ts): return f"<t:{int(ts)}:R>"

     try:
        created = timestamp_gen(member.created_at.replace(tzinfo=timezone.utc).timestamp())
        joined = timestamp_gen(member.joined_at.replace(tzinfo=timezone.utc).timestamp())
        type_icon = "🤖" if member.bot else "👤"

        perms = member.guild_permissions
        category = (
            "Admin" if perms.administrator or perms.manage_guild else
            "Moderator" if perms.kick_members or perms.ban_members or perms.manage_messages else
            "Member"
        )

        top_roles = sorted(
            [r for r in member.roles if r.name != "@everyone" and (
                r.permissions.administrator or r.permissions.kick_members or
                r.permissions.ban_members or r.permissions.manage_messages)],
            key=lambda r: (
                r.permissions.administrator,
                r.permissions.kick_members or r.permissions.ban_members,
                r.permissions.manage_messages
            ), reverse=True)

        top_roles_text = "".join(
            f"- {r.mention} (admin)\n" if r.permissions.administrator else
            f"- {r.mention} (moderator)\n" if r.permissions.kick_members or r.permissions.ban_members else
            f"- {r.mention} (baby moderator)\n" if r.permissions.manage_messages else
            f"- {r.mention}\n"
            for r in top_roles) or "No top roles"

        embed = discord.Embed(
            title=member.display_name,
            description=(
                f"**User**: {member}\n**Nick**: {member.nick or 'No nickname'}\n\n"
                f"**Created**: {created}    **Joined**: {joined}\n\n"
                f"-# **Top Roles with perms:**\n{top_roles_text}"
            ),
            color=member.color,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_footer(text=f"ID: {member.id} | {type_icon} {category}")

        banner_url = await Information_Embed.get_user_banner_url(bot, member)
        if banner_url:
            embed.set_image(url=banner_url)

        
        button = discord.ui.Button(label="Show Roles", style=discord.ButtonStyle.primary)

        async def button_callback(interaction: discord.Interaction):
            try:
                chan_perms = set()
                for chan in member.guild.channels:
                    if isinstance(chan, discord.TextChannel) and not chan.permissions_for(member.guild.default_role).view_channel:
                        for role in member.guild.roles:
                            if role != member.guild.default_role and chan.permissions_for(role).view_channel:
                                chan_perms.add(role)

                channel_roles = [r for r in member.roles if r in chan_perms]
                misc_roles = [r for r in member.roles if r.name != "@everyone" and r not in top_roles and r not in channel_roles]

                embed_chan = discord.Embed(
                    title=f"{member.display_name}'s Channel Permission Roles",
                    description="".join(f"- {r.mention}\n" for r in channel_roles) or "No channel permission roles",
                    color=member.color,
                    timestamp=datetime.now()
                )

                misc_embeds = []
                for i in range(0, len(misc_roles), 25):
                    page = discord.Embed(
                        title=f"{member.display_name}'s Misc Roles",
                        description="".join(f"- {r.mention}\n" for r in misc_roles[i:i + 25]) or "No miscellaneous roles",
                        color=member.color,
                        timestamp=datetime.now()
                    )
                    page.set_footer(text=f"Page {i // 25 + 1}")
                    misc_embeds.append(page)

                await interaction.response.send_message(
                    embeds=[embed_chan] + misc_embeds, ephemeral=True
                )

            except Exception as e:
                logging.exception("Error in button callback:")

        button.callback = button_callback
        view = discord.ui.View()
        view.add_item(button)

        return embed, view

     except Exception as e:
        logging.exception("Error in get_member_embed:")
        return None, None
    
    @staticmethod
    async def get_guild_embed(guild, invite=None, bot=None):
     try:
        ts_fmt = lambda ts: f"<t:{int(ts)}:R>"
        is_partial = isinstance(guild, discord.PartialInviteGuild)

        # === Owner ===
        if not is_partial:
            owner = getattr(guild, "owner", None)
            owner_text = owner.mention if owner else f"ID: {getattr(guild, 'owner_id', 'Unknown')}"
        else:
            owner_text = "Unknown (invite preview only)"

        # === Boost Info ===
        if not is_partial:
            boosts = getattr(guild, "premium_subscription_count", 0) or 0
            boost_tier = f"Tier {getattr(guild, 'premium_tier', 0)}" if boosts else "Not boosted"
            booster = f"Boosts: {boosts}/14\nBoost Tier: {boost_tier}"
        else:
            booster = "Boost info unavailable (invite preview)"

        # === Overview ===
        created_ts = getattr(guild, "created_at", datetime.now()).timestamp()
        overview = f"Owner: {owner_text}\nCreated: {ts_fmt(created_ts)}"

        # === Member & Channel Info ===
        if not is_partial:
            member_count = getattr(guild, "member_count", None)
            online_count = 0
            bot_count = 0
            user_count = 0

            if member_count is None and bot:
                try:
                    # Fetch full guild counts
                    full_guild = await bot.fetch_guild(guild.id, with_counts=True)
                    member_count = getattr(full_guild, "approximate_member_count", 0) or 0
                    online_count = getattr(full_guild, "approximate_presence_count", 0) or 0
                except Exception:
                    member_count = 0
                    online_count = 0

            # Count bots/users if cache exists
            members = getattr(guild, "members", [])
            if members:
                bot_count = sum(1 for m in members if m.bot)
                user_count = sum(1 for m in members if not m.bot)
                online_count = sum(1 for m in members if m.status != discord.Status.offline)
            else:
                user_count = member_count - bot_count

            other = (
                f"Roles: {len(getattr(guild, 'roles', []))}\n"
                f"Channels: {len(getattr(guild, 'channels', []))} "
                f"(Text: {len(getattr(guild, 'text_channels', []))}, "
                f"Voice: {len(getattr(guild, 'voice_channels', []))})\n"
                f"Members: {member_count} (Users: {user_count}, Bots: {bot_count})\n"
                f"Online: {online_count}"
            )
        else:
            member_count = getattr(guild, "approximate_member_count", 0) or 0
            online_count = getattr(guild, "approximate_presence_count", 0) or 0
            other = f"Approx Members: {member_count}\nApprox Online: {online_count}"

        # === Embed ===
        embed = discord.Embed(
            title=getattr(guild, "name", "Unknown Server"),
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        if getattr(guild, "icon", None):
            embed.set_thumbnail(url=guild.icon.url)
        if getattr(guild, "banner", None):
            embed.set_image(url=guild.banner.url)

        embed.add_field(name="Overview", value=overview, inline=True)
        embed.add_field(name="Other", value=other, inline=True)
        embed.add_field(name="Boost Info", value=booster, inline=False)
        embed.set_footer(text=f"ID: {getattr(guild, 'id', 'Unknown')}")

        return embed, None

     except Exception:
        logging.error("get_guild_embed error:\n" + traceback.format_exc())
        return None, None
    
    @staticmethod
    async def get_invite_embed(invite_str: str | discord.Invite, bot: commands.Bot):
     try:
        if isinstance(invite_str, discord.Invite):
            invite = invite_str
        else:
            invite_code = invite_str.split("/")[-1].strip()
            try:
                invite = await bot.fetch_invite(invite_code, with_counts=True, with_expiration=True)
            except discord.NotFound:
                invite = None

        guild = getattr(invite, "guild", None)

        if not guild:
            invite_code = invite_str.split("/")[-1].strip()
            url = f"https://discord.com/api/v10/invites/{invite_code}?with_counts=true&with_expiration=true"
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json().get("guild", {})
                guild_id = data.get("id")
                icon_hash = data.get("icon")
                name = data.get("name", "Unknown Server")
                ext = "gif" if icon_hash and icon_hash.startswith("a_") else "png"
                icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.{ext}" if guild_id and icon_hash else None

                embed = discord.Embed(
                    title=name,
                    description=f"ID: `{guild_id}`",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                if icon_url:
                    embed.set_thumbnail(url=icon_url)
                return embed, None
            else:
                return discord.Embed(
                    title="Invalid Invite",
                    description="This invite link/code appears to be invalid or expired.",
                    color=discord.Color.red()
                ), None

        try:
            embed, _ = await Information_Embed.get_guild_embed(guild, bot=bot)
        except Exception:
            embed = discord.Embed(
                title="Invite Information",
                description="Could not fetch guild info from invite.",
                color=discord.Color.red(),
                timestamp=datetime.now(),
            )

        return embed, None

     except Exception as e:
        logging.error(f"get_invite_embed error: {e}")
        return None, None

class RoleLookupView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.selected = []
        self.user_select = ui.UserSelect(placeholder="Select users...", min_values=1, max_values=25)
        self.user_select.callback = self.user_select_callback
        self.add_item(self.user_select)

    async def user_select_callback(self, interaction: Interaction):
        self.selected = self.user_select.values
        await interaction.response.send_message(f"✅ Selected {len(self.selected)} user(s). Click Validate.", ephemeral=True)

    def get_role_category(self, role):
        p = role.permissions
        if p.administrator: return "admin"
        if p.kick_members or p.ban_members: return "moderator"
        if p.manage_messages: return "baby moderator"
        return None

    def categorize_roles(self, member):
        chan_perms = set()
        for chan in member.guild.channels:
            if isinstance(chan, discord.TextChannel) and not chan.permissions_for(member.guild.default_role).view_channel:
                for role in member.guild.roles:
                    if role != member.guild.default_role and chan.permissions_for(role).view_channel:
                        chan_perms.add(role)
        perm_roles, channel_roles, misc_roles = [], [], []
        for r in member.roles[1:]:
            c = self.get_role_category(r)
            if c: perm_roles.append((r, c))
            elif r in chan_perms: channel_roles.append(r)
            else: misc_roles.append(r)
        perm_roles.sort(key=lambda x: ("admin", "moderator", "baby moderator").index(x[1]) if x[1] in ("admin", "moderator", "baby moderator") else 99)
        return perm_roles, channel_roles, misc_roles

    async def create_user_embeds(self, member):
        perm, chan, misc = self.categorize_roles(member)
        embeds = []
        overview = discord.Embed(
            title=f"Roles for {member.display_name}",
            description=(
                f"Breakdown of {member.mention}'s roles by category.\n\n"
                "**How to use:**\n"
                "- Use the dropdown to jump between categories.\n"
                "- Categories shown depend on roles the member has."
            ),
            color=member.color,
            timestamp=datetime.now()
        ).set_thumbnail(url=member.display_avatar.url)
        embeds.append(overview)

        if perm:
            txt = "".join(f"- {r.mention} ({c})\n" for r, c in perm)
            embeds.append(discord.Embed(title="Permission Roles", description=txt, color=member.color, timestamp=datetime.now()).set_thumbnail(url=member.display_avatar.url))
        if chan:
            embeds.append(discord.Embed(title="Channel Access", description="".join(f"- {r.mention}\n" for r in chan), color=member.color, timestamp=datetime.now()).set_thumbnail(url=member.display_avatar.url))
        if misc:
            misc_pages = [misc[i:i+10] for i in range(0, len(misc), 10)]
            for i, page in enumerate(misc_pages):
                title = "Misc" if len(misc_pages) == 1 else f"Misc P.{i+1}"
                e = discord.Embed(title=title, description="".join(f"- {r.mention}\n" for r in page), color=member.color, timestamp=datetime.now()).set_thumbnail(url=member.display_avatar.url)
                e.set_footer(text=f"Page {i+1} of {len(misc_pages)}")
                embeds.append(e)
        return embeds

    class RolePaginationView(ui.View):
        def __init__(self, embeds):
            super().__init__(timeout=None)
            self.embeds = embeds
            options = [discord.SelectOption(label="Overview", value="0")]
            for i, embed in enumerate(embeds[1:], start=1):
                options.append(discord.SelectOption(label=embed.title, value=str(i)))
            self.page_select = ui.Select(placeholder="Jump to section...", options=options)
            self.page_select.callback = self.select_page
            self.add_item(self.page_select)
            self.idx = 0

        async def select_page(self, interaction):
            self.idx = int(self.page_select.values[0])
            await interaction.response.edit_message(embed=self.embeds[self.idx], view=self)

    @ui.button(label="Validate", style=discord.ButtonStyle.success, row=1)
    async def validate(self, button, interaction):
        if not self.selected:
            return await button.response.send_message("❌ No users selected.", ephemeral=True)
        try:
            await button.response.defer(ephemeral=True)
            # Send each user's paginated role embeds with their own select menu
            for member in self.selected:
                embeds = await self.create_user_embeds(member)
                view = self.RolePaginationView(embeds)
                await button.followup.send(embed=embeds[0], view=view, ephemeral=True)

        except Exception:
            import traceback
            tb = traceback.format_exc()
            print(tb)
            await button.followup.send(f"⚠️ Error:\n```\n{tb[:1900]}\n```", ephemeral=True)












