import traceback
import typing
from Imports.discord_imports import *
from Data.const import Quest_Progress, error_custom_embed, primary_color, QuestEmbed
from Data.mongo import find_quests_by_user_and_server, insert_quest, get_latest_quest_id

class Quest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            quests = await find_quests_by_user_and_server(user_id, guild_id)

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
            print(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, ctx, e, title="Quest Error")

class Quest_Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            print(f"Guild ID: {guild_id}")
            
            new_quest_id = await self.get_new_quest_id(guild_id)
            print(f"New Quest ID: {new_quest_id}")
            
            # Prompt user for additional content
            await interaction.response.send_message(
                content=f"Please provide the content for the {method.name}:",
                ephemeral=True
            )
            response = await self.bot.wait_for("message", check=lambda m: m.author == interaction.user)
            content = response.content
            await response.delete()

            print(f"Action: {action.name} ({action.value})")
            print(f"Method: {method.name} ({method.value}): {content}")
            print(f"Channel: {channel.name} ({channel.id})")
            print(f"Times: {times}")

            # Create the quest embed
            embed = await QuestEmbed.create_quest_embed("Created",new_quest_id, action.value, method.value, channel, times=times, content=content)
            print("Quest embed created.")

            # Insert the quest into the database
            quest_data = {
                "quest_id": new_quest_id,
                "action": action.value,
                "method": {method.value: content},  # Updated method value to dictionary
                "channel_id": channel.id,
                "times": times,
            }
            print("Quest data:", quest_data)
            await insert_quest(quest_data)
            print("Quest inserted into the database.")
            
            # Send the embed
            await interaction.followup.send(embed=embed)
            print("Embed sent.")
        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, interaction, e, title="Quest Creation")

    async def get_new_quest_id(self, guild_id: int) -> int:
        latest_quest_id = await get_latest_quest_id(guild_id)
        new_quest_id = latest_quest_id + 1 if latest_quest_id else 1
        return new_quest_id

def setup(bot):
    bot.add_cog(Quest(bot))
    bot.add_cog(Quest_Slash(bot))
