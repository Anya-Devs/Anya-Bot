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


