import aiohttp
import asyncio
import os
import aiofiles
import logging
from tqdm.asyncio import tqdm_asyncio
import random
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PokemonImageDownloader:
    def __init__(self):
        self.image_folder = Path("data/commands/pokemon/pokemon_images")
        self.image_folder.mkdir(parents=True, exist_ok=True)
        self.pokemon_api_url = "https://pokeapi.co/api/v2/pokemon"
        self.pokemon_info_url = "https://pokeapi.co/api/v2/pokemon/{}/"

    async def fetch_all_pokemon_names(self, session):
        names = []
        url = self.pokemon_api_url
        while url:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch Pokémon names, status {response.status}")
                    break
                data = await response.json()
                names.extend([p["name"] for p in data["results"]])
                url = data.get("next")
        return names

    async def fetch_pokemon_info(self, session, name):
        url = self.pokemon_info_url.format(name.lower())
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["sprites"]["other"]["official-artwork"]["front_default"]
        except Exception as e:
            logger.warning(f"Failed fetching {name}: {e}")
        return None

    async def download_image(self, session, name, semaphore):
        async with semaphore:
            await asyncio.sleep(0.01)
            filepath = self.image_folder / f"{name.lower()}.png"
            if filepath.exists():
                return
            url = await self.fetch_pokemon_info(session, name)
            if not url:
                return
            try:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        async with aiofiles.open(filepath, "wb") as f:
                            await f.write(await resp.read())
            except Exception as e:
                logger.warning(f"Failed to download {name}: {e}")

    async def download_all_images(self, max_concurrent=10):
        semaphore = asyncio.Semaphore(max_concurrent)
        async with aiohttp.ClientSession() as session:
            names = await self.fetch_all_pokemon_names(session)
            tasks = [self.download_image(session, n, semaphore) for n in names]
            for f in tqdm_asyncio.as_completed(tasks, total=len(tasks), desc="Downloading Pokémon"):
                await f

if __name__ == "__main__":
    downloader = PokemonImageDownloader()
    asyncio.run(downloader.download_all_images())
