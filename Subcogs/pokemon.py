import csv
import re
import logging
from fuzzywuzzy import fuzz
from Imports.discord_imports import *

# Setup the logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Ping_Pokemon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.csv_file = 'Data/pokemon/pokemon_special_names.csv'
        self.user_author_id = 854233015475109888  # ID of the user who triggers the special message
        # Define the messages for rare and regional Pokémon
        self.message_rare_pokemon = "<@&1278580577104040023>"
        self.message_regional_pokemon = "<@&1278580577104040022>"
        #self.message_unknown_pokemon = "<:mimikyu_n_pat:1318004958356045825> This Pokémon is not recognized as rare or regional."

    def load_pokemon_data(self):
        """Load the rare and regional Pokémon names from the CSV file."""
        rare_pokemon = []
        regional_pokemon = []
        
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # Skip header row
                for row in reader:
                    rare_name = row[0].strip()
                    regional_name = row[1].strip()

                    if rare_name:
                        rare_pokemon.append(rare_name.lower())  # Add rare Pokémon to list (lowercase)
                    if regional_name:
                        regional_pokemon.append(regional_name.lower())  # Add regional Pokémon to list (lowercase)
            
            return rare_pokemon, regional_pokemon
        except FileNotFoundError:
            logger.error(f"CSV file not found: {self.csv_file}")
            return [], []

    def transform_pokemon_name(self, name):
        """Transforms the Pokémon name with region and cleans up."""
        # Translation map for regional variants
        translation_map = {
            "alolan": "-alola",
            "galarian": "-galar",
            "hisui": "-hisui",
            "paldean": "-paldea"
        }

        # Optional: Use regex to remove any extra non-alphabetic characters (e.g., percentages, numbers, etc.)
        name_cleaned = re.sub(r'[^a-zA-Z\s]', '', name)  # Remove anything that's not a letter or space

        # Check if the name matches any regional variant (e.g., alolan, galarian)
        name_lower = name_cleaned.lower()
        for region, suffix in translation_map.items():
            if region in name_lower:
                # Split the name to separate the regional prefix from the base Pokémon name
                parts = name_cleaned.split()
                base_name = parts[1].capitalize() if len(parts) > 1 else parts[0].capitalize()  # Pokémon name is the second part
                return f"{base_name.lower()}{suffix}", region  # Return both the transformed name and the region

        # If no transformation is needed, return the cleaned name and None for region
        return name_cleaned, None

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages and check for Pokémon names with percentages."""
        # Ignore bot messages and messages from other users
        if message.author.bot or message.author.id != self.user_author_id:
            return

        # Regex pattern to match Pokémon names with spaces and percentages
        pattern = re.compile(r"([a-zA-Z\s-]+):\s([\d\.]+)%")
        match = pattern.search(message.content)
        
        if match:
            pokemon_name = match.group(1).strip()  # Strip leading/trailing spaces
            percentage = match.group(2)

            print(f"Matched Pokémon name: {pokemon_name}, Percentage: {percentage}")

            # Translate the Pokémon name if it's regional
            translated_pokemon_name, region = self.transform_pokemon_name(pokemon_name)

            # Load Pokémon data (rare and regional)
            rare_pokemon, regional_pokemon = self.load_pokemon_data()

            # Fuzzy matching to check if the Pokémon is rare or regional
            matched_rare = None
            matched_regional = None
            for rare in rare_pokemon:
                if fuzz.ratio(translated_pokemon_name, rare) > 90:  # Fuzzy match threshold
                    matched_rare = rare
                    break

            for regional in regional_pokemon:
                if fuzz.ratio(translated_pokemon_name, regional) > 90:  # Fuzzy match threshold
                    matched_regional = regional
                    break

            if matched_rare:
                await message.channel.send(self.message_rare_pokemon)
            elif matched_regional:
                await message.channel.send(self.message_regional_pokemon)
            """
            else:
                await message.channel.send(self.message_unknown_pokemon)
            """
