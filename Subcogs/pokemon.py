import csv
import re
import logging
from fuzzywuzzy import fuzz
from Imports.discord_imports import *

                  
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Ping_Pokemon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.csv_file = 'Data/pokemon/pokemon_special_names.csv'
        self.user_author_id = 854233015475109888                                                   
                                                           
        self.message_rare_pokemon = "<@&1278580577104040023>"
        self.message_regional_pokemon = "<@&1278580577104040022>"
                                                                                                                                  

    def load_pokemon_data(self):
        rare_pokemon = []
        regional_pokemon = []
        
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)                   
                for row in reader:
                    rare_name = row[0].strip()
                    regional_name = row[1].strip()

                    if rare_name:
                        rare_pokemon.append(rare_name.lower())                                        
                    if regional_name:
                        regional_pokemon.append(regional_name.lower())                                            
            
            return rare_pokemon, regional_pokemon
        except FileNotFoundError:
            logger.error(f"CSV file not found: {self.csv_file}")
            return [], []

    def transform_pokemon_name(self, name):
                                               
        translation_map = {
            "alolan": "-alola",
            "galarian": "-galar",
            "hisui": "-hisui",
            "paldean": "-paldea"
        }

                                                                                                              
        name_cleaned = re.sub(r'[^a-zA-Z\s]', '', name)                                                

                                                                                 
        name_lower = name_cleaned.lower()
        for region, suffix in translation_map.items():
            if region in name_lower:
                                                                                           
                parts = name_cleaned.split()
                base_name = parts[1].capitalize() if len(parts) > 1 else parts[0].capitalize()                                   
                return f"{base_name.lower()}{suffix}", region                                                   

                                                                                     
        return name_cleaned, None

    @commands.Cog.listener()
    async def on_message(self, message):
        """ Listen for messages and check for Pokémon names with percentages."""
                                                           
        if message.author.bot or message.author.id != self.user_author_id:
            return

                                                                          
        pattern = re.compile(r"([a-zA-Z\s-]+):\s([\d\.]+)%")
        match = pattern.search(message.content.split("\n")[0].strip())
        
        message_content = message.content
        if match:
            pokemon_name = match.group(1).strip()                                 
            percentage = match.group(2)

            print(f"Matched Pokémon name: {pokemon_name}, Percentage: {percentage}")

                                                         
            translated_pokemon_name, region = self.transform_pokemon_name(pokemon_name)
        
            translated_pokemon_name = translated_pokemon_name.lower()
                                                   
            rare_pokemon, regional_pokemon = self.load_pokemon_data()

                                                                        
            matched_rare = None
            matched_regional = None
            for rare in rare_pokemon:
                if fuzz.ratio(translated_pokemon_name, rare) > 90:                         
                    matched_rare = rare
                    break

            for regional in regional_pokemon:
                if fuzz.ratio(translated_pokemon_name, regional) > 90:                         
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
