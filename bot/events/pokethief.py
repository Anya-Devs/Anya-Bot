import asyncio
import datetime
import re
import time
import traceback
import aiohttp
import os
import random
import json

from discord.ext.commands.core import P
from motor.motor_asyncio import AsyncIOMotorClient
from data.local.const import primary_color
from bot.token import get_bot_token, use_test_bot as ut
from imports.log_imports import *
from imports.discord_imports import *
from utils.subcogs.utils.mongo import *
from datetime import datetime, timedelta



MONGO_URI = os.getenv("MONGO_URI")
mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["Commands"]["pokemon"]





class Anti_Thief(commands.Cog):
    BOT_IDS = {874910942490677270, 1234247716243112100, 854233015475109888, 1250128097941000223}
    IGNORE_CHANNEL_KEYWORD = 'incense'
    DEBUG = 0  # Set to 1 to enable debug prints, 0 to disable

    def __init__(self, bot):
        self.bot = bot
        self.shiny_regex = re.compile(r"<@(\d+)>")
        self.shiny_hunters = []
        self.primary_color = primary_color()
        self.mongo = MongoShHelper(db)
        self.logger = logger
        

    async def get_member(self, guild, user_id):
        if isinstance(guild, int):
            guild = self.bot.get_guild(guild)
        try:
            return await guild.fetch_member(user_id)
        except Exception as e:
            if self.DEBUG:
                print(f"ERROR fetching member {user_id}: {e}")
            return None

    async def parse_hunters_and_collectors(self, guild, message_content) -> tuple[list, list]:
        """Parse both shinyhunt and collectors from message content"""
        shiny_hunters = []
        collectors = []
        
        if self.DEBUG:
            print(f"[PARSE] Input message content: {message_content[:200]}")
        
        if isinstance(guild, int):
            guild = self.bot.get_guild(guild)
        if not guild:
            return shiny_hunters, collectors
            
        try:
            lines = message_content.splitlines()
            if self.DEBUG:
                print(f"[PARSE] Lines: {lines[:5]}")
            
            sections = {}
            header_regex = re.compile(r'>\s*\*\*(.+?)\*\*:?')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                match = header_regex.search(line)
                if match:
                    header = match.group(1).strip()
                    i += 1
                    if i < len(lines):
                        mention_line = lines[i].strip()
                        if mention_line.startswith('>') and '<@' in mention_line:
                            user_ids = self.shiny_regex.findall(mention_line)
                            sections[header] = user_ids
                            if self.DEBUG:
                                print(f"[PARSE] Found section {header} with IDs {user_ids}")
                i += 1
            
            # Only process Shinyhunt and Collectors sections
            shiny_header = next((h for h in sections if "shinyhunt" in h.lower()), None)
            collectors_header = next((h for h in sections if "collectors" in h.lower()), None)
            
            # Collect only relevant user_ids from Shinyhunt and Collectors
            relevant_user_ids = set()
            if shiny_header:
                relevant_user_ids.update(sections[shiny_header])
            if collectors_header:
                relevant_user_ids.update(sections[collectors_header])
            
            # If no relevant sections found, return empty lists
            if not relevant_user_ids:
                if self.DEBUG:
                    print("[PARSE] No Shinyhunt or Collectors sections found, ignoring message")
                return shiny_hunters, collectors
            
            # Fetch all unique members
            unique_ids = list(relevant_user_ids)
            members_tasks = [self.get_member(guild, int(uid)) for uid in unique_ids]
            members_results = await asyncio.gather(*members_tasks, return_exceptions=True)
            id_to_member = {}
            for uid, res in zip(unique_ids, members_results):
                if not isinstance(res, Exception) and res:
                    id_to_member[int(uid)] = res
            
            # Assign to shiny_hunters and collectors
            if shiny_header:
                uids = sections[shiny_header]
                shiny_hunters = [id_to_member.get(int(uid)) for uid in uids if int(uid) in id_to_member]
                
            if collectors_header:
                uids = sections[collectors_header]
                collectors = [id_to_member.get(int(uid)) for uid in uids if int(uid) in id_to_member]
                        
        except Exception as e:
            if self.DEBUG:
                print(f"ERROR parsing hunters and collectors: {e}")
            
        return shiny_hunters, collectors

    async def is_shiny_hunter(self, user_id: int) -> bool:
        return any(h.id == user_id for h in self.shiny_hunters)
    
    async def is_shiny_protected_channel(self, guild_id: int, channel_id: int) -> bool:
        protected_channels = await self.mongo.get_shiny_protected_channels(guild_id)
        return channel_id in protected_channels
    
    async def is_collection_protected_channel(self, guild_id: int, channel_id: int) -> bool:
        protected_channels = await self.mongo.get_collection_protected_channels(guild_id)
        return channel_id in protected_channels

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if self.IGNORE_CHANNEL_KEYWORD in message.channel.name.lower():
                return


            # --- POKÉMON SPAWN CHECK ---
            # Check both message content and embed titles for new spawns
            is_new_spawn = False
            if message.embeds:
                for embed in message.embeds:
                    if embed.title and "pokémon has appeared!" in embed.title.lower():
                        is_new_spawn = True
                        break
            
            if is_new_spawn:
                if self.DEBUG:
                    print("[on_message] New Pokémon spawn detected in channel.")
                event_gate = self.bot.get_cog('EventGate')

                if not event_gate:
                    if self.DEBUG:
                        print("[on_message] EventGate cog NOT FOUND.")
                else:
                    if message.channel.id in event_gate.active_events:
                        if self.DEBUG:
                            print(
                                f"[on_message] New spawn detected! Canceling active protection timer for channel {message.channel.id}"
                            )
                        # Cancel the active timer by setting a flag
                        event_gate.cancel_timer(message.channel.id)
                    else:
                        if self.DEBUG:
                            print(
                                f"[on_message] No active event running in channel {message.channel.id}"
                            )

            # --- PROTECTION CHANNEL CHECKS ---
            guild_id = getattr(message.guild, "id", None)
            channel_id = message.channel.id

            is_shiny_protected_channel = await self.is_shiny_protected_channel(guild_id, channel_id)
            is_collection_protected_channel = await self.is_collection_protected_channel(guild_id, channel_id)

            #if ut:
            #    return

            # --- BOT MESSAGE PROCESSING ---
            if message.author.id in self.BOT_IDS and message.guild:
                if self.DEBUG:
                    print(
                        f"[on_message] Message is from watched bot {message.author.id}."
                    )

                if is_shiny_protected_channel or is_collection_protected_channel:
                    if self.DEBUG:
                        print("[on_message] Protection active. Parsing hunters/collectors.")
                        print(f"[DEBUG] Message content: {message.content[:200]}")

                    shiny_hunters, collectors = await self.parse_hunters_and_collectors(
                        message.guild, message.content
                    )

                    # Filter based on channel protection settings
                    if not is_shiny_protected_channel:
                        if self.DEBUG:
                            print("[on_message] Shiny protection not enabled for this channel, clearing shiny hunters")
                        shiny_hunters = []
                    if not is_collection_protected_channel:
                        if self.DEBUG:
                            print("[on_message] Collection protection not enabled for this channel, clearing collectors")
                        collectors = []

                    if self.DEBUG:
                        print(
                            f"[on_message] After filtering - shiny_hunters={[h.id for h in shiny_hunters if h]}, collectors={[c.id for c in collectors if c]}"
                        )

                    if shiny_hunters or collectors:
                        if self.DEBUG:
                            print("[on_message] Sending protection embed.")
                        event_gate = self.bot.get_cog('EventGate')
                        if event_gate:
                            await event_gate.send_protection_embed(
                                message.channel,
                                shiny_hunters,
                                collectors,
                                reference_message=message
                            )
                        else:
                            if self.DEBUG:
                                print("[on_message] EventGate cog NOT FOUND when trying to send embed.")
                    else:
                        self.logger.debug("[on_message] No hunters/collectors found after filtering—embed skipped.")
                else:
                    if self.DEBUG:
                        print(
                            "[on_message] Bot message received but channel not protected; skipping."
                        )
        except Exception as e:
            if self.DEBUG:
                print(f"[on_message] ERROR processing message: {e}")
                traceback.print_exc()


