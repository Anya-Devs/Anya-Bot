import traceback
import re
import typing
from datetime import datetime, timedelta
import random

from Imports.discord_imports import *
from Data.const import Quest_Progress, error_custom_embed, primary_color, QuestEmbed, Quest_Prompt, Quest_Completed_Embed, AnyaImages

from Imports.log_imports import *
import motor.motor_asyncio
from pymongo.errors import PyMongoError
import os





class Quest_View(View):
    def __init__(self, bot, quests, ctx, page=0, filtered_quests=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.quests = quests
        self.filtered_quests = filtered_quests if filtered_quests is not None else quests
        self.ctx = ctx
        self.page = page
        self.max_pages = min((len(self.filtered_quests) + 2) // 3, 2)  # Calculate max pages, with a maximum of 2 pages

        # Add Quest_Select_Filter regardless of page
        self.add_item(Quest_Select_Filter(bot, quests, ctx))  # Pass original quests list

        # Add Quest_Select if page > 1
        if self.page < self.max_pages - 1:
            self.add_item(Quest_Select(bot, self.filtered_quests, ctx, self.max_pages))

        # Add Previous and Next buttons based on page
        if self.page > 0:
            self.add_item(QuestButton("Previous", discord.ButtonStyle.primary, "previous", bot, self.filtered_quests, ctx, self.page))
        if self.page < self.max_pages - 1:
            self.add_item(QuestButton("Next", discord.ButtonStyle.primary, "next", bot, self.filtered_quests, ctx, self.page))

    async def generate_embeds(self):
        start_index = self.page * 2
        end_index = start_index + 2
        embeds = []
        
        for quest in self.filtered_quests[start_index:end_index]:
            quest_id = quest['quest_id']
            progress = quest['progress']
            times = quest['times']
            action = quest['action']
            method = quest['method']
            content = quest['content']
            reward = quest['reward']
            channel = self.bot.get_channel(quest['channel_id'])

            if re.match(r'^<:\w+:\d+>$', content):
                emoji_id = int(re.findall(r'\d+', content)[0])
                emoji = discord.utils.get(self.bot.emojis, id=emoji_id)
                if emoji:
                    content = str(emoji)
            elif method == 'message':
                content = f"`{content}`"

            progress_bar = await Quest_Progress.generate_progress_bar(progress / times, self.bot)
            
            reward_emoji_id = 1247800150479339581
            reward_emoji = discord.utils.get(self.bot.emojis, id=reward_emoji_id)
            
            objective = f"{action.title()} - {method.title()}: {content}"


            embed = discord.Embed()
            embed.add_field(name=f'Quest {quest_id}', value=objective, inline=True)
            embed.add_field(name="Location", value=channel.mention, inline=True)

       
            embed.add_field(name=" ", value=" ", inline=False)
            embed.add_field(name='Progress', value=f'{progress_bar} {progress}/{times} ', inline=True)

            if reward:
             embed.add_field(name="Reward", value=f"{reward_emoji} `{reward} stp`", inline=True)



            embeds.append(embed)

        return embeds
    
class Quest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    @commands.command(name='quest', aliases=['q'])
    async def quest(self, ctx, test=None):
        logger.debug("Quest command invoked.")
        if test:
            author = ctx.author
            guild_id = str(ctx.guild.id)
            content = await self.quest_data.generate_random_quest_content(self.bot, author, guild_id)
            await ctx.send(str(content))
            return

        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)

            user_exists = await self.quest_data.find_user_in_server(user_id, guild_id)
            
            if not user_exists:
                prompt_embed = await Quest_Prompt.get_embed(self.bot)
                await ctx.reply(embed=prompt_embed, view=Quest_Button(self.bot, ctx))
                return

            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)

            if quests:
                view = Quest_View(self.bot, quests, ctx)
                embeds = await view.generate_embeds()
                
                if len(quests) > 0:  # Check if there are any embeds generated
                 if len(quests) > 2:
                    await ctx.reply(embeds=embeds, view=view)  # Send first 2 embeds
                 else:
                  await ctx.reply(embeds=embeds)  # Send all embeds

            else:
                no_quest_embed = await QuestEmbed.get_no_quest_embed()
                await ctx.reply(embed=no_quest_embed)
                
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, ctx, error_message, title="Quest Fetch Error")
            
    @commands.command(name='stars', aliases=['bal','points','balance'])
    async def balance(self, ctx, method=None, amount: int = None, member: discord.Member = None):
     user_id = str(ctx.author.id)
     guild_id = str(ctx.guild.id)
     if member is None:
        member = ctx.author
        
     try:
        # Check if the command includes the "add" flag
        if method == "add":
            # Check if the user has administrator permissions
            if ctx.author.id == 1030285330739363880:
                await self.quest_data.add_balance(str(member.id), guild_id, amount)
                amount_with_commas = "{:,}".format(amount)  # Add commas to amount
                await ctx.send(f":white_check_mark: Successfully added {amount_with_commas} balance to {member.display_name}'s account.")
            else:
                await ctx.send("You don't have permission to use this command to add balance to other users.")
        else:
            if member is None and amount is None:
                # Ensure the user has a balance
                await self.quest_data.initialize_balance(user_id, guild_id)

            # Retrieve and display the user's balance
            balance = await self.quest_data.get_balance(user_id, guild_id)
            balance_with_commas = "{:,}".format(balance)  # Add commas to balance
            await ctx.send(f"Your balance: {balance_with_commas} Stella Points")

     except Exception as e:
        # Log the error
        logger.error(f"An error occurred in the balance command: {e}")
        # Send a message to the user indicating an error occurred
        await ctx.send("An error occurred while processing your request. Please try again later.")

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
            embeds = await view.generate_embeds()
            await interaction.response.edit_message(embeds=embeds, view=view)
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, self.ctx, error_message, title="Quest Fetch Error")

