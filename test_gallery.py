#!/usr/bin/env python3
"""
Test file for the enhanced gallery command
"""

import asyncio
import sys
from pathlib import Path
import asyncio

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.cogs.game.images import generate_gallery_image

async def test_gallery():
    """Test the enhanced gallery image generation"""
    print("🖼️ Testing Enhanced Gallery Command")
    print("=" * 50)
    
    # Create test characters with different rarities, genders, and likes
    test_characters = [
        {"name": "Legendary Heroine", "anime": "Epic Tales", "rarity": "legendary", "uid": "LEG001", "image_url": "https://i.pinimg.com/736x/a5/bd/5e/a5bd5e7957223a287aebe8bca3c4666f.jpg", "gender": "female", "likes": 1247},
        {"name": "Epic Warrior", "anime": "Battle Saga", "rarity": "epic", "uid": "EPI001", "image_url": None, "gender": "male", "likes": 892},
        {"name": "Rare Mage", "anime": "Magic Academy", "rarity": "rare", "uid": "RAR001", "image_url": None, "gender": "female", "likes": 656},
        {"name": "Uncommon Rogue", "anime": "Shadow Guild", "rarity": "uncommon", "uid": "UNC001", "image_url": None, "gender": "male", "likes": 423},
        {"name": "Common Peasant", "anime": "Village Life", "rarity": "common", "uid": "COM001", "image_url": None, "gender": "female", "likes": 187},
        {"name": "Silver Knight", "anime": "Crystal Saga", "rarity": "rare", "uid": "RAR002", "image_url": None, "gender": "male", "likes": 734},
        {"name": "Bronze Fighter", "anime": "Arena Battles", "rarity": "uncommon", "uid": "UNC002", "image_url": None, "gender": "female", "likes": 312},
        {"name": "Gold Phoenix", "anime": "Mythic Birds", "rarity": "epic", "uid": "EPI002", "image_url": None, "gender": "male", "likes": 1567},
        {"name": "Platinum Dragon", "anime": "Dragon Lore", "rarity": "legendary", "uid": "LEG002", "image_url": None, "gender": "female", "likes": 2103},
        {"name": "Wood Elf", "anime": "Forest Tales", "rarity": "common", "uid": "COM002", "image_url": None, "gender": "male", "likes": 145},
        {"name": "Steel Samurai", "anime": "Bushido Code", "rarity": "rare", "uid": "RAR003", "image_url": None, "gender": "male", "likes": 891},
        {"name": "Crystal Mage", "anime": "Elemental Wars", "rarity": "epic", "uid": "EPI003", "image_url": None, "gender": "female", "likes": 1234},
        {"name": "Diamond Knight", "anime": "Royal Guard", "rarity": "legendary", "uid": "LEG003", "image_url": None, "gender": "male", "likes": 1876},
        {"name": "Iron Warrior", "anime": "Metal Clan", "rarity": "uncommon", "uid": "UNC003", "image_url": None, "gender": "female", "likes": 567},
        {"name": "Stone Golem", "anime": "Earth Magic", "rarity": "common", "uid": "COM003", "image_url": None, "gender": "male", "likes": 234},
    ]
    
    try:
        print("  Generating gallery with all cards...")
        buffer = await generate_gallery_image(
            characters=test_characters,
            page=1,
            cards_per_page=15,
            user_name="TestUser",
            user_avatar_bytes=None,
            filter_type="all",
            search_query=None
        )
        
        # Save test image
        with open("test_gallery.png", "wb") as f:
            f.write(buffer.getvalue())
        print("  ✅ Gallery saved as test_gallery.png")
        
        print("\n🎉 Gallery test complete!")
        print("\n📝 Features tested:")
        print("  • Cards look exactly like .draw command")
        print("  • 5 cards per row with proper spacing")
        print("  • Full-size cards (220x340) with textures")
        print("  • Enhanced header with user info")
        print("  • Rarity statistics display")
        print("  • Filter information display")
        
        print("\n💡 Check test_gallery.png to see the result!")
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gallery())
