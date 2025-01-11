import aiohttp
import asyncio
import os
import aiofiles
import logging

# Setup the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pokemon_Image_Downloader:
    def __init__(self):
        self.image_folder = "Data/pokemon/pokemon_images"
        self.local_color_memory = []  # Binary local color comparator memory
        self.pokemon_api_url = "https://pokeapi.co/api/v2/pokemon"
        self.pokemon_info_url = "https://pokeapi.co/api/v2/pokemon/{}/"

    async def fetch_all_pokemon_names(self):
        pokemon_names = []
        url = self.pokemon_api_url
        while url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        for result in data["results"]:
                            pokemon_names.append(result["name"])
                        url = data.get("next")
                    else:
                        logger.error("Failed to fetch Pokémon names.")
                        break
        return pokemon_names

    async def fetch_pokemon_info(self, pokemon_name):
        url = self.pokemon_info_url.format(pokemon_name.lower())
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["sprites"]["other"]["official-artwork"]["front_default"]
                else:
                    logger.error(f"Failed to fetch info for {pokemon_name}.")
                    return None

    async def download_image(self, session, pokemon_name, semaphore):
        async with semaphore:
            filename = f"{pokemon_name.lower()}.png"
            filepath = os.path.join(self.image_folder, filename)
            if not os.path.exists(filepath):
                official_artwork_url = await self.fetch_pokemon_info(pokemon_name)
                if official_artwork_url:
                    try:
                        async with session.get(official_artwork_url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                async with aiofiles.open(filepath, "wb") as f:
                                    await f.write(image_data)
                                logger.info(f"Downloaded image for {pokemon_name}.")
                            else:
                                logger.error(
                                    f"Failed to download image for {pokemon_name}."
                                )
                    except Exception as e:
                        logger.error(f"Error downloading image for {pokemon_name}: {e}")
                else:
                    logger.error(f"Failed to fetch information for {pokemon_name}.")
            else:
                logger.info(
                    f"Image for {pokemon_name} already exists, skipping download."
                )

    async def download_all_images(self, max_concurrent_tasks=10):
        pokemon_names = await self.fetch_all_pokemon_names()
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

        async with aiohttp.ClientSession() as session:
            tasks = []
            semaphore = asyncio.Semaphore(max_concurrent_tasks)
            for pokemon_name in pokemon_names:
                tasks.append(self.download_image(session, pokemon_name, semaphore))
            await asyncio.gather(*tasks)


downloader = Pokemon_Image_Downloader()
asyncio.run(downloader.download_all_images())
