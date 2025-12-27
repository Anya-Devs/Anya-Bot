#!/usr/bin/env python3
import asyncio
import aiohttp

async def test():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    async with aiohttp.ClientSession() as session:
        params = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": 1,
            "tags": "1girl",
            "limit": 5,
            "pid": 0,
            "api_key": "",
            "user_id": "2"
        }
        async with session.get("https://api.rule34.xxx/index.php", params=params, headers=headers) as resp:
            print(f"Status: {resp.status}")
            text = await resp.text()
            print(f"Response: {text[:500]}")

if __name__ == "__main__":
    asyncio.run(test())
