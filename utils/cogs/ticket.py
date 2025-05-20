import os
import json
import traceback
from imports.discord_imports import *
from motor.motor_asyncio import AsyncIOMotorClient

mongo_url = os.getenv("MONGO_URI")
cluster = AsyncIOMotorClient(mongo_url)
db = cluster["Commands"]
server_collection = db["ticket"]

class Ticket_Dataset:
    def __init__(self, mongo_uri=None, db_name="Commands", collection_name="ticket"):
        mongo_uri = mongo_uri or os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI not provided or set in environment variables.")
        
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    async def save_message(self, ctx, msg, embed, button_data, thread_msg, close_button_data, ticket_name):
        message_link = f"https://discord.com/channels/{ctx.guild.id}/{msg.channel.id}/{msg.id}"
        await self.collection.insert_one({
            "guild_id": ctx.guild.id,
            "message_id": msg.id,
            "channel_id": msg.channel.id,
            "embed": embed.to_dict(),
            "button_data": button_data,
            "thread_message": thread_msg,
            "close_button_data": close_button_data,
            "ticket_name": ticket_name,
            "message_link": message_link
        })

    async def update_message(self, ctx, msg, embed, ticket_name=None):
        update_data = {"embed": embed.to_dict()}
        if ticket_name:
            update_data["ticket_name"] = ticket_name
        await self.collection.update_one(
            {"guild_id": ctx.guild.id, "message_id": msg.id},
            {"$set": update_data}
        )

    async def get_message_from_link(self, ctx, message_link):
        try:
            parts = message_link.split("/")
            channel_id = int(parts[-2])
            msg_id = int(parts[-1])
            channel = ctx.guild.get_channel(channel_id)
            return await channel.fetch_message(msg_id)
        except Exception:
            return None

    def load_embed(self, raw_json):
        try:
            data = json.loads(raw_json)
            return discord.Embed.from_dict(data)
        except Exception:
            return None

    async def load_all_tickets(self):
        return await self.collection.find().to_list(length=None)

    async def delete_ticket(self, ticket_id):
        return await self.collection.delete_one({"_id": ticket_id})

    async def get_ticket_by_id(self, ticket_id):
        return await self.collection.find_one({"_id": ticket_id})


        
