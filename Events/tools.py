import redis
import json
import logging
import os
import asyncio
import re
from datetime import datetime, timedelta, timezone
from discord.ext import commands
import motor.motor_asyncio
from pymongo.errors import PyMongoError
from Cogs.quest import Quest_Data

# Initialize logger
logger = logging.getLogger(__name__)

# Configurations for tool durations (can be extended as needed)
class Config:
    TOOL_DURATIONS = {
        "Motion Alarm": 20,  # Duration in seconds
        "Chimera": 0,  # No duration for Chimera
        "Shadow Cloak": 45,  # Duration for Shadow Cloak in minutes
        "Spy Briefcase": 0,  # No duration, but points are siphoned immediately
    }

# Redis Client
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

def timestamp_gen(timestamp: int) -> str:
    """Generate a timestamp string in Discord's time format."""
    dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
    return f'<t:{int(dt.timestamp())}:R>'

class AffectedUser:
    def __init__(self, guild_id: str, user_id: str, redis_client=None):
        self.guild_id = guild_id
        self.user_id = user_id
        self.redis = redis_client if redis_client else redis.StrictRedis(host='localhost', port=6379, db=0)

    def _get_tool_key(self, tool: str) -> str:
        """Generate a Redis key for the tool effect of the user."""
        return f"affected_user:{self.guild_id}:{self.user_id}:{tool}"

    async def apply_tool(self, tool: str):
        """Apply the tool effect on the user and store the effect in Redis."""
        tool_key = self._get_tool_key(tool)
        current_time = datetime.utcnow()

        if tool == "Motion Alarm":
            duration = timedelta(seconds=Config.TOOL_DURATIONS.get("Motion Alarm", 20))
            expiration_time = current_time + duration
            effect = {"type": "Motion Alarm", "expires_at": expiration_time.isoformat()}

        elif tool == "Chimera":
            effect = {"type": "Chimera", "expires_at": None}

        elif tool == "Shadow Cloak":
            duration = timedelta(minutes=Config.TOOL_DURATIONS.get("Shadow Cloak", 45))
            expiration_time = current_time + duration
            effect = {"type": "Shadow Cloak", "expires_at": expiration_time.isoformat()}

        elif tool == "Spy Briefcase":
            effect = {"type": "Spy Briefcase", "expires_at": None}

        else:
            return None  # Unknown tool, return None

        # Store the effect in Redis
        self.redis.set(tool_key, json.dumps(effect))
        
        if effect["expires_at"]:
            expiration_time = datetime.fromisoformat(effect["expires_at"]) - current_time
            self.redis.expire(tool_key, max(0, expiration_time.total_seconds()))
        
        return effect

    async def get_tool_effect(self, tool: str):
        """Retrieve the tool effect from Redis."""
        tool_key = self._get_tool_key(tool)
        effect_data = self.redis.get(tool_key)

        if effect_data:
            effect = json.loads(effect_data)
            if effect["expires_at"]:
                expiration_time = datetime.fromisoformat(effect["expires_at"])
                if datetime.utcnow() > expiration_time:
                    self.redis.delete(tool_key)
                    return None  # Effect expired, return None
            return effect
        return None  # No effect found in Redis


