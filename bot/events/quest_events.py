import logging, re, traceback, asyncio, time
from fuzzywuzzy import fuzz
from data.local.const import Quest_Completed_Embed
from imports.discord_imports import *

logger = logging.getLogger("Quest_Events")

class Quest_Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = bot.get_cog("Quest_Data")
        self.progress_emoji = "<:anyasus:1244195699331960863>"
        self.channel_stats = {}
        self.SPAM_WINDOW_SECONDS = 60
        self.SPAM_THRESHOLD = 50
        self.bot.loop.create_task(self._periodic_cleanup())

        self._db_error_silence_until: float = 0.0
        self._db_error_silence_seconds: int = 60
        
        # Anti-spam tracking for quest completion
        self.user_interaction_tracking = {}  # {user_id: {target_user_id: last_interaction_time, replied_messages: set()}}
        self.INTERACTION_COOLDOWN = 300  # 5 minutes between interactions with same user
        self.MESSAGE_REPLY_REQUIREMENT = True  # Must reply to messages for quest progress
        
        # Emoji quest cooldown tracking
        self.emoji_quest_cooldowns = {}  # {user_id: last_emoji_quest_time}
        self.EMOJI_QUEST_COOLDOWN = 5430  # 1 hour 30 seconds cooldown
        
        # Feedback system for quest guidance
        self.user_feedback_settings = {}  # {user_id: bool} - True = feedback enabled, False = disabled
        self.feedback_messages = {}  # {message_id: asyncio.Task} - Track feedback messages for deletion
        self.feedback_cooldowns = {}  # {user_id: {message_type: last_shown_time}} - Rate limit feedback

    def _is_db_down_error(self, e: Exception) -> bool:
        msg = str(e)
        return (
            "No replica set members available" in msg
            or "ReplicaSetNoPrimary" in msg
            or "ServerSelectionTimeoutError" in msg
        )

    def _should_silence_db_error(self) -> bool:
        return time.time() < float(self._db_error_silence_until or 0.0)

    def _note_db_error(self, e: Exception) -> None:
        if self._should_silence_db_error():
            return
        self._db_error_silence_until = time.time() + float(self._db_error_silence_seconds)
        logger.error("Database unavailable (cooldown %ss): %s", self._db_error_silence_seconds, e)

    def _can_interact_with_user(self, user_id: str, target_user_id: str) -> bool:
        """Check if user can interact with target user (cooldown check)."""
        if user_id not in self.user_interaction_tracking:
            return True
        
        user_data = self.user_interaction_tracking[user_id]
        if target_user_id not in user_data:
            return True
            
        last_interaction = user_data[target_user_id].get('last_interaction_time', 0)
        return time.time() - last_interaction > self.INTERACTION_COOLDOWN

    def _is_valid_reply(self, message) -> bool:
        """Check if message is a reply to another user's message."""
        if not message.reference or not message.reference.message_id:
            return False
        return True

    def _has_replied_to_message_before(self, user_id: str, message_id: int) -> bool:
        """Check if user has already replied to this specific message."""
        if user_id not in self.user_interaction_tracking:
            return False
        
        for target_data in self.user_interaction_tracking[user_id].values():
            if isinstance(target_data, dict) and message_id in target_data.get('replied_messages', set()):
                return True
        return False

    def _record_interaction(self, user_id: str, target_user_id: str, message_id: int):
        """Record user interaction with target user and message."""
        if user_id not in self.user_interaction_tracking:
            self.user_interaction_tracking[user_id] = {}
        
        if target_user_id not in self.user_interaction_tracking[user_id]:
            self.user_interaction_tracking[user_id][target_user_id] = {
                'last_interaction_time': 0,
                'replied_messages': set()
            }
        
        self.user_interaction_tracking[user_id][target_user_id]['last_interaction_time'] = time.time()
        self.user_interaction_tracking[user_id][target_user_id]['replied_messages'].add(message_id)

    def _is_feedback_enabled(self, user_id: str) -> bool:
        """Check if user has feedback enabled (default: True)."""
        return self.user_feedback_settings.get(user_id, True)

    def _toggle_feedback(self, user_id: str) -> bool:
        """Toggle feedback setting for user. Returns new state."""
        current = self.user_feedback_settings.get(user_id, True)
        self.user_feedback_settings[user_id] = not current
        return not current

    async def _send_feedback_message(self, channel, user, message_type: str = "reply_required"):
        """Send feedback message to user and auto-delete after 5 seconds."""
        if not self._is_feedback_enabled(str(user.id)):
            return
        
        # Rate limiting - only show feedback once per user per 30 minutes total (not per type)
        user_id = str(user.id)
        now = time.time()
        FEEDBACK_COOLDOWN = 1800  # 30 minutes total cooldown per user
        
        if user_id not in self.feedback_cooldowns:
            self.feedback_cooldowns[user_id] = {}
        
        # Check if any feedback was shown recently (global user cooldown)
        last_any_feedback = max(self.feedback_cooldowns[user_id].values()) if self.feedback_cooldowns[user_id] else 0
        if now - last_any_feedback < FEEDBACK_COOLDOWN:
            return  # Still on global cooldown for this user
        
        # Update cooldown for this specific type
        self.feedback_cooldowns[user_id][message_type] = now
        
        embed = discord.Embed(color=0xff6b9d)  # Anya pink
        
        embed.set_footer(text="💡 Use -q feedback to toggle these tips on/off")
        
        try:
            feedback_msg = await channel.send(embed=embed, delete_after=10)
            # Track the message for potential early cleanup
            self.feedback_messages[feedback_msg.id] = asyncio.create_task(asyncio.sleep(5))
        except Exception:
            pass  # Silently fail if can't send feedback

    async def _periodic_cleanup(self):
        while True:
            await asyncio.sleep(600)
            now = time.time()
            to_remove = [cid for cid, stats in self.channel_stats.items() if now - stats['window_start'] > 1800]
            for cid in to_remove:
                del self.channel_stats[cid]
            if len(self.channel_stats) > 100:
                recent = {cid: stats for cid, stats in self.channel_stats.items() if now - stats['window_start'] < 3600}
                self.channel_stats.clear()
                self.channel_stats.update(recent)
            logger.debug(f"Cleaned up {len(to_remove)} inactive channel stats; total now {len(self.channel_stats)}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        cid = message.channel.id
        now = time.time()
        if cid not in self.channel_stats:
            self.channel_stats[cid] = {'count': 0, 'window_start': now, 'ignored': False}
        stats = self.channel_stats[cid]
        if now - stats['window_start'] > self.SPAM_WINDOW_SECONDS:
            stats['count'] = 1
            stats['window_start'] = now
        else:
            stats['count'] += 1
        if not stats['ignored'] and stats['count'] > self.SPAM_THRESHOLD:
            stats['ignored'] = True
            channel_name = message.channel.name if hasattr(message.channel, 'name') else 'Unknown'
            print(f"Marked high-volume channel {cid} ({channel_name}) as spam (rate: {stats['count']} msg/{self.SPAM_WINDOW_SECONDS}s), ignoring future messages.")
        if stats['ignored']:
            return
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
            if self._is_db_down_error(e):
                self._note_db_error(e)
                return
            logger.error("Error in on_message:\n%s", e)

    async def handle_message_quest(self, quest, message, user_id, guild_id):
        quest_content = quest["content"]
        member_ids = re.findall(r"<@!?(\d+)>", message.content)
        quest_content_replaced = quest_content.replace("{member}", f"<@{member_ids[0]}>" if member_ids else "{member}")
        norm_msg = re.sub(r"\s+", " ", message.content.strip()).lower()
        norm_quest = re.sub(r"\s+", " ", quest_content_replaced.strip()).lower()
        
        if fuzz.ratio(norm_msg, norm_quest) >= 83:
            mentions = [m for m in message.mentions if m.id != message.author.id and not m.bot]
            if "{member}" in quest_content and not mentions: 
                return
            if "{member}" not in quest_content or (mentions and mentions[0].id != message.author.id):
                quest["progress"] += 1
                await message.add_reaction(self.progress_emoji)
                await self.update_quest_progress(guild_id, user_id, quest["quest_id"], quest["progress"])
                
            if quest["progress"] >= quest["times"]:
                await self.complete_quest(guild_id, user_id, quest, quest["times"], message.author, quest["quest_id"], message, method="sent", reward=quest["reward"])
                await self.quest_data.add_new_quest(guild_id, message.author)

    async def handle_emoji_quest(self, quest, message, user_id, guild_id):
        # Check emoji quest cooldown (1 hour 30 seconds)
        now = time.time()
        last_emoji_time = self.emoji_quest_cooldowns.get(user_id, 0)
        if now - last_emoji_time < self.EMOJI_QUEST_COOLDOWN:
            return  # Still on cooldown
        
        quest_emoji = str(discord.utils.get(self.bot.emojis, id=int(quest["content"]))) if isinstance(quest["content"], int) else quest["content"]
        ids = re.findall(r"<:[\w~]+:(\d+)>", message.content)
        named_emojis = [str(discord.utils.get(self.bot.emojis, id=int(e))) for e in ids]
        unicode_emojis = re.findall(r"[\U0001F600-\U0001F64F]", message.content)
        if quest_emoji in named_emojis or quest_emoji in unicode_emojis:
            # Update cooldown timestamp
            self.emoji_quest_cooldowns[user_id] = now
            
            # Check if this is a reply - gives double points bonus
            is_reply_bonus = self._is_valid_reply(message)
            
            quest["progress"] += 1
            await message.add_reaction(self.progress_emoji)
            await self.update_quest_progress(guild_id, user_id, quest["quest_id"], quest["progress"])
            
            if quest["progress"] >= quest["times"]:
                # Double reward if user replied to someone's message
                reward = quest["reward"] * 2 if is_reply_bonus else quest["reward"]
                method = "sent emoji (2x bonus!)" if is_reply_bonus else "sent emoji"
                await self.complete_quest(guild_id, user_id, quest, quest["times"], message.author, quest["quest_id"], message, method=method, reward=reward)
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
            if self._is_db_down_error(e):
                self._note_db_error(e)
                return
            logger.error("Error in on_reaction_add:\n%s", e)

    async def complete_quest(self, guild_id, user_id, quest, times, user_mention, quest_id, message, method=None, reward="N/A"):
        try:
            channel = self.bot.get_channel(int(quest["channel_id"]))
            if channel:
                await self.quest_data.initialize_balance(user_id, guild_id)
                await self.quest_data.add_balance(user_id, guild_id, quest["reward"])
                await self.quest_data.increment_quests_done(user_id, guild_id)
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
