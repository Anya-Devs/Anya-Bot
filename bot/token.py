import os
from motor.motor_asyncio import AsyncIOMotorClient
from data.local.const import bot_config
use_test_bot = 0

prefix = bot_config[use_test_bot]["prefix"]
token_flavor = bot_config[use_test_bot]["token_key"]


async def get_bot_token():
    mongo_url = os.getenv("MONGO_URI")
    if not mongo_url:
        raise ValueError("No MONGO_URI found in environment variables")

    client = AsyncIOMotorClient(mongo_url)
    db = client["Bot"]
    collection = db["information"]

    token_data = await collection.find_one({token_flavor: {"$exists": True}})
    if token_data:
        return token_data.get(token_flavor)
    else:
        raise ValueError(f"No token found in the database for key: {token_flavor}")
