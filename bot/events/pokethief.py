import asyncio
import datetime
import re
import time
import traceback
import aiohttp
import os

from motor.motor_asyncio import AsyncIOMotorClient
from utils.events.pokethief import *
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

    def __init__(self, bot):
        self.bot = bot
        self.shiny_ping_phrase = load_ping_phrase()
        self.shiny_regex = re.compile(r"<@(\d+)>")
        self.shiny_hunters = []
        self.primary_color = primary_color()
        self.mongo = MongoShHelper(db)
        

    async def get_member(self, guild, user_id):
        if isinstance(guild, int):
            guild = self.bot.get_guild(guild)
        try:
            return await guild.fetch_member(user_id)
        except Exception as e:
            print(f"ERROR fetching member {user_id}: {e}")
            return None

    async def process_pings(self, guild, message_content) -> list:
        if isinstance(guild, int):
            guild = self.bot.get_guild(guild)
        if not guild or self.shiny_ping_phrase not in message_content:
            return []

        try:
            start = message_content.find(self.shiny_ping_phrase) + len(self.shiny_ping_phrase)
            lines = message_content[start:].splitlines()
            if len(lines) < 2:
                return []
            mentions_line = lines[1].strip()
            user_ids = self.shiny_regex.findall(mentions_line)
            members = await asyncio.gather(*(self.get_member(guild, int(uid)) for uid in user_ids))
            return [m for m in members if m]
        except Exception as e:
            print(f"ERROR processing pings: {e}")
            return []

    async def is_shiny_hunter(self, user_id: int) -> bool:
        return any(h.id == user_id for h in self.shiny_hunters)
    
    async def is_shiny_protected_channel(self, guild_id: int, channel_id: int) -> bool:
        protected_channels = await self.mongo.get_shiny_protected_channels(guild_id)
        return channel_id in protected_channels

    @commands.command(name='set_phrase', hidden=True)
    async def set_ping_phrase(self, ctx, *, new_phrase: str):
        if ctx.author.id != 1124389055598170182:
            return
        self.shiny_ping_phrase = new_phrase
        save_ping_phrase(new_phrase)
        await ctx.reply(f"Shiny hunt ping phrase updated to: {new_phrase}", mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message):
        is_shiny_protected_channel = await self.is_shiny_protected_channel(message.guild.id, message.channel.id)
        if self.IGNORE_CHANNEL_KEYWORD in message.channel.name.lower():
            return
        if message.author.id in self.BOT_IDS and message.guild:
            if is_shiny_protected_channel:
             self.shiny_hunters = await self.process_pings(message.guild, message.content)
             if self.shiny_hunters:
                await self.bot.get_cog('EventGate').send_shiny_hunt_embed(
                    message.channel, self.shiny_hunters, reference_message=message
                )

