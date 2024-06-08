import re
from Cogs.quest import Quest_Data
from datetime import datetime, timedelta
from Imports.discord_imports import *
from Imports.log_imports import *
from Data.const import Quest_Progress, error_custom_embed, primary_color, QuestEmbed, Quest_Prompt, Quest_Completed_Embed
import traceback
from fuzzywuzzy import fuzz

class Quest_Checker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        logger.debug("Quest_Checker initialized")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        try:
            guild_id = str(message.guild.id)
            user_id = str(message.author.id)
            logger.debug(f"Message received in guild: {guild_id}, user: {user_id}")

            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)
            logger.debug(f"Found {len(quests)} quests for user: {user_id} in guild: {guild_id}")

            if not quests:
                return

            for quest in quests:
                logger.debug(f"Checking quest: {quest['quest_id']} for user: {user_id} in guild: {guild_id}")
                if quest['action'] == 'send' and quest['method'] == 'message':
                    if quest['channel_id'] == message.channel.id:
                        logger.debug(f"Quest {quest['quest_id']} is a message quest and matches channel: {message.channel.id}")
                        quest_content = quest['content']  # Quest content with {member}
                        
                        member_id_pattern = r'<@!?(\d+)>'
                        message_content = message.content
                        member_ids = re.findall(member_id_pattern, message_content)
                        for member_id in member_ids:
                            message_content = message_content.replace(f'<@{member_id}>', f'<@{member_id}>')  # Ensure mentions are properly formatted
                        
                        quest_content_replaced = quest_content.replace('{member}', f'<@{member_ids[0]}>' if member_ids else '{member}')  # Replace {member} with a placeholder for mention

                        # Normalize the message content and the quest content for comparison
                        normalized_message_content = re.sub(r'\s+', ' ', message_content.strip()).lower()
                        normalized_quest_content = re.sub(r'\s+', ' ', quest_content_replaced.strip()).lower()

                        # Use fuzzy matching to compare the quest content with the message content
                        similarity_ratio = fuzz.ratio(normalized_message_content, normalized_quest_content)

                        logger.debug(f"Similarity ratio between message and quest content: {similarity_ratio}")

                        # Check if the similarity ratio is above a certain threshold (e.g., 80)
                        if similarity_ratio >= 80:
                            logger.debug("Similarity ratio is above threshold. Checking if a valid member is mentioned.")
                            mentions = [member for member in message.mentions if member.id != message.author.id and not member.bot]

                            if '{member}' in quest_content and not mentions:
                                logger.debug("No valid member mention found for a quest requiring member mention.")
                                continue

                            if '{member}' not in quest_content or (mentions and mentions[0].id != message.author.id and not mentions[0].bot):
                                # Update quest progress
                                quest['progress'] += 1
                                await self.update_quest_progress(guild_id, user_id, quest['quest_id'], quest['progress'])

                            if quest['progress'] >= quest['times']:
                                logger.debug("Quest progress meets or exceeds required times. Completing quest.")
                                times = quest['times']
                                user = message.author
                                quest_id = quest['quest_id']
                                reward = quest['reward']
                                await self.complete_quest(guild_id, user_id, quest, times, user, quest_id, message, method='sent', reward=reward)
                                for _ in range(1):
                                    await self.quest_data.add_new_quest(guild_id, message.author)
        except Exception as e:
            logger.error("An error occurred in on_message:")
            logger.error(e)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        try:
            message = reaction.message
            guild_id = str(message.guild.id)
            user_id = str(user.id)
            logger.debug(f"Reaction added in guild: {guild_id}, user: {user_id}")

            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)

            logger.debug(f"Found {len(quests)} quests for user: {user_id} in guild: {guild_id}")

            if not quests:
                return

            for quest in quests:
                logger.debug(f"Checking quest: {quest['quest_id']} for user: {user_id} in guild: {guild_id}")
                if quest['action'] == 'send' and quest['method'] == 'reaction':
                    if quest['channel_id'] == message.channel.id:
                        logger.debug(f"Quest {quest['quest_id']} is a reaction quest and matches channel: {message.channel.id}")
                        quest_emoji = quest['content']

                        if isinstance(quest_emoji, int):
                            quest_emoji = str(discord.utils.get(self.bot.emojis, id=int(quest_emoji)))
                        
                        reaction_emoji = str(reaction.emoji)

                        if quest_emoji == reaction_emoji:
                            logger.debug("Reaction matches quest emoji. Updating quest progress.")
                            quest['progress'] += 1
                            await self.update_quest_progress(guild_id, user_id, quest['quest_id'], quest['progress'])

                        if quest['progress'] >= quest['times']:
                            logger.debug("Quest progress meets or exceeds required times. Completing quest.")
                            times = quest['times']
                            user = user
                            quest_id = quest['quest_id']
                            reward = quest['reward']

                            await self.complete_quest(guild_id, user_id, quest, times, user, quest_id, message, method='reacted with', reward=reward)
                            for _ in range(1):
                                await self.quest_data.add_new_quest(guild_id, user)
        except Exception as e:
            logger.error("An error occurred in on_reaction_add:")
            logger.error(e)

    async def complete_quest(self, guild_id, user_id, quest, times, user_mention, quest_id, message, method=None, reward='N/A'):
        try:
            logger.debug(f"Completing quest: {quest_id} for user_id: {user_id} in guild_id: {guild_id}")
            channel = self.bot.get_channel(quest['channel_id'])
            if channel:
                embed = await Quest_Completed_Embed.create_embed(
                    self.bot, quest['content'], channel.mention, times, user_mention, quest_id, method, reward
                )
                await channel.send(embed=embed, reference=message)

            await self.quest_data.delete_quest_for_user(guild_id, user_id, quest['quest_id'])
            logger.debug(f"Quest {quest['quest_id']} deleted for user {user_id} in guild {guild_id}.")

        except Exception as e:
            logger.error(f"Error occurred while completing quest: {e}")
            traceback.print_exc()

    async def update_quest_progress(self, guild_id, user_id, quest_id, progress):
        try:
            logger.debug(f"Updating progress for quest_id: {quest_id} for user_id: {user_id} in guild_id: {guild_id} to progress: {progress}")
            await self.quest_data.update_quest_progress(guild_id, user_id, quest_id, progress)
            logger.debug(f"Quest {quest_id} progress updated for user {user_id} in guild {guild_id}.")
        except Exception as e:
            logger.error(f"Error occurred while updating quest progress: {e}")
            traceback.print_exc()

def setup(bot):
    bot.add_cog(Quest_Checker(bot))
