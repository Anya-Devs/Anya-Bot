import asyncio
import datetime
import re
import time
import os
import requests

from discord import Embed
from discord.ext import commands

# Custom imports
from Imports.discord_imports import *
from Data.const import primary_color

# Timestamp function
def timestamp_gen(timestamp: int) -> str:
    dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=datetime.timezone.utc)
    return f'<t:{int(dt.timestamp())}:R>'  # Returns relative time format (e.g., "in 30 seconds")

class Anti_Thief(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_id = 874910942490677270  # ID of the bot sending shiny hunt messages
        self.shiny_hunters = []
        self.shiny_ping_phrase = "**Shiny Hunt Pings:**"
        self.shiny_regex = r"<@(\d+)>"
        self.primary_color = primary_color

    async def process_pings(self, guild, message_content):
        shiny_hunters = []
        if self.shiny_ping_phrase in message_content:
            mention_start_index = message_content.find(self.shiny_ping_phrase) + len(self.shiny_ping_phrase)
            mention_part = message_content[mention_start_index:].strip()

            if mention_part:
                try:
                    shiny_match = re.findall(self.shiny_regex, mention_part)
                    if shiny_match:
                        shiny_hunters = [
                            await self.get_member(guild, int(user_id))
                            for user_id in shiny_match
                            if await self.get_member(guild, int(user_id))
                        ]
                except re.error as e:
                    print(f"Regex error: {e}")

        return shiny_hunters

    async def get_member(self, guild, user_id):
        try:
            return await guild.fetch_member(user_id)
        except Exception as e:
            print(f"Error fetching member {user_id}: {e}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot_id:
            self.shiny_hunters = await self.process_pings(message.guild, message.content)
            channel = message.channel
            if len(self.shiny_hunters) > 0:
                await self.bot.get_cog('EventGate').send_shiny_hunt_embed(channel, self.shiny_hunters, reference_message=message)

class EventGate(commands.Cog):
    def __init__(self, bot, anti_thief=None):
        self.bot = bot
        self.anti_thief = anti_thief  # Link to Anti_Thief cog
        self.timeout_duration = datetime.timedelta(hours=3)  # Timeout duration (3 hours)
        self.detect_bot_id = 716390085896962058  # Bot ID for detection
        self.wait_time = 30  # Timer for shiny event in seconds
        self.primary_color = primary_color()  # Example primary color
        self.active_events = {}  # Track active shiny events per channel
        self.handled_congrats = set()  # Track handled congratulatory messages

    def timestamp_gen(self, timestamp: int) -> str:
        dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=datetime.timezone.utc)
        return f'<t:{int(dt.timestamp())}:R>'  # Returns relative time format (e.g., "in 30 seconds")

    async def send_shiny_hunt_embed(self, channel, shiny_hunters, reference_message=None):
        if channel.id in self.active_events:
            return  # Avoid multiple shiny hunt events in the same channel

        timestamp = datetime.datetime.utcnow().timestamp()
        wait_until = timestamp + self.wait_time  # Event end time
        self.active_events[channel.id] = wait_until  # Mark the event as active

        embed = Embed(
            description=f"{self.timestamp_gen(wait_until)} | ✨ Shiny hunters: {' '.join([hunter.mention for hunter in shiny_hunters])}",
            color=self.primary_color
        )
        message = await channel.send(embed=embed, reference=reference_message)
        await self.start_countdown(message, wait_until)

    async def start_countdown(self, message, wait_until):
        try:
            await asyncio.wait_for(self.wait_for_congratulations(message, wait_until), timeout=self.wait_time)
        except asyncio.TimeoutError:
            await self.allow_all_to_catch(message)
        finally:
            self.active_events.pop(message.channel.id, None)

    async def wait_for_congratulations(self, message, wait_until):
        def check(m):
            if m.author.id == self.detect_bot_id and m.id not in self.handled_congrats:
                match = re.match(r"Congratulations <@(\d+)>! You caught a Level \d+ .+", m.content)
                if match:
                    return True
            return False

        congrats_message = await self.bot.wait_for('message', check=check, timeout=wait_until - time.time())
        self.handled_congrats.add(congrats_message.id)
        await self.process_congratulations(congrats_message, message)

    async def process_congratulations(self, congrats_message, original_message):
        mentioned_user_id = re.search(r"<@(\d+)>", congrats_message.content).group(1)
        shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(original_message.guild, original_message.content)

        shiny_hunter = next((hunter for hunter in shiny_hunters if str(hunter.id) == mentioned_user_id), None)
        if shiny_hunter:
            embed = Embed(
                title="Congratulations!",
                description=f"Well done, {shiny_hunter.mention}, good luck on your streak!",
                color=self.primary_color
            )
            await original_message.channel.send(embed=embed, reference=original_message)
        else:
            non_hunter = await self.bot.fetch_user(mentioned_user_id)
            await self.timeout_user(non_hunter, original_message)
            embed = Embed(
                title="Shiny Thief Detected!",
                description=f"{non_hunter.mention} tried to steal the shiny Pokémon. They've been timed out for 3 hours.",
                color=self.primary_color
            )
            await original_message.channel.send(embed=embed, reference=original_message)

    async def allow_all_to_catch(self, message):
        embed = message.embeds[0]
        embed.description = "✅ Everyone may catch the Pokémon now! No restrictions."
        embed.color = 0x00FF00  # Green color for success
        await message.edit(embed=embed)

    async def timeout_user(self, user, message):
        BOT_TOKEN = os.getenv("TOKEN")  # Replace with your bot token
        GUILD_ID = message.guild.id  # Use the guild ID of the user
        USER_ID = user.id  # Use the ID of the user to be timed out

        # Calculate the timeout end time
        timeout_duration = 180  # Timeout duration in minutes (3 hours)
        timeout_end = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_duration)

        # API request headers
        headers = {
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json",
        }

        # API request payload
        payload = {
            "communication_disabled_until": timeout_end.isoformat() + "Z"  # UTC timestamp
        }

        # Send the request to timeout the user
        url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{USER_ID}"
        response = requests.patch(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"User {USER_ID} has been timed out successfully.")
        else:
            print(f"Failed to timeout user {USER_ID}: {response.status_code}, {response.text}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.detect_bot_id and "Congratulations" in message.content:
            if message.id not in self.handled_congrats:
                await self.wait_for_congratulations(message, time.time() + self.wait_time)
                self.handled_congrats.add(message.id)
        else:
            shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(message.guild, message.content)
            if shiny_hunters:
                await self.send_shiny_hunt_embed(message.channel, shiny_hunters, reference_message=message)

async def setup(bot):
    anti_thief = Anti_Thief(bot)
    event_gate = EventGate(bot, anti_thief)
    bot.add_cog(anti_thief)
    bot.add_cog(event_gate)
