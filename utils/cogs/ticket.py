import os, json,traceback, random
from bson import ObjectId
from imports.discord_imports import *
from motor.motor_asyncio import AsyncIOMotorClient

mongo_url = os.getenv("MONGO_URI")
cluster = AsyncIOMotorClient(mongo_url)
db = cluster["Commands"]
server_collection = db["ticket"]

class TicketSystem:
    def __init__(self, bot, mongo_uri=None, db_name="Commands", collection_name="ticket"):
        self.bot = bot
        mongo_uri = mongo_uri or os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI not provided or set in environment variables.")
        
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    # Database Operations
    async def save_ticket(self, guild_id, message_id, channel_id, embed_data, button_data, 
                         thread_message, close_button_data, ticket_name, user_id=None, thread_id=None):
        message_link = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
        ticket = {
            "guild_id": guild_id,
            "message_id": message_id,
            "channel_id": channel_id,
            "embed": embed_data,
            "button_data": button_data,
            "thread_message": thread_message,
            "close_button_data": close_button_data,
            "ticket_name": ticket_name,
            "message_link": message_link,
            "status": "open"  # Mark ticket as open when created
        }
        if user_id is not None:
            ticket["user_id"] = user_id
        if thread_id is not None:
            ticket["thread_id"] = thread_id
        return await self.collection.insert_one(ticket)

    async def update_ticket(self, message_id, embed_data, button_data, thread_message, 
                           close_button_data, ticket_name):
        return await self.collection.update_one(
            {"message_id": message_id},
            {"$set": {
                "embed": embed_data,
                "button_data": button_data,
                "thread_message": thread_message,
                "close_button_data": close_button_data,
                "ticket_name": ticket_name
            }}
        )

    async def get_ticket_by_message_id(self, message_id):
        return await self.collection.find_one({"message_id": message_id})

    async def get_all_tickets(self, guild_id=None):
        query = {"guild_id": guild_id} if guild_id else {}
        return await self.collection.find(query).to_list(length=None)

    async def delete_ticket(self, ticket_id):
        return await self.collection.delete_one({"_id": ObjectId(ticket_id)})

    # Check if a user has an open ticket in the guild
    async def user_has_open_ticket(self, guild_id, user_id):
        ticket = await self.collection.find_one({
            "guild_id": guild_id,
            "user_id": user_id,
            "status": "open"
        })
        return ticket is not None

    # UI Components
    def create_ticket_button(self, ticket_data):
        class TicketButton(discord.ui.Button):
            def __init__(self, parent_system, ticket_data):
                button_data = ticket_data.get("button_data", {})
                super().__init__(
                    label=button_data.get("label", "Open Ticket"),
                    emoji=button_data.get("emoji", "🎫"),
                    style=discord.ButtonStyle.green,
                    custom_id=f"ticket_{ticket_data['guild_id']}_{ticket_data['channel_id']}"
                )
                self.parent_system = parent_system
                self.ticket_data = ticket_data

            async def callback(self, interaction: discord.Interaction):
                await self.parent_system.handle_ticket_creation(interaction, self.ticket_data)

        return TicketButton(self, ticket_data)

    def create_close_ticket_view(self, thread_id, close_button_data):
        class CloseTicketView(discord.ui.View):
            def __init__(self, parent_system, thread_id, close_button_data):
                super().__init__(timeout=None)
                self.parent_system = parent_system
                self.thread_id = thread_id
                
                close_btn = discord.ui.Button(
                    label=close_button_data.get("label", "Close Thread"),
                    emoji=close_button_data.get("emoji", "🔒"),
                    style=discord.ButtonStyle.red,
                    custom_id=f"close_{thread_id}"
                )
                close_btn.callback = self.close_callback
                self.add_item(close_btn)

            async def close_callback(self, interaction: discord.Interaction):
                await self.parent_system.handle_ticket_close(interaction, self.thread_id)

        return CloseTicketView(self, thread_id, close_button_data)

    def create_setup_modal(self, channel, existing_data=None):
        class TicketSetupModal(discord.ui.Modal):
            def __init__(self, parent_system, channel, existing_data=None):
                super().__init__(title="Ticket System Setup")
                self.parent_system = parent_system
                self.channel = channel
                self.existing_data = existing_data or {}
                
                embed_data = self.existing_data.get("embed", {})
                button_data = self.existing_data.get("button_data", {})
                
                self.add_item(discord.ui.TextInput(
                    label="Ticket Name",
                    placeholder="My Support Ticket",
                    default=self.existing_data.get("ticket_name", ""),
                    required=True
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Title",
                    placeholder="Support Ticket",
                    default=embed_data.get("title", ""),
                    required=False
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Description",
                    placeholder="Click below to open a support ticket",
                    default=embed_data.get("description", ""),
                    style=discord.TextStyle.paragraph,
                    required=True
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Button Label",
                    placeholder="Open Ticket",
                    default=button_data.get("label", ""),
                    required=False
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Thread Welcome Message",
                    placeholder="Welcome! A staff member will help you soon.",
                    default=self.existing_data.get("thread_message", ""),
                    style=discord.TextStyle.paragraph,
                    required=False
                ))

            async def on_submit(self, interaction: discord.Interaction):
                await self.parent_system.handle_setup_submission(interaction, self)

        return TicketSetupModal(self, channel, existing_data)

    def create_image_modal(self, ticket_data, setup_modal):
        class ImageSetupModal(discord.ui.Modal):
            def __init__(self, parent_system, ticket_data, setup_modal):
                super().__init__(title="Embed Image Settings")
                self.parent_system = parent_system
                self.ticket_data = ticket_data
                self.setup_modal = setup_modal
                
                embed_data = ticket_data.get("embed", {})
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Image URL",
                    placeholder="https://example.com/image.png",
                    default=embed_data.get("image", {}).get("url", ""),
                    required=False
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Thumbnail URL",
                    placeholder="https://example.com/thumbnail.png",
                    default=embed_data.get("thumbnail", {}).get("url", ""),
                    required=False
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Color (Hex)",
                    placeholder="2ecc71 (without #)",
                    default=hex(embed_data.get("color", 0x2ecc71))[2:],
                    required=False
                ))

            async def on_submit(self, interaction: discord.Interaction):
                await self.parent_system.handle_image_setup(interaction, self)

        return ImageSetupModal(self, ticket_data, setup_modal)

    def create_management_view(self, tickets, author_id, action_type="activate"):
        class TicketManagementView(discord.ui.View):
            def __init__(self, parent_system, tickets, author_id, action_type="activate"):
                super().__init__(timeout=300)
                self.parent_system = parent_system
                self.tickets = tickets
                self.author_id = author_id
                self.action_type = action_type
                
                options = [
                    discord.SelectOption(
                        label=ticket.get('ticket_name', 'Unnamed Ticket')[:100],
                        description=f"Channel: #{ticket.get('channel_id')}",
                        value=str(ticket.get('_id'))
                    ) for ticket in tickets[:25]
                ]
                
                self.select = discord.ui.Select(
                    placeholder=f"Select a ticket to {action_type}",
                    options=options
                )
                self.select.callback = self.select_callback
                self.add_item(self.select)

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user.id != self.author_id:
                    await interaction.response.send_message("You can't use this menu.", ephemeral=True)
                    return False
                return True

            async def select_callback(self, interaction: discord.Interaction):
                ticket_id = self.select.values[0]
                selected_ticket = next((t for t in self.tickets if str(t.get('_id')) == ticket_id), None)
                
                if not selected_ticket:
                    return await interaction.response.send_message("Ticket not found.", ephemeral=True)

                if self.action_type == "activate":
                    await self.parent_system.activate_ticket(interaction, selected_ticket)
                elif self.action_type == "delete":
                    await self.parent_system.delete_ticket_with_confirmation(interaction, selected_ticket, ticket_id, self.author_id)

        return TicketManagementView(self, tickets, author_id, action_type)

    # Event Handlers
    async def handle_ticket_creation(self, interaction, ticket_data):
        try:
            # Check if user already has an open ticket
            if await self.user_has_open_ticket(interaction.guild.id, interaction.user.id):
                await interaction.response.send_message(
                    "❌ You already have an open ticket! Please close it before opening a new one.",
                    ephemeral=True
                )
                return

            # Create private thread for ticket
            thread = await interaction.channel.create_thread(
                name=f"Ticket-{interaction.user.name}",
                type=discord.ChannelType.private_thread
            )

            # Get admin mentions
            owner = interaction.guild.owner
            admins = [m for m in interaction.guild.members 
                     if m.guild_permissions.administrator and not m.bot and m != owner]
            online_admins = [m for m in admins if m.status != discord.Status.offline]
        
            selected_admins = [owner] + random.sample(
                online_admins or admins, min(2, len(online_admins or admins))
            )

            # Send messages to thread
            embed = discord.Embed.from_dict(ticket_data["embed"])
            await thread.send(f"<@{interaction.user.id}>", embed=embed)
            
            if selected_admins:
                mentions = ' '.join(m.mention for m in selected_admins)
                await thread.send(f"> Team members assisting: {mentions}")

            # Add close button
            close_view = self.create_close_ticket_view(thread.id, ticket_data.get("close_button_data", {}))
            await thread.send(ticket_data.get("thread_message", "Welcome! A staff member will help you soon."), view=close_view)
            
            # Save ticket info including user_id and thread_id with status "open"
            await self.save_ticket(
                guild_id=interaction.guild.id,
                message_id=interaction.message.id,
                channel_id=interaction.channel.id,
                embed_data=ticket_data["embed"],
                button_data=ticket_data["button_data"],
                thread_message=ticket_data["thread_message"],
                close_button_data=ticket_data["close_button_data"],
                ticket_name=ticket_data["ticket_name"],
                user_id=interaction.user.id,
                thread_id=thread.id
            )
            
            await interaction.response.send_message(f"✅ Ticket created: {thread.mention}", ephemeral=True)
        except Exception as e:
            print(f"❌ Error creating ticket: {e}")
            try:
                await interaction.response.send_message("❌ Failed to create ticket.", ephemeral=True)
            except:
                pass

    async def handle_ticket_close(self, interaction, thread_id):
        try:
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(
                    "Only administrators can close tickets.", ephemeral=True
                )
            
            thread = interaction.guild.get_thread(thread_id)
            if thread:
                await thread.edit(locked=True, archived=True)
            
            # Update ticket status in DB to "closed"
            await self.collection.update_one(
                {"thread_id": thread_id},
                {"$set": {"status": "closed"}}
            )
            
            await interaction.response.send_message("Thread closed.", ephemeral=True)
        except Exception as e:
            print(f"❌ Error closing ticket {thread_id}: {e}")
            try:
                await interaction.response.send_message("❌ Failed to close ticket.", ephemeral=True)
            except:
                pass

    async def handle_setup_submission(self, interaction, modal):
        try:
            await interaction.response.defer(ephemeral=True)
            
            ticket_data = {
                "guild_id": interaction.guild.id,
                "channel_id": modal.channel.id,
                "ticket_name": modal.children[0].value,
                "embed": {
                    "title": modal.children[1].value or "Support Ticket",
                    "description": modal.children[2].value,
                    "color": 0x2ecc71
                },
                "button_data": {
                    "label": modal.children[3].value or "Open Ticket",
                    "emoji": "🎫"
                },
                "close_button_data": {
                    "label": "Close Thread",
                    "emoji": "🔒"
                },
                "thread_message": modal.children[4].value or "Welcome! A staff member will help you soon."
            }
            
            image_modal = self.create_image_modal(ticket_data, modal)
            view = discord.ui.View(timeout=300)
            
            async def show_image_modal(img_interaction):
                try:
                    if img_interaction.user.id == interaction.user.id:
                        await img_interaction.response.send_modal(image_modal)
                    else:
                        await img_interaction.response.send_message("Not your button!", ephemeral=True)
                except Exception as e:
                    print(f"❌ Error showing image modal: {e}")
                    try:
                        await img_interaction.response.send_message("❌ Failed to show image modal.", ephemeral=True)
                    except:
                        pass
            
            async def skip_images(skip_interaction):
                try:
                    if skip_interaction.user.id == interaction.user.id:
                        await self.finalize_ticket_setup(skip_interaction, ticket_data, modal.existing_data, modal.channel)
                    else:
                        await skip_interaction.response.send_message("Not your button!", ephemeral=True)
                except Exception as e:
                    print(f"❌ Error in skip images: {e}")
                    try:
                        await skip_interaction.response.send_message("❌ Failed to skip images.", ephemeral=True)
                    except:
                        pass
            
            image_btn = discord.ui.Button(label="Set Images", style=discord.ButtonStyle.secondary)
            skip_btn = discord.ui.Button(label="Skip Images", style=discord.ButtonStyle.primary)
            image_btn.callback = show_image_modal
            skip_btn.callback = skip_images
            view.add_item(image_btn)
            view.add_item(skip_btn)
            
            image_modal.ticket_data = ticket_data
            
            await interaction.followup.send("Configure embed images or skip:", view=view, ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            traceback.print_exception(type(e), e, e.__traceback__)

    async def handle_image_setup(self, interaction, modal):
        try:
            await interaction.response.defer(ephemeral=True)
            
            ticket_data = modal.ticket_data
            
            image_url = modal.children[0].value.strip()
            thumbnail_url = modal.children[1].value.strip()
            color_hex = modal.children[2].value.strip()
            
            if image_url:
                ticket_data["embed"]["image"] = {"url": image_url}
            
            if thumbnail_url:
                ticket_data["embed"]["thumbnail"] = {"url": thumbnail_url}
            
            if color_hex:
                try:
                    color_int = int(color_hex, 16)
                    ticket_data["embed"]["color"] = color_int
                except ValueError:
                    pass
            
            await self.finalize_ticket_setup(interaction, ticket_data, modal.setup_modal.existing_data, modal.setup_modal.channel)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            traceback.print_exception(type(e), e, e.__traceback__)

    async def finalize_ticket_setup(self, interaction, ticket_data, existing_data, channel):
        try:
            embed = discord.Embed.from_dict(ticket_data["embed"])
            view = discord.ui.View(timeout=None)
            view.add_item(self.create_ticket_button(ticket_data))
            
            if existing_data:
                message_id = existing_data["message_id"]
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed, view=view)
                await self.update_ticket(
                    message_id, ticket_data["embed"], ticket_data["button_data"],
                    ticket_data["thread_message"], ticket_data["close_button_data"],
                    ticket_data["ticket_name"]
                )
                if hasattr(interaction, 'edit_original_response'):
                    await interaction.edit_original_response(content="✅ Ticket system updated!", view=None)
                else:
                    await interaction.followup.send("✅ Ticket system updated!", ephemeral=True)
            else:
                message = await channel.send(embed=embed, view=view)
                ticket_data["message_id"] = message.id
                await self.save_ticket(**ticket_data)
                if hasattr(interaction, 'edit_original_response'):
                    await interaction.edit_original_response(content="✅ Ticket system created!", view=None)
                else:
                    await interaction.followup.send("✅ Ticket system created!", ephemeral=True)
                
        except Exception as e:
            if hasattr(interaction, 'edit_original_response'):
                await interaction.edit_original_response(content=f"❌ Error: {str(e)}", view=None)
            else:
                await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
            traceback.print_exception(type(e), e, e.__traceback__)

    async def activate_ticket(self, interaction, ticket_data):
        try:
            channel = interaction.guild.get_channel(ticket_data["channel_id"])
            if not channel:
                return await interaction.response.send_message("Channel not found!", ephemeral=True)
            
            embed = discord.Embed.from_dict(ticket_data["embed"])
            view = discord.ui.View(timeout=None)
            view.add_item(self.create_ticket_button(ticket_data))
            
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(
                f"✅ Ticket '{ticket_data['ticket_name']}' activated in <#{channel.id}>!", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    async def delete_ticket_with_confirmation(self, interaction, ticket_data, ticket_id, author_id):
        confirm_view = discord.ui.View(timeout=60)
        
        async def confirm_delete(confirm_interaction):
            if confirm_interaction.user.id != author_id:
                return await confirm_interaction.response.send_message("Not your button!", ephemeral=True)
            
            try:
                await self.delete_ticket(ticket_id)
                
                try:
                    channel = interaction.guild.get_channel(ticket_data["channel_id"])
                    if channel and ticket_data.get("message_id"):
                        msg = await channel.fetch_message(ticket_data["message_id"])
                        await msg.delete()
                except:
                    pass
                
                await confirm_interaction.response.edit_message(
                    content=f"✅ Ticket '{ticket_data['ticket_name']}' deleted!",
                    embed=None, view=None
                )
            except Exception as e:
                await confirm_interaction.response.edit_message(
                    content=f"❌ Error deleting: {str(e)}", embed=None, view=None
                )
        
        async def cancel_delete(cancel_interaction):
            if cancel_interaction.user.id != author_id:
                return await cancel_interaction.response.send_message("Not your button!", ephemeral=True)
            await cancel_interaction.response.edit_message(
                content="❌ Deletion cancelled.", embed=None, view=None
            )
        
        yes_btn = discord.ui.Button(label="Yes, Delete", style=discord.ButtonStyle.red)
        no_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.grey)
        yes_btn.callback = confirm_delete
        no_btn.callback = cancel_delete
        confirm_view.add_item(yes_btn)
        confirm_view.add_item(no_btn)
        
        embed = discord.Embed(
            title="⚠️ Confirm Deletion",
            description=f"Delete ticket '{ticket_data['ticket_name']}'?\nThis cannot be undone.",
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

    # Utility Methods
    def has_manage_role_or_perms(self, member):
        if any(role.name == "Anya Manager" for role in member.roles):
            return True
        return member.guild_permissions.manage_guild or member.guild_permissions.manage_channels

    # Command Methods
    async def setup_ticket_command(self, ctx, channel):
        modal = self.create_setup_modal(channel)
        view = discord.ui.View()
        
        setup_btn = discord.ui.Button(label="Setup Ticket", style=discord.ButtonStyle.primary)
        
        async def on_click(interaction):
            if interaction.user.id == ctx.author.id:
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message("Not your button!", ephemeral=True)
        
        setup_btn.callback = on_click
        view.add_item(setup_btn)
        
        await ctx.send("Click to setup ticket system:", view=view)

    async def edit_ticket_command(self, ctx, message_ref):
        if "discord.com/channels/" in message_ref:
            try:
                message_id = int(message_ref.strip().split("/")[-1])
            except ValueError:
                return await ctx.send("❌ Invalid message link.")
        else:
            if not message_ref.isdigit():
                return await ctx.send("❌ Provide a valid message ID or link.")
            message_id = int(message_ref)

        ticket_data = await self.get_ticket_by_message_id(message_id)

        if not ticket_data:
            return await ctx.send("❌ No ticket system found for this message.")

        channel = ctx.guild.get_channel(ticket_data["channel_id"])
        if not channel:
            return await ctx.send("❌ Original channel not found.")

        modal = self.create_setup_modal(channel, ticket_data)
        view = discord.ui.View()
        edit_btn = discord.ui.Button(label="Edit Ticket", style=discord.ButtonStyle.secondary)

        async def on_click(interaction):
            if interaction.user.id == ctx.author.id:
                await interaction.response.send_modal(modal)
            else:
                await interaction.response.send_message("Not your button!", ephemeral=True)

        edit_btn.callback = on_click
        view.add_item(edit_btn)

        await ctx.send("Click to edit ticket system:", view=view)

    async def manage_tickets_command(self, ctx, action="activate"):
        tickets = await self.get_all_tickets(ctx.guild.id)
        
        if not tickets:
            return await ctx.send("❌ No tickets found.")
        
        view = self.create_management_view(tickets, ctx.author.id, action)
        action_word = "activate" if action == "activate" else "delete"
        await ctx.send(f"Select a ticket to {action_word}:", view=view)

    async def ticket_command(self, ctx, action, param=None):
        if not self.has_manage_role_or_perms(ctx.author):
            return await ctx.reply(embed=discord.Embed(
                title="⛔ Missing Permissions",
                description=(
                    "```You need one of the following to use this command:```\n"
                    "• A role named `Anya Manager`\n• `Manage Server` or `Manage Channels` permission"
                ),
                color=discord.Color.red()
            ).set_footer(text="Permission Check Failed"), mention_author=False ,delete_after=15)

        try:
            if action == "create":
                if not param or not (param.startswith('<#') and param.endswith('>') or param.isdigit()):
                    return await ctx.send("❌ Provide a valid channel mention or ID.\nExample: `!ticket create #support`")
                
                channel_id = int(param[2:-1]) if param.startswith('<#') else int(param)
                channel = ctx.guild.get_channel(channel_id)
                
                if not isinstance(channel, discord.TextChannel):
                    return await ctx.send("❌ Channel not found or is not a text channel.")
                
                await self.setup_ticket_command(ctx, channel)

            elif action in {"activate", "delete"}:
                await self.manage_tickets_command(ctx, action)

            elif action == "edit":
                if not param or "discord.com/channels/" not in param:
                    return await ctx.send("❌ Provide a valid message link.\nExample: `!ticket edit https://discord.com/channels/123/456/789`")
                
                await self.edit_ticket_command(ctx, param)

        except Exception as e:
            await ctx.send(f"❌ An error occurred: {e}")
            traceback.print_exception(type(e), e, e.__traceback__)

class Invalidation:
    @staticmethod
    def usage_ticket(prefix):
        return (
            f"Usage:\n"
            f"`{prefix}ticket create <#channel>` - Start a ticket system in the specified channel\n"
            f"`{prefix}ticket activate` - Activate an existing ticket configuration\n"
            f"`{prefix}ticket delete` - Delete an existing ticket configuration\n"
            f"`{prefix}ticket edit <message_link>` - Update an existing ticket embed message"
        )

    @staticmethod
    def missing_channel(prefix):
        return f"Missing channel. Usage: `{prefix}ticket create <#channel>`"

    @staticmethod
    def invalid_channel():
        return "Channel not found. Please mention a valid text channel."

    @staticmethod
    def missing_link(prefix):
        return f"Missing message link. Usage: `{prefix}ticket edit <message_link>`"

    @staticmethod
    def invalid_link():
        return "Invalid message link."

    @staticmethod
    def prompt_method():
        return "Submit a full embed JSON or fill out the example fields? Type `json` or `prompt`."

    @staticmethod
    def prompt_json():
        return "Send the raw JSON for the embed."

    @staticmethod
    def invalid_json():
        return "Invalid JSON format."

    @staticmethod
    def timeout():
        return "No response received. Operation cancelled."

    @staticmethod
    def json_timeout():
        return "No JSON received. Operation cancelled."

    @staticmethod
    def update_success():
        return "Ticket message updated."

    @staticmethod
    def form_prompt():
        return "Fill out the embed form."

async def setup_persistent_views(bot):
    try:
        mongo_url = os.getenv("MONGO_URI") or "mongodb://localhost:27017/"
        ticket_system = TicketSystem(bot, mongo_url)
        await ticket_system.client.admin.command('ping')
        tickets = await ticket_system.get_all_tickets()

        success_count = error_count = thread_button_count = 0
        named = [t for t in tickets if t.get("ticket_name")]
        unnamed = [t for t in tickets if not t.get("ticket_name")]

        for ticket in named + unnamed:
            try:
                guild_id = ticket.get("guild_id")
                channel_id = ticket.get("channel_id")
                message_id = ticket.get("message_id")
                embed_data = ticket.get("embed", {})
                button_data = ticket.get("button_data", {})
                thread_message = ticket.get("thread_message", "Welcome to your ticket!")
                close_button_data = ticket.get("close_button_data", {})
                message_link = ticket.get("message_link", "")
                ticket_name = ticket.get("ticket_name") or f"Ticket-{guild_id}-{channel_id}"

                if not ticket.get("ticket_name"):
                    try:
                        await ticket_system.collection.update_one(
                            {"_id": ticket.get("_id")},
                            {"$set": {"ticket_name": ticket_name}}
                        )
                    except Exception as e:
                        print(f"❌ Failed to name ticket: {e}")

                view = discord.ui.View(timeout=None)
                view.add_item(ticket_system.create_ticket_button(ticket))
                message_found = False

                if message_link and "/channels/" in message_link:
                    try:
                        parts = message_link.split("/")
                        g_id, c_id, m_id = map(int, parts[-3:])
                        guild = bot.get_guild(g_id)
                        channel = guild.get_channel(c_id) or bot.get_thread(c_id) if guild else None
                        if channel:
                            bot.add_view(view, message_id=m_id)
                            message_found = True
                            success_count += 1
                    except Exception as e:
                        print(f"❌ Message link error [{ticket_name}]: {e}")

                if not message_found:
                    try:
                        guild = bot.get_guild(guild_id)
                        channel = guild.get_channel(channel_id) or bot.get_thread(channel_id) if guild else None
                        if channel:
                            bot.add_view(view, message_id=message_id)
                            message_found = True
                            success_count += 1
                    except Exception as e:
                        print(f"❌ Direct view error [{ticket_name}]: {e}")

                if not message_found:
                    error_count += 1
                    print(f"❌ Could not register view [{ticket_name}]")

                if message_found:
                    try:
                        guild = bot.get_guild(guild_id)
                        if guild:
                            for channel in guild.channels:
                                if isinstance(channel, discord.TextChannel):
                                    try:
                                        for thread in channel.threads:
                                            view = ticket_system.create_close_ticket_view(thread.id, close_button_data)
                                            bot.add_view(view, message_id=None)
                                            thread_button_count += 1
                                    except Exception as e:
                                        print(f"❌ Thread error [{channel.id}]: {e}")

                                    # Skip archived threads cleanup to avoid rate limits
                                    # Archived threads will be cleaned up when accessed or through manual cleanup
                    except Exception as e:
                        print(f"❌ Thread register error [{ticket_name}]: {e}")
            except Exception as e:
                error_count += 1
                print(f"❌ Ticket error [{ticket.get('_id', 'unknown')}]: {e}")

        bot.ticket_system = ticket_system
    except Exception as e:
        print(f"❌ Setup error: {e}")
        try:
            class GenericTicketView(discord.ui.View):
                def __init__(self): super().__init__(timeout=None)
            bot.add_view(GenericTicketView())
        except Exception as e:
            print(f"❌ Fallback view error: {e}")









