import os
import io
import cv2
import numpy as np
from PIL import Image
import logging

from Imports.discord_imports import *
from Imports.log_imports import logger

from skimage.metrics import structural_similarity as ssim


import asyncio
import aiohttp

class PokemonPredictor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.image_folder = 'Data/pokemon_images'
        logger.info("Initializing PokemonPredictor...")
        
    @staticmethod
    async def fetch_pokemon_info(pokemon_name):
        url = f"https://pokeapi.co/api/v2/pokemon/{pokemon_name.lower()}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    official_artwork_url = data['sprites']['other']['official-artwork']['front_default']
                    return official_artwork_url
                else:
                    return None

    async def download_all_images(self):
        pokemon_names = await self.fetch_all_pokemon_names()
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

        async with aiohttp.ClientSession() as session:
            for pokemon_name in pokemon_names:
                filename = f"{pokemon_name}.png"
                filepath = os.path.join(self.image_folder, filename)
                if not os.path.exists(filepath):
                    official_artwork_url = await self.fetch_pokemon_info(pokemon_name)
                    if official_artwork_url:
                        async with session.get(official_artwork_url) as response:
                            if response.status == 200:
                                image_data = await response.read()
                                with open(filepath, 'wb') as f:
                                    f.write(image_data)
                                logger.info(f"Downloaded image for {pokemon_name}.")
                            else:
                                logger.error(f"Failed to download image for {pokemon_name}.")
                    else:
                        logger.error(f"Failed to fetch information for the Pokémon {pokemon_name}.")
                else:
                    logger.info(f"Image for {pokemon_name} already exists, skipping download.")

    async def predict_pokemon(self, ctx, img, threshold=0.8):
     try:
        logger.debug("Predicting Pokémon from provided image...")
        async with ctx.typing():  # Activate typing indicator
            if not os.path.exists(self.image_folder):
                os.makedirs(self.image_folder)

            pokemon_files = os.listdir(self.image_folder)
            logger.debug(f"Number of Pokémon images found: {len(pokemon_files)}")

            best_match = None
            highest_score = 0

            img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            img = cv2.resize(img, (224, 224))

            orb = cv2.ORB_create()

            keypoints1, descriptors1 = orb.detectAndCompute(img, None)

            for pokemon_file in pokemon_files:
                pokemon_name, _ = os.path.splitext(pokemon_file)
                stored_img_path = os.path.join(self.image_folder, pokemon_file)
                stored_img = Image.open(stored_img_path)
                stored_img = stored_img.convert("RGBA") if stored_img.mode == "P" else stored_img
                stored_img = stored_img.resize((224, 224)).convert('RGB')
                stored_img = cv2.cvtColor(np.array(stored_img), cv2.COLOR_RGB2BGR)

                keypoints2, descriptors2 = orb.detectAndCompute(stored_img, None)

                if descriptors1 is not None and descriptors2 is not None:
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                    matches = bf.match(descriptors1, descriptors2)
                    matches = sorted(matches, key=lambda x: x.distance)

                    if matches:
                        score = len(matches) / len(descriptors1)
                        logger.debug(f"Matching score for {pokemon_name}: {score:.2%}")

                        if score < highest_score:
                            highest_score = score
                            best_match = pokemon_name

                        if highest_score >= threshold:
                            break

            logger.info(f"Best match: {best_match} with score {highest_score:.2%}")
            return best_match, highest_score

     except Exception as e:
        logger.error(f"An error occurred during prediction: {e}")
        return None, 0

    def calculate_ssim(self, img1, img2):
     img1_gray = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
     img2_gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
     ssim_score, _ = ssim(img1_gray, img2_gray, full=True)
     logger.debug(f"Calculated SSIM score: {ssim_score:.2%}")
     return ssim_score


    @commands.command(name='predict')
    async def predict(self, ctx):
        # Initial message asking the user to provide an image
        embed = discord.Embed(
            title="Predict Pokémon",
            description="Please send an image of the Pokémon to predict.\n\nType `c` to cancel.",
            color=discord.Color.blue()
        )
        progress_message = await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            user_response = await self.bot.wait_for('message', timeout=120, check=check)

            if user_response.content.lower() == 'c':
                await ctx.send("Operation cancelled.")
                logger.debug("User cancelled the operation.")
                return

            if user_response.attachments:
                attachment = user_response.attachments[0]
                if attachment.filename.endswith(('png', 'jpg', 'jpeg')):
                    img_bytes = await attachment.read()
                    img = Image.open(io.BytesIO(img_bytes))
                    img = img.resize((224, 224))
                    img = np.array(img.convert('RGB'))  # Convert to RGB
                    logger.debug("Image received and processed from attachment.")
                else:
                    await ctx.send("Please attach a valid image file.")
                    logger.debug("Invalid image file attached.")
                    return
            else:
                await ctx.send("Please attach an image.")
                logger.debug("No valid image provided.")
                return

            # Perform prediction
            predicted_pokemon, confidence_score = await self.predict_pokemon(ctx,img)

            # If prediction is successful, send success message with prediction result
            if predicted_pokemon:
                success_embed = discord.Embed(
                    title="Prediction Result",
                    description=f"The predicted Pokémon is: **{predicted_pokemon}** with a confidence score of **{confidence_score:.2%}**.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=success_embed)
                logger.info(f"Prediction result sent: {predicted_pokemon} with score {confidence_score:.2%}")
            else:
                # If prediction fails, send failure message
                failure_embed = discord.Embed(
                    title="Prediction Failed",
                    description="Failed to predict the Pokémon. Please try again with a different image.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=failure_embed)
                logger.error("Prediction failed.")

        except asyncio.TimeoutError:
            await ctx.send("Time's up. Operation cancelled.")
            logger.info("Timeout occurred. Operation cancelled.")

    @commands.command(name='add')
    async def add_pokemon(self, ctx, pokemon_name: str):
     logger.info(f"Attempting to add Pokémon: {pokemon_name}")
     filename = f"{pokemon_name}.png"
     filepath = os.path.join(self.image_folder, filename)
    
     try:
        # Create the directory if it doesn't exist
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)

        if os.path.exists(filepath):
            await ctx.send(f"The Pokémon {pokemon_name} already exists in the database.")
            logger.debug(f"The Pokémon {pokemon_name} already exists in the database.")
            return

        official_artwork_url = await self.fetch_pokemon_info(pokemon_name)
        logger.debug(f"Official artwork URL for {pokemon_name}: {official_artwork_url}")
        
        if official_artwork_url:
            async with aiohttp.ClientSession() as session:
                async with session.get(official_artwork_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        with open(filepath, 'wb') as f:
                            f.write(image_data)
                        await ctx.send(f"Added the Pokémon {pokemon_name} to the database.")
                        logger.info(f"Added the Pokémon {pokemon_name} to the database.")
                    else:
                        await ctx.send("Failed to download the image.")
                        logger.error("Failed to download the image.")
        else:
            await ctx.send(f"Failed to fetch information for the Pokémon {pokemon_name}.")
            logger.error(f"Failed to fetch information for the Pokémon {pokemon_name}.")
            
     except Exception as e:
        await ctx.send("An error occurred while adding the Pokémon. Please try again later.")
        logger.error(f"An error occurred while adding the Pokémon {pokemon_name}: {e}")

    
    @commands.command(name='all')
    async def download_images(self, ctx):
        await ctx.send("Starting download of all Pokémon images. This may take a while.")
        await self.download_all_images()
        await ctx.send("Completed download of all Pokémon images.")

def setup(bot):
    bot.add_cog(PokemonPredictor(bot))
