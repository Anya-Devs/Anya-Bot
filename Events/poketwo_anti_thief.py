import asyncio
import datetime
import re
import time
import os
import requests
import traceback
import logging
import json

# Custom imports
from Imports.discord_imports import *
from Data.const import primary_color

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Timestamp function
def timestamp_gen(timestamp: int) -> str:
    dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=datetime.timezone.utc)
    return f'<t:{int(dt.timestamp())}:R>'  # Returns relative time format (e.g., "in 30 seconds")

# Load shiny ping phrase from config file
def load_ping_phrase():
    config_path = "Data/commands/poketwo_anti_thief/shiny_ping_config.json"
    if os.path.exists(config_path):
        with open(config_path, 'r') as file:
            config = json.load(file)
        return config.get("shiny_ping_phrase", "**:sparkles: Shiny Hunt Pings:**")
    else:
        return "**:sparkles: Shiny Hunt Pings:**"

# Save shiny ping phrase to config file
def save_ping_phrase(new_phrase):
    config_path = "Data/commands/poketwo_anti_thief/shiny_ping_config.json"
    if not os.path.exists(os.path.dirname(config_path)):
        os.makedirs(os.path.dirname(config_path))
    
    config = {"shiny_ping_phrase": new_phrase}
    with open(config_path, 'w') as file:
        json.dump(config, file, indent=4)