class EventGate(commands.Cog):
    WAIT_TIME = 30  # seconds to wait
    DETECT_BOT_ID = 874910942490677270  # Poketwo bot ID
    OFFENSE_PHASES = [1, 3, 6, 12, 24, 48]  # hours for each offense level
    PENALTY_EXPIRY_DAYS = 30
    DEBUG = 0

    def __init__(self, bot):
        self.bot = bot
        self.primary_color = primary_color()
        self.active_events = {}
        self.channel_hunters = {}
        self.handled_congrats = set()
        self.cancelled_timers = set()
        self.offenses_cache = {}
        self.mongo_sh = MongoShHelper(db)

    @staticmethod
    def timestamp_gen(ts: int) -> str:
        return f"<t:{int(ts)}:R>"

    def cancel_timer(self, channel_id):
        """Cancel an active timer for a channel"""
        self.cancelled_timers.add(channel_id)

    async def send_protection_embed(self, channel, shiny_hunters, collectors, reference_message):
        """Send the protection embed with timer"""
        if not hasattr(self, 'channel_hunters'):
            self.channel_hunters = {}
        self.channel_hunters[channel.id] = {'shiny': shiny_hunters, 'collectors': collectors}
        
        wait_until = time.time() + self.WAIT_TIME
        self.active_events[channel.id] = wait_until
        
        # Build embed description
        lines = []
        if shiny_hunters:
            lines.append(f"{self.timestamp_gen(wait_until)} | waiting for {' '.join(h.mention for h in shiny_hunters)}")
            if collectors:
                lines.append("Collectors: waiting for shiny timer to end...")
        elif collectors:
            lines.append(f"{self.timestamp_gen(wait_until)} | waiting for {' '.join(c.mention for c in collectors)}")
        
        embed = Embed(description='\n'.join(lines), color=self.primary_color)
        
        try:
            msg = await channel.send(embed=embed, reference=reference_message)
        except Exception as e:
            if self.DEBUG:
                print(f"[EventGate] ERROR sending embed: {e}")
            msg = await channel.send(embed=embed)
            
        await self.start_countdown(msg, wait_until, reference_message)

    async def start_countdown(self, message, wait_until, reference_message):
        channel_id = message.channel.id
        hunters = self.channel_hunters.get(channel_id, {})
        shiny_hunters = hunters.get('shiny', [])
        collectors = hunters.get('collectors', [])
        
        try:
            if shiny_hunters:
                # Shiny takes priority
                try:
                    await asyncio.wait_for(
                        self.wait_for_congratulations(message, wait_until, reference_message, "shiny"),
                        timeout=self.WAIT_TIME
                    )
                    # If shiny caught, we're done - cleanup and exit
                    return
                except asyncio.TimeoutError:
                    # Shiny timer expired
                    if collectors:
                        # Start collection timer
                        await self.handle_shiny_timeout(message, reference_message)
                        collection_wait_until = time.time() + self.WAIT_TIME
                        # Don't return here - let it fall through to collection timer
                        try:
                            await asyncio.wait_for(
                                self.wait_for_congratulations(message, collection_wait_until, reference_message, "collection"),
                                timeout=self.WAIT_TIME
                            )
                            # Collection caught, we're done
                            return
                        except asyncio.TimeoutError:
                            # Collection timer also expired
                            await self.allow_all_to_catch(message)
                    else:
                        # No collectors, just allow all
                        await self.allow_all_to_catch(message)
            elif collectors:
                # Only collection protection
                try:
                    await asyncio.wait_for(
                        self.wait_for_congratulations(message, wait_until, reference_message, "collection"),
                        timeout=self.WAIT_TIME
                    )
                    # Collection caught
                    return
                except asyncio.TimeoutError:
                    await self.allow_all_to_catch(message)
            else:
                # No protection, allow all immediately
                await self.allow_all_to_catch(message)
        except Exception as e:
            if self.DEBUG:
                print(f"[EventGate] ERROR in countdown: {e}")
        finally:
            self.active_events.pop(channel_id, None)
            self.channel_hunters.pop(channel_id, None)

    async def handle_shiny_timeout(self, message, reference_message):
        """Update embed to strike through shiny timer and start collection timer"""
        channel_id = message.channel.id
        hunters = self.channel_hunters.get(channel_id, {})
        collectors = hunters.get('collectors', [])
        
        # Update embed with strikethrough shiny timer
        lines = []
        lines.append(f"~~{self.timestamp_gen(time.time())} | waiting for {' '.join(h.mention for h in hunters.get('shiny', []))}~~")
        if collectors:
            collection_wait_until = time.time() + self.WAIT_TIME
            lines.append(f"{self.timestamp_gen(collection_wait_until)} | waiting for {' '.join(c.mention for c in collectors)}")
        
        embed = Embed(description='\n'.join(lines), color=self.primary_color)
        await message.edit(embed=embed)

    async def wait_for_congratulations(self, message, wait_until, reference_message, event_type="shiny"):
        channel_id = message.channel.id
        
        def check(m):
            if event_type == "shiny":
                pattern = r"Congratulations <@(\d+)>! You caught a level \d+ .+"
            else:  # collection
                pattern = r"Congratulations <@(\d+)>! You caught a level \d+ .+"
            
            return (
                m.channel.id == message.channel.id
                and m.author.id == self.DETECT_BOT_ID
                and m.id not in self.handled_congrats
                and re.match(pattern, m.content)
            )
        
        # Check for cancellation periodically
        while time.time() < wait_until:
            # Check if timer was cancelled
            if channel_id in self.cancelled_timers:
                if self.DEBUG:
                    print(f"[EventGate] Timer cancelled for channel {channel_id}, exiting without penalties")
                self.cancelled_timers.discard(channel_id)
                # Delete the protection embed
                try:
                    await message.delete()
                except Exception as e:
                    if self.DEBUG:
                        print(f"[EventGate] ERROR deleting cancelled timer embed: {e}")
                return
            
            try:
                remaining_time = max(0, wait_until - time.time())
                # Wait for up to 1 second or remaining time, whichever is shorter
                check_interval = min(1.0, remaining_time)
                
                congrats_msg = await self.bot.wait_for(
                    'message', check=check, timeout=check_interval
                )
                self.handled_congrats.add(congrats_msg.id)
                await self.process_congratulations(congrats_msg, message, reference_message, event_type)
                return
            except asyncio.TimeoutError:
                # Continue checking for cancellation
                continue
        
        # Timer expired naturally
        raise asyncio.TimeoutError()

    async def process_congratulations(self, congrats_message, original_message, reference_message, event_type="shiny"):
        try:
            anti_thief: Anti_Thief = self.bot.get_cog('Anti_Thief')
            channel_id = original_message.channel.id
            hunters = self.channel_hunters.get(channel_id, {})
            
            if event_type == "shiny":
                shiny_hunters = hunters.get('shiny', [])
                quest_user_ids = [str(h.id) for h in shiny_hunters]
                log_channel_method = anti_thief.mongo.get_shiny_log_channel
                title = "Shiny Thief Detected!"
            else:  # collection
                collectors = hunters.get('collectors', [])
                quest_user_ids = [str(c.id) for c in collectors]
                log_channel_method = anti_thief.mongo.get_collection_log_channel
                title = "Collection Thief Detected!"

            who_caught_id = re.search(r"<@(\d+)>", congrats_message.content).group(1)
            
            if who_caught_id not in quest_user_ids:
                non_hunter = await self.bot.fetch_user(who_caught_id)
                
                p_match = re.search(r"level \d+ ((?:[A-Z][a-z]*\s*)+)", congrats_message.content)
                pokemon_name = p_match.group(1).strip() if p_match else "Unknown Pokémon"

                phase_hours, offense_number = await self.calculate_offense_phase(original_message.guild.id, non_hunter.id)
                await self.timeout_user(non_hunter, original_message.guild.id, phase_hours)

                embed = Embed(
                    title=title,
                    description=f"<:sigh:1328502167153410068> {non_hunter.mention} stole **{pokemon_name}**. "
                                f"Timed out for {phase_hours}h. Offense {offense_number}x.",
                    color=self.primary_color,
                )
                await reference_message.channel.send(embed=embed)

                # Log embed
                logger_channel_id = await log_channel_method(reference_message.guild.id)
                        
                if logger_channel_id:
                    logger_channel = self.bot.get_channel(logger_channel_id)
                    if logger_channel:
                        log_embed = Embed(
                            title="Shiny Theft" if event_type == "shiny" else "Collection Theft",
                            description=(
                                f"**User:** {non_hunter.mention} (`{non_hunter.id}`)\n"
                                f"**Pokémon:** {pokemon_name}\n"
                                f"**Location:** [{reference_message.channel.name}]({congrats_message.jump_url})\n"
                                f"**Timeout Duration:** {phase_hours}h\n"
                                f"**Offense:** {offense_number}x"
                            ),
                            color=self.primary_color,
                        )
                        if non_hunter.avatar:
                            log_embed.set_thumbnail(url=non_hunter.avatar.url)
                        log_embed.set_footer(icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None,
                                             text='Anya Logger')
                        await logger_channel.send(embed=log_embed)
                await self.delete_embed_on_catch(original_message)
                return

            # Not a thief
            if event_type == "shiny":
                shiny_hunter = next((h for h in shiny_hunters if str(h.id) == who_caught_id), None)
                if shiny_hunter:
                    thumbnails = [
                        "https://cdn.discordapp.com/emojis/1328500899953512569.webp?size=96&animated=true",
                        "https://media.discordapp.net/attachments/1279353553110040596/1417134726631919716/image-removebg-preview_28.png?ex=68c9610f&is=68c80f8f&hm=8d103ce1912a9f059c5627db2d267b105f5dc430381c0b7ade92678877260e94&=&format=webp&quality=lossless&width=563&height=563",
                        "https://media.discordapp.net/attachments/1279353553110040596/1417137329193091162/image-removebg-preview_30.png?ex=68c9637c&is=68c811fc&hm=a4a79fb63c790cb7ba4ad86f65cdfc0d4114007117f35b4731c22d5157547b12&=&format=webp&quality=lossless&width=563&height=563"]
                    descriptions = [
                        "Nice job, <@{user_id}>! You're one step closer to finding a shiny.",
                        "Keep hunting, <@{user_id}>! That shiny is waiting for you.",
                        "You're making progress, <@{user_id}>! Stay determined.",
                        "Almost there, <@{user_id}>! One step closer to the shiny Pokémon.",
                        "Best of luck on your shiny hunt, <@{user_id}>!"
                    ]
                    embed = Embed(
                        title=":sparkles: Congratulations!",
                        description=random.choice(descriptions).format(user_id=who_caught_id),
                        color=self.primary_color,
                    )

                    embed.set_thumbnail(url=random.choice(thumbnails))
                    await reference_message.channel.send(embed=embed)
                    await self.delete_embed_on_catch(original_message)
            else:
                await self.delete_embed_on_catch(original_message)

        except Exception as e:
            if self.DEBUG:
                print(f"[EventGate] ERROR processing congratulations: {e}")
            traceback.print_exc()

    async def calculate_offense_phase(self, guild_id: int, user_id: int):
        now = datetime.utcnow()
        if guild_id not in self.offenses_cache:
            # Load from Mongo
            doc = await self.mongo_sh.db.find_one({"guild_id": guild_id})
            if doc and "offenses_cache" in doc:
                cached = doc["offenses_cache"]
                self.offenses_cache[guild_id] = {}
                for suid, offenses in cached.items():
                    uid = int(suid)
                    self.offenses_cache[guild_id][uid] = [(datetime.fromisoformat(ts), dur) for ts, dur in offenses]
            else:
                self.offenses_cache[guild_id] = {}
        if user_id not in self.offenses_cache[guild_id]:
            self.offenses_cache[guild_id][user_id] = []

        # Remove expired offenses
        self.offenses_cache[guild_id][user_id] = [
            (ts, dur) for ts, dur in self.offenses_cache[guild_id][user_id]
            if ts + timedelta(days=self.PENALTY_EXPIRY_DAYS) > now
        ]

        offenses_count = len(self.offenses_cache[guild_id][user_id])
        phase_index = min(offenses_count, len(self.OFFENSE_PHASES) - 1)
        phase_hours = self.OFFENSE_PHASES[phase_index]
        self.offenses_cache[guild_id][user_id].append((now, phase_hours))

        # Save cache to Mongo
        mongo_safe_cache = {
            str(uid): [(ts.isoformat(), dur) for ts, dur in user_offenses]
            for uid, user_offenses in self.offenses_cache[guild_id].items()
        }
        await self.mongo_sh.db.update_one(
            {"guild_id": guild_id},
            {"$set": {"offenses_cache": mongo_safe_cache}},
            upsert=True
        )

        return phase_hours, offenses_count + 1

    @staticmethod
    async def allow_all_to_catch(message):
        if message.embeds:
            embed = message.embeds[0]
            embed.description = ":white_check_mark: Everyone may catch the Pokémon now! No restrictions."
            await message.edit(embed=embed)

    async def timeout_user(self, user, guild_id, hours: int):
        try:
            BOT_TOKEN = await get_bot_token()
            timeout_end = datetime.utcnow() + timedelta(hours=hours)
            headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
            payload = {"communication_disabled_until": timeout_end.isoformat() + "Z", "reason": "Shiny theft detected"}
            url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user.id}"
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, json=payload, headers=headers) as resp:
                    if resp.status != 204:
                        text = await resp.text()
                        print(f"[EventGate] ERROR timing out {user.mention}: {resp.status} - {text}")
        except Exception as e:
            print(f"[EventGate] EXCEPTION timing out {user.mention}: {e}")

    @staticmethod
    async def delete_embed_on_catch(message):
        try:
            await message.delete()
        except Exception as e:
            print(f"[EventGate] ERROR deleting embed: {e}")
            
            
            
def setup(bot):
    bot.add_cog(Anti_Thief(bot))
    bot.add_cog(EventGate(bot))