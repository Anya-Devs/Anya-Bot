# Standard Library Imports
import os
import datetime
import random
import re
from datetime import timedelta, datetime
import typing
import traceback
import asyncio
import discord
import random
import logging
from concurrent.futures import ThreadPoolExecutor



# Third-Party Library Imports
import json
import motor.motor_asyncio
from pymongo.errors import PyMongoError

# Project-Specific Imports
from Data.const import Quest_Progress, error_custom_embed, primary_color, ShopEmbed,QuestEmbed, Quest_Prompt, Quest_Completed_Embed, AnyaImages, TutorialMission
from Imports.discord_imports import *
from Imports.log_imports import *





    
class Quest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        self.shop_file = 'Data/commands/quest/shop.json'
        
    @commands.command(name="redirect")
    async def redirect(self, ctx, *channel_mentions: discord.TextChannel):
     if not (ctx.author.guild_permissions.manage_channels or discord.utils.get(ctx.author.roles, name="Anya Manager")):
        await ctx.reply("You need the `Manage Channels` permission or the `Anya Manager` role to use this command.", mention_author=False)
        return  # Exit if the user doesn't have the required permission or role
     """
     Command to store channels for the guild.
     Usage: !setchannels #channel1 #channel2
     """
     try:
        guild_id = str(ctx.guild.id)
        channel_ids = [str(channel.id) for channel in channel_mentions]
        
        # Store the channels in the database
        if await self.quest_data.store_channels_for_guild(guild_id, channel_ids):
            await ctx.reply(f"Now redirecting missions to {', '.join([channel.mention for channel in channel_mentions])}", mention_author=False)
        else:
            await ctx.reply("Failed to store the channels. Please try again later.", mention_author=False)
     except Exception as e:
        logger.error(f"Error in setchannels command: {e}")
        await ctx.send("An error occurred while setting the channels.")
        
    @commands.command(name='quest', aliases=['q'])
    async def quest(self, ctx, args: str = None):
        logger.debug("Quest command invoked.")

        if args == 'newbie':
            logger.debug("Starting newbie tutorial.")
            tutorial_mission = TutorialMission(self.bot)
            await tutorial_mission.wait_for_user_action(ctx)

        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)

            user_exists = await self.quest_data.find_user_in_server(user_id, guild_id)
            
            if not user_exists:
                prompt_embed = await Quest_Prompt.get_embed(self.bot)
                await ctx.reply(embed=prompt_embed, view=Quest_Button(self.bot, ctx), mention_author=False)
                return

            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)

            if quests:
                view = Quest_View(self.bot, quests, ctx)
                embeds = await view.generate_messages()

                # Send initial embed and view
                if embeds:
                    if len(quests) > 3:
                        # Multiple pages if there are more quests than fit on one page
                        await ctx.reply(embed=embeds, view=view, mention_author=False)
                    else:
                        # Single embed if the number of quests fits on one page
                        await ctx.reply(embed=embeds, mention_author=False)

            else:
                no_quest_message = "You have no quests."
                
                await ctx.reply(no_quest_message, view=Quest_Button1(self.bot, ctx), mention_author=False)
                
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await ctx.send(f"{error_message}")

    @commands.command(name='stars', aliases=['bal', 'points', 'balance'])
    async def balance(self, ctx, method=None, amount: int = None, member: discord.Member = None):
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id)
        if member is None:
            member = ctx.author
            
        try:
            if method == "add":
                if ctx.author.id == 1030285330739363880:
                    await self.quest_data.add_balance(str(member.id), guild_id, amount)
                    amount_with_commas = "{:,}".format(amount)
                    await ctx.send(f":white_check_mark: Successfully added {amount_with_commas} balance to {member.display_name}'s account.")
                else:
                    await ctx.send("You don't have permission to use this command to add balance to other users.")
            else:
                if member is None and amount is None:
                    await self.quest_data.initialize_balance(user_id, guild_id)
                balance = await self.quest_data.get_balance(user_id, guild_id)
                balance_with_commas = "{:,}".format(balance)
                
                embed = discord.Embed(title="Stella", description=f"-# {ctx.author.mention}'s balance", timestamp=datetime.now())
                embed.set_thumbnail(url=ctx.author.avatar)
                embed.add_field(name='Stars', value=None, inline=True)
                embed.add_field(name='Points', value=balance_with_commas, inline=True)
                embed.add_field(name='Class Ranking', value=f'`#{None}`', inline=False)
                embed.set_footer(icon_url=self.bot.user.avatar)
                await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
            logger.error(f"An error occurred in the balance command: {e}")
            await ctx.send("An error occurred while processing your request. Please try again later.")

    @commands.command(name='shop')
    async def shop(self, ctx):
        try:
            shop_data = self.read_shop_file(self.shop_file)
            view = ShopView(self.bot, shop_data)
            await view.start(ctx)

        except Exception as e:
            await ctx.send(f"An error occurred while processing the shop: {e}")

    def read_shop_file(self, filename):
        with open(filename, 'r', encoding='utf-8') as file:
            shop_data = json.load(file)
        return shop_data
    
        
        
