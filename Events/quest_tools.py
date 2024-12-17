import discord
from discord.ext import commands
import re
import logging
import os
import random
from datetime import datetime, timedelta
import motor.motor_asyncio
from pymongo.errors import PyMongoError
import redis
from Cogs.quest import Quest_Data
from datetime import datetime, timedelta, timezone

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set to DEBUG for more detailed logs
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Redis Client
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

def timestamp_gen(timestamp: int) -> str:
    """Generate a timestamp string in Discord's time format."""
    dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
    return f'<t:{int(dt.timestamp())}:R>'

class DatabaseManager:

    def __init__(self, db_name):
        # Retrieve the MongoDB URI from environment variables
        mongo_url = os.getenv('MONGO_URI')

        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")

        # Initialize MongoDB connection
        self.mongoConnect = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        self.db = self.mongoConnect[db_name]
        db_name = 'Quest'  # Or set this dynamically based on your setup
        

    def get_collection(self, collection_name):
        """Returns a MongoDB collection."""
        return self.db[collection_name]
    
    async def get_balance(self, user_id: str, guild_id: str):
        """Retrieve the stella points balance of a user."""
        logger.debug(f"Fetching balance for user {user_id} in guild {guild_id}")
        try:
            server_collection = self.db['Servers']
            user_balance_key = f"members.{user_id}.stella_points"
            user_data = await server_collection.find_one(
                {'guild_id': guild_id},
                {user_balance_key: 1, '_id': 0}
            )
            balance = user_data.get('members', {}).get(user_id, {}).get('stella_points', 0)
            logger.info(f"User {user_id} balance fetched: {balance}")
            return balance
        except PyMongoError as e:
            logger.error(f"Error occurred while getting balance for {user_id} in guild {guild_id}: {e}")
            return 0

    async def update_balance(self, user_id: str, guild_id: str, new_balance: float):
        """Update the stella points balance of a user."""
        logger.debug(f"Updating balance for user {user_id} in guild {guild_id} to {new_balance}")
        try:
            server_collection = self.db['Servers']
            result = await server_collection.update_one(
                {'guild_id': guild_id},
                {'$set': {f'members.{user_id}.stella_points': new_balance}}
            )
            if result.modified_count > 0:
                logger.info(f"Updated balance for user {user_id} in guild {guild_id}. New balance: {new_balance}")
            else:
                logger.error(f"Failed to update balance for user {user_id} in guild {guild_id}.")
        except PyMongoError as e:
            logger.error(f"Error occurred while updating balance for {user_id} in guild {guild_id}: {e}")
  
    async def add_stolen_balance(self, user_id: str, guild_id: str, stolen_points: float):
     """Add stolen balance (siphoned points) to the author's balance."""
     logger.debug(f"Adding stolen balance of {stolen_points} to user {user_id} in guild {guild_id}")
     try:
        # Get the current balance of the user (author)
        current_balance = await self.get_balance(user_id, guild_id)

        # Update the balance by adding stolen points
        server_collection = self.db['Servers']
        result = await server_collection.update_one(
            {'guild_id': guild_id},
            {'$inc': {f'members.{user_id}.stella_points': stolen_points}}
        )
        
        if result.modified_count > 0:
            new_balance = current_balance + stolen_points
            logger.info(f"Successfully added stolen points ({stolen_points}) to user {user_id}'s balance. New balance: {new_balance}")
        else:
            logger.error(f"Failed to add stolen points for user {user_id} in guild {guild_id}.")
     except PyMongoError as e:
        logger.error(f"Error occurred while adding stolen points for {user_id} in guild {guild_id}: {e}")
class Config:
    # Configurations for tool durations (can be extended as needed)
    TOOL_DURATIONS = {
        "Motion Alarm": 20,  # Duration in seconds
        "Chimera": 0,  # No duration for Chimera
        "Shadow Cloak": 45,  # Duration for Shadow Cloak in minutes
        "Spy Briefcase": 0,  # No duration, but points are siphoned immediately
    }

