class Pokemon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = 'Data/pokemon_data.pkl'
        self.pokemon_api_url = "https://pokeapi.co/api/v2/pokemon"
        self.pokemon_info_url = "https://pokeapi.co/api/v2/pokemon/{}/"
        self.pokemon_data = {}
        self.primary_color = primary_color
        self.error_custom_embed = error_custom_embed
        self.temp_folder = 'temp'
        self.owner_id =  None
        if not os.path.exists(self.temp_folder):
            os.makedirs(self.temp_folder)  # Ensure temp directory exists

    async def load_data(self, ctx):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'rb') as f:
                    self.pokemon_data = pickle.load(f)
                logger.info("Data loaded successfully from %s", self.data_file)
            except (EOFError, pickle.UnpicklingError) as e:
                logger.error("Data file is corrupted. Reprocessing images. Error: %s", e)
                await ctx.send("Data file is corrupted. Reprocessing images...")
                self.pokemon_data = await self.process_and_save_images(ctx)
        else:
            logger.info("Data file does not exist. Processing images...")
            await ctx.send("Data file does not exist. Processing images...")
            self.pokemon_data = await self.process_and_save_images(ctx)

    async def process_and_save_images(self, ctx):
        temp_data_files = []
        pokemon_names = await self.fetch_pokemon_names()
        for pokemon_name in pokemon_names:
            try:
                image_url = await self.fetch_pokemon_image_url(pokemon_name)
                if image_url:
                    image_path = await self.download_image(image_url)
                    image_data = self.create_image_data(image_path)
                    
                    # Save image data to a temporary file
                    temp_file_path = os.path.join(self.temp_folder, f'{pokemon_name}.pkl')
                    with open(temp_file_path, 'wb') as f:
                        pickle.dump({pokemon_name: image_data}, f)
                    temp_data_files.append(temp_file_path)

                    logger.info("Processed image for Pokémon: %s", pokemon_name)
                else:
                    logger.warning("No image URL found for Pokémon: %s", pokemon_name)
            except Exception as e:
                logger.error("Failed to process image for Pokémon %s. Error: %s", pokemon_name, e)
                continue  # Skip this Pokémon and move to the next one

        # Merge temporary files into final data file
        final_data = {}
        for temp_file in temp_data_files:
            try:
                with open(temp_file, 'rb') as f:
                    data = pickle.load(f)
                    final_data.update(data)
                os.remove(temp_file)  # Clean up temporary file
            except Exception as e:
                logger.error("Failed to merge temporary data file %s. Error: %s", temp_file, e)

        with open(self.data_file, 'wb') as f:
            pickle.dump(final_data, f)
        logger.info("Completed processing and saved %d Pokémon.", len(final_data))
        return final_data

    async def fetch_pokemon_names(self):
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
    
    async def fetch_pokemon_image_url(self, pokemon_name):
        url = f'https://pokeapi.co/api/v2/pokemon/{pokemon_name}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['sprites']['other']['official-artwork']['front_default']
                else:
                    logger.error("Failed to fetch image URL for Pokémon %s. Status code: %d", pokemon_name, response.status)
                    return None

    def create_image_data(self, image_path):
        try:
            with Image.open(image_path) as img:
                img = img.convert('RGB')
                image_data = self.extract_features(img)
            return image_data
        except Exception as e:
            logger.error("Failed to create image data from %s. Error: %s", image_path, e)
            raise

    def extract_features(self, img):
        img_resized = resize(np.array(img), (128, 128))
        edges = canny(img_resized.mean(axis=2))
        return edges.tobytes()

    async def process_prediction(self, ctx, url):
        await self.load_data(ctx)

        if url:
            try:
                image_path = await self.download_image(url)
                image_data = self.create_image_data(image_path)

                best_match = None
                highest_score = float('-inf')

                for pokemon_name, stored_image_data in self.pokemon_data.items():
                    score = self.compare_images(image_data, stored_image_data)
                    if score > highest_score:
                        highest_score = score
                        best_match = pokemon_name

                if highest_score >= 0.70:
                    await ctx.send(f"The Pokémon in the image is most likely: **{best_match}** with a confidence of {highest_score:.2f}.")
                    logger.info("Prediction: %s with confidence %.2f", best_match, highest_score)

                    if ctx.author.id == self.owner_id:
                        await ctx.send(f"Is this prediction correct? Type 'yes' if correct or 'no' to provide a correction.")
                        try:
                            response = await self.bot.wait_for(
                                'message',
                                check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                timeout=60.0
                            )
                            if response.content.lower() == 'no':
                                await ctx.send("Please provide the correct Pokémon name.")
                                try:
                                    correction_response = await self.bot.wait_for(
                                        'message',
                                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel,
                                        timeout=60.0
                                    )
                                    correct_name = correction_response.content.strip()
                                    if correct_name and correct_name != best_match:
                                        await self.update_data_with_correct_name(image_path, correct_name)
                                        await ctx.send(f"Updated the Pokémon name to **{correct_name}** and saved the data.")
                                        logger.info("Updated Pokémon name to %s", correct_name)
                                except asyncio.TimeoutError:
                                    await ctx.send("No response received. The prediction will not be updated.")
                            else:
                                logger.info("Prediction confirmed as correct.")
                        except asyncio.TimeoutError:
                            await ctx.send("No response received. The prediction will not be updated.")
                else:
                    await ctx.send("I couldn't confidently identify the Pokémon. Please try with another image.")
                    logger.info("Confidence too low for prediction.")
            except Exception as e:
                logger.error("Failed to process prediction. Error: %s", e)
                await ctx.send("An error occurred while processing the image.")

    def compare_images(self, image_data1, image_data2):
        array1 = np.frombuffer(image_data1, dtype=bool)
        array2 = np.frombuffer(image_data2, dtype=bool)
        return np.sum(array1 == array2) / len(array1)

    async def download_image(self, url):
        filename = os.path.join(self.temp_folder, 'downloaded_image.png')
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(filename, 'wb') as f:
                            f.write(await response.read())
            logger.info("Downloaded image from %s", url)
            return filename
        except Exception as e:
            logger.error("Failed to download image from %s. Error: %s", url, e)
            raise

    async def update_data_with_correct_name(self, image_path, correct_name):
        try:
            image_data = self.create_image_data(image_path)
            self.pokemon_data[correct_name] = image_data  # Overwrite or add the new data

            with open(self.data_file, 'wb') as f:
                pickle.dump(self.pokemon_data, f)
            logger.info("Updated data with correct Pokémon name: %s", correct_name)
        except Exception as e:
            logger.error("Failed to update Pokémon data for %s. Error: %s", correct_name, e)

            
    async def predict_pokemon_command(self, ctx, arg=None):
        image_url = None
        
        if arg:
            image_url = arg
        elif ctx.message.attachments:
            image_url = ctx.message.attachments[0].url
        elif ctx.message.reference:
            reference_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if reference_message.attachments:
                image_url = reference_message.attachments[0].url
            elif reference_message.embeds:
                embed = reference_message.embeds[0]
                if embed.image:
                    image_url = embed.image.url

        if image_url:
            await self.process_prediction(ctx, image_url)
        else:
            await ctx.send("Please provide an image or a URL to an image.")
            logger.info("No image URL provided.")
            
    @commands.command(name='predict')
    async def pokemon_command(self, ctx, action: str = None, *, arg: str = None):
        if action == 'predict' or action == None:
            await self.predict_pokemon_command(ctx, arg)
        elif action == 'add':
            await self.add_pokemon_command(ctx, arg)
        elif action == 'all':
            await self.download_all_images_command(ctx)
        else:
            embed = discord.Embed(
                title=" ",
                description="Use these commands to interact with Pokémon predictions and database:\n\n"
                            "- **`pokemon predict <url:optional>`**: Predict Pokémon from an image.\n"
                            "- **`pokemon add <pokemon_name>`**: Add a Pokémon to the database.\n"
                            "- **`pokemon all`**: Download all Pokémon images. (in testing)\n\n"
                            "> <:help:1245611726838169642>  Remember to replace `<url>` with a valid image `url (.png, .jpg)` and `<pokemon_name>` with the Pokémon's name.",
                color=discord.Color.green()
            )
           
            await ctx.reply(embed=embed)

            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            


    @commands.command(help="Displays Pokemon dex information.", aliases=['pokdex', 'dex','d'])
    async def pokemon(self, ctx, *, args=None, form=None):   
     # Get the primary color of the bot's icon
     primary_color = self.primary_color()
     async with ctx.typing():
        is_shiny = False
        is_form = False
        is_mega = None

        if not args:
            pokemon_id = random.randint(1, 1021)
        elif args.lower() == "shiny":
            is_shiny = True
            pokemon_id = random.randint(1, 1021)
        else:
            args = args.lower().replace(' ', '-').replace("shiny-","shiny ")
            is_shiny = args.startswith("shiny ")
            is_form = form is not None

            args = args.replace("shiny ", "")
            pokemon_id = args


                 
        folder_path = "Data"
        os.makedirs(folder_path, exist_ok=True)
        pokemon_folder_path = os.path.join(folder_path, "pokemon")
        os.makedirs(pokemon_folder_path, exist_ok=True)
        file_path = os.path.join(pokemon_folder_path, "pokemon.json")

        if not os.path.exists(file_path):
            with open(file_path, 'w') as file:
                file.write("{}")  # Creating an empty JSON file
        
        pokemon_data = {}

        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                pokemon_data = json.load(file)

            if str(pokemon_id) in pokemon_data:
                existing_data = pokemon_data[str(pokemon_id)]
                return await self.send_pokemon_info(ctx, existing_data, type="mega" if is_mega else "shiny" if is_shiny else None,color=primary_color)

        if is_form:
            url = f"https://pokeapi.co/api/v2/pokemon-form/{pokemon_id}-{form}"
        else:
            url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_id}"
         
        response = requests.get(url)
        if response.status_code != 200:
            if is_form:
                
                return await ctx.send(f"Form data not found for `{pokemon_id}`.")
            else:
                return await ctx.send(f"Pokemon `{pokemon_id}` not found.")

        try:
            data = response.json()
            if is_form:
                await self.send_form_pokemon(ctx, data)
            else:
                await self.send_pokemon_info(ctx, data, type="mega" if is_mega else "shiny" if is_shiny else None,color=primary_color)

            # Save or update JSON data in the Pokemon folder
            pokemon_data[str(pokemon_id)] = data

            with open(file_path, 'w') as file:
                json.dump(pokemon_data, file)

        except json.JSONDecodeError:
            if isinstance(pokemon_id, int):
                await ctx.send(f"Failed to parse JSON data for `{pokemon_id}`.")

                
                
    async def send_pokemon_info(self, ctx, data, type, color):
    
     name = data['name'].capitalize()
     id = data['id']

     types = [t['type']['name'].capitalize() for t in data['types']]
     pokemon_type_unformatted = types
     
     formatted_types = "\n".join(types)
    
     abilities = [a['ability']['name'].capitalize() for a in data['abilities']]
    
    
     pokemon_name = name
     base_url = "https://pokeapi.co/api/v2/pokemon-species/"
     if type == "mega":
                        print("Getting Mega Evolution")
                        mega_url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}-mega"
                        mega_response = requests.get(mega_url)
                        print(requests.get(mega_url))
                        if mega_response.status_code == 200:
                            try:
                                mega_data = mega_response.json()
                                data_species = mega_response.json()  # Corrected line

                            except json.JSONDecodeError:
                                await ctx.send(f"Failed to parse JSON data for mega evolution of `{pokemon_name}`.")
                        else:
                            await ctx.send(f"Mega evolution data not found for `{pokemon_name}`.")
     else:
            print("Getting Basic Pokemon")
            url = f"{base_url}{pokemon_name.lower()}/"
            response_species = requests.get(url)
            if response_species.status_code != 200:
             # Fetch form data if species data not found
             url = f"https://pokeapi.co/api/v2/pokemon-form/{pokemon_name.lower()}/"
             form_response = requests.get(url)
             if form_response.status_code == 200:
                 data_species = form_response.json()
            else:
                 data_species = response_species.json()
           
    
             
     if type == "mega":
        print(f"Pokemon {name} is mega")
    
    
     async def title_case_except_all_caps(text):
        words = text.split()
        result = []

        for word in words:
            if word.isupper():
                result.append(word.title())
            else:
                result.append(word)

        return ' '.join(result)

     async def get_pokemon_info(data_species, pokemon_name):
      try:
        flavor = data_species['flavor_text_entries'][0]['flavor_text']
        english_flavor = next(
            (entry['flavor_text'] for entry in data_species['flavor_text_entries'] if entry['language']['name'] == 'en'),
            None
        )

        if english_flavor:
            flavor = english_flavor
            formatted_flavor = ' '.join(flavor.split())
            formatted_description = await capitalize_sentences(formatted_flavor)

            word_replacements = {
                'POKéMON': 'Pokémon',
                'POKé BALL': 'Poké Ball',
                # Add more replacements as needed
            }

            formatted_description = await replace_words(formatted_description, word_replacements)

            return formatted_description
        else:
            await find_pokemon_description(pokemon_name)
      except Exception as e:
        await find_pokemon_description(pokemon_name)
        print(f"Error: An unexpected error occurred - {e}")

        
     async def find_pokemon_description(pokemon_name):
      POKEMON_DIR = "Data/pokemon"
      os.makedirs(POKEMON_DIR, exist_ok=True)
      POKEMON_DESCRIPTION_FILE = os.path.join(POKEMON_DIR, "pokemon_descriptions.txt")

      if not os.path.exists(POKEMON_DESCRIPTION_FILE):
            with open(POKEMON_DESCRIPTION_FILE, 'w') as file:
                file.write("")  # Creating an empty text file          
      with open(POKEMON_DESCRIPTION_FILE, 'r') as file:
        pokemon_name = pokemon_name.lower()
        print(pokemon_name)
        for line in file:
            # Split the line into Pokemon name and description
            pokemon, description = line.strip().split(':', 1)
            
            # Check if the current line's Pokemon name matches the requested name
            if pokemon.strip() == pokemon_name:
                print(f"{pokemon.strip()} : {description.strip()}")
                return description.strip()
            
            else:
                return None
    
      # If the Pokemon name is not found, return None
      return None

     async def replace_words(text, replacements):
        for old_word, new_word in replacements.items():
            text = text.replace(old_word, new_word)
        return text

     async def capitalize_sentences(text):
        sentences = text.split('.')
        capitalized_sentences = '. '.join(sentence.strip().capitalize() for sentence in sentences if sentence.strip())
        return capitalized_sentences

     pokemon_description = await get_pokemon_info(data_species,name) or await find_pokemon_description(pokemon_name) or " "
   
     species_url = data['species']['url']
     species_data = requests.get(species_url).json()
     species_name = species_data['name']
     # Fetch the Pokémon's characteristic
     characteristic_id = id  # You can use the Pokémon's ID as the characteristic ID
     characteristic_url = f'https://pokeapi.co/api/v2/characteristic/{characteristic_id}/'
     characteristic_response = requests.get(characteristic_url)

     if characteristic_response.status_code == 200:
       characteristic_data = characteristic_response.json()
       # Get the English description
       for description in characteristic_data['descriptions']:
                    if description['language']['name'] == 'en':
                        characteristic_description = description['description']
                        break
                    else:
                         characteristic_description = 'No English description available'

     else:
                characteristic_description = 'Characteristic data not found'
        
     if type == "shiny":
      image_url = data['sprites']['other']['official-artwork']['front_shiny']
      image_thumb = data['sprites']['versions']['generation-v']['black-white']['animated']['front_shiny']
     elif type == "mega":
                        print("Getting Mega Evolution")
                        mega_url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}-mega"
                        mega_response = requests.get(mega_url)
                        print(requests.get(mega_url))
                        if mega_response.status_code == 200:
                            try:
                                mega_data = mega_response.json()
                                # Redefine data for mega evolution
                                data = mega_data
                                image_url = mega_data['sprites']['other']['official-artwork']['front_default']
                                image_thumb = mega_data['sprites']['versions']['generation-v']['black-white']['animated']['front_default']
                            except json.JSONDecodeError:
                                await ctx.send(f"Failed to parse JSON data for mega evolution of `{pokemon_name}`.")
                        else:
                            await ctx.send(f"Mega evolution data not found for `{pokemon_name}`.")
     else:
      image_url = data['sprites']['other']['official-artwork']['front_default']
      image_thumb = data['sprites']['versions']['generation-v']['black-white']['animated']['front_default']

   
     height, weight = (float(int(data['height'])) / 10, float(int(data['weight'])) / 10)
     max_stat = 255
     bar_length = 13  # Length of the level bar
     fixed_bar_length = 13

    
     # Mapping for renaming
     stat_name_mapping = {
      "hp": "Hp",
      "special-attack": "Sp. Atk",
      "special-defense": "Sp. Def"
     }
    
     # Bar types
     bar_symbols = {
      0: {
        "front":"<:__:1194757522041618572>",
        "mid": "<:__:1194758504490205364>",
        "end": "<:__:1194758898721239040>"
      },
      1: {
        "front": "<:__:1194759037024206859>",
        "mid": "<:__:1194759109401133136>",
        "end": "<:__:1194759199071141999>"
      }
     }
     # Fixed length for all bars
     # Generate base_stats with modified names and level bars
     base_stats = [
        f"{str(stat_name_mapping.get(stat['stat']['name'], stat['stat']['name']).title()).replace('Hp', 'Health'):<10} {str(stat['base_stat']):>5} {'▒' * int(stat['base_stat'] / max_stat * bar_length)}{'░' * (bar_length - int(stat['base_stat'] / max_stat * bar_length))}" for stat in data['stats']]
     formatted_base_stats = "\n".join(base_stats)
    
     _base_stats =   [f"**{str(stat_name_mapping.get(stat['stat']['name'], stat['stat']['name']).title()).replace('Hp', 'HP')}:** {str(stat['base_stat'])}" for stat in data['stats']]
     basic_base_stats = "\n".join(_base_stats)
   
    

     mot = ctx.guild.get_member(ctx.bot.user.id)
     # color = mot.color
    
     # Define the function to get alternate names
     def get_pokemon_alternate_names(data_species, pokemon_name):
      try:
       if data_species:
        alternate_names = [(name['name'], name['language']['name']) for name in data_species['names']]
        return alternate_names
       else:
        print(f"Error: Unable to retrieve data for {pokemon_name}")
        return None
      except KeyError:
        return None  # or handle the missing key case accordingly
    
     def get_pokemon_species_data(name):
      response = requests.get(f'https://pokeapi.co/api/v2/pokemon-species/{name.lower()}')
      if response.status_code == 200:
        species_data = response.json()
        return species_data
      else:
        return None

            






   
     def get_pokemon_region(data_species,pokemon_name):
 
      if data_species:
       try:
        generation_url = data_species['generation']['url']

        # Fetch information about the generation (region)
        response_generation = requests.get(generation_url)

        if response_generation.status_code == 200:
            data_generation = response_generation.json()
            region_name = data_generation['main_region']['name']
            print("Region Name: ",region_name)
            return region_name
            
        else:
            return None
       except KeyError:
        print(KeyError)
        return None  # or handle the missing key case accordingly
      else:
        return None
     
     region = get_pokemon_region(data_species,name) or None

     language_codes = ["ja", "ja", "ja", "en", "de", "fr"]
      # Define a mapping between language codes and flag emojis
     flag_mapping = {
        "en": "🇬🇧", "fr": "🇫🇷", "es": "🇪🇸", "de": "🇩🇪", "it": "🇮🇹", "ja": "🇯🇵", "ko": "🇰🇷", "zh-Hans": "🇨🇳", "ru": "🇷🇺", "es-MX": "🇲🇽",
        "pt": "🇵🇹", "nl": "🇳🇱", "tr": "🇹🇷", "ar": "🇸🇦", "th": "🇹🇭", "vi": "🇻🇳", "pl": "🇵🇱", "sv": "🇸🇪", "da": "🇩🇰", "no": "🇳🇴",
        "fi": "🇫🇮", "el": "🇬🇷", "id": "🇮🇩", "ms": "🇲🇾", "fil": "🇵🇭", "hu": "🇭🇺", "cs": "🇨🇿", "sk": "🇸🇰", "ro": "🇷🇴", "uk": "🇺🇦",
        "hr": "🇭🇷", "bg": "🇧🇬", "et": "🇪🇪", "lv": "🇱🇻", "lt": "🇱🇹", "sl": "🇸🇮", "mt": "🇲🇹", "sq": "🇦🇱", "mk": "🇲🇰", "bs": "🇧🇦",
        "sr": "🇷🇸", "cy": "🇨🇾", "ga": "🇮🇪", "gd": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "kw": "🇰🇾", "br": "🇧🇷", "af": "🇿🇦", "xh": "🇿🇦", "zu": "🇿🇦",
        "tn": "🇿🇦", "st": "🇿🇦", "ss": "🇿🇦", "nr": "🇿🇦", "nso": "🇿🇦", "ts": "🇿🇦", "ve": "🇿🇦", "xog": "🇺🇬", "lg": "🇺🇬", "ak": "🇬🇭",
        "tw": "🇬🇭", "bm": "🇧🇫", "my": "🇲🇲", "km": "🇰🇭", "lo": "🇱🇦", "am": "🇪🇹", "ti": "🇪🇹", "om": "🇪🇹", "so": "🇸🇴", "sw": "🇰🇪",
        "rw": "🇷🇼", "yo": "🇳🇬", "ig": "🇳🇬", "ha": "🇳🇬", "bn": "🇧🇩", "pa": "🇮🇳", "gu": "🇮🇳", "or": "🇮🇳", "ta": "🇮🇳", "te": "🇮🇳",
         "kn": "🇮🇳", "ml": "🇮🇳", "si": "🇱🇰", "ne": "🇳🇵", "dz": "🇧🇹", "ti": "🇪🇷", "be": "🇧🇾", "kk": "🇰🇿", "uz": "🇺🇿", "ky": "🇰🇬"}

     # Fetch alternative names from the PokeAPI
     alternate_names = get_pokemon_alternate_names(data_species,species_name)
    
     desired_pokemon = name  # Replace with the desired Pokémon name
    

     if alternate_names:
      alt_names_info = {}

      for name, lang in alternate_names:
        # Create a unique key for each name
        key = name.lower()

        flag = flag_mapping.get(lang, None)  # Get the flag for the language, or None if not found

        # Check if the Pokemon name is the same as the language name, and skip it
        if name.lower() != lang.lower() and flag is not None:
            if key not in alt_names_info:
                alt_names_info[key] = f"{flag} {name}"

      # Extract the unique names with their flags
      name_list = sorted(list(alt_names_info.values()), key=lambda x: x.split(' ')[-1])

     # Join the results with newline characters
      alt_names_str = "\n".join(name_list[:6])




     else:
      alt_names_str = "No alternate names available."
      print(alt_names_str)
        
     def organize_pokemon_names_by_region(pokemon_name):
      region = get_pokemon_region(data_species,pokemon_name)
    
      if region:
        result = f"Region: {region.capitalize()}\n"
        
        # Fetch alternative names from the PokeAPI
        alternate_names = get_pokemon_alternate_names(data_species,pokemon_name)

        if alternate_names:
            alt_names_info = {}

            for name, lang in alternate_names:
                key = name.lower()

                flag = flag_mapping.get(lang, None)
                if key not in alt_names_info and flag is not None:
                    alt_names_info[key] = f"{flag} {name.capitalize()}"

            name_list = sorted(list(alt_names_info.values()), key=lambda x: x.split(' ')[1],reverse=True)
            alt_names_str = "\n".join(f"`{name_list}`")
            
            result += alt_names_str
        else:
            result += "No alternate names available."
      else:
        result = "Region information not available."
    
      return result
    
     p = organize_pokemon_names_by_region(name)
     print(p)
     async def get_type_chart(max_retries=3):
      url = 'https://pokeapi.co/api/v2/type'

      for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        type_chart = {}
                        types_data = (await response.json())['results']

                        for type_data in types_data:
                            type_name = type_data['name']
                            effectiveness_url = type_data['url']

                            async with session.get(effectiveness_url) as effectiveness_response:
                                if effectiveness_response.status == 200:
                                    damage_relations = (await effectiveness_response.json())['damage_relations']
                                    type_chart[type_name] = {
                                        'double_damage_to': [],
                                        'half_damage_to': [],
                                        'no_damage_to': [],
                                        'double_damage_from': [],
                                        'half_damage_from': [],
                                        'no_damage_from': []
                                    }

                                    for key, values in damage_relations.items():
                                        for value in values:
                                            type_chart[type_name][key].append(value['name'])

                        return type_chart
                    else:
                        # Handle other HTTP response codes if needed
                        print(f"Error: HTTP request failed with status code {response.status}")
                        return None
        except aiohttp.ClientError as e:
            print(f"Error: aiohttp client error - {e}")
        except Exception as e:
            print(f"Error: An unexpected error occurred - {e}")

        # If the attempt is not the last one, wait for a while before retrying
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

   
    
     def find_pokemon_weaknesses(pokemon_info, type_chart):
      if pokemon_info is None:
        print("Failed to retrieve Pokemon info.")
        return None, None

      types = [t['type']['name'] for t in pokemon_info['types']]

      weaknesses = set()
      strengths = set()

      for pokemon_type in types:
        weaknesses.update(type_chart.get(pokemon_type, {}).get('double_damage_from', []))
        strengths.update(type_chart.get(pokemon_type, {}).get('double_damage_to', []))

      weaknesses.discard('')
 
      # Capitalize the output
      weaknesses = {weakness.capitalize() for weakness in weaknesses}
      strengths = {strength.capitalize() for strength in strengths}

      return weaknesses, strengths

    
    
     type_chart = await get_type_chart()
    
     def get_pokemon_spawn_rate(pokemon_id):
      url = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}/encounters'
      response = requests.get(url)

      if response.status_code == 200:
        data = response.json()
        return data
      else:
        print(f"Error: {response.status_code}")
        return None
    
     spawn_data = get_pokemon_spawn_rate(id)
    
     def get_pokemon_gender_ratio_display(data_species):
      try:
       # Extract gender data
       gender_rate = data_species['gender_rate']

       # Gender rate is an integer representing the likelihood of a Pokemon being female
       # -1: Genderless
       # 0: Always male
       # 1-7: Female ratio (e.g., 1 = 12.5% female, 2 = 25% female, etc.)
       if gender_rate == -1:
        return "Genderless"
       elif gender_rate == 0:
        return "♂️ Male only"
       else:
        female_ratio = (8 - gender_rate) / 8
        male_ratio = gender_rate / 8
        male_percentage = int(female_ratio * 100)
        female_percentage = int(male_ratio * 100)
        if female_percentage == 100:
            return "♀️ Female only"
        elif male_percentage == 100:
            return "♂️ Male only"

        # Create a string representing the gender ratio with Discord markdown
        
        # <:male:1212308647984635986> {male_percentage}% - <:female:1212308708151787550> {female_percentage}%  
        # ♂ {male_percentage}% - ♀ {female_percentage}%
        gender_ratio_display = f"♂ {male_percentage}% - ♀ {female_percentage}%"

        return gender_ratio_display
      except KeyError:
        return None  # or handle the missing key case accordingly
     gender = get_pokemon_gender_ratio_display(data_species) or None

    
    
     def determine_pokemon_category(data_species):
      try: 
       pokemon_info = data_species
    
       if pokemon_info:
        if pokemon_info['is_legendary']:
            return "Legendary"
        elif pokemon_info['is_mythical']:
            return f"Mythical"
        else:
            flavor_text_entries = pokemon_info['flavor_text_entries']
            english_flavor = next((entry['flavor_text'] for entry in flavor_text_entries if entry['language']['name'] == 'en'), None)
            if english_flavor and 'ultra beast' in english_flavor.lower():
                return f"Ultra Beast"
            else:
                return None
       else:
         return None
      except KeyError:
         return None  # or handle the missing key case accordingly
        
     rarity = determine_pokemon_category(data_species) or None
    

    

   
     if pokemon_description != " ":
        
      embed = discord.Embed(title=f" #{id} — {species_name.title()}" if type != "shiny" else f" #{id} — ✨ {species_name.title()}" , description=f'\n{pokemon_description}.\n',color=color)  # Blue color
     else:
             embed = discord.Embed(title=f" #{id} — {species_name.title()}" if type != "shiny" else f" #{id} — ✨ {species_name.title()}", color=color)  
   
            
     pokemon_dex_name = f" #{id} — {species_name.title()}" if type != "shiny" else f" #{id} — ✨ {species_name.title()}"
     embed.set_image(url=image_url)  
     description= f'\n{pokemon_description}.\n'if pokemon_description != " " else None

    
     # Information about the Pokémon itself
    
     """
      [Gender] [Apperence]
     
      [Rarity] [Region]    [Names] 
     
     
      [Names]

    
     """
     type_chart = await get_type_chart()
     pokemon_info = data
     weaknesses, strengths = find_pokemon_weaknesses(pokemon_info, type_chart)
     label_width = max(len("Type"), len("Weaknesses"), len("Strengths"))

    
    
     result = (
      "● Strengths\n"
      "{2}"
      "{3}\n\n"
      "● Weaknesses\n"
      "{4}"
      "{5}"
      )
     weaknesses = list(weaknesses)
     strengths = list(strengths)

     if len(weaknesses) == 1:
      weaknesses_formatted = f'╚ {weaknesses[0]}'
     else:
      weaknesses_formatted = '\n'.join([f'╠ {weakness}' for weakness in weaknesses[:-1]]) + (f'\n╚ {weaknesses[-1]}' if weaknesses else '╚ None')
     if len(strengths) == 1:
      strengths_formatted = f'╚ {strengths[0]}'
     else:
      strengths_formatted = '\n'.join([f'╠ {strength}' for strength in strengths[:-1]]) + (f'\n╚ {strengths[-1]}' if strengths else '╚ None')
     wes = result.format(
      '',
      '',
      strengths_formatted,
      '',
      weaknesses_formatted,
      ''
      )
     
     pokemon_type_result = (
      "● Type\n"
      "{2}\n\n"
     )
     if len(pokemon_type_unformatted) == 1:
      pokemon_types_formatted = f'╚ {pokemon_type_unformatted[0]}'
     else:
      pokemon_types_formatted = '\n'.join([f'╠ {types}' for types in pokemon_type_unformatted[:-1]]) + (f'\n╚ {pokemon_type_unformatted[-1]}' if pokemon_type_unformatted else '╚ None')

     pokemon_type = pokemon_type_result.format('', '', pokemon_types_formatted)
     print(pokemon_type)


     """" Weakness stuff  """
     weaknesses, _ = find_pokemon_weaknesses(pokemon_info, type_chart)

     result = "{0}"

     weaknesses_formatted = '\n'.join([f'    {i}. {weakness}' for i, weakness in enumerate(weaknesses, start=1)]) if weaknesses else 'None'

     output_weak = result.format(weaknesses_formatted)
     print(output_weak)
    
     """" Strengths stuff  """
     _ , strengths = find_pokemon_weaknesses(pokemon_info, type_chart)

     result = "{0}"

     strengths_formatted = '\n'.join([f'    {i}. {strength}' for i, strength in enumerate(strengths, start=1)]) if strengths else 'None'

     output_strength = result.format(strengths_formatted)
     print(output_strength)
    





     s_and_w = wes

     # Define the mappings
     region_mappings = {
      "Paldea": "<:Paldea:1212335178714980403>",
      "Sinnoh": "<:Sinnoh:1212335180459544607>",
      "Alola": "<:Alola:1212335185228472411>",
      "Kalos": "<:Kalos:1212335190656024608>",
      "Galar": "<:Galar:1212335192740470876>",
      "Pasio": "<:848495108667867139:1212335194628034560>",
      "Hoenn": "<:Hoenn:1212335197304004678>",
      "Unova": "<:Unova:1212335199095095306>",
      "Kanto": "<:Kanto:1212335202341363713>",
      "Johto": "<:Kanto:1212335202341363713>"
     } 
     if region:
        region = region.title()
     else:
        region = None
        
     appearance_info = [
      f"**Height:** {height:.2f} m",
      f"**Weight:** {weight:.2f} kg"
     ]
     appearance = '\n'.join(appearance_info)
    
     # embed.add_field(name='Type', value=f"{formatted_types}", inline=True)
   

     if region != None:
        if region in region_mappings:
           region_emoji = region_mappings[region]
           embed.add_field(name='Region', value=f"{region_emoji} {region}", inline=True)
           region = f"{region_emoji} {region}" or region

        
     embed.add_field(name='Names', value=alt_names_str, inline=True)
    
   
    
    
     if gender != None:
        if gender != "♀️ Female only" or "♂️ Male only" or "Genderless":
           gender_differ = True
        else:
            gender_differ = False
     else:
        gender_differ = False
        
     spawn_data = get_pokemon_spawn_rate(id)
     
    
     # embed.add_field(name='', value=f"```Type: {formatted_types}```",inline=False)
     base_stats = formatted_base_stats
    
     # Include alternate names



  
     appearance = f"Height: {height:.2f} m\nWeight: {weight:.2f} kg\t\t" if gender is not None and gender != "♂ 50% - ♀ 50%" else f"Height: {height:.2f} m\nWeight: {weight:.2f} kg"

     gender_info = None

     if image_thumb:

        embed.set_footer(icon_url=image_thumb,text=appearance)
        gender_info = None
        if gender != None and gender != "♂ 50% - ♀ 50%":
                    embed.set_footer(icon_url=image_thumb,text= appearance + f"Gender: {gender}")
                    appearance_footer = embed.set_footer(icon_url=image_thumb,text= appearance + f"Gender: {gender}")
                    gender_info =  f"Gender: {gender}"

     else:
        if type == "shiny":
         image_thumb = data['sprites']['versions']['generation-v']['black-white']['front_shiny']
        else:
         image_thumb = data['sprites']['versions']['generation-v']['black-white']['front_default']
        
        if image_thumb: 
         embed.set_footer(icon_url=image_thumb,text=appearance)
        else:
         image_thumb = None
         embed.set_footer(text=appearance)

        
        if gender and rarity != None and gender != "♂ 50% - ♀ 50%":

           embed.set_footer(icon_url=image_thumb,text=f"Rarity: {rarity}\n\n" + appearance + f"Gender: {gender}")
           appearance_footer = embed.set_footer(icon_url=image_thumb,text=f"Rarity: {rarity}\n\n" + appearance + f"Gender: {gender}")
           gender_info =  f"Gender: {gender}"

        elif  gender != None and gender != "♂ 50% - ♀ 50%":
            
           embed.set_footer(icon_url=image_thumb,text= appearance + f"Gender: {gender}")
           appearance_footer = embed.set_footer(icon_url=image_thumb,text= appearance + f"Gender: {gender}")
           gender_info =  f"Gender: {gender}"

           

    
     h_w = f"Height: {height:.2f} m\nWeight: {weight:.2f} kg"
     print('is_shiny: ',type)      
     self.bot.add_view(Pokebuttons(alt_names_str,species_name))
     
     await ctx.reply(embed=embed,view=Pokebuttons(alt_names_str,species_name,formatted_base_stats,type,wes,pokemon_type,base_stats,image_url,h_w,image_thumb,pokemon_dex_name,color,data,gender_differ,region, description,gender_info))
    