class Quest_Select_Filter(Select):
    def __init__(self, bot, quests, ctx):
        methods = list(set(quest['method'] for quest in quests))
        options = [
            discord.SelectOption(label=method.title(), value=method)
            for method in methods
        ]
        options.insert(0, discord.SelectOption(label="All", value="all"))  # Add an option to show all quests
        super().__init__(placeholder="Filter...", options=options)
        self.bot = bot
        self.quests = quests
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
     try:
        selected_method = self.values[0]
        if selected_method == "all":
            print('All')
            filtered_quests = None  # Set filtered_quests to None to indicate all quests
        else:
            filtered_quests = [quest for quest in self.quests if quest['method'] == selected_method]

        view = Quest_View(self.bot, self.quests, self.ctx, filtered_quests=filtered_quests)
        embeds = await view.generate_embeds()
        await interaction.response.edit_message(embeds=embeds, view=view)
     except Exception as e:
        error_message = "An error occurred while fetching quests."
        logger.error(f"{error_message}: {e}")
        traceback.print_exc()
        await error_custom_embed(self.bot, self.ctx, error_message, title="Quest Fetch Error")

        


class QuestButton(discord.ui.Button):
    def __init__(self, label, style, custom_id, bot, quests, ctx, page):
        super().__init__(label=label, style=style, custom_id=custom_id)
        self.bot = bot
        self.quests = quests
        self.ctx = ctx
        self.page = page

    async def callback(self, interaction: discord.Interaction):
        if self.custom_id == "previous":
            self.page -= 1
        elif self.custom_id == "next":
            self.page += 1
        view = Quest_View(self.bot, self.quests, self.ctx, self.page)  # Change to Quest_View
        embeds = await view.generate_embeds()  # Await the method call
        await interaction.response.edit_message(embeds=embeds, view=view)



            
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
        try:
            added = await self.add_user_to_server()
            
            
            if added:
                embed = await QuestEmbed.get_agree_confirmation_embed(self.bot, button.user)
                
                await button.response.send_message("You have been added!", embed=embed, ephemeral=True)
                await button.followup.delete_message(button.message.id)

                button_user = button.user
                guild_id = str(button.guild.id)
                
                await self.quest_data.add_balance(button_user, guild_id, 0)
                
                for _ in range(10):
                                logger.debug("Adding new quest")
                                await self.quest_data.add_new_quest(guild_id, button_user)


            else:
                await button.response.send_message("You are already part of the game!", ephemeral=True)
                await button.followup.edit_message(button.message.id,view=None)
        except Exception as e:
            error_message = "An error occurred while processing the accept button."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, self.ctx, error_message, title="Button Error")

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
        self.quest_content_file = 'Data/quest_content.txt'

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
            
            logger.debug(f"Found {len(users_in_server)} users in server {guild_id}.")
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
            
            logger.debug(f"Found {len(users_with_quest)} users with quest ID {quest_id} in guild {guild_id}.")
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
                logger.debug(f"Found {len(quests)} quests for user {user_id} in guild {guild_id}.")
                if  len(quests) == 0:
                    return None
                return quests
                
            else:
                logger.debug("No server data found.")
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
                logger.debug(f"No server data found for user {user_id} in guild {guild_id}.")
                return 0
        except PyMongoError as e:
            logger.error(f"Error occurred while getting latest quest ID: {e}")
            if interaction:
                await self.handle_error(interaction, e, title="Latest Quest ID")
            return 0

    async def create_quest(self, guild_id: str, action: str, method: str, content: str, channel_id: int ,times: int, reward: int, interaction=None):
        try:
            # Calculate reward as a random value between 4 and 20 times the `times` value
            reward = random.randint(4, 20) * times
            
            # Ensure the reward is correctly set in the quest data
            quest_data = {
                'action': action,
                'method': method,
                'content': content,
                'channel_id': channel_id,
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

            users_in_server = await self.find_users_in_server(guild_id)
            if not users_in_server:
                raise ValueError("No users found in the server.")

            for user_id in users_in_server:
                quest_data['quest_id'] = quest_count + 1  # Set the quest_id to be the next number
                await self.insert_quest(guild_id, user_id, quest_data, interaction)

                # Update the quest_count to ensure unique quest IDs
                quest_count += 1
            logger.debug(f"Created quest for guild {guild_id} with action {action} and content {content}.")
            return quest_count

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
    
    async def get_most_active_channel(self, guild_id, threshold=5, message_limit=100):
     try:
        logger.debug('Entering get_most_active_channel function')
        guild = self.bot.get_guild(int(guild_id))
        if guild:
            logger.debug(f"Guild found: {guild.name} (ID: {guild_id})")
            channel_activity = {}
            for channel in guild.text_channels:
                # Check if the channel is accessible to all members or to a role with a significant number of members
                if channel.permissions_for(guild.default_role).send_messages:
                    logger.debug(f"Processing channel: {channel.name} (ID: {channel.id})")
                    # Count the number of messages and the number of members who have sent messages in the channel
                    message_count = 0
                    member_set = set()
                    async for message in channel.history(limit=message_limit):
                        message_count += 1
                        if not message.author.bot:
                            member_set.add(message.author.id)
                    member_count = len(member_set)
                    logger.debug(f"Message count for channel {channel.name} (ID: {channel.id}): {message_count}")
                    logger.debug(f"Member count for channel {channel.name} (ID: {channel.id}): {member_count}")
                    
                    channel_activity[channel.id] = (message_count, member_count)
            
            # Sort channels by member count and then by message count
            sorted_channels = sorted(channel_activity.items(), key=lambda x: (x[1][1], x[1][0]), reverse=True)
            if sorted_channels:
                logger.debug(f"Sorted channels by activity: {sorted_channels}")
                if len(sorted_channels) > threshold:
                    # Select a random channel from the top active channels
                    most_active_channel_id = random.choice(sorted_channels[:threshold])[0]
                    logger.debug(f"Randomly selected active channel from top {threshold}: {most_active_channel_id}")
                else:
                    most_active_channel_id = sorted_channels[0][0]  # Get the ID of the most active channel
                    logger.debug(f"Selected the most active channel: {most_active_channel_id}")
                return most_active_channel_id
            else:
                logger.debug('No active channels found')
                return None  # No active channels found
        else:
            logger.debug(f"Guild not found: {guild_id}")
            return None
     except Exception as e:
        logger.error(f"Error occurred while getting the most active channel: {e}")
        traceback.print_exc()
        return None

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
            content_exists = False
            for quest in existing_quests:
                if quest['content'] == content:
                    content_exists = True
                    break

            if not content_exists:
                break  # Exit the loop if the content is unique

        logger.debug(f"Generated quest content: {content}")

        # Get the most active channel in the guild
        channel_id = await self.get_most_active_channel(guild_id)
        logger.debug(f"Most active channel ID: {channel_id}")

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
            'times': times,
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
                logger.debug(f"Found quest with ID {quest_id} for user {member_id} in guild {guild_id}.")
                
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
        description="Set the maximum number of quests a user can have.",
    )
    async def set_quest_limit(
        self,
        interaction: discord.Interaction,
        limit: int
    ) -> None:
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


          
def setup(bot):
    bot.add_cog(Quest_Data(bot))
    bot.add_cog(Quest(bot))
    bot.add_cog(Quest_Slash(bot))
