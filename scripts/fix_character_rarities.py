"""
Fix character rarities in the database.
Recalculates rarity for all existing characters based on their favorites count.
"""

import asyncio
import os
import sys
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from bot.utils.cogs.game.const import get_rarity_from_favorites

# Load environment variables from the .github directory
env_path = parent_dir / '.github' / '.env'
load_dotenv(dotenv_path=env_path)

async def fix_character_rarities():
    """Fix all character rarities in the database."""
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        print("❌ MONGO_URI not found in environment variables!")
        return
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client["Quest"]
    server_col = db["Servers"]
    
    print("🔍 Scanning all servers for characters...")
    
    total_updated = 0
    total_characters = 0
    servers_processed = 0
    
    async for server in server_col.find({}):
        guild_id = server.get("guild_id")
        members = server.get("members", {})
        
        if not members:
            continue
        
        servers_processed += 1
        print(f"\n📊 Processing server: {guild_id}")
        
        for user_id, member_data in members.items():
            inventory = member_data.get("gacha_inventory", [])
            
            if not inventory:
                continue
            
            updated_inventory = []
            user_updated = 0
            
            for char in inventory:
                total_characters += 1
                favorites = char.get("favorites", 0)
                old_rarity = char.get("rarity", "common")
                
                # Calculate correct rarity based on favorites
                correct_rarity = get_rarity_from_favorites(favorites)
                
                # Update if rarity is wrong
                if old_rarity != correct_rarity:
                    char["rarity"] = correct_rarity
                    total_updated += 1
                    user_updated += 1
                    print(f"  ✅ Fixed {char.get('name', 'Unknown')} ({favorites:,} ❤️): {old_rarity} → {correct_rarity}")
                
                updated_inventory.append(char)
            
            # Update user's inventory if any changes were made
            if user_updated > 0:
                await server_col.update_one(
                    {"guild_id": guild_id},
                    {"$set": {f"members.{user_id}.gacha_inventory": updated_inventory}}
                )
    
    print(f"\n{'='*60}")
    print(f"✨ Migration Complete!")
    print(f"{'='*60}")
    print(f"📊 Servers processed: {servers_processed}")
    print(f"🎴 Total characters scanned: {total_characters}")
    print(f"✅ Characters updated: {total_updated}")
    print(f"{'='*60}")
    
    client.close()

if __name__ == "__main__":
    print("🚀 Starting character rarity fix...")
    asyncio.run(fix_character_rarities())
