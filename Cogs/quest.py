# Standard Library Imports
import os
import datetime
import random
import re
import uuid
import string
from datetime import timedelta, datetime
import typing
import traceback
import asyncio
import discord
import random
import logging
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont, ImageSequence


# Third-Party Library Imports
import json
import numpy as np
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
        self.shop_data = self.load_shop_data()

    def load_shop_data(self):
        """Loads shop data from the shop.json file."""
        try:
            with open(self.shop_file, 'r') as file:
                return json.load(file)
        except Exception as e:
            logger.error(f"Error loading shop data: {e}")
            return {}

    def get_tool_emoji(self, tool_name):
        """Fetches the emoji for a given tool name."""
        for category, items in self.shop_data.items():
            for item in items:
                if item['name'].lower() == tool_name.lower():
                    return item.get('emoji', '')
        return ''  # Return empty string if emoji not found

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
                # Initialize the ImageGenerator class
                image_generator = ImageGenerator(ctx, text='Here are the quests you need to complete. Each quest has a specific objective, progress, and reward. Click on the location link to navigate to the respective channel where the quest can be completed.')  # Pass the quest message as text to the image generator
                # Generate the image
                img = image_generator.create_image()
                # Save the image as a BytesIO object to send as an embed
                img_bytes = BytesIO()
                img.save(img_bytes, format='PNG')
                img_bytes.seek(0)  # Reset the pointer to the start of the BytesIO object

                image_generator = ImageGenerator(
                    ctx=ctx, 
                    text='Here are the quests you need to complete. Each quest has a specific objective, progress, and reward. Click on the location link to navigate to the respective channel where the quest can be completed.'
                )

                image_generator.save_image(file_path="Data/Images/generated_image.png")
                file = discord.File("Data/Images/generated_image.png", filename='image.png')
    
                # Set the image in the embed using the attachment URL
                embeds.set_image(url=f"attachment://image.png")
                


                # Send initial embed and view
                if embeds:
                    if len(quests) > 3:
                        # Multiple pages if there are more quests than fit on one page
                        await ctx.reply(embed=embeds, view=view, mention_author=False,  file=file)
                    else:
                        # Single embed if the number of quests fits on one page
                        await ctx.reply(embed=embeds, mention_author=False,  file=file)

            else:
                no_quest_message = "You have no quests."
                
                await ctx.reply(no_quest_message, view=Quest_Button1(self.bot, ctx), mention_author=False)
                
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await ctx.send(f"{error_message}")

    @commands.command(name='q_roles')
    async def q_roles(self, ctx, *role_mentions: discord.Role):
        """Command for admins to set or list roles that a target can get randomly."""
        
        # Check for required permissions
        if not (ctx.author.guild_permissions.manage_roles or discord.utils.get(ctx.author.roles, name="Anya Manager")):
            embed = discord.Embed(
                title="Permission Denied",
                description="You need the `Manage Roles` permission or the `Anya Manager` role to use this command.",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
            await ctx.reply(embed=embed, mention_author=False)
            return

        guild_id = str(ctx.guild.id)

        # If no roles are mentioned, list the currently set roles
        if not role_mentions:
            current_roles = await self.quest_data.get_roles_for_guild(guild_id)
            if current_roles:
                roles_list = "\n".join([f"<@&{role_id}>" for role_id in current_roles])
            else:
                roles_list = (
                    "No roles have been set yet.\n\n"
                    "**Admins can set roles using the command below:**\n"
                    "`...q_roles <@mention role1> <@mention role2> ... etc`"
                )

            embed = discord.Embed(
                title="",
                description=f"```Grants the target user a random role from the list of available roles in the server.```\n**Current Set Roles:**\n{roles_list}",
                color=primary_color(),
                timestamp=datetime.now()
            )
            embed.set_footer(text="Needed Tool: Key Chain Sheep",icon_url=self.bot.user.avatar)
            embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
            await ctx.reply(embed=embed, mention_author=False)
            return

        # Convert roles to IDs and store them in the database
        role_ids = [str(role.id) for role in role_mentions]
        await self.quest_data.store_roles_for_guild(guild_id, role_ids)

        # Success response embed
        embed = discord.Embed(
            title="Roles Set Successfully",
            description="Allows targets to get a random role.\n\nThe following roles have been set for this guild:",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
        
        # Add roles to the embed
        roles_list = "\n".join([f"{role.mention}" for role in role_mentions])
        embed.add_field(name="Roles", value=roles_list, inline=False)

        await ctx.reply(embed=embed, mention_author=False)
 
    @commands.command(name="inventory", aliases=["inv"]) 
    async def inventory(self, ctx):
     """Displays the user's tool inventory."""
     try:
        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        # Fetch the user's inventory from the database
        db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
        server_collection = db['Servers']

        user_data = await server_collection.find_one(
            {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
            {f'members.{user_id}.inventory.tool'}
        )

        inventory = user_data.get('members', {}).get(user_id, {}).get('inventory', {}).get('tool', {})

        if not inventory:
            await ctx.reply(
                f"{ctx.author.mention}, your inventory is empty! Start collecting tools to see them here.",
                mention_author=False
            )
            return

        # Prepare the embed
        embed = discord.Embed(
            title=f"{ctx.author.display_name}'s Inventory",
            description="Your current tool inventory:\n- ||Due to bugs, purchasing doesn't grant an item but only reserves a slot on first purchase.||",
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=ctx.author.avatar.url)

         # Add fields for each tool and its quantity, including emojis
        for tool in inventory.keys():
            try:
                # Fetch the unique tool ID
                un_tool_id = await self.quest_data.get_existing_tool_id(guild_id, user_id, tool)

                if not un_tool_id:
                    # Create a new unique tool ID if it doesn't exist
                    un_tool_id = await self.quest_data.create_un_tool_id(guild_id, user_id, tool)

                # Fetch the quantity for the tool
                quantity = await self.quest_data.get_quantity(guild_id, user_id, tool)
     

                emoji = self.get_tool_emoji(tool) or ""  # Default to empty string if emoji not found
                
                tool = str(tool)
                # Add field to embed
                embed.add_field(
                    name=f"{tool.title()}",
                    value=f"`{un_tool_id}` : \t{emoji}\t`x{quantity}`",
                    inline=False
                )
            except Exception as e:
                await ctx.reply(
                    f"{ctx.author.mention}, there was an issue processing `{tool}`. Please try again later.",
                    mention_author=False
                )
                logger.error(f"Error generating or fetching un_tool_id or quantity for {tool}: {e}")

        embed.set_footer(text="Inventory", icon_url=self.bot.user.avatar.url)

        # Send the embed
        await ctx.reply(embed=embed, mention_author=False)

     except Exception as e:
        await ctx.reply(f"An error occurred while fetching your inventory: {e}", mention_author=False)
        logger.error(f"Error in inventory command: {e}")
   
   
   
   
   
   
   
    @commands.command(name='stars', aliases=['bal', 'points', 'balance'])
    async def balance(self, ctx, method=None, amount: int = None, member: discord.Member = None):
        user_id = str(ctx.author.id)
        guild_id = str(ctx.guild.id)
        if member is None:
            member = ctx.author
            
        try:
            if method == "add":
                if ctx.author.id in [1030285330739363880, 1124389055598170182] :
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
        self.max_pages = (len(self.filtered_quests) + 2) // 3  # Calculate the total number of pages

        # Add quest filters and navigation buttons
        self.add_item(Quest_Select_Filter(bot, quests, ctx))
        if self.page < self.max_pages - 1:
            self.add_item(Quest_Select(bot, self.filtered_quests, ctx, self.max_pages))  # Add the Quest_Select button if there are more pages
        if self.page > 0:
            self.add_item(QuestButton("Previous", discord.ButtonStyle.primary, "previous", bot, self.filtered_quests, ctx, self.page))
        if self.page < self.max_pages - 1:
            self.add_item(QuestButton("Next", discord.ButtonStyle.primary, "next", bot, self.filtered_quests, ctx, self.page))

        # Add the "Fresh Start" button on the bottom row
        self.add_item(QuestButton("Fresh Start", discord.ButtonStyle.danger, "fresh_start", bot, self.filtered_quests, ctx, self.page))

    async def generate_messages(self):
        start_index = self.page * 3
        end_index = start_index + 3  # Always try to display 3 quests per page
        quests_to_display = self.filtered_quests[start_index:end_index]

        # Create a single embed for the current page
        embed = discord.Embed(
            color=primary_color()
        )
        embed.set_footer(text=f"{self.ctx.author.display_name}'s quests", icon_url=self.ctx.author.avatar)

        field_count = 0  # Track how many fields have been added
        index = start_index  # Start index for iterating over all filtered quests

        # Try to add up to 3 quests per page, replacing inaccessible quests
        while field_count < 3 and index < len(self.filtered_quests):
            quest = self.filtered_quests[index]
            index += 1  # Move to the next quest in the list

            quest_id = quest['quest_id']
            progress = quest['progress']
            times = quest['times']
            method = quest['method']
            content = quest['content']
            reward = quest['reward']

            # Get the channel using the channel ID
            channel = self.bot.get_channel(int(quest['channel_id']))

            # Generate instructions based on method
            if method == 'message':
                instruction = "Send: {0}".format(content.replace('\n', ' '))
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
            instructions_emoji = '📋'

            # Construct the channel link based on whether it's the current channel
            if channel:
                channel_link = f'[Go here](https://discord.com/channels/{self.ctx.guild.id}/{channel.id})' if channel.id != self.ctx.channel.id else 'In this channel'
            else:
                channel_link = f'Channel not found | Recommended: `/quest delete quest_id: {quest_id}`'  # Fallback in case the channel is not found

            message = (
                f"✦ Quest {quest_id} | {progress_bar} `{progress}/{times}`\n"  # Progress info
                f"├ {instructions_emoji} {channel_link} | **{instruction}**\n"
                f"└ {reward_emoji} Reward: `{reward} stp`"  # Reward and instruction
                f"\n\n"  # For spacing
            )

            # Check if the channel exists and if the member has required roles
            can_view_channel = True  # Default to True if channel does not exist
            if channel:
                overwrites = channel.overwrites
                can_view_channel = False
                for role, overwrite in overwrites.items():
                    if overwrite.read_messages and any(role in self.ctx.author.roles for role in [role]):
                        can_view_channel = True
                        break

            # Add the quest to the embed only if the user can view it
            if can_view_channel:
                embed.add_field(
                    name="",  # Field name remains blank
                    value=message,
                    inline=False
                )
                field_count += 1
            else:
                # Skip the quest and move to the next available one
                continue

        # If you want to set an image, here’s how you can handle it (optional):
        file = discord.File("Data/Images/generated_image.png", filename='image.png')
        embed.set_image(url=f"attachment://image.png")

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
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This is not your section.", ephemeral=True)
            return

        try:
            page_index = int(self.values[0])
            view = Quest_View(self.bot, self.quests, self.ctx, page=page_index, filtered_quests=self.quests)
            embed = await view.generate_messages()
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await self.ctx.send(f"{error_message}")

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
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This is not your section.", ephemeral=True)
            return

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
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This is not your section.", ephemeral=True)
            return

        embed = None  # Declare embed variable
        view = None  # Default to no view

        if self.custom_id == "previous":
            self.page -= 1
        elif self.custom_id == "next":
            self.page += 1
        elif self.custom_id == "fresh_start":
            # Call the delete all quests function
            success = await self.quest_data.delete_all_quests(self.ctx.guild.id, self.ctx.author)
            if success:
                embed = discord.Embed(
                    description=f":white_check_mark: All quests have been deleted for you {self.ctx.author.mention}. Starting fresh!",
                    color=discord.Color.green()
                )
                # Reset page and quest list after deletion
                self.page = 0
                self.quests = []  # Clear quests since they are all deleted
                # After fresh start, we don't need a view anymore
                view = None  # Remove the view after successful fresh start
            else:
                embed = discord.Embed(
                    description="You have no quests.",
                    color=discord.Color.red()
                )
                # If no quests exist, maintain the view and reset quests accordingly
                view = Quest_View(self.bot, self.quests, self.ctx, self.page)

        # Only call view.generate_messages() if fresh start wasn't successful
        if not embed:  
            view = Quest_View(self.bot, self.quests, self.ctx, self.page)
            embed = await view.generate_messages()

        # Edit the message to include the embed and updated view (even if the view is None)
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
                # If no redirect channels are found, edit the original message (instead of sending a new one)
                await button.response.edit_message(
                    content="No redirected channels found for this guild. Please set redirect channels before creating a new quest.\n"
                            "> Ask a member with permission to manage channels or with the Anya Manager role to use the command: `...redirect <channels>`"
                )
                return  # Exit if no channels are set

            # Proceed to create new quests for the user
            button_user = button.user

            # Add the user to the guild's quest balance
            await self.quest_data.add_balance(button_user, guild_id, 0)

            # Add new quests for the user
            for _ in range(50):
                logger.debug("Adding new quest")
                await self.quest_data.add_new_quest(guild_id, button_user, chance=100)

            # Edit the original message to notify the user that new quests have been created
            await button.response.edit_message(
                content=f"Successfully created new quests for you, {button_user.mention}!",
                view=None
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

            
            
class ImageGenerator:
    def __init__(self, ctx, text):
        """Initialize the ImageGenerator with cog-specific data and load resources."""
        # Configurable values
        self.font_path_header = "Data/commands/help/menu/initial/style/assets/font/valentine.ttf"
        self.font_path_base = "Data/commands/help/menu/initial/style/assets/font/dizhitl-italic.ttf"
        self.character_path = "Data/commands/help/menu/initial/style/assets/character_quest.png"
        self.background_path = "Data/commands/help/menu/initial/style/assets/background.png"
 
        # Font sizes
        self.header_font_size = 35
        self.base_font_size = 11

        # Font colors
        self.header_font_color = "white"
        self.base_font_color = "black"

        # Character image scale
        self.character_scale = 0.4

        # Text content
        self.header_text = 'Anya Quest!'
        self.description_text = text

        # Layout positions
        self.character_pos = (5, 5)
        self.text_x_offset = 10
        self.text_y_offset = 25
        self.text_spacing = 20
        self.text_box_margin = 20  # Margin for text box

        # Color replacements
        self.color_replacements_map = {
            # Add your custom mappings here
        }

        # Load fonts and images
        self._load_resources()
        self._apply_color_replacements()

    def _load_resources(self):
        """Load the fonts and images required for generating the image."""
        try:
            self.header_font = ImageFont.truetype(self.font_path_header, self.header_font_size)
        except Exception:
            self.header_font = ImageFont.load_default()

        try:
            self.base_font = ImageFont.truetype(self.font_path_base, self.base_font_size)
        except Exception:
            self.base_font = ImageFont.load_default()

        self.character = Image.open(self.character_path).convert("RGBA")
        self.background = Image.open(self.background_path).convert("RGBA")

        # Resize character image
        self._resize_character()

    def _resize_character(self):
        """Resize the character image to a percentage of its original size."""
        new_width = round(self.character.width * self.character_scale)
        new_height = round(self.character.height * self.character_scale)
        self.character = self.character.resize((new_width, new_height))

    def _apply_color_replacements(self):
        """Replace specific colors in the background image."""
        bg_array = np.array(self.background).copy()

        for old_hex, replacement in self.color_replacements_map.items():
            old_color = tuple(int(old_hex[i:i+2], 16) for i in (0, 2, 4))
            lower_bound = np.array(old_color) - 10
            upper_bound = np.array(old_color) + 10

            if replacement == 'transparent':  # Replace with transparency
                mask = cv2.inRange(bg_array[:, :, :3], lower_bound, upper_bound)
                bg_array[mask > 0] = [0, 0, 0, 0]
            elif replacement.startswith('http'):  # Replace with image from URL
                replacement_img = self._download_image(replacement)
                replacement_img = replacement_img.resize((self.background.width, self.background.height))
                replacement_array = np.array(replacement_img)[:, :, :3]

                mask = cv2.inRange(bg_array[:, :, :3], lower_bound, upper_bound)
                bg_array[mask > 0, :3] = replacement_array[mask > 0]
            else:  # Replace with solid color
                replacement_color = tuple(int(replacement[i:i+2], 16) for i in (1, 3, 5))
                mask = cv2.inRange(bg_array[:, :, :3], lower_bound, upper_bound)
                bg_array[mask > 0, :3] = replacement_color

        self.background = Image.fromarray(bg_array, 'RGBA')

    def _wrap_text(self, text, max_width):
        """Wrap text to fit within the specified width."""
        lines = []
        words = text.split()
        current_line = []

        dummy_img = Image.new('RGBA', (1, 1))
        draw = ImageDraw.Draw(dummy_img)

        for word in words:
            current_line.append(word)
            line_width = draw.textlength(' '.join(current_line), font=self.base_font)
            if line_width > max_width:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        return '\n'.join(lines)

    def _draw_text(self, draw, text_x, text_y):
        """Draw all text on the image, ensuring it doesn't touch the edges."""
        # Draw header text
        draw.text((text_x, text_y), self.header_text, font=self.header_font, fill=self.header_font_color)
        text_y += self.header_font.size + self.text_spacing
        
        # Set the max width of the description text box
        text_box_width = self.background.width - text_x - self.text_box_margin * 2
        wrapped_text = self._wrap_text(self.description_text, text_box_width)
        draw.multiline_text((text_x + self.text_box_margin, text_y), wrapped_text, font=self.base_font, fill=self.base_font_color)

    def _download_image(self, url):
        """Download an image from a URL."""
        try:
            response = requests.get(url)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGBA")
        except Exception as e:
            print(f"Error downloading image: {e}")
            raise

    def create_image(self):
        """Generate the complete image with the background, character, and text."""
        bg = self.background.copy()
        draw = ImageDraw.Draw(bg)
        character_x, character_y = self.character_pos
        bg.paste(self.character, (character_x, character_y), self.character)

        # Use the adjusted text_x with proper margin for wrapping
        text_x = self.character.width + self.text_x_offset - 45

        text_y = self.text_y_offset
        self._draw_text(draw, text_x, text_y)

        return bg

    def save_image(self, file_path):
        """Save the generated image to the given file path."""
        img = self.create_image()
        img.save(file_path)
        return file_path

    def show_image(self):
        """Display the generated image."""
        img = self.create_image()
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        display(IPImage(img_bytes.getvalue()))


            
            
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
            
    async def store_roles_for_guild(self, guild_id, role_ids):
        """Store or override the roles for the guild."""
        collection = self.mongoConnect[self.DB_NAME].roles
        guild_data = await collection.find_one({"guild_id": guild_id})
        
        if guild_data:
            # Update the existing roles
            await collection.update_one(
                {"guild_id": guild_id},
                {"$set": {"roles": role_ids}}
            )
        else:
            # Insert a new document for the guild if it doesn't exist
            await collection.insert_one({"guild_id": guild_id, "roles": role_ids})
    
    async def get_roles_for_guild(self, guild_id):
        """Retrieve the stored roles for the guild."""
        collection = self.mongoConnect[self.DB_NAME].roles
        guild_data = await collection.find_one({"guild_id": guild_id})
        if guild_data:
            return guild_data['roles']
        return []

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
        
    async def get_existing_tool_id(self, guild_id: str, user_id: str, tool_name: str) -> str:
        """Fetches the existing un_tool_id for the tool from the inventory."""
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            user_data = await server_collection.find_one(
                {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
                {f'members.{user_id}.inventory.tool.{tool_name}': 1}
            )

            # Check if the tool has an existing un_tool_id
            tool_data = user_data.get('members', {}).get(user_id, {}).get('inventory', {}).get('tool', {}).get(tool_name, {})
            return tool_data.get('un_tool_id', None)
        except PyMongoError as e:
            logger.error(f"Error occurred while getting existing tool ID: {e}")
            return None
            
    async def get_quantity(self, guild_id: str, user_id: str, material_name: str) -> int:
     """
     Retrieves the quantity of a specific material in a user's inventory.
     If the material does not exist, returns 0.
     """
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']

        # Fetch the user's inventory and get the quantity for the specific material
        user_data = await server_collection.find_one(
            {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
            {f'members.{user_id}.inventory.tool.{material_name}.quantity': 1}
        )

        # Retrieve the quantity or default to 0 if not found
        quantity = user_data.get('members', {}).get(user_id, {}).get('inventory', {}).get('tool', {}).get(material_name, {}).get('quantity', 0)
        return quantity
     except PyMongoError as e:
        logger.error(f"Error occurred while retrieving quantity for {material_name}: {e}")
        raise e
     
    async def add_tool_to_inventory(self, guild_id: str, user_id: str, material_name: str, quantity: int) -> None:
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']

        # Increment the material quantity while ensuring the structure includes a `quantity` field
        await server_collection.update_one(
            {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
            {
                '$inc': {f'members.{user_id}.inventory.tool.{material_name}.quantity': quantity}
            },
            upsert=True
        )
        await self.get_quantity(guild_id, user_id, material_name)

     except PyMongoError as e:
        logger.error(f"Error occurred while adding item to inventory: {e}")
        raise e

    async def remove_tool_from_inventory(self, guild_id: str, user_id: str, tool_name: str) -> None:
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']

        # Fetch the current quantity of the tool in the user's inventory
        current_quantity = await self.get_quantity(guild_id, user_id, tool_name)

        if current_quantity > 0:
            # Decrease the quantity by 1
            await server_collection.update_one(
                {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
                {'$inc': {f'members.{user_id}.inventory.tool.{tool_name}.quantity': -1}},
                upsert=True
            )
        else:
            logger.warning(f"{user_id} does not have the tool `{tool_name}` in their inventory.")
            await server_collection.update_one(
                {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
                {'$set': {f'members.{user_id}.inventory.tool.{tool_name}.quantity': 0}},
                upsert=True
            )

     except PyMongoError as e:
        logger.error(f"Error occurred while removing tool from inventory: {e}")
        raise e 
     
    async def create_un_tool_id(self, guild_id, user_id, tool):
     """Create a new unique tool ID for the user and tool."""
    
     # Helper function to generate a short, 6-digit unique ID for the tool
     def generate_short_uuid():
        return ''.join(random.choices(string.digits, k=6) + 1000)  # Only digits now

     db = self.mongoConnect[self.DB_NAME]
     server_collection = db['Servers']

     try:
        # Generate a new 6-digit ID
        un_tool_id = generate_short_uuid()

        # Create the tool data with the generated un_tool_id
        tool_data = {'un_tool_id': un_tool_id}

        # Use upsert to ensure the tool is added with the generated un_tool_id
        result = await server_collection.update_one(
            {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
            {'$set': {f'members.{user_id}.inventory.tool.{tool}': tool_data}},
            upsert=True  # Ensures the tool is inserted if missing
        )

        # Debugging info
        logger.debug(f"Generated new un_tool_id: {un_tool_id} for tool '{tool}'")
        logger.debug(f"Database update result: {result.raw_result}")
        
        return un_tool_id
     except Exception as e:
        logger.error(f"Error in create_un_tool_id for tool '{tool}' (guild: {guild_id}, user: {user_id}): {e}")
        raise  # Re-raise the exception after logging it

    
     
    async def get_un_tool_id(self, guild_id, user_id, tool):
        """Fetch the unique tool ID for the user and tool."""
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']

        # Check if the tool exists in the user's inventory
        user_tool_data = await server_collection.find_one(
            {'guild_id': guild_id, f'members.{user_id}.inventory.tool.{tool}': {'$exists': True}},
            {f'members.{user_id}.inventory.tool.{tool}': 1}
        )

        if user_tool_data:
            try:
                # Access the tool data safely
                tool_data = user_tool_data['members'][user_id]['inventory']['tool'].get(tool)

                if isinstance(tool_data, dict) and 'un_tool_id' in tool_data:
                    # Return the un_tool_id if it exists
                    return tool_data['un_tool_id']

                # If the un_tool_id doesn't exist, handle the case separately
                logger.error(f"Tool {tool} does not have an 'un_tool_id' or is in an unexpected format.")
                return None

            except KeyError as e:
                logger.error(f"KeyError: Missing key in user_tool_data for {guild_id} and {user_id}: {e}")
                return None
        else:
            # If the tool does not exist in the user's inventory
            logger.error(f"Tool {tool} does not exist in the inventory.")
            return None
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
            'times': times if method not in ('message', 'emoji') else random.randint(1,3), # Updated
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
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']

        # Find the guild document by guild_id
        guild_document = await server_collection.find_one({'guild_id': str(guild_id)})

        if not guild_document:
            logger.debug(f"No guild found with ID {guild_id}.")
            return False  # No guild data found

        # Extract the members data
        members_data = guild_document.get('members', {})

        # Check if the user exists in the members data
        if user_id not in members_data:
            logger.debug(f"User ID {user_id} not found in the guild {guild_id}.")
            return False  # No quests to delete if user does not exist

        user_data = members_data[user_id]
        quests = user_data.get('quests', [])

        if not quests:
            logger.debug("No quests found for the user. Nothing to delete.")
            return False  # No quests to delete for the user

        # Loop through and delete each quest individually
        for quest in quests:
            quest_id = quest.get('quest_id')
            deletion_success = await self.delete_quest(guild_id, quest_id, message_author)
            
            if deletion_success:
                logger.debug(f"Deleted quest_id: {quest_id} for user_id: {user_id} in guild_id: {guild_id}")
            else:
                logger.warning(f"Failed to delete quest_id: {quest_id} for user_id: {user_id} in guild_id: {guild_id}")

        logger.info(f"Successfully deleted all quests for user_id: {user_id} in guild_id: {guild_id}")
        return True  # Return True once all quests are deleted

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
    
            # Fetch the user's current quantity of the purchased tool
            quantity = await self.quest_data.get_quantity(self.guild_id, self.user_id, tool_name)

            # Create the success embed message
            success_embed = discord.Embed(
             title="Purchase Successful",
             description=f"- {tool_name} has been purchased successfully!\n> {tool.get('emoji', '')} : `x{quantity}`",
             color=primary_color()  # Use the primary color for the embed
            )

            

            # Send the embed response
            await interaction.response.send_message(embed=success_embed, ephemeral=True)

          
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
            discord.SelectOption(emoji=f"{tool.get('emoji', '')}", label=f"{tool.get('name', 'Unknown Item')}", value=tool.get('name', 'Unknown Item'))
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
            # Check if the user who clicked the select is the same as the author
            id_1 = int(self.user_id)
            id_2 = int(interaction.user.id)
            if id_1 != id_2:
                await interaction.response.send_message("This is not your section.", ephemeral=True)
                return

            selected_tool_name = self.values[0]
            tool = next((t for t in self.shop_data.get("Spy Tools", []) if t.get("name") == selected_tool_name), None)

            if not tool:
                await interaction.response.send_message("hey, that's not yours! go awayyy!", ephemeral=True)
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