class ToolActivation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DB_NAME = 'Quest'
        mongo_url = os.getenv('MONGO_URI')
        self.quest_data = Quest_Data(bot)

        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")
        self.mongoConnect = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)

    async def apply_tool_effect(self, message, mentioned_user, tool):
        """Apply the effect of the tool based on its type."""
        if tool == "Motion Alarm":
            await self.handle_motion_alarm(message, mentioned_user)
        elif tool == "Chimera":
            await self.handle_chimera(message, mentioned_user)
        elif tool == "Spy Briefcase":
            await self.handle_spy_briefcase(message, mentioned_user)
        elif tool == "Shadow Cloak":
            await self.handle_shadow_cloak(message, mentioned_user)
        else:
            await message.channel.send(f"Tool {tool} not recognized. Please check the tool name.")
    
    async def handle_motion_alarm(self, message, mentioned_user):
        """Handle the Motion Alarm effect when emojis are detected."""
        emoji_pattern = re.compile(r'<:[a-zA-Z0-9_]+:[0-9]+>|[\U00010000-\U0010ffff]')
        if emoji_pattern.search(message.content):
            affected_user = AffectedUser(str(message.guild.id), str(mentioned_user.id), redis_client)
            effect = await affected_user.apply_tool("Motion Alarm")
            await message.channel.send(f"{mentioned_user.mention} has triggered the Motion Alarm due to emoji usage!")
        else:
            await message.channel.send(f"{mentioned_user.mention} did not trigger the Motion Alarm as no emoji was detected.")

    async def handle_chimera(self, message, mentioned_user):
        """Handle the Chimera tool effect (protection)."""
        affected_user = AffectedUser(str(message.guild.id), str(mentioned_user.id), redis_client)
        effect = await affected_user.apply_tool("Chimera")
        if effect:
            await message.channel.send(f"{mentioned_user.mention} has been affected by Chimera! Effect: {effect}")
        else:
            await message.channel.send(f"{mentioned_user.mention} could not be affected by Chimera.")
    
    async def handle_spy_briefcase(self, message, mentioned_user):
        """Handle the Spy Briefcase effect (siphon points from another member)."""
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        target_user_id = str(mentioned_user.id)
        
        user_balance = await self.get_balance(user_id, guild_id)
        target_balance = await self.get_balance(target_user_id, guild_id)

        siphoned_points = target_balance * 0.30
        
        if siphoned_points > 0:
            new_target_balance = target_balance - siphoned_points
            new_user_balance = user_balance + siphoned_points
            
            await self.update_balance(user_id, guild_id, new_user_balance)
            await self.update_balance(target_user_id, guild_id, new_target_balance)
            
            await message.channel.send(
                f"{message.author.mention} has siphoned {siphoned_points} points from {mentioned_user.mention} using the Spy Briefcase!"
            )
        else:
            await message.channel.send(f"{mentioned_user.mention} has no points to siphon.")
    
    async def handle_shadow_cloak(self, message, mentioned_user):
        """Handle the Shadow Cloak effect, which deletes messages from the user."""
        duration = Config.TOOL_DURATIONS["Shadow Cloak"]
        end_time = datetime.utcnow() + timedelta(minutes=duration)

        while datetime.utcnow() < end_time:
            if message.author == mentioned_user:
                await message.delete()
            await asyncio.sleep(5)

        await message.channel.send(f"{mentioned_user.mention}'s Shadow Cloak effect has ended.")
    
    async def get_balance(self, user_id: str, guild_id: str):
        """Retrieve the stella points balance of a user."""
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']

            user_balance_key = f"members.{user_id}.stella_points"

            user_data = await server_collection.find_one(
                {'guild_id': guild_id},
                {user_balance_key: 1, '_id': 0}
            )

            balance = user_data.get('members', {}).get(user_id, {}).get('stella_points', 0)
            return balance
        except PyMongoError as e:
            logger.error(f"Error occurred while getting balance: {e}")
            return 0

    async def update_balance(self, user_id: str, guild_id: str, new_balance: float):
        """Update the stella points balance of a user."""
        try:
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db['Servers']

            result = await server_collection.update_one(
                {'guild_id': guild_id},
                {'$set': {f'members.{user_id}.stella_points': new_balance}}
            )
            if result.modified_count > 0:
                logger.info(f"Updated balance for user {user_id} in guild {guild_id}. New balance: {new_balance}")
            else:
                logger.error(f"Failed to update balance for user {user_id} in guild {guild_id}.")
        except PyMongoError as e:
            logger.error(f"Error occurred while updating balance: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
     """Listen for messages and apply tool effects when triggered."""
    
     # Ignore messages from bots or bot mentions
     if message.author.bot or any(mention.bot for mention in message.mentions):
        return

     content = message.content.split()

     # Ensure the message contains enough content and includes a mentioned user
     if len(content) >= 2:
        un_tool_id = content[0]
        mentioned_user = message.mentions[0] if message.mentions else None

        if mentioned_user:
            tool = content[1].strip()

            # Fetch or create the tool's unique ID for the mentioned user
            un_tool_id_db = await self.quest_data.get_un_tool_id(
                str(message.guild.id), str(mentioned_user.id), tool
            )

            if un_tool_id == un_tool_id_db:
                await self.apply_tool_effect(message, mentioned_user, tool)
            else:
                await message.channel.send("Tool mismatch detected.")
