#!/usr/bin/env python3
import asyncio
import aiohttp

async def test():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    async with aiohttp.ClientSession() as session:
        # Test rule34.xxx directly
        params = {"page": "dapi", "s": "post", "q": "index", "json": 1, "tags": "1girl", "limit": 5, "pid": 0}
        async with session.get("https://rule34.xxx/index.php", params=params, headers=headers) as resp:
            print(f"Status: {resp.status}")
            print(f"Content-Type: {resp.content_type}")
            text = await resp.text()
            print(f"Response ({len(text)} chars): {text[:500]}")

if __name__ == "__main__":
    asyncio.run(test())