class EventGate(commands.Cog):
    DETECT_BOT_ID = 716390085896962058
    WAIT_TIME = 30
    OFFENSE_PHASES = [3, 6, 12, 24, 48]  # hours per offense phase
    PENALTY_EXPIRY_DAYS = 14

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.primary_color = primary_color()
        self.active_events: dict[int, float] = {}
        self.handled_congrats: set[int] = set()
        self.mongo_sh = MongoShHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.offenses_cache: dict[int, dict[int, list]] = {}  # guild_id -> user_id -> [(timestamp, duration)]

    @staticmethod
    def timestamp_gen(timestamp: float) -> str:
        return f"<t:{int(timestamp)}:R>"

    async def send_shiny_hunt_embed(self, channel: TextChannel, shiny_hunters: list, reference_message=None):
        if channel.id in self.active_events:
            return
        wait_until = time.time() + self.WAIT_TIME
        self.active_events[channel.id] = wait_until
        desc = f"{self.timestamp_gen(wait_until)} | waiting for {' '.join(h.mention for h in shiny_hunters)}"
        embed = Embed(description=desc, color=self.primary_color)
        try:
            msg = await channel.send(embed=embed, reference=reference_message)
        except Exception as e:
            print(f"[EventGate] ERROR sending embed: {e}")
            msg = await channel.send(embed=embed)
        await self.start_countdown(msg, wait_until, reference_message)

    async def start_countdown(self, message, wait_until, reference_message):
        try:
            await asyncio.wait_for(
                self.wait_for_congratulations(message, wait_until, reference_message),
                timeout=self.WAIT_TIME
            )
        except asyncio.TimeoutError:
            await self.allow_all_to_catch(message)
        finally:
            self.active_events.pop(message.channel.id, None)

    async def wait_for_congratulations(self, message, wait_until, reference_message):
        def check(m):
            return (
                m.channel.id == message.channel.id
                and m.author.id == self.DETECT_BOT_ID
                and m.id not in self.handled_congrats
                and re.match(r"Congratulations <@(\d+)>! You caught a Level \d+ .+", m.content)
            )
        try:
            congrats_msg = await self.bot.wait_for(
                'message', check=check, timeout=max(0, wait_until - time.time())
            )
            self.handled_congrats.add(congrats_msg.id)
            await self.process_congratulations(congrats_msg, message, reference_message)
        except asyncio.TimeoutError:
            await self.allow_all_to_catch(message)
        except Exception as e:
            print(f"[EventGate] ERROR waiting for congratulations: {e}")
            traceback.print_exc()

    async def process_congratulations(self, congrats_message, original_message, reference_message):
        try:
            anti_thief: Anti_Thief = self.bot.get_cog('Anti_Thief')
            shiny_hunters = await anti_thief.process_pings(reference_message.guild, reference_message.content)

            mentioned_user_id = re.search(r"<@(\d+)>", reference_message.content).group(1)
            who_caught_id = re.search(r"<@(\d+)>", congrats_message.content).group(1)
            quest_user_ids = [str(h.id) for h in shiny_hunters]

            if who_caught_id not in quest_user_ids:
                is_hunter = await anti_thief.is_shiny_hunter(int(who_caught_id))
                if not is_hunter:
                    non_hunter = await self.bot.fetch_user(who_caught_id)
                    p_match = re.search(r"Level \d+ ((?:[A-Z][a-z]*\s*)+)", congrats_message.content)
                    pokemon_name = p_match.group(1).strip() if p_match else "Unknown Pokémon"

                    phase_hours, offense_number = await self.calculate_offense_phase(reference_message.guild.id, non_hunter.id)
                    await self.timeout_user(non_hunter, reference_message.guild.id, phase_hours)

                    embed = Embed(
                        title="Shiny Thief Detected!",
                        description=f"<:sigh:1328502167153410068> {non_hunter.mention} stole **{pokemon_name}**. "
                                    f"Timed out for {phase_hours}h. Offense {offense_number}x.",
                        color=self.primary_color,
                    )
                    await reference_message.channel.send(embed=embed)

                    # Log embed
                    logger_channel_id = await self.mongo_sh.get_shiny_log_channel(reference_message.guild.id)
                    if logger_channel_id:
                        logger_channel = self.bot.get_channel(logger_channel_id)
                        if logger_channel:
                            log_embed = Embed(
                                title="Shiny Theft",
                                description=(
                                    f"**User:** {non_hunter.mention} (`{non_hunter.id}`)\n"
                                    f"**Pokémon:** {pokemon_name}\n"
                                    f"**Location:** [{reference_message.channel.name}]({original_message.jump_url})\n"
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
                    return

            shiny_hunter = next((h for h in shiny_hunters if str(h.id) == mentioned_user_id), None)
            if shiny_hunter:
                embed = Embed(
                    title=":sparkles: Congratulations!",
                    description=f"Best of luck on your shiny hunt, <@{who_caught_id}>!",
                    color=self.primary_color,
                )
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1328500899953512569.webp?size=96&animated=true")
                await reference_message.channel.send(embed=embed)
                await self.delete_embed_on_catch(original_message)
            else:
                await reference_message.channel.send("⚠️ No shiny hunter detected for the channel. Please double-check.")
        except Exception as e:
            print(f"[EventGate] ERROR processing congratulations: {e}")
            traceback.print_exc()

    async def calculate_offense_phase(self, guild_id: int, user_id: int):
        now = datetime.utcnow()
        if guild_id not in self.offenses_cache:
            self.offenses_cache[guild_id] = {}
        if user_id not in self.offenses_cache[guild_id]:
            self.offenses_cache[guild_id][user_id] = []

        # Remove expired offenses
        self.offenses_cache[guild_id][user_id] = [
            (ts, dur) for ts, dur in self.offenses_cache[guild_id][user_id]
            if ts + timedelta(days=self.PENALTY_EXPIRY_DAYS) > now
        ]

        offenses_count = len(self.offenses_cache[guild_id][user_id])
        phase_hours = self.OFFENSE_PHASES[min(offenses_count, len(self.OFFENSE_PHASES)-1)]
        self.offenses_cache[guild_id][user_id].append((now, phase_hours))

        # Save cache to Mongo
        mongo_safe_cache = {
            str(uid): [(ts.isoformat(), dur) for ts, dur in users]
            for uid, users in self.offenses_cache[guild_id].items()
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