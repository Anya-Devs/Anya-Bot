import asyncio
import datetime
import re
import time
import os
import requests
import traceback
import json

from data.local.const import primary_color
from bot.token import get_bot_token, use_test_bot as ut

from imports.log_imports import *
from imports.discord_imports import *

log_dir = "data"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

config_path = "data/commands/pokethief/shiny_ping_config.json"

def timestamp_gen(timestamp: int) -> str:
    dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=datetime.timezone.utc)
    return f'<t:{int(dt.timestamp())}:R>'

def load_ping_phrase():
    if os.path.exists(config_path):
        with open(config_path, 'r') as file:
            config = json.load(file)
        return config.get("shiny_ping_phrase", "**:sparkles: Shiny Hunt Pings:**")
    return "**:sparkles: Shiny Hunt Pings:**"

def save_ping_phrase(new_phrase):
    if not os.path.exists(os.path.dirname(config_path)):
        os.makedirs(os.path.dirname(config_path))
    config = {"shiny_ping_phrase": new_phrase}
    with open(config_path, 'w') as file:
        json.dump(config, file, indent=4)

class Anti_Thief(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_id = [874910942490677270, 1234247716243112100, 854233015475109888, 1250128097941000223]
        self.shiny_hunters = []
        self.shiny_ping_phrase = load_ping_phrase()
        self.shiny_regex = r"<@(\d+)>"
        self.primary_color = primary_color()
        self.ignore_channel = 'incense'

    async def process_pings(self, guild, message_content):
        shiny_hunters = []
        if isinstance(guild, int):
            guild = self.bot.get_guild(guild)
        if not guild:
            print("ERROR: Guild not found!")
            return shiny_hunters

        if self.shiny_ping_phrase in message_content:
            mention_start_index = message_content.find(self.shiny_ping_phrase) + len(self.shiny_ping_phrase)
            lines_after = message_content[mention_start_index:].split("\n")
            mention_part = lines_after[1].strip() if len(lines_after) > 1 else ""
            if mention_part:
                try:
                    shiny_match = re.findall(self.shiny_regex, mention_part)
                    if shiny_match:
                        shiny_hunters = [
                            member for member in [
                                await self.get_member(guild, int(user_id)) for user_id in shiny_match
                            ] if member
                        ]
                except re.error as e:
                    print(f"ERROR: Regex error: {e}")
        return shiny_hunters

    async def get_member(self, guild, user_id):
        try:
            if isinstance(guild, int):
                guild = self.bot.get_guild(guild)
            return await guild.fetch_member(user_id)
        except Exception as e:
            print(f"ERROR: Error fetching member {user_id}: {e}")
            return None

    async def is_shiny_hunter(self, user_id):
        return any(hunter.id == user_id for hunter in self.shiny_hunters)

    @commands.command(name='set_phrase', hidden=True)
    async def set_ping_phrase(self, ctx, *, new_phrase: str):
        if ctx.author.id != 1124389055598170182:
            return
        self.shiny_ping_phrase = new_phrase
        save_ping_phrase(new_phrase)
        await ctx.reply(f"Shiny hunt ping phrase updated to: {new_phrase}", mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message):
        if ut:
            return  # Skip processing in test mode
        if self.ignore_channel in message.channel.name.lower():
            return
        if message.author.id in self.bot_id and message.guild:
            self.shiny_hunters = await self.process_pings(message.guild, message.content)
            if self.shiny_hunters:
                await self.bot.get_cog('EventGate').send_shiny_hunt_embed(
                    message.channel,
                    self.shiny_hunters,
                    reference_message=message
                )
class EventGate(commands.Cog):
    def __init__(self, bot, anti_thief=None):
        self.bot = bot
        self.anti_thief = anti_thief
        self.timeout_duration = datetime.timedelta(seconds=30)  # fixed to 30 seconds
        self.detect_bot_id = 716390085896962058
        self.logger_channel_id = 1278580578593148976
        self.wait_time = 30
        self.primary_color = primary_color()
        self.active_events = {}
        self.handled_congrats = set()
        self.shiny_ping_phrase = load_ping_phrase()

    @staticmethod
    def timestamp_gen(timestamp: float) -> str:
        return f"<t:{int(timestamp)}:R>"

    async def send_shiny_hunt_embed(self, channel, shiny_hunters, reference_message=None):
        if channel.id in self.active_events:
            return  # silently skip

        wait_until = time.time() + self.wait_time
        self.active_events[channel.id] = wait_until

        wait_embed = Embed(
            description=f"{self.timestamp_gen(wait_until)} | waiting for {' '.join([hunter.mention for hunter in shiny_hunters])}",
            color=self.primary_color
        )

        try:
            message = await channel.send(embed=wait_embed, reference=reference_message)
        except Exception as e:
            print(f"ERROR: Failed to send shiny hunt embed: {e}")
            message = await channel.send(embed=wait_embed)

        await self.start_countdown(message, wait_until, reference_message)

    async def start_countdown(self, message, wait_until, reference_message):
        try:
            await asyncio.wait_for(self.wait_for_congratulations(message, wait_until, reference_message), timeout=self.wait_time)
        except asyncio.TimeoutError:
            await self.allow_all_to_catch(message)
        finally:
            self.active_events.pop(message.channel.id, None)

    async def wait_for_congratulations(self, message, wait_until, reference_message):
        def check(m):
            return (
                m.channel.id == message.channel.id and
                m.author.id == self.detect_bot_id and
                m.id not in self.handled_congrats and
                re.match(r"Congratulations <@(\d+)>! You caught a Level \d+ .+", m.content)
            )

        try:
            congrats_message = await self.bot.wait_for(
                'message',
                check=check,
                timeout=max(0, wait_until - time.time())
            )
            self.handled_congrats.add(congrats_message.id)
            await self.process_congratulations(congrats_message, message, reference_message)
        except asyncio.TimeoutError:
            await self.allow_all_to_catch(message)
        except Exception as e:
            print(f"ERROR: Unexpected error in wait_for_congratulations: {e}")
            traceback.print_exc()

    async def process_congratulations(self, congrats_message, original_message, reference_message):
        try:
            self.shiny_ping_phrase = load_ping_phrase()

            quest_user_ids = []
            catch_channel = reference_message.channel

            mentioned_user_id = re.search(r"<@(\d+)>", reference_message.content).group(1)
            who_caught_pokemon_user_id = re.search(r"<@(\d+)>", congrats_message.content).group(1)

            if who_caught_pokemon_user_id not in congrats_message.content:
                report_channel = "https://discord.com/channels/1278580577104040018/1307894465440256100"
                await catch_channel.send(
                    f"⚠️ Something weird is going on. Please submit the issue and screenshot to {report_channel}."
                )
                return

            if self.shiny_ping_phrase in reference_message.content:
                pattern = re.escape(self.shiny_ping_phrase) + r"\s*(.*)"
                match = re.search(pattern, reference_message.content, re.DOTALL)
                if match:
                    shiny_ping_block = match.group(1).strip()
                    quest_user_ids = re.findall(r"<@(\d+)>", shiny_ping_block)

            if who_caught_pokemon_user_id not in quest_user_ids:
                is_shiny_hunter = await self.bot.get_cog('Anti_Thief').is_shiny_hunter(int(who_caught_pokemon_user_id))
                if not is_shiny_hunter:
                    non_hunter = await self.bot.fetch_user(who_caught_pokemon_user_id)
                    p_match = re.search(r"Level \d+ ((?:[A-Z][a-z]*\s*)+)", congrats_message.content)
                    pokemon_name = p_match.group(1).strip() if p_match else "Unknown Pokémon"

                    await self.timeout_user(non_hunter, original_message)

                    embed = Embed(
                        title="Shiny Thief Detected!",
                        description=f"<:sigh:1328502167153410068> {non_hunter.mention} stole **{pokemon_name}**. They've been timed out for 30 seconds.",
                        color=self.primary_color
                    )
                    await catch_channel.send(embed=embed)

                    logger_channel = self.bot.get_channel(self.logger_channel_id)
                    log_embed = Embed(
                        title="Shiny Theft",
                        description=(
                            f"**User:** {non_hunter.mention} (`{non_hunter.id}`)\n"
                            f"**Pokémon:** {pokemon_name}\n"
                            f"**Location:** [{catch_channel.name}]({original_message.jump_url})"
                        ),
                        color=self.primary_color
                    )
                    log_embed.set_thumbnail(url=non_hunter.avatar)
                    log_embed.set_footer(icon_url=self.bot.user.avatar, text='Anya Logger')
                    await logger_channel.send(embed=log_embed)
                    return

            shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(reference_message.guild.id, reference_message.content)
            shiny_hunter = next((hunter for hunter in shiny_hunters if str(hunter.id) == mentioned_user_id), None)

            if shiny_hunter:
                embed = Embed(
                    title=":sparkles: Congratulations!",
                    description=f"Best of luck on your shiny hunt, <@{who_caught_pokemon_user_id}>!",
                    color=self.primary_color
                )
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1328500899953512569.webp?size=96&animated=true")
                await catch_channel.send(embed=embed)
                await self.delete_embed_on_catch(original_message)
            else:
                await catch_channel.send("⚠️ No shiny hunter detected for the channel. Please double-check.")

        except Exception as e:
            print(f"ERROR: Unexpected error in process_congratulations: {e}")
            traceback.print_exc()

    @staticmethod
    async def allow_all_to_catch(message):
        embed = message.embeds[0]
        embed.description = ":white_check_mark: Everyone may catch the Pokémon now! No restrictions."
        await message.edit(embed=embed)

    @staticmethod
    async def timeout_user(user, message):
     try:
        BOT_TOKEN = await get_bot_token()
        GUILD_ID = message.guild.id
        USER_ID = user.id

        timeout_end = datetime.datetime.utcnow() + datetime.timedelta(hours=3)

        headers = {
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json",
        }

        payload = {
            "communication_disabled_until": timeout_end.isoformat() + "Z",
        }

        url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{USER_ID}"

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, json=payload, headers=headers) as response:
                if response.status == 204:
                    print(f"INFO: User {user.mention} timed out for 3 hours.")
                else:
                    text = await response.text()
                    print(f"ERROR: Failed to timeout user {user.mention}: {response.status} - {text}")

     except Exception as e:
        print(f"EXCEPTION: An error occurred while trying to timeout {user.mention}: {e}")
         
    @staticmethod
    async def delete_embed_on_catch(message):
        try:
            await message.delete()
        except Exception as e:
            print(f"ERROR: Error deleting embed: {e}")
            
def setup(bot):
    bot.add_cog(Anti_Thief(bot))
    bot.add_cog(EventGate(bot))
