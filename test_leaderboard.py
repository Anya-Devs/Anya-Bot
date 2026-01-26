"""Test script to generate a sample leaderboard image."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.utils.cogs.leaderboard_image import LeaderboardImageGenerator


async def main():
    """Generate a test leaderboard image with sample data."""
    generator = LeaderboardImageGenerator()
    
    # Sample entries mimicking real data
    entries = [
        {"rank": 1, "username": "AnyaForger", "points": 15420, "cards": 45, "quests_done": 23, "reviews": 12, "avatar_url": None},
        {"rank": 2, "username": "LoidForger", "points": 12350, "cards": 38, "quests_done": 19, "reviews": 8, "avatar_url": None},
        {"rank": 3, "username": "YorForger", "points": 10890, "cards": 32, "quests_done": 15, "reviews": 6, "avatar_url": None},
        {"rank": 4, "username": "BondTheGreat", "points": 8540, "cards": 28, "quests_done": 12, "reviews": 5, "avatar_url": None},
        {"rank": 5, "username": "FrankieTheInformer", "points": 7230, "cards": 24, "quests_done": 10, "reviews": 3, "avatar_url": None},
        {"rank": 6, "username": "DamianDesmond", "points": 6120, "cards": 20, "quests_done": 8, "reviews": 2, "avatar_url": None},
        {"rank": 7, "username": "BeckyBlackbell", "points": 5480, "cards": 18, "quests_done": 7, "reviews": 4, "avatar_url": None},
        {"rank": 8, "username": "HendersonSensei", "points": 4320, "cards": 15, "quests_done": 6, "reviews": 1, "avatar_url": None},
        {"rank": 9, "username": "SylviaWatcher", "points": 3890, "cards": 12, "quests_done": 5, "reviews": 2, "avatar_url": None},
        {"rank": 10, "username": "NightfallAgent", "points": 2750, "cards": 10, "quests_done": 4, "reviews": 1, "avatar_url": None},
    ]
    
    print("Generating leaderboard image...")
    print(f"Image width: {generator.width}px")
    
    try:
        # Generate image with pagination
        buffer = await generator.generate(entries, title="LEADERBOARD", page=1, total_pages=3)
        
        # Save to file for inspection
        output_path = os.path.join(os.path.dirname(__file__), "test_leaderboard_output.png")
        with open(output_path, "wb") as f:
            f.write(buffer.read())
        
        print(f"Leaderboard image saved to: {output_path}")
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Error generating leaderboard: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
