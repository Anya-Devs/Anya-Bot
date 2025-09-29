
 

import json
import numpy as np
import motor.motor_asyncio
from pymongo.errors import PyMongoError
from imports.discord_imports import *
from imports.log_imports import *
import random
import re
import asyncio
import string
from concurrent.futures import ThreadPoolExecutor
import typing



class DatabaseManager:    
    def __init__(self, mongo_connect, db_name, bot=None, config=None):
        self.mongoConnect = mongo_connect
        self.DB_NAME = db_name
        self.bot = bot
        self.config = config or self.QuestConfig()
        
        # Initialize nested class instances
        self.roles = self.RoleClass(mongo_connect, db_name)
        self.inventory = self.InventoryClass(mongo_connect, db_name)
        self.tools = self.ToolClass(mongo_connect, db_name, self.config)
        self.server = self.ServerClass(mongo_connect, db_name)
        self.channels = self.ChannelClass(mongo_connect, db_name, bot, self.config)
        self.balance = self.BalanceClass(mongo_connect, db_name)
        self.quests = self.QuestClass(mongo_connect, db_name, self.config, bot, self)

    class QuestConfig:
        """Configuration class for quest-related settings."""
        def __init__(self):
            self.db_name = "Quest"
            self.quest_content_file = "data/commands/quest/quest_content.txt"
            self.min_reward_per_time = 4
            self.max_reward_per_time = 20
            self.min_reward_per_time_message = 5
            self.max_reward_per_time_message = 22
            # Method-specific times ranges
            self.min_times_message = 1
            self.max_times_message = 3
            self.min_times_emoji = 3
            self.max_times_emoji = 5
            self.min_times_reaction = 3
            self.max_times_reaction = 5
            self.default_quest_limit = 25
            self.add_quest_chance = 50
            self.most_active_threshold = 5
            self.most_active_message_limit = 100
            self.short_uuid_digits = 6
            self.min_custom_emojis = 5
            self.booster = {'message': 3, 'reaction': 1.2}

    class RoleClass:
        """Handles role-related database operations."""
        def __init__(self, mongo_connect, db_name):
            self.mongoConnect = mongo_connect
            self.DB_NAME = db_name

        async def store_roles_for_guild(self, guild_id, role_ids):
            """Store or override the roles for the guild."""
            collection = self.mongoConnect[self.DB_NAME].roles
            guild_data = await collection.find_one({"guild_id": guild_id})

            if guild_data:
                await collection.update_one(
                    {"guild_id": guild_id}, {"$set": {"roles": role_ids}}
                )
            else:
                await collection.insert_one({"guild_id": guild_id, "roles": role_ids})

        async def get_roles_for_guild(self, guild_id):
            """Retrieve the stored roles for the guild."""
            collection = self.mongoConnect[self.DB_NAME].roles
            guild_data = await collection.find_one({"guild_id": guild_id})
            if guild_data:
                return guild_data["roles"]
            return []

    class InventoryClass:
        """Handles inventory-related database operations."""
        def __init__(self, mongo_connect, db_name):
            self.mongoConnect = mongo_connect
            self.DB_NAME = db_name

        async def get_user_inventory_count(
            self, guild_id: str, user_id: str, material_name: str
        ) -> int:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                user_data = await server_collection.find_one(
                    {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                    {f"members.{user_id}.inventory.{material_name}": 1},
                )

                if user_data:
                    if (
                        "inventory" in user_data["members"][user_id]
                        and material_name in user_data["members"][user_id]["inventory"]
                    ):
                        return user_data["members"][user_id]["inventory"].get(
                            material_name, 0
                        )
                    else:
                        await server_collection.update_one(
                            {"guild_id": guild_id},
                            {"$set": {f"members.{user_id}.inventory.{material_name}": 0}},
                            upsert=True,
                        )
                        return 0
                else:
                    return 0
            except PyMongoError as e:
                logger.error(
                    f"Error occurred while getting user inventory count: {e}")
                return 0

        async def add_item_to_inventory(
            self, guild_id: str, user_id: str, material_name: str, quantity: int
        ) -> None:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                await server_collection.update_one(
                    {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                    {"$inc": {f"members.{user_id}.inventory.{material_name}": quantity}},
                    upsert=True,
                )
            except PyMongoError as e:
                logger.error(f"Error occurred while adding item to inventory: {e}")
                raise e

    class ToolClass:
        """Handles tool-related database operations."""
        def __init__(self, mongo_connect, db_name, config):
            self.mongoConnect = mongo_connect
            self.DB_NAME = db_name
            self.config = config

        async def get_existing_tool_id(
            self, guild_id: str, user_id: str, tool_name: str
        ) -> str:
            """Fetches the existing un_tool_id for the tool from the inventory."""
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                user_data = await server_collection.find_one(
                    {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                    {f"members.{user_id}.inventory.tool.{tool_name}": 1},
                )

                tool_data = (
                    user_data.get("members", {})
                    .get(user_id, {})
                    .get("inventory", {})
                    .get("tool", {})
                    .get(tool_name, {})
                )
                return tool_data.get("un_tool_id", None)
            except PyMongoError as e:
                logger.error(f"Error occurred while getting existing tool ID: {e}")
                return None

        async def get_quantity(
            self, guild_id: str, user_id: str, material_name: str
        ) -> int:
            """
            Retrieves the quantity of a specific material in a user's inventory.
            If the material does not exist, returns 0.
            """
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                user_data = await server_collection.find_one(
                    {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                    {f"members.{user_id}.inventory.tool.{material_name}.quantity": 1},
                )

                quantity = (
                    user_data.get("members", {})
                    .get(user_id, {})
                    .get("inventory", {})
                    .get("tool", {})
                    .get(material_name, {})
                    .get("quantity", 0)
                )
                return quantity
            except PyMongoError as e:
                logger.error(
                    f"Error occurred while retrieving quantity for {material_name}: {e}"
                )
                raise e

        async def add_tool_to_inventory(
            self, guild_id: str, user_id: str, material_name: str, quantity: int
        ) -> None:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                await server_collection.update_one(
                    {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                    {
                        "$inc": {
                            f"members.{user_id}.inventory.tool.{material_name}.quantity": quantity
                        }
                    },
                    upsert=True,
                )
                await self.get_quantity(guild_id, user_id, material_name)

            except PyMongoError as e:
                logger.error(f"Error occurred while adding item to inventory: {e}")
                raise e

        async def remove_tool_from_inventory(
            self, guild_id: str, user_id: str, tool_name: str
        ) -> None:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                current_quantity = await self.get_quantity(guild_id, user_id, tool_name)

                if current_quantity > 0:
                    await server_collection.update_one(
                        {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                        {
                            "$inc": {
                                f"members.{user_id}.inventory.tool.{tool_name}.quantity": -1
                            }
                        },
                        upsert=True,
                    )
                else:
                    logger.warning(
                        f"{user_id} does not have the tool `{tool_name}` in their inventory."
                    )
                    await server_collection.update_one(
                        {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                        {
                            "$set": {
                                f"members.{user_id}.inventory.tool.{tool_name}.quantity": 0
                            }
                        },
                        upsert=True,
                    )

            except PyMongoError as e:
                logger.error(
                    f"Error occurred while removing tool from inventory: {e}")
                raise e

        async def create_un_tool_id(self, guild_id, user_id, tool):
            """Create a new unique tool ID for the user and tool."""

            def generate_short_uuid():
                return str(int("".join(random.choices(string.digits, k=6))) + 1000)

            db = self.mongoConnect[self.DB_NAME]
            server_collection = db["Servers"]

            try:
                un_tool_id = generate_short_uuid()
                tool_data = {"un_tool_id": un_tool_id}

                result = await server_collection.update_one(
                    {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                    {"$set": {f"members.{user_id}.inventory.tool.{tool}": tool_data}},
                    upsert=True,  
                )

                logger.debug(
                    f"Generated new un_tool_id: {un_tool_id} for tool '{tool}'")
                logger.debug(f"Database update result: {result.raw_result}")

                return un_tool_id
            except Exception as e:
                logger.error(
                    f"Error in create_un_tool_id for tool '{tool}' (guild: {guild_id}, user: {user_id}): {e}"
                )
                raise  

        async def get_un_tool_id(self, guild_id, user_id, tool):
            """Fetch the unique tool ID for the user and tool."""
            db = self.mongoConnect[self.DB_NAME]
            server_collection = db["Servers"]

            user_tool_data = await server_collection.find_one(
                {
                    "guild_id": guild_id,
                    f"members.{user_id}.inventory.tool.{tool}": {"$exists": True},
                },
                {f"members.{user_id}.inventory.tool.{tool}": 1},
            )

            if user_tool_data:
                try:
                    tool_data = user_tool_data["members"][user_id]["inventory"]["tool"].get(
                        tool
                    )

                    if isinstance(tool_data, dict) and "un_tool_id" in tool_data:
                        return tool_data["un_tool_id"]

                    logger.error(
                        f"Tool {tool} does not have an 'un_tool_id' or is in an unexpected format."
                    )
                    return None

                except KeyError as e:
                    logger.error(
                        f"KeyError: Missing key in user_tool_data for {guild_id} and {user_id}: {e}"
                    )
                    return None
            else:
                logger.error(f"Tool {tool} does not exist in the inventory.")
                return None

    class ServerClass:
        """Handles server-related database operations."""
        def __init__(self, mongo_connect, db_name):
            self.mongoConnect = mongo_connect
            self.DB_NAME = db_name

        async def find_user_in_server(self, user_id: str, guild_id: str) -> bool:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                server_data = await server_collection.find_one({"guild_id": guild_id})

                if server_data:
                    members_data = server_data.get("members", {})
                    return user_id in members_data
                else:
                    return False
            except PyMongoError as e:
                logger.error(f"Error occurred while finding user in server: {e}")
                return False

        async def find_users_in_server(self, guild_id: str):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                logger.debug(f"Querying for guild_id: {guild_id}")

                guild_document = await server_collection.find_one(
                    {"guild_id": str(guild_id)}
                )

                if guild_document:
                    members_data = guild_document.get("members", {})
                    users_in_server = list(members_data.keys())  
                    return users_in_server
                else:
                    logger.debug(f"No guild found with ID {guild_id}.")
                    return []
            except PyMongoError as e:
                logger.error(f"Error occurred while finding users in server: {e}")
                return []

        async def add_user_to_server(self, user_id: str, guild_id: str):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                server_data = await server_collection.find_one({"guild_id": guild_id})
                if not server_data:
                    server_data = {"guild_id": guild_id, "members": {}}

                members_data = server_data.get("members", {})
                members_data[user_id] = {"quests": []}

                await server_collection.update_one(
                    {"guild_id": guild_id}, {"$set": {"members": members_data}}, upsert=True
                )
            except PyMongoError as e:
                logger.error(f"Error occurred while adding user to server: {e}")

    class ChannelClass:
        """Handles channel-related database operations."""
        def __init__(self, mongo_connect, db_name, bot, config):
            self.mongoConnect = mongo_connect
            self.DB_NAME = db_name
            self.bot = bot
            self.config = config

        async def get_random_channel_for_guild(self, guild_id: str, fallback_channel=None):
            """
            Retrieve a random channel ID for the specified guild from the database.
            If no channels are found, return the fallback channel ID if provided.
            """
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                guild_data = await server_collection.find_one(
                    {"guild_id": guild_id}, {"channels": 1}
                )

                if guild_data and "channels" in guild_data and guild_data["channels"]:
                    channel_ids = guild_data["channels"]
                    random_channel_id = random.choice(channel_ids)
                    logger.debug(
                        f"Random channel ID selected: {random_channel_id} for guild {guild_id}"
                    )
                    return random_channel_id
                else:
                    logger.debug(
                        f"No channels found for guild {guild_id}. Using fallback channel."
                    )
                    return fallback_channel.id if fallback_channel else None

            except PyMongoError as e:
                logger.error(
                    f"Error occurred while retrieving random channel: {e}")
                return fallback_channel.id if fallback_channel else None

        async def store_channels_for_guild(self, guild_id: str, channel_ids: list):
            """
            Store the provided list of channel IDs for the guild in the database,
            replacing any existing channel IDs.
            """
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                await server_collection.update_one(
                    {"guild_id": guild_id},
                    {
                        "$set": {"channels": channel_ids}
                    },  
                    upsert=True,
                )

                logger.debug(
                    f"Stored (overwritten) channels {channel_ids} for guild {guild_id}."
                )
                return True
            except PyMongoError as e:
                logger.error(f"Error occurred while storing channels: {e}")
                return False

        async def get_most_active_channel(
            self, guild_id, threshold=5, message_limit=100, fallback_channel_id=None
        ):
            try:
                logger.debug("Entering get_most_active_channel function")
                guild = self.bot.get_guild(int(guild_id))

                if guild:
                    logger.debug(f"Guild found: {guild.name} (ID: {guild_id})")
                    channel_activity = {}

                    with ThreadPoolExecutor() as executor:
                        loop = asyncio.get_event_loop()

                        async def count_messages(channel):
                            try:
                                message_count = 0
                                member_set = set()
                                async for message in channel.history(limit=message_limit):
                                    message_count += 1
                                    if not message.author.bot:
                                        member_set.add(message.author.id)
                                return channel.id, message_count, len(member_set)
                            except Exception as e:
                                logger.error(
                                    f"Error while processing channel {channel.name}: {e}"
                                )
                                return None

                        tasks = [
                            loop.run_in_executor(executor, count_messages, channel)
                            for channel in guild.text_channels
                            if channel.permissions_for(guild.default_role).send_messages
                        ]

                        results = await asyncio.gather(*tasks)

                        for result in results:
                            if result:
                                channel_id, message_count, member_count = result
                                channel_activity[channel_id] = (
                                    message_count, member_count)
                                logger.debug(
                                    f"Processed channel {channel_id}: {message_count} messages, {member_count} members"
                                )

                    sorted_channels = sorted(
                        channel_activity.items(),
                        key=lambda x: (x[1][1], x[1][0]),
                        reverse=True,
                    )
                    if sorted_channels:
                        logger.debug(
                            f"Sorted channels by activity: {sorted_channels}")
                        if len(sorted_channels) > threshold:
                            most_active_channel_id = random.choice(
                                [channel[0]
                                    for channel in sorted_channels[:threshold]]
                            )
                        else:
                            most_active_channel_id = sorted_channels[0][0]
                        logger.debug(
                            f"Selected most active channel: {most_active_channel_id}"
                        )
                    else:
                        most_active_channel_id = fallback_channel_id or random.choice(
                            [channel.id for channel in guild.text_channels]
                        )
                        logger.debug(
                            f"No active channels found, using fallback: {most_active_channel_id}"
                        )

                    return most_active_channel_id
                else:
                    logger.debug(f"Guild not found: {guild_id}")
                    return fallback_channel_id or None
            except Exception as e:
                logger.error(
                    f"Error occurred while getting the most active channel: {e}")
                traceback.print_exc()
                return fallback_channel_id or None

    class BalanceClass:
        """Handles balance-related database operations."""
        def __init__(self, mongo_connect, db_name):
            self.mongoConnect = mongo_connect
            self.DB_NAME = db_name

        async def get_balance(self, user_id: str, guild_id: str):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                user_balance_key = f"members.{user_id}.stella_points"

                user_data = await server_collection.find_one(
                    {"guild_id": guild_id}, {user_balance_key: 1, "_id": 0}
                )

                balance = (
                    user_data.get("members", {}).get(
                        user_id, {}).get("stella_points", 0)
                )
                return balance
            except PyMongoError as e:
                logger.error(f"Error occurred while getting balance: {e}")
                return 0

        async def add_balance(self, user_id: str, guild_id: str, amount: int):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                user_balance_key = f"members.{user_id}.stella_points"

                await server_collection.update_one(
                    {"guild_id": guild_id},
                    {
                        "$inc": {user_balance_key: amount},
                        "$setOnInsert": {
                            "members.{user_id}.stella_points": 0,
                        },
                    },
                    upsert=True,
                )
            except PyMongoError as e:
                logger.error(f"Error occurred while adding balance: {e}")

        async def initialize_balance(self, user_id: str, guild_id: str):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                user_balance_key = f"members.{user_id}.stella_points"

                await server_collection.update_one(
                    {"guild_id": guild_id},
                    {
                        "$setOnInsert": {
                            user_balance_key: 0,
                        }
                    },
                    upsert=True,
                )
            except PyMongoError as e:
                logger.error(f"Error occurred while initializing balance: {e}")

    class QuestClass:
        """Handles quest-related database operations."""
        def __init__(self, mongo_connect, db_name, config, bot, main_manager):
            self.mongoConnect = mongo_connect
            self.DB_NAME = db_name
            self.config = config
            self.bot = bot
            self.main_manager = main_manager  # Reference to main DatabaseManager instance
            self.quest_content_file = config.quest_content_file

        async def remove_all_server_quests(self, guild_id: str) -> None:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                await server_collection.update_many(
                    {"guild_id": guild_id, "members.quests": {"$exists": False}},
                    {"$set": {"members.$.quests": []}},
                )

                await server_collection.update_many(
                    {"guild_id": guild_id}, {"$set": {"members.$[].quests": []}}
                )

                logger.debug(f"All server quests removed for guild {guild_id}.")
            except PyMongoError as e:
                logger.error(
                    f"Error occurred while removing all server quests: {e}")
                raise e

        async def get_server_quest_count(self, guild_id: str) -> int:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                guild_data = await server_collection.find_one({"guild_id": guild_id})
                if guild_data:
                    members_data = guild_data.get("members", {})
                    total_quests = sum(
                        len(member.get("quests", [])) for member in members_data.values()
                    )
                    return total_quests
                else:
                    return 0
            except PyMongoError as e:
                logger.error(
                    f"Error occurred while getting server quest count: {e}")
                return 0

        async def get_beginner_quests(
            self, guild_id: str
        ) -> List[Dict[str, Union[str, int]]]:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                guild_data = await server_collection.find_one({"guild_id": guild_id})
                if guild_data:
                    beginner_quests = []
                    members_data = guild_data.get("members", {})
                    for member_id, member_data in members_data.items():
                        quests = member_data.get("quests", [])
                        for quest in quests:
                            if quest.get("progress", 0) == 0:
                                beginner_quests.append(
                                    {
                                        "action": quest.get("action", ""),
                                        "method": quest.get("method", ""),
                                        "content": quest.get("content", ""),
                                        "times": quest.get("times", 0),
                                    }
                                )
                    return beginner_quests
                else:
                    return []
            except PyMongoError as e:
                logger.error(f"Error occurred while getting beginner quests: {e}")
                return []

        async def set_quest_limit(self, guild_id: str, limit: int) -> None:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                await server_collection.update_one(
                    {"guild_id": guild_id}, {"$set": {"quest_limit": limit}}, upsert=True
                )
            except PyMongoError as e:
                logger.error(f"Error occurred while setting quest limit: {e}")
                raise e

        async def get_quest_limit(self, guild_id: str) -> int:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                guild_doc = await server_collection.find_one({"guild_id": guild_id})
                if guild_doc:
                    return guild_doc.get(
                        "quest_limit", 25
                    )  
                else:
                    return 25  
            except PyMongoError as e:
                logger.error(f"Error occurred while getting quest limit: {e}")
                raise e

        async def find_users_with_quest(self, guild_id: str, quest_id: int):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                logger.debug(
                    f"Querying for guild_id: {guild_id} with quest_id: {quest_id}")

                guild_document = await server_collection.find_one(
                    {"guild_id": str(guild_id)}
                )

                if guild_document:
                    members_data = guild_document.get("members", {})
                    users_with_quest = []

                    for user_id, user_data in members_data.items():
                        quests = user_data.get("quests", [])
                        if any(quest["quest_id"] == quest_id for quest in quests):
                            users_with_quest.append(user_id)

                    return users_with_quest
                else:
                    logger.debug(f"No guild found with ID {guild_id}.")
                    return []
            except PyMongoError as e:
                logger.error(f"Error occurred while finding users with quest: {e}")
                return []

        async def find_quests_by_user_and_server(
            self, user_id: str, guild_id: str, interaction=None
        ):
            try:
                await self.validate_input(user_id=user_id, guild_id=guild_id)
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                server_data = await server_collection.find_one({"guild_id": guild_id})
                if server_data:
                    member_data = server_data.get("members", {}).get(user_id, {})
                    quests = member_data.get("quests", [])
                    
                    if len(quests) == 0:
                        return None
                    return quests

                else:
                    return []
            except PyMongoError as e:
                logger.error(f"Error occurred while finding quests: {e}")
                if interaction:
                    await self.handle_error(interaction, e, title="Quest Finding")
                return None

        async def insert_quest(
            self, guild_id: str, user_id: str, quest_data: dict, interaction=None
        ):
            try:
                quest_data["progress"] = 0
                await self.validate_input(**quest_data)
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                await server_collection.update_one(
                    {
                        "guild_id": guild_id,
                        f"members.{user_id}.quests": {
                            "$not": {"$elemMatch": {"quest_id": quest_data["quest_id"]}}
                        },
                    },
                    {"$push": {f"members.{user_id}.quests": quest_data}},
                    upsert=True,
                )
                logger.debug(
                    f"Inserted quest data for user {user_id} in guild {guild_id}.")
            except (ValueError, PyMongoError) as e:
                logger.error(f"Error occurred while inserting quest: {e}")
                if interaction:
                    await self.handle_error(interaction, e, title="Quest Insertion")

        async def get_latest_quest_id(
            self, guild_id: str, user_id: str, interaction=None
        ) -> int:
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]
                server_data = await server_collection.find_one({"guild_id": guild_id})
                if server_data:
                    member_data = server_data.get("members", {}).get(user_id, {})
                    quests = member_data.get("quests", [])
                    latest_quest = max(
                        [quest.get("quest_id", 0) for quest in quests], default=0
                    )
                    logger.debug(
                        f"Latest quest ID for user {user_id} in guild {guild_id}: {latest_quest}."
                    )
                    return latest_quest
                else:
                    return 0
            except PyMongoError as e:
                logger.error(f"Error occurred while getting latest quest ID: {e}")
                if interaction:
                    await self.handle_error(interaction, e, title="Latest Quest ID")
                return 0

        async def store_server_quest(self, guild_id: str, quest_data: dict):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                server_doc = await server_collection.find_one({"_id": guild_id})
                if not server_doc:
                    server_doc = {"_id": guild_id, "server_quest": []}

                quest_id = len(server_doc["server_quest"]) + 1
                quest_data["quest_id"] = quest_id

                server_doc["server_quest"].append(quest_data)

                await server_collection.update_one(
                    {"_id": guild_id}, {"$set": server_doc}, upsert=True
                )

                logger.debug(
                    f"Stored quest data for guild {guild_id}: {quest_data}")

            except PyMongoError as e:
                logger.error(f"Error occurred while storing quest data: {e}")
                raise e

        async def server_quests(self, guild_id: str):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                server_doc = await server_collection.find_one({"_id": guild_id})
                if not server_doc or "server_quest" not in server_doc:
                    return None

                return server_doc["server_quest"]

            except PyMongoError as e:
                logger.error(f"Error occurred while getting server quests: {e}")
                raise e

        async def create_quest(
            self,
            guild_id: str,
            action: str,
            method: str,
            content: str,
            times: int,
            reward: int,
            interaction=None,
        ):
            try:
                fallback_channel = (
                    discord.utils.get(interaction.guild.text_channels, name="general")
                    if interaction
                    else None
                )
                # Use the main manager's channel instance
                channel_id = await self.main_manager.channels.get_random_channel_for_guild(guild_id, fallback_channel=fallback_channel)
                if not channel_id:
                    message = "No redirected channels found for this guild. Please use the command to set redirect channels first."
                    logger.error(message)
                    if interaction:
                        await interaction.send(message)
                    return
                reward = random.randint(self.config.min_reward_per_time, self.config.max_reward_per_time) * times
                quest_data = {
                    "action": action,
                    "method": method,
                    "content": content,
                    "channel_id": channel_id,
                    "times": times,
                    "reward": reward,
                }
                await self.validate_input(**quest_data)
                await self.store_server_quest(guild_id, quest_data)
                quest_count = await self.get_server_quest_count(guild_id)
                quest_data["quest_id"] = quest_count + 1
                # Use the main manager's server instance
                users_in_server = await self.main_manager.server.find_users_in_server(guild_id)
                if not users_in_server:
                    raise ValueError("No users found in the server.")
                for user_id in users_in_server:
                    await self.insert_quest(guild_id, user_id, quest_data, interaction)
                logger.debug(f"Created quest for guild {guild_id} with action {action} and content {content}.")
                return quest_count + 1
            except (ValueError, PyMongoError) as e:
                logger.error(f"Error occurred while creating quest: {e}")
                if interaction:
                    await self.handle_error(interaction, e, title="Quest Creation")
                raise e

        async def create_member_quest(
            self,
            guild_id: str,
            user_id: str,
            action: str,
            method: str,
            content: str,
            times: int,
            interaction=None,
        ):
            try:
                reward = random.randint(self.config.min_reward_per_time, self.config.max_reward_per_time) * times
                quest_data = {
                    "action": action,
                    "method": method,
                    "content": content,
                    "times": times,
                    "reward": reward,
                }
                await self.validate_input(**quest_data)
                db = self.mongoConnect[self.config.db_name]
                server_collection = db["Servers"]
                quest_count = await self.get_server_quest_count(guild_id)
                quest_limit = await self.get_quest_limit(guild_id)
                if quest_count >= quest_limit:
                    raise ValueError("Quest limit exceeded for this server.")
                # Use the main manager's server instance
                user_exists = await self.main_manager.server.find_user_in_server(user_id, guild_id)
                if not user_exists:
                    raise ValueError("User not found in the server.")
                quest_data["quest_id"] = quest_count + 1
                await self.insert_quest(guild_id, user_id, quest_data, interaction)
                logger.debug(f"Created member quest for user {user_id} in guild {guild_id} with action {action} and content {content}.")
            except (ValueError, PyMongoError) as e:
                logger.error(f"Error occurred while creating member quest: {e}")
                if interaction:
                    await self.handle_error(interaction, e, title="Member Quest Creation")
                raise e

        async def generate_random_quest_content(self, bot, author, guild_id):
            try:
                with open(self.quest_content_file, "r") as quest_content_file:
                    quest_templates = quest_content_file.readlines()

                selected_quest_template = random.choice(quest_templates)

                return selected_quest_template
            except Exception as e:
                logger.error(
                    f"Error occurred while generating random quest content: {e}")
                return None

        async def generate_random_reaction_content(self, guild_id):
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return None

            emojis = [emoji for emoji in guild.emojis if not emoji.animated]

            if len(emojis) < 5:
                default_emojis = [
                    "😄",
                    "😁",
                    "😆",
                    "😅",
                    "😂",
                    "🤣",
                    "😊",
                    "😇",
                    "🙂",
                    "🙃",
                    "😉",
                    "😌",
                    "😍",
                    "🥰",
                    "😘",
                    "😗",
                    "😙",
                    "😚",
                ]
                emoji = random.choice(default_emojis)
            else:
                emoji = random.choice(emojis)

            logger.debug(f"Selected emoji: {emoji}")
            return str(emoji)

        async def insert_quest_existing_path(
            self, guild_id: str, user_id: str, quest_data: dict, interaction=None
        ):
            try:
                await self.validate_input(**quest_data)
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                server_data = await server_collection.find_one(
                    {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}}
                )

                if not server_data:
                    logger.debug(
                        f"User ID {user_id} does not exist in guild {guild_id}.")
                    return False

                await server_collection.update_one(
                    {
                        "guild_id": guild_id,
                        f"members.{user_id}.quests": {
                            "$not": {"$elemMatch": {"quest_id": quest_data["quest_id"]}}
                        },
                    },
                    {"$push": {f"members.{user_id}.quests": quest_data}},
                )
                logger.debug(
                    f"Inserted quest data for user {user_id} in guild {guild_id}.")
                return True
            except (ValueError, PyMongoError) as e:
                logger.error(f"Error occurred while inserting quest: {e}")
                if interaction:
                    await self.handle_error(interaction, e, title="Quest Insertion")
                return False

        async def add_new_quest(self, guild_id, message_author, action="send", method=None, chance=50):
         logger.debug(
            f"Attempting to add new quest for guild_id: {guild_id}, "
            f"message_author: {message_author}, action: {action}, method: {method}, chance: {chance}"
         )
         try:
            user_id = str(message_author.id)
            logger.debug(f"User ID: {user_id}")
            
            # Determine method if not provided
            if method is None:
                method = random.choice(["message", "reaction", "emoji"])
                logger.debug(f"Method chosen: {method}")
            
            # Set times range based on method
            if method == "message":
                min_times = self.config.min_times_message
                max_times = self.config.max_times_message
            elif method == "emoji":
                min_times = self.config.min_times_emoji
                max_times = self.config.max_times_emoji
            else:  # reaction
                min_times = self.config.min_times_reaction
                max_times = self.config.max_times_reaction
            
            times = random.randint(min_times, max_times)
            logger.debug(f"Random times selected: {times}")
            
            # Base reward calculation
            reward = random.randint(
                self.config.min_reward_per_time, 
                self.config.max_reward_per_time
            ) * times

            # Apply booster if method is boosted
            if method in self.config.booster:
                boost_value = self.config.booster[method]
                reward = int(reward * boost_value)
                logger.debug(
                    f"Applied booster for method '{method}': x{boost_value}, new reward: {reward}"
                )
                 
            # Random chance gating
            if random.randint(1, 100) > self.config.add_quest_chance:
                logger.debug("Random chance check failed. No quest will be created.")
                return None
            
            quest_limit = await self.get_quest_limit(guild_id)
            existing_quests = await self.find_quests_by_user_and_server(user_id, guild_id)
            if existing_quests is None:
                existing_quests = []
            if len(existing_quests) >= quest_limit:
                logger.debug("User has reached the quest limit. No quest will be created.")
                return None
            
            fallback_channel = (
                discord.utils.get(message_author.guild.text_channels, name="general")
                if message_author.guild
                else None
            )
            channel_id = await self.main_manager.channels.get_random_channel_for_guild(
                guild_id, fallback_channel=fallback_channel
            )
            if not channel_id:
                message = "No redirected channels found for this guild. Please use the command to set redirect channels first."
                logger.error(message)
                await message_author.send(message)
                return None
            
            # Generate unique quest content
            while True:
                if method == "message":
                    content = await self.generate_random_quest_content(self.bot, message_author, guild_id)
                else:
                    content = await self.generate_random_reaction_content(guild_id)
                if content is None:
                    logger.error("Failed to generate random quest content.")
                    return None
                content_exists = any(quest["content"] == content for quest in existing_quests)
                if not content_exists:
                    break
            
            logger.debug(f"Generated quest content: {content}")
            latest_quest_id = await self.get_latest_quest_id(guild_id, user_id)
            new_quest_id = 1 if latest_quest_id is None else latest_quest_id + 1
            quest_data = {
                "quest_id": new_quest_id,
                "action": action,
                "method": method,
                "channel_id": channel_id,
                "times": times,
                "content": content,
                "reward": reward,
                "progress": 0,
            }
            logger.debug(
                f"Creating quest for user_id: {user_id}, guild_id: {guild_id}, quest_data: {quest_data}"
            )
            if await self.insert_quest_existing_path(guild_id, user_id, quest_data):
                logger.debug(
                    f"Quest created for user_id: {user_id}, guild_id: {guild_id}, quest_data: {quest_data}"
                )
                return new_quest_id
            else:
                logger.debug(
                    f"Failed to create quest for user_id: {user_id}, guild_id: {guild_id} "
                    "because the user path does not exist."
                )
                return None
         except Exception as e:
            logger.error(f"Error occurred while adding new quest: {e}", exc_info=True)
            return None

        async def delete_all_quests(self, guild_id, message_author):
            logger.debug(
                f"Attempting to delete all quests for guild_id: {guild_id}, user_id: {message_author.id}"
            )
            try:
                user_id = str(message_author.id)

                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                guild_document = await server_collection.find_one(
                    {"guild_id": str(guild_id)}
                )

                if not guild_document:
                    logger.debug(f"No guild found with ID {guild_id}.")
                    return False  

                members_data = guild_document.get("members", {})

                if user_id not in members_data:
                    logger.debug(
                        f"User ID {user_id} not found in the guild {guild_id}.")
                    return False  

                user_data = members_data[user_id]
                quests = user_data.get("quests", [])

                if not quests:
                    logger.debug(
                        "No quests found for the user. Nothing to delete.")
                    return False  

                for quest in quests:
                    quest_id = quest.get("quest_id")
                    deletion_success = await self.delete_quest(
                        guild_id, quest_id, message_author
                    )

                    if deletion_success:
                        logger.debug(
                            f"Deleted quest_id: {quest_id} for user_id: {user_id} in guild_id: {guild_id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to delete quest_id: {quest_id} for user_id: {user_id} in guild_id: {guild_id}"
                        )

                logger.info(
                    f"Successfully deleted all quests for user_id: {user_id} in guild_id: {guild_id}"
                )
                return True  

            except Exception as e:
                logger.error(f"Error occurred while deleting all quests: {e}")
                return False

        async def delete_quest(self, guild_id: str, quest_id: int, interaction=None):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                logger.debug(
                    f"Querying for guild_id: {guild_id} with quest_id: {quest_id}")

                guild_document = await server_collection.find_one(
                    {"guild_id": str(guild_id)}
                )

                if not guild_document:
                    logger.debug(f"No guild found with ID {guild_id}.")
                    return

                members_data = guild_document.get("members", {})

                for member_id, member_data in members_data.items():
                    quests = member_data.get("quests", [])

                    logger.debug(f"Current quests for user {member_id}: {quests}")

                    if any(quest.get("quest_id") == quest_id for quest in quests):
                        new_quests = [
                            quest for quest in quests if quest.get("quest_id") != quest_id
                        ]

                        result = await server_collection.update_one(
                            {"guild_id": str(guild_id)},
                            {"$set": {f"members.{member_id}.quests": new_quests}},
                        )

                        if result.modified_count > 0:
                            logger.debug(
                                f"Deleted quest with ID {quest_id} for user {member_id} in guild {guild_id}."
                            )
                        else:
                            logger.debug(
                                f"Failed to delete quest with ID {quest_id} for user {member_id} in guild {guild_id}."
                            )
                    else:
                        logger.debug(
                            f"No quest with ID {quest_id} found for user {member_id} in guild {guild_id} to delete."
                        )

            except PyMongoError as e:
                logger.error(f"Error occurred while deleting quest: {e}")
                if interaction:
                    await self.handle_error(interaction, e, title="Quest Deletion")

        async def delete_quest_for_user(
            self, guild_id: str, user_id: str, quest_id: int, interaction=None
        ):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                logger.debug(
                    f"Querying for guild_id: {guild_id} with quest_id: {quest_id}")

                guild_document = await server_collection.find_one(
                    {"guild_id": str(guild_id)}
                )

                if not guild_document:
                    logger.debug(f"No guild found with ID {guild_id}.")
                    return

                members_data = guild_document.get("members", {})

                if user_id not in members_data:
                    logger.debug(
                        f"No user found with ID {user_id} in guild {guild_id}.")
                    return

                user_quests = members_data[user_id].get("quests", [])

                for quest in user_quests:
                    if quest.get("quest_id") == quest_id:
                        user_quests.remove(quest)
                        logger.debug(
                            f"Deleted quest with ID {quest_id} for user {user_id} in guild {guild_id}."
                        )
                        break  

                await server_collection.update_one(
                    {"guild_id": guild_id},
                    {"$set": {f"members.{user_id}.quests": user_quests}},
                )

            except PyMongoError as e:
                logger.error(f"Error occurred while deleting quest for user: {e}")
                if interaction:
                    await self.handle_error(interaction, e, title="Quest Deletion")

        async def update_quest_progress(
            self, guild_id: str, user_id: str, quest_id: int, progress: int
        ):
            try:
                db = self.mongoConnect[self.DB_NAME]
                server_collection = db["Servers"]

                await server_collection.update_one(
                    {"guild_id": guild_id, f"members.{user_id}.quests.quest_id": quest_id},
                    {"$set": {f"members.{user_id}.quests.$.progress": progress}},
                )

                logger.debug(
                    f"Quest {quest_id} progress updated for user {user_id} in guild {guild_id}."
                )
            except PyMongoError as e:
                logger.error(f"Error occurred while updating quest progress: {e}")
                raise e

        # Helper methods that need to be accessible
        @staticmethod
        async def validate_input(**kwargs):
            for key, value in kwargs.items():
                if value is None or value == "":
                    raise ValueError(f"{key} cannot be None or empty")

        async def handle_error(self, interaction, error, title="Error"):
            """Handle errors by logging and optionally sending a message to the user."""
            logger.error(f"{title}: {error}")
            if interaction and hasattr(interaction, 'send'):
                try:
                    await interaction.send(f"An error occurred: {str(error)}")
                except Exception as e:
                    logger.error(f"Failed to send error message: {e}")

