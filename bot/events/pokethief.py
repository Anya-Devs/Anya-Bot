import asyncio
import datetime
import re
import time
import os
import json
import traceback
import aiohttp

from data.local.const import primary_color
from bot.token import get_bot_token, use_test_bot as ut
from imports.log_imports import *
from imports.discord_imports import *

# Ensure data directory exists
os.makedirs("data/commands/pokethief", exist_ok=True)
CONFIG_PATH = "data/commands/pokethief/shiny_ping_config.json"


def load_ping_phrase() -> str:
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f).get("shiny_ping_phrase", "**:sparkles: Shiny Hunt Pings:**")
    return "**:sparkles: Shiny Hunt Pings:**"


def save_ping_phrase(new_phrase: str):
    with open(CONFIG_PATH, 'w') as f:
        json.dump({"shiny_ping_phrase": new_phrase}, f, indent=4)


class Anti_Thief(commands.Cog):
    BOT_IDS = {874910942490677270, 1234247716243112100, 854233015475109888, 1250128097941000223}
    IGNORE_CHANNEL_KEYWORD = 'incense'

    def __init__(self, bot):
        self.bot = bot
        self.shiny_ping_phrase = load_ping_phrase()
        self.shiny_regex = re.compile(r"<@(\d+)>")
        self.shiny_hunters = []
        self.primary_color = primary_color()

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

    @commands.command(name='set_phrase', hidden=True)
    async def set_ping_phrase(self, ctx, *, new_phrase: str):
        if ctx.author.id != 1124389055598170182:
            return
        self.shiny_ping_phrase = new_phrase
        save_ping_phrase(new_phrase)
        await ctx.reply(f"Shiny hunt ping phrase updated to: {new_phrase}", mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message):
        if ut or self.IGNORE_CHANNEL_KEYWORD in message.channel.name.lower():
            return
        if message.author.id in self.BOT_IDS and message.guild:
            self.shiny_hunters = await self.process_pings(message.guild, message.content)
            if self.shiny_hunters:
                await self.bot.get_cog('EventGate').send_shiny_hunt_embed(
                    message.channel, self.shiny_hunters, reference_message=message
                )