class AffectedUser:
    def __init__(self, guild_id: str, user_id: str, redis_client: redis.StrictRedis):
        """Initialize an AffectedUser instance."""
        self.guild_id = guild_id
        self.user_id = user_id
        self.redis_client = redis_client

    async def apply_tool(self, tool_name: str):
        """Apply the effect of the tool."""
        tool_duration = Config.TOOL_DURATIONS.get(tool_name, 0)
        logger.debug(f"Applying {tool_name} for user {self.user_id} in guild {self.guild_id}")

        # Set up the affected user in Redis
        user_key = f"{self.guild_id}:{self.user_id}"
        current_time = datetime.utcnow()
        
        tool_name = tool_name.title()

        if tool_name == "Motion Alarm":
            await self.apply_motion_alarm(user_key, current_time, tool_duration)
        elif tool_name == "Chimera":
            return await self.apply_chimera(user_key)
        elif tool_name == "Shadow Cloak":
            return await self.apply_shadow_cloak(user_key, tool_duration)
        elif tool_name == "Spy Briefcase":
            return await self.apply_spy_briefcase(user_key)
        else:
            logger.warning(f"Unknown tool: {tool_name}")
            return None

    async def apply_motion_alarm(self, user_key: str, current_time: datetime, duration: int):
        """Apply the Motion Alarm effect."""
        if duration > 0:
            expiration_time = current_time + timedelta(seconds=duration)
            self.redis_client.setex(f"{user_key}:motion_alarm", duration, expiration_time.timestamp())
            logger.info(f"Motion Alarm applied to {self.user_id} for {duration} seconds.")
            return f"Motion Alarm triggered until {timestamp_gen(expiration_time.timestamp())}"
        return None

    async def apply_chimera(self, user_key: str):
        """Apply the Chimera effect (no duration)."""
        logger.info(f"Chimera applied to {self.user_id} indefinitely.")
        return "Chimera effect applied."

    async def apply_shadow_cloak(self, user_key: str, duration: int):
        """Apply the Shadow Cloak effect."""
        expiration_time = datetime.utcnow() + timedelta(minutes=duration)
        self.redis_client.setex(f"{user_key}:shadow_cloak", duration * 60, expiration_time.timestamp())
        logger.info(f"Shadow Cloak applied to {self.user_id} for {duration} minutes.")
        return f"Shadow Cloak triggered until {timestamp_gen(expiration_time.timestamp())}"

    async def apply_spy_briefcase(self, user_key: str):
        """Apply the Spy Briefcase effect (no duration)."""
        logger.info(f"Spy Briefcase used by {self.user_id}.")
        return "Spy Briefcase used to siphon points."

    async def remove_tool(self, tool_name: str):
        """Remove a tool from the affected user."""
        user_key = f"{self.guild_id}:{self.user_id}"

        if tool_name == "Motion Alarm":
            self.redis_client.delete(f"{user_key}:motion_alarm")
            logger.info(f"Motion Alarm removed for {self.user_id}")
        elif tool_name == "Chimera":
            logger.info(f"Chimera removed for {self.user_id}")
        elif tool_name == "Key Chain Sheep":
            self.redis_client.delete(f"{user_key}:shadow_cloak")
            logger.info(f"Key Chain Sheep removed for {self.user_id}")
        elif tool_name == "Spy Briefcase":
            logger.info(f"Spy Briefcase removed for {self.user_id}")
        else:
            logger.warning(f"Unknown tool: {tool_name}")

class Server:
    def __init__(self, guild_id: str, redis_client: redis.StrictRedis):
        self.guild_id = guild_id
        self.redis_client = redis_client
        self.affected_users = {}

    def get_affected_user(self, user_id: str):
        """Retrieve or create an affected user."""
        if user_id not in self.affected_users:
            self.affected_users[user_id] = AffectedUser(self.guild_id, user_id, self.redis_client)
        return self.affected_users[user_id]

