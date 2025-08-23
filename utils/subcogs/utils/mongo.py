from motor.motor_asyncio import AsyncIOMotorClient


class MongoHelper:
    def __init__(self, db):
        self.db = db

    async def add(self, col, pokemon, uid):
        c, d = self.db[col], await self.db[col].find_one({"user_id": uid})
        if not d:
            await c.insert_one({"user_id": uid, "pokemon": [pokemon]})
            return True
        if pokemon in d["pokemon"]:
            return False
        await c.update_one({"user_id": uid}, {"$push": {"pokemon": pokemon}})
        return True

    async def remove(self, col, pokemon, uid):
        d = await self.db[col].find_one({"user_id": uid})
        if not d or pokemon not in d["pokemon"]:
            return False
        await self.db[col].update_one({"user_id": uid}, {"$pull": {"pokemon": pokemon}})
        return True

    async def list(self, col, uid):
        d = await self.db[col].find_one({"user_id": uid})
        return d["pokemon"] if d else []

    async def replace(self, col, pokemon, uid):
        await self.db[col].update_one({"user_id": uid}, {"$set": {"pokemon": [pokemon]}}, upsert=True)
        return True

    async def clear(self, col, uid):
        await self.db[col].update_one({"user_id": uid}, {"$set": {"pokemon": []}})
        return True

    # Starboard methods
    async def add_star(self, message_id, user_id, pokemon, level, shiny=False, rare=False, regional=False, timestamp=None, jump_url=None):
        doc = {
            "message_id": message_id,
            "user_id": user_id,
            "pokemon": pokemon,
            "level": level,
            "shiny": shiny,
            "rare": rare,
            "regional": regional,
            "timestamp": timestamp,
            "jump_url": jump_url
        }
        await self.db["starboard"].insert_one(doc)
        return True

    async def get_star(self, message_id):
        return await self.db["starboard"].find_one({"message_id": message_id})

    async def remove_star(self, message_id):
        result = await self.db["starboard"].delete_one({"message_id": message_id})
        return result.deleted_count > 0

    async def list_stars_by_user(self, user_id):
        cursor = self.db["starboard"].find({"user_id": user_id})
        return await cursor.to_list(length=None)  # fetch all

    # Starboard config methods
    async def set_starboard_channel(self, guild_id, channel_id):
        await self.db["starboard_config"].update_one(
            {"_id": str(guild_id)},
            {"$set": {"channel_id": str(channel_id)}},
            upsert=True
        )
        return True

    async def get_starboard_channel(self, guild_id):
        doc = await self.db["starboard_config"].find_one({"_id": str(guild_id)})
        if doc and "channel_id" in doc:
            return int(doc["channel_id"])
        return None

