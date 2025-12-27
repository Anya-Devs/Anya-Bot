#!/usr/bin/env python3
import asyncio
import aiohttp
import sys
sys.path.append('.')
from utils.cogs.art import Gelbooru, Rule34, art_logger

async def test():
    async with aiohttp.ClientSession() as session:
        # Test Gelbooru
        print("Testing Gelbooru...")
        gelbooru = Gelbooru(session)
        results = await gelbooru.search("1girl", limit=5, nsfw=False, page=0)
        print(f"Gelbooru: {len(results)} results")
        if results:
            print(f"  Sample: {results[0]['url'][:60]}...")
        
        print("\nTesting Rule34...")
        rule34 = Rule34(session)
        results = await rule34.search("1girl", limit=5, nsfw=True, page=0)
        print(f"Rule34: {len(results)} results")
        if results:
            print(f"  Sample: {results[0]['url'][:60]}...")

if __name__ == "__main__":
    asyncio.run(test())
