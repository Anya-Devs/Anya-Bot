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


class Quest_Select(Select):
    def __init__(self, bot, quests, ctx, max_pages):
        self.bot = bot
        self.quests = quests
        self.ctx = ctx
        self.max_pages = max_pages
        options = []

        for i in range(max_pages):
            start_index = i * 3
            end_index = min((i + 1) * 3, len(quests))
            label = f"Page {i+1}"
            # description = f"View quests {start_index + 1} to {end_index} out of {len(quests)}"
            options.append(discord.SelectOption(label=label, value=str(i)))

        super().__init__(placeholder="Select page...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
     try:
        page_index = int(self.values[0])
        view = Quest_View(self.bot, self.quests, self.ctx, page=page_index)
        embeds = await view.generate_embeds()
        await interaction.response.edit_message(embeds=embeds, view=view)
     except Exception as e:
        error_message = "An error occurred while fetching quests."
        logger.error(f"{error_message}: {e}")
        traceback.print_exc()
        await error_custom_embed(self.bot, ctx, error_message, title="Quest Fetch Error")


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

class Quest_View(View):
    def __init__(self, bot, quests, ctx, page=0):
        super().__init__(timeout=None)
        self.bot = bot
        self.quests = quests
        self.ctx = ctx
        self.page = page
        self.max_pages = (len(quests) + 2) // 3  # Calculate max pages, showing 3 quests per page
        
        self.add_item(Quest_Select(bot, quests, ctx, self.max_pages))

        if self.page > 0:
            self.add_item(QuestButton("Previous", discord.ButtonStyle.primary, "previous", bot, quests, ctx, self.page))
        if self.page < self.max_pages - 1:
            self.add_item(QuestButton("Next", discord.ButtonStyle.primary, "next", bot, quests, ctx, self.page))


    async def generate_embeds(self):
        start_index = self.page * 3
        end_index = start_index + 3
        embeds = []
        """
         author_embed = discord.Embed()
         author_embed.set_author(name=f"{self.ctx.author.display_name}'s quests", icon_url=self.ctx.author.avatar.url)
         embeds.append(author_embed)
        """

        for quest in self.quests[start_index:end_index]:
            quest_id = quest['quest_id']
            progress = quest['progress']
            times = quest['times']
            action = quest['action']
            method = quest['method']
            content = quest['content']
            channel = self.bot.get_channel(quest['channel_id'])

            if re.match(r'^<:\w+:\d+>$', content):
                emoji_id = int(re.findall(r'\d+', content)[0])
                emoji = discord.utils.get(self.bot.emojis, id=emoji_id)
                if emoji:
                    content = str(emoji)
            elif method == 'message':
                content = f"`{content}`"

            progress_bar = await Quest_Progress.generate_progress_bar(progress / times, self.bot)

            embed = discord.Embed()
            embed.add_field(name="\n", value=f'**Mission**: {content}\n`{progress}/{times}` {progress_bar}', inline=True)
            embed.add_field(name="Location", value=channel.mention, inline=True)
            embed.set_footer(text=f"Quest ID: {quest_id}\nKey: {action.title()} {method.title()}")
            embeds.append(embed)
            
        """
         last_embed = discord.Embed()
         last_embed.set_footer(text='Server Quest\n', icon_url=AnyaImages.show_quest_anya)
         last_embed.timestamp = datetime.now()
         embeds.append(last_embed)
        """

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
                await ctx.reply(embeds=embeds, view=view)
            else:
                no_quest_embed = await QuestEmbed.get_no_quest_embed()
                await ctx.reply(embed=no_quest_embed)
                
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, ctx, error_message, title="Quest Fetch Error")

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
                embed = await QuestEmbed.get_agree_confirmation_embed()
                await button.response.send_message("You have been added!", ephemeral=True)

                await button.followup.edit_message(button.message.id,embed=embed, view=None)
                button_user = button.user
                
                guild_id = str(button.guild.id)
                for _ in range(3):
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

    async def create_new_quest_for_all(
        self,
        guild_id: str,
        action: str,
        method: str,
        channel_id: int,
        times: int,
        content: str,
        interaction=None):
        
        try:
            logger.debug('create_new_quest_for_all has been activated')
            await self.validate_input(guild_id=guild_id, action=action, method=method, channel_id=channel_id, times=times, content=content)
            users_in_server = await self.find_users_in_server(guild_id)
            logger.debug(f"Found {len(users_in_server)} users in server.")
            
            new_quest_id = None  # Initialize new_quest_id outside the loop
            
            for user_id in users_in_server:
                latest_quest_id = await self.get_latest_quest_id(guild_id, user_id)
                new_quest_id = latest_quest_id + 1 if latest_quest_id is not None else 1
                
                quest_data = {
                    'quest_id': new_quest_id,
                    'action': action,
                    'method': method,
                    'channel_id': channel_id,
                    'times': times,
                    'content': content,
                    'progress': 0  # Initialize progress to 0
                }
                logger.debug(f"Creating quest for user_id: {user_id}, guild_id: {guild_id}, quest_data: {quest_data}")
                await self.insert_quest(guild_id, user_id, quest_data)
                logger.debug(f"Quest created for user_id: {user_id}, guild_id: {guild_id}, quest_data: {quest_data}")
            
            # Return new_quest_id after the loop
            return new_quest_id  # Return the new quest_id
        
        except Exception as e:
            logger.error(f"Error occurred while creating new quest for all users: {e}")
            if interaction:
                await self.handle_error(interaction, e, title="Quest Creation for All")
    async def create_new_quest_person(
     self,
     user_id: str,
     guild_id: str,
     action: str,
     method: str,
     channel_id: int,
     times: int,
     content: str):
     try:
        latest_quest_id = await self.get_latest_quest_id(guild_id, user_id)
        new_quest_id = latest_quest_id + 1 if latest_quest_id is not None else 1

        quest_data = {
            'quest_id': new_quest_id,
            'action': action,
            'method': method,
            'channel_id': channel_id,
            'times': times,
            'content': content,
            'progress': 0  # Initialize progress to 0
        }
        logger.debug(f"Creating quest for user_id: {user_id}, guild_id: {guild_id}, quest_data: {quest_data}")
        await self.insert_quest(guild_id, user_id, quest_data)
        logger.debug(f"Quest created for user_id: {user_id}, guild_id: {guild_id}, quest_data: {quest_data}")

        return new_quest_id  # Return the new quest_id

     except Exception as e:
        logger.error(f"Error occurred while creating new quest for user {user_id}: {e}")
        return None

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
        # Check the random chance first
        if random.randint(1, 100) > chance:
            logger.debug("Random chance check failed. No quest will be created.")
            return None

        user_id = str(message_author.id)
        logger.debug(f"User ID: {user_id}")

        # Check quest limit
        quest_limit = await self.get_quest_limit(guild_id)
        existing_quests = await self.find_quests_by_user_and_server(user_id, guild_id)
        if existing_quests is not None and len(existing_quests) >= quest_limit:
            logger.debug("User has reached the quest limit. No quest will be created.")
            return None

        # Generate random times for the quest
        times = random.randint(1, 5)
        logger.debug(f"Random times selected: {times}")

        # Randomly choose method if not provided
        if method is None:
            method = random.choice(['message', 'reaction'])
        logger.debug(f"Method chosen: {method}")

        # Generate random quest content based on the method
        if method == 'message':
            content = await self.generate_random_quest_content(self.bot, message_author, guild_id)
        else:  # method == 'reaction'
            content = await self.generate_random_reaction_content(guild_id)
        if content is None:
            logger.error("Failed to generate random quest content.")
            return None
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

    @app_commands.command(
        name="create_quest",
        description="Create a new quest.",
    )
    @app_commands.describe(action='The action to perform for the quest. (e.g., send, receive)')
    @app_commands.describe(method='The method to use for the quest. (e.g., message, reaction)')
    @app_commands.describe(content='The content for the quest.')
    @app_commands.choices(action=[
        discord.app_commands.Choice(name='send', value='send'), 
        discord.app_commands.Choice(name='receive', value='receive'), 
    ])
    @app_commands.choices(method=[
        discord.app_commands.Choice(name='message', value='message'),
        discord.app_commands.Choice(name='reaction', value='reaction')
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
            quest_id = await self.quest_data.create_new_quest_for_all(guild_id, action.value, method.value, channel.id, times, content, interaction)
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

    @app_commands.command(
        name="delete_quest",
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
    @app_commands.command(
    name="remove_all_server_quests",
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

    @app_commands.command(
        name="set_quest_limit",
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
