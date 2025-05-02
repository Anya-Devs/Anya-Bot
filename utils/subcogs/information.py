import os
import tempfile
import traceback
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO

import aiohttp
import asyncio
from PIL import Image

from Imports.discord_imports import *


class SelectMenu(Select):
    def __init__(self, roles: list, cog):
        options = [
            discord.SelectOption(label=role.name[:100], value=str(role.id))
            for role in roles
        ]
        super().__init__(placeholder="Select a Role", options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        try:
            role_id = interaction.data["values"][0]
            page_num = 0
            await self.cog.navigate_role_members_embed(
                interaction, interaction.message, role_id, page_num
            )
        except discord.errors.NotFound:
            # This exception is raised when the message or interaction is not found.
            # You can silently ignore it or handle it as you see fit.
            pass
        except Exception as e:
            print(f"Error in callback method: {e}")
            traceback.print_exc()


class SelectView(discord.ui.View):
    def __init__(self, roles: list, cog):
        super().__init__()
        self.add_item(SelectMenu(roles, cog))


class FilterOption(Enum):
    NEWEST_TO_OLDEST = "n-o"
    OLDEST_TO_NEWEST = "o-n"
    MOST_ACTIVE_TO_LEAST_ACTIVE = "ma-la"
    LEAST_ACTIVE_TO_MOST_ACTIVE = "la-ma"
    MOST_ROLES_TO_LEAST_ROLES = "mr-lr"
    LEAST_ROLES_TO_MOST_ROLES = "lr-mr"


class ButtonNavigationView(View):
    def __init__(self, embeds, timeout=180):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0

        # Update buttons' state
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        self.add_item(
            Button(
                label="◀️",
                style=discord.ButtonStyle.primary,
                custom_id="prev",
                disabled=self.current_page == 0,
            )
        )
        self.add_item(
            Button(
                label="▶️",
                style=discord.ButtonStyle.primary,
                custom_id="next",
                disabled=self.current_page == len(self.embeds) - 1,
            )
        )

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary, custom_id="prev")
    async def previous_button_callback(
        self, interaction: discord.Interaction, button: Button
    ):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page], view=self
            )
            self.update_buttons()

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary, custom_id="next")
    async def next_button_callback(
        self, interaction: discord.Interaction, button: Button
    ):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            await interaction.response.edit_message(
                embed=self.embeds[self.current_page], view=self
            )
            self.update_buttons()

    async def on_timeout(self):
        # Disable all buttons when the view times out
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)


