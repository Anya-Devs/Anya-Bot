from Cogs.quest import  Quest_Data
from datetime import datetime, timedelta
from Imports.discord_imports import *
from Data.const import Quest_Progress, error_custom_embed, primary_color, QuestEmbed, Quest_Prompt, Quest_Completed_Embed


class Quest_Checker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        try:
            guild_id = str(message.guild.id)
            user_id = str(message.author.id)
            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)

            if not quests:
                return

            for quest in quests:
                if quest['action'] == 'send' and quest['method'] == 'message':
                    if quest['channel_id'] == message.channel.id and quest['content'] in message.content:
                        quest['progress'] += 1
                        if quest['progress'] >= quest['times']:
                            # Quest completed
                            times = quest['times']
                            user_mention = message.author.mention
                            quest_id = quest['quest_id']
                            await self.complete_quest(guild_id, user_id, quest,times, user_mention, quest_id)
                        else:
                            # Update progress
                            await self.update_quest_progress(guild_id, user_id, quest['quest_id'], quest['progress'])
                            # await message.add_reaction("✨")


        except Exception as e:
            logger.error(f"Error occurred in on_message event: {e}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
        
        try:
            guild_id = str(reaction.message.guild.id)
            user_id = str(user.id)
            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)

            if not quests:
                return

            for quest in quests:
                if quest['action'] == 'react' and quest['method'] == 'reaction':
                    if quest['channel_id'] == reaction.message.channel.id and quest['content'] in str(reaction.emoji):
                        quest['progress'] += 1
                        if quest['progress'] >= quest['times']:
                            # Quest completed
                            await self.complete_quest(guild_id, user_id, quest)
                        else:
                            # Update progress
                            await self.update_quest_progress(guild_id, user_id, quest['quest_id'], quest['progress'])

        except Exception as e:
            logger.error(f"Error occurred in on_reaction_add event: {e}")
            traceback.print_exc()

    async def complete_quest(self, guild_id, user_id, quest, times, user_mention, quest_id):
        try:
            # Notify the user about the quest completion
            channel = self.bot.get_channel(quest['channel_id'])
            if channel:
              embed = await Quest_Completed_Embed.create_embed(self.bot,quest['content'], channel.mention, times, user_mention,quest_id)
              await channel.send(embed=embed)

            # Delete the completed quest for this user
            await self.quest_data.delete_quest_for_user(guild_id, user_id, quest['quest_id'])

            logger.debug(f"Quest {quest['quest_id']} completed for user {user_id} in guild {guild_id}.")

        except Exception as e:
            logger.error(f"Error occurred while completing quest: {e}")
            traceback.print_exc()

    async def update_quest_progress(self, guild_id, user_id, quest_id, progress):
        try:
            await self.quest_data.update_quest_progress(guild_id, user_id, quest_id, progress)
            logger.debug(f"Quest {quest_id} progress updated for user {user_id} in guild {guild_id}.")
        except Exception as e:
            logger.error(f"Error occurred while updating quest progress: {e}")
            traceback.print_exc()
           
def setup(bot):
    bot.add_cog(Quest_Checker(bot))