class Quest_View(View):
    def __init__(self, bot, quests, ctx, page=0, filtered_quests=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.quests = quests
        self.filtered_quests = filtered_quests if filtered_quests is not None else quests
        self.ctx = ctx
        self.page = page
        self.max_pages = min((len(self.filtered_quests) + 2) // 3, 2)

        # Add quest filters and navigation buttons
        self.add_item(Quest_Select_Filter(bot, quests, ctx))
        if self.page < self.max_pages - 1:
            self.add_item(Quest_Select(bot, self.filtered_quests, ctx, self.max_pages))
        if self.page > 0:
            self.add_item(QuestButton("Previous", discord.ButtonStyle.primary, "previous", bot, self.filtered_quests, ctx, self.page))
        if self.page < self.max_pages - 1:
            self.add_item(QuestButton("Next", discord.ButtonStyle.primary, "next", bot, self.filtered_quests, ctx, self.page))

        # Add the "Fresh Start" button on the bottom row
        self.add_item(QuestButton("Fresh Start", discord.ButtonStyle.danger, "fresh_start", bot, self.filtered_quests, ctx, self.page))

    async def generate_messages(self):
     start_index = self.page * 3
     end_index = start_index + 3
     quests_to_display = self.filtered_quests[start_index:end_index]

     # Create a single embed for the current page
     embed = discord.Embed(
        title="Quests", 
        description="Here are the quests you need to complete. Each quest has a specific objective, progress, and reward. Click on the location link to navigate to the respective channel where the quest can be completed.", 
        color=primary_color()
     )
    
     for quest in quests_to_display:
        quest_id = quest['quest_id']
        progress = quest['progress']
        times = quest['times']
        action = quest['action']
        method = quest['method']
        content = quest['content']
        reward = quest['reward']
        
        # Get the channel using the channel ID
        channel = self.bot.get_channel(int(quest['channel_id']))

        # Generate instructions based on method
        if method == 'message':
            instruction = f"Send: {content}"
        elif method == 'emoji':
            instruction = f"Send emoji: {content}"
        elif method == 'reaction':
            instruction = f"React with: {content}"
        else:
            instruction = "Unknown method. Please refer to the quest details."

        # Generate progress bar
        progress_bar = await Quest_Progress.generate_progress_bar(progress / times, self.bot)
        
        reward_emoji_id = 1247800150479339581
        reward_emoji = discord.utils.get(self.bot.emojis, id=reward_emoji_id)

        # Construct the channel link based on whether it's the current channel
        if channel:
            channel_link = f'[Go here](https://discord.com/channels/{self.ctx.guild.id}/{channel.id})' if channel.id != self.ctx.channel.id else 'In this channel'
        else:
            channel_link = f'Channel not found | Recommended: `/quest delete quest_id: {quest_id}`'  # Fallback in case the channel is not found

        embed.add_field(
            name="",  # Step 1: Field name
            value=(
                f"Quest {quest_id} | {progress_bar} `{progress}/{times}`\n"  # Step 2: Progress information
                f"**{channel_link}** | **{instruction}** | {reward_emoji} `{reward} stp`"  # Step 5: Reward information
                f"\n\n"  # Steps 3 & 4: Channel link and instructions
            ),
            inline=False
        )

     return embed

    
    
    
    
    
    
    
class Quest_Select(Select):
    def __init__(self, bot, quests, ctx, max_pages):
        options = [
            discord.SelectOption(label=f"Page {i+1}", value=str(i))
            for i in range(max_pages)
        ]
        super().__init__(placeholder="Select page...", options=options)
        self.bot = bot
        self.quests = quests
        self.ctx = ctx
        self.max_pages = max_pages

    async def callback(self, interaction: discord.Interaction):
        try:
            page_index = int(self.values[0])
            view = Quest_View(self.bot, self.quests, self.ctx, page=page_index, filtered_quests=self.quests)
            embed = await view.generate_messages()
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await ctx.send(f"{error_message}")

class Quest_Select_Filter(Select):
    def __init__(self, bot, quests, ctx):
        methods = list(set(quest['method'] for quest in quests))
        options = [
            discord.SelectOption(label=method.title(), value=method)
            for method in methods
        ]
        options.insert(0, discord.SelectOption(label="All", value="all"))
        super().__init__(placeholder="Filter...", options=options)
        self.bot = bot
        self.quests = quests
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_method = self.values[0]
            if selected_method == "all":
                filtered_quests = None
            else:
                filtered_quests = [quest for quest in self.quests if quest['method'] == selected_method]

            view = Quest_View(self.bot, self.quests, self.ctx, filtered_quests=filtered_quests)
            embed = await view.generate_messages()
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await self.ctx.send(f"{error_message}")

class QuestButton(discord.ui.Button):
    def __init__(self, label, style, custom_id, bot, quests, ctx, page):
        super().__init__(label=label, style=style, custom_id=custom_id)
        self.bot = bot
        self.quests = quests
        self.ctx = ctx
        self.page = page
        
        self.quest_data = Quest_Data(bot)


    async def callback(self, interaction: discord.Interaction):
        if self.custom_id == "previous":
            self.page -= 1
        elif self.custom_id == "next":
            self.page += 1
        elif self.custom_id == "fresh_start":
            # Call the delete all quests function
            success = await self.quest_data.delete_all_quests(self.ctx.guild.id, self.ctx.author)
            if success:
                await interaction.response.send_message("All quests have been deleted. Starting fresh!", ephemeral=True)
            else:
                await interaction.response.send_message("Failed to delete quests. Please try again.", ephemeral=True)
            # Reset the page and quests list after deletion
            self.page = 0
            self.quests = []  # Clear quests as they have all been deleted

        # Update the view with the current page and reset quests if necessary
        view = Quest_View(self.bot, self.quests, self.ctx, self.page)
        embed = await view.generate_messages()
        await interaction.response.edit_message(embed=embed, view=view)
        
class Quest_Button1(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    async def add_user_to_server(self):
        logger.debug("Adding user to server.")
        try:
            user_id = str(self.ctx.author.id)
            guild_id = str(self.ctx.guild.id)
            users_in_server = await self.quest_data.find_users_in_server(guild_id)
            logger.debug(f"Users in server: {users_in_server}")

            if user_id not in users_in_server:
                await self.quest_data.add_user_to_server(user_id, guild_id)
                return True
            else:
                return False
        except Exception as e:
            error_message = "An error occurred while adding user to server."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, self.ctx, error_message, title="Add User Error")
            return False

    @discord.ui.button(label="New Quest", style=discord.ButtonStyle.success)
    async def new_quest_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        try:
            # Retrieve guild ID and check if redirect channels exist for this guild
            guild_id = str(button.guild.id)
            channel_id = await self.quest_data.get_random_channel_for_guild(guild_id)

            if not channel_id:
                # If no redirect channels are found, notify the user (without mentioning the author)
                await button.response.send_message(
                    "No redirected channels found for this guild. Please set redirect channels before creating a new quest.\n"
                    "> Ask a member with permission to manage channels or with the Anya Manager role to use the command: `...redirect <channels>`",
                    ephemeral=True)
                return  # Exit if no channels are set

            # Proceed to create new quests for the user
            button_user = button.user

            # Add the user to the guild's quest balance
            await self.quest_data.add_balance(button_user, guild_id, 0)

            # Add new quests for the user
            for _ in range(25):
                logger.debug("Adding new quest")
                await self.quest_data.add_new_quest(guild_id, button_user, chance=100)

            # Notify the user that new quests have been created
            await button.response.send_message(
                f"Successfully created new quests for you, {button_user.mention}!",
                ephemeral=True,
            )

        except Exception as e:
            error_message = "An error occurred while processing the new quest button."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, self.ctx, error_message, title="Button Error")
        
class Quest_Button(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    async def add_user_to_server(self):
        logger.debug("Adding user to server.")
        try:
            user_id = str(self.ctx.author.id)
            guild_id = str(self.ctx.guild.id)
            users_in_server = await self.quest_data.find_users_in_server(guild_id)
            logger.debug(f"Users in server: {users_in_server}")

            if user_id not in users_in_server:
                await self.quest_data.add_user_to_server(user_id, guild_id)
                return True
            else:
                return False
        except Exception as e:
            error_message = "An error occurred while adding user to server."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, self.ctx, error_message, title="Add User Error")
            return False

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, button: discord.ui.Button, interaction: discord.Interaction):
     guild_id = str(button.guild.id)
     channel_id = await self.quest_data.get_random_channel_for_guild(guild_id)
     if not channel_id:
                # If no redirect channels are found, notify the user (without mentioning the author)
                await button.response.send_message(
                    "No redirected channels found for this guild. Please set redirect channels before creating a new quest.\n"
                    "> Ask a member with permission to manage channels or with the Anya Manager role to use the command: `...redirect <channels>`",
                    ephemeral=True, 
                )
                return  # Exit if no channels are set
     try:
        added = await self.add_user_to_server()
        
        if added:
            # Retrieve guild ID and check if redirect channels exist for this guild
            guild_id = str(button.guild.id)
            

            # Proceed if channels are available
            embed = await QuestEmbed.get_agree_confirmation_embed(self.bot, button.user)
            await button.response.send_message(embed=embed)
            await button.followup.delete_message(button.message.id)

            button_user = button.user

            # Add the user to the guild's quest balance
            await self.quest_data.add_balance(button_user, guild_id, 0)
            
            # Add new quests for the user
            for _ in range(10):
                logger.debug("Adding new quest")
                await self.quest_data.add_new_quest(guild_id, button_user, chance=100)

        else:
            # Notify the user if they are already part of the game
            await button.response.send_message("You are already part of the game!", ephemeral=True, mention_author=False)
            await button.followup.edit_message(button.message.id, view=None)
     except Exception as e:
        error_message = "An error occurred while processing the accept button."
        logger.error(f"{error_message}: {e}")
        traceback.print_exc()
        await error_custom_embed(self.bot, self.ctx, error_message, title="Button Error", mention_author=False)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        try:
            embed = discord.Embed(title="Quest Canceled", description="You have declined the quest.", color=discord.Color.red())
            await button.response.edit_message(embed=embed, view=None)
        except Exception as e:
            error_message = "An error occurred while processing the decline button."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, self.ctx, error_message, title="Button Error")

            
