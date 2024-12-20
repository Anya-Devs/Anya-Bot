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
        self.logger_channel_id = 1278580578593148976
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
        # Ensure the message is from the correct channel
        if m.channel.id != message.channel.id:
            return False
        
        if m.author.id == self.detect_bot_id and m.id not in self.handled_congrats:
            match = re.match(r"Congratulations <@(\d+)>! You caught a Level \d+ .+", m.content)
            if match:
                return True
        return False

     try:
        # Wait for the congratulatory message in the correct channel only
        congrats_message = await self.bot.wait_for(
            'message',
            check=check,
            timeout=max(0, wait_until - time.time())
        )
        self.handled_congrats.add(congrats_message.id)
        await self.process_congratulations(congrats_message, message, reference_message)
     except asyncio.TimeoutError:
        logger.warning(f"Timeout: No congratulatory message detected in channel {message.channel.id}.")
        await self.allow_all_to_catch(message)
     except Exception as e:
        logger.error(f"Unexpected error in wait_for_congratulations: {e}")
        logger.error("Traceback:")
        traceback.print_exc()
        
    async def process_congratulations(self, congrats_message, original_message, reference_message):
     try:
        # Load the shiny ping phrase
        self.shiny_ping_phrase = load_ping_phrase()

        # Initialize variables
        quest_user_ids = []
        catch_channel = reference_message.channel
        logger.info(f"Reference message content: {reference_message.content}")

        # Extract user IDs from messages
        mentioned_user_id = re.search(r"<@(\d+)>", reference_message.content).group(1)
        who_caught_pokemon_user_id = re.search(r"<@(\d+)>", congrats_message.content).group(1)

        # Validate that the shiny ping phrase exists in the congratulatory message
        if who_caught_pokemon_user_id not in congrats_message.content:
            logger.warning(f"Something weird happened in {catch_channel.channel.name}.")
            report_channel = "https://discord.com/channels/1278580577104040018/1307894465440256100"
            await catch_channel.send(
                f"⚠️ Something weird is going on. Please submit the issue and screenshot to {report_channel}."
            )
            return

        # Extract quest pings from the reference message
        if self.shiny_ping_phrase in reference_message.content:
            quest_pings_content = reference_message.content.split(self.shiny_ping_phrase)[1].strip()
            quest_user_ids = re.findall(r"<@(\d+)>", quest_pings_content)
            logger.info(f"Extracted Shiny Pings user IDs: {quest_user_ids}")

        # Verify the catcher against quest pings and shiny hunter status
        if who_caught_pokemon_user_id not in quest_user_ids:
            logger.warning(f"User {who_caught_pokemon_user_id} is not in the quest pings list.")
            is_shiny_hunter = await self.bot.get_cog('Anti_Thief').is_shiny_hunter(int(who_caught_pokemon_user_id))

            if not is_shiny_hunter:
                # Log potential theft and notify channel
                logger.info(f"User {who_caught_pokemon_user_id} is not a shiny hunter. Logging incident.")
                non_hunter = await self.bot.fetch_user(who_caught_pokemon_user_id)

                # Extract Pokémon name
                p_match = re.search(r"Level \d+ (\w+)", congrats_message.content)
                pokemon_name = p_match.group(1) if p_match else "Unknown Pokémon"

                # Timeout the non-hunter user for stealing the shiny Pokémon
                await self.timeout_user(non_hunter, original_message)

                # Send a warning embed to the channel
                embed = Embed(
                    title="Shiny Thief Detected!",
                    description=f"🚨 {non_hunter.mention} stole **{pokemon_name}**. They've been timed out for 3 hours.",
                    color=self.primary_color  # Color for non-hunter detection
                )
                await catch_channel.send(embed=embed)
                logger.info(f"Non-hunter {non_hunter.mention} detected and timed out.")

                # Log the incident details to the logger channel
                logger_channel = self.bot.get_channel(self.logger_channel_id)
                log_embed = Embed(
                    title="Shiny Theft",
                    description=(
                        f"**User:** {non_hunter.mention} (`{non_hunter.id}`)\n"
                        f"**Pokémon:** {pokemon_name}\n"
                        f"**Location** [{catch_channel.name}]({original_message.jump_url})\n"  # Added message link
                        f"**Action Taken:** :hourglass:  Timeout - 3 hours"
                    ),
                    color=primary_color()
                )
                log_embed.set_thumbnail(url=non_hunter.avatar)
                log_embed.set_footer(icon_url=self.bot.user.avatar, text='Anya Logger')
                await logger_channel.send(embed=log_embed)
                return

        # If the catcher is valid, send congratulations
        logger.info(f"User {who_caught_pokemon_user_id} is valid. Proceeding with congratulations.")
        shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(reference_message.guild.id, reference_message.content)
        shiny_hunter = next((hunter for hunter in shiny_hunters if str(hunter.id) == mentioned_user_id), None)

        if shiny_hunter:
            embed = Embed(
                title="Congratulations!",
                description=f"✅ Good luck on your shiny hunt, <@{who_caught_pokemon_user_id}>! Keep up the great work!",
                color=0x00FF00
            )
            await catch_channel.send(embed=embed)
            await self.delete_embed_on_catch(original_message)
        else:
            logger.warning(f"No shiny hunter found for user {mentioned_user_id}.")
            await catch_channel.send("⚠️ No shiny hunter detected for the quest. Please double-check.")

     except Exception as e:
        logger.error(f"Unexpected error in process_congratulations: {e}")
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