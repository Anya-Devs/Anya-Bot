import traceback
import re
import typing
from Imports.discord_imports import *
from Data.const import Quest_Progress, error_custom_embed, primary_color, QuestEmbed
from Imports.log_imports import *
import motor.motor_asyncio
from pymongo.errors import PyMongoError
import os

class Quest_Data(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DB_NAME = 'Quest'
        self.COLLECTION_NAME = 'Missions'

        # Initialize MongoDB connection
        mongo_url = os.getenv('MONGO_URI')
        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")
        self.mongoConnect = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)

    async def handle_error(self, interaction, error, title):
        await error_custom_embed(self.bot, interaction, error, title=title)

    async def validate_input(self, **kwargs):
        for key, value in kwargs.items():
            if value is None or value == "":
                raise ValueError(f"{key} cannot be None or empty")

    async def find_quests_by_user_and_server(self, user_id: str, guild_id: str, interaction=None):
        try:
            await self.validate_input(user_id=user_id, guild_id=guild_id)
            db = self.mongoConnect[self.DB_NAME]  # Use self.mongoConnect here
            collection = db[self.COLLECTION_NAME]
            quests = await collection.find({'user_id': user_id, 'guild_id': guild_id}).to_list(length=None)
            return quests
        except (ValueError, PyMongoError) as e:
            logger.error(f"Error occurred while finding quests: {e}")
            traceback.print_exc()
            if interaction:
                await self.handle_error(interaction, e, title="Quest Finding")
            return None

    async def insert_quest(self, quest_data: dict, interaction=None):
        try:
            await self.validate_input(**quest_data)
            db = self.mongoConnect[self.DB_NAME]  # Use self.mongoConnect here
            collection = db[self.COLLECTION_NAME]
            await collection.insert_one(quest_data)
        except (ValueError, PyMongoError) as e:
            logger.error(f"Error occurred while inserting quest: {e}")
            traceback.print_exc()
            if interaction:
                await self.handle_error(interaction, e, title="Quest Insertion")

    async def get_latest_quest_id(self, guild_id: str, interaction=None) -> int:
        try:
            await self.validate_input(guild_id=guild_id)
            db = self.mongoConnect[self.DB_NAME]  # Use self.mongoConnect here
            collection = db[self.COLLECTION_NAME]
            latest_quest = await collection.find_one({'guild_id': guild_id}, sort=[('quest_id', -1)])
            if latest_quest:
                return latest_quest['quest_id']
            else:
                return 0
        except (ValueError, PyMongoError) as e:
            logger.error(f"Error occurred while getting latest quest ID: {e}")
            traceback.print_exc()
            if interaction:
                await self.handle_error(interaction, e, title="Latest Quest ID")
            return 0

    async def create_new_quest(self, user_id: str, guild_id: str, action: str, method: str, channel_id: int, times: int, content: str, interaction=None) -> int:
        try:
            await self.validate_input(user_id=user_id, guild_id=guild_id, action=action, method=method, channel_id=channel_id, times=times, content=content)
            new_quest_id = await self.get_latest_quest_id(guild_id)
            if new_quest_id is None:
                raise ValueError("Failed to get the latest quest ID")
            new_quest_id += 1
            quest_data = {
                'quest_id': new_quest_id,
                'user_id': user_id,
                'guild_id': guild_id,
                'action': action,
                'method': method,
                'channel_id': channel_id,
                'times': times,
                'content': content
            }
            await self.insert_quest(quest_data)
            return new_quest_id
        except (ValueError, PyMongoError) as e:
            logger.error(f"Error occurred while creating new quest: {e}")
            traceback.print_exc()
            if interaction:
                await self.handle_error(interaction, e, title="Quest Creation")
            return None
        
class Quest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    # Function to parse fraction input
    def parse_fraction(self, fraction_str):
        try:
            if "/" in fraction_str:
                parts = fraction_str.split("/")
                return int(parts[0]), int(parts[1])
            elif "," in fraction_str:
                parts = fraction_str.split(",")
                return int(parts[0]), int(parts[1])
            elif " " in fraction_str:
                parts = fraction_str.split(" ")
                return int(parts[0]), int(parts[1])
            else:
                return None
        except Exception as e:
            print(f"Error occurred while parsing fraction: {e}")
            traceback.print_exc()
            return None

    # Define the quest command
    @commands.command()
    async def quest(self, ctx):
        try:
            # Find all quests for the user in the server
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)
            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)
            if quests:
                embed = discord.Embed(title="Quest Progress", color=primary_color())

                for task_id, quest_data in quests.items():
                    current_progress = quest_data.get("current_progress", 0)
                    task_times = quest_data.get("task_times", 1)

                    # Calculate progress
                    progress = current_progress / task_times

                    # Generate progress bar
                    progress_bar = await Quest_Progress.generate_progress_bar(progress, self.bot)

                    # Add field to embed
                    embed.add_field(name=" ", value=f"`{task_id}`\t{progress_bar} `{current_progress}/{task_times}`", inline=False)

                await ctx.send(embed=embed)
            else:
                await ctx.send("No quest progress found for this user in this server.")
        except Exception as e:
            error_message = f"An error occurred: {e}"
            print(error_message)
            traceback.print_exc()
            await error_custom_embed(self.bot, ctx, error_message, title="Quest Error")

class Quest_Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        super().__init__()  # this is now required in this context.

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
            guild_id = interaction.guild.id
            user_id = interaction.user.id  # Assuming you want to associate the quest with the user who created it
            
            # Prompt user for additional content
            await interaction.response.send_message(
                content=f"Please provide the content for the {method.name}:",
                ephemeral=True
            )
            response = await self.bot.wait_for("message", check=lambda m: m.author == interaction.user)
            content = response.content
            await response.delete()

            # Create the quest
            quest_id = await self.quest_data.create_new_quest(user_id, guild_id, action.value, method.value, channel.id, times, content)
            if quest_id:
                # Create the quest embed
                embed = await QuestEmbed.create_quest_embed("Created", quest_id, action.value, method.value, channel, times=times, content=content)
                
                # Send the embed
                await interaction.followup.send(embed=embed)
                print("Embed sent.")
            else:
                await interaction.followup.send("Failed to create the quest.")
                
        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, interaction, e, title="Quest Creation")
            
            
def setup(bot):
    bot.add_cog(Quest_Data(bot))
    bot.add_cog(Quest(bot))
    bot.add_cog(Quest_Slash(bot))
