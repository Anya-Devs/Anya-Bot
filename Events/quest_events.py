# Standard library imports
import asyncio
import logging
import re
import traceback

# Third-party library imports
from fuzzywuzzy import fuzz

# Local imports
from Cogs.quest import Quest_Data
from Data.const import (
    Quest_Completed_Embed
)
from Imports.discord_imports import *


logger = logging.getLogger('Quest_Checker')

class Quest_Checker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        logger.debug("Quest_Checker initialized")

    async def cog_load(self):
        # Start the background task in the async cog_load method
        self.process_message_queue.start()

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
                if quest['action'] == 'send':
                    if int(quest['channel_id']) == message.channel.id:
                        if quest['method'] == 'message':
                            await self.handle_message_quest(quest, message, user_id, guild_id)
                        elif quest['method'] == 'emoji':
                            await self.handle_emoji_quest(quest, message, user_id, guild_id)
        except Exception as e:
            logger.error("An error occurred in on_message:")
            logger.error(e)

    async def handle_message_quest(self, quest, message, user_id, guild_id):
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

        # Check if the similarity ratio is above a certain threshold (e.g., 88)
        if similarity_ratio >= 88:
            mentions = [member for member in message.mentions if member.id != message.author.id and not member.bot]

            if '{member}' in quest_content and not mentions:
                return

            if '{member}' not in quest_content or (mentions and mentions[0].id != message.author.id and not mentions[0].bot):
                # Update quest progress
                quest['progress'] += 1
                await message.add_reaction('<:anyasus:1244195699331960863>')
                await self.update_quest_progress(guild_id, user_id, quest['quest_id'], quest['progress'])

            if quest['progress'] >= quest['times']:
                times = quest['times']
                user = message.author
                quest_id = quest['quest_id']
                reward = quest['reward']
                await self.complete_quest(guild_id, user_id, quest, times, user, quest_id, message, method='sent', reward=reward)
                for _ in range(1):
                    await self.quest_data.add_new_quest(guild_id, message.author)

    async def handle_emoji_quest(self, quest, message, user_id, guild_id):
        quest_emoji = quest['content']

        if isinstance(quest_emoji, int):
            quest_emoji = str(discord.utils.get(self.bot.emojis, id=int(quest_emoji)))

        message_emojis = re.findall(r'<:[\w~]+:(\d+)>', message.content)
        message_emoji_names = [str(discord.utils.get(self.bot.emojis, id=int(emoji_id))) for emoji_id in message_emojis]
        unicode_emojis = re.findall(r'[\U0001F600-\U0001F64F]', message.content)

        if quest_emoji in message_emoji_names or quest_emoji in unicode_emojis:
            quest['progress'] += 1
            await message.add_reaction('<:anyasus:1244195699331960863>')
            await self.update_quest_progress(guild_id, user_id, quest['quest_id'], quest['progress'])

            if quest['progress'] >= quest['times']:
                times = quest['times']
                user = message.author
                quest_id = quest['quest_id']
                reward = quest['reward']
                await self.complete_quest(guild_id, user_id, quest, times, user, quest_id, message, method='sent emoji', reward=reward)
                for _ in range(1):
                    await self.quest_data.add_new_quest(guild_id, message.author)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return

        try:
            message = reaction.message
            guild_id = str(message.guild.id)
            user_id = str(user.id)

            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)

            if not quests:
                return

            for quest in quests:
                if quest['action'] == 'send' and quest['method'] == 'reaction':
                    if int(quest['channel_id']) == message.channel.id:
                        quest_emoji = quest['content']
                        reaction_emoji = str(reaction.emoji)

                        if isinstance(quest_emoji, int):
                            quest_emoji = str(discord.utils.get(self.bot.emojis, id=int(quest_emoji)))

                        if quest_emoji == reaction_emoji:
                            quest['progress'] += 1
                            await message.add_reaction('<:anyasus:1244195699331960863>')
                            await self.update_quest_progress(guild_id, user_id, quest['quest_id'], quest['progress'])
                            user = await self.bot.fetch_user(user_id)

                            if quest['progress'] >= quest['times']:
                                times = quest['times']
                                user = user
                                quest_id = quest['quest_id']
                                reward = quest['reward']
                                await self.complete_quest(guild_id, user_id, quest, times, user, quest_id, message, method='reaction', reward=reward)
                                for _ in range(1):
                                    await self.quest_data.add_new_quest(guild_id, user)
        except Exception as e:
            logger.error("An error occurred in on_reaction_add:")
            logger.error(e)

    async def complete_quest(self, guild_id, user_id, quest, times, user_mention, quest_id, message, method=None, reward='N/A'):
        try:
            logger.debug(f"Completing quest: {quest_id} for user_id: {user_id} in guild_id: {guild_id}")
            channel = self.bot.get_channel(int(quest['channel_id']))
            if channel:
                await self.quest_data.add_balance(user_id, guild_id, quest['reward'])

                await self.quest_data.initialize_balance(user_id, guild_id)
                balance = await self.quest_data.get_balance(user_id, guild_id)
                balance_with_commas = "{:,}".format(balance)
                
                embed = await Quest_Completed_Embed.create_embed(
                    self.bot, quest['content'], channel.mention, times, user_mention, quest_id, method, reward, balance
                )
                await channel.send(embed=embed, reference=message)
                
            # Add balance to user's account

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


    @tasks.loop(seconds=5)
    async def process_message_queue(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            # Perform necessary background tasks here
            await asyncio.sleep(5)  # Example delay for demonstration

async def setup(bot):
    await bot.add_cog(Quest_Checker(bot))