class Quest_Data(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DB_NAME = 'Quest'
        self.quest_content_file = 'Data/commands/quest/quest_content.txt'

        # Initialize MongoDB connection
        mongo_url = os.getenv('MONGO_URI')
        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")
        self.mongoConnect = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)

    async def handle_error(self, interaction, error, title):
        await error_custom_embed(self.bot, interaction, str(error), title=title)

    async def validate_input(self, **kwargs):
        for key, value in kwargs.items():
            if value is None or value == "":
                raise ValueError(f"{key} cannot be None or empty")
                
    async def get_user_inventory_count(self, guild_id: str, user_id: str, material_name: str) -> int:
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']
        
        # Query to find the user's inventory entry
        user_data = await server_collection.find_one(
            {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
            {f'members.{user_id}.inventory.{material_name}': 1}
        )
        
        if user_data:
            # Check if the material_name exists in the user's inventory
            if 'inventory' in user_data['members'][user_id] and material_name in user_data['members'][user_id]['inventory']:
                return user_data['members'][user_id]['inventory'].get(material_name, 0)
            else:
                # If the material_name does not exist, create a slot for it with default value 0
                await server_collection.update_one(
                    {'guild_id': guild_id},
                    {'$set': {f'members.{user_id}.inventory.{material_name}': 0}},
                    upsert=True
                )
                return 0
        else:
            return 0
     except PyMongoError as e:
        logger.error(f"Error occurred while getting user inventory count: {e}")
        return 0
    
    async def add_item_to_inventory(self, guild_id: str, user_id: str, material_name: str, quantity: int) -> None:
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            await server_collection.update_one(
                {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
                {'$inc': {f'members.{user_id}.inventory.{material_name}': quantity}},
                upsert=True
            )
        except PyMongoError as e:
            logger.error(f"Error occurred while adding item to inventory: {e}")
            raise e
    
    async def add_tool_to_inventory(self, guild_id: str, user_id: str, material_name: str, quantity: int) -> None:
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            await server_collection.update_one(
                {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
                {'$inc': {f'members.{user_id}.inventory.tool.{material_name}': quantity}},
                upsert=True
            )
        except PyMongoError as e:
            logger.error(f"Error occurred while adding item to inventory: {e}")
            raise e
            
    async def remove_all_server_quests(self, guild_id: str) -> None:
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']

        # Update documents where quests field is missing or not an array
        await server_collection.update_many(
            {
                'guild_id': guild_id,
                'members.quests': {'$exists': False}
            },
            {'$set': {'members.$.quests': []}}
        )

        # Remove all quests for all users in the server
        await server_collection.update_many(
            {'guild_id': guild_id},
            {'$set': {'members.$[].quests': []}}
        )

        logger.debug(f"All server quests removed for guild {guild_id}.")
     except PyMongoError as e:
        logger.error(f"Error occurred while removing all server quests: {e}")
        raise e

    
    async def get_server_quest_count(self, guild_id: str) -> int:
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            guild_data = await server_collection.find_one({'guild_id': guild_id})
            if guild_data:
                members_data = guild_data.get('members', {})
                total_quests = sum(len(member.get('quests', [])) for member in members_data.values())
                return total_quests
            else:
                return 0
        except PyMongoError as e:
            logger.error(f"Error occurred while getting server quest count: {e}")
            return 0

    async def get_beginner_quests(self, guild_id: str) -> List[Dict[str, Union[str, int]]]:
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            guild_data = await server_collection.find_one({'guild_id': guild_id})
            if guild_data:
                beginner_quests = []
                members_data = guild_data.get('members', {})
                for member_id, member_data in members_data.items():
                    quests = member_data.get('quests', [])
                    for quest in quests:
                        if quest.get('progress', 0) == 0:
                            beginner_quests.append({
                                'action': quest.get('action', ''),
                                'method': quest.get('method', ''),
                                'content': quest.get('content', ''),
                                'times': quest.get('times', 0)
                            })
                return beginner_quests
            else:
                return []
        except PyMongoError as e:
            logger.error(f"Error occurred while getting beginner quests: {e}")
            return []
    async def set_quest_limit(self, guild_id: str, limit: int) -> None:
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            await server_collection.update_one(
                {'guild_id': guild_id},
                {'$set': {'quest_limit': limit}},
                upsert=True
            )
        except PyMongoError as e:
            logger.error(f"Error occurred while setting quest limit: {e}")
            raise e

    async def get_quest_limit(self, guild_id: str) -> int:
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            guild_doc = await server_collection.find_one({'guild_id': guild_id})
            if guild_doc:
                return guild_doc.get('quest_limit', 25)  # Default to 25 if limit is not found
            else:
                return 25  # Default limit if not set
        except PyMongoError as e:
            logger.error(f"Error occurred while getting quest limit: {e}")
            raise e
            
    async def find_user_in_server(self, user_id: str, guild_id: str) -> bool:
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']
        server_data = await server_collection.find_one({'guild_id': guild_id})
        
        if server_data:
            members_data = server_data.get('members', {})
            return user_id in members_data
        else:
            return False
     except PyMongoError as e:
        logger.error(f"Error occurred while finding user in server: {e}")
        return False
    
    async def find_users_in_server(self, guild_id: str):
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']
        
        # Log the query being made
        logger.debug(f"Querying for guild_id: {guild_id}")
        
        # Find the guild document by its ID
        guild_document = await server_collection.find_one({'guild_id': str(guild_id)})
        
        if guild_document:
            # Extract the members data from the guild document
            members_data = guild_document.get('members', {})
            users_in_server = list(members_data.keys())  # Extract user IDs
            
            # logger.debug(f"Found {len(users_in_server)} users in server {guild_id}.")
            return users_in_server
        else:
            logger.debug(f"No guild found with ID {guild_id}.")
            return []
     except PyMongoError as e:
        logger.error(f"Error occurred while finding users in server: {e}")
        return []

    async def find_users_with_quest(self, guild_id: str, quest_id: int):
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']
        
        # Log the query being made
        logger.debug(f"Querying for guild_id: {guild_id} with quest_id: {quest_id}")
        
        # Find the guild document by its ID
        guild_document = await server_collection.find_one({'guild_id': str(guild_id)})
        
        if guild_document:
            # Extract the members data from the guild document
            members_data = guild_document.get('members', {})
            users_with_quest = []
            
            # Iterate through each user and their quests to find the specified quest
            for user_id, user_data in members_data.items():
                quests = user_data.get('quests', [])
                if any(quest['quest_id'] == quest_id for quest in quests):
                    users_with_quest.append(user_id)
            
            # logger.debug(f"Found {len(users_with_quest)} users with quest ID {quest_id} in guild {guild_id}.")
            return users_with_quest
        else:
            logger.debug(f"No guild found with ID {guild_id}.")
            return []
     except PyMongoError as e:
        logger.error(f"Error occurred while finding users with quest: {e}")
        return []
    
    async def find_quests_by_user_and_server(self, user_id: str, guild_id: str, interaction=None):
        try:
            await self.validate_input(user_id=user_id, guild_id=guild_id)
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            server_data = await server_collection.find_one({'guild_id': guild_id})
            if server_data:
                member_data = server_data.get('members', {}).get(user_id, {})
                quests = member_data.get('quests', [])
                # logger.debug(f"Found {len(quests)} quests for user {user_id} in guild {guild_id}.")
                if  len(quests) == 0:
                    return None
                return quests
                
            else:
                # logger.debug("No server data found.")
                return []
        except PyMongoError as e:
            logger.error(f"Error occurred while finding quests: {e}")
            if interaction:
                await self.handle_error(interaction, e, title="Quest Finding")
            return None

    async def insert_quest(self, guild_id: str, user_id: str, quest_data: dict, interaction=None):
        try:
            quest_data['progress'] = 0  # Add progress field with default value 0
            await self.validate_input(**quest_data)
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            
            # Append the quest data to the appropriate spot
            await server_collection.update_one(
                {'guild_id': guild_id, f'members.{user_id}.quests': {'$not': {'$elemMatch': {'quest_id': quest_data['quest_id']}}}},
                {'$push': {f'members.{user_id}.quests': quest_data}},
                upsert=True
            )
            logger.debug(f"Inserted quest data for user {user_id} in guild {guild_id}.")
        except (ValueError, PyMongoError) as e:
            logger.error(f"Error occurred while inserting quest: {e}")
            if interaction:
                await self.handle_error(interaction, e, title="Quest Insertion")

    async def get_latest_quest_id(self, guild_id: str, user_id: str, interaction=None) -> int:
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            server_data = await server_collection.find_one({'guild_id': guild_id})
            if server_data:
                member_data = server_data.get('members', {}).get(user_id, {})
                quests = member_data.get('quests', [])
                latest_quest = max([quest.get('quest_id', 0) for quest in quests], default=0)
                logger.debug(f"Latest quest ID for user {user_id} in guild {guild_id}: {latest_quest}.")
                return latest_quest
            else:
                # logger.debug(f"No server data found for user {user_id} in guild {guild_id}.")
                return 0
        except PyMongoError as e:
            logger.error(f"Error occurred while getting latest quest ID: {e}")
            if interaction:
                await self.handle_error(interaction, e, title="Latest Quest ID")
            return 0
        
    async def store_server_quest(self, guild_id: str, quest_data: dict):
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']
        
        # Find the server document by guild_id or create a new one if not exists
        server_doc = await server_collection.find_one({'_id': guild_id})
        if not server_doc:
            server_doc = {'_id': guild_id, 'server_quest': []}
        
        # Assign a quest_id based on the current number of quests
        quest_id = len(server_doc['server_quest']) + 1
        quest_data['quest_id'] = quest_id
        
        # Append the quest data and update the document
        server_doc['server_quest'].append(quest_data)
        
        # Update the document in MongoDB
        await server_collection.update_one({'_id': guild_id}, {'$set': server_doc}, upsert=True)
        
        logger.debug(f"Stored quest data for guild {guild_id}: {quest_data}")
        
     except PyMongoError as e:
        logger.error(f"Error occurred while storing quest data: {e}")
        raise e
        
        
    async def get_random_channel_for_guild(self, guild_id: str, fallback_channel=None):
        """
        Retrieve a random channel ID for the specified guild from the database.
        If no channels are found, return the fallback channel ID if provided.
        """
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']

            # Fetch the channels for the guild from the database
            guild_data = await server_collection.find_one({'guild_id': guild_id}, {'channels': 1})

            if guild_data and 'channels' in guild_data and guild_data['channels']:
                # If channels are found, select a random one
                channel_ids = guild_data['channels']
                random_channel_id = random.choice(channel_ids)
                logger.debug(f"Random channel ID selected: {random_channel_id} for guild {guild_id}")
                return random_channel_id
            else:
                logger.debug(f"No channels found for guild {guild_id}. Using fallback channel.")
                return fallback_channel.id if fallback_channel else None

        except PyMongoError as e:
            logger.error(f"Error occurred while retrieving random channel: {e}")
            return fallback_channel.id if fallback_channel else None    
    
    
    async def store_channels_for_guild(self, guild_id: str, channel_ids: list):
     """
     Store the provided list of channel IDs for the guild in the database, 
     replacing any existing channel IDs.
     """
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']
        
        # Replace the document with the new channel IDs for the guild
        await server_collection.update_one(
            {'guild_id': guild_id},
            {'$set': {'channels': channel_ids}},  # This will replace the 'channels' field
            upsert=True
        )
        
        logger.debug(f"Stored (overwritten) channels {channel_ids} for guild {guild_id}.")
        return True
     except PyMongoError as e:
        logger.error(f"Error occurred while storing channels: {e}")
        return False     
    
    
    async def server_quests(self, guild_id: str):
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            
            # Find the server document by guild_id
            server_doc = await server_collection.find_one({'_id': guild_id})
            if not server_doc or 'server_quest' not in server_doc:
                return None
            
            return server_doc['server_quest']
        
        except PyMongoError as e:
            logger.error(f"Error occurred while getting server quests: {e}")
            raise e
    async def create_quest(self, guild_id: str, action: str, method: str, content: str, times: int, reward: int, interaction=None):
     try:
        # Fetch a random channel for the guild, provide an interaction fallback
        fallback_channel = discord.utils.get(interaction.guild.text_channels, name="general") if interaction else None
        channel_id = await self.get_random_channel_for_guild(guild_id, fallback_channel=fallback_channel)

        if not channel_id:
            # Notify you or the user that no channels have been redirected for the guild
            message = "No redirected channels found for this guild. Please use the command to set redirect channels first."
            logger.error(message)
            if interaction:
                await interaction.send(message)
            return  # Exit function, no channels to create the quest
        
        # Calculate reward as a random value between 4 and 20 times the `times` value
        reward = random.randint(4, 20) * times

        # Prepare quest data
        quest_data = {
            'action': action,
            'method': method,
            'content': content,
            'channel_id': channel_id,
            'times': times,
            'reward': reward
        }
        
        # Validate the quest data
        await self.validate_input(**quest_data)
        
        # Store the quest data in MongoDB
        await self.store_server_quest(guild_id, quest_data)

        # Increment and assign the quest ID
        quest_count = await self.get_server_quest_count(guild_id)
        quest_data['quest_id'] = quest_count + 1
        
        # Insert the quest for each user in the server
        users_in_server = await self.find_users_in_server(guild_id)
        if not users_in_server:
            raise ValueError("No users found in the server.")

        for user_id in users_in_server:
            await self.insert_quest(guild_id, user_id, quest_data, interaction)

        logger.debug(f"Created quest for guild {guild_id} with action {action} and content {content}.")
        
        return quest_count + 1  # Return the incremented quest count

     except (ValueError, PyMongoError) as e:
        logger.error(f"Error occurred while creating quest: {e}")
        if interaction:
            await self.handle_error(interaction, e, title="Quest Creation")
        raise e

    async def create_member_quest(self, guild_id: str, user_id: str, action: str, method: str, content: str, times: int, interaction=None):
        try:
            # Calculate reward as a random value between 4 and 20 times the `times` value
            reward = random.randint(4, 20) * times
            
            # Ensure the reward is correctly set in the quest data
            quest_data = {
                'action': action,
                'method': method,
                'content': content,
                'times': times,
                'reward': reward
            }
            await self.validate_input(**quest_data)
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']

            quest_count = await self.get_server_quest_count(guild_id)
            quest_limit = await self.get_quest_limit(guild_id)

            if quest_count >= quest_limit:
                raise ValueError("Quest limit exceeded for this server.")

            user_exists = await self.find_user_in_server(user_id, guild_id)
            if not user_exists:
                raise ValueError("User not found in the server.")

            quest_data['quest_id'] = quest_count + 1  # Set the quest_id to be the next number
            await self.insert_quest(guild_id, user_id, quest_data, interaction)

            logger.debug(f"Created member quest for user {user_id} in guild {guild_id} with action {action} and content {content}.")
        except (ValueError, PyMongoError) as e:
            logger.error(f"Error occurred while creating member quest: {e}")
            if interaction:
                await self.handle_error(interaction, e, title="Member Quest Creation")
            raise e
            
            
    async def generate_random_quest_content(self, bot, author, guild_id):
        try:
            with open(self.quest_content_file, 'r') as quest_content_file:
                quest_templates = quest_content_file.readlines()

            selected_quest_template = random.choice(quest_templates)

            return selected_quest_template
        except Exception as e:
            logger.error(f"Error occurred while generating random quest content: {e}")
            return None
    
    async def generate_random_reaction_content(self, guild_id):
     guild = self.bot.get_guild(int(guild_id))
     if not guild:
        return None
    
     # Get the list of emojis in the server
     emojis = [emoji for emoji in guild.emojis if not emoji.animated]

    
     # If there are fewer than 5 custom emojis, use default Discord emojis
     if len(emojis) < 5:
        default_emojis = ['😄', '😁', '😆', '😅', '😂', '🤣', '😊', '😇', '🙂', '🙃', '😉', '😌', '😍', '🥰', '😘', '😗', '😙', '😚']
        emoji = random.choice(default_emojis)
     else:
        emoji = random.choice(emojis)
    
     logger.debug(f"Selected emoji: {emoji}")
     return str(emoji)
    
    async def get_most_active_channel(self, guild_id, threshold=5, message_limit=100, fallback_channel_id=None):
     try:
        logger.debug('Entering get_most_active_channel function')
        guild = self.bot.get_guild(int(guild_id))
        
        if guild:
            logger.debug(f"Guild found: {guild.name} (ID: {guild_id})")
            channel_activity = {}

            # Executor for concurrent task execution
            with ThreadPoolExecutor() as executor:
                loop = asyncio.get_event_loop()
                
                async def count_messages(channel):
                    try:
                        message_count = 0
                        member_set = set()
                        async for message in channel.history(limit=message_limit):
                            message_count += 1
                            if not message.author.bot:
                                member_set.add(message.author.id)
                        return channel.id, message_count, len(member_set)
                    except Exception as e:
                        logger.error(f"Error while processing channel {channel.name}: {e}")
                        return None

                # List of tasks for concurrent execution
                tasks = [
                    loop.run_in_executor(executor, count_messages, channel)
                    for channel in guild.text_channels
                    if channel.permissions_for(guild.default_role).send_messages
                ]
                
                # Gather all results
                results = await asyncio.gather(*tasks)

                # Process the results
                for result in results:
                    if result:
                        channel_id, message_count, member_count = result
                        channel_activity[channel_id] = (message_count, member_count)
                        logger.debug(f"Processed channel {channel_id}: {message_count} messages, {member_count} members")

            # Sort channels by member count and message count
            sorted_channels = sorted(channel_activity.items(), key=lambda x: (x[1][1], x[1][0]), reverse=True)
            if sorted_channels:
                logger.debug(f"Sorted channels by activity: {sorted_channels}")
                if len(sorted_channels) > threshold:
                    most_active_channel_id = random.choice([channel[0] for channel in sorted_channels[:threshold]])
                else:
                    most_active_channel_id = sorted_channels[0][0]
                logger.debug(f"Selected most active channel: {most_active_channel_id}")
            else:
                # Handle fallback if no active channels found
                most_active_channel_id = fallback_channel_id or random.choice([channel.id for channel in guild.text_channels])
                logger.debug(f"No active channels found, using fallback: {most_active_channel_id}")

            return most_active_channel_id
        else:
            logger.debug(f"Guild not found: {guild_id}")
            return fallback_channel_id or None
     except Exception as e:
        logger.error(f"Error occurred while getting the most active channel: {e}")
        traceback.print_exc()
        return fallback_channel_id or None
    
    
    
    async def insert_quest_existing_path(self, guild_id: str, user_id: str, quest_data: dict, interaction=None):
     try:
        await self.validate_input(**quest_data)
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']

        # Check if the user exists in the server
        server_data = await server_collection.find_one({'guild_id': guild_id, f'members.{user_id}': {'$exists': True}})
        
        if not server_data:
            logger.debug(f"User ID {user_id} does not exist in guild {guild_id}.")
            return False

        # Append the quest data to the user's quest list
        await server_collection.update_one(
            {'guild_id': guild_id, f'members.{user_id}.quests': {'$not': {'$elemMatch': {'quest_id': quest_data['quest_id']}}}},
            {'$push': {f'members.{user_id}.quests': quest_data}}
        )
        logger.debug(f"Inserted quest data for user {user_id} in guild {guild_id}.")
        return True
     except (ValueError, PyMongoError) as e:
        logger.error(f"Error occurred while inserting quest: {e}")
        if interaction:
            await self.handle_error(interaction, e, title="Quest Insertion")
        return False
    
    async def add_new_quest(self, guild_id, message_author, action='send', method=None, chance=50):
     logger.debug(f"Attempting to add new quest for guild_id: {guild_id}, message_author: {message_author}, action: {action}, method: {method}, chance: {chance}")
     try:
        user_id = str(message_author.id)
        logger.debug(f"User ID: {user_id}")

        # Generate random times for the quest
        times = random.randint(1, 5)
        logger.debug(f"Random times selected: {times}")

        reward = random.randint(4, 20) * times

        # Check the random chance first
        if random.randint(1, 100) > chance:
            logger.debug("Random chance check failed. No quest will be created.")
            return None

        # Check quest limit
        quest_limit = await self.get_quest_limit(guild_id)
        existing_quests = await self.find_quests_by_user_and_server(user_id, guild_id)
        if existing_quests is None:
            existing_quests = []  # Initialize as an empty list if None

        if len(existing_quests) >= quest_limit:
            logger.debug("User has reached the quest limit. No quest will be created.")
            return None

        # Get a random channel for the guild, provide an interaction fallback
        fallback_channel = discord.utils.get(message_author.guild.text_channels, name="general") if message_author.guild else None
        channel_id = await self.get_random_channel_for_guild(guild_id, fallback_channel=fallback_channel)

        if not channel_id:
            # Notify user to create redirect channels
            message = "No redirected channels found for this guild. Please use the command to set redirect channels first."
            logger.error(message)
            await message_author.send(message)  # Assuming `message_author` is a user object
            return None  # Exit function, no channels to create the quest

        while True:
            # Randomly choose method if not provided
            if method is None:
                method = random.choice(['message', 'reaction', 'emoji'])
                logger.debug(f"Method chosen: {method}")
                
            # Generate random quest content based on the method
            if method == 'message':
                content = await self.generate_random_quest_content(self.bot, message_author, guild_id)
            else:  # method == 'reaction'
                content = await self.generate_random_reaction_content(guild_id)
            if content is None:
                logger.error("Failed to generate random quest content.")
                return None

            # Check if the content is already used in other quests
            content_exists = any(quest['content'] == content for quest in existing_quests)

            if not content_exists:
                break  # Exit the loop if the content is unique

        logger.debug(f"Generated quest content: {content}")

        # Fetch the latest quest ID for the user in the guild
        latest_quest_id = await self.get_latest_quest_id(guild_id, user_id)

        # If latest_quest_id is None, set new_quest_id to 1
        new_quest_id = 1 if latest_quest_id is None else latest_quest_id + 1

        # Define the new quest data
        quest_data = {
            'quest_id': new_quest_id,
            'action': action,
            'method': method,
            'channel_id': channel_id,
            'times': times if method not in ('message', 'emoji') else 1, # Updated
            'content': content,
            'reward': reward,
            'progress': 0  # Initialize progress to 0
        }
        logger.debug(f"Creating quest for user_id: {user_id}, guild_id: {guild_id}, quest_data: {quest_data}")

        # Insert the new quest for the user in the guild
        if await self.insert_quest_existing_path(guild_id, user_id, quest_data):
            logger.debug(f"Quest created for user_id: {user_id}, guild_id: {guild_id}, quest_data: {quest_data}")
            return new_quest_id  # Return the new quest ID
        else:
            logger.debug(f"Failed to create quest for user_id: {user_id}, guild_id: {guild_id} because the user path does not exist.")
            return None

     except Exception as e:
        logger.error(f"Error occurred while adding new quest: {e}")
        return None
    
    async def delete_all_quests(self, guild_id, message_author):
     logger.debug(f"Attempting to delete all quests for guild_id: {guild_id}, user_id: {message_author.id}")
     try:
        user_id = str(message_author.id)

        # Fetch all quests for the user in the specified guild
        existing_quests = await self.find_quests_by_user_and_server(user_id, guild_id)
        if not existing_quests:
            logger.debug("No quests found for the user. Nothing to delete.")
            return False  # Indicate no quests to delete

        # Loop through and delete each quest individually
        for quest in existing_quests:
            quest_id = quest['quest_id']
            deletion_success = await self.delete_quest(guild_id, user_id, quest_id)
            
            if deletion_success:
                logger.debug(f"Deleted quest_id: {quest_id} for user_id: {user_id} in guild_id: {guild_id}")
            else:
                logger.warning(f"Failed to delete quest_id: {quest_id} for user_id: {user_id} in guild_id: {guild_id}")

        logger.info(f"Successfully deleted all quests for user_id: {user_id} in guild_id: {guild_id}")
        return True  # Indicate successful deletion of all quests

     except Exception as e:
        logger.error(f"Error occurred while deleting all quests: {e}")
        return False
    
    async def add_user_to_server(self, user_id: str, guild_id: str):
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            server_data = await server_collection.find_one({'guild_id': guild_id})
            if not server_data:
                server_data = {'guild_id': guild_id, 'members': {}}

            members_data = server_data.get('members', {})
            members_data[user_id] = {'quests': []}

            await server_collection.update_one(
                {'guild_id': guild_id},
                {'$set': {'members': members_data}},
                upsert=True
            )
        except PyMongoError as e:
            logger.error(f"Error occurred while adding user to server: {e}")

    
    async def delete_quest(self, guild_id: str, quest_id: int, interaction=None):
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']

        # Log the query being made
        logger.debug(f"Querying for guild_id: {guild_id} with quest_id: {quest_id}")

        # Find the guild document by its ID
        guild_document = await server_collection.find_one({'guild_id': str(guild_id)})

        if not guild_document:
            logger.debug(f"No guild found with ID {guild_id}.")
            return

        # Extract the members data from the guild document
        members_data = guild_document.get('members', {})

        # Loop through each member
        for member_id, member_data in members_data.items():
            # Extract quests for the current member
            quests = member_data.get('quests', [])

            # Log the current quests for the member
            logger.debug(f"Current quests for user {member_id}: {quests}")

            # Check if any quest matches the specified quest ID
            if any(quest.get('quest_id') == quest_id for quest in quests):
                # logger.debug(f"Found quest with ID {quest_id} for user {member_id} in guild {guild_id}.")
                
                # Remove the quests that match the quest_id
                new_quests = [quest for quest in quests if quest.get('quest_id') != quest_id]

                # Update the guild document with the modified member data
                result = await server_collection.update_one(
                    {'guild_id': str(guild_id)},
                    {'$set': {f'members.{member_id}.quests': new_quests}}
                )

                if result.modified_count > 0:
                    logger.debug(f"Deleted quest with ID {quest_id} for user {member_id} in guild {guild_id}.")
                else:
                    logger.debug(f"Failed to delete quest with ID {quest_id} for user {member_id} in guild {guild_id}.")
            else:
                logger.debug(f"No quest with ID {quest_id} found for user {member_id} in guild {guild_id} to delete.")

     except PyMongoError as e:
        logger.error(f"Error occurred while deleting quest: {e}")
        if interaction:
            await self.handle_error(interaction, e, title="Quest Deletion")
   
    async def delete_quest_for_user(self, guild_id: str, user_id: str, quest_id: int, interaction=None):
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']

        # Log the query being made
        logger.debug(f"Querying for guild_id: {guild_id} with quest_id: {quest_id}")

        # Find the guild document by its ID
        guild_document = await server_collection.find_one({'guild_id': str(guild_id)})

        if not guild_document:
            logger.debug(f"No guild found with ID {guild_id}.")
            return

        # Extract the members data from the guild document
        members_data = guild_document.get('members', {})

        # Check if the specified user exists in the guild
        if user_id not in members_data:
            logger.debug(f"No user found with ID {user_id} in guild {guild_id}.")
            return

        # Extract quests for the specified user
        user_quests = members_data[user_id].get('quests', [])

        # Loop through the user's quests
        for quest in user_quests:
            if quest.get('quest_id') == quest_id:
                user_quests.remove(quest)
                logger.debug(f"Deleted quest with ID {quest_id} for user {user_id} in guild {guild_id}.")
                break  # No need to continue searching once the quest is deleted

        # Update the guild document with the modified member data
        await server_collection.update_one(
            {'guild_id': guild_id},
            {'$set': {f'members.{user_id}.quests': user_quests}}
        )

     except PyMongoError as e:
        logger.error(f"Error occurred while deleting quest for user: {e}")
        if interaction:
            await self.handle_error(interaction, e, title="Quest Deletion")
    
    async def update_quest_progress(self, guild_id: str, user_id: str, quest_id: int, progress: int):
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            
            # Update the progress of the specified quest for the user
            await server_collection.update_one(
                {'guild_id': guild_id, f'members.{user_id}.quests.quest_id': quest_id},
                {'$set': {f'members.{user_id}.quests.$.progress': progress}}
            )

            logger.debug(f"Quest {quest_id} progress updated for user {user_id} in guild {guild_id}.")
        except PyMongoError as e:
            logger.error(f"Error occurred while updating quest progress: {e}")
            raise e
            
    async def get_balance(self, user_id: str, guild_id: str):
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']

            user_balance_key = f"members.{user_id}.stella_points"

            user_data = await server_collection.find_one(
                {'guild_id': guild_id},
                {user_balance_key: 1, '_id': 0}
            )

            balance = user_data.get('members', {}).get(user_id, {}).get('stella_points', 0)
            return balance
        except PyMongoError as e:
            logger.error(f"Error occurred while getting balance: {e}")
            return 0
        
    async def add_balance(self, user_id: str, guild_id: str, amount: int):
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']

            user_balance_key = f"members.{user_id}.stella_points"

            await server_collection.update_one(
                {'guild_id': guild_id},
                {
                    '$inc': {user_balance_key: amount},
                    '$setOnInsert': {
                        'members.{user_id}.stella_points': 0,
                    }
                },
                upsert=True
            )
        except PyMongoError as e:
            logger.error(f"Error occurred while adding balance: {e}")



    async def initialize_balance(self, user_id: str, guild_id: str):
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']

            user_balance_key = f"members.{user_id}.stella_points"

            await server_collection.update_one(
                {'guild_id': guild_id},
                {
                    '$setOnInsert': {
                        user_balance_key: 0,
                    }
                },
                upsert=True
            )
        except PyMongoError as e:
            logger.error(f"Error occurred while initializing balance: {e}")
            
class Quest_Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        super().__init__()

    async def check_server_quest_limit(self, guild_id: int) -> bool:
        """
        Check if the server has reached its quest limit.
        """
        server_quest_count = await self.quest_data.get_server_quest_count(guild_id)
        server_quest_limit = await self.quest_data.get_quest_limit(guild_id)
        if server_quest_count >= server_quest_limit:
            return False
        return True

    quest_group = app_commands.Group(name="quest", description="Quest related commands")

    @quest_group.command(
        name="create",
        description="Create a new quest.",
    )
    @app_commands.describe(action='The action to perform for the quest.')
    @app_commands.describe(method='The method to use for the quest.')
    @app_commands.describe(content='The content for the quest.')
    @app_commands.choices(action=[
        discord.app_commands.Choice(name='send', value='send'), 
        discord.app_commands.Choice(name='receive', value='receive'), 
    ])
    @app_commands.choices(method=[
        discord.app_commands.Choice(name='message', value='message'),
        discord.app_commands.Choice(name='reaction', value='reaction'),
        discord.app_commands.Choice(name='emoji', value='emoji')

    ])
    async def create_quest(
        self,
        interaction: discord.Interaction,
        action: discord.app_commands.Choice[str],
        method: discord.app_commands.Choice[str],
        channel: discord.TextChannel,
        content: str,
        times: typing.Optional[int] = 1,
    ) -> None:
        try:
            # Check if content contains mentions
            if any(mention in content for mention in ['<@', '<@&']):
                await interaction.response.send_message("Content cannot contain user or role mentions.", ephemeral=True)
                return

            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            user = interaction.user
            
            # Create the quest
            quest_id = await self.quest_data.create_quest(guild_id, action.value, method.value, content, channel.id, times, 0, interaction)
            if quest_id is not None:
                # Create the quest embed
                embed = await QuestEmbed.create_quest_embed(self.bot,"Created", quest_id, action.value, method.value, channel, times=times, content=content,user=user)
                
                # Send the embed
                await interaction.response.send_message(embed=embed)
                logger.debug("Quest creation successful.")
            else:
                await interaction.response.send_message("Try doing `...quest`", ephemeral=True)
                logger.debug("Failed to create the quest.")
                
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, interaction, e, title="Quest Creation")

    @quest_group.command(
        name="delete",
        description="Delete a quest by its ID.",
    )
    async def delete_quest(
     self,
     interaction: discord.Interaction,
     quest_id: int) -> None:
     try:
        guild_id = interaction.guild.id
        
        # Find all users in the guild
        users_in_guild = await self.quest_data.find_users_in_server(guild_id)
        
        if not users_in_guild:
            await interaction.response.send_message("No users found in the server.", ephemeral=True)
            return
        
        quest_deleted = False

        for user_id in users_in_guild:
            # Check if the quest exists for the user
            quest_exists =  await self.quest_data.find_users_with_quest(guild_id, quest_id)
            if quest_exists:
                # Delete the quest for this user
                await self.quest_data.delete_quest(guild_id, quest_id)
                quest_deleted = True

        if quest_deleted:
            await interaction.response.send_message(f"The quest with ID {quest_id} has been deleted for all users who had it.", ephemeral=True)
        else:
            await interaction.response.send_message("The specified quest does not exist for any user.", ephemeral=True)
        
     except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()
        await self.quest_data.handle_error(interaction, e, title="Quest Deletion")

    @quest_group.command(
        name="removeall",
        description="Remove all server quests from every member.",
    )
    async def remove_all_server_quests(
     self,
     interaction: discord.Interaction
     ) -> None:
     try:
        guild_id = str(interaction.guild_id)

        # Remove all server quests
        await self.quest_data.remove_all_server_quests(guild_id)

        await interaction.response.send_message("All server quests have been removed from every member.", ephemeral=True)
        logger.debug("All server quests removed successfully.")
     except Exception as e:
        logger.error(f"An error occurred: {e}")
        traceback.print_exc()
        await self.quest_data.handle_error(interaction, e, title="Remove All Server Quests")

    @quest_group.command(
        name="setlimit",
        description="Set the maximum number of quests a user can have.",)
    async def set_quest_limit(
        self,
        interaction: discord.Interaction,
        limit: int) -> None:
        try:
            guild_id = str(interaction.guild_id)

            # Update the quest limit for the guild
            await self.quest_data.set_quest_limit(guild_id, limit)

            await interaction.response.send_message(f"Quest limit set to {limit} for this server.", ephemeral=True)
            logger.debug("Quest limit updated successfully.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, interaction, e, title="Quest Limit Update")
            
    @quest_group.command(
     name="serverquest",
     description="View all quests created for the server.",)        
    async def view_all_server_quests(
    self,
    interaction: discord.Interaction
) -> None:
     try:
        guild_id = str(interaction.guild_id)
        
        quests = await self.quest_data.server_quests(guild_id)
        
        embed = discord.Embed(title=f"All Server Quests for Server {guild_id}", color=0x7289DA)
        
        for quest_data in quests:
            embed.add_field(
                name=f"Quest ID: {quest_data['quest_id']}",
                value=f"**Action:** {quest_data['action']}\n"
                      f"**Method:** {quest_data['method']}\n"
                      f"**Content:** {quest_data['content']}\n"
                      f"**Channel ID:** {quest_data['channel_id']}\n"
                      f"**Times:** {quest_data['times']}\n"
                      f"**Reward:** {quest_data['reward']}\n",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
        logger.debug("Viewed all server quests successfully.")
    
     except Exception as e:
        logger.error(f"An error occurred: {e}")
        traceback.print_exc()
        await self.quest_data.handle_error(interaction, e, title="View All Server Quests")


class ShopView(discord.ui.View):
    def __init__(self, bot, shop_data):
        super().__init__()
        self.bot = bot
        self.quest_data = Quest_Data(bot)

        self.shop_data = shop_data
        self.materials_dict = {material['name']: material['emoji'] for material in self.shop_data.get("Materials", [])}

    async def start(self, ctx):
        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)

            balance = await self.quest_data.get_balance(user_id, guild_id)
            balance = "{:,}".format(balance)

            shop_embed = await ShopEmbed.start_shop_embed(self.bot, ctx, balance)

            # Create and add the select menu
            select = SpyToolSelect(self.shop_data, self.materials_dict, self.quest_data, user_id, guild_id)
            self.add_item(select)

            # Send the initial embed with the select menu
            await ctx.send(embed=shop_embed, view=self)
        except Exception as e:
            await self.handle_error(ctx, e)

    async def handle_error(self, interaction, exception):
        traceback_msg = ''.join(traceback.format_exception(type(exception), exception, exception.__traceback__))
        error_message = f"An error occurred: {exception}\n\n```{traceback_msg}```"
        print(traceback_msg)
        await interaction.response.send_message(error_message, ephemeral=True)


class MaterialsButton(discord.ui.View):
    def __init__(self, shop_data, quest_data, user_id, guild_id, original_embed=None):
        super().__init__(timeout=None)
        self.shop_data = shop_data
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.page = 0
        self.items_per_page = 5
        self.max_pages = (len(shop_data["Materials"]) - 1) // self.items_per_page + 1
        self.original_embed = original_embed  # Store the original embed
        self.materials_dict = {material['name']: material['emoji'] for material in self.shop_data.get("Materials", [])}

    async def update_view(self):
        self.clear_items()  # Clear all buttons

        # Check if all materials are sufficient
        material_checks = await asyncio.gather(*(self.check_material_indicator(material) for material in self.shop_data["Materials"]))

        # Create the Buy button and check if it's enabled
        if all(material_checks):
            buy_button = discord.ui.Button(style=discord.ButtonStyle.blurple, label='Buy', custom_id='buy_button', row=0, disabled=False)
            buy_button.callback = self.buy_tool_callback
            self.add_item(buy_button)  # Add the Buy button at the top
        else:
            buy_button = discord.ui.Button(style=discord.ButtonStyle.grey, label='Buy', custom_id='buy_button', row=0, disabled=True)
            self.add_item(buy_button)  # Add disabled Buy button

        # Add the material buttons below the Buy button
        start_index = self.page * self.items_per_page
        end_index = start_index + self.items_per_page
        materials = self.shop_data["Materials"][start_index:end_index]

        for material in materials:
            try:
                name = material.get("name", "Unknown Material")
                emoji = material.get("emoji", "")
                material_count = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, name)
                material_button = discord.ui.Button(
                    style=discord.ButtonStyle.green,
                    emoji=emoji,
                    label=f'{material_count}',
                    custom_id=name,
                    row=1
                )
                material_button.callback = self.material_callback
                self.add_item(material_button)
            except Exception as e:
                traceback.print_exc()

        # Add pagination buttons at the bottom
        if self.page > 0:
            prev_button = discord.ui.Button(emoji='⬅️', style=discord.ButtonStyle.primary, custom_id='prev_page', row=2)
            prev_button.callback = self.prev_page_callback
            self.add_item(prev_button)

        if self.page < self.max_pages - 1:
            next_button = discord.ui.Button(emoji='➡️', style=discord.ButtonStyle.primary, custom_id='next_page', row=2)
            next_button.callback = self.next_page_callback
            self.add_item(next_button)

    async def refresh_embed(self, interaction: discord.Interaction):
        tool_name = self.original_embed.title
        tool = next((t for t in self.shop_data.get("Spy Tools", []) if t.get("name") == tool_name), None)

        if not tool:
            await interaction.response.send_message("Spy Tool not found.", ephemeral=True)
            return

        emoji = tool.get("emoji", "")
        description = tool.get("description", "No description available.")
        materials_list = "\n".join([await self.format_materials(item) for item in tool.get("materials", [])])
        user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

        shop_embed = discord.Embed(title=f"{tool_name}", description=f'{emoji} {description}', color=primary_color())
        shop_embed.add_field(name="Materials", value=materials_list or "No materials needed", inline=False)
        user_balance = "{:,}".format(user_balance)
        shop_embed.set_footer(text=f"Stella Points: {user_balance}")

        await self.update_view()
        await interaction.response.edit_message(embed=shop_embed, view=self)

    async def check_material_indicator(self, material):
        material_name = material.get('name', '')
        required_quantity = material.get('quantity', 0)
        user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, material_name) or 0
        return user_quantity >= required_quantity

    async def material_callback(self, interaction: discord.Interaction):
        try:
            material_name = interaction.data["custom_id"]
            material = next((m for m in self.shop_data["Materials"] if m.get("name") == material_name), None)

            if not material:
                await interaction.response.send_message("Material not found.", ephemeral=True)
                return

            price = material.get("price", 0)
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

            if user_balance >= price:
                await self.quest_data.add_item_to_inventory(self.guild_id, self.user_id, material_name, 1)
                spent = -price
                await self.quest_data.add_balance(self.user_id, self.guild_id, spent)

                # Refresh the embed with updated inventory
                await self.refresh_embed(interaction)
            else:
                await interaction.response.send_message(f"You do not have enough points to purchase {material_name}.", ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    async def buy_tool_callback(self, interaction: discord.Interaction):
        try:
            tool_name = self.original_embed.title
            tool = next((t for t in self.shop_data.get("Spy Tools", []) if t.get("name") == tool_name), None)

            if not tool:
                await interaction.response.send_message("Spy Tool not found.", ephemeral=True)
                return

            # Check if user has enough materials
            for material in tool.get("materials", []):
                material_name = material.get('material', '')
                required_quantity = material.get('quantity', 0)
                user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, material_name) or 0

                if user_quantity < required_quantity:
                    await interaction.response.send_message(f"Not enough {material_name}.", ephemeral=True)
                    return

            # Deduct materials and add the tool to inventory
            for material in tool.get("materials", []):
                material_name = material.get('material', '')
                required_quantity = material.get('quantity', 0)
                await self.quest_data.add_item_to_inventory(self.guild_id, self.user_id, material_name, -required_quantity)

            # Add tool to inventory
            await self.quest_data.add_tool_to_inventory(self.guild_id, self.user_id, tool_name, 1)

            # Call update_view after buying
            await self.update_view()

            await interaction.response.send_message(f"{tool_name} purchased successfully!", ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    async def get_user_inventory_count(self, material_name):
        # Retrieve the user's inventory count for a given material from quest_data
        material_count = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, material_name)
        return material_count
    
    async def format_materials(self, item):
        material_name = item.get('material', '')
        required_quantity = item.get('quantity', 0)
        user_quantity = await self.get_user_inventory_count(material_name) or 0

        if user_quantity == 0:
            indicator_emoji = "<:red:1261639413943762944> "  # Red
        elif user_quantity < required_quantity:
            indicator_emoji = "<:yellow:1261639412253724774> "  # Yellow
        else:
            indicator_emoji = "<:green:1261639410181476443> "  # Green

        return f"{indicator_emoji} : {self.materials_dict.get(material_name, '')} - {user_quantity}/{required_quantity}"

    async def prev_page_callback(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            await self.update_view()
            await interaction.response.edit_message(view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        if self.page < self.max_pages - 1:
            self.page += 1
            await self.update_view()
            await interaction.response.edit_message(view=self)

            
            
class SpyToolSelect(discord.ui.Select):
    def __init__(self, shop_data, materials_dict, quest_data, user_id, guild_id):
        spy_tools = shop_data.get("Spy Tools", [])
        options = [
            discord.SelectOption(label=f"{tool.get('emoji', '')} {tool.get('name', 'Unknown Item')}", value=tool.get('name', 'Unknown Item'))
            for tool in spy_tools
        ]
        super().__init__(placeholder="Select a Spy Tool", options=options)
        self.shop_data = shop_data
        self.materials_dict = materials_dict
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_tool_name = self.values[0]
            tool = next((t for t in self.shop_data.get("Spy Tools", []) if t.get("name") == selected_tool_name), None)

            if not tool:
                await interaction.response.send_message("Spy Tool not found.", ephemeral=True)
                return

            emoji = tool.get("emoji", "")
            description = tool.get("description", "No description available.")
            materials_list = "\n".join([await self.format_materials(item) for item in tool.get("materials", [])])

            # Create the embed and send it
            initial_embed = discord.Embed(
                title=f"{selected_tool_name}",
                description=f'{emoji} {description}',
                color=primary_color()
            )
            initial_embed.add_field(name="Materials", value=materials_list or "No materials needed", inline=False)
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_balance = "{:,}".format(user_balance)            
            initial_embed.set_footer(text=f"Stella Points: {user_balance}")


            # Create MaterialsButton view
            materials_button_view = MaterialsButton(self.shop_data, self.quest_data, self.user_id, self.guild_id, original_embed=initial_embed)
            await materials_button_view.update_view()

            # Send the initial embed with buttons
            await interaction.response.send_message(embed=initial_embed, view=materials_button_view, ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    async def get_user_inventory_count(self, material_name):
        # Retrieve the user's inventory count for a given material from quest_data
        material_count = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, material_name)
        return material_count

    async def format_materials(self, item):
        material_name = item.get('material', '')
        required_quantity = item.get('quantity', 0)
        user_quantity = await self.get_user_inventory_count(material_name) or 0

        if user_quantity == 0:
            indicator_emoji = "<:red:1261639413943762944> "  # Red
        elif user_quantity < required_quantity:
            indicator_emoji = "<:yellow:1261639412253724774> "  # Yellow
        else:
            indicator_emoji = "<:green:1261639410181476443> "  # Green

        return f"{indicator_emoji} : {self.materials_dict.get(material_name, '')} - {user_quantity}/{required_quantity}"
  
    
    
    
    
    
    
def setup(bot):
    bot.add_cog(Quest_Data(bot))
    bot.add_cog(Quest(bot))
    bot.add_cog(Quest_Slash(bot))