class Guide(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.data = {}
        self.invites = {}  # Dictionary to track invites
        self.current_page = 0

        self.afk_file_path = "Caster-Bot/Caster-main/afk_members.json"

    @staticmethod
    async def fetch_invites(guild):
        return await guild.invites()

    async def update_invites(self, guild):
        new_invites = await self.fetch_invites(guild)
        self.invites[guild.id] = new_invites

    async def fetch_invite_for_member(self, member):
        guild = member.guild
        if guild.id not in self.invites:
            await self.update_invites(guild)

        invites_before = self.invites[guild.id]
        invites_after = await self.fetch_invites(guild)

        for invite in invites_after:
            if invite.uses > invite.max_uses and invite not in invites_before:
                return invite
        return None

    async def get_inviter_mention(self, member):
        try:
            invite = await self.fetch_invite_for_member(member)
            if invite and invite.inviter:
                inviter_mention = invite.inviter.mention
            else:
                inviter_mention = "`Unknown`"
        except Exception as e:
            inviter_mention = f"Error: {str(e)}"

        return inviter_mention

    @staticmethod
    async def get_avatar_emoji(ctx, member):
        if member.bot:
            return "🤖"  # Bot emoji
        else:
            return "👤"  # Member emoji

    @staticmethod
    def timestamp_gen(timestamp: int) -> str:
        dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
        formatted_timestamp = f"<t:{int(dt.timestamp())}:R>"
        return formatted_timestamp

    async def navigate_role_members_embed(
        self, interaction, message, role_id, page_num
    ):
        try:
            wait_message = None  # Initialize wait_message variable
            print(
                f"Navigation started for role ID: {role_id}, page number: {page_num}")
            guild = interaction.guild
            role = discord.utils.get(guild.roles, id=int(role_id))

            if role:
                wait_message = await interaction.response.send_message(
                    f"Generating embeds for page: `This might take a moment please wait.` ",
                    ephemeral=True,
                )

                embeds = await self.generate_role_members_embed(guild, role)

                if embeds:
                    print(f"Total embeds to navigate: {len(embeds)}")
                    await message.edit(embed=embeds[0])

                    if wait_message:  # Check if wait_message is not None
                        await wait_message.edit(
                            content=f"`Completed`\n```Total embeds to navigate: {len(embeds)}```"
                        )

                    if len(embeds) > 1:
                        # Create the buttons for navigation
                        prev_button = discord.ui.Button(
                            label="◀️", style=discord.ButtonStyle.primary
                        )
                        next_button = discord.ui.Button(
                            label="▶️", style=discord.ButtonStyle.primary
                        )

                        # Define the button callbacks
                        async def prev_callback(interaction: discord.Interaction):
                            nonlocal current_page
                            if current_page > 0:
                                current_page -= 1
                                await message.edit(embed=embeds[current_page])

                        async def next_callback(interaction: discord.Interaction):
                            nonlocal current_page
                            if current_page < len(embeds) - 1:
                                current_page += 1
                                await message.edit(embed=embeds[current_page])

                        # Set the button callbacks
                        prev_button.callback = prev_callback
                        next_button.callback = next_callback

                        # Create the view to hold the buttons
                        view = discord.ui.View()
                        view.add_item(prev_button)
                        view.add_item(next_button)

                        # Send the message with the buttons
                        await message.edit(
                            content="page updated", embed=embeds[0], view=view
                        )

                        current_page = 0  # Initialize current_page to 0 for navigation

                        # Ensure the message will have an interactive view
                        await message.edit(view=view)

        except Exception as e:
            await interaction.response.send_message(
                f"Error navigating through role members: {e}"
            )

    async def navigate_embed(self, ctx, message, embeds):
        guild = ctx.guild
        roles = sorted(
            guild.roles,
            key=lambda role: (len(role.members), role.color.value),
            reverse=True,
        )
        most_common_roles = [
            (role, len(role.members))
            for role in roles
            if len(role.members) >= 5 and role.name
        ]
        select_roles = most_common_roles[:25]  # Limit to 25 roles

        select_view = SelectView(
            roles=[role for role, _ in select_roles], cog=self)

        # Use self.current_page to maintain state across method calls
        await message.edit(embed=embeds[self.current_page], view=select_view)

        if len(embeds) > 1:
            # Create the view for navigation
            view = discord.ui.View()

            # Navigation buttons
            prev_button = discord.ui.Button(
                label="◀️", style=discord.ButtonStyle.primary
            )
            next_button = discord.ui.Button(
                label="▶️", style=discord.ButtonStyle.primary
            )

            # Define button callbacks
            async def prev_callback(interaction):
                await interaction.response.defer()  # Acknowledge the interaction
                if self.current_page > 0:
                    self.current_page -= 1
                    await message.edit(embed=embeds[self.current_page], view=view)

            async def next_callback(interaction):
                await interaction.response.defer()  # Acknowledge the interaction
                if self.current_page < len(embeds) - 1:
                    self.current_page += 1
                    await message.edit(embed=embeds[self.current_page], view=view)

            # Integrate SelectView
            for item in select_view.children:
                # Add each item from SelectView to the main view
                view.add_item(item)

            # Add callbacks to buttons
            prev_button.callback = prev_callback
            next_button.callback = next_callback

            # Add buttons and select view to the view
            view.add_item(prev_button)
            view.add_item(next_button)

            # Update the message with navigation controls
            await message.edit(
                content="Page updated", embed=embeds[self.current_page], view=view
            )

    async def navigate_role_members_embed(
        self, interaction, message, role_id, page_num
    ):
        try:
            wait_message = None  # Initialize wait_message variable
            print(
                f"Navigation started for role ID: {role_id}, page number: {page_num}")
            guild = interaction.guild
            role = discord.utils.get(guild.roles, id=int(role_id))

            if role:
                wait_message = await interaction.response.send_message(
                    f"Generating embeds for page: `This might take a momment please wait.` ",
                    ephemeral=True,
                )
                embeds = await self.generate_role_members_embed(guild, role)

                if embeds:
                    print(f"Total embeds to navigate: {len(embeds)}")
                    await message.edit(embed=embeds[0])
                    if wait_message:  # Check if wait_message is not None
                        await wait_message.edit(
                            content=f"`Completed`\n```Total embeds to navigate: {len(embeds)}```"
                        )

                    if len(embeds) > 1:
                        await message.add_reaction("◀️")
                        await message.add_reaction("▶️")
                        print("Reactions added for navigation")

                        def check(reaction, user):
                            return user == interaction.user and str(reaction.emoji) in [
                                "◀️",
                                "▶️",
                            ]

                        current_page = 0
                        while True:
                            try:
                                reaction, user = await self.bot.wait_for(
                                    "reaction_add", timeout=180.0, check=check
                                )
                                print(
                                    f"Reaction received: {reaction.emoji} by {user}")

                                if (
                                    str(reaction.emoji) == "▶️"
                                    and current_page < len(embeds) - 1
                                ):
                                    current_page += 1
                                    await message.edit(embed=embeds[current_page])
                                    await message.remove_reaction(reaction, user)
                                    print(
                                        f"Switched to page {current_page + 1}")
                                elif str(reaction.emoji) == "◀️" and current_page > 0:
                                    current_page -= 1
                                    await message.edit(embed=embeds[current_page])
                                    await message.remove_reaction(reaction, user)
                                    print(
                                        f"Switched to page {current_page + 1}")
                            except asyncio.TimeoutError:
                                await message.clear_reactions()
                                break
        except Exception as e:
            await interaction.response.send_message(
                f"Error navigating through role members: {e}"
            )

    async def generate_role_members_embed(self, guild, role):
        try:
            members_with_role = [
                member for member in guild.members if role in member.roles
            ]
            members_per_page = 3
            total_members = len(members_with_role)
            total_pages = (total_members + members_per_page -
                           1) // members_per_page

            embeds = []
            for i in range(0, total_members, members_per_page):
                print(
                    f"Generating embeds for page {i // members_per_page + 1}/{total_pages}"
                )

                embed = discord.Embed(title=f"{role.name}", color=role.color)
                footer_text = f"Role: {role.name}\nPage {i // members_per_page + 1} of {total_pages}"
                embed.set_footer(text=footer_text)

                row_images = []
                temp_files = []

                for member in members_with_role[i: i + members_per_page]:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            str(member.avatar.with_size(128))
                        ) as resp:
                            if resp.status != 200:
                                print(
                                    f"Failed to get avatar for {member.display_name}")
                                continue
                            data = await resp.read()

                    # Save the image to a temporary file
                    temp_file = tempfile.NamedTemporaryFile(
                        suffix=".png", delete=False)
                    temp_file.write(data)
                    temp_file.seek(0)  # Move to the beginning of the file
                    temp_files.append(temp_file.name)

                    img = Image.open(temp_file.name)
                    row_images.append(img)

                # Concatenate the images horizontally
                total_width = sum(img.width for img in row_images)
                max_height = max(img.height for img in row_images)
                concatenated_image = Image.new(
                    "RGB", (total_width, max_height))

                x_offset = 0
                for img in row_images:
                    concatenated_image.paste(img, (x_offset, 0))
                    x_offset += img.width

                # Save the concatenated image to a temporary file
                temp_concatenated_file = tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False
                )
                concatenated_image.save(
                    temp_concatenated_file.name, format="PNG")

                # Upload the image as an attachment
                with open(temp_concatenated_file.name, "rb") as image_file:
                    file = discord.File(fp=image_file, filename="avatars.png")
                    log_channel = self.bot.get_channel(1262668450900480041)
                    message = await log_channel.send(
                        file=file
                    )  # Send the file to the bot's DM
                    attachment_url = message.attachments[0].url

                embed.set_image(url=attachment_url)

                for member in members_with_role[i: i + members_per_page]:
                    emoji = await self.get_avatar_emoji(guild, member)
                    joined_timestamp = self.timestamp_gen(
                        member.joined_at.timestamp())
                    other_roles = "\n".join(
                        [
                            f"➱ {r.mention}"
                            for r in member.roles
                            if r != role and r.name != "@everyone"
                        ]
                    )

                    # Fetch invite information
                    inviter_mention = await self.get_inviter_mention(
                        member
                    )  # Fetch invite information

                    embed.add_field(
                        name=f"\n",
                        value=f"{member.mention}```js\n{emoji} {member.display_name} ({member.id})````Other Roles`\n{other_roles if len(other_roles) > 0 else '`None`'}",
                        inline=False,
                    )
                    embed.add_field(name=f" ", value=f" ", inline=False)

                embeds.append(embed)

                # Close temporary files
                for file_path in temp_files:
                    os.unlink(file_path)  # Remove temporary files

            await log_channel.send(
                f"Embed Completed with {total_pages} pages", delete_after=180
            )
            return embeds
        except discord.errors.InteractionResponded:
            pass  # Interaction already responded to

    @commands.command(name="members", hidden=True)
    async def list_members(self, ctx, *, filter_option: str = None):
        try:
            guild = ctx.guild
            roles = sorted(
                guild.roles,
                key=lambda role: (len(role.members), role.color.value),
                reverse=True,
            )
            most_common_roles = [
                (role, len(role.members))
                for role in roles
                if len(role.members) >= 5 and role.name
            ]
            select_roles = most_common_roles[:25]  # Limit to 25 roles
            select_view = SelectView(
                roles=[role for role, _ in select_roles], cog=self)

            # Fetch all members in the guild
            all_members = guild.members
            usage_guide = (
                "Usage: \n"
                ",members --filter <context>\n"
                "\n"
                "where context can be:\n"
                "• [n-w] (newest to oldest)\n"
                "• [o-n] (oldest to newest)\n"
                "• [ma-la] (most active to least active)\n"
                "• [la-ma] (least active to most active)\n"
                "• [mr-lr] (most roles to least roles)\n"
                "• [lr-mr] (least roles to most roles)\n"
                "```"
            )

            # Apply filtering if specified
            if filter_option:
                filter_option = filter_option.lower()

            if filter_option and filter_option.startswith(
                ("-filter", "-fl", "-f", "-filter", "-fl", "-f")
            ):
                if len(filter_option.split()) == 1:
                    await ctx.reply(usage_guide)
                    return
                else:
                    filter_option = filter_option.split()[1]

                    if filter_option not in [fo.value for fo in FilterOption]:
                        await ctx.reply(usage_guide)
                        return

            # Apply filtering to all members
            if filter_option == FilterOption.NEWEST_TO_OLDEST.value:
                all_members = sorted(
                    all_members, key=lambda member: member.joined_at, reverse=True
                )
                embed_title = "Server Member List (Newest to Oldest)"
            elif filter_option == FilterOption.OLDEST_TO_NEWEST.value:
                all_members = sorted(
                    all_members, key=lambda member: member.joined_at)
                embed_title = "Server Member List (Oldest to Newest)"
            elif filter_option == FilterOption.MOST_ACTIVE_TO_LEAST_ACTIVE.value:
                all_members = sorted(
                    all_members,
                    key=lambda member: (
                        member.activity if isinstance(
                            member.activity, int) else 0
                    ),
                    reverse=True,
                )
                embed_title = "Server Member List (Most Active to Least Active)"
            elif filter_option == FilterOption.LEAST_ACTIVE_TO_MOST_ACTIVE.value:
                all_members = sorted(
                    all_members, key=lambda member: member.activity or 0
                )
                embed_title = "Server Member List (Least Active to Most Active)"
            elif filter_option == FilterOption.MOST_ROLES_TO_LEAST_ROLES.value:
                all_members = sorted(
                    all_members, key=lambda member: len(member.roles), reverse=True
                )
                embed_title = "Server Member List (Most Roles to Least Roles)"
            elif filter_option == FilterOption.LEAST_ROLES_TO_MOST_ROLES.value:
                all_members = sorted(
                    all_members, key=lambda member: len(member.roles))
                embed_title = "Server Member List (Least Roles to Most Roles)"
            else:
                # Default to unfiltered list
                embed_title = "Server Member List"

            # Filter out members with invalid avatars (NoneType)
            valid_members = []
            for member in all_members:
                if member.avatar and member.avatar.with_size(128):
                    valid_members.append(member)
                else:
                    print(
                        f"Skipping {member.display_name} due to invalid avatar")

            # Split valid members into chunks of 3 for embedding
            chunked_members = [
                valid_members[i: i + 3] for i in range(0, len(valid_members), 3)
            ]

            # Create embeds for each chunk
            embeds = []
            for chunk in chunked_members:
                embed = discord.Embed(title=embed_title)
                row_images = []

                for member in chunk:
                    emoji = await self.get_avatar_emoji(ctx, member)
                    joined_timestamp = self.timestamp_gen(
                        member.joined_at.timestamp())

                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            str(member.avatar.with_size(128))
                        ) as resp:
                            if resp.status != 200:
                                print(
                                    f"Failed to get avatar for {member.display_name}")
                                continue
                            data = await resp.read()

                    # Save the image to a BytesIO object
                    temp_file = BytesIO()
                    temp_file.write(data)
                    temp_file.seek(
                        0
                    )  # Reset the position of the file cursor to the beginning of the file
                    img = Image.open(temp_file)
                    row_images.append(img)

                    # Add member information to the embed
                    embed = self.add_member_info_to_embed(
                        embed, member, emoji, joined_timestamp, filter_option
                    )

                # Concatenate the images horizontally
                total_width = sum(img.width for img in row_images)
                max_height = max(img.height for img in row_images)
                concatenated_image = Image.new(
                    "RGB", (total_width, max_height))

                x_offset = 0
                for img in row_images:
                    concatenated_image.paste(img, (x_offset, 0))
                    x_offset += img.width

                # Save the concatenated image to a BytesIO object
                temp_file = BytesIO()
                concatenated_image.save(temp_file, format="PNG")
                temp_file.seek(
                    0
                )  # Reset the position of the file cursor to the beginning of the file

                # Upload the image as an attachment
                file = discord.File(temp_file, filename="avatars.png")
                # Send the file as an attachment
                message = await ctx.send(file=file, delete_after=1)
                # Get the attachment URL
                attachment_url = message.attachments[0].url
                embed.set_image(url=attachment_url)
                embeds.append(embed)

            # Send the first embed
            message = await ctx.send(embed=embeds[0], view=select_view)

            # Add navigation reactions if needed
            if len(embeds) > 1:
                await self.navigate_embed(ctx, message, embeds)

        except Exception as e:
            # Log the traceback and send an error message to the user
            error_message = (
                f"Error listing members: {str(e)}\n```{traceback.format_exc()}```"
            )
            await ctx.send(error_message)
            print(f"Error encountered: {traceback.format_exc()}")

    @staticmethod
    def get_usage_guide():
        return (
            "Usage: \n"
            ",members --filter <context>\n"
            "\n"
            "where context can be:\n"
            "• [n-w] (newest to oldest)\n"
            "• [o-n] (oldest to newest)\n"
            "• [ma-la] (most active to least active)\n"
            "• [la-ma] (least active to most active)\n"
            "• [mr-lr] (most roles to least roles)\n"
            "• [lr-mr] (least roles to most roles)\n"
            "```"
        )

    @staticmethod
    def apply_filter(all_members, filter_option):
        if filter_option == FilterOption.NEWEST_TO_OLDEST.value:
            all_members = sorted(
                all_members, key=lambda member: member.joined_at, reverse=True
            )
            return "Server Member List (Newest to Oldest)", all_members
        elif filter_option == FilterOption.OLDEST_TO_NEWEST.value:
            all_members = sorted(
                all_members, key=lambda member: member.joined_at)
            return "Server Member List (Oldest to Newest)", all_members
        elif filter_option == FilterOption.MOST_ACTIVE_TO_LEAST_ACTIVE.value:
            all_members = sorted(
                all_members,
                key=lambda member: (
                    member.activity if isinstance(member.activity, int) else 0
                ),
                reverse=True,
            )
            return "Server Member List (Most Active to Least Active)", all_members
        elif filter_option == FilterOption.LEAST_ACTIVE_TO_MOST_ACTIVE.value:
            all_members = sorted(
                all_members, key=lambda member: member.activity or 0)
            return "Server Member List (Least Active to Most Active)", all_members
        elif filter_option == FilterOption.MOST_ROLES_TO_LEAST_ROLES.value:
            all_members = sorted(
                all_members, key=lambda member: len(member.roles), reverse=True
            )
            return "Server Member List (Most Roles to Least Roles)", all_members
        elif filter_option == FilterOption.LEAST_ROLES_TO_MOST_ROLES.value:
            all_members = sorted(
                all_members, key=lambda member: len(member.roles))
            return "Server Member List (Least Roles to Most Roles)", all_members
        else:
            return "Server Member List", all_members

    async def create_member_embeds(
        self, chunked_members, ctx, embed_title, filter_option
    ):
        embeds = []
        for chunk in chunked_members:
            embed = discord.Embed(title=embed_title)
            row_images = []

            for member in chunk:
                if not hasattr(
                    member.avatar, "with_size"
                ):  # Check for NoneType attribute
                    continue

                emoji = await self.get_avatar_emoji(ctx, member)
                joined_timestamp = self.timestamp_gen(
                    member.joined_at.timestamp())
                data = await self.fetch_avatar_data(member)

                if data:
                    row_images.append(data)

                # Add member information to the embed
                embed = await self.add_member_info_to_embed(
                    embed, member, emoji, joined_timestamp, filter_option
                )

            concatenated_image = self.concatenate_images(row_images)
            file = discord.File(concatenated_image, filename="avatars.png")
            message = await ctx.send(file=file, delete_after=1)

            embed.set_image(url=message.attachments[0].url)
            embeds.append(embed)

        return embeds

    @staticmethod
    async def fetch_avatar_data(member):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(member.avatar.with_size(128))) as resp:
                    if resp.status != 200:
                        print(
                            f"Failed to get avatar for {member.display_name}")
                        return None
                    return await resp.read()
        except Exception as e:
            print(f"Error fetching avatar for {member.display_name}: {e}")
            return None

    @staticmethod
    def concatenate_images(row_images):
        total_width = sum(img.width for img in row_images)
        max_height = max(img.height for img in row_images)
        concatenated_image = Image.new("RGB", (total_width, max_height))

        x_offset = 0
        for img in row_images:
            concatenated_image.paste(img, (x_offset, 0))
            x_offset += img.width

        temp_file = BytesIO()
        concatenated_image.save(temp_file, format="PNG")
        temp_file.seek(0)  # Reset the position of the file cursor
        return temp_file

    @staticmethod
    def add_member_info_to_embed(
        embed, member, emoji, joined_timestamp, filter_option
    ):
        # Add the member's display name and roles to the embed
        embed.add_field(
            name=f"",
            value=f"{emoji} {member.mention}\n"
            f"- Roles: {', '.join([role.mention for role in member.roles[1:]]) or 'No roles'}\n"
            f"- Joined: {joined_timestamp}",
            inline=False,
        )

        # Optionally add extra information depending on the filter_option
        if filter_option == FilterOption.MOST_ACTIVE_TO_LEAST_ACTIVE.value:
            # Add activity status if available
            activity = member.activity.name if member.activity else "No activity"
            embed.add_field(
                name=f"{emoji} {member.display_name} Activity",
                value=f"Activity: {activity}",
                inline=False,
            )
        elif filter_option == FilterOption.MOST_ROLES_TO_LEAST_ROLES.value:
            # Display the number of roles if sorted by roles
            embed.add_field(
                name=f"{emoji} {member.display_name} Roles",
                value=f"Role count: {len(member.roles) - 1}",
                inline=False,
            )

        return embed

    @commands.command(help="Go ahead and take a little break from the keyboard.")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def afk(self, ctx, *, msg: str = None):
        await ctx.message.delete()
        if msg is None:
            msg = "[ AFK ] "

        # Add user ID and reason to AFK data
        self.data[ctx.author.id] = msg
        self.save_data()

        await ctx.send(f"{ctx.author.mention} I set your AFK: {msg}")
        nickname = f"[AFK] {ctx.author.display_name}"
        await ctx.author.edit(nick=nickname)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Load AFK data from the file

        if not message.author.bot:
            author_id_str = str(message.author.id)

            if author_id_str in self.data:
                # Send a welcome back message
                await message.channel.send(
                    f"Welcome back {message.author.mention}, I removed your AFK!",
                    delete_after=35,
                )

                # Remove the user from the AFK JSON file
                del self.data[author_id_str]
                self.save_data()

                # Remove AFK nickname and save data
                await message.author.edit(nick=None)

            # Check for other mentions in the message
            for user_id, afk_reason in dict(self.data).items():
                if f"<@{user_id}>" in message.content:
                    await message.channel.send(
                        f"<@{user_id}> is currently AFK, reason: {afk_reason}",
                        delete_after=35,
                    )

    @commands.command(
        name="lock", help="Lock channels (Role required: Lock)", hidden=True
    )
    @commands.has_role("Lock")
    async def lock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        incense = "incense"

        if (
            incense in channel.name
            or ctx.author.id == 1030285330739363880
            or ctx.author.guild_permissions.manage_channels
        ):
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            await ctx.send(
                f"{ctx.author.mention} has locked {channel.mention}, {channel.mention} is now :lock: "
            )
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        else:
            await ctx.send(
                f"{ctx.author.name}, I am sorry but you don't have the permission to lock {channel.mention}. ||Missing Permission: [manage_channels]||. Try locking channels called incense for now."
            )

    @commands.command(
        name="unlock", help="Unlock channels (Role required: Lock)", hidden=True
    )
    @commands.has_role("Lock")
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await ctx.send(
            f"{ctx.author.mention} has unlocked {channel.mention}, {channel.mention} is now :unlock:"
        )
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

    @lock.error
    async def lock_error(self, ctx, error):
        if isinstance(error, (commands.MissingRole, commands.MissingAnyRole)):
            text = "Sorry {}, you don't have the correct role to lock channels. || Role required = Role Name: 'Lock' || ".format(
                ctx.message.author
            )


def setup(bot):
    bot.add_cog(Guide(bot))