class Anti_Thief(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_id = 874910942490677270  # ID of the bot sending shiny hunt messages
        self.shiny_hunters = []
        self.shiny_ping_phrase = load_ping_phrase()  # Load shiny ping phrase from file
        self.shiny_regex = r"<@(\d+)>"
        self.primary_color = primary_color()  # Example primary color

    async def process_pings(self, guild, message_content):
     shiny_hunters = []
     if isinstance(guild, int):
        guild = self.bot.get_guild(guild)
    
     if not guild:
        logger.warning("Guild not found!")
        return shiny_hunters

     if self.shiny_ping_phrase in message_content:
        mention_start_index = message_content.find(self.shiny_ping_phrase) + len(self.shiny_ping_phrase)
        mention_part = message_content[mention_start_index:].split("\n")[0].strip()  # Split at newline and take the first part

        if mention_part:
            try:
                shiny_match = re.findall(self.shiny_regex, mention_part)
                if shiny_match:
                    shiny_hunters = [
                        member for member in [
                            await self.get_member(guild, int(user_id)) for user_id in shiny_match
                            ] if member]
            except re.error as e:
                logger.error(f"Regex error: {e}")

     return shiny_hunters
    
    async def get_member(self, guild, user_id):
        try:
            if isinstance(guild, int):
                guild = self.bot.get_guild(guild)

            return await guild.fetch_member(user_id)
        except Exception as e:
            logger.error(f"Error fetching member {user_id}: {e}")
            return None

    async def is_shiny_hunter(self, user_id):
        return any(hunter.id == user_id for hunter in self.shiny_hunters)
    
    @commands.command(name='set_phrase')
    async def set_ping_phrase(self, ctx, *, new_phrase: str):
        """
        Update the shiny ping phrase used for detecting shiny hunt messages.
        """
        if ctx.author.id != 1124389055598170182:
            return
        
        self.shiny_ping_phrase = new_phrase
        save_ping_phrase(new_phrase)  # Save new phrase to the config file
        await ctx.reply(f"Shiny hunt ping phrase updated to: {new_phrase}", mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot_id and message.guild:  # Ensure message has a valid guild
            self.shiny_hunters = await self.process_pings(message.guild, message.content)
            if self.shiny_hunters:
                await self.bot.get_cog('EventGate').send_shiny_hunt_embed(message.channel, self.shiny_hunters, reference_message=message)

class EventGate(commands.Cog):
    def __init__(self, bot, anti_thief=None):
        self.bot = bot
        self.anti_thief = anti_thief  # Link to Anti_Thief cog
        self.timeout_duration = datetime.timedelta(hours=3)
        self.detect_bot_id = 716390085896962058  # Bot ID for detection
        self.wait_time = 30  # Timer for shiny event in seconds
        self.primary_color = primary_color()  # Example primary color
        self.active_events = {}  # Track active shiny events per channel
        self.handled_congrats = set()  # Track handled congratulatory messages
        self.shiny_ping_phrase = load_ping_phrase()  # Load shiny ping phrase from file


    def timestamp_gen(self, timestamp: int) -> str:
        dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=datetime.timezone.utc)
        return f'<t:{int(dt.timestamp())}:R>'  # Returns relative time format (e.g., "in 30 seconds")

    async def send_shiny_hunt_embed(self, channel, shiny_hunters, reference_message=None):
        if channel.id in self.active_events:
            logger.info(f"Shiny hunt already active in channel {channel.id}. Skipping new event.")
            return  # Avoid multiple shiny hunt events in the same channel

        timestamp = datetime.datetime.utcnow().timestamp()
        wait_until = timestamp + self.wait_time  # Event end time
        self.active_events[channel.id] = wait_until  # Mark the event as active

        wait_embed = Embed(
            description=f"{self.timestamp_gen(wait_until)} | ✨ Shiny hunters: {' '.join([hunter.mention for hunter in shiny_hunters])}",
            color=self.primary_color
        )
        try:
            message = await channel.send(embed=wait_embed, reference=reference_message)
            logger.info(f"Sent shiny hunt embed to channel {channel.id}.")
        except Exception as e:
            logger.error(f"Failed to send shiny hunt embed: {e}")
            message = await channel.send(embed=wait_embed)

        await self.start_countdown(message, wait_until, reference_message)

    async def start_countdown(self, message, wait_until, reference_message):
        try:
            await asyncio.wait_for(self.wait_for_congratulations(message, wait_until, reference_message), timeout=self.wait_time)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout reached in channel {message.channel.id}. Allowing all to catch.")
            await self.allow_all_to_catch(message)
        finally:
            self.active_events.pop(message.channel.id, None)

    async def wait_for_congratulations(self, message, wait_until, reference_message):
        def check(m):
            if m.author.id == self.detect_bot_id and m.id not in self.handled_congrats:
                match = re.match(r"Congratulations <@(\d+)>! You caught a Level \d+ .+", m.content)
                if match:
                    return True
            return False

        try:
            congrats_message = await self.bot.wait_for(
                'message',
                check=check,
                timeout=max(0, wait_until - time.time())
            )
            self.handled_congrats.add(congrats_message.id)
            await self.process_congratulations(congrats_message, message, reference_message)
        except asyncio.TimeoutError:
            logger.warning("Timeout: No congratulatory message detected.")
            await self.allow_all_to_catch(message)
        except Exception as e:
            logger.error(f"Unexpected error in wait_for_congratulations: {e}")
            logger.error("Traceback:")
            traceback.print_exc()

    async def process_congratulations(self, congrats_message, original_message, reference_message):
     try:
        # Initialize the list at the start of the function
        quest_user_ids = []

        # Corrected logging statement
        logger.info(f"Content for reference message: {reference_message.content}")

        # Extract the mentioned user ID from the congrats message and the original reference message
        mentioned_user_id = re.search(r"<@(\d+)>", reference_message.content).group(1)
        who_caught_pokemon_user_id = re.search(r"<@(\d+)>", congrats_message.content).group(1)
        logger.info(f"Mentioned user ID extracted: {mentioned_user_id}")

        # Extract Quest Pings from the reference message content
        quest_ping_phrase = self.shiny_ping_phrase
        logger.debug("Phrase Detected: ", quest_ping_phrase)
        if quest_ping_phrase in reference_message.content:
            quest_pings_content = reference_message.content.split(quest_ping_phrase)[1].strip()
            # Extract all user IDs mentioned in the Quest Pings
            quest_user_ids = re.findall(r"<@(\d+)>", quest_pings_content)
            logger.info(f"Extracted Quest Pings user IDs: {quest_user_ids}")
            
            # First, delete the original message
            logger.info(f"Attempting to delete original message {original_message.id} in channel {original_message.channel.id}")
            x = await original_message.delete()

            # Check if the original message is still available
            if not x:
                logger.warning(f"Original message {original_message.id} is no longer available for reference.")
            
            # Check if who_caught_pokemon_user_id is in the Quest Pings list
            if who_caught_pokemon_user_id not in quest_user_ids:
                logger.warning(f"{who_caught_pokemon_user_id} is not in the Quest Pings list. Triggering Shiny Thief.")
                # Trigger shiny thief logic
                non_hunter = await self.bot.fetch_user(who_caught_pokemon_user_id)
                p_match = re.search(r"Level \d+ (\w+)", congrats_message.content)
                if p_match:
                        pokemon_name = p_match.group(1)

                
                # Timeout the non-hunter user for stealing the shiny Pokémon
                await self.timeout_user(non_hunter, original_message)
                embed = Embed(
                    title="Shiny Thief Detected!",
                    description=f"{non_hunter.mention} stole **{pokemon_name}**. They've been timed out for 3 hours.",
                    color=self.primary_color  # Color for non-hunter detection
                )
                # Send a warning embed with reference to the original message
                await reference_message.channel.send(embed=embed)  # Removed the reference
                logger.info(f"Non-hunter {non_hunter.mention} detected and timed out.")
                return  # Exit early if thief is detected

            # If the user is in the Quest Pings list, process further
            else:
                logger.info(f"User {mentioned_user_id} is in the Quest Pings list. Proceeding with congratulations.")

                # Check if the mentioned user is a shiny hunter
                logger.info(f"Checking if user {mentioned_user_id} is a shiny hunter...")
                is_shiny_hunter = await self.bot.get_cog('Anti_Thief').is_shiny_hunter(int(mentioned_user_id))
                logger.info(f"Is user {mentioned_user_id} a shiny hunter? {is_shiny_hunter}")

                if is_shiny_hunter:
                    # If they are a shiny hunter, process shiny hunter logic
                    logger.info(f"Processing shiny hunters for the reference message {reference_message.id}.")
                    shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(reference_message.guild.id, reference_message.content)
                    shiny_hunter = next((hunter for hunter in shiny_hunters if str(hunter.id) == mentioned_user_id), None)

                    if shiny_hunter:
                        logger.info(f"Shiny hunter {shiny_hunter.mention} found. Stopping countdown.")
                        self.active_events[original_message.channel.id] = 0  # Stop countdown
                        embed = Embed(
                            title="Congratulations!",
                            description=f"✅ Good luck on your shiny hunt, {shiny_hunter.mention}! Keep up the great work!",
                            color=0x00FF00  # Green color for success
                        )
                        # Send a congratulatory embed with reference to the original message
                        await reference_message.channel.send(embed=embed)  # Removed the reference here as well
                        logger.info(f"Sent congratulatory message to {shiny_hunter.mention}.")
                        await self.delete_embed_on_catch(original_message)
                    else:
                        logger.warning(f"Shiny hunter {mentioned_user_id} not found in the list of shiny hunters.")
                else:
                    # If the user is not a shiny hunter, treat them as a non-hunter
                    logger.warning(f"User {mentioned_user_id} is not a shiny hunter. Initiating timeout.")
                    non_hunter = await self.bot.fetch_user(mentioned_user_id)
                    
                    # Timeout the non-hunter user for stealing the shiny Pokémon
                    await self.timeout_user(non_hunter, original_message)
                    p_match = re.search(r"Level \d+ (\w+)", congrats_message)
                    if p_match:
                        pokemon_name = p_match.group(1)

                    embed = Embed(
                        title="Shiny Thief Detected!",
                        description=f"{non_hunter.mention} stole **{pokemon_name}**. They've been timed out for 3 hours.",
                        color=self.primary_color  # Color for non-hunter detection
                    )
                    # Send a warning embed with reference to the original message
                    await reference_message.channel.send(embed=embed)  # Removed the reference
                    logger.info(f"Non-hunter {non_hunter.mention} detected and timed out.")

     except Exception as e:
        # Log any unexpected errors
        logger.error(f"Unexpected error in process_congratulations: {e}")
        logger.error("Traceback:")
        traceback.print_exc()
    async def allow_all_to_catch(self, message):
        embed = message.embeds[0]
        embed.description = "✅ Everyone may catch the Pokémon now! No restrictions."
        embed.color = 0x00FF00
        await message.edit(embed=embed)
        logger.info("Everyone is allowed to catch the Pokémon now.")

    async def timeout_user(self, user, message):
        BOT_TOKEN = os.getenv("TOKEN")
        GUILD_ID = message.guild.id
        USER_ID = user.id

        timeout_duration = 180  # 3 hours
        timeout_end = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout_duration)

        headers = {
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json",
        }

        payload = {
            "communication_disabled_until": timeout_end.isoformat() + "Z",
        }

        url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{USER_ID}"

        response = requests.patch(url, json=payload, headers=headers)

        if response.status_code == 204:
            logger.info(f"User {user.mention} timed out for 3 hours.")
        else:
            logger.error(f"Failed to timeout user {user.mention}: {response.status_code}")

    async def delete_embed_on_catch(self, message):
        try:
            await message.delete()
            logger.info("Embed deleted after successful catch.")
        except Exception as e:
            logger.error(f"Error deleting embed: {e}")


def setup(bot):
    bot.add_cog(Anti_Thief(bot))
    bot.add_cog(EventGate(bot))
