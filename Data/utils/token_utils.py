import os
from motor.motor_asyncio import AsyncIOMotorClient

prefix = "."

async def get_bot_token():

    mongo_url = os.getenv("MONGO_URI")
    if not mongo_url:
        raise ValueError("No MONGO_URI found in environment variables")

    client = AsyncIOMotorClient(mongo_url)
    db = client["Bot"] 
    collection = db["information"]
    token_flavor = "Token"
    
    token_data = await collection.find_one({token_flavor: {"$exists": True}})
    if token_data:
        return token_data.get(token_flavor)
    else:
        raise ValueError("No token found in the database")