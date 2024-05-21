import traceback
import re
import typing
from Imports.discord_imports import *
from Data.const import Quest_Progress, error_custom_embed, primary_color, QuestEmbed, Quest_Prompt

from Imports.log_imports import *
import motor.motor_asyncio
from pymongo.errors import PyMongoError
import os

class Quest_Data(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DB_NAME = 'Quest'

        # Initialize MongoDB connection
        mongo_url = os.getenv('MONGO_URI')
        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")
        self.mongoConnect = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        logger.debug("Quest_Data initialized with MongoDB connection.")

    async def handle_error(self, interaction, error, title):
        await error_custom_embed(self.bot, interaction, str(error), title=title)

    async def validate_input(self, **kwargs):
        for key, value in kwargs.items():
            if value is None or value == "":
                raise ValueError(f"{key} cannot be None or empty")

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
            await self.validate_input(**quest_data)
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']
            
            # Update the database to ensure 'members' field is a dictionary
            await server_collection.update_one(
                {'guild_id': guild_id},
                {'$set': {f'members.{user_id}': {}}},
                upsert=True
            )
            
            # Append the quest data to the appropriate spot
            await server_collection.update_one(
                {'guild_id': guild_id},
                {'$addToSet': {f'members.{user_id}.quests': quest_data}},
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
                    'content': content
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

    async def find_users_in_server(self, guild_id: str):
     try:
        db = self.mongoConnect[self.DB_NAME]
        server_collection = db['Servers']
        server_data = await server_collection.find_one({'guild_id': guild_id})
        if server_data:
            members_data = server_data.get('members', [])
            if isinstance(members_data, list):
                # Convert the list of member IDs to a dictionary with empty quest data
                members_data = {str(member_id): {'quests': []} for member_id in members_data}
                await server_collection.update_one(
                    {'guild_id': guild_id},
                    {'$set': {'members': members_data}},
                    upsert=True
                )
                logger.info(f"Converted 'members' data to dictionary format for guild {guild_id}.")
            users = list(members_data.keys())
            logger.debug(f"Found {len(users)} users in server {guild_id}.")
            return users
        else:
            logger.debug(f"No server data found for guild {guild_id}.")
            return []
     except PyMongoError as e:
        logger.error(f"Error occurred while finding users in server: {e}")
        return []
  
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




         
class Quest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    async def prompt_user_agreement(self, ctx):
        logger.debug("Prompting user for agreement.")
        try:
            prompt_embed = await Quest_Prompt.get_embed()
            prompt_message = await ctx.send(embed=prompt_embed)

            def check(m):
                return m.author == ctx.author and m.content.lower() == 'yes'

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30.0)
                logger.debug("User agreed to the quest.")
                return True
            except asyncio.TimeoutError:
                logger.debug("User did not respond in time.")
                await ctx.send("You didn't respond in time. Please try again.")
                return False
        except Exception as e:
            error_message = "An error occurred while prompting user agreement."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, ctx, error_message, title="User Agreement Error")
            return False

    async def add_user_to_server(self, ctx):
        logger.debug("Adding user to server.")
        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)
            users_in_server = await self.quest_data.find_users_in_server(guild_id)
            logger.debug(f"Users in server: {users_in_server}")

            if user_id not in users_in_server:
                agreement = await self.prompt_user_agreement(ctx)
                if agreement:
                    await self.quest_data.add_user_to_server(user_id, guild_id)
                    await ctx.send("You have been added to the game!")
                    logger.debug("User added to the game.")
                else:
                    await ctx.send("You did not agree to the terms. You cannot play the game.")
                    logger.debug("User did not agree to the terms.")
            else:
                await ctx.send("You are already part of the game!")
                logger.debug("User is already part of the game.")
        except Exception as e:
            error_message = "An error occurred while adding user to server."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, ctx, error_message, title="Add User Error")
            
    @commands.command()
    async def quest(self, ctx):
        logger.debug("Quest command invoked.")
        await self.add_user_to_server(ctx)
        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)
            logger.debug(f"Fetching quests for guild_id: {guild_id} and user_id: {user_id}")

            users_in_server = await self.quest_data.find_users_in_server(guild_id)
            logger.debug(f"Users in server: {users_in_server}")
            quests = []
            for user_id in users_in_server:
                user_quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)
                logger.debug(f"Quests for user_id {user_id}: {user_quests}")
                quests.extend(user_quests)

            if quests:
                embed = discord.Embed(title="Quest Progress", color=primary_color())
                logger.debug("Creating quest progress embed.")

                for quest_data in quests:
                    quest_id = quest_data.get("quest_id")
                    current_progress = quest_data.get("current_progress", 0)
                    task_times = quest_data.get("times", 1)

                    progress = current_progress / task_times
                    progress_bar = await Quest_Progress.generate_progress_bar(progress, self.bot)
                    logger.debug(f"Quest {quest_id}: Progress bar - {progress_bar}")

                    embed.add_field(name=f"Quest {quest_id}", value=f"Progress: {progress_bar} ({current_progress}/{task_times})", inline=False)

                await ctx.send(embed=embed)
                logger.debug("Quest progress embed sent.")
            else:
                await ctx.send("No quest progress found for this user in this server.")
                logger.debug("No quest progress found.")
        except Exception as e:
            error_message = "An error occurred while fetching or displaying quest progress."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, ctx, error_message, title="Quest Error")
         
class Quest_Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        super().__init__()

    @app_commands.command(
        name="create_quest",
        description="Create a new quest.",
    )
    @app_commands.describe(action='The action to perform for the quest. (e.g., send, receive, react)')
    @app_commands.describe(method='The method to use for the quest. (e.g., message, reaction)')
    @app_commands.choices(action=[
        discord.app_commands.Choice(name='send', value='send'), 
        discord.app_commands.Choice(name='receive', value='receive'), 
        discord.app_commands.Choice(name='react', value='react')
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
        times: typing.Optional[int] = 1,
    ) -> None:
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            # Prompt user for additional content
            await interaction.response.send_message(
                content=f"Please provide the content for the {method.name}:",
                ephemeral=True
            )
            response = await self.bot.wait_for("message", check=lambda m: m.author == interaction.user)
            content = response.content
            await response.delete()

            # Create the quest
            quest_id = await self.quest_data.create_new_quest_for_all(guild_id, action.value, method.value, channel.id, times, content, interaction)
            if quest_id is not None:
                # Create the quest embed
                embed = await QuestEmbed.create_quest_embed("Created", quest_id, action.value, method.value, channel, times=times, content=content)
                
                # Send the embed
                await interaction.followup.send(embed=embed)
                logger.debug("Quest creation successful.")
            else:
                await interaction.followup.send("Failed to create the quest.")
                logger.debug("Failed to create the quest.")
                
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, interaction, e, title="Quest Creation")

          
def setup(bot):
    bot.add_cog(Quest_Data(bot))
    bot.add_cog(Quest(bot))
    bot.add_cog(Quest_Slash(bot))