class Ticket_View:
    class TicketButton(discord.ui.Button):
        def __init__(self, button_data, thread_message, embed_data, guild_id, channel_id, close_button_data):
            super().__init__(
                label=button_data.get("label", "Open Ticket"),
                emoji=button_data.get("emoji", None),
                style=discord.ButtonStyle.green,
                custom_id=f"ticket_open_{guild_id}_{channel_id}"
            )
            self.thread_message = thread_message
            self.embed_data = embed_data
            self.guild_id = guild_id
            self.channel_id = channel_id
            self.close_button_data = close_button_data

        async def callback(self, interaction: discord.Interaction):
            thread = await interaction.channel.create_thread(
                name=f"Ticket-{interaction.user.name}", 
                type=discord.ChannelType.private_thread
            )
            await thread.send(
                f"<@{interaction.user.id}>", 
                embed=discord.Embed.from_dict(self.embed_data)
            )
            await thread.send(
                self.thread_message, 
                view=Ticket_View.CloseButton(thread.id, self.close_button_data)
            )
            await interaction.response.send_message("Thread created!", ephemeral=True)

    class CloseButton(discord.ui.View):
        def __init__(self, thread_id, button_data=None):
            super().__init__(timeout=None)
            if button_data is None:
                button_data = {"label": "Close Thread", "emoji": None}
            
            close_button = discord.ui.Button(
                label=button_data.get("label", "Close Thread"),
                emoji=button_data.get("emoji", None),
                style=discord.ButtonStyle.red,
                custom_id=f"close_{thread_id}"
            )
            
            async def close_callback(interaction: discord.Interaction):
                thread = interaction.guild.get_thread(thread_id)
                await thread.edit(locked=True, archived=True)
                await interaction.response.send_message("Thread closed.", ephemeral=True)
            
            close_button.callback = close_callback
            self.add_item(close_button)

    class TicketActivateView(discord.ui.View):
        def __init__(self, tickets):
            super().__init__()
            self.tickets = tickets
            
            # Create a dropdown for ticket selection with names
            self.select = discord.ui.Select(
                placeholder="Select a ticket configuration",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(
                        label=f"{ticket.get('ticket_name', 'Unnamed Ticket')}",
                        description=f"Channel: #{ticket.get('channel_id')}",
                        value=str(ticket.get('_id'))
                    ) for ticket in tickets[:25]  # Discord limits to 25 options
                ]
            )
            
            async def select_callback(interaction: discord.Interaction):
                ticket_id = self.select.values[0]
                for ticket in self.tickets:
                    if str(ticket.get('_id')) == ticket_id:
                        guild_id = ticket.get("guild_id")
                        channel_id = ticket.get("channel_id")
                        embed_data = ticket.get("embed", {})
                        button_data = ticket.get("button_data", {})
                        thread_message = ticket.get("thread_message", "Welcome to your ticket!")
                        close_button_data = ticket.get("close_button_data", {})
                        ticket_name = ticket.get("ticket_name", "Ticket")
                        
                        try:
                            channel = interaction.guild.get_channel(channel_id)
                            if not channel:
                                await interaction.response.send_message("Channel not found! The ticket channel may have been deleted.", ephemeral=True)
                                return
                                
                            view = discord.ui.View(timeout=None)
                            view.add_item(Ticket_View.TicketButton(
                                button_data,
                                thread_message,
                                embed_data,
                                guild_id,
                                channel_id,
                                close_button_data
                            ))
                            
                            embed = discord.Embed.from_dict(embed_data)
                            msg = await channel.send(embed=embed, view=view)
                            
                            # Create message link for the new message
                            message_link = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{msg.id}"
                            
                            # Update database with the new message ID and link
                            await server_collection.insert_one({
                                "guild_id": interaction.guild.id,
                                "message_id": msg.id,
                                "channel_id": channel_id,
                                "embed": embed_data,
                                "button_data": button_data,
                                "thread_message": thread_message,
                                "close_button_data": close_button_data,
                                "ticket_name": ticket_name,
                                "message_link": message_link
                            })
                            
                            await interaction.response.send_message(f"Ticket system '{ticket_name}' activated in <#{channel_id}>!", ephemeral=True)
                        except Exception as e:
                            await interaction.response.send_message(f"Error activating ticket: {str(e)}", ephemeral=True)
                        break
            
            self.select.callback = select_callback
            self.add_item(self.select)
    
    class TicketDeleteView(discord.ui.View):
        def __init__(self, tickets):
            super().__init__()
            self.tickets = tickets
            
            # Create a dropdown for ticket selection with names
            self.select = discord.ui.Select(
                placeholder="Select a ticket configuration to delete",
                min_values=1,
                max_values=1,
                options=[
                    discord.SelectOption(
                        label=f"{ticket.get('ticket_name', 'Unnamed Ticket')}",
                        description=f"Channel: #{ticket.get('channel_id')}",
                        value=str(ticket.get('_id'))
                    ) for ticket in tickets[:25]  # Discord limits to 25 options
                ]
            )
            
            async def select_callback(interaction: discord.Interaction):
                ticket_id = self.select.values[0]
                selected_ticket = None
                
                for ticket in self.tickets:
                    if str(ticket.get('_id')) == ticket_id:
                        selected_ticket = ticket
                        break
                
                ticket_name = selected_ticket.get('ticket_name', 'Unnamed Ticket') if selected_ticket else 'Unknown Ticket'
                
                # Create confirmation view
                confirm_view = discord.ui.View()
                
                yes_button = discord.ui.Button(label="Yes", style=discord.ButtonStyle.red)
                no_button = discord.ui.Button(label="No", style=discord.ButtonStyle.grey)
                
                async def yes_callback(confirm_interaction: discord.Interaction):
                    try:
                        await Ticket_Dataset().delete_ticket(ticket_id)
                        await confirm_interaction.response.edit_message(content=f"Ticket configuration '{ticket_name}' deleted!", view=None)
                    except Exception as e:
                        await confirm_interaction.response.edit_message(content=f"Error deleting ticket: {str(e)}", view=None)
                
                async def no_callback(confirm_interaction: discord.Interaction):
                    await confirm_interaction.response.edit_message(content="Operation cancelled.", view=None)
                
                yes_button.callback = yes_callback
                no_button.callback = no_callback
                
                confirm_view.add_item(yes_button)
                confirm_view.add_item(no_button)
                
                await interaction.response.send_message(f"Are you sure you want to delete the ticket configuration '{ticket_name}'?", view=confirm_view, ephemeral=True)
            
            self.select.callback = select_callback
            self.add_item(self.select)

    class TicketSetupView:
        @staticmethod
        async def start_setup(ctx, channel):
            paginated_form = Ticket_View.PaginatedEmbedSetup(ctx, channel)
            await paginated_form.start(ctx)
            
        @staticmethod
        async def start_edit(ctx, msg):
            try:
                # Get existing configuration from database
                ticket = await server_collection.find_one({"message_id": msg.id})
                if not ticket:
                    await ctx.send("This message is not configured as a ticket system.")
                    return
                    
                # Initialize the edit form
                paginated_form = Ticket_View.PaginatedEmbedSetup(ctx, msg.channel, edit_mode=True, message=msg)
                
                # Pre-fill form data from existing configuration
                embed_data = ticket.get("embed", {})
                paginated_form.form_data = {
                    "title": embed_data.get("title", ""),
                    "description": embed_data.get("description", ""),
                    "color": f"#{hex(embed_data.get('color', 0x2ecc71))[2:]}",
                    "footer": embed_data.get("footer", {}).get("text", ""),
                    "thumbnail_url": embed_data.get("thumbnail", {}).get("url", ""),
                    "image_url": embed_data.get("image", {}).get("url", ""),
                    "open_button_label": ticket.get("button_data", {}).get("label", "Open Ticket"),
                    "open_button_emoji": ticket.get("button_data", {}).get("emoji", ""),
                    "close_button_label": ticket.get("close_button_data", {}).get("label", "Close Thread"),
                    "close_button_emoji": ticket.get("close_button_data", {}).get("emoji", ""),
                    "thread_msg": ticket.get("thread_message", "Welcome to your ticket! A staff member will assist you shortly."),
                    "ticket_name": ticket.get("ticket_name", "")  # Add existing ticket name
                }
                
                await paginated_form.start(ctx)
            except Exception as e:
                await ctx.send(f"Error starting edit: {str(e)}")
                traceback.print_exception(type(e), e, e.__traceback__)

    class PaginatedEmbedSetup:
        def __init__(self, ctx, channel, edit_mode=False, message=None):
            self.ctx = ctx
            self.channel = channel
            self.page = 1
            self.total_pages = 3
            self.edit_mode = edit_mode
            self.message = message
            self.form_data = {
                "title": "", "description": "", "color": "", "footer": "",
                "thumbnail_url": "", "image_url": "", "open_button_label": "",
                "open_button_emoji": "", "close_button_label": "",
                "close_button_emoji": "", "thread_msg": "", "ticket_name": ""
            }
            self.current_modal = self.create_page_modal(1)
            
        def create_page_modal(self, page_number):
            if page_number == 1:
                return self.Page1Modal(self)
            elif page_number == 2:
                return self.Page2Modal(self)
            elif page_number == 3:
                return self.Page3Modal(self)
        
        async def start(self, interaction_or_ctx):
            if isinstance(interaction_or_ctx, discord.Interaction):
                await interaction_or_ctx.response.send_modal(self.current_modal)
            else:
                view = self.ModalView(self.current_modal)
                if self.edit_mode:
                    await interaction_or_ctx.send("Click the button below to edit your ticket system:", view=view)
                else:
                    await interaction_or_ctx.send("Click the button below to setup your ticket system:", view=view)
                
        class ModalView(discord.ui.View):
            def __init__(self, modal):
                super().__init__()
                self.modal = modal
                setup_button = discord.ui.Button(
                    label="Setup Ticket System", 
                    style=discord.ButtonStyle.primary,
                    custom_id="setup_modal_button"
                )
                
                async def setup_callback(interaction: discord.Interaction):
                    await interaction.response.send_modal(self.modal)
                
                setup_button.callback = setup_callback
                self.add_item(setup_button)
                
        async def next_page(self, interaction):
            if self.page < self.total_pages:
                self.page += 1
                self.current_modal = self.create_page_modal(self.page)
                try:
                    await interaction.response.send_modal(self.current_modal)
                except (discord.errors.InteractionResponded, discord.errors.HTTPException):
                    view = discord.ui.View()
                    button = discord.ui.Button(label=f"Continue to step {self.page}/{self.total_pages}", style=discord.ButtonStyle.primary)
                    
                    async def button_callback(button_interaction):
                        await button_interaction.response.send_modal(self.current_modal)
                    
                    button.callback = button_callback
                    view.add_item(button)
                    await interaction.followup.send("Continue to the next step:", view=view, ephemeral=True)
            else:
                await self.process_complete_form(interaction)
                
        async def process_complete_form(self, interaction):
            try:
                try:
                    await interaction.response.defer(ephemeral=True)
                except (discord.errors.InteractionResponded, discord.errors.HTTPException):
                    pass
                    
                title = self.form_data["title"]
                description = self.form_data["description"] or "Click the button below to open a ticket"
                color_str = self.form_data["color"] or "#2ecc71"
                footer = self.form_data["footer"]
                thumbnail_url = self.form_data["thumbnail_url"]
                image_url = self.form_data["image_url"]
                open_button_label = self.form_data["open_button_label"] or "Open Ticket"
                open_button_emoji = self.form_data["open_button_emoji"] or "🎫"
                close_button_label = self.form_data["close_button_label"] or "Close Thread"
                close_button_emoji = self.form_data["close_button_emoji"] or "🔒"
                thread_msg = self.form_data["thread_msg"] or "Welcome to your ticket! A staff member will assist you shortly."
                ticket_name = self.form_data["ticket_name"] or f"Ticket-{interaction.guild.id}-{self.channel.id}"

                try:
                    if color_str.startswith("#"):
                        color = int(color_str[1:], 16)
                    else:
                        color = int(color_str)
                except (ValueError, TypeError):
                    color = discord.Color.green().value

                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=color
                )
                
                if footer:
                    embed.set_footer(text=footer)
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                if image_url:
                    embed.set_image(url=image_url)

                open_button_data = {
                    "label": open_button_label,
                    "emoji": open_button_emoji
                }
                
                close_button_data = {
                    "label": close_button_label,
                    "emoji": close_button_emoji
                }

                view = discord.ui.View(timeout=None)
                ticket_button = Ticket_View.TicketButton(
                    open_button_data, 
                    thread_msg, 
                    embed.to_dict(), 
                    self.ctx.guild.id, 
                    self.channel.id,
                    close_button_data
                )
                view.add_item(ticket_button)

                if self.edit_mode and self.message:
                    # Update existing message
                    await self.message.edit(embed=embed, view=view)
                    await Ticket_Dataset().update_message(self.ctx, self.message, embed, ticket_name)
                    await interaction.followup.send(f"Ticket system '{ticket_name}' updated successfully!", ephemeral=True)
                else:
                    # Create new message
                    msg = await self.channel.send(embed=embed, view=view)
                    
                    # Create message link
                    message_link = f"https://discord.com/channels/{self.ctx.guild.id}/{self.channel.id}/{msg.id}"
                    
                    try:
                        
                        await Ticket_Dataset().save_message(
                            self.ctx, 
                            msg, 
                            embed, 
                            open_button_data, 
                            thread_msg,
                            close_button_data,
                            ticket_name
                        )
                    except Exception as e:
                        traceback.print_exception(type(e), e, e.__traceback__)

                    await interaction.followup.send(f"Ticket system '{ticket_name}' created successfully!", ephemeral=True)
            except Exception as e:
                await interaction.followup.send("An error occurred while processing the ticket system.", ephemeral=True)
                traceback.print_exception(type(e), e, e.__traceback__)

        class Page1Modal(discord.ui.Modal):
            def __init__(self, parent):
                super().__init__(title=f"Embed Setup (1/{parent.total_pages})")
                self.parent = parent
                
                # Add ticket name field at the top
                self.add_item(discord.ui.TextInput(
                    label="Ticket Name",
                    placeholder="Enter a name for this ticket system",
                    required=True,
                    default=parent.form_data.get("ticket_name", "")
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Title",
                    placeholder="Enter a title for your embed",
                    required=False,
                    default=parent.form_data.get("title", "")
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Description",
                    placeholder="Enter a description for your embed",
                    required=True,
                    style=discord.TextStyle.paragraph,
                    default=parent.form_data.get("description", "")
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Color (hex or int)",
                    placeholder="#2ecc71 or 3066993",
                    required=False,
                    default=parent.form_data.get("color", "")
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Footer",
                    placeholder="Enter footer text (optional)",
                    required=False,
                    default=parent.form_data.get("footer", "")
                ))

            async def on_submit(self, interaction: discord.Interaction):
                self.parent.form_data["ticket_name"] = self.children[0].value
                self.parent.form_data["title"] = self.children[1].value
                self.parent.form_data["description"] = self.children[2].value
                self.parent.form_data["color"] = self.children[3].value
                self.parent.form_data["footer"] = self.children[4].value
                
                try:
                    await interaction.response.defer(ephemeral=True)
                    await self.parent.next_page(interaction)
                except Exception as e:
                    await interaction.followup.send("An error occurred, please try again.", ephemeral=True)
                    traceback.print_exception(type(e), e, e.__traceback__)
                
            async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
                await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
                traceback.print_exception(type(error), error, error.__traceback__)

        class Page2Modal(discord.ui.Modal):
            def __init__(self, parent):
                super().__init__(title=f"Button Setup (2/{parent.total_pages})")
                self.parent = parent
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Thumbnail URL",
                    placeholder="URL for thumbnail image",
                    required=False,
                    default=parent.form_data.get("thumbnail_url", "")
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Embed Image URL",
                    placeholder="URL for main embed image",
                    required=False,
                    default=parent.form_data.get("image_url", "")
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Open Ticket Button Label",
                    placeholder="Open Ticket",
                    required=False,
                    default=parent.form_data.get("open_button_label", "")
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Open Ticket Button Emoji",
                    placeholder="🎫",
                    required=False,
                    default=parent.form_data.get("open_button_emoji", "")
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Close Ticket Button Label",
                    placeholder="Close Thread",
                    required=False,
                    default=parent.form_data.get("close_button_label", "")
                ))

            async def on_submit(self, interaction: discord.Interaction):
                self.parent.form_data["thumbnail_url"] = self.children[0].value
                self.parent.form_data["image_url"] = self.children[1].value
                self.parent.form_data["open_button_label"] = self.children[2].value
                self.parent.form_data["open_button_emoji"] = self.children[3].value
                self.parent.form_data["close_button_label"] = self.children[4].value
                
                try:
                    await interaction.response.defer(ephemeral=True)
                    await self.parent.next_page(interaction)
                except Exception as e:
                    await interaction.followup.send("An error occurred, please try again.", ephemeral=True)
                    traceback.print_exception(type(e), e, e.__traceback__)
                
            async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
                await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
                traceback.print_exception(type(error), error, error.__traceback__)

        class Page3Modal(discord.ui.Modal):
            def __init__(self, parent):
                super().__init__(title=f"Thread Message (3/{parent.total_pages})")
                self.parent = parent
                
                self.add_item(discord.ui.TextInput(
                    label="Close Ticket Button Emoji",
                    placeholder="🔒",
                    required=False,
                    default=parent.form_data.get("close_button_emoji", "")
                ))
                
                self.add_item(discord.ui.TextInput(
                    label="Thread Welcome Message",
                    placeholder="Welcome to your ticket! A staff member will assist you shortly.",
                    required=False,
                    style=discord.TextStyle.paragraph,
                    default=parent.form_data.get("thread_msg", "")
                ))

            async def on_submit(self, interaction: discord.Interaction):
                self.parent.form_data["close_button_emoji"] = self.children[0].value
                self.parent.form_data["thread_msg"] = self.children[1].value
                
                try:
                    await interaction.response.defer(ephemeral=True)
                    await self.parent.process_complete_form(interaction)
                except Exception as e:
                    await interaction.followup.send("An error occurred, please try again.", ephemeral=True)
                    traceback.print_exception(type(e), e, e.__traceback__)
                
            async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
                await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)
                traceback.print_exception(type(error), error, error.__traceback__)

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
    # print("Setting up persistent views for tickets...")
    try:
        mongo_url = os.getenv("MONGO_URI") or "mongodb://localhost:27017/"
        if not os.getenv("MONGO_URI"):
            print(f"Warning: MONGO_URI not set, using default: {mongo_url}")
        cluster = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        db = cluster["Commands"]
        collection = db["ticket"]
        await cluster.admin.command('ping')
        # print("✅ Connected to MongoDB successfully")
        tickets = await collection.find().to_list(length=None)
        # print(f"Loading {len(tickets)} ticket configurations...")

        success_count = error_count = thread_button_count = 0

        named_tickets = [t for t in tickets if t.get("ticket_name")]
        unnamed_tickets = [t for t in tickets if not t.get("ticket_name")]

        # if named_tickets:
        #     print(f"Found {len(named_tickets)} named tickets and {len(unnamed_tickets)} unnamed tickets")

        for ticket in named_tickets + unnamed_tickets:
            try:
                guild_id = ticket.get("guild_id")
                channel_id = ticket.get("channel_id")
                message_id = ticket.get("message_id")
                embed_data = ticket.get("embed", {})
                button_data = ticket.get("button_data", {})
                thread_message = ticket.get("thread_message", "Welcome to your ticket!")
                close_button_data = ticket.get("close_button_data", {})
                message_link = ticket.get("message_link", "")

                ticket_name = ticket.get("ticket_name")
                if not ticket_name:
                    ticket_name = f"Ticket-{guild_id}-{channel_id}"
                    try:
                        await collection.update_one(
                            {"_id": ticket.get("_id")},
                            {"$set": {"ticket_name": ticket_name}}
                        )
                        # print(f"✅ Updated unnamed ticket with generated name: {ticket_name}")
                    except Exception as e:
                        print(f"❌ Failed to update unnamed ticket with name: {str(e)}")

                view = discord.ui.View(timeout=None)
                ticket_button = Ticket_View.TicketButton(button_data, thread_message, embed_data, guild_id, channel_id, close_button_data)
                view.add_item(ticket_button)
                message_found = False

                if message_link and "/channels/" in message_link:
                    try:
                        parts = message_link.split("/")
                        link_guild_id, link_channel_id, link_message_id = int(parts[-3]), int(parts[-2]), int(parts[-1])
                        guild = bot.get_guild(link_guild_id)
                        if guild:
                            channel = guild.get_channel(link_channel_id) or bot.get_thread(link_channel_id)
                            if channel:
                                bot.add_view(view, message_id=link_message_id)
                                message_found = True
                                success_count += 1
                                # print(f"✅ Registered view for ticket '{ticket_name}' via message link")
                    except Exception as e:
                        print(f"❌ Error processing message link for ticket '{ticket_name}': {str(e)}")

                if not message_found:
                    try:
                        guild = bot.get_guild(guild_id)
                        if guild:
                            channel = guild.get_channel(channel_id) or bot.get_thread(channel_id)
                            if channel:
                                bot.add_view(view, message_id=message_id)
                                message_found = True
                                success_count += 1
                                # print(f"✅ Registered view for ticket '{ticket_name}' via channel/message ID")
                    except Exception as e:
                        print(f"❌ Error registering view directly for ticket '{ticket_name}': {str(e)}")

                if not message_found:
                    error_count += 1
                    print(f"❌ Could not register view for ticket '{ticket_name}'")

                if message_found:
                    try:
                        guild = bot.get_guild(guild_id)
                        if guild:
                            thread_count = 0
                            for channel in guild.channels:
                                if isinstance(channel, discord.TextChannel):
                                    try:
                                        for thread in channel.threads:
                                            thread_ticket_name = f"{ticket_name}-Thread-{thread.id}"
                                            close_view = Ticket_View.CloseButton(thread.id, close_button_data)
                                            bot.add_view(close_view, message_id=None)
                                            thread_button_count += 1
                                            thread_count += 1
                                    except Exception as e:
                                        print(f"❌ Error processing threads in channel {channel.id}: {str(e)}")

                            for channel in guild.channels:
                                if isinstance(channel, discord.TextChannel):
                                    try:
                                        async for thread in channel.archived_threads():
                                            close_view = Ticket_View.CloseButton(thread.id, close_button_data)
                                            bot.add_view(close_view, message_id=None)
                                            thread_button_count += 1
                                            thread_count += 1
                                    except Exception as e:
                                        print(f"❌ Error processing archived threads in channel {channel.id}: {str(e)}")
                                    try:
                                        async for thread in channel.archived_threads(private=True):
                                            close_view = Ticket_View.CloseButton(thread.id, close_button_data)
                                            bot.add_view(close_view, message_id=None)
                                            thread_button_count += 1
                                            thread_count += 1
                                    except Exception as e:
                                        print(f"❌ Error processing archived private threads in channel {channel.id}: {str(e)}")

                            # if thread_count > 0:
                            #     print(f"✅ Registered {thread_count} thread buttons for ticket '{ticket_name}'")
                    except Exception as e:
                        print(f"❌ Error registering thread close buttons for ticket '{ticket_name}': {str(e)}")
            except Exception as e:
                error_count += 1
                print(f"❌ Error processing ticket {ticket.get('_id', 'unknown')}: {str(e)}")

        # print(f"✅ Tickets loaded: {success_count} successful, {error_count} failed, {thread_button_count} thread buttons registered")
    except Exception as e:
        print(f'❌ Setup persistent views error: {str(e)}')
        print("🔄 Falling back to empty persistent views setup")
        try:
            class GenericTicketView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=None)
            bot.add_view(GenericTicketView())
            print("✅ Generic fallback view registered")
        except Exception as e:
            print(f"❌ Failed to register fallback view: {str(e)}")
    # print("✅ Persistent ticket views setup complete")


