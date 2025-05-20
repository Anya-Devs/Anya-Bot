import aiohttp
import asyncio
import os
import csv
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PokemonNamesDownloader:
    def __init__(self):
        self.pokemon_species_url = "https://pokeapi.co/api/v2/pokemon-species"
        self.csv_file = 'data/commands/pokemon/pokemon_special_names.csv'
        self.regional_terms = ["alola", "galar", "hisui", "paldea"]  

    async def fetch_pokemon_species(self):
        species_list = []
        url = self.pokemon_species_url
        while url:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        species_list.extend(data["results"])
                        url = data.get("next")
                    else:
                        logger.error("Failed to fetch Pokémon species.")
                        break
        return species_list

    async def categorize_pokemon(self, species_list):
        rare_pokemon = []
        regional_pokemon = []

        async with aiohttp.ClientSession() as session:
            for species in species_list:
                async with session.get(species["url"]) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data["is_legendary"] or data["is_mythical"]:
                            rare_pokemon.append(data["name"])

                        
                        for variety in data["varieties"]:
                            if any(region in variety["pokemon"]["name"] for region in self.regional_terms):
                                regional_pokemon.append(variety["pokemon"]["name"])
                    else:
                        logger.error(f"Failed to fetch details for {species['name']}.")

        return rare_pokemon, regional_pokemon

    async def save_to_csv(self, rare_pokemon, regional_pokemon):
        os.makedirs(os.path.dirname(self.csv_file), exist_ok=True)
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Rare Pokémon", "Regional Pokémon"])
            
            max_rows = max(len(rare_pokemon), len(regional_pokemon))
            for i in range(max_rows):
                rare_name = rare_pokemon[i] if i < len(rare_pokemon) else ""
                regional_name = regional_pokemon[i] if i < len(regional_pokemon) else ""
                writer.writerow([rare_name, regional_name])
        logger.info(f"Pokémon names saved to {self.csv_file}")

    async def generate_pokemon_csv(self):
        """Generate the CSV file with rare and regional Pokémon."""
        species_list = await self.fetch_pokemon_species()
        logger.info(f"Fetched {len(species_list)} Pokémon species.")

        rare_pokemon, regional_pokemon = await self.categorize_pokemon(species_list)
        logger.info(f"Found {len(rare_pokemon)} rare Pokémon and {len(regional_pokemon)} regional Pokémon.")

        await self.save_to_csv(rare_pokemon, regional_pokemon)


async def main():
    downloader = PokemonNamesDownloader()
    await downloader.generate_pokemon_csv()

asyncio.run(main())