class ToolHandler:
    def __init__(self, bot, db_manager, redis_client):
        self.db_manager = db_manager
        self.redis_client = redis_client
        self.quest_data = Quest_Data(bot)


    async def handle_motion_alarm(self, user_id, channel):
        """Handle the Motion Alarm effect when emojis are detected."""
        logger.debug(f"Handling Motion Alarm for {user_id} in channel {channel.id}")
        emoji_pattern = re.compile(r'<:[a-zA-Z0-9_]+:[0-9]+>|[\U00010000-\U0010ffff]')
        
        # Check the recent messages in the channel for emoji usage
        async for message in channel.history(limit=10):  # Fetching last 10 messages in the channel
            if emoji_pattern.search(message.content):
                affected_user = AffectedUser(str(channel.guild.id), str(user_id), self.redis_client)
                effect = await affected_user.apply_tool("Motion Alarm")
                logger.info(f"Motion Alarm triggered for {user_id}")
                await channel.send(f"<@{user_id}> has triggered the Motion Alarm due to emoji usage!")
                return
        
        logger.info(f"No emoji detected for Motion Alarm for {user_id}")
        await channel.send(f"<@{user_id}> did not trigger the Motion Alarm as no emoji was detected.")

    async def handle_chimera(self, user_id, channel):
        """Handle the Chimera tool effect (protection)."""
        logger.debug(f"Handling Chimera effect for {user_id} in channel {channel.id}")
        affected_user = AffectedUser(str(channel.guild.id), str(user_id), self.redis_client)
        effect = await affected_user.apply_tool("Chimera")
        if effect:
            logger.info(f"Chimera tool applied successfully for {user_id} with effect: {effect}")
            await channel.send(f"<@{user_id}> has been affected by Chimera! Effect: {effect}")
        else:
            logger.warning(f"Chimera tool failed for {user_id}")
            await channel.send(f"<@{user_id}> could not be affected by Chimera.")

    async def handle_spy_briefcase(self, author_id, user_id, channel):
     """Handle the Spy Briefcase effect (siphon points from another member)."""
     logger.debug(f"Handling Spy Briefcase for {author_id} in channel {channel.id}")
     guild_id = str(channel.guild.id)

     # Check if user has the tool in their inventory
     tool_inventory = await self.check_inventory(author_id, guild_id, "Spy Briefcase")
     if not tool_inventory:
        logger.warning(f"You do not have the Spy Briefcase in inventory.")
        await channel.send(f"<@{author_id}>, you do not have the Spy Briefcase tool in your inventory.")
        return

     # Assuming the mentioned user is the target for siphoning points
     mentioned_user_id = str(channel.last_message.mentions[0].id)  # Taking the last mentioned user

     # Get balances
     author_balance = await self.db_manager.get_balance(author_id, guild_id)  # Balance of the author
     target_balance = await self.db_manager.get_balance(mentioned_user_id, guild_id)  # Balance of the mentioned user
     siphoned_points = target_balance * 0.25  # Points to siphon (25%)
     siphoned_points = round(siphoned_points)

     if siphoned_points > 0:
        new_target_balance = target_balance - siphoned_points
        new_author_balance = author_balance + siphoned_points  # Add siphoned points to the author's balance
        
        # Update target balance
        await self.db_manager.update_balance(mentioned_user_id, guild_id, new_target_balance)

        # Add siphoned points to author's balance
        await self.db_manager.add_stolen_balance(author_id, guild_id, siphoned_points)
        
        logger.info(f"Siphoned {siphoned_points} points from {mentioned_user_id} to {author_id}.")
        await channel.send(
            f"<@{author_id}> has siphoned {siphoned_points} points from <@{mentioned_user_id}> using the Spy Briefcase!"
        )
     else:
        logger.info(f"{mentioned_user_id} has no points to siphon.")
        await channel.send(f"<@{mentioned_user_id}> has no points to siphon.")

    async def handle_key_chain_sheep(self, author_id, user_id, channel):
        """Handle the Key Chain Sheep tool effect (assigning a random role)."""
        logger.debug(f"Handling Key Chain Sheep for {user_id} in channel {channel.id}")

        # Fetch the list of roles for the guild
        roles = await self.quest_data.get_roles_for_guild(str(channel.guild.id))

        if not roles:
            logger.warning(f"No roles found for the guild {channel.guild.id}.")
            await channel.send("No roles found for this server. Please ensure roles are properly set.")
            return

        # Select a random role from the available roles
        random_role_id = random.choice(roles)
        random_role = channel.guild.get_role(int(random_role_id))

        if random_role:
            target = channel.guild.get_member(int(user_id))
            if target:
                # Add the random role to the target user
                await target.add_roles(random_role)
                await channel.send(f"{target.mention} has been assigned the role {random_role.name}.")
                logger.info(f"<:keychain_sheep:1318415294758129692> Assigned the role **{random_role.name}** to {target.name}.")
            else:
                logger.warning(f"Target user {user_id} not found in the guild.")
                await channel.send(f"Could not find the user <@{user_id}> in the guild.")
        else:
            logger.warning(f"The role {random_role_id} could not be found in the guild.")
            await channel.send("The selected role could not be found. Please ensure the roles are set correctly.")

    async def check_inventory(self, user_id: str, guild_id: str, tool: str):
     """Check if a user has a specific tool in their inventory and fetch its details."""
     logger.debug(f"Checking inventory for user {user_id} in guild {guild_id} for tool {tool}")

     try:
        # Fetch the user's inventory from the database
        db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
        server_collection = db['Servers']

        # Query to find the user and their inventory
        user_data = await server_collection.find_one(
            {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
            {f'members.{user_id}.inventory': 1}  # Fetch the inventory only
        )
        logger.debug(f"user_data is: {user_data}")

        if not user_data:
            logger.warning(f"No data found for user {user_id} in guild {guild_id}.")
            return False

        # Extract the inventory from the nested structure
        inventory = user_data.get('members', {}).get(str(user_id), {}).get('inventory', {})
        logger.debug(f"Inventory: {inventory}")

        # Check for the tool in the nested 'tool' section of the inventory
        tools = inventory.get('tool', {})  # Access the nested 'tool' dictionary
        tool_lower = tool.lower()
        matching_tool = next((key for key in tools if key.lower() == tool_lower), None)

        if matching_tool:
            logger.debug(f"Tool {tool} found in inventory for user {user_id}.")

            # Fetch unique tool ID and quantity
            tool_data = tools[matching_tool]
            un_tool_id = tool_data.get('un_tool_id')
            quantity = tool_data.get('quantity', 0)

            logger.info(f"User has {quantity} of {tool} (Tool ID: {un_tool_id})")

            # Validate quantity
            if quantity > 0:
                logger.info(f"User has the required {tool} with sufficient quantity.")

                # Remove 1 from the inventory
                success = await self.remove_one_from_inventory(user_id, guild_id, tool)
                if success:
                    logger.info(f"Successfully removed 1 {tool} from user {user_id}'s inventory.")
                    return True
                else:
                    logger.warning(f"Failed to remove 1 {tool} from user {user_id}'s inventory.")
                    return False
            else:
                logger.warning(f"Tool {tool} found but insufficient quantity ({quantity}).")
                return False
        else:
            logger.warning(f"Tool {tool} not found in inventory for user {user_id}.")
            return False
     except Exception as e:
        logger.error(f"Error checking inventory for user {user_id} in guild {guild_id}: {e}")
        return False
    
    async def remove_one_from_inventory(self, user_id: str, guild_id: str, tool: str):
     """Remove 1 quantity of a specific tool from the user's inventory."""
     logger.debug(f"Removing 1 quantity of {tool} from user {user_id} in guild {guild_id}.")

     try:
        # Connect to the database
        db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
        server_collection = db['Servers']

        # Fetch the user's inventory
        user_data = await server_collection.find_one(
            {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
            {f'members.{user_id}.inventory': 1}
        )
        logger.debug(f"user_data is: {user_data}")

        if not user_data:
            logger.warning(f"No data found for user {user_id} in guild {guild_id}.")
            return False

        # Extract the inventory and the tool
        inventory = user_data.get('members', {}).get(str(user_id), {}).get('inventory', {})
        tools = inventory.get('tool', {})
        tool_lower = tool.lower()
        matching_tool = next((key for key in tools if key.lower() == tool_lower), None)

        if not matching_tool:
            logger.warning(f"Tool {tool} not found in inventory for user {user_id}.")
            return False

        # Get current quantity and validate
        current_quantity = tools[matching_tool].get('quantity', 0)
        if current_quantity <= 0:
            logger.warning(f"Insufficient quantity of {tool} for user {user_id}. Current quantity: {current_quantity}.")
            return False

        # Decrement quantity by 1
        new_quantity = current_quantity - 1
        update_query = {
            f'members.{user_id}.inventory.tool.{matching_tool}.quantity': new_quantity
        }
        await server_collection.update_one(
            {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
            {'$set': update_query}
        )
        logger.info(f"Decremented {tool} quantity by 1 for user {user_id}. New quantity: {new_quantity}.")
        return True

     except Exception as e:
        logger.error(f"Error removing 1 quantity of {tool} for user {user_id} in guild {guild_id}: {e}")
        return False
     
    async def apply_tool_effect(self, author_id, user_id, tool, channel):
        """Apply the effect of the tool based on its name."""
        # Log the action for debugging
        logger.debug(f"Applying tool effect: {tool} for user {user_id} in channel {channel.id}")
        tool = tool.title()
        # Handle the tool effect based on its name
        if tool == "Motion Alarm":
            await self.handle_motion_alarm(author_id, user_id, channel)
        elif tool == "Chimera":
            await self.handle_chimera(author_id,user_id, channel)
        elif tool == "Spy Briefcase":
            await self.handle_spy_briefcase(author_id,user_id, channel)
        elif tool == "Key Chain Sheep":
            await self.handle_key_chain_sheep(author_id,user_id, channel)
        else:
            # Warn if the tool is unrecognized
            logger.warning(f"Unrecognized tool: {tool}")
            await channel.send(f"Tool {tool} not recognized. Please check the tool name.")


class ToolBot(commands.Cog):
    """Main bot logic that listens for messages and applies tool effects."""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Retrieve MongoDB URI from environment variables
        mongo_url = os.getenv('MONGO_URI')
        db_name = 'Quest'  # Or set this dynamically based on your setup
        
        # Initialize the database manager
        self.db_manager = DatabaseManager(db_name)

        # Initialize the quest data handler
        self.quest_data = Quest_Data(bot)
        
        # Initialize the tool handler with the database manager and quest data
        self.tool_handler = ToolHandler(bot, self.db_manager, self.quest_data)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
     """Listen to messages and trigger actions based on tool ID and mentioned user."""

     # Skip if the message is sent by the bot itself or in the ignored channel
     if message.author == self.bot.user or message.channel.id == 1278580578593148978:
        return

     # Ensure the message contains enough content (at least a tool ID and a mentioned user)
     if len(message.content.split()) < 2:
        return

     content = message.content.split()
     tool_id = content[0]  # First argument is the tool ID
    
     # Regular expression for a 6-digit tool ID
     tool_id_pattern = r'^\d{6}$'  # Match exactly 6 digits
     if not re.match(tool_id_pattern, tool_id):
        return

     try:
        # Keep tool_id as a string (to preserve leading zeros)
        tool_id_str = tool_id

        mentioned_user = message.mentions[0] if message.mentions else None  # Get the mentioned user

        # Log detected tool ID and mentioned user ID
        if mentioned_user:
            print(f"Tool_ID: {tool_id_str} detected in message {message.id}")
            print(f"Target_ID: {mentioned_user.id} mentioned in message")

            # Fetch the message author's inventory (not the mentioned user's inventory)
            guild_id = str(message.guild.id)
            user_id = str(message.author.id)  # Fetching the inventory of the message author
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db['Servers']

            user_data = await server_collection.find_one(
                {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
                {f'members.{user_id}.inventory.tool'}
            )

            inventory = user_data.get('members', {}).get(user_id, {}).get('inventory', {}).get('tool', {})

            # Log the inventory to show what tools are available
            if inventory:
                print(f"Inventory for User {message.author.display_name} (ID: {message.author.id}):")
                for tool, tool_data in inventory.items():
                    tool_name = tool.capitalize()  # Assuming tool name is the tool key (e.g., "hammer")
                    tool_id_in_inventory = await self.quest_data.get_existing_tool_id(guild_id, user_id, tool)
                    
                    # Print the tool found in the inventory
                    print(f" - Tool: {tool_name} (Tool_ID: {tool_id_in_inventory})")
                    
                    # Check if the tool matches the requested tool ID (compare as strings to keep leading zeros)
                    if str(tool_id_in_inventory) == tool_id_str:
                        print(f"Match found: Tool ID {tool_id_str} matches {tool_name}")
                        # Apply the tool effect to the mentioned user
                        await self.tool_handler.apply_tool_effect(message.author.id, mentioned_user.id, tool_name, message.channel)
                        
                        # Stop further processing after the tool is applied
                        break
                else:
                    print(f"No match found for Tool_ID: {tool_id_str} in the inventory.")
            else:
                print(f"User {message.author.display_name} (ID: {message.author.id}) has an empty inventory.")

        else:
            print("No user mentioned in the message.")

     except Exception as e:
        print(f"Error processing tool in message {message.id}: {e}")



async def setup(bot):
    # Initialize quest_data instance (Quest_Data needs to be imported from your cogs)
    quest_data = Quest_Data(bot)
    mongo_url = os.getenv('MONGO_URI')  # Retrieve MongoDB URI from environment variables
    db_name = 'Quest'  # Or set this dynamically based on the requirements

    # Initialize ToolBot with the required arguments
    await bot.add_cog(ToolBot(bot, mongo_url, db_name, quest_data))