class EventGate(commands.Cog):
    DETECT_BOT_ID = 716390085896962058
    LOGGER_CHANNEL_ID = 1278580578593148976
    TIMEOUT_HOURS = 3
    WAIT_TIME = 30  # seconds

    def __init__(self, bot, anti_thief=None):
        self.bot = bot
        self.primary_color = primary_color()
        self.active_events = {}
        self.handled_congrats = set()
        self.shiny_ping_phrase = load_ping_phrase()

    @staticmethod
    def timestamp_gen(timestamp: float) -> str:
        return f"<t:{int(timestamp)}:R>"

    async def send_shiny_hunt_embed(self, channel, shiny_hunters, reference_message=None):
        if channel.id in self.active_events:
            return
        wait_until = time.time() + self.WAIT_TIME
        self.active_events[channel.id] = wait_until
        desc = f"{self.timestamp_gen(wait_until)} | waiting for {' '.join(h.mention for h in shiny_hunters)}"
        embed = Embed(description=desc, color=self.primary_color)
        try:
            msg = await channel.send(embed=embed, reference=reference_message)
        except Exception as e:
            print(f"ERROR sending embed: {e}")
            msg = await channel.send(embed=embed)
        await self.start_countdown(msg, wait_until, reference_message)

    async def start_countdown(self, message, wait_until, reference_message):
        try:
            await asyncio.wait_for(
                self.wait_for_congratulations(message, wait_until, reference_message),
                timeout=self.WAIT_TIME,
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
            print(f"ERROR in wait_for_congratulations: {e}")
            traceback.print_exc()

    async def process_congratulations(self, congrats_message, original_message, reference_message):
        try:
            self.shiny_ping_phrase = load_ping_phrase()
            catch_channel = reference_message.channel

            mentioned_user_id = re.search(r"<@(\d+)>", reference_message.content).group(1)
            who_caught_id = re.search(r"<@(\d+)>", congrats_message.content).group(1)

            if who_caught_id not in congrats_message.content:
                report_channel = "https://discord.com/channels/1278580577104040018/1307894465440256100"
                await catch_channel.send(
                    f"⚠️ Something weird is going on. Please submit the issue and screenshot to {report_channel}."
                )
                return

            quest_user_ids = []
            if self.shiny_ping_phrase in reference_message.content:
                pattern = re.escape(self.shiny_ping_phrase) + r"\s*(.*)"
                match = re.search(pattern, reference_message.content, re.DOTALL)
                if match:
                    quest_user_ids = re.findall(r"<@(\d+)>", match.group(1).strip())

            if who_caught_id not in quest_user_ids:
                is_hunter = await self.bot.get_cog('Anti_Thief').is_shiny_hunter(int(who_caught_id))
                if not is_hunter:
                    non_hunter = await self.bot.fetch_user(who_caught_id)
                    p_match = re.search(r"Level \d+ ((?:[A-Z][a-z]*\s*)+)", congrats_message.content)
                    pokemon_name = p_match.group(1).strip() if p_match else "Unknown Pokémon"

                    await self.timeout_user(non_hunter, original_message)

                    embed = Embed(
                        title="Shiny Thief Detected!",
                        description=f"<:sigh:1328502167153410068> {non_hunter.mention} stole **{pokemon_name}**. They've been timed out for {self.TIMEOUT_HOURS} hours.",
                        color=self.primary_color,
                    )
                    await catch_channel.send(embed=embed)

                    logger_channel = self.bot.get_channel(self.LOGGER_CHANNEL_ID)
                    log_embed = Embed(
                        title="Shiny Theft",
                        description=(
                            f"**User:** {non_hunter.mention} (`{non_hunter.id}`)\n"
                            f"**Pokémon:** {pokemon_name}\n"
                            f"**Location:** [{catch_channel.name}]({original_message.jump_url})"
                        ),
                        color=self.primary_color,
                    )
                    if non_hunter.avatar:
                        log_embed.set_thumbnail(url=non_hunter.avatar.url)
                    log_embed.set_footer(icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None, text='Anya Logger')
                    await logger_channel.send(embed=log_embed)
                    return

            shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(reference_message.guild.id, reference_message.content)
            shiny_hunter = next((h for h in shiny_hunters if str(h.id) == mentioned_user_id), None)
            if shiny_hunter:
                embed = Embed(
                    title=":sparkles: Congratulations!",
                    description=f"Best of luck on your shiny hunt, <@{who_caught_id}>!",
                    color=self.primary_color,
                )
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1328500899953512569.webp?size=96&animated=true")
                await catch_channel.send(embed=embed)
                await self.delete_embed_on_catch(original_message)
            else:
                await catch_channel.send("⚠️ No shiny hunter detected for the channel. Please double-check.")
        except Exception as e:
            print(f"ERROR in process_congratulations: {e}")
            traceback.print_exc()

    @staticmethod
    async def allow_all_to_catch(message):
        embed = message.embeds[0]
        embed.description = ":white_check_mark: Everyone may catch the Pokémon now! No restrictions."
        await message.edit(embed=embed)

    async def timeout_user(self, user, message):
        try:
            BOT_TOKEN = await get_bot_token()
            guild_id = message.guild.id
            user_id = user.id
            timeout_end = datetime.datetime.utcnow() + datetime.timedelta(hours=self.TIMEOUT_HOURS)

            headers = {
                "Authorization": f"Bot {BOT_TOKEN}",
                "Content-Type": "application/json",
            }
            payload = {
                "communication_disabled_until": timeout_end.isoformat() + "Z",
                "reason": "Shiny theft detected - user timed out for stealing a shiny."
                }
            
            url = f"https://discord.com/api/v10/guilds/{guild_id}/members/{user_id}"

            async with aiohttp.ClientSession() as session:
                async with session.patch(url, json=payload, headers=headers) as resp:
                    if resp.status == 204:
                        return
                        #print(f"INFO: Timed out {user.mention} for {self.TIMEOUT_HOURS} hours.")
                    else:
                        text = await resp.text()
                        return
                        #print(f"ERROR timing out {user.mention}: {resp.status} - {text}")
        except Exception as e:
            print(f"EXCEPTION timing out {user.mention}: {e}")

    @staticmethod
    async def delete_embed_on_catch(message):
        try:
            await message.delete()
        except Exception as e:
            print(f"ERROR deleting embed: {e}")


def setup(bot):
    bot.add_cog(Anti_Thief(bot))
    bot.add_cog(EventGate(bot))
