
import logging, re, traceback
from fuzzywuzzy import fuzz
from data.local.const import Quest_Completed_Embed
from imports.discord_imports import *

logger = logging.getLogger("Quest_Events")

class Quest_Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = bot.get_cog("Quest_Data")
        self.progress_emoji = "<:anyasus:1244195699331960863>"

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        try:
            guild_id, user_id = str(message.guild.id), str(message.author.id)
            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)
            if not quests: return
            for quest in quests:
                if quest["action"] == "send" and int(quest["channel_id"]) == message.channel.id:
                    if quest["method"] == "message":
                        await self.handle_message_quest(quest, message, user_id, guild_id)
                    elif quest["method"] == "emoji":
                        await self.handle_emoji_quest(quest, message, user_id, guild_id)
        except Exception as e:
            logger.error("Error in on_message:\n%s", e)

    async def handle_message_quest(self, quest, message, user_id, guild_id):
        quest_content = quest["content"]
        member_ids = re.findall(r"<@!?(\d+)>", message.content)
        quest_content_replaced = quest_content.replace("{member}", f"<@{member_ids[0]}>" if member_ids else "{member}")
        norm_msg = re.sub(r"\s+", " ", message.content.strip()).lower()
        norm_quest = re.sub(r"\s+", " ", quest_content_replaced.strip()).lower()
        if fuzz.ratio(norm_msg, norm_quest) >= 88:
            mentions = [m for m in message.mentions if m.id != message.author.id and not m.bot]
            if "{member}" in quest_content and not mentions: return
            if "{member}" not in quest_content or (mentions and mentions[0].id != message.author.id):
                quest["progress"] += 1
                await message.add_reaction(self.progress_emoji)
                await self.update_quest_progress(guild_id, user_id, quest["quest_id"], quest["progress"])
            if quest["progress"] >= quest["times"]:
                await self.complete_quest(guild_id, user_id, quest, quest["times"], message.author, quest["quest_id"], message, method="sent", reward=quest["reward"])
                await self.quest_data.add_new_quest(guild_id, message.author)

    async def handle_emoji_quest(self, quest, message, user_id, guild_id):
        quest_emoji = str(discord.utils.get(self.bot.emojis, id=int(quest["content"]))) if isinstance(quest["content"], int) else quest["content"]
        ids = re.findall(r"<:[\w~]+:(\d+)>", message.content)
        named_emojis = [str(discord.utils.get(self.bot.emojis, id=int(e))) for e in ids]
        unicode_emojis = re.findall(r"[\U0001F600-\U0001F64F]", message.content)
        if quest_emoji in named_emojis or quest_emoji in unicode_emojis:
            quest["progress"] += 1
            await message.add_reaction(self.progress_emoji)
            await self.update_quest_progress(guild_id, user_id, quest["quest_id"], quest["progress"])
            if quest["progress"] >= quest["times"]:
                await self.complete_quest(guild_id, user_id, quest, quest["times"], message.author, quest["quest_id"], message, method="sent emoji", reward=quest["reward"])
                await self.quest_data.add_new_quest(guild_id, message.author)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot: return
        try:
            message = reaction.message
            guild_id, user_id = str(message.guild.id), str(user.id)
            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)
            if not quests: return
            for quest in quests:
                if quest["action"] == "send" and quest["method"] == "reaction" and int(quest["channel_id"]) == message.channel.id:
                    quest_emoji = str(discord.utils.get(self.bot.emojis, id=int(quest["content"]))) if isinstance(quest["content"], int) else quest["content"]
                    if str(reaction.emoji) == quest_emoji:
                        quest["progress"] += 1
                        await message.add_reaction(self.progress_emoji)
                        await self.update_quest_progress(guild_id, user_id, quest["quest_id"], quest["progress"])
                        if quest["progress"] >= quest["times"]:
                            user_obj = await self.bot.fetch_user(user_id)
                            await self.complete_quest(guild_id, user_id, quest, quest["times"], user_obj, quest["quest_id"], message, method="reaction", reward=quest["reward"])
                            await self.quest_data.add_new_quest(guild_id, user_obj)
        except Exception as e:
            logger.error("Error in on_reaction_add:\n%s", e)

    async def complete_quest(self, guild_id, user_id, quest, times, user_mention, quest_id, message, method=None, reward="N/A"):
        try:
            channel = self.bot.get_channel(int(quest["channel_id"]))
            if channel:
                await self.quest_data.initialize_balance(user_id, guild_id)
                await self.quest_data.add_balance(user_id, guild_id, quest["reward"])
                balance = await self.quest_data.get_balance(user_id, guild_id)
                embed = await Quest_Completed_Embed.create_embed(self.bot, quest["content"], channel.mention, times, user_mention, quest_id, method, reward, balance)
                await channel.send(embed=embed, reference=message)
            await self.quest_data.delete_quest_for_user(guild_id, user_id, quest_id)
        except Exception as e:
            logger.error(f"Error completing quest: {e}")
            traceback.print_exc()

    async def update_quest_progress(self, guild_id, user_id, quest_id, progress):
        try:
            await self.quest_data.update_quest_progress(guild_id, user_id, quest_id, progress)
        except Exception as e:
            logger.error(f"Error updating quest progress: {e}")
            traceback.print_exc()

async def setup(bot): await bot.add_cog(Quest_Events(bot